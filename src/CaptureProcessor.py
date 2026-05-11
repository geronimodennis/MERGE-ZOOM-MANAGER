from threading import Lock

from image_utils import draw_debug_overlay
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
            self.last_screenshots.update(screenshots)
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
        return draw_debug_overlay(image, tiles)

    def setChromaKey(self, chromaKey):
        self._chromaKey = chromaKey or (0, 177, 64)

    @staticmethod
    def _source_key(config: dict) -> str:
        capture_handler = config.get("captureHandler")
        hwnd = getattr(capture_handler, "hwnd", None)
        if hwnd:
            return str(hwnd)
        return str(config.get("winName", "unknown"))
