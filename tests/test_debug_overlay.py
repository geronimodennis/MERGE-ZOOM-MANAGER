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
    assert tuple(int(value) for value in frame[30, 20]) == (80, 220, 80)


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
