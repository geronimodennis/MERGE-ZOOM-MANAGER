import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from image_utils import stack_tiles
from models import ParticipantTile
from participant_detection import MAX_PARTICIPANT_RECT_HEIGHT, MAX_PARTICIPANT_RECT_WIDTH, DetectionCandidate, ZoomGalleryDetector
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


def full_frame_roi(image):
    height, width = image.shape[:2]
    return 0, 0, width, height


def put_centered_text(image, text, center):
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 1.15
    thickness = 2
    text_size, baseline = cv2.getTextSize(text, font, scale, thickness)
    x = int(round(center[0] - text_size[0] / 2))
    y = int(round(center[1] + text_size[1] / 2))
    cv2.putText(image, text, (x, y), font, scale, (235, 235, 235), thickness)


def test_detector_finds_dynamic_gallery_tiles():
    image, _rects = synthetic_gallery()
    detector = ZoomGalleryDetector()

    tiles = detector.detect(image, source_key="zoom", roi=full_frame_roi(image))

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

    tiles = detector.detect(image, source_key="zoom", roi=full_frame_roi(image))

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
    card_h = 450
    card_w = 800
    first_x = 150
    second_x = 970

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

    tiles = detector.detect(image, source_key="zoom", roi=full_frame_roi(image))

    assert len(tiles) == 2
    assert tiles[0].x <= first_x + 15
    assert abs(tiles[0].width - card_w) < 60
    assert abs(tiles[0].height - card_h) < 60
    assert tiles[0].width <= MAX_PARTICIPANT_RECT_WIDTH
    assert tiles[0].height <= MAX_PARTICIPANT_RECT_HEIGHT
    assert tiles[1].x >= second_x - 20
    assert abs(tiles[1].width - card_w) < 60
    assert tiles[1].width <= MAX_PARTICIPANT_RECT_WIDTH
    assert tiles[1].height <= MAX_PARTICIPANT_RECT_HEIGHT


