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


def test_get_screenshot_prefers_application_window_capture(monkeypatch):
    capture = WindowCapture(hwnd="0")
    capture.hwnd = 123
    capture.w = 4
    capture.h = 3
    expected = np.full((3, 4, 3), 80, dtype=np.uint8)

    monkeypatch.setattr(capture, "_refresh_window_size", lambda: True)
    monkeypatch.setattr("windowCaptureHandler.win32gui.IsIconic", lambda _hwnd: False)
    monkeypatch.setattr(capture, "_capture_with_windows_graphics_capture", lambda: expected)
    monkeypatch.setattr(
        capture,
        "_capture_with_print_window",
        lambda: (_ for _ in ()).throw(AssertionError("PrintWindow should not run after a window frame")),
    )

    image = capture.get_screenshot()

    assert np.array_equal(image, expected)


def test_get_screenshot_does_not_capture_desktop_when_window_backends_fail(monkeypatch):
    capture = WindowCapture(hwnd="0")
    capture.hwnd = 123
    capture.w = 4
    capture.h = 3

    monkeypatch.setattr(capture, "_refresh_window_size", lambda: True)
    monkeypatch.setattr("windowCaptureHandler.win32gui.IsIconic", lambda _hwnd: False)
    monkeypatch.setattr(capture, "_capture_with_windows_graphics_capture", lambda: None)
    monkeypatch.setattr(capture, "_capture_with_print_window", lambda: None)
    monkeypatch.setattr(
        capture,
        "_capture_selected_rect_from_screen",
        lambda: (_ for _ in ()).throw(AssertionError("desktop crop must not be used")),
    )

    image = capture.get_screenshot()

    assert image.shape[:2] == (3, 4)
    assert tuple(int(value) for value in image[0, 0]) == (64, 177, 0)


def test_shell_window_helper_is_available_without_pywin32_wrapper():
    shell_hwnd = get_shell_window()
    desktop_hwnd = get_desktop_window()

    assert isinstance(shell_hwnd, int)
    assert is_desktop_or_shell_window(desktop_hwnd)
