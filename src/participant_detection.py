from dataclasses import dataclass
from typing import Iterable, List, Tuple

import cv2
import numpy as np

from models import ParticipantTile, Rect


DEFAULT_TOP_MENU_HEIGHT = 53
DEFAULT_BOTTOM_MENU_HEIGHT = 100
MAX_PARTICIPANT_RECT_WIDTH = 945
MAX_PARTICIPANT_RECT_HEIGHT = 535
PROBABLE_PARTICIPANT_RECT_WIDTH = 945
PROBABLE_PARTICIPANT_RECT_HEIGHT = 535
DETECTION_SCAN_MAX_WIDTH = 960
STABLE_TILE_REASONS = {
    "gallery-rectangle",
    "gallery-rectangle-split",
    "zoom-name-badge-layout",
    "center-name-layout",
    "greenish-light-base-rectangle",
    "probable-base-rectangle",
}
UNSTABLE_TILE_REASONS = {"edge", "projection", "fragment-union"}


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

    def detect(
        self,
        image: np.ndarray,
        source_key: str = "",
        frame_index: int = 0,
        roi: Rect | None = None,
    ) -> List[ParticipantTile]:
        if image is None or image.size == 0:
            return []

        gallery_roi = self._normalize_roi(image, roi) if roi is not None else self._gallery_search_roi(image)
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
        candidates.extend(self._detect_from_centered_names(image, gallery_roi, candidates))
        candidates = [candidate for candidate in candidates if self._rect_inside_roi(candidate.rect, gallery_roi)]
        candidates = self._dedupe(candidates)
        candidates = self._remove_overlapping_unstable_boxes(candidates)
        candidates = self._remove_containing_boxes(candidates)
        candidates = self._filter_inconsistent_tile_sizes(candidates)
        if not candidates:
            candidates = self._detect_initial_base_rectangle(image, gallery_roi)
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
        search_image, scan_scale = self._scaled_search_image(image, (roi_x, roi_y, roi_width, roi_height))
        if search_image.size == 0:
            return []

        mask = self._foreground_mask(search_image)
        scan_height, scan_width = mask.shape[:2]
        image_height, image_width = image.shape[:2]
        x_segments = self._segments_from_projection(mask, axis=0)
        y_segments = self._segments_from_projection(mask, axis=1)

        candidates: List[DetectionCandidate] = []
        for x1, x2 in x_segments:
            for y1, y2 in y_segments:
                width = x2 - x1
                height = y2 - y1
                rect = (x1, y1, width, height)
                if not self._is_valid_rect(rect, scan_width, scan_height):
                    continue

                density = float(np.count_nonzero(mask[y1:y2, x1:x2])) / max(1, width * height)
                if density < 0.04:
                    continue
                absolute_rect = self._absolute_rect_from_scan(rect, roi_x, roi_y, scan_scale)
                if not self._is_valid_rect(absolute_rect, image_width, image_height):
                    continue
                candidates.append(DetectionCandidate(absolute_rect, min(0.99, 0.55 + density), "projection"))
        return candidates

    def _detect_from_edges(self, image: np.ndarray, roi: Rect | None = None) -> List[DetectionCandidate]:
        roi_x, roi_y, roi_width, roi_height = self._normalize_roi(image, roi)
        search_image, scan_scale = self._scaled_search_image(image, (roi_x, roi_y, roi_width, roi_height))
        if search_image.size == 0:
            return []

        scan_height, scan_width = search_image.shape[:2]
        image_height, image_width = image.shape[:2]
        gray = cv2.cvtColor(search_image, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(gray, 45, 140)

        kernel_size = max(3, min(scan_width, scan_height) // 180)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: List[DetectionCandidate] = []
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            rect = (x, y, width, height)
            if not self._is_valid_rect(rect, scan_width, scan_height):
                continue
            area_ratio = (width * height) / float(scan_width * scan_height)
            absolute_rect = self._absolute_rect_from_scan(rect, roi_x, roi_y, scan_scale)
            if not self._is_valid_rect(absolute_rect, image_width, image_height):
                continue
            candidates.append(DetectionCandidate(absolute_rect, min(0.9, 0.45 + area_ratio), "edge"))
        return candidates

    def _detect_from_gallery_rectangles(self, image: np.ndarray, roi_rect: Rect | None = None) -> List[DetectionCandidate]:
        image_height, image_width = image.shape[:2]
        roi_x, roi_y, roi_width, roi_height = self._normalize_roi(image, roi_rect)
        roi, scan_scale = self._scaled_search_image(image, (roi_x, roi_y, roi_width, roi_height))
        if roi.size == 0:
            return []

        scan_height, scan_width = roi.shape[:2]
        background = self._estimate_border_color(roi)
        diff = np.max(np.abs(roi.astype(np.int16) - background.astype(np.int16)), axis=2)
        mask = (diff > 8).astype(np.uint8) * 255

        kernel_width = max(9, scan_width // 120)
        kernel_height = max(5, scan_height // 120)
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

            absolute_rect = self._absolute_rect_from_scan((x, y, width, height), roi_x, roi_y, scan_scale)
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
    def _gallery_search_roi(
        image: np.ndarray,
        top_menu_height: int = DEFAULT_TOP_MENU_HEIGHT,
        bottom_menu_height: int = DEFAULT_BOTTOM_MENU_HEIGHT,
    ) -> Rect:
        height, width = image.shape[:2]
        top = max(0, min(int(top_menu_height), max(0, height - 1)))
        bottom = max(top + 1, min(height, height - max(0, int(bottom_menu_height))))
        return 0, top, width, bottom - top

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
        if not content_candidates:
            badges = self._compact_zoom_badges_for_layout_only(badges, gallery_roi)
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

    @staticmethod
    def _compact_zoom_badges_for_layout_only(badges: List[Rect], roi: Rect) -> List[Rect]:
        _roi_x, _roi_y, _roi_width, roi_height = roi
        max_badge_height = max(30, min(32, int(round(roi_height * 0.030))))
        return [badge for badge in badges if badge[3] <= max_badge_height]

    def _detect_from_centered_names(
        self,
        image: np.ndarray,
        roi: Rect,
        existing_candidates: List[DetectionCandidate],
    ) -> List[DetectionCandidate]:
        labels = self._find_centered_name_labels(image, roi)
        if not labels:
            return []

        uncovered_labels = [label for label in labels if not self._label_center_inside_candidates(label, existing_candidates)]
        if not uncovered_labels:
            return []

        roi_x, roi_y, roi_width, roi_height = self._normalize_roi(image, roi)
        image_height, image_width = image.shape[:2]
        row_groups = self._group_badges_by_row(uncovered_labels, max_gap=max(18, roi_height // 18))
        row_centers = [float(np.mean([label[1] + label[3] / 2.0 for label in row])) for row in row_groups]
        known_size = self._probable_tile_size_from_candidates(existing_candidates)

        candidates: List[DetectionCandidate] = []
        for row_index, row_labels in enumerate(row_groups):
            row_labels.sort(key=lambda rect: rect[0])
            row_center_y = row_centers[row_index]

            for label in row_labels:
                nearest_size = self._nearest_tile_size_for_label(label, existing_candidates)
                if nearest_size is not None:
                    tile_width, tile_height = nearest_size
                elif known_size is not None:
                    tile_width, tile_height = known_size
                else:
                    tile_width, tile_height = self._estimate_tile_size_for_name_row(
                        row_labels,
                        row_index,
                        row_centers,
                        roi_width,
                        roi_height,
                    )
                tile_width, tile_height = self._clamp_participant_size(tile_width, tile_height)
                if tile_width <= 0 or tile_height <= 0:
                    continue

                label_center_x = label[0] + label[2] / 2.0
                label_center_y = label[1] + label[3] / 2.0 if len(row_groups) == 1 else row_center_y
                rect = self._rect_centered_in_roi(label_center_x, label_center_y, tile_width, tile_height, (roi_x, roi_y, roi_width, roi_height))
                if not self._is_valid_rect(rect, image_width, image_height):
                    continue
                candidates.append(DetectionCandidate(rect, 0.74, "center-name-layout"))

        return self._dedupe(candidates)

    def _detect_initial_base_rectangle(self, image: np.ndarray, roi: Rect) -> List[DetectionCandidate]:
        color_candidates = self._detect_from_greenish_or_light_rectangles(image, roi)
        if color_candidates:
            return color_candidates

        roi_x, roi_y, roi_width, roi_height = self._normalize_roi(image, roi)
        if roi_width < PROBABLE_PARTICIPANT_RECT_WIDTH or roi_height < PROBABLE_PARTICIPANT_RECT_HEIGHT:
            return []
        width, height = self._clamp_participant_size(PROBABLE_PARTICIPANT_RECT_WIDTH, PROBABLE_PARTICIPANT_RECT_HEIGHT)
        rect = self._rect_centered_in_roi(
            roi_x + roi_width / 2.0,
            roi_y + roi_height / 2.0,
            min(width, roi_width),
            min(height, roi_height),
            (roi_x, roi_y, roi_width, roi_height),
        )
        if self._is_valid_rect(rect, image.shape[1], image.shape[0]):
            return [DetectionCandidate(rect, 0.55, "probable-base-rectangle")]
        return []

    def _detect_from_greenish_or_light_rectangles(self, image: np.ndarray, roi: Rect) -> List[DetectionCandidate]:
        roi_x, roi_y, roi_width, roi_height = self._normalize_roi(image, roi)
        search_image = image[roi_y : roi_y + roi_height, roi_x : roi_x + roi_width]
        if search_image.size == 0:
            return []

        source_height, source_width = search_image.shape[:2]
        max_scan_width = 960
        scan_scale = min(1.0, max_scan_width / float(max(1, source_width)))
        if scan_scale < 1.0:
            scan_width = max(1, int(round(source_width * scan_scale)))
            scan_height = max(1, int(round(source_height * scan_scale)))
            scan_image = cv2.resize(search_image, (scan_width, scan_height), interpolation=cv2.INTER_AREA)
        else:
            scan_image = search_image
            scan_width = source_width
            scan_height = source_height

        b_channel, g_channel, r_channel = cv2.split(scan_image.astype(np.int16))
        gray = cv2.cvtColor(scan_image, cv2.COLOR_BGR2GRAY)
        greenish = (g_channel >= 54) & (g_channel >= r_channel + 10) & (g_channel >= b_channel + 6)
        light_colored = gray >= 122
        mask = (greenish | light_colored).astype(np.uint8) * 255

        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (max(5, scan_width // 160), max(5, scan_height // 160)),
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: List[DetectionCandidate] = []
        min_width = max(90, int(source_width * 0.08))
        min_height = max(70, int(source_height * 0.08))

        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            if scan_scale < 1.0:
                x = int(round(x / scan_scale))
                y = int(round(y / scan_scale))
                width = int(round(width / scan_scale))
                height = int(round(height / scan_scale))
            if width < min_width or height < min_height:
                continue

            rect = (x + roi_x, y + roi_y, width, height)
            rect = self._clamp_rect_to_participant_bounds(rect, (roi_x, roi_y, roi_width, roi_height))
            if not self._is_valid_rect(rect, image.shape[1], image.shape[0]):
                continue

            local_x = max(0, rect[0] - roi_x)
            local_y = max(0, rect[1] - roi_y)
            local_width = min(source_width - local_x, rect[2])
            local_height = min(source_height - local_y, rect[3])
            region = mask[
                int(local_y * scan_scale) : max(int((local_y + local_height) * scan_scale), int(local_y * scan_scale) + 1),
                int(local_x * scan_scale) : max(int((local_x + local_width) * scan_scale), int(local_x * scan_scale) + 1),
            ]
            fill_ratio = float(np.count_nonzero(region)) / float(max(1, region.size))
            if fill_ratio < 0.45:
                continue
            candidates.append(DetectionCandidate(rect, min(0.84, 0.62 + fill_ratio * 0.20), "greenish-light-base-rectangle"))

        candidates = self._dedupe(candidates)
        candidates = self._remove_containing_boxes(candidates)
        return sorted(candidates, key=lambda item: (item.rect[1], item.rect[0]))

    def _find_centered_name_labels(self, image: np.ndarray, roi: Rect) -> List[Rect]:
        roi_x, roi_y, roi_width, roi_height = self._normalize_roi(image, roi)
        search_image = image[roi_y : roi_y + roi_height, roi_x : roi_x + roi_width]
        if search_image.size == 0:
            return []

        image_height, image_width = search_image.shape[:2]
        gray = cv2.cvtColor(search_image, cv2.COLOR_BGR2GRAY)
        bright_text = (gray > 145).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(19, image_width // 80), max(5, image_height // 180)))
        mask = cv2.dilate(bright_text, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        labels: List[Rect] = []
        min_centered_text_height = max(14, int(round(image_height * 0.022)))
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            if not (35 <= width <= image_width * 0.40):
                continue
            if not (min_centered_text_height <= height <= max(80, image_height * 0.12)):
                continue
            if y < image_height * 0.04 or y + height > image_height * 0.96:
                continue

            absolute_rect = (x + roi_x, y + roi_y, width, height)
            labels.append(absolute_rect)

        return self._dedupe_badges(labels)

    def _probable_tile_size_from_candidates(self, candidates: List[DetectionCandidate]) -> Tuple[int, int] | None:
        stable_cardish = [
            candidate.rect
            for candidate in candidates
            if candidate.reason in STABLE_TILE_REASONS and self._is_cardish_aspect(candidate.rect)
        ]
        if stable_cardish:
            widths = np.array([rect[2] for rect in stable_cardish], dtype=np.float32)
            heights = np.array([rect[3] for rect in stable_cardish], dtype=np.float32)
            return int(round(float(np.median(widths)))), int(round(float(np.median(heights))))

        cardish_candidates = [candidate for candidate in candidates if self._is_cardish_aspect(candidate.rect)]
        if len(cardish_candidates) < 2 or not self._candidates_look_like_tiles(cardish_candidates):
            return None
        cardish = [candidate.rect for candidate in cardish_candidates]
        widths = np.array([rect[2] for rect in cardish], dtype=np.float32)
        heights = np.array([rect[3] for rect in cardish], dtype=np.float32)
        return int(round(float(np.median(widths)))), int(round(float(np.median(heights))))

    def _nearest_tile_size_for_label(
        self,
        label: Rect,
        candidates: List[DetectionCandidate],
    ) -> Tuple[int, int] | None:
        label_center_x = label[0] + label[2] / 2.0
        label_center_y = label[1] + label[3] / 2.0
        scored_sizes = []

        for candidate in candidates:
            x, y, width, height = candidate.rect
            if not self._is_cardish_aspect(candidate.rect):
                continue

            center_x = x + width / 2.0
            center_y = y + height / 2.0
            label_inside = x <= label_center_x <= x + width and y <= label_center_y <= y + height
            if label_inside and not self._candidate_covers_centered_label(label, candidate):
                continue

            clamped_width, clamped_height = self._clamp_participant_size(width, height)
            stable_penalty = 0 if candidate.reason in STABLE_TILE_REASONS else 1
            row_distance = abs(label_center_y - center_y)
            center_distance = ((label_center_x - center_x) ** 2 + (label_center_y - center_y) ** 2) ** 0.5
            scored_sizes.append((stable_penalty, row_distance, center_distance, clamped_width, clamped_height))

        if not scored_sizes:
            return None

        _stable_penalty, _row_distance, _center_distance, width, height = min(scored_sizes)
        return width, height

    def _estimate_tile_size_for_name_row(
        self,
        row_labels: List[Rect],
        row_index: int,
        row_centers: List[float],
        roi_width: int,
        roi_height: int,
    ) -> Tuple[int, int]:
        visual_gap = max(8, int(roi_width * 0.012))
        if len(row_labels) >= 2:
            centers = sorted(label[0] + label[2] / 2.0 for label in row_labels)
            tile_width = int(round(float(np.median(np.diff(centers))) - visual_gap))
            tile_height = int(round(tile_width * 9.0 / 16.0))
        else:
            row_height = self._estimate_row_height(row_index, row_centers, roi_height)
            tile_height = max(1, row_height - visual_gap)
            tile_width = int(round(tile_height * 16.0 / 9.0))

        row_height = self._estimate_row_height(row_index, row_centers, roi_height)
        if tile_height > row_height - visual_gap:
            tile_height = max(1, row_height - visual_gap)
            tile_width = int(round(tile_height * 16.0 / 9.0))

        if tile_width > roi_width:
            tile_width = roi_width
            tile_height = int(round(tile_width * 9.0 / 16.0))
        if tile_height > roi_height:
            tile_height = roi_height
            tile_width = int(round(tile_height * 16.0 / 9.0))

        return self._clamp_participant_size(tile_width, tile_height)

    @staticmethod
    def _clamp_participant_size(width: int, height: int) -> Tuple[int, int]:
        width = max(1, int(width))
        height = max(1, int(height))
        scale = min(
            1.0,
            MAX_PARTICIPANT_RECT_WIDTH / float(width),
            MAX_PARTICIPANT_RECT_HEIGHT / float(height),
        )
        if scale < 1.0:
            width = max(1, int(round(width * scale)))
            height = max(1, int(round(height * scale)))
        return width, height

    @staticmethod
    def _estimate_row_height(row_index: int, row_centers: List[float], roi_height: int) -> int:
        if len(row_centers) <= 1:
            return roi_height
        if row_index == 0:
            spacing = row_centers[1] - row_centers[0]
        elif row_index == len(row_centers) - 1:
            spacing = row_centers[-1] - row_centers[-2]
        else:
            spacing = min(row_centers[row_index] - row_centers[row_index - 1], row_centers[row_index + 1] - row_centers[row_index])
        return max(1, int(round(spacing)))

    @staticmethod
    def _rect_centered_in_roi(center_x: float, center_y: float, width: int, height: int, roi: Rect) -> Rect:
        roi_x, roi_y, roi_width, roi_height = roi
        width = min(max(1, int(width)), roi_width)
        height = min(max(1, int(height)), roi_height)
        x = int(round(center_x - width / 2.0))
        y = int(round(center_y - height / 2.0))
        x = max(roi_x, min(x, roi_x + roi_width - width))
        y = max(roi_y, min(y, roi_y + roi_height - height))
        return x, y, width, height

    def _clamp_rect_to_participant_bounds(self, rect: Rect, roi: Rect) -> Rect:
        x, y, width, height = rect
        width, height = self._clamp_participant_size(width, height)
        center_x = x + rect[2] / 2.0
        center_y = y + rect[3] / 2.0
        return self._rect_centered_in_roi(center_x, center_y, width, height, roi)

    def _label_center_inside_candidates(self, label: Rect, candidates: List[DetectionCandidate]) -> bool:
        return any(self._candidate_covers_centered_label(label, candidate) for candidate in candidates)

    def _candidate_covers_centered_label(self, label: Rect, candidate: DetectionCandidate) -> bool:
        center_x = label[0] + label[2] / 2.0
        center_y = label[1] + label[3] / 2.0
        x, y, width, height = candidate.rect
        if not (x <= center_x <= x + width and y <= center_y <= y + height):
            return False
        if not self._is_cardish_aspect(candidate.rect):
            return False
        if self._label_looks_like_name_badge_inside_candidate(label, candidate.rect):
            return True

        candidate_center_x = x + width / 2.0
        candidate_center_y = y + height / 2.0
        horizontal_offset = abs(center_x - candidate_center_x) / float(max(1, width))
        vertical_offset = abs(center_y - candidate_center_y) / float(max(1, height))

        left_margin = center_x - x
        right_margin = x + width - center_x
        top_margin = center_y - y
        bottom_margin = y + height - center_y
        min_horizontal_margin = max(18.0, label[2] * 0.55, width * 0.12)
        min_vertical_margin = max(18.0, label[3] * 1.4, height * 0.18)

        return (
            horizontal_offset <= 0.28
            and vertical_offset <= 0.30
            and left_margin >= min_horizontal_margin
            and right_margin >= min_horizontal_margin
            and top_margin >= min_vertical_margin
            and bottom_margin >= min_vertical_margin
        )

    @staticmethod
    def _label_looks_like_name_badge_inside_candidate(label: Rect, candidate_rect: Rect) -> bool:
        label_x, label_y, label_width, label_height = label
        candidate_x, candidate_y, candidate_width, candidate_height = candidate_rect
        label_center_y = label_y + label_height / 2.0
        lower_badge_band = candidate_y + candidate_height * 0.68
        label_is_compact = label_width <= candidate_width * 0.45
        label_has_left_room = label_x <= candidate_x + candidate_width * 0.50
        return label_center_y >= lower_badge_band and label_is_compact and label_has_left_room

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
    def _scaled_search_image(
        image: np.ndarray,
        roi: Rect,
        max_width: int = DETECTION_SCAN_MAX_WIDTH,
    ) -> Tuple[np.ndarray, float]:
        roi_x, roi_y, roi_width, roi_height = roi
        search_image = image[roi_y : roi_y + roi_height, roi_x : roi_x + roi_width]
        if search_image.size == 0:
            return search_image, 1.0

        scale = min(1.0, max(1, int(max_width)) / float(max(1, roi_width)))
        if scale >= 1.0:
            return search_image, 1.0

        scan_width = max(1, int(round(roi_width * scale)))
        scan_height = max(1, int(round(roi_height * scale)))
        return cv2.resize(search_image, (scan_width, scan_height), interpolation=cv2.INTER_AREA), scale

    @staticmethod
    def _absolute_rect_from_scan(rect: Rect, roi_x: int, roi_y: int, scan_scale: float) -> Rect:
        x, y, width, height = rect
        if scan_scale < 1.0:
            x = int(round(x / scan_scale))
            y = int(round(y / scan_scale))
            width = int(round(width / scan_scale))
            height = int(round(height / scan_scale))
        return x + roi_x, y + roi_y, max(1, width), max(1, height)

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
        if width > MAX_PARTICIPANT_RECT_WIDTH or height > MAX_PARTICIPANT_RECT_HEIGHT:
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
            if any(self._is_duplicate_candidate(candidate, other) for other in keep):
                continue
            keep.append(candidate)
        return keep

    def _is_duplicate_candidate(self, candidate: DetectionCandidate, other: DetectionCandidate) -> bool:
        if self._iou(candidate.rect, other.rect) <= 0.55:
            return False
        if self._is_allowed_center_name_overlap(candidate, other):
            return False
        return True

    @staticmethod
    def _is_allowed_center_name_overlap(candidate: DetectionCandidate, other: DetectionCandidate) -> bool:
        if candidate.reason == other.reason:
            return False
        if candidate.reason != "center-name-layout" and other.reason != "center-name-layout":
            return False

        candidate_center_x = candidate.rect[0] + candidate.rect[2] / 2.0
        candidate_center_y = candidate.rect[1] + candidate.rect[3] / 2.0
        other_center_x = other.rect[0] + other.rect[2] / 2.0
        other_center_y = other.rect[1] + other.rect[3] / 2.0
        min_width = min(candidate.rect[2], other.rect[2])
        min_height = min(candidate.rect[3], other.rect[3])
        return (
            abs(candidate_center_x - other_center_x) >= min_width * 0.20
            or abs(candidate_center_y - other_center_y) >= min_height * 0.20
        )

    def _remove_containing_boxes(self, candidates: List[DetectionCandidate]) -> List[DetectionCandidate]:
        remove_indexes = set()

        for index, candidate in enumerate(candidates):
            candidate_area = self._rect_area(candidate.rect)
            large_contained = [
                other
                for other in candidates
                if other is not candidate
                and self._contains(candidate.rect, other.rect)
                and self._rect_area(other.rect) >= candidate_area * 0.18
                and self._is_cardish_aspect(other.rect)
            ]
            if len(large_contained) >= 2:
                remove_indexes.add(index)

        for index, candidate in enumerate(candidates):
            if index in remove_indexes:
                continue
            candidate_area = self._rect_area(candidate.rect)
            for outer_index, outer in enumerate(candidates):
                if outer_index == index or outer_index in remove_indexes:
                    continue
                outer_area = self._rect_area(outer.rect)
                if candidate_area >= outer_area * 0.75:
                    continue
                if self._contains(outer.rect, candidate.rect):
                    remove_indexes.add(index)
                    break

        return [candidate for index, candidate in enumerate(candidates) if index not in remove_indexes]

    def _remove_overlapping_unstable_boxes(self, candidates: List[DetectionCandidate]) -> List[DetectionCandidate]:
        if len(candidates) <= 1:
            return candidates

        remove_indexes = set()
        for index, candidate in enumerate(candidates):
            if candidate.reason not in UNSTABLE_TILE_REASONS:
                continue

            candidate_area = self._rect_area(candidate.rect)
            if candidate_area <= 0:
                remove_indexes.add(index)
                continue

            for other_index, other in enumerate(candidates):
                if other_index == index or other.reason not in STABLE_TILE_REASONS:
                    continue

                smaller_area = min(candidate_area, self._rect_area(other.rect))
                overlap_ratio = self._intersection_area(candidate.rect, other.rect) / float(max(1, smaller_area))
                if overlap_ratio >= 0.28:
                    remove_indexes.add(index)
                    break

        return [candidate for index, candidate in enumerate(candidates) if index not in remove_indexes]

    def _filter_inconsistent_tile_sizes(self, candidates: List[DetectionCandidate]) -> List[DetectionCandidate]:
        if len(candidates) <= 1:
            return candidates

        cardish_candidates = [candidate for candidate in candidates if self._is_cardish_aspect(candidate.rect)]
        if not cardish_candidates:
            return candidates

        widths = np.array([candidate.rect[2] for candidate in cardish_candidates], dtype=np.float32)
        heights = np.array([candidate.rect[3] for candidate in cardish_candidates], dtype=np.float32)
        areas = widths * heights
        large_half_start = max(0, len(areas) // 2)
        area_order = np.argsort(areas)
        large_candidates = [cardish_candidates[index] for index in area_order[large_half_start:]]

        reference_width = float(np.median([candidate.rect[2] for candidate in large_candidates]))
        reference_height = float(np.median([candidate.rect[3] for candidate in large_candidates]))
        reference_area = float(np.median([self._rect_area(candidate.rect) for candidate in large_candidates]))

        filtered = []
        for candidate in candidates:
            width = candidate.rect[2]
            height = candidate.rect[3]
            area = self._rect_area(candidate.rect)
            if not self._is_cardish_aspect(candidate.rect):
                continue
            if area < reference_area * 0.45:
                continue
            if width < reference_width * 0.55 and height < reference_height * 0.55:
                continue
            filtered.append(candidate)

        return filtered or candidates

    @staticmethod
    def _rect_area(rect: Rect) -> int:
        return max(0, int(rect[2])) * max(0, int(rect[3]))

    @staticmethod
    def _is_cardish_aspect(rect: Rect) -> bool:
        _x, _y, width, height = rect
        aspect = width / float(max(1, height))
        return 1.05 <= aspect <= 2.55

    @staticmethod
    def _contains(outer: Rect, inner: Rect) -> bool:
        ox, oy, ow, oh = outer
        ix, iy, iw, ih = inner
        return ox <= ix and oy <= iy and ox + ow >= ix + iw and oy + oh >= iy + ih

    @staticmethod
    def _intersection_area(a: Rect, b: Rect) -> int:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        x1 = max(ax, bx)
        y1 = max(ay, by)
        x2 = min(ax + aw, bx + bw)
        y2 = min(ay + ah, by + bh)
        return max(0, x2 - x1) * max(0, y2 - y1)

    @staticmethod
    def _iou(a: Rect, b: Rect) -> float:
        intersection = ZoomGalleryDetector._intersection_area(a, b)
        aw, ah = a[2], a[3]
        bw, bh = b[2], b[3]
        union = aw * ah + bw * bh - intersection
        return intersection / float(union) if union else 0.0
