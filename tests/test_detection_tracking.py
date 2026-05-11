import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from image_utils import stack_tiles
from models import ParticipantTile
from participant_detection import ZoomGalleryDetector
from participant_tracking import ParticipantTracker


def synthetic_gallery(columns=3, rows=2, tile_size=(160, 90), gap=12, offset=(20, 28)):
    tile_width, tile_height = tile_size
    width = offset[0] * 2 + columns * tile_width + (columns - 1) * gap
    height = offset[1] * 2 + rows * tile_height + (rows - 1) * gap
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :] = (18, 18, 18)

    colors = [
        (60, 80, 220),
        (80, 180, 80),
        (220, 120, 60),
        (160, 90, 200),
        (70, 190, 210),
        (210, 210, 80),
    ]
    rects = []
    for index in range(columns * rows):
        row = index // columns
        column = index % columns
        x = offset[0] + column * (tile_width + gap)
        y = offset[1] + row * (tile_height + gap)
        color = colors[index % len(colors)]
        image[y : y + tile_height, x : x + tile_width] = color
        cv2.putText(
            image,
            f"P{index + 1}",
            (x + 18, y + 52),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (245, 245, 245),
            2,
        )
        rects.append((x, y, tile_width, tile_height))
    return image, rects


def test_detector_finds_dynamic_gallery_tiles():
    image, _rects = synthetic_gallery()
    detector = ZoomGalleryDetector()

    tiles = detector.detect(image, source_key="zoom")

    assert len(tiles) == 6
    assert all(tile.width >= 150 and tile.height >= 80 for tile in tiles)
    assert [tile.rect for tile in tiles] == sorted([tile.rect for tile in tiles], key=lambda rect: (rect[1], rect[0]))


def test_tracker_keeps_ids_when_gallery_layout_changes():
    detector = ZoomGalleryDetector()
    tracker = ParticipantTracker()

    first_image, _ = synthetic_gallery(columns=3, rows=2)
    first_tiles = tracker.update(detector.detect(first_image, source_key="zoom"))
    first_ids = {tile.track_id for tile in first_tiles}

    second_image, _ = synthetic_gallery(columns=2, rows=3, tile_size=(150, 84), gap=14, offset=(34, 20))
    second_tiles = tracker.update(detector.detect(second_image, source_key="zoom"))
    second_ids = {tile.track_id for tile in second_tiles}

    assert len(first_ids) == 6
    assert second_ids == first_ids


def test_stack_tiles_keeps_cell_metadata_for_pins():
    crops = [np.full((80, 120, 3), value, dtype=np.uint8) for value in (30, 90, 150)]
    tiles = [
        ParticipantTile(track_id=index + 1, source_key="zoom", rect=(0, 0, 120, 80), crop=crop)
        for index, crop in enumerate(crops)
    ]

    composite = stack_tiles(tiles, background=(0, 177, 64))

    assert composite.count == 3
    assert composite.columns == 2
    assert composite.rows == 2
    assert [cell["tile_id"] for cell in composite.cells] == [1, 2, 3]
