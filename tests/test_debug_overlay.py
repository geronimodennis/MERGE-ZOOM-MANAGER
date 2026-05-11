import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from CaptureProcessor import CaptureProcessor
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
