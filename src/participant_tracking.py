from time import time
from typing import Dict, Iterable, List, Optional, Set, Tuple

import numpy as np

from models import ParticipantTile, Rect


class ParticipantTracker:
    """Assign stable ids to detected tiles across frame, resize, and layout changes."""

    def __init__(self, max_missing_frames: int = 90, match_threshold: float = 0.36):
        self.max_missing_frames = max_missing_frames
        self.match_threshold = match_threshold
        self._next_id = 1
        self._tracks: Dict[int, ParticipantTile] = {}

    def update(self, detections: Iterable[ParticipantTile]) -> List[ParticipantTile]:
        detections = list(detections)
        now = time()

        matches = self._match(detections)
        matched_track_ids: Set[int] = set()
        matched_detection_indexes: Set[int] = set()

        for track_id, detection_index in matches:
            detection = detections[detection_index]
            detection.track_id = track_id
            detection.last_seen = now
            detection.missing_frames = 0
            self._tracks[track_id] = detection
            matched_track_ids.add(track_id)
            matched_detection_indexes.add(detection_index)

        for track_id in list(self._tracks.keys()):
            if track_id in matched_track_ids:
                continue
            previous = self._tracks[track_id]
            previous.missing_frames += 1
            if previous.missing_frames > self.max_missing_frames:
                del self._tracks[track_id]

        for index, detection in enumerate(detections):
            if index in matched_detection_indexes:
                continue
            track_id = self._next_id
            self._next_id += 1
            detection.track_id = track_id
            detection.last_seen = now
            detection.missing_frames = 0
            self._tracks[track_id] = detection

        visible = [tile for tile in self._tracks.values() if tile.missing_frames == 0]
        visible.sort(key=lambda tile: (tile.source_key, tile.y, tile.x))
        return visible

    def get(self, track_id: int, include_missing: bool = False) -> Optional[ParticipantTile]:
        tile = self._tracks.get(track_id)
        if tile is None:
            return None
        if tile.missing_frames and not include_missing:
            return None
        return tile

    def get_many(self, track_ids: Iterable[int], include_missing: bool = False) -> List[ParticipantTile]:
        tiles = []
        for track_id in track_ids:
            tile = self.get(track_id, include_missing=include_missing)
            if tile is not None:
                tiles.append(tile)
        return tiles

    def missing_count(self, track_ids: Iterable[int]) -> int:
        count = 0
        for track_id in track_ids:
            tile = self._tracks.get(track_id)
            if tile is None or tile.missing_frames:
                count += 1
        return count

    def _match(self, detections: List[ParticipantTile]) -> List[Tuple[int, int]]:
        if not self._tracks or not detections:
            return []

        scored_pairs = []
        for track_id, previous in self._tracks.items():
            if previous.missing_frames > self.max_missing_frames:
                continue
            for detection_index, detection in enumerate(detections):
                if previous.source_key != detection.source_key:
                    continue
                score = self._match_score(previous, detection)
                if score >= self.match_threshold:
                    scored_pairs.append((score, track_id, detection_index))

        scored_pairs.sort(reverse=True, key=lambda item: item[0])
        used_tracks: Set[int] = set()
        used_detections: Set[int] = set()
        matches: List[Tuple[int, int]] = []

        for _score, track_id, detection_index in scored_pairs:
            if track_id in used_tracks or detection_index in used_detections:
                continue
            used_tracks.add(track_id)
            used_detections.add(detection_index)
            matches.append((track_id, detection_index))
        return matches

    def _match_score(self, previous: ParticipantTile, detection: ParticipantTile) -> float:
        overlap = self._iou(previous.rect, detection.rect)
        appearance = self._descriptor_similarity(previous.descriptor, detection.descriptor)
        position = self._center_similarity(previous, detection)
        size = self._size_similarity(previous.rect, detection.rect)
        return 0.30 * overlap + 0.50 * appearance + 0.15 * position + 0.05 * size

    @staticmethod
    def _descriptor_similarity(left: Optional[np.ndarray], right: Optional[np.ndarray]) -> float:
        if left is None or right is None or left.shape != right.shape:
            return 0.0
        diff = np.mean(np.abs(left.astype(np.float32) - right.astype(np.float32)))
        return max(0.0, min(1.0, 1.0 - diff / 2.0))

    @staticmethod
    def _center_similarity(previous: ParticipantTile, detection: ParticipantTile) -> float:
        px, py = previous.center
        dx, dy = detection.center
        distance = ((px - dx) ** 2 + (py - dy) ** 2) ** 0.5
        scale = max(previous.width, previous.height, detection.width, detection.height, 1)
        return max(0.0, 1.0 - min(1.0, distance / (scale * 2.0)))

    @staticmethod
    def _size_similarity(left: Rect, right: Rect) -> float:
        left_area = max(1, left[2] * left[3])
        right_area = max(1, right[2] * right[3])
        ratio = min(left_area, right_area) / float(max(left_area, right_area))
        return max(0.0, min(1.0, ratio))

    @staticmethod
    def _iou(left: Rect, right: Rect) -> float:
        lx, ly, lw, lh = left
        rx, ry, rw, rh = right
        x1 = max(lx, rx)
        y1 = max(ly, ry)
        x2 = min(lx + lw, rx + rw)
        y2 = min(ly + lh, ry + rh)
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        union = lw * lh + rw * rh - intersection
        return intersection / float(union) if union else 0.0
