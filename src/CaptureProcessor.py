from threading import Lock

import numpy as np

from image_utils import blank_image, draw_debug_overlay
from participant_detection import ZoomGalleryDetector
from participant_tracking import ParticipantTracker


class CaptureProcessor:
    def __init__(self, captureConfigurationList: list, chromaKey=(0, 177, 64)):
        self._captureConfigurationList = captureConfigurationList
        self._chromaKey = chromaKey or (0, 177, 64)
        self.detector = ZoomGalleryDetector()
        self.tracker = ParticipantTracker()
        self.last_tiles = []
        self.last_screenshots = {}
        self.frame_index = 0
        self._lock = Lock()

    def processScreenShot(self, useSmallerCapture=False):
        self.last_tiles = self.process_tiles()
        return [tile.crop for tile in self.last_tiles]

    def process_tiles(self):
        detections = []
        screenshots = {}
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
            tiles = self.detector.detect(screenshot, source_key=source_key, frame_index=self.frame_index)
            detections.extend(tiles)

        with self._lock:
            self.last_screenshots = screenshots
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
            image = image.copy()
            tiles = [tile for tile in self.last_tiles if tile.source_key == source_key]
            roi = self.detector._gallery_search_roi(image)
        return draw_debug_overlay(image, tiles, title=f"source {source_key}", roi=roi)

    def build_live_debug_overlay(self):
        with self._lock:
            screenshots = [(source_key, image.copy()) for source_key, image in self.last_screenshots.items()]
            tiles = list(self.last_tiles)

        if not screenshots:
            return None, []

        overlays = []
        cells = []
        for source_key, image in screenshots:
            source_tiles = [tile for tile in tiles if tile.source_key == source_key]
            roi = self.detector._gallery_search_roi(image)
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

    @staticmethod
    def _source_key(config: dict) -> str:
        capture_handler = config.get("captureHandler")
        hwnd = getattr(capture_handler, "hwnd", None)
        if hwnd:
            return str(hwnd)
        return str(config.get("winName", "unknown"))