def test_detector_uses_name_badges_for_gray_open_camera_tiles_without_edges():
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    image[:, :] = (94, 94, 94)

    card_y = 260
    card_h = 315
    card_w = 560
    card_xs = [80, 680, 1280]
    for index, card_x in enumerate(card_xs):
        image[card_y : card_y + card_h, card_x : card_x + card_w] = (94, 94, 94)
        cv2.ellipse(
            image,
            (card_x + card_w // 2, card_y + 150),
            (74, 104),
            0,
            0,
            360,
            (102, 102, 102),
            -1,
        )

        badge_x = card_x + 8
        badge_y = card_y + card_h - 30
        cv2.rectangle(image, (badge_x, badge_y), (badge_x + 132, badge_y + 28), (35, 35, 35), -1)
        cv2.circle(image, (badge_x + 13, badge_y + 14), 8, (45, 45, 235), -1)
        cv2.putText(
            image,
            f"Person {index + 1}",
            (badge_x + 30, badge_y + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (245, 245, 245),
            2,
        )

    detector = ZoomGalleryDetector()

    tiles = detector.detect(image, source_key="zoom", roi=full_frame_roi(image))

    assert len(tiles) == 3
    assert [tile.debug_reason for tile in tiles] == [
        "zoom-name-badge-layout",
        "zoom-name-badge-layout",
        "zoom-name-badge-layout",
    ]
    assert all(tile.width <= MAX_PARTICIPANT_RECT_WIDTH for tile in tiles)
    assert all(tile.height <= MAX_PARTICIPANT_RECT_HEIGHT for tile in tiles)
    assert [tile.x for tile in tiles] == sorted(tile.x for tile in tiles)


def test_detector_uses_gallery_rectangles_before_inner_fragments():
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    image[:, :] = (17, 20, 22)
    image[:78, :] = (43, 43, 45)
    image[995:, :] = (2, 2, 3)

    card_y = 270
    card_h = 450
    card_w = 800
    first_x = 160
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

    top_menu_h = 53
    bottom_menu_y = 980
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

    assert roi == (0, top_menu_h, 1920, bottom_menu_y - top_menu_h)
    assert len(tiles) == 2
    assert all(tile.y >= top_menu_h for tile in tiles)
    assert all(tile.y + tile.height <= bottom_menu_y for tile in tiles)


def test_gallery_roi_uses_fixed_zoom_menu_dimensions_by_default():
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)

    assert ZoomGalleryDetector._gallery_search_roi(image) == (0, 53, 1920, 927)


def test_gallery_roi_height_updates_when_zoom_window_resizes():
    image = np.zeros((720, 1280, 3), dtype=np.uint8)

    assert ZoomGalleryDetector._gallery_search_roi(image) == (0, 53, 1280, 567)


def test_detector_accepts_manual_roi_override():
    image = np.zeros((360, 480, 3), dtype=np.uint8)
    image[:, :] = (17, 20, 22)
    image[280:350, 80:204] = (70, 120, 180)
    detector = ZoomGalleryDetector()

    default_tiles = detector.detect(image, source_key="zoom")
    manual_tiles = detector.detect(image, source_key="zoom", roi=full_frame_roi(image))

    assert default_tiles == []
    assert len(manual_tiles) == 1


def test_detector_infers_camera_off_tiles_from_centered_names():
    image = np.zeros((600, 1000, 3), dtype=np.uint8)
    image[:, :] = (17, 20, 22)
    put_centered_text(image, "Alice", (250, 300))
    put_centered_text(image, "Bob Martin", (750, 300))
    detector = ZoomGalleryDetector()

    tiles = detector.detect(image, source_key="zoom", roi=full_frame_roi(image))

    assert len(tiles) == 2
    assert [tile.debug_reason for tile in tiles] == ["center-name-layout", "center-name-layout"]
    assert all(430 <= tile.width <= 500 for tile in tiles)
    assert all(240 <= tile.height <= 290 for tile in tiles)
    assert tiles[0].x < 40
    assert 480 <= tiles[1].x <= 530


def test_detector_rejects_participant_rectangles_larger_than_max_bound():
    detector = ZoomGalleryDetector()

    assert detector._is_valid_rect((0, 0, MAX_PARTICIPANT_RECT_WIDTH, MAX_PARTICIPANT_RECT_HEIGHT), 1920, 1080)
    assert not detector._is_valid_rect((0, 0, MAX_PARTICIPANT_RECT_WIDTH + 1, MAX_PARTICIPANT_RECT_HEIGHT), 1920, 1080)
    assert not detector._is_valid_rect((0, 0, MAX_PARTICIPANT_RECT_WIDTH, MAX_PARTICIPANT_RECT_HEIGHT + 1), 1920, 1080)


def test_detector_uses_greenish_light_rectangle_when_normal_detection_fails():
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    image[:, :] = (17, 20, 22)
    image[260:820, 450:1450] = (112, 174, 132)
    detector = ZoomGalleryDetector()

    tiles = detector.detect(image, source_key="zoom", roi=full_frame_roi(image))

    assert len(tiles) == 1
    assert tiles[0].debug_reason == "greenish-light-base-rectangle"
    assert tiles[0].width <= MAX_PARTICIPANT_RECT_WIDTH
    assert tiles[0].height <= MAX_PARTICIPANT_RECT_HEIGHT


def test_detector_uses_probable_base_rectangle_when_no_visual_fallback_exists():
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    image[:, :] = (17, 20, 22)
    detector = ZoomGalleryDetector()

    tiles = detector.detect(image, source_key="zoom", roi=full_frame_roi(image))

    assert len(tiles) == 1
    assert tiles[0].debug_reason == "probable-base-rectangle"
    assert tiles[0].width == MAX_PARTICIPANT_RECT_WIDTH
    assert tiles[0].height == MAX_PARTICIPANT_RECT_HEIGHT


def test_centered_name_fallback_stays_inside_max_participant_bound():
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    image[:, :] = (17, 20, 22)
    put_centered_text(image, "Camera Off", (960, 540))
    detector = ZoomGalleryDetector()

    tiles = detector.detect(image, source_key="zoom", roi=full_frame_roi(image))

    assert len(tiles) == 1
    assert tiles[0].debug_reason == "center-name-layout"
    assert tiles[0].width <= MAX_PARTICIPANT_RECT_WIDTH
    assert tiles[0].height <= MAX_PARTICIPANT_RECT_HEIGHT


def test_centered_name_fallback_ignores_partial_edge_box_near_label_edge():
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    image[:, :] = (17, 20, 22)
    roi = (0, 53, 1920, 855)
    put_centered_text(image, "Dennis", (960, 480))
    partial_edge = DetectionCandidate((210, 160, 780, 409), 0.64, "edge")
    detector = ZoomGalleryDetector()

    candidates = detector._detect_from_centered_names(image, roi, [partial_edge])

    assert len(candidates) == 1
    assert candidates[0].reason == "center-name-layout"
    assert candidates[0].rect[2] <= MAX_PARTICIPANT_RECT_WIDTH
    assert candidates[0].rect[3] <= MAX_PARTICIPANT_RECT_HEIGHT


def test_centered_name_fallback_uses_nearest_detected_tile_size():
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    image[:, :] = (17, 20, 22)
    roi = full_frame_roi(image)
    put_centered_text(image, "Camera Off", (940, 260))
    detected_tile = DetectionCandidate((80, 88, 640, 360), 0.64, "edge")
    detector = ZoomGalleryDetector()

    candidates = detector._detect_from_centered_names(image, roi, [detected_tile])

    assert len(candidates) == 1
    assert candidates[0].reason == "center-name-layout"
    assert candidates[0].rect[2:] == detected_tile.rect[2:]


def test_centered_name_fallback_allows_overlap_margin_from_neighbor_tile():
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    image[:, :] = (17, 20, 22)
    roi = full_frame_roi(image)
    put_centered_text(image, "Camera Off", (680, 260))
    neighbor_tile = DetectionCandidate((100, 88, 600, 338), 0.98, "gallery-rectangle")
    detector = ZoomGalleryDetector()

    candidates = detector._detect_from_centered_names(image, roi, [neighbor_tile])

    assert len(candidates) == 1
    assert candidates[0].reason == "center-name-layout"
    assert candidates[0].rect[2:] == neighbor_tile.rect[2:]


def test_centered_name_fallback_suppresses_bottom_name_badge_inside_tile():
    image = np.zeros((520, 900, 3), dtype=np.uint8)
    image[:, :] = (18, 18, 18)
    put_centered_text(image, "DenDen", (210, 412))
    existing_tile = DetectionCandidate((90, 70, 700, 394), 0.92, "fragment-union")
    detector = ZoomGalleryDetector()

    candidates = detector._detect_from_centered_names(image, full_frame_roi(image), [existing_tile])

    assert candidates == []


def test_centered_name_fallback_keeps_nearest_size_inside_roi_edge():
    detector = ZoomGalleryDetector()

    rect = detector._rect_centered_in_roi(960, 900, 900, 506, (0, 53, 1920, 855))

    assert rect == (510, 402, 900, 506)


def test_dedupe_allows_overlapping_center_name_with_distinct_center():
    detector = ZoomGalleryDetector()
    existing_tile = DetectionCandidate((100, 100, 700, 400), 0.98, "gallery-rectangle")
    camera_off_tile = DetectionCandidate((260, 100, 700, 400), 0.74, "center-name-layout")

    candidates = detector._dedupe([existing_tile, camera_off_tile])

    assert candidates == [existing_tile, camera_off_tile]


def test_detector_removes_overlapping_partial_edge_when_full_tile_exists():
    detector = ZoomGalleryDetector()
    partial_edge = DetectionCandidate((210, 160, 780, 409), 0.64, "edge")
    full_tile = DetectionCandidate((488, 213, 945, 535), 0.74, "center-name-layout")

    candidates = detector._remove_overlapping_unstable_boxes([partial_edge, full_tile])

    assert candidates == [full_tile]


def test_tracker_keeps_ids_when_gallery_layout_changes():
    detector = ZoomGalleryDetector()
    tracker = ParticipantTracker()

    first_image, _ = synthetic_gallery(columns=3, rows=2)
    first_tiles = tracker.update(detector.detect(first_image, source_key="zoom", roi=full_frame_roi(first_image)))
    first_ids = {tile.track_id for tile in first_tiles}

    second_image, _ = synthetic_gallery(columns=2, rows=3, tile_size=(150, 84), gap=14, offset=(34, 20))
    second_tiles = tracker.update(detector.detect(second_image, source_key="zoom", roi=full_frame_roi(second_image)))
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
