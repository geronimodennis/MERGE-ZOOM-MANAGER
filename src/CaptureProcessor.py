from threading import Lock

import numpy as np

from image_utils import blank_image, draw_debug_overlay
from models import ParticipantTile, Rect
from participant_detection import ZoomGalleryDetector
from participant_tracking import ParticipantTracker


class CaptureProcessor:
    def __init__(self, captureConfigurationList: list, chromaKey=(0, 177, 64), detection_interval: int = 3):
        self._captureConfigurationList = captureConfigurationList
        self._chromaKey = chromaKey or (0, 177, 64)
        self.detection_interval = max(1, int(detection_interval))
        self.detector = ZoomGalleryDetector()
        self.tracker = ParticipantTracker()
        self.last_tiles = []
        self.last_screenshots = {}
        self.last_rois = {}
        self.frame_index = 0
        self._last_full_detection = {}
        self._lock = Lock()

    def processScreenShot(self, useSmallerCapture=False):
        self.last_tiles = self.process_tiles()
        return [tile.crop for tile in self.last_tiles]

    def process_tiles(self):
        detections = []
        screenshots = {}
        rois = {}
        self.frame_index += 1

        for config in self._captureConfigurationList:
            capture_handler = config.get("captureHandler")
            if capture_handler is None:
                continue

            source_key = self._source_key(config)
            screenshot = capture_handler.get_screenshot()
            if screenshot is None or screenshot.size == 0:
                continue

            screenshots[source_key] = screenshot
            roi = self._roi_for_config(config, screenshot)
            rois[source_key] = roi
            if self._should_run_full_detection(source_key, screenshot, roi):
                tiles = self.detector.detect(screenshot, source_key=source_key, frame_index=self.frame_index, roi=roi)
                self._last_full_detection[source_key] = {
                    "frame_index": self.frame_index,
                    "roi": roi,
                    "shape": screenshot.shape[:2],
                }
            else:
                tiles = self._tiles_from_previous_rects(source_key, screenshot)
            detections.extend(tiles)

        with self._lock:
            self.last_screenshots = screenshots
            self.last_rois = rois
            tracked = self.tracker.update(detections)
            self.last_tiles = tracked
        return tracked

    def get_tiles(self):
        with self._lock:
            return list(self.last_tiles)

    def get_tile(self, track_id, include_missing=False):
        with self._lock:
            return self.tracker.get(track_id, include_missing=include_missing)

    def get_tiles_by_ids(self, track_ids, include_missing=False):
        with self._lock:
            return self.tracker.get_many(track_ids, include_missing=include_missing)

    def get_missing_count(self, track_ids):
        with self._lock:
            return self.tracker.missing_count(track_ids)

    def build_debug_overlay(self, source_key=None):
        with self._lock:
            if not self.last_screenshots:
                return None
            if source_key is None:
                source_key = next(iter(self.last_screenshots.keys()))
            image = self.last_screenshots.get(source_key)
            if image is None:
                return None
            tiles = [tile for tile in self.last_tiles if tile.source_key == source_key]
            roi = self.last_rois.get(source_key) or self.detector._gallery_search_roi(image)
        return draw_debug_overlay(image, tiles, title=f"source {source_key}", roi=roi)

    def build_live_debug_overlay(self):
        with self._lock:
            screenshots = list(self.last_screenshots.items())
            tiles = list(self.last_tiles)
            rois = dict(self.last_rois)

        if not screenshots:
            return None, []

        overlays = []
        cells = []
        for source_key, image in screenshots:
            source_tiles = [tile for tile in tiles if tile.source_key == source_key]
            roi = rois.get(source_key) or self.detector._gallery_search_roi(image)
            overlay = draw_debug_overlay(
                image,
                source_tiles,
                title=f"source {source_key}   tiles {len(source_tiles)}",
                roi=roi,
            )
            overlays.append((source_key, overlay, source_tiles))

        frame, offsets = self._stack_debug_overlays([overlay for _source_key, overlay, _tiles in overlays])
        for source_index, (_source_key, _overlay, source_tiles) in enumerate(overlays):
            offset_x, offset_y = offsets[source_index]
            for tile in source_tiles:
                x, y, width, height = tile.rect
                cells.append(
                    {
                        "tile_id": tile.track_id,
                        "index": len(cells),
                        "source_key": tile.source_key,
                        "rect": (x + offset_x, y + offset_y, width, height),
                    }
                )
        return frame, cells

    def get_source_snapshot(self, preferred_source_key=None):
        with self._lock:
            if not self.last_screenshots:
                return None
            source_key = preferred_source_key if preferred_source_key in self.last_screenshots else next(iter(self.last_screenshots.keys()))
            image = self.last_screenshots[source_key].copy()
            roi = self.last_rois.get(source_key) or self.detector._gallery_search_roi(image)
            config = self._config_for_source_key(source_key)
            manual = bool(config.get("manualRoi")) if config else False
        return {"source_key": source_key, "image": image, "roi": roi, "manual": manual}

    def set_manual_roi(self, source_key: str, roi: Rect):
        with self._lock:
            config = self._config_for_source_key(source_key)
            if config is None and len(self._captureConfigurationList) == 1:
                config = self._captureConfigurationList[0]
                source_key = self._source_key(config)
            if config is None:
                return False

            image = self.last_screenshots.get(source_key)
            normalized_roi = self.detector._normalize_roi(image, roi) if image is not None else tuple(int(value) for value in roi)
            config["manualRoi"] = normalized_roi
            self.last_rois[source_key] = normalized_roi
        return True

    def clear_manual_roi(self, source_key: str | None = None):
        with self._lock:
            changed = False
            for config in self._captureConfigurationList:
                config_source_key = self._source_key(config)
                if source_key is not None and config_source_key != source_key:
                    continue
                if config.get("manualRoi") is not None:
                    changed = True
                config["manualRoi"] = None
                image = self.last_screenshots.get(config_source_key)
                if image is not None:
                    self.last_rois[config_source_key] = self.detector._gallery_search_roi(image)
        return changed

    def close(self):
        with self._lock:
            self.last_tiles = []
            self.last_screenshots = {}
            self.last_rois = {}
            self._last_full_detection = {}

        for config in self._captureConfigurationList:
            capture_handler = config.get("captureHandler")
            if capture_handler is None:
                continue
            try:
                if hasattr(capture_handler, "freeResources"):
                    capture_handler.freeResources()
                elif hasattr(capture_handler, "stopFramePool"):
                    capture_handler.stopFramePool()
            except Exception:
                pass

    def _stack_debug_overlays(self, overlays):
        if len(overlays) == 1:
            return overlays[0], [(0, 0)]

        max_width = max(image.shape[1] for image in overlays)
        total_height = sum(image.shape[0] for image in overlays)
        frame = blank_image((max_width, total_height), self._chromaKey)
        offsets = []
        y = 0
        for image in overlays:
            height, width = image.shape[:2]
            frame[y : y + height, 0:width] = image
            offsets.append((0, y))
            y += height
        return np.ascontiguousarray(frame), offsets

    def setChromaKey(self, chromaKey):
        self._chromaKey = chromaKey or (0, 177, 64)

    def _roi_for_config(self, config: dict, image: np.ndarray) -> Rect:
        manual_roi = config.get("manualRoi")
        if manual_roi is not None:
            return self.detector._normalize_roi(image, manual_roi)
        return self.detector._gallery_search_roi(image)

    def _should_run_full_detection(self, source_key: str, image: np.ndarray, roi: Rect) -> bool:
        previous_tiles = self._previous_tiles_for_source(source_key)
        if not previous_tiles:
            return True

        state = self._last_full_detection.get(source_key)
        if state is None:
            return True
        if state.get("roi") != roi:
            return True
        if state.get("shape") != image.shape[:2]:
            return True
        return self.frame_index - int(state.get("frame_index", 0)) >= self.detection_interval

    def _tiles_from_previous_rects(self, source_key: str, image: np.ndarray):
        height, width = image.shape[:2]
        tiles = []
        for previous in self._previous_tiles_for_source(source_key):
            rect = self._clamp_rect_to_image(previous.rect, width, height)
            if rect is None:
                continue

            x, y, tile_width, tile_height = rect
            crop = image[y : y + tile_height, x : x + tile_width].copy()
            if crop.size == 0:
                continue

            tiles.append(
                ParticipantTile(
                    track_id=previous.track_id,
                    source_key=previous.source_key,
                    rect=rect,
                    crop=crop,
                    confidence=previous.confidence,
                    descriptor=self.detector.build_descriptor(crop),
                    frame_index=self.frame_index,
                    debug_reason=previous.debug_reason,
                )
            )
        return tiles

    def _previous_tiles_for_source(self, source_key: str):
        with self._lock:
            return [tile for tile in self.last_tiles if tile.source_key == source_key and tile.missing_frames == 0]

    @staticmethod
    def _clamp_rect_to_image(rect: Rect, image_width: int, image_height: int):
        x, y, width, height = rect
        x = max(0, min(int(x), max(0, image_width - 1)))
        y = max(0, min(int(y), max(0, image_height - 1)))
        width = max(1, min(int(width), image_width - x))
        height = max(1, min(int(height), image_height - y))
        if width <= 0 or height <= 0:
            return None
        return x, y, width, height

    def _config_for_source_key(self, source_key: str):
        for config in self._captureConfigurationList:
            if self._source_key(config) == source_key:
                return config
        return None

    @staticmethod
    def _source_key(config: dict) -> str:
        capture_handler = config.get("captureHandler")
        hwnd = getattr(capture_handler, "hwnd", None)
        if hwnd:
            return str(hwnd)
        return str(config.get("winName", "unknown"))
