import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from image_utils import stack_tiles
from models import ParticipantTile
from participant_detection import DetectionCandidate, ZoomGalleryDetector
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


def test_detector_consolidates_single_tile_content_fragments():
    image = np.zeros((520, 900, 3), dtype=np.uint8)
    image[:, :] = (18, 18, 18)
    tile_x, tile_y, tile_width, tile_height = 90, 70, 700, 394
    image[tile_y : tile_y + tile_height, tile_x : tile_x + tile_width] = (22, 22, 22)

    cv2.ellipse(image, (tile_x + 180, tile_y + 150), (115, 155), 0, 0, 360, (90, 150, 205), -1)
    cv2.rectangle(image, (tile_x + 430, tile_y + 40), (tile_x + 680, tile_y + 260), (55, 95, 80), -1)
    cv2.rectangle(image, (tile_x + 24, tile_y + tile_height - 78), (tile_x + 250, tile_y + tile_height - 20), (12, 12, 12), -1)
    cv2.putText(
        image,
        "DenDen",
        (tile_x + 35, tile_y + tile_height - 36),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.5,
        (245, 245, 245),
        4,
    )

    detector = ZoomGalleryDetector()

    tiles = detector.detect(image, source_key="zoom")

    assert len(tiles) == 1
    assert tiles[0].width > 500
    assert tiles[0].height > 300


def test_detector_cleanup_keeps_outer_card_and_drops_inner_fragments():
    detector = ZoomGalleryDetector()
    candidates = [
        DetectionCandidate((80, 90, 720, 405), 0.92, "outer-card"),
        DetectionCandidate((250, 160, 270, 170), 0.88, "inner-video"),
        DetectionCandidate((100, 440, 190, 34), 0.86, "name-badge"),
    ]

    filtered = detector._filter_inconsistent_tile_sizes(detector._remove_containing_boxes(candidates))

    assert [candidate.reason for candidate in filtered] == ["outer-card"]


def test_detector_cleanup_drops_multi_tile_container_not_real_tiles():
    detector = ZoomGalleryDetector()
    candidates = [
        DetectionCandidate((40, 100, 1840, 520), 0.75, "row-container"),
        DetectionCandidate((40, 100, 920, 518), 0.96, "left-card"),
        DetectionCandidate((960, 100, 920, 518), 0.96, "right-card"),
    ]

    filtered = detector._remove_containing_boxes(candidates)

    assert [candidate.reason for candidate in filtered] == ["left-card", "right-card"]


