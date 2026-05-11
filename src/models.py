from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


Rect = Tuple[int, int, int, int]


@dataclass
class ParticipantTile:
    """A detected Zoom Gallery View participant tile."""

    track_id: Optional[int]
    source_key: str
    rect: Rect
    crop: np.ndarray
    confidence: float = 0.0
    descriptor: Optional[np.ndarray] = None
    frame_index: int = 0
    last_seen: float = 0.0
    missing_frames: int = 0
    debug_reason: str = ""

    @property
    def x(self) -> int:
        return self.rect[0]

    @property
    def y(self) -> int:
        return self.rect[1]

    @property
    def width(self) -> int:
        return self.rect[2]

    @property
    def height(self) -> int:
        return self.rect[3]

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.width / 2.0, self.y + self.height / 2.0)

    @property
    def area(self) -> int:
        return self.width * self.height


@dataclass
class CompositeFrame:
    """A rendered gallery/group image plus source tile positions inside it."""

    frame: Optional[np.ndarray]
    cells: list
    columns: int
    rows: int
    count: int
