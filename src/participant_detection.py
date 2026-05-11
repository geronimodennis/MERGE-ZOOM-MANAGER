from dataclasses import dataclass
from typing import Iterable, List, Tuple

import cv2
import numpy as np

from models import ParticipantTile, Rect


@dataclass
class DetectionCandidate:
    rect: Rect
    score: float
    reason: str


class ZoomGalleryDetector:
    """Detect participant rectangles from the current Zoom Gallery View frame."""

    def __init__(
        self,
        min_area_ratio: float = 0.004,
        max_area_ratio: float = 0.95,
        min_aspect_ratio: float = 0.45,
        max_aspect_ratio: float = 3.4,
        background_tolerance: int = 18,
    ):
        self.min_area_ratio = min_area_ratio
        self.max_area_ratio = max_area_ratio
        self.min_aspect_ratio = min_aspect_ratio
        self.max_aspect_ratio = max_aspect_ratio
        self.background_tolerance = background_tolerance

    def detect(self, image: np.ndarray, source_key: str = "", frame_index: int = 0) -> List[ParticipantTile]:
        if image is None or image.size == 0:
            return []

        candidates = []
        candidates.extend(self._detect_from_projection(image))
        candidates.extend(self._detect_from_edges(image))
        candidates = self._consolidate_candidates(image, candidates)
        candidates = self._remove_containing_boxes(self._dedupe(candidates))
        candidates.sort(key=lambda item: (item.rect[1], item.rect[0]))

        tiles: List[ParticipantTile] = []
        for candidate in candidates:
            x, y, width, height = candidate.rect
            crop = image[y : y + height, x : x + width].copy()
            if crop.size == 0:
                continue
            tiles.append(
                ParticipantTile(
                    track_id=None,
                    source_key=source_key,
                    rect=candidate.rect,
                    crop=crop,
                    confidence=candidate.score,
                    descriptor=self.build_descriptor(crop),
                    frame_index=frame_index,
                    debug_reason=candidate.reason,
                )
            )
        return tiles

    def build_descriptor(self, crop: np.ndarray) -> np.ndarray:
        if crop is None or crop.size == 0:
            return np.zeros(1, dtype=np.float32)

        thumb = cv2.resize(crop, (32, 18), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(thumb, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        gray -= float(gray.mean())
        std = float(gray.std())
        if std > 0.001:
            gray /= std

        hist = cv2.calcHist([thumb], [0, 1, 2], None, [4, 4, 4], [0, 256, 0, 256, 0, 256])
        hist = cv2.normalize(hist, hist).flatten().astype(np.float32)
        return np.concatenate([gray.flatten(), hist])

    def _detect_from_projection(self, image: np.ndarray) -> List[DetectionCandidate]:
        mask = self._foreground_mask(image)
        image_height, image_width = mask.shape[:2]
        x_segments = self._segments_from_projection(mask, axis=0)
        y_segments = self._segments_from_projection(mask, axis=1)

        candidates: List[DetectionCandidate] = []
        for x1, x2 in x_segments:
            for y1, y2 in y_segments:
                width = x2 - x1
                height = y2 - y1
                rect = (x1, y1, width, height)
                if not self._is_valid_rect(rect, image_width, image_height):
                    continue

                density = float(np.count_nonzero(mask[y1:y2, x1:x2])) / max(1, width * height)
                if density < 0.04:
                    continue
                candidates.append(DetectionCandidate(rect, min(0.99, 0.55 + density), "projection"))
        return candidates

    def _detect_from_edges(self, image: np.ndarray) -> List[DetectionCandidate]:
        image_height, image_width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(gray, 45, 140)

        kernel_size = max(3, min(image_width, image_height) // 180)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: List[DetectionCandidate] = []
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            rect = (x, y, width, height)
            if not self._is_valid_rect(rect, image_width, image_height):
                continue
            area_ratio = (width * height) / float(image_width * image_height)
            candidates.append(DetectionCandidate(rect, min(0.9, 0.45 + area_ratio), "edge"))
        return candidates

    def _consolidate_candidates(
        self,
        image: np.ndarray,
        candidates: List[DetectionCandidate],
    ) -> List[DetectionCandidate]:
        candidates = self._remove_containing_boxes(self._dedupe(candidates))
        if len(candidates) <= 1 or self._candidates_look_like_tiles(candidates):
            return candidates

        image_height, image_width = image.shape[:2]
        union = self._expand_to_tile_rect(self._union_rect([candidate.rect for candidate in candidates]), image_width, image_height)
        if self._is_valid_rect(union, image_width, image_height) and self._has_meaningful_content(image, union):
            return [DetectionCandidate(union, 0.92, "fragment-union")]

        return candidates

    @staticmethod
    def _union_rect(rects: List[Rect]) -> Rect:
        x1 = min(rect[0] for rect in rects)
        y1 = min(rect[1] for rect in rects)
        x2 = max(rect[0] + rect[2] for rect in rects)
        y2 = max(rect[1] + rect[3] for rect in rects)
        return x1, y1, x2 - x1, y2 - y1

    def _expand_to_tile_rect(self, rect: Rect, image_width: int, image_height: int) -> Rect:
        x, y, width, height = rect
        margin_x = max(4, int(image_width * 0.008))
        margin_y = max(4, int(image_height * 0.008))
        x -= margin_x
        y -= margin_y
        width += margin_x * 2
        height += margin_y * 2

        target_aspect = 16.0 / 9.0
        aspect = width / float(max(1, height))
        center_x = x + width / 2.0
        center_y = y + height / 2.0

        if aspect < 1.15:
            width = int(height * target_aspect)
        elif aspect > 2.35:
            height = int(width / target_aspect)

        x = int(round(center_x - width / 2.0))
        y = int(round(center_y - height / 2.0))
        x = max(0, min(x, image_width - 1))
        y = max(0, min(y, image_height - 1))
        width = min(width, image_width - x)
        height = min(height, image_height - y)
        return x, y, max(1, int(width)), max(1, int(height))

    @staticmethod
    def _candidates_look_like_tiles(candidates: List[DetectionCandidate]) -> bool:
        if len(candidates) <= 1:
            return True

        widths = np.array([candidate.rect[2] for candidate in candidates], dtype=np.float32)
        heights = np.array([candidate.rect[3] for candidate in candidates], dtype=np.float32)
        areas = widths * heights
        aspects = widths / np.maximum(1.0, heights)

        width_cv = float(np.std(widths) / max(1.0, np.mean(widths)))
        height_cv = float(np.std(heights) / max(1.0, np.mean(heights)))
        area_cv = float(np.std(areas) / max(1.0, np.mean(areas)))
        sane_aspects = bool(np.all((aspects >= 1.05) & (aspects <= 2.45)))
        return sane_aspects and width_cv < 0.28 and height_cv < 0.28 and area_cv < 0.45

    def _has_meaningful_content(self, image: np.ndarray, rect: Rect) -> bool:
        x, y, width, height = rect
        crop = image[y : y + height, x : x + width]
        if crop.size == 0:
            return False
        mask = self._foreground_mask(crop)
        density = float(np.count_nonzero(mask)) / max(1, width * height)
        return density >= 0.015

    def _foreground_mask(self, image: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]
        border = max(2, min(height, width) // 80)
        samples = np.concatenate(
            [
                image[:border, :, :].reshape(-1, 3),
                image[-border:, :, :].reshape(-1, 3),
                image[:, :border, :].reshape(-1, 3),
                image[:, -border:, :].reshape(-1, 3),
            ],
            axis=0,
        )
        background = np.median(samples, axis=0)
        diff = np.max(np.abs(image.astype(np.int16) - background.astype(np.int16)), axis=2)
        mask = (diff > self.background_tolerance).astype(np.uint8) * 255

        kernel_side = max(3, min(width, height) // 100)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_side, kernel_side))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        return mask

    def _segments_from_projection(self, mask: np.ndarray, axis: int) -> List[Tuple[int, int]]:
        if axis == 0:
            projection = np.mean(mask > 0, axis=0)
            length = mask.shape[1]
        else:
            projection = np.mean(mask > 0, axis=1)
            length = mask.shape[0]

        smooth_width = max(3, length // 200)
        kernel = np.ones(smooth_width, dtype=np.float32) / smooth_width
        smoothed = np.convolve(projection, kernel, mode="same")
        threshold = max(0.025, min(0.25, float(np.max(smoothed)) * 0.08))
        high = smoothed > threshold

        segments = self._runs(high)
        min_len = max(24, length // 30)
        max_gap = max(2, length // 260)
        merged = self._merge_close_segments(segments, max_gap)
        return [(start, end) for start, end in merged if end - start >= min_len]

    @staticmethod
    def _runs(values: Iterable[bool]) -> List[Tuple[int, int]]:
        runs: List[Tuple[int, int]] = []
        start = None
        for index, value in enumerate(values):
            if value and start is None:
                start = index
            elif not value and start is not None:
                runs.append((start, index))
                start = None
        if start is not None:
            runs.append((start, len(values)))
        return runs

    @staticmethod
    def _merge_close_segments(segments: List[Tuple[int, int]], max_gap: int) -> List[Tuple[int, int]]:
        if not segments:
            return []
        merged = [segments[0]]
        for start, end in segments[1:]:
            prev_start, prev_end = merged[-1]
            if start - prev_end <= max_gap:
                merged[-1] = (prev_start, end)
            else:
                merged.append((start, end))
        return merged

    def _is_valid_rect(self, rect: Rect, image_width: int, image_height: int) -> bool:
        x, y, width, height = rect
        if width <= 0 or height <= 0:
            return False
        if x < 0 or y < 0 or x + width > image_width or y + height > image_height:
            return False

        min_width = max(48, int(image_width * 0.045))
        min_height = max(42, int(image_height * 0.05))
        if width < min_width or height < min_height:
            return False

        area_ratio = (width * height) / float(max(1, image_width * image_height))
        if area_ratio < self.min_area_ratio or area_ratio > self.max_area_ratio:
            return False

        aspect_ratio = width / float(height)
        return self.min_aspect_ratio <= aspect_ratio <= self.max_aspect_ratio

    def _dedupe(self, candidates: List[DetectionCandidate]) -> List[DetectionCandidate]:
        candidates = sorted(candidates, key=lambda item: item.score, reverse=True)
        keep: List[DetectionCandidate] = []
        for candidate in candidates:
            if any(self._iou(candidate.rect, other.rect) > 0.55 for other in keep):
                continue
            keep.append(candidate)
        return keep

    def _remove_containing_boxes(self, candidates: List[DetectionCandidate]) -> List[DetectionCandidate]:
        result: List[DetectionCandidate] = []
        for candidate in candidates:
            contained = [
                other
                for other in candidates
                if other is not candidate
                and self._contains(candidate.rect, other.rect)
                and other.rect[2] * other.rect[3] < candidate.rect[2] * candidate.rect[3] * 0.75
            ]
            if len(contained) >= 2:
                continue
            result.append(candidate)
        return result

    @staticmethod
    def _contains(outer: Rect, inner: Rect) -> bool:
        ox, oy, ow, oh = outer
        ix, iy, iw, ih = inner
        return ox <= ix and oy <= iy and ox + ow >= ix + iw and oy + oh >= iy + ih

    @staticmethod
    def _iou(a: Rect, b: Rect) -> float:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        x1 = max(ax, bx)
        y1 = max(ay, by)
        x2 = min(ax + aw, bx + bw)
        y2 = min(ay + ah, by + bh)
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        union = aw * ah + bw * bh - intersection
        return intersection / float(union) if union else 0.0
