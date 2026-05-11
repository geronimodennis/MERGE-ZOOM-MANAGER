from time import time
from typing import Optional, Tuple

import numpy as np
import win32con
import win32gui
import win32ui
from win32api import GetSystemMetrics

from image_utils import blank_image
from performance import get_logger


logger = get_logger()


class WindowCapture:
    def __init__(self, hwnd: str = "", window_name: str = ""):
        self.hwnd = self._resolve_hwnd(hwnd, window_name)
        self.w = GetSystemMetrics(0)
        self.h = GetSystemMetrics(1)
        self._cached_size: Optional[Tuple[int, int]] = None
        self._compatible_dc = None
        self._bitmap = None
        self._selected_bitmap = None
        self._last_error_at = 0.0
        self._refresh_window_size()

    @staticmethod
    def _resolve_hwnd(hwnd, window_name: str) -> int:
        if hwnd not in ("", None):
            try:
                return int(hwnd)
            except (TypeError, ValueError):
                return 0
        if window_name:
            return int(win32gui.FindWindow(None, window_name))
        return 0

    @property
    def framePool(self):
        return []

    @framePool.setter
    def framePool(self, _value):
        pass

    def resetCapture(self, hwnd: str = "", window_name: str = ""):
        self.freeResources()
        self.hwnd = self._resolve_hwnd(hwnd, window_name)
        self._cached_size = None
        self._refresh_window_size()

    def startFramePool(self):
        return self

    def stopFramePool(self):
        return self

    def _refresh_window_size(self) -> bool:
        if not self.hwnd or not win32gui.IsWindow(self.hwnd):
            return False
        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        width = max(1, right - left)
        height = max(1, bottom - top)
        if (width, height) != self._cached_size:
            self.freeResources()
            self.w = width
            self.h = height
            self._cached_size = (width, height)
        return True

    def get_screenshot(self) -> np.ndarray:
        try:
            if not self._refresh_window_size():
                return self.newBlankImage()
            if win32gui.IsIconic(self.hwnd):
                return self.newBlankImageSize((self.w, self.h))

            window_dc = win32gui.GetWindowDC(self.hwnd)
            source_dc = win32ui.CreateDCFromHandle(window_dc)
            try:
                self._ensure_capture_resources(source_dc)
                self._compatible_dc.BitBlt((0, 0), (self.w, self.h), source_dc, (0, 0), win32con.SRCCOPY)
                bitmap_bytes = self._bitmap.GetBitmapBits(True)
            finally:
                source_dc.DeleteDC()
                win32gui.ReleaseDC(self.hwnd, window_dc)

            image = np.frombuffer(bitmap_bytes, dtype=np.uint8).reshape((self.h, self.w, 4))
            return np.ascontiguousarray(image[:, :, :3])
        except Exception as error:
            now = time()
            if now - self._last_error_at > 2:
                logger.warning("Window capture failed for hwnd=%s: %s", self.hwnd, error)
                self._last_error_at = now
            self.freeResources()
            return self.newBlankImageSize((max(1, self.w), max(1, self.h)))

    def _ensure_capture_resources(self, source_dc) -> None:
        if self._compatible_dc is not None and self._bitmap is not None:
            return
        self._compatible_dc = source_dc.CreateCompatibleDC()
        self._bitmap = win32ui.CreateBitmap()
        self._bitmap.CreateCompatibleBitmap(source_dc, self.w, self.h)
        self._selected_bitmap = self._compatible_dc.SelectObject(self._bitmap)

    def freeResources(self):
        try:
            if self._compatible_dc is not None:
                if self._selected_bitmap is not None:
                    self._compatible_dc.SelectObject(self._selected_bitmap)
                self._compatible_dc.DeleteDC()
        except Exception:
            pass
        try:
            if self._bitmap is not None:
                win32gui.DeleteObject(self._bitmap.GetHandle())
        except Exception:
            pass
        self._compatible_dc = None
        self._bitmap = None
        self._selected_bitmap = None

    @staticmethod
    def getScreeDimention():
        return [GetSystemMetrics(0), GetSystemMetrics(1)]

    @staticmethod
    def newBlankImage(r=0, g=0, b=0):
        return blank_image((GetSystemMetrics(0), GetSystemMetrics(1)), (r, g, b))

    @staticmethod
    def newBlankImageSize(size=(0, 0), rbgChromaKey=(0, 177, 64)):
        width, height = size
        if width <= 0:
            width = GetSystemMetrics(0)
        if height <= 0:
            height = GetSystemMetrics(1)
        return blank_image((width, height), rbgChromaKey)

    def __del__(self):
        self.freeResources()
