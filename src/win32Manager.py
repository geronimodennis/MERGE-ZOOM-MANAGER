import win32gui

from win32_utils import is_desktop_or_shell_window

titles = []


def winEnumHandler(hwnd, ctx):
    global titles
    title = win32gui.GetWindowText(hwnd)
    if not title:
        return
    if is_desktop_or_shell_window(hwnd):
        return
    if not win32gui.IsWindowVisible(hwnd):
        return
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    if right - left <= 1 or bottom - top <= 1:
        return
    titles.append(str(hwnd) + ":" + title)


def getWindowsTitle():
    global titles
    titles = []
    win32gui.EnumWindows(winEnumHandler, None)

    return titles

# def getWindowsTitle():
# 	titles = []
# 	windows = Desktop(backend="uia").windows()
# 	#windows32 = Desktop(backend="win32",  allow_magic_lookup=False).windows()
# 	for w in windows:
# 		titles.append(w.window_text())

# 	#for w32 in windows32:
# 	#	titles.append(w32.window_text())

# 	print("titles", titles.sort())


# 	return titles
