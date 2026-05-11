import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from CaptureProcessor import CaptureProcessor
from captureRunnerOnThread import CaptureRunnerOnThread
from models import ParticipantTile


def test_live_debug_overlay_draws_tile_rectangles_and_click_cells():
    processor = CaptureProcessor([], chromaKey=(0, 177, 64))
    image = np.zeros((120, 200, 3), dtype=np.uint8)
    image[:, :] = (17, 20, 22)
    tile = ParticipantTile(
        track_id=7,
        source_key="zoom",
        rect=(20, 30, 80, 45),
        crop=image[30:75, 20:100].copy(),
        confidence=0.93,
        debug_reason="test-rect",
    )

    with processor._lock:
        processor.last_screenshots = {"zoom": image}
        processor.last_tiles = [tile]

    frame, cells = processor.build_live_debug_overlay()

    assert frame is not None
    assert cells == [{"tile_id": 7, "index": 0, "source_key": "zoom", "rect": (20, 30, 80, 45)}]
    assert not np.array_equal(frame, image)
    assert tuple(int(value) for value in frame[30, 20]) == (255, 80, 30)
    assert tuple(int(value) for value in frame[53, 0]) == (80, 220, 80)


def test_live_debug_overlay_stacks_multiple_capture_sources():
    processor = CaptureProcessor([], chromaKey=(0, 177, 64))
    first = np.zeros((80, 120, 3), dtype=np.uint8)
    second = np.zeros((60, 90, 3), dtype=np.uint8)
    first[:, :] = (18, 18, 18)
    second[:, :] = (22, 22, 22)
    first_tile = ParticipantTile(track_id=1, source_key="first", rect=(8, 10, 40, 30), crop=first[10:40, 8:48].copy())
    second_tile = ParticipantTile(track_id=2, source_key="second", rect=(12, 14, 36, 24), crop=second[14:38, 12:48].copy())

    with processor._lock:
        processor.last_screenshots = {"first": first, "second": second}
        processor.last_tiles = [first_tile, second_tile]

    frame, cells = processor.build_live_debug_overlay()

    assert frame.shape[:2] == (140, 120)
    assert cells[0]["rect"] == (8, 10, 40, 30)
    assert cells[1]["rect"] == (12, 94, 36, 24)


class FakeDebugProcessor:
    def __init__(self):
        self.calls = 0
        self.tile = ParticipantTile(
            track_id=4,
            source_key="fake",
            rect=(0, 0, 32, 18),
            crop=np.full((18, 32, 3), 60, dtype=np.uint8),
        )

    def process_tiles(self):
        return [self.tile]

    def setChromaKey(self, _chroma_key):
        return None

    def build_live_debug_overlay(self):
        self.calls += 1
        frame = np.full((18, 32, 3), self.calls, dtype=np.uint8)
        return frame, [{"tile_id": 4, "index": 0, "source_key": "fake", "rect": (0, 0, 32, 18)}]


class FakeCaptureHandler:
    hwnd = 0

    def __init__(self, image):
        self.image = image
        self.closed = False

    def get_screenshot(self):
        return self.image.copy()

    def freeResources(self):
        self.closed = True


def test_capture_processor_applies_manual_roi_to_detection_and_overlay():
    image = np.zeros((360, 480, 3), dtype=np.uint8)
    image[:, :] = (17, 20, 22)
    image[280:350, 80:204] = (70, 120, 180)
    config = {"winName": "zoom", "captureHandler": FakeCaptureHandler(image), "manualRoi": None}
    processor = CaptureProcessor([config], chromaKey=(0, 177, 64))

    assert processor.process_tiles() == []
    assert processor.set_manual_roi("zoom", (0, 0, 480, 360))

    tiles = processor.process_tiles()
    overlay, _cells = processor.build_live_debug_overlay()

    assert len(tiles) == 1
    assert processor.last_rois["zoom"] == (0, 0, 480, 360)
    assert overlay is not None


