import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from win32_utils import get_desktop_window, get_shell_window, is_desktop_or_shell_window
from windowCaptureHandler import DEFAULT_CAPTURE_SIZE, WindowCapture


def test_resolve_hwnd_accepts_dropdown_option_value():
    assert WindowCapture._resolve_hwnd("123456:Zoom Meeting", "") == 123456


def test_invalid_hwnd_returns_window_sized_blank_not_desktop_capture():
    capture = WindowCapture(hwnd="0")

    image = capture.get_screenshot()

    assert image.shape[:2] == (DEFAULT_CAPTURE_SIZE[1], DEFAULT_CAPTURE_SIZE[0])


def test_blank_print_window_frame_is_rejected_for_fallback():
    blank = np.zeros((20, 20, 3), dtype=np.uint8)
    varied = blank.copy()
    varied[0, 0] = (255, 255, 255)

    assert WindowCapture._looks_blank(blank)
    assert not WindowCapture._looks_blank(varied)


def test_shell_window_helper_is_available_without_pywin32_wrapper():
    shell_hwnd = get_shell_window()
    desktop_hwnd = get_desktop_window()

    assert isinstance(shell_hwnd, int)
    assert is_desktop_or_shell_window(desktop_hwnd)
