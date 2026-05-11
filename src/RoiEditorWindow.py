import tkinter as TK
from tkinter import messagebox

import numpy as np

from image_utils import aspect_fit_rect, cv_to_photo_image
from models import Rect


class RoiEditorWindow:
    def __init__(self, parent, title: str, image: np.ndarray, roi: Rect, background, on_save, on_reset):
        self.parent = parent
        self.image = image
        self.roi = tuple(int(value) for value in roi)
        self.background = background
        self.on_save = on_save
        self.on_reset = on_reset
        self.display_rect = (0, 0, 1, 1)
        self.drag_start = None
        self.photo = None

        self.window = TK.Toplevel(parent)
        self.window.title(title)
        self.window.geometry("960x640")
        self.window.minsize(480, 320)

        self.canvas = TK.Canvas(self.window, background="#111111", highlightthickness=0)
        self.canvas.pack(fill=TK.BOTH, expand=True)

        button_bar = TK.Frame(self.window, padx=8, pady=8)
        button_bar.pack(fill=TK.X)
        TK.Button(button_bar, text="Save ROI", width=12, command=self._save).pack(side=TK.LEFT, padx=(0, 6))
        TK.Button(button_bar, text="Reset Default", width=12, command=self._reset).pack(side=TK.LEFT, padx=(0, 6))
        TK.Button(button_bar, text="Cancel", width=12, command=self.close).pack(side=TK.RIGHT)

        self.canvas.bind("<Configure>", lambda _event: self._redraw())
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.after(50, self._redraw)

    def close(self):
        if self.window is not None and self.window.winfo_exists():
            self.window.destroy()

    def _save(self):
        if self.roi[2] < 2 or self.roi[3] < 2:
            messagebox.showwarning(title="Gallery ROI", message="Draw a larger ROI before saving.")
            return
        self.on_save(self.roi)
        self.close()

    def _reset(self):
        self.on_reset()
        self.close()

    def _redraw(self):
        if self.image is None or self.image.size == 0:
            return

        canvas_width = max(1, self.canvas.winfo_width())
        canvas_height = max(1, self.canvas.winfo_height())
        source_height, source_width = self.image.shape[:2]
        self.display_rect = aspect_fit_rect((source_width, source_height), (canvas_width, canvas_height))
        self.photo = cv_to_photo_image(self.image, (canvas_width, canvas_height), self.background)

        self.canvas.delete("all")
        display_x, display_y, _display_width, _display_height = self.display_rect
        self.canvas.create_image(display_x, display_y, image=self.photo, anchor=TK.NW)
        self._draw_roi()

    def _draw_roi(self):
        x, y, width, height = self.roi
        x1, y1 = self._source_to_display(x, y)
        x2, y2 = self._source_to_display(x + width, y + height)
        self.canvas.create_rectangle(x1, y1, x2, y2, outline="#ffaa28", width=2)
        self.canvas.create_text(
            x1 + 6,
            max(14, y1 + 14),
            text=f"x={x} y={y} w={width} h={height}",
            fill="#ffaa28",
            anchor=TK.W,
            font=("Segoe UI", 10, "bold"),
        )

    def _start_drag(self, event):
        if not self._inside_display(event.x, event.y):
            self.drag_start = None
            return
        self.drag_start = self._display_to_source(event.x, event.y)
        self.roi = (self.drag_start[0], self.drag_start[1], 1, 1)
        self._redraw()

    def _drag(self, event):
        if self.drag_start is None:
            return
        self._update_drag_roi(event.x, event.y)
        self._redraw()

    def _end_drag(self, event):
        if self.drag_start is None:
            return
        self._update_drag_roi(event.x, event.y)
        self.drag_start = None
        self._redraw()

    def _update_drag_roi(self, display_x: int, display_y: int):
        source_x, source_y = self._display_to_source(display_x, display_y)
        start_x, start_y = self.drag_start
        x1 = min(start_x, source_x)
        y1 = min(start_y, source_y)
        x2 = max(start_x, source_x)
        y2 = max(start_y, source_y)
        self.roi = (x1, y1, max(1, x2 - x1), max(1, y2 - y1))

    def _inside_display(self, x: int, y: int) -> bool:
        display_x, display_y, display_width, display_height = self.display_rect
        return display_x <= x <= display_x + display_width and display_y <= y <= display_y + display_height

    def _display_to_source(self, x: int, y: int) -> tuple[int, int]:
        source_height, source_width = self.image.shape[:2]
        display_x, display_y, display_width, display_height = self.display_rect
        clamped_x = max(display_x, min(x, display_x + display_width))
        clamped_y = max(display_y, min(y, display_y + display_height))
        source_x = int(round((clamped_x - display_x) * source_width / float(max(1, display_width))))
        source_y = int(round((clamped_y - display_y) * source_height / float(max(1, display_height))))
        return max(0, min(source_width, source_x)), max(0, min(source_height, source_y))

    def _source_to_display(self, x: int, y: int) -> tuple[int, int]:
        source_height, source_width = self.image.shape[:2]
        display_x, display_y, display_width, display_height = self.display_rect
        display_point_x = display_x + int(round(x * display_width / float(max(1, source_width))))
        display_point_y = display_y + int(round(y * display_height / float(max(1, source_height))))
        return display_point_x, display_point_y
