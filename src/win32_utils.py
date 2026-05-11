import ctypes
from ctypes import wintypes

import win32gui


_user32 = ctypes.windll.user32
_user32.GetShellWindow.restype = wintypes.HWND


def get_shell_window() -> int:
    try:
        return int(_user32.GetShellWindow() or 0)
    except Exception:
        return 0


def get_desktop_window() -> int:
    try:
        return int(win32gui.GetDesktopWindow() or 0)
    except Exception:
        return 0


def is_desktop_or_shell_window(hwnd: int) -> bool:
    return int(hwnd or 0) in {get_desktop_window(), get_shell_window()}
