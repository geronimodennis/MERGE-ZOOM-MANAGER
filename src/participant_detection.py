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
