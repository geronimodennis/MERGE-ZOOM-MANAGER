import tkinter as TK
from tkinter import messagebox
from tkinter.colorchooser import askcolor

import cv2

from WindowRenderer import WindowRenderer
from image_utils import cv_to_photo_image
from win32Manager import getWindowsTitle
from windowCaptureHandler import WindowCapture


class WindowCaptureConfiguration:
    def __init__(self):
        self._chromaColorKey = (0, 177, 64)
        self._captureConfiguration = []
        self._rows = []
        self.options = [""]
        self.renderWindow = None

        self.window = TK.Tk()
        self.window.title("MCGI ADDPRO-TOOL : COMBINE ZOOM GALLERIES : Setup Capture")
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

        self._create_search()
        self._create_data_grid()
        self._addRow(isShowDelete=False)
        self._updateOptionList()
        self.window.mainloop()

    def rgb_hack(self, rgb):
        return "#%02x%02x%02x" % rgb

    def _new_config(self, option_menu=None, option_var=None, preview_canvas=None):
        return {
            "winName": "",
            "win_hwnd": None,
            "index": len(self._captureConfiguration),
            "optionMenu": option_menu,
            "optionMenuStringVar": option_var,
            "optionMenuCallback": None,
            "previewCanvas": preview_canvas,
            "captureHandler": None,
        }

    def _create_search(self):
        frame = TK.Frame(self.window, padx=8, pady=8)
        frame.grid(row=0, column=0, sticky=TK.W)

        TK.Label(frame, text="Window Search").grid(row=0, column=0, sticky=TK.W)
        self._txtWindowNameSearch = TK.Entry(frame, width=40)
        self._txtWindowNameSearch.insert(TK.INSERT, "zoom meeting")
        self._txtWindowNameSearch.grid(row=0, column=1, padx=(6, 6))
        TK.Button(frame, text="Refresh", width=10, command=self._updateOptionList).grid(row=0, column=2)

    def _create_data_grid(self):
        self._frameForDataGrid = TK.Frame(self.window, padx=8, pady=4)
        self._frameForDataGrid.grid(row=1, column=0, sticky=TK.W)

        header = TK.Frame(self._frameForDataGrid)
        header.config(background=self.rgb_hack(self._chromaColorKey))
        header.grid(row=0, column=0, sticky=TK.W)

        TK.Button(header, text="ADD", width=10, command=lambda: self._addRow(isShowDelete=True)).grid(row=0, column=1)
        TK.Button(header, text="CHROMA", width=10, command=lambda: self.selectChroma(header)).grid(row=0, column=2)
        TK.Button(header, text="RENDER", width=10, command=self.runCaptureClickV2).grid(row=0, column=3)

        TK.Label(header, bg="GRAY", text="DEL", relief=TK.FLAT, width=10).grid(row=1, column=1)
        TK.Label(header, bg="GRAY", text="SELECT WINDOW", relief=TK.FLAT, width=80).grid(row=1, column=2)
        TK.Label(header, bg="GRAY", text="PREVIEW", relief=TK.FLAT, width=40).grid(row=1, column=4)

        self._rowsFrame = TK.Frame(self._frameForDataGrid)
        self._rowsFrame.grid(row=1, column=0, sticky=TK.W)

    def _updateOptionList(self):
        findWhat = self._txtWindowNameSearch.get().strip().lower()
        options = getWindowsTitle()
        if findWhat:
            options = [title for title in options if findWhat in title.lower()]
        self.options = [""] + options

        for row in self._rows:
            dropdown = row["dropdown"]
            string_var = row["var"]
            callback = row["callback"]
            dropdown["menu"].delete(0, "end")
            for option in self.options:
                dropdown["menu"].add_command(label=option, command=TK._setit(string_var, option, callback))

    def runCaptureClickV2(self):
        if self.renderWindow is None:
            self.renderWindow = WindowRenderer(self.window, self._chromaColorKey, self._captureConfiguration)
        else:
            self.renderWindow.background = self._chromaColorKey
        self.renderWindow.render()

    def openCVImageToTkImage(self, cvImage, size=(200, 100)):
        return cv_to_photo_image(cvImage, size, self._chromaColorKey)

    def selectChroma(self, buttonChroma):
        colors = askcolor(title="Choose color", color=self._chromaColorKey)
        if colors and colors[0]:
            self._chromaColorKey = tuple(int(value) for value in colors[0])
            buttonChroma.config(background=self.rgb_hack(self._chromaColorKey))
            buttonChroma.update()

    def _addRow(self, isShowDelete):
        row_frame = TK.Frame(self._rowsFrame)
        row_frame.grid(row=len(self._rows), column=0, sticky=TK.W, pady=2)

        option_var = TK.StringVar()
        preview_canvas = TK.Canvas(row_frame, width=200, height=100)
        config = self._new_config(option_var=option_var, preview_canvas=preview_canvas)

        def _windowNameSelectChange(choice):
            self._select_window(config, choice)

        config["optionMenuCallback"] = _windowNameSelectChange

        if isShowDelete:
            TK.Button(row_frame, text="DEL", width=10, command=lambda: self._deleteRow(row_frame, config)).grid(row=0, column=1)
        else:
            TK.Label(row_frame, text=" ", width=10).grid(row=0, column=1)

        dropdown = TK.OptionMenu(row_frame, option_var, *self.options, command=_windowNameSelectChange)
        dropdown.config(width=80)
        dropdown.grid(row=0, column=2, sticky=TK.W)
        TK.Button(row_frame, text="Refresh list", width=10, command=self._updateOptionList).grid(row=0, column=3)
        preview_canvas.grid(row=0, column=4)
        preview_canvas.bind("<Button-1>", lambda event: self._refresh_preview(config, show_large=True))

        config["optionMenu"] = dropdown
        self._captureConfiguration.append(config)
        self._rows.append(
            {
                "frame": row_frame,
                "config": config,
                "dropdown": dropdown,
                "var": option_var,
                "callback": _windowNameSelectChange,
            }
        )
        self._updateOptionList()

    def _deleteRow(self, row_frame, config):
        row_frame.grid_forget()
        row_frame.destroy()
        if config in self._captureConfiguration:
            self._captureConfiguration.remove(config)
        self._rows = [row for row in self._rows if row["config"] is not config]

    def _select_window(self, config, choice):
        if not choice:
            return

        hwnd = choice.split(":", 1)[0]
        config["winName"] = choice
        config["win_hwnd"] = hwnd
        capture_handler = config.get("captureHandler")
        if capture_handler is None:
            config["captureHandler"] = WindowCapture(hwnd=hwnd)
        else:
            capture_handler.resetCapture(hwnd=hwnd)
        self._refresh_preview(config)

    def _refresh_preview(self, config, show_large=False):
        capture_handler = config.get("captureHandler")
        canvas = config.get("previewCanvas")
        if capture_handler is None or canvas is None:
            return

        image = capture_handler.get_screenshot()
        canvas.cvImage = image
        canvas.background = self.openCVImageToTkImage(image)
        canvas.delete("all")
        canvas.create_image(0, 0, image=canvas.background, anchor=TK.NW)

        if show_large:
            height, width = image.shape[:2]
            scale = min(0.5, 800.0 / max(width, 1))
            resized = cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
            cv2.imshow("preview", resized)

    def on_closing(self):
        if messagebox.askokcancel(title="Quit", message="Do you want to quit?"):
            if self.renderWindow is not None:
                self.renderWindow.on_closing()
            self.window.destroy()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    WindowCaptureConfiguration()