def test_detector_uses_zoom_name_badges_to_infer_full_cards():
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    image[:, :] = (17, 20, 22)
    image[:78, :] = (43, 43, 45)
    image[995:, :] = (2, 2, 3)

    card_y = 281
    card_h = 526
    card_w = 936
    first_x = 24
    second_x = 960

    image[card_y : card_y + card_h, first_x : first_x + card_w] = (34, 34, 34)
    image[card_y : card_y + card_h, second_x : second_x + card_w] = (34, 34, 34)

    video_x = first_x + 320
    video_w = 360
    image[card_y : card_y + card_h, video_x : video_x + video_w] = (22, 22, 30)
    cv2.ellipse(image, (video_x + 185, card_y + 260), (95, 135), 0, 0, 360, (115, 155, 185), -1)
    cv2.rectangle(image, (second_x + 320, card_y + 180), (second_x + 615, card_y + 250), (34, 34, 34), -1)
    cv2.putText(
        image,
        "Dennis",
        (second_x + 320, card_y + 295),
        cv2.FONT_HERSHEY_SIMPLEX,
        2.5,
        (245, 245, 245),
        6,
    )

    for badge_x, label in ((first_x + 8, "Dennis Geronimo"), (second_x + 8, "Dennis")):
        badge_y = card_y + card_h - 30
        badge_w = 195 if "Geronimo" in label else 100
        cv2.rectangle(image, (badge_x, badge_y), (badge_x + badge_w, badge_y + 28), (35, 35, 35), -1)
        cv2.circle(image, (badge_x + 13, badge_y + 14), 8, (45, 45, 235), -1)
        cv2.putText(
            image,
            label,
            (badge_x + 30, badge_y + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (245, 245, 245),
            2,
        )

    detector = ZoomGalleryDetector()

    tiles = detector.detect(image, source_key="zoom")

    assert len(tiles) == 2
    assert tiles[0].x <= first_x + 15
    assert abs(tiles[0].width - card_w) < 60
    assert abs(tiles[0].height - card_h) < 60
    assert tiles[1].x >= second_x - 20
    assert abs(tiles[1].width - card_w) < 60


def test_detector_uses_gallery_rectangles_before_inner_fragments():
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    image[:, :] = (17, 20, 22)
    image[:78, :] = (43, 43, 45)
    image[995:, :] = (2, 2, 3)

    card_y = 270
    card_h = 504
    card_w = 896
    first_x = 64
    second_x = first_x + card_w

    image[card_y : card_y + card_h, first_x : second_x + card_w] = (34, 34, 34)
    cv2.rectangle(image, (first_x + 330, card_y + 92), (first_x + 575, card_y + 337), (92, 142, 180), -1)
    cv2.ellipse(image, (first_x + 460, card_y + 250), (78, 116), 0, 0, 360, (118, 160, 195), -1)
    cv2.rectangle(image, (second_x + 310, card_y + 138), (second_x + 620, card_y + 300), (28, 28, 36), -1)
    cv2.circle(image, (second_x + 465, card_y + 238), 85, (78, 118, 170), -1)

    detector = ZoomGalleryDetector()

    tiles = detector.detect(image, source_key="zoom")

    assert len(tiles) == 2
    assert [tile.debug_reason for tile in tiles] == ["gallery-rectangle-split", "gallery-rectangle-split"]
    assert abs(tiles[0].x - first_x) < 20
    assert abs(tiles[0].width - card_w) < 30
    assert abs(tiles[0].height - card_h) < 30
    assert abs(tiles[1].x - second_x) < 20
    assert abs(tiles[1].width - card_w) < 30


def test_detector_excludes_zoom_top_and_bottom_menu_bars():
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    image[:, :] = (17, 20, 22)

    top_menu_h = 92
    bottom_menu_y = 958
    image[:top_menu_h, :] = (17, 20, 22)
    image[bottom_menu_y:, :] = (17, 20, 22)

    cv2.putText(image, "Zoom Meeting", (28, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (235, 235, 235), 2)
    cv2.putText(image, "View", (1810, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (235, 235, 235), 2)
    for x in range(420, 1500, 170):
        cv2.circle(image, (x, 1018), 18, (235, 235, 235), 2)
        cv2.putText(image, "Menu", (x - 28, 1058), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (235, 235, 235), 1)

    card_y = 220
    card_h = 506
    card_w = 900
    first_x = 60
    second_x = 960
    image[card_y : card_y + card_h, first_x : first_x + card_w] = (34, 34, 34)
    image[card_y : card_y + card_h, second_x : second_x + card_w] = (34, 34, 34)

    cv2.ellipse(image, (first_x + 450, card_y + 360), (90, 125), 0, 0, 360, (104, 145, 188), -1)
    cv2.circle(image, (second_x + 450, card_y + 350), 105, (72, 116, 172), -1)

    roi = ZoomGalleryDetector._gallery_search_roi(image)
    detector = ZoomGalleryDetector()

    tiles = detector.detect(image, source_key="zoom")

    assert roi[1] >= top_menu_h - 10
    assert roi[1] + roi[3] <= bottom_menu_y + 10
    assert len(tiles) == 2
    assert all(tile.y >= top_menu_h - 10 for tile in tiles)
    assert all(tile.y + tile.height <= bottom_menu_y + 10 for tile in tiles)


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
