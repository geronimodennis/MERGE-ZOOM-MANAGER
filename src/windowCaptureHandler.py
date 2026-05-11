import ctypes
from ctypes import wintypes
from time import time
from typing import Optional, Tuple

import numpy as np
import win32con
import win32gui
import win32ui
from win32api import GetSystemMetrics

from image_utils import blank_image
from performance import get_logger
from win32_utils import get_desktop_window, get_shell_window


logger = get_logger()

PW_RENDERFULLCONTENT = 0x00000002
DEFAULT_CAPTURE_SIZE = (640, 360)


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class WindowCapture:
    def __init__(self, hwnd: str = "", window_name: str = ""):
        self.hwnd = self._resolve_hwnd(hwnd, window_name)
        self.w, self.h = DEFAULT_CAPTURE_SIZE
        self.bounds = (0, 0, self.w, self.h)
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
                if isinstance(hwnd, str) and ":" in hwnd:
                    hwnd = hwnd.split(":", 1)[0]
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

    def is_valid(self) -> bool:
        return self._is_valid_hwnd(self.hwnd)

    @staticmethod
    def _is_valid_hwnd(hwnd: int) -> bool:
        if not hwnd:
            return False
        try:
            desktop_hwnd = get_desktop_window()
            shell_hwnd = get_shell_window()
            return bool(
                hwnd not in (desktop_hwnd, shell_hwnd)
                and win32gui.IsWindow(hwnd)
                and win32gui.IsWindowVisible(hwnd)
            )
        except Exception:
            return False

    def _refresh_window_size(self) -> bool:
        if not self._is_valid_hwnd(self.hwnd):
            return False

        left, top, right, bottom = self._get_window_bounds()
        width = max(1, right - left)
        height = max(1, bottom - top)
        if width <= 1 or height <= 1:
            return False
        if (width, height) != self._cached_size:
            self.freeResources()
            self.w = width
            self.h = height
            self._cached_size = (width, height)
        self.bounds = (left, top, right, bottom)
        return True

    def _get_window_bounds(self) -> Tuple[int, int, int, int]:
        try:
            rect = RECT()
            result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
                wintypes.HWND(self.hwnd),
                9,  # DWMWA_EXTENDED_FRAME_BOUNDS
                ctypes.byref(rect),
                ctypes.sizeof(rect),
            )
            if result == 0 and rect.right > rect.left and rect.bottom > rect.top:
                return rect.left, rect.top, rect.right, rect.bottom
        except Exception:
            pass
        return win32gui.GetWindowRect(self.hwnd)

    def get_screenshot(self) -> np.ndarray:
        try:
            if not self._refresh_window_size():
                return self.newBlankImageSize((self.w, self.h))
            if win32gui.IsIconic(self.hwnd):
                return self.newBlankImageSize((self.w, self.h))

            image = self._capture_with_print_window()
            if image is None:
                image = self._capture_selected_rect_from_screen()
            return image
        except Exception as error:
            now = time()
            if now - self._last_error_at > 2:
                logger.warning("Window capture failed for hwnd=%s: %s", self.hwnd, error)
                self._last_error_at = now
            self.freeResources()
            return self.newBlankImageSize((max(1, self.w), max(1, self.h)))

    def _capture_with_print_window(self) -> Optional[np.ndarray]:
        window_dc = win32gui.GetWindowDC(self.hwnd)
        source_dc = win32ui.CreateDCFromHandle(window_dc)
        try:
            self._ensure_capture_resources(source_dc)
            result = ctypes.windll.user32.PrintWindow(
                wintypes.HWND(self.hwnd),
                self._compatible_dc.GetSafeHdc(),
                PW_RENDERFULLCONTENT,
            )
            if result != 1:
                return None
            image = self._bitmap_to_bgr()
            if self._looks_blank(image):
                return None
            return image
        finally:
            source_dc.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, window_dc)

    def _capture_selected_rect_from_screen(self) -> np.ndarray:
        left, top, _right, _bottom = self.bounds
        desktop_dc = win32gui.GetWindowDC(0)
        source_dc = win32ui.CreateDCFromHandle(desktop_dc)
        try:
            self._ensure_capture_resources(source_dc)
            self._compatible_dc.BitBlt(
                (0, 0),
                (self.w, self.h),
                source_dc,
                (left, top),
                win32con.SRCCOPY,
            )
            return self._bitmap_to_bgr()
        finally:
            source_dc.DeleteDC()
            win32gui.ReleaseDC(0, desktop_dc)

    def _bitmap_to_bgr(self) -> np.ndarray:
        bitmap_bytes = self._bitmap.GetBitmapBits(True)
        image = np.frombuffer(bitmap_bytes, dtype=np.uint8).reshape((self.h, self.w, 4))
        return np.ascontiguousarray(image[:, :, :3])

    @staticmethod
    def _looks_blank(image: np.ndarray) -> bool:
        if image.size == 0:
            return True
        return float(np.std(image)) < 2.0

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
