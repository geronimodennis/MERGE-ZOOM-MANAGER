import tkinter as TK

from image_utils import aspect_fit_rect, blank_image, cv_to_photo_image, find_cell_at


class WindowRendererGroupPreview:
    title = "MCGI ADDPRO-TOOL : {0}"

    def __init__(self, parent, title, background, captureRunnerOnThread):
        self.parent = parent
        self.windowTitle = title
        self.background = background
        self.captureRunnerOnThread = captureRunnerOnThread
        self.window = None
        self.currentImage = None
        self.currentCells = []
        self.currentSourceSize = (0, 0)
        self.displayRect = (0, 0, 1, 1)
        self.currentTileId = None
        self.isRendering = False
        self._create_window()

    def exists(self):
        return self.window is not None and self.window.winfo_exists()

    def _create_window(self):
        if self.exists():
            self.window.focus_set()
            return

        self.window = TK.Toplevel(self.parent)
        self.window.title(self.title.format(self.windowTitle))
        self.window.attributes("-fullscreen", True)
        self.window.configure(background=self.backgroundColorToStr())
        self.window.canvas = TK.Canvas(self.window, background=self.backgroundColorToStr(), highlightthickness=0)
        self.window.canvas.pack(fill=TK.BOTH, expand=True)
        self.window.canvasImageConfigId = self.window.canvas.create_image(0, 0, image=None, anchor=TK.NW)
        self.window.canvasTextConfigId = self.window.canvas.create_text(
            12,
            12,
            text="No participants pinned.",
            fill="white",
            anchor=TK.NW,
            font=("Segoe UI", 11, "bold"),
        )
        self.window.bind("<Button-1>", self.windowClick)
        self.window.bind("<Button-3>", self.windowRClick)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.addContextMenu()

    def addContextMenu(self):
        self.window.menu = TK.Menu(self.window, tearoff=0)
        self.window.menu.add_command(label="Remove Selected From Group Pin", command=self.menu_RemoveFromPin)
        self.window.menu.add_separator()
        self.window.menu.add_command(label="Clear Group Pins", command=self.menu_ClearGroupPreview)

    def update(self, background, captureRunnerOnThread):
        self.background = background
        self.captureRunnerOnThread = captureRunnerOnThread
        self._create_window()
        return self

    def render(self):
        self._create_window()
        if not self.isRendering:
            self.isRendering = True
            self.window.after(16, self.__runCapture)

    def __runCapture(self):
        if not self.isRendering or not self.exists():
            return

        tile_ids = list(self.captureRunnerOnThread.imageIndexes)
        composite, missing = self.captureRunnerOnThread.get_pinned_composite(tile_ids)
        frame = composite.frame
        message = ""
        if frame is None:
            frame = blank_image((640, 360), self.background)
            message = "No participants pinned."
        elif missing:
            message = "Searching for {0} pinned participant(s)...".format(missing)

        canvas_width = max(1, self.window.canvas.winfo_width())
        canvas_height = max(1, self.window.canvas.winfo_height())
        frame_height, frame_width = frame.shape[:2]
        self.currentImage = cv_to_photo_image(frame, (canvas_width, canvas_height), self.background)
        self.currentCells = composite.cells
        self.currentSourceSize = (frame_width, frame_height)
        self.displayRect = aspect_fit_rect(self.currentSourceSize, (canvas_width, canvas_height))
        x, y, _width, _height = self.displayRect
        self.window.canvas.coords(self.window.canvasImageConfigId, x, y)
        self.window.canvas.itemconfig(self.window.canvasImageConfigId, image=self.currentImage)
        self.window.canvas.itemconfig(self.window.canvasTextConfigId, text=message)
        self.window.after(16, self.__runCapture)

    def close(self):
        self.isRendering = False
        if self.exists():
            self.window.destroy()

    def _select_tile_at(self, x, y):
        display_x, display_y, display_width, display_height = self.displayRect
        if display_width <= 0 or display_height <= 0:
            self.currentTileId = None
            return None
        if x < display_x or y < display_y or x >= display_x + display_width or y >= display_y + display_height:
            self.currentTileId = None
            return None

        source_width, source_height = self.currentSourceSize
        source_x = (x - display_x) * source_width / float(display_width)
        source_y = (y - display_y) * source_height / float(display_height)
        cell = find_cell_at(self.currentCells, source_x, source_y)
        self.currentTileId = None if cell is None else cell.get("tile_id")
        return self.currentTileId

    def windowClick(self, event):
        self._select_tile_at(event.x, event.y)

    def windowRClick(self, event):
        if self._select_tile_at(event.x, event.y) is not None:
            self.window.menu.tk_popup(event.x_root, event.y_root)

    def menu_ClearGroupPreview(self):
        self.captureRunnerOnThread.clearPinnedTiles()

    def menu_RemoveFromPin(self):
        if self.currentTileId is not None:
            self.captureRunnerOnThread.removePinnedTile(self.currentTileId)

    def backgroundColorToStr(self):
        return "#%02x%02x%02x" % self.background
