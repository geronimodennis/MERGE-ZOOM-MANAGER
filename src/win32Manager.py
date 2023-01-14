from pywinauto import Desktop
import win32gui

titles = []
def winEnumHandler( hwnd, ctx ):
	global titles
	if(win32gui.IsWindowVisible( hwnd )):
		titles.append(str(hwnd) + ':' + win32gui.GetWindowText( hwnd ))

def getWindowsTitle():
	global titles
	titles = []
	win32gui.EnumWindows(winEnumHandler, None )

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