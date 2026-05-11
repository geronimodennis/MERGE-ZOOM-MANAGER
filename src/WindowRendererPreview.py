import tkinter as TK

from image_utils import aspect_fit_rect, blank_image, cv_to_photo_image
from performance import UI_FRAME_INTERVAL_MS


class WindowRendererPreview:
    xtitle = "MCGI ADDPRO-TOOL : {0}"

    def __init__(self, parent, title, background, captureRunnerOnThread, tile_ids):
        self.parent = parent
        self.title = title
        self.background = background
        self.captureRunnerOnThread = captureRunnerOnThread
        self.tile_ids = list(tile_ids)
        self.window = None
        self.currentImage = None
        self.isRendering = False
        self.displayRect = (0, 0, 1, 1)
        self._create_window()

    def exists(self):
        return self.window is not None and self.window.winfo_exists()

    def _create_window(self):
        if self.exists():
            self.window.focus_set()
            return

        self.window = TK.Toplevel(self.parent)
        self.window.title(self.xtitle.format(self.title))
        self.window.attributes("-fullscreen", True)
        self.window.configure(background=self.backgroundColorToStr())
        self.window.canvas = TK.Canvas(self.window, background=self.backgroundColorToStr(), highlightthickness=0)
        self.window.canvas.pack(fill=TK.BOTH, expand=True)
        self.window.canvasImageConfigId = self.window.canvas.create_image(0, 0, image=None, anchor=TK.NW)
        self.window.canvasTextConfigId = self.window.canvas.create_text(
            12,
            12,
            text="Waiting for pinned participant...",
            fill="white",
            anchor=TK.NW,
            font=("Segoe UI", 11, "bold"),
        )
        self.window.protocol("WM_DELETE_WINDOW", self.close)

    def update(self, captureRunnerOnThread, tile_ids):
        self.captureRunnerOnThread = captureRunnerOnThread
        self.tile_ids = list(tile_ids)
        self._create_window()
        return self

    def render(self):
        self._create_window()
        if not self.isRendering:
            self.isRendering = True
            self.window.after(UI_FRAME_INTERVAL_MS, self.__runCapture)

    def __runCapture(self):
        if not self.isRendering or not self.exists():
            return

        composite, missing = self.captureRunnerOnThread.get_pinned_composite(self.tile_ids)
        frame = composite.frame
        message = ""
        if frame is None:
            frame = blank_image((640, 360), self.background)
            message = "Pinned participant is not currently detected."
        elif missing:
            message = "Searching for {0} pinned participant(s)...".format(missing)

        canvas_width = max(1, self.window.canvas.winfo_width())
        canvas_height = max(1, self.window.canvas.winfo_height())
        frame_height, frame_width = frame.shape[:2]
        self.currentImage = cv_to_photo_image(frame, (canvas_width, canvas_height), self.background)
        self.displayRect = aspect_fit_rect((frame_width, frame_height), (canvas_width, canvas_height))
        x, y, _width, _height = self.displayRect
        self.window.canvas.coords(self.window.canvasImageConfigId, x, y)
        self.window.canvas.itemconfig(self.window.canvasImageConfigId, image=self.currentImage)
        self.window.canvas.itemconfig(self.window.canvasTextConfigId, text=message)

        self.window.after(UI_FRAME_INTERVAL_MS, self.__runCapture)

    def close(self):
        self.isRendering = False
        if self.exists():
            self.window.destroy()

    def backgroundColorToStr(self):
        return "#%02x%02x%02x" % self.background