def test_capture_processor_reuses_previous_rects_between_full_detection_frames():
    first = np.zeros((160, 240, 3), dtype=np.uint8)
    second = first.copy()
    third = first.copy()
    first[30:90, 40:140] = (10, 40, 180)
    second[30:90, 40:140] = (30, 160, 40)
    third[30:90, 40:140] = (180, 40, 10)

    handler = FakeCaptureHandler(first)
    config = {"winName": "zoom", "captureHandler": handler, "manualRoi": (0, 0, 240, 160)}
    processor = CaptureProcessor([config], chromaKey=(0, 177, 64), detection_interval=3)
    calls = {"detect": 0}

    def fake_detect(image, source_key="", frame_index=0, roi=None):
        calls["detect"] += 1
        rect = (40, 30, 100, 60)
        x, y, width, height = rect
        return [
            ParticipantTile(
                track_id=None,
                source_key=source_key,
                rect=rect,
                crop=image[y : y + height, x : x + width].copy(),
                frame_index=frame_index,
                debug_reason="fake-full-detect",
            )
        ]

    processor.detector.detect = fake_detect

    first_tiles = processor.process_tiles()
    handler.image = second
    second_tiles = processor.process_tiles()
    handler.image = third
    processor.process_tiles()
    processor.process_tiles()

    assert calls["detect"] == 2
    assert second_tiles[0].track_id == first_tiles[0].track_id
    assert tuple(int(value) for value in second_tiles[0].crop[0, 0]) == (30, 160, 40)
    assert second_tiles[0].debug_reason == "fake-full-detect"


def test_capture_processor_close_releases_capture_handlers_and_cached_frames():
    image = np.zeros((120, 200, 3), dtype=np.uint8)
    handler = FakeCaptureHandler(image)
    processor = CaptureProcessor([{"winName": "zoom", "captureHandler": handler}], chromaKey=(0, 177, 64))
    with processor._lock:
        processor.last_screenshots = {"zoom": image}
        processor.last_rois = {"zoom": (0, 0, 200, 120)}

    processor.close()

    assert handler.closed
    assert processor.last_screenshots == {}
    assert processor.last_rois == {}


class FakeWorker:
    def __init__(self):
        self.join_timeout = None

    def is_alive(self):
        return True

    def join(self, timeout=None):
        self.join_timeout = timeout


class FakeClosableProcessor:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_runner_stop_joins_worker_and_closes_processor():
    runner = CaptureRunnerOnThread([], (0, 177, 64))
    fake_processor = FakeClosableProcessor()
    fake_worker = FakeWorker()
    runner.capPorcessor = fake_processor
    runner._worker = fake_worker
    runner._running = True
    runner._debug_frame = np.zeros((1, 1, 3), dtype=np.uint8)
    runner._frame = np.zeros((1, 1, 3), dtype=np.uint8)

    runner.stopFramePool()

    assert not runner._running
    assert fake_worker.join_timeout == 2.0
    assert fake_processor.closed
    assert runner._worker is None
    assert runner._debug_frame is None
    assert runner._frame is None


def test_runner_publishes_fresh_debug_frames_when_enabled():
    runner = CaptureRunnerOnThread([], (0, 177, 64))
    runner.capPorcessor = FakeDebugProcessor()
    runner.set_live_debug_overlay_enabled(True)

    runner.threadRunner()
    first = runner.get_snapshot()
    runner.threadRunner()
    second = runner.get_snapshot()

    assert first.debug_frame is not None
    assert second.debug_frame is not None
    assert int(first.debug_frame[0, 0, 0]) == 1
    assert int(second.debug_frame[0, 0, 0]) == 2
    assert second.debug_cells[0]["tile_id"] == 4


def test_runner_clears_debug_frame_when_overlay_is_disabled():
    runner = CaptureRunnerOnThread([], (0, 177, 64))
    runner.capPorcessor = FakeDebugProcessor()
    runner.set_live_debug_overlay_enabled(True)
    runner.threadRunner()

    runner.set_live_debug_overlay_enabled(False)
    snapshot = runner.get_snapshot()

    assert snapshot.debug_frame is None
    assert snapshot.debug_cells == []
