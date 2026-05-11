from math import ceil, sqrt
from typing import Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image, ImageTk

from models import CompositeFrame, ParticipantTile


RGBColor = Tuple[int, int, int]


def rgb_to_bgr(color: Optional[RGBColor]) -> Tuple[int, int, int]:
    if color is None:
        color = (0, 177, 64)
    r, g, b = [int(v) for v in color]
    return b, g, r


def blank_image(size: Tuple[int, int], rgb_color: RGBColor = (0, 177, 64)) -> np.ndarray:
    width = max(1, int(size[0]))
    height = max(1, int(size[1]))
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :] = rgb_to_bgr(rgb_color)
    return image


def aspect_fit_size(source_size: Tuple[int, int], target_size: Tuple[int, int]) -> Tuple[int, int]:
    source_width, source_height = source_size
    target_width, target_height = target_size

    if source_width <= 0 or source_height <= 0:
        return 1, 1
    if target_width == 0 and target_height == 0:
        return int(source_width), int(source_height)
    if target_width > 0 and target_height > 0:
        ratio = min(target_width / float(source_width), target_height / float(source_height))
        return max(1, int(source_width * ratio)), max(1, int(source_height * ratio))
    if target_width == 0:
        ratio = target_height / float(source_height)
        return max(1, int(source_width * ratio)), max(1, int(target_height))

    ratio = target_width / float(source_width)
    return max(1, int(target_width)), max(1, int(source_height * ratio))


def aspect_fit_rect(source_size: Tuple[int, int], target_size: Tuple[int, int]) -> Tuple[int, int, int, int]:
    fit_width, fit_height = aspect_fit_size(source_size, target_size)
    target_width, target_height = target_size
    if target_height == 0:
        target_height = fit_height

    x = max(0, int((target_width - fit_width) / 2))
    y = max(0, int((target_height - fit_height) / 2))
    return x, y, fit_width, fit_height


def resize_cv_image(image: np.ndarray, target_size: Tuple[int, int]) -> np.ndarray:
    if image is None:
        return image

    height, width = image.shape[:2]
    new_width, new_height = aspect_fit_size((width, height), target_size)
    if (new_width, new_height) == (width, height):
        return image

    interpolation = cv2.INTER_AREA if new_width < width or new_height < height else cv2.INTER_LINEAR
    return cv2.resize(image, (new_width, new_height), interpolation=interpolation)


def cv_to_photo_image(image: Optional[np.ndarray], target_size: Tuple[int, int], background: RGBColor) -> ImageTk.PhotoImage:
    if image is None:
        image = blank_image((max(1, target_size[0]), max(1, target_size[1] or 1)), background)
    resized = resize_cv_image(image, target_size)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    return ImageTk.PhotoImage(image=Image.fromarray(rgb))


def _tile_crop(tile_or_image) -> np.ndarray:
    if isinstance(tile_or_image, ParticipantTile):
        return tile_or_image.crop
    return tile_or_image


def _tile_id(tile_or_image):
    if isinstance(tile_or_image, ParticipantTile):
        return tile_or_image.track_id
    return None


def stack_tiles(
    tiles: Sequence,
    background: RGBColor = (0, 177, 64),
    columns: Optional[int] = None,
) -> CompositeFrame:
    visible_tiles = [tile for tile in tiles if _tile_crop(tile) is not None]
    count = len(visible_tiles)
    if count == 0:
        return CompositeFrame(None, [], 0, 0, 0)

    if columns is None:
        columns = max(1, int(ceil(sqrt(count))))
    rows = int(ceil(count / float(columns)))

    first = _tile_crop(visible_tiles[0])
    tile_height, tile_width = first.shape[:2]
    tile_width = max(1, tile_width)
    tile_height = max(1, tile_height)

    output = blank_image((columns * tile_width, rows * tile_height), background)
    cells: List[dict] = []

    for index, tile in enumerate(visible_tiles):
        row = index // columns
        column = index % columns
        x = column * tile_width
        y = row * tile_height

        crop = _tile_crop(tile)
        if crop.shape[:2] != (tile_height, tile_width):
            crop = cv2.resize(crop, (tile_width, tile_height), interpolation=cv2.INTER_LINEAR)

        output[y : y + tile_height, x : x + tile_width] = crop
        cells.append(
            {
                "tile_id": _tile_id(tile),
                "index": index,
                "rect": (x, y, tile_width, tile_height),
            }
        )

    return CompositeFrame(output, cells, columns, rows, count)


def find_cell_at(cells: Iterable[dict], x: float, y: float) -> Optional[dict]:
    for cell in cells:
        cell_x, cell_y, width, height = cell["rect"]
        if cell_x <= x < cell_x + width and cell_y <= y < cell_y + height:
            return cell
    return None


def draw_debug_overlay(
    image: np.ndarray,
    tiles: Sequence[ParticipantTile],
    title: Optional[str] = None,
    roi: Optional[Tuple[int, int, int, int]] = None,
) -> np.ndarray:
    overlay = image.copy()
    if roi is not None:
        roi_x, roi_y, roi_width, roi_height = roi
        cv2.rectangle(overlay, (roi_x, roi_y), (roi_x + roi_width, roi_y + roi_height), (255, 170, 40), 2)
        cv2.putText(
            overlay,
            "gallery roi",
            (roi_x + 6, max(18, roi_y + 18)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 170, 40),
            2,
        )

    if title:
        cv2.rectangle(overlay, (0, 0), (min(overlay.shape[1] - 1, 620), 28), (0, 0, 0), -1)
        cv2.putText(overlay, title, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (245, 245, 245), 2)

    for tile in tiles:
        x, y, width, height = tile.rect
        color = (80, 220, 80) if tile.track_id is not None else (0, 200, 255)
        cv2.rectangle(overlay, (x, y), (x + width, y + height), color, 2)
        label_parts = [f"#{tile.track_id if tile.track_id is not None else '?'}", f"{tile.confidence:.2f}"]
        if tile.debug_reason:
            label_parts.append(tile.debug_reason)
        label_parts.append(f"{width}x{height}")
        label = " ".join(label_parts)
        label_y = max(18, y + 18)
        label_width = min(overlay.shape[1] - x - 1, max(80, len(label) * 8))
        if label_width > 0:
            cv2.rectangle(overlay, (x, max(0, label_y - 15)), (x + label_width, label_y + 4), (0, 0, 0), -1)
        cv2.putText(overlay, label, (x + 4, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    return overlay
