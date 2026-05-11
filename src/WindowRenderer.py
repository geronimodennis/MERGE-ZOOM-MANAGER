import tkinter as TK
from tkinter import messagebox

import cv2

from WindowRendererGroupPreview import WindowRendererGroupPreview
from WindowRendererPreview import WindowRendererPreview
from captureRunnerOnThread import CaptureRunnerOnThread
from image_utils import aspect_fit_rect, cv_to_photo_image, find_cell_at


class WindowRenderer:
    title = "MCGI ADDPRO-TOOL : COMBINE ZOOM GALLERIES"

    def __init__(self, parent, background, captureConfiguration):
        self.parent = parent
        self.background = background
        self.captureConfiguration = captureConfiguration
        self.window = None
        self.captureRunnerOnThread = None
        self.renderPreviewWindow = None
        self.renderGroupPreviewWindow = None
        self.pinWindows = []
        self.isRendering = False
        self.currentImage = None
        self.currentTileId = None
        self.currentCells = []
        self.currentSourceSize = (0, 0)
        self.displayRect = (0, 0, 1, 1)
        self.initializeObject(parent, background, captureConfiguration)

    def initializeObject(self, parent, background, captureConfiguration):
        self.parent = parent
        self.background = background
        self.captureConfiguration = captureConfiguration

        if self.window is not None and self.window.winfo_exists():
            self.window.focus_set()
            return

        self.window = TK.Toplevel(self.parent)
        self.window.title(self.title)
        self.window.attributes("-fullscreen", True)
        self.window.configure(background=self.backgroundColorToStr())

        self.window.canvas = TK.Canvas(self.window, background=self.backgroundColorToStr(), highlightthickness=0)
        self.window.canvas.pack(fill=TK.BOTH, expand=True)
        self.window.canvasImageConfigId = self.window.canvas.create_image(0, 0, image=None, anchor=TK.NW)
        self.window.canvasTextConfigId = self.window.canvas.create_text(
            12,
            12,
            text="Waiting for Zoom capture...",
            fill="white",
            anchor=TK.NW,
            font=("Segoe UI", 11, "bold"),
        )

        self.captureRunnerOnThread = CaptureRunnerOnThread(captureConfiguration, self.background).startFramePool(
            self.background,
            self.window.winfo_screenwidth(),
            3,
        )

        self.addContextMenu()
        self.window.bind("<Button-1>", self.windowClick)
        self.window.bind("<Button-3>", self.windowRClick)
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        if self.captureRunnerOnThread is not None:
            self.captureRunnerOnThread.stopFramePool()
        for pin_window in list(self.pinWindows):
            pin_window.close()
        if self.renderPreviewWindow is not None:
            self.renderPreviewWindow.close()
        if self.renderGroupPreviewWindow is not None:
            self.renderGroupPreviewWindow.close()
        self.window.destroy()
        self.isRendering = False

    def addContextMenu(self):
        self.window.menu = TK.Menu(self.window, tearoff=0)
        self.window.menu.add_command(label="Pin Selected Participant", command=self.menu_OpenToPreview)
        self.window.menu.add_command(label="Pin Selected In New Window", command=self.menu_Open)
        self.window.menu.add_separator()
        self.window.menu.add_command(label="Open Group Pin Window", command=self.menu_OpenGroupPreview)
        self.window.menu.add_command(label="Add Selected To Group Pin", command=self.menu_OpenToGroupPreview)
        self.window.menu.add_separator()
        self.window.menu.add_command(label="Show Detection Debug Overlay", command=self.menu_ShowDebugOverlay)
        self.window.menu.add_separator()
        self.window.menu.add_command(label="Clear Group Pins", command=self.menu_ClearGroupPreview)

    def render(self):
        self.initializeObject(self.parent, self.background, self.captureConfiguration)
        if not self.isRendering:
            self.isRendering = True
            self.window.after(16, self.__runCapture)

    def __runCapture(self):
        if not self.isRendering or self.window is None or not self.window.winfo_exists():
            return

        snapshot = self.captureRunnerOnThread.get_snapshot()
        if snapshot.frame is not None:
            canvas_width = max(1, self.window.canvas.winfo_width())
            canvas_height = max(1, self.window.canvas.winfo_height())
            frame_height, frame_width = snapshot.frame.shape[:2]

            self.currentImage = cv_to_photo_image(snapshot.frame, (canvas_width, canvas_height), self.background)
            self.currentCells = snapshot.cells
            self.currentSourceSize = (frame_width, frame_height)
            self.displayRect = aspect_fit_rect(self.currentSourceSize, (canvas_width, canvas_height))
            x, y, _width, _height = self.displayRect
            self.window.canvas.coords(self.window.canvasImageConfigId, x, y)
            self.window.canvas.itemconfig(self.window.canvasImageConfigId, image=self.currentImage)

            text = "Tiles: {0}   Capture FPS: {1:.1f}".format(len(snapshot.tiles), snapshot.capture_fps)
            if snapshot.missing_pins:
                text += "   Missing pinned: {0}".format(snapshot.missing_pins)
            self.window.canvas.itemconfig(self.window.canvasTextConfigId, text=text)
        else:
            self.window.canvas.itemconfig(
                self.window.canvasTextConfigId,
                text="No participant tiles detected. Check the selected Zoom window and Gallery View.",
            )

        self.window.after(16, self.__runCapture)

    def backgroundColorToStr(self):
        return "#%02x%02x%02x" % self.background

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

    def _require_selected_tile(self):
        if self.currentTileId is None:
            messagebox.showinfo(title="Pin participant", message="Select a participant tile first.")
            return None
        return self.currentTileId

    def menu_OpenToPreview(self):
        tile_id = self._require_selected_tile()
        if tile_id is None:
            return

        if self.renderPreviewWindow is None or not self.renderPreviewWindow.exists():
            self.renderPreviewWindow = WindowRendererPreview(
                self.window,
                "PINNED PARTICIPANT",
                self.background,
                self.captureRunnerOnThread,
                [tile_id],
            )
        else:
            self.renderPreviewWindow.update(self.captureRunnerOnThread, [tile_id])
        self.renderPreviewWindow.render()

    def menu_Open(self):
        tile_id = self._require_selected_tile()
        if tile_id is None:
            return

        pin_window = WindowRendererPreview(
            self.window,
            "PINNED PARTICIPANT",
            self.background,
            self.captureRunnerOnThread,
            [tile_id],
        )
        self.pinWindows.append(pin_window)
        pin_window.render()

    def menu_OpenToGroupPreview(self):
        tile_id = self._require_selected_tile()
        if tile_id is None:
            return

        self.captureRunnerOnThread.addPinnedTile(tile_id)
        self.menu_OpenGroupPreview()

    def menu_OpenGroupPreview(self):
        if self.renderGroupPreviewWindow is None or not self.renderGroupPreviewWindow.exists():
            self.renderGroupPreviewWindow = WindowRendererGroupPreview(
                self.window,
                "GROUP PREVIEW",
                self.background,
                self.captureRunnerOnThread,
            )
        else:
            self.renderGroupPreviewWindow.update(self.background, self.captureRunnerOnThread)
        self.renderGroupPreviewWindow.render()

    def menu_ClearGroupPreview(self):
        self.captureRunnerOnThread.clearPinnedTiles()

    def menu_ShowDebugOverlay(self):
        overlay = self.captureRunnerOnThread.capPorcessor.build_debug_overlay()
        if overlay is None:
            messagebox.showinfo(title="Detection debug", message="No detection overlay is available yet.")
            return
        cv2.imshow("detection debug overlay", overlay)
