from collections import deque
from dataclasses import dataclass
from threading import Lock, Thread
from time import perf_counter
from typing import Iterable, List, Optional

import numpy as np

from CaptureProcessor import CaptureProcessor
from image_utils import cv_to_photo_image, stack_tiles
from performance import FpsCounter, FrameRateLimiter, get_logger


logger = get_logger()


@dataclass
class CaptureSnapshot:
    frame: Optional[np.ndarray]
    tiles: list
    cells: list
    imageListInfo: list
    capture_fps: float
    missing_pins: int


class CaptureRunnerOnThread:
    def __init__(self, _captureConfiguration, _chromaColorKey, target_fps: int = 30):
        self.captureConfiguration = _captureConfiguration
        self.chromaColorKey = _chromaColorKey or (0, 177, 64)
        self.target_fps = target_fps
        self.width = 0
        self.background = self.chromaColorKey
        self.treshholdFrameCount = 3

        self._capPorcessor = None
        self._frame = None
        self._groupFrame = None
        self._framePool = deque(maxlen=3)
        self._groupFramePool = deque(maxlen=3)
        self._running = False
        self._worker = None
        self._lock = Lock()
        self._uniformSize = (0, 0)
        self._imageListInfo = [0, 0, 0, []]
        self._imageTileInfo = [0, 0, 0, []]
        self._groupImageListInfo = [0, 0, 0]
        self._imageIndexes: List[int] = []
        self._composite_cells = []
        self._group_cells = []
        self._frmaeCreateionTime = 0.0
        self._capture_fps = 0.0
        self._missing_pins = 0
        self._last_logged_fps = 0.0

        self.initCapturePocessor()

    @property
    def frame(self):
        return self._frame

    @frame.setter
    def frame(self, value):
        self._frame = value

    @property
    def frmaeCreateionTime(self):
        return self._frmaeCreateionTime

    @frmaeCreateionTime.setter
    def frmaeCreateionTime(self, value):
        self._frmaeCreateionTime = value

    @property
    def framePool(self):
        return self._framePool

    @framePool.setter
    def framePool(self, value):
        self._framePool = deque(value, maxlen=3)

    @property
    def groupFrame(self):
        return self._groupFrame

    @groupFrame.setter
    def groupFrame(self, value):
        self._groupFrame = value

    @property
    def groupFramePool(self):
        return self._groupFramePool

    @groupFramePool.setter
    def groupFramePool(self, value):
        self._groupFramePool = deque(value, maxlen=3)

    @property
    def uniformSize(self):
        return self._uniformSize

    @uniformSize.setter
    def uniformSize(self, value):
        self._uniformSize = value

    @property
    def imageListInfo(self):
        return self._imageListInfo

    @imageListInfo.setter
    def imageListInfo(self, value):
        self._imageListInfo = value

    @property
    def groupImageListInfo(self):
        return self._groupImageListInfo

    @groupImageListInfo.setter
    def groupImageListInfo(self, value):
        self._groupImageListInfo = value

    @property
    def imageIndexes(self):
        return self._imageIndexes

    @imageIndexes.setter
    def imageIndexes(self, value):
        self._imageIndexes = list(value)

    @property
    def capPorcessor(self):
        return self._capPorcessor

    @capPorcessor.setter
    def capPorcessor(self, value):
        self._capPorcessor = value

    @property
    def compositeCells(self):
        return self._composite_cells

    @property
    def groupCells(self):
        return self._group_cells

    @property
    def captureFps(self):
        return self._capture_fps

    @property
    def missingPins(self):
        return self._missing_pins

    def initCapturePocessor(self):
        if self.capPorcessor is None:
            self.capPorcessor = CaptureProcessor(self.captureConfiguration, self.chromaColorKey)
        self.capPorcessor.setChromaKey(self.chromaColorKey)
        return self

    def start(self):
        self.startFramePool(self.background, self.width or 0, self.treshholdFrameCount)
        return self

    def startNoThread(self):
        self.frame = self.threadRunner()
        return self

    def startFramePool(self, background, imageWidth, treshholdFrameCount=3):
        self.background = background or self.chromaColorKey
        self.width = imageWidth
        self.treshholdFrameCount = max(1, min(5, int(treshholdFrameCount)))
        if self._running:
            return self
        self._running = True
        self._worker = Thread(target=self._capture_loop, daemon=True)
        self._worker.start()
        return self

    def stopFramePool(self):
        self._running = False
        self._framePool.clear()
        self._groupFramePool.clear()

    def stopGroupImagesPool(self):
        self._groupFramePool.clear()

    def startGroupImages(self):
        self._refresh_group_frame()
        return self

    def startGroupImagesPool(self, background, imageWidth):
        self.background = background or self.background
        self.width = imageWidth
        return self.start()

    def setImageIndexes(self, imageIndexes):
        cleaned = []
        for value in imageIndexes:
            if value is None:
                continue
            int_value = int(value)
            if int_value not in cleaned:
                cleaned.append(int_value)
        with self._lock:
            self.imageIndexes = cleaned
        return self

    def addPinnedTile(self, track_id):
        with self._lock:
            if track_id is not None and int(track_id) not in self._imageIndexes:
                self._imageIndexes.append(int(track_id))
        return self

    def removePinnedTile(self, track_id):
        with self._lock:
            self._imageIndexes = [tile_id for tile_id in self._imageIndexes if tile_id != track_id]
        return self

    def clearPinnedTiles(self):
        with self._lock:
            self._imageIndexes.clear()
        return self

    def get_tile(self, track_id, include_missing=False):
        return self.capPorcessor.get_tile(track_id, include_missing=include_missing)

    def get_tiles_by_ids(self, track_ids, include_missing=False):
        return self.capPorcessor.get_tiles_by_ids(track_ids, include_missing=include_missing)

    def get_pinned_composite(self, track_ids: Iterable[int]):
        tiles = self.get_tiles_by_ids(track_ids)
        composite = stack_tiles(tiles, self.background)
        missing = self.capPorcessor.get_missing_count(track_ids)
        return composite, missing

    def get_live_debug_overlay(self):
        return self.capPorcessor.build_live_debug_overlay()

    def get_snapshot(self) -> CaptureSnapshot:
        with self._lock:
            return CaptureSnapshot(
                frame=self._frame.copy() if self._frame is not None else None,
                tiles=list(self._imageTileInfo[3]),
                cells=list(self._composite_cells),
                imageListInfo=[
                    self._imageListInfo[0],
                    self._imageListInfo[1],
                    self._imageListInfo[2],
                    list(self._imageListInfo[3]),
                ],
                capture_fps=self._capture_fps,
                missing_pins=self._missing_pins,
            )

    def threadRunner(self):
        self.initCapturePocessor()
        tiles = self.capPorcessor.process_tiles()
        composite = stack_tiles(tiles, self.background)
        self._apply_composite(tiles, composite)
        return composite.frame

    def threadRunnerForImageList(self):
        self._refresh_group_frame()
        return self._groupFrame

    def get(self):
        self._frame = self.threadRunner()

    def getImages(self):
        self._frame = self.threadRunner()
        self._refresh_group_frame()

    def pilStart(self, background, imageWidth):
        self.startFramePool(background, imageWidth, self.treshholdFrameCount)
        return self

    def getAndConvert(self):
        self._frame = self.threadRunner()
        self._pilFrame = self.openCVImageToTkImage(self._frame, (self.width, 0))

    def openCVImageToTkImage(self, cvImage, size=(0, 100)):
        return cv_to_photo_image(cvImage, size, self.background)

    def _capture_loop(self):
        limiter = FrameRateLimiter(self.target_fps)
        fps_counter = FpsCounter(report_interval=2.0)

        while self._running:
            started_at = perf_counter()
            try:
                frame = self.threadRunner()
                self._refresh_group_frame()
                if frame is not None:
                    fps = fps_counter.tick()
                    if fps:
                        self._capture_fps = fps
                        if abs(fps - self._last_logged_fps) >= 1.0:
                            logger.info("Capture FPS: %.1f (target %s)", fps, self.target_fps)
                            self._last_logged_fps = fps
                self._frmaeCreateionTime = perf_counter() - started_at
            except Exception as error:
                logger.warning("Capture loop failed: %s", error)
            limiter.sleep_remaining(started_at)

    def _apply_composite(self, tiles, composite):
        images = [tile.crop for tile in tiles]
        uniform_size = (0, 0)
        if images:
            first_height, first_width = images[0].shape[:2]
            uniform_size = (first_width, first_height)

        with self._lock:
            self._frame = composite.frame
            self._uniformSize = uniform_size
            self._imageTileInfo = [composite.columns, composite.rows, composite.count, list(tiles)]
            self._imageListInfo = [composite.columns, composite.rows, composite.count, images]
            self._composite_cells = composite.cells
            if composite.frame is not None:
                self._framePool.append(composite.frame)

    def _refresh_group_frame(self):
        with self._lock:
            track_ids = list(self._imageIndexes)
        composite, missing = self.get_pinned_composite(track_ids)
        with self._lock:
            self._groupFrame = composite.frame
            self._groupImageListInfo = [composite.columns, composite.rows, composite.count]
            self._group_cells = composite.cells
            self._missing_pins = missing
            if composite.frame is not None:
                self._groupFramePool.append(composite.frame)
        return composite.frame

    def stop(self):
        self.stopFramePool()
