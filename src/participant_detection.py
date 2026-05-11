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

        gallery_roi = self._gallery_search_roi(image)
        candidates = []
        candidates.extend(self._detect_from_projection(image, gallery_roi))
        candidates.extend(self._detect_from_edges(image, gallery_roi))
        gallery_rect_candidates = self._detect_from_gallery_rectangles(image, gallery_roi)
        zoom_layout_candidates = self._detect_from_zoom_name_badges(image, candidates, gallery_roi)

        if gallery_rect_candidates and len(gallery_rect_candidates) >= len(zoom_layout_candidates):
            candidates = gallery_rect_candidates
        elif zoom_layout_candidates:
            candidates = zoom_layout_candidates
        else:
            candidates = self._consolidate_candidates(image, candidates)
        candidates = [candidate for candidate in candidates if self._rect_inside_roi(candidate.rect, gallery_roi)]
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

    def _detect_from_projection(self, image: np.ndarray, roi: Rect | None = None) -> List[DetectionCandidate]:
        roi_x, roi_y, roi_width, roi_height = self._normalize_roi(image, roi)
        search_image = image[roi_y : roi_y + roi_height, roi_x : roi_x + roi_width]
        if search_image.size == 0:
            return []

        mask = self._foreground_mask(search_image)
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
                absolute_rect = (x1 + roi_x, y1 + roi_y, width, height)
                candidates.append(DetectionCandidate(absolute_rect, min(0.99, 0.55 + density), "projection"))
        return candidates

    def _detect_from_edges(self, image: np.ndarray, roi: Rect | None = None) -> List[DetectionCandidate]:
        roi_x, roi_y, roi_width, roi_height = self._normalize_roi(image, roi)
        search_image = image[roi_y : roi_y + roi_height, roi_x : roi_x + roi_width]
        if search_image.size == 0:
            return []

        image_height, image_width = search_image.shape[:2]
        gray = cv2.cvtColor(search_image, cv2.COLOR_BGR2GRAY)
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
            absolute_rect = (x + roi_x, y + roi_y, width, height)
            candidates.append(DetectionCandidate(absolute_rect, min(0.9, 0.45 + area_ratio), "edge"))
        return candidates

    def _detect_from_gallery_rectangles(self, image: np.ndarray, roi_rect: Rect | None = None) -> List[DetectionCandidate]:
        image_height, image_width = image.shape[:2]
        roi_x, roi_y, roi_width, roi_height = self._normalize_roi(image, roi_rect)
        roi = image[roi_y : roi_y + roi_height, roi_x : roi_x + roi_width]
        if roi.size == 0:
            return []

        background = self._estimate_border_color(roi)
        diff = np.max(np.abs(roi.astype(np.int16) - background.astype(np.int16)), axis=2)
        mask = (diff > 8).astype(np.uint8) * 255

        kernel_width = max(9, roi_width // 120)
        kernel_height = max(5, roi_height // 120)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, kernel_height))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: List[DetectionCandidate] = []
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            contour_area = cv2.contourArea(contour)
            fill_ratio = contour_area / float(max(1, width * height))
            if fill_ratio < 0.28:
                continue

            absolute_rect = (x + roi_x, y + roi_y, width, height)
            candidates.extend(self._candidate_rects_from_gallery_rect(absolute_rect, image_width, image_height))

        candidates = self._dedupe(candidates)
        candidates.sort(key=lambda item: (item.rect[1], item.rect[0]))
        return candidates

    def _candidate_rects_from_gallery_rect(
        self,
        rect: Rect,
        image_width: int,
        image_height: int,
    ) -> List[DetectionCandidate]:
        x, y, width, height = rect
        aspect = width / float(max(1, height))
        if aspect > 2.45:
            target_width = max(1, int(round(height * 16.0 / 9.0)))
            columns = int(round(width / float(target_width)))
            if columns >= 2:
                split_width = width / float(columns)
                split_candidates = []
                for column in range(columns):
                    split_x = int(round(x + column * split_width))
                    next_x = int(round(x + (column + 1) * split_width))
                    split_rect = (split_x, y, max(1, next_x - split_x), height)
                    if self._is_gallery_card_rect(split_rect, image_width, image_height):
                        split_candidates.append(DetectionCandidate(split_rect, 0.97, "gallery-rectangle-split"))
                if split_candidates:
                    return split_candidates

        if self._is_gallery_card_rect(rect, image_width, image_height):
            return [DetectionCandidate(rect, 0.98, "gallery-rectangle")]
        return []

    def _is_gallery_card_rect(self, rect: Rect, image_width: int, image_height: int) -> bool:
        x, y, width, height = rect
        if width < max(90, int(image_width * 0.08)):
            return False
        if height < max(70, int(image_height * 0.08)):
            return False

        aspect = width / float(max(1, height))
        if not (1.12 <= aspect <= 2.35):
            return False
        if abs(width - height) < min(width, height) * 0.18:
            return False
        return self._is_valid_rect(rect, image_width, image_height)

    @staticmethod
    def _estimate_border_color(image: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]
        border = max(3, min(height, width) // 60)
        samples = np.concatenate(
            [
                image[:border, :, :].reshape(-1, 3),
                image[-border:, :, :].reshape(-1, 3),
                image[:, :border, :].reshape(-1, 3),
                image[:, -border:, :].reshape(-1, 3),
            ],
            axis=0,
        )
        return np.median(samples, axis=0)

    @staticmethod
    def _gallery_search_roi(image: np.ndarray) -> Rect:
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        content_start = int(height * 0.18)
        content_end = max(content_start + 1, int(height * 0.82))
        content_median = float(np.median(gray[content_start:content_end, :]))
        tolerance = 10.0

        top = 0
        top_limit = min(int(height * 0.20), 190)
        for y in range(0, top_limit):
            band = gray[y : min(height, y + 8), :]
            if band.size and abs(float(np.median(band)) - content_median) <= tolerance:
                top = max(0, y - 2)
                break

        bottom = height
        bottom_limit = max(0, height - min(int(height * 0.22), 240))
        for y in range(height - 1, bottom_limit, -1):
            band = gray[max(0, y - 8) : y + 1, :]
            if band.size and abs(float(np.median(band)) - content_median) <= tolerance:
                bottom = min(height, y + 2)
                break

        if bottom - top < height * 0.35:
            top = int(height * 0.07)
            bottom = int(height * 0.92)

        activity_top, activity_bottom = ZoomGalleryDetector._chrome_activity_bounds(image)
        top = max(top, activity_top)
        bottom = min(bottom, activity_bottom)

        if bottom - top < height * 0.35:
            top = int(height * 0.07)
            bottom = int(height * 0.92)

        return 0, top, width, max(1, bottom - top)

    @staticmethod
    def _chrome_activity_bounds(image: np.ndarray) -> Tuple[int, int]:
        height = image.shape[0]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        bright_pixels = gray > 145
        row_activity = np.mean(bright_pixels, axis=1)

        window = max(5, height // 180)
        if window % 2 == 0:
            window += 1
        kernel = np.ones(window, dtype=np.float32) / float(window)
        smooth = np.convolve(row_activity, kernel, mode="same")
        threshold = max(0.003, min(0.035, float(np.percentile(smooth, 97)) * 0.35))

        top_limit = min(int(height * 0.18), 190)
        bottom_limit = max(0, height - min(int(height * 0.20), 230))
        edge_zone = max(18, int(height * 0.035))
        quiet_run = max(18, int(height * 0.025))
        padding = max(6, int(height * 0.008))

        top = 0
        top_active = smooth[:top_limit] > threshold
        if top_active.size and bool(np.any(top_active[:edge_zone])):
            top = ZoomGalleryDetector._activity_boundary_from_top(top_active, quiet_run, padding)
            top = max(top, min(top_limit, int(height * 0.085)))

        bottom = height
        bottom_active = smooth[bottom_limit:] > threshold
        if bottom_active.size and bool(np.any(bottom_active[-edge_zone:])):
            local_bottom = ZoomGalleryDetector._activity_boundary_from_bottom(bottom_active, quiet_run, padding)
            bottom = bottom_limit + local_bottom
            bottom = min(bottom, max(bottom_limit, height - int(height * 0.105)))

        return min(top, top_limit), max(bottom, bottom_limit)

    @staticmethod
    def _activity_boundary_from_top(active_rows: np.ndarray, quiet_run: int, padding: int) -> int:
        seen_active = False
        last_active = 0
        quiet_count = 0

        for y, active in enumerate(active_rows):
            if active:
                seen_active = True
                last_active = y
                quiet_count = 0
            elif seen_active:
                quiet_count += 1
                if quiet_count >= quiet_run:
                    break

        return last_active + padding if seen_active else 0

    @staticmethod
    def _activity_boundary_from_bottom(active_rows: np.ndarray, quiet_run: int, padding: int) -> int:
        seen_active = False
        first_active = len(active_rows)
        quiet_count = 0

        for y in range(len(active_rows) - 1, -1, -1):
            if active_rows[y]:
                seen_active = True
                first_active = y
                quiet_count = 0
            elif seen_active:
                quiet_count += 1
                if quiet_count >= quiet_run:
                    break

        return max(0, first_active - padding) if seen_active else len(active_rows)

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

    def _detect_from_zoom_name_badges(
        self,
        image: np.ndarray,
        content_candidates: List[DetectionCandidate],
        roi: Rect | None = None,
    ) -> List[DetectionCandidate]:
        gallery_roi = self._normalize_roi(image, roi)
        badges = self._find_zoom_name_badges(image, gallery_roi)
        if not badges:
            return []

        image_height, image_width = image.shape[:2]
        roi_x, roi_y, roi_width, roi_height = gallery_roi
        roi_bottom = roi_y + roi_height
        row_groups = self._group_badges_by_row(badges, max_gap=max(12, image_height // 45))
        candidates: List[DetectionCandidate] = []

        for row_badges in row_groups:
            row_badges.sort(key=lambda rect: rect[0])
            row_bottom = min(
                roi_bottom,
                max(badge[1] + badge[3] for badge in row_badges) + max(3, image_height // 240),
            )

            inferred_width = self._infer_tile_width_from_badges(row_badges, image_width)
            inferred_height = int(round(inferred_width * 9.0 / 16.0)) if inferred_width else 0

            content_top = self._content_top_for_badge_row(row_badges, content_candidates, row_bottom, image_height)
            if content_top is not None and inferred_height:
                row_top = min(content_top, row_bottom - inferred_height)
            elif content_top is not None:
                row_top = content_top
            elif inferred_height:
                row_top = row_bottom - inferred_height
            else:
                row_top = row_bottom - int(image_height * 0.45)

            row_top = max(roi_y, row_top)
            row_height = max(1, row_bottom - row_top)
            tile_width = max(inferred_width, int(round(row_height * 16.0 / 9.0)))
            if tile_width <= 0:
                continue

            for badge in row_badges:
                badge_x, _badge_y, _badge_w, _badge_h = badge
                tile_x = max(roi_x, badge_x - max(2, image_width // 480))
                if tile_x + tile_width > roi_x + roi_width:
                    tile_x = max(roi_x, roi_x + roi_width - tile_width)
                rect = (int(tile_x), int(row_top), int(min(tile_width, roi_x + roi_width - tile_x)), int(row_height))
                if self._is_valid_rect(rect, image_width, image_height) and self._rect_inside_roi(rect, gallery_roi):
                    candidates.append(DetectionCandidate(rect, 0.96, "zoom-name-badge-layout"))

        return self._dedupe(candidates)

    def _find_zoom_name_badges(self, image: np.ndarray, roi: Rect | None = None) -> List[Rect]:
        roi_x, roi_y, roi_width, roi_height = self._normalize_roi(image, roi)
        search_image = image[roi_y : roi_y + roi_height, roi_x : roi_x + roi_width]
        if search_image.size == 0:
            return []

        image_height, image_width = search_image.shape[:2]
        gray = cv2.cvtColor(search_image, cv2.COLOR_BGR2GRAY)
        b_channel, g_channel, r_channel = cv2.split(search_image)
        bright_text = gray > 155
        red_muted_icon = (r_channel > 135) & (g_channel < 95) & (b_channel < 125)
        mask = (bright_text | red_muted_icon).astype(np.uint8) * 255

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(9, image_width // 160), max(3, image_height // 360)))
        mask = cv2.dilate(mask, kernel, iterations=1)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        badges: List[Rect] = []
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            if not (35 <= width <= image_width * 0.28):
                continue
            if not (12 <= height <= max(48, image_height * 0.055)):
                continue
            if y < image_height * 0.02 or y > image_height * 0.98:
                continue

            pad_x = max(4, image_width // 360)
            pad_y = max(3, image_height // 360)
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(image_width, x + width + pad_x)
            y2 = min(image_height, y + height + pad_y)
            badge_region = gray[y1:y2, x1:x2]
            if badge_region.size == 0 or float(np.median(badge_region)) > 82:
                continue

            badges.append((x1 + roi_x, y1 + roi_y, x2 - x1, y2 - y1))

        return self._dedupe_badges(badges)

    @staticmethod
    def _dedupe_badges(badges: List[Rect]) -> List[Rect]:
        badges = sorted(badges, key=lambda rect: rect[2] * rect[3], reverse=True)
        keep: List[Rect] = []
        for badge in badges:
            if any(ZoomGalleryDetector._iou(badge, other) > 0.35 for other in keep):
                continue
            keep.append(badge)
        return sorted(keep, key=lambda rect: (rect[1], rect[0]))

    @staticmethod
    def _group_badges_by_row(badges: List[Rect], max_gap: int) -> List[List[Rect]]:
        rows: List[List[Rect]] = []
        for badge in sorted(badges, key=lambda rect: rect[1] + rect[3] / 2):
            center_y = badge[1] + badge[3] / 2
            for row in rows:
                row_center = np.mean([item[1] + item[3] / 2 for item in row])
                if abs(center_y - row_center) <= max_gap:
                    row.append(badge)
                    break
            else:
                rows.append([badge])
        return rows

    @staticmethod
    def _infer_tile_width_from_badges(row_badges: List[Rect], image_width: int) -> int:
        if len(row_badges) < 2:
            return 0

        x_positions = sorted(badge[0] for badge in row_badges)
        gaps = np.diff(x_positions)
        if len(gaps) == 0:
            return 0

        median_spacing = float(np.median(gaps))
        visual_gap = max(8, int(image_width * 0.012))
        return max(1, int(round(median_spacing - visual_gap)))

    @staticmethod
    def _content_top_for_badge_row(
        row_badges: List[Rect],
        content_candidates: List[DetectionCandidate],
        row_bottom: int,
        image_height: int,
    ) -> int | None:
        min_candidate_height = max(48, int(image_height * 0.06))
        row_left = min(badge[0] for badge in row_badges)
        row_right = max(badge[0] + badge[2] for badge in row_badges)
        row_margin = max(80, int(image_height * 0.12))
        tops = []

        for candidate in content_candidates:
            x, y, width, height = candidate.rect
            if height < min_candidate_height:
                continue
            if y >= row_bottom:
                continue
            if y + height < row_bottom - int(image_height * 0.75):
                continue
            if x + width < row_left - row_margin or x > row_right + row_margin:
                continue
            tops.append(y)

        if not tops:
            return None
        return int(min(tops))

    @staticmethod
    def _normalize_roi(image: np.ndarray, roi: Rect | None) -> Rect:
        image_height, image_width = image.shape[:2]
        if roi is None:
            return 0, 0, image_width, image_height

        x, y, width, height = roi
        x = max(0, min(int(x), image_width - 1))
        y = max(0, min(int(y), image_height - 1))
        width = max(1, min(int(width), image_width - x))
        height = max(1, min(int(height), image_height - y))
        return x, y, width, height

    @staticmethod
    def _rect_inside_roi(rect: Rect, roi: Rect, tolerance: int = 2) -> bool:
        x, y, width, height = rect
        roi_x, roi_y, roi_width, roi_height = roi
        return (
            x >= roi_x - tolerance
            and y >= roi_y - tolerance
            and x + width <= roi_x + roi_width + tolerance
            and y + height <= roi_y + roi_height + tolerance
        )

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
