import ctypes
from threading import Event, Lock
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

try:
    from windows_capture import WindowsCapture as NativeWindowsCapture
except Exception:
    NativeWindowsCapture = None


logger = get_logger()

PW_RENDERFULLCONTENT = 0x00000002
DEFAULT_CAPTURE_SIZE = (640, 360)
WINDOW_GRAPHICS_TIMEOUT_SECONDS = 0.15


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class WindowsGraphicsCaptureBackend:
    """Capture one HWND through Windows Graphics Capture without desktop occlusion."""

    def __init__(self, hwnd: int, target_fps: int = 30):
        self.hwnd = int(hwnd or 0)
        self.target_fps = max(1, int(target_fps))
        self._capture = None
        self._control = None
        self._frame = None
        self._lock = Lock()
        self._first_frame = Event()
        self._closed = False
        self._last_error = ""

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def is_available(self) -> bool:
        return NativeWindowsCapture is not None

    def start(self) -> bool:
        if self._control is not None:
            return True
        if NativeWindowsCapture is None or not self.hwnd:
            self._last_error = "windows-capture package is not available"
            return False

        try:
            interval_ms = max(1, int(round(1000 / self.target_fps)))
            capture = NativeWindowsCapture(
                cursor_capture=False,
                draw_border=False,
                minimum_update_interval=interval_ms,
                window_hwnd=self.hwnd,
            )

            @capture.event
            def on_frame_arrived(frame, _capture_control):
                image = np.ascontiguousarray(frame.frame_buffer[:, :, :3]).copy()
                with self._lock:
                    self._frame = image
                self._first_frame.set()

            @capture.event
            def on_closed():
                self._closed = True

            self._capture = capture
            self._control = capture.start_free_threaded()
            return True
        except Exception as error:
            self._last_error = str(error)
            self.stop()
            return False

    def get_frame(self, timeout: float = 0.0) -> Optional[np.ndarray]:
        if self._closed:
            return None
        if not self.start():
            return None
        if timeout > 0:
            self._first_frame.wait(timeout)
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def stop(self) -> None:
        try:
            if self._control is not None and not self._control.is_finished():
                self._control.stop()
        except Exception:
            pass
        self._capture = None
        self._control = None
        self._frame = None
        self._first_frame.clear()
        self._closed = False


class WindowCapture:
    def __init__(self, hwnd: str = "", window_name: str = ""):
        self.hwnd = self._resolve_hwnd(hwnd, window_name)
        self.w, self.h = DEFAULT_CAPTURE_SIZE
        self.bounds = (0, 0, self.w, self.h)
        self._cached_size: Optional[Tuple[int, int]] = None
        self._compatible_dc = None
        self._bitmap = None
        self._selected_bitmap = None
        self._graphics_capture: Optional[WindowsGraphicsCaptureBackend] = None
        self._last_error_at = 0.0
        self._last_backend_warning_at = 0.0
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
        self._graphics_capture = None
        self._refresh_window_size()

    def startFramePool(self):
        return self

    def stopFramePool(self):
        self.freeResources()
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
                self._stop_graphics_capture()
                return self.newBlankImageSize((self.w, self.h))

            image = self._capture_with_windows_graphics_capture()
            if image is not None:
                return image

            image = self._capture_with_print_window()
            if image is not None:
                return image

            self._log_backend_warning(
                "Selected window did not provide a capturable frame. "
                "If this is Zoom with DirectX 12/hardware acceleration, Windows Graphics Capture is required; "
                "otherwise disable Zoom video rendering hardware acceleration and reselect the window."
            )
            return self.newBlankImageSize((max(1, self.w), max(1, self.h)))
        except Exception as error:
            now = time()
            if now - self._last_error_at > 2:
                logger.warning("Window capture failed for hwnd=%s: %s", self.hwnd, error)
                self._last_error_at = now
            self.freeResources()
            return self.newBlankImageSize((max(1, self.w), max(1, self.h)))

    def _capture_with_windows_graphics_capture(self) -> Optional[np.ndarray]:
        if NativeWindowsCapture is None:
            self._log_backend_warning("Windows Graphics Capture backend is unavailable; falling back to PrintWindow.")
            return None

        if self._graphics_capture is None or self._graphics_capture.hwnd != self.hwnd:
            self._graphics_capture = WindowsGraphicsCaptureBackend(self.hwnd)

        image = self._graphics_capture.get_frame(WINDOW_GRAPHICS_TIMEOUT_SECONDS)
        if image is None:
            self._log_backend_warning(
                "Windows Graphics Capture has not produced a frame yet: "
                f"{self._graphics_capture.last_error or 'waiting for first frame'}"
            )
            return None

        if self._looks_blank(image):
            return None
        return image

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
        self._stop_graphics_capture()
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

    def _stop_graphics_capture(self) -> None:
        try:
            if self._graphics_capture is not None:
                self._graphics_capture.stop()
        except Exception:
            pass
        self._graphics_capture = None

    def _log_backend_warning(self, message: str) -> None:
        now = time()
        if now - self._last_backend_warning_at > 5:
            logger.warning(message)
            self._last_backend_warning_at = now

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
