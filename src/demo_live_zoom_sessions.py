"""Run synthetic Zoom Gallery View windows for a local live demo.

The demo windows are regular Windows/Tk windows whose titles include
"Zoom Meeting" so the normal setup screen can discover and capture them.
"""

import argparse
import math
import random
import tkinter as tk
from dataclasses import dataclass


TOP_BAR_HEIGHT = 52
BOTTOM_BAR_HEIGHT = 82
TILE_GAP = 8
CONTENT_MARGIN = 14
DEFAULT_FPS = 24


@dataclass(frozen=True)
class DemoParticipant:
    name: str
    initials: str
    color: str
    camera_on: bool


PARTICIPANT_NAMES = [
    ("Ana Reyes", "AR"),
    ("Ben Santos", "BS"),
    ("Dennis Geronimo", "DG"),
    ("Ella Cruz", "EC"),
    ("Marco Lim", "ML"),
    ("Nina Ramos", "NR"),
    ("Paolo Tan", "PT"),
    ("Rhea Dizon", "RD"),
    ("Sam Uy", "SU"),
    ("Tina Lopez", "TL"),
    ("Victor Ong", "VO"),
    ("Wendy Chua", "WC"),
    ("Carlo Diaz", "CD"),
    ("Maya Flores", "MF"),
    ("Luis Garcia", "LG"),
    ("Ivy Chan", "IC"),
    ("Owen Lee", "OL"),
    ("Grace Yu", "GY"),
]

CAMERA_COLORS = [
    "#3b65c9",
    "#2e8f69",
    "#b96545",
    "#7355af",
    "#2f8fa3",
    "#9d7c2f",
    "#b04e75",
    "#4c7a9f",
]


class DemoSessionWindow:
    def __init__(
        self,
        parent: tk.Tk,
        session_index: int,
        participants: list[DemoParticipant],
        fps: int,
        width: int,
        height: int,
        x: int,
        y: int,
    ):
        self.session_index = session_index
        self.participants = participants
        self.frame_index = 0
        self.paused = False
        self.frame_delay_ms = max(10, int(1000 / max(1, fps)))

        self.window = tk.Toplevel(parent)
        self.window.title(f"Zoom Meeting - Demo Session {session_index}")
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        self.window.minsize(640, 420)

        self.canvas = tk.Canvas(self.window, highlightthickness=0, background="#111111")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.window.bind("<space>", self._toggle_pause)
        self.window.bind("<Configure>", lambda _event: self.draw())

        self.draw()
        self.window.after(self.frame_delay_ms, self.tick)

    def _toggle_pause(self, _event=None):
        self.paused = not self.paused

    def tick(self):
        if not self.paused:
            self.frame_index += 1
            self.draw()
        self.window.after(self.frame_delay_ms, self.tick)

    def draw(self):
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        if width <= 1 or height <= 1:
            width, height = 960, 610

        canvas = self.canvas
        canvas.delete("all")
        canvas.create_rectangle(0, 0, width, height, fill="#111111", outline="")
        self._draw_top_bar(width)
        self._draw_bottom_bar(width, height)

        content_y = TOP_BAR_HEIGHT
        content_height = max(1, height - TOP_BAR_HEIGHT - BOTTOM_BAR_HEIGHT)
        rects = self._gallery_rects(width, content_y, content_height)
        active_index = (self.frame_index // 48) % max(1, len(rects))

        for index, rect in enumerate(rects):
            participant = self.participants[index]
            self._draw_participant_tile(rect, participant, index, active_index == index)

    def _draw_top_bar(self, width: int):
        self.canvas.create_rectangle(0, 0, width, TOP_BAR_HEIGHT, fill="#171717", outline="")
        self.canvas.create_text(
            18,
            18,
            anchor=tk.W,
            text=f"Demo Zoom Session {self.session_index}",
            fill="#f1f1f1",
            font=("Segoe UI", 12, "bold"),
        )
        self.canvas.create_text(
            width - 18,
            18,
            anchor=tk.E,
            text="Gallery View",
            fill="#d8d8d8",
            font=("Segoe UI", 10),
        )
        self.canvas.create_rectangle(width - 126, 30, width - 18, 46, fill="#2b2b2b", outline="#484848")
        self.canvas.create_text(width - 72, 38, text="Demo Source", fill="#f0f0f0", font=("Segoe UI", 8))

    def _draw_bottom_bar(self, width: int, height: int):
        y = height - BOTTOM_BAR_HEIGHT
        self.canvas.create_rectangle(0, y, width, height, fill="#151515", outline="")
        labels = ["Mute", "Stop Video", "Participants", "Share", "More"]
        for index, label in enumerate(labels):
            x = 58 + index * 118
            self.canvas.create_oval(x - 14, y + 14, x + 14, y + 42, fill="#292929", outline="#444444")
            self.canvas.create_text(x, y + 58, text=label, fill="#dcdcdc", font=("Segoe UI", 8))
        self.canvas.create_rectangle(width - 116, y + 22, width - 24, y + 54, fill="#8f2020", outline="")
        self.canvas.create_text(width - 70, y + 38, text="Leave", fill="#ffffff", font=("Segoe UI", 9, "bold"))

    def _gallery_rects(self, width: int, content_y: int, content_height: int) -> list[tuple[int, int, int, int]]:
        count = len(self.participants)
        available_width = max(1, width - CONTENT_MARGIN * 2)
        available_height = max(1, content_height - CONTENT_MARGIN * 2)
        best = None

        for columns in range(1, count + 1):
            rows = int(math.ceil(count / float(columns)))
            tile_width = int((available_width - (columns - 1) * TILE_GAP) / columns)
            tile_height = int(tile_width * 9 / 16)
            if rows * tile_height + (rows - 1) * TILE_GAP > available_height:
                tile_height = int((available_height - (rows - 1) * TILE_GAP) / rows)
                tile_width = int(tile_height * 16 / 9)
            if tile_width <= 0 or tile_height <= 0:
                continue
            if columns * tile_width + (columns - 1) * TILE_GAP > available_width:
                continue

            area = tile_width * tile_height
            if best is None or area > best[0]:
                best = (area, columns, rows, tile_width, tile_height)

        if best is None:
            return []

        _area, columns, rows, tile_width, tile_height = best
        total_grid_height = rows * tile_height + (rows - 1) * TILE_GAP
        start_y = content_y + CONTENT_MARGIN + int((available_height - total_grid_height) / 2)
        rects = []
        remaining = count

        for row in range(rows):
            row_count = min(columns, remaining)
            remaining -= row_count
            row_width = row_count * tile_width + (row_count - 1) * TILE_GAP
            start_x = CONTENT_MARGIN + int((available_width - row_width) / 2)
            for column in range(row_count):
                x = start_x + column * (tile_width + TILE_GAP)
                y = start_y + row * (tile_height + TILE_GAP)
                rects.append((x, y, tile_width, tile_height))
        return rects

    def _draw_participant_tile(
        self,
        rect: tuple[int, int, int, int],
        participant: DemoParticipant,
        index: int,
        is_active: bool,
    ):
        x, y, width, height = rect
        if participant.camera_on:
            self._draw_camera_on_tile(x, y, width, height, participant.color, index)
        else:
            self._draw_camera_off_tile(x, y, width, height, participant, index)

        if is_active:
            self.canvas.create_rectangle(x + 1, y + 1, x + width - 2, y + height - 2, outline="#2dff7d", width=4)
        else:
            self.canvas.create_rectangle(x, y, x + width, y + height, outline="#222222", width=1)

        self._draw_name_badge(x, y, width, height, participant)

    def _draw_camera_on_tile(self, x: int, y: int, width: int, height: int, color: str, index: int):
        base_colors = [color, "#20242d", "#3f4655"]
        self.canvas.create_rectangle(x, y, x + width, y + height, fill=base_colors[index % len(base_colors)], outline="")
        offset = (self.frame_index * 3 + index * 31) % max(1, width)
        for band in range(-width, width * 2, max(28, width // 8)):
            band_x = x + ((band + offset) % (width + 80)) - 40
            self.canvas.create_polygon(
                band_x,
                y,
                band_x + 42,
                y,
                band_x - 20,
                y + height,
                band_x - 62,
                y + height,
                fill="#ffffff",
                stipple="gray75",
                outline="",
            )
        cx = x + width // 2
        cy = y + height // 2
        radius = max(22, min(width, height) // 5)
        self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill="#d7d7d7", outline="")
        self.canvas.create_oval(cx - radius // 2, cy - radius, cx + radius // 2, cy, fill="#f0f0f0", outline="")
        self.canvas.create_arc(
            cx - radius,
            cy - radius // 4,
            cx + radius,
            cy + radius,
            start=0,
            extent=180,
            fill="#ececec",
            outline="",
        )

    def _draw_camera_off_tile(self, x: int, y: int, width: int, height: int, participant: DemoParticipant, index: int):
        low_contrast_colors = ["#232323", "#050505", "#282828", "#181818"]
        fill = low_contrast_colors[index % len(low_contrast_colors)]
        self.canvas.create_rectangle(x, y, x + width, y + height, fill=fill, outline="")

        if index % 3 != 2:
            cx = x + width // 2
            cy = y + height // 2 - max(8, height // 12)
            radius = max(22, min(width, height) // 5)
            self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill="#3f4e63", outline="")
            self.canvas.create_text(
                cx,
                cy,
                text=participant.initials,
                fill="#eeeeee",
                font=("Segoe UI", max(14, radius // 2), "bold"),
            )

    def _draw_name_badge(self, x: int, y: int, width: int, height: int, participant: DemoParticipant):
        badge_width = min(width - 12, max(112, len(participant.name) * 8 + 34))
        badge_height = max(22, min(28, height // 6))
        badge_x = x + 8
        badge_y = y + height - badge_height - 8
        self.canvas.create_rectangle(
            badge_x,
            badge_y,
            badge_x + badge_width,
            badge_y + badge_height,
            fill="#242424",
            outline="#303030",
        )
        self.canvas.create_oval(badge_x + 8, badge_y + 7, badge_x + 18, badge_y + 17, fill="#d64242", outline="")
        self.canvas.create_line(badge_x + 9, badge_y + 17, badge_x + 18, badge_y + 7, fill="#ffffff", width=1)
        self.canvas.create_text(
            badge_x + 27,
            badge_y + badge_height // 2,
            anchor=tk.W,
            text=participant.name,
            fill="#f5f5f5",
            font=("Segoe UI", 9),
        )


class DemoControlWindow:
    def __init__(self, root: tk.Tk, sessions: list[DemoSessionWindow]):
        self.root = root
        self.sessions = sessions
        root.title("MERGE-ZOOM-MANAGER Live Demo Controls")
        root.geometry("520x250+60+60")
        root.configure(background="#f5f5f5")

        tk.Label(
            root,
            text="Live Demo Sources",
            background="#f5f5f5",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor=tk.W, padx=16, pady=(14, 4))
        tk.Label(
            root,
            text=(
                "These windows simulate Zoom Gallery View sessions. Open the normal setup app, "
                "search for 'zoom meeting', add each demo session, then click RENDER."
            ),
            wraplength=480,
            justify=tk.LEFT,
            background="#f5f5f5",
            font=("Segoe UI", 10),
        ).pack(anchor=tk.W, padx=16)

        button_row = tk.Frame(root, background="#f5f5f5")
        button_row.pack(anchor=tk.W, padx=16, pady=16)
        tk.Button(button_row, text="Pause / Resume", command=self.toggle_pause).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(button_row, text="Shuffle Participants", command=self.shuffle_participants).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(button_row, text="Quit Demo", command=root.destroy).pack(side=tk.LEFT)

        source_names = "\n".join(f"- Zoom Meeting - Demo Session {session.session_index}" for session in sessions)
        tk.Label(
            root,
            text=source_names,
            justify=tk.LEFT,
            background="#f5f5f5",
            font=("Consolas", 9),
        ).pack(anchor=tk.W, padx=16)

    def toggle_pause(self):
        for session in self.sessions:
            session.paused = not session.paused

    def shuffle_participants(self):
        for session in self.sessions:
            random.shuffle(session.participants)
            session.draw()


def build_participants(session_index: int, count: int) -> list[DemoParticipant]:
    participants = []
    offset = (session_index - 1) * count
    for index in range(count):
        name, initials = PARTICIPANT_NAMES[(offset + index) % len(PARTICIPANT_NAMES)]
        participants.append(
            DemoParticipant(
                name=name,
                initials=initials,
                color=CAMERA_COLORS[(offset + index) % len(CAMERA_COLORS)],
                camera_on=(index % 4 != 2),
            )
        )
    return participants


def parse_args():
    parser = argparse.ArgumentParser(description="Run live synthetic Zoom Gallery View demo windows.")
    parser.add_argument("--sessions", type=int, default=2, help="Number of demo Zoom sessions to create.")
    parser.add_argument("--participants", type=int, default=9, help="Participants per demo session.")
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS, help="Animation FPS for the demo windows.")
    parser.add_argument("--width", type=int, default=900, help="Width of each demo Zoom session window.")
    parser.add_argument("--height", type=int, default=520, help="Height of each demo Zoom session window.")
    return parser.parse_args()


def main():
    args = parse_args()
    session_count = max(1, args.sessions)
    participant_count = max(1, args.participants)
    root = tk.Tk()

    sessions = []
    for index in range(session_count):
        x = 80 + index * 70
        y = 210 + index * 38
        participants = build_participants(index + 1, participant_count)
        sessions.append(
            DemoSessionWindow(
                root,
                index + 1,
                participants,
                max(1, args.fps),
                max(640, args.width),
                max(420, args.height),
                x,
                y,
            )
        )

    DemoControlWindow(root, sessions)
    root.mainloop()


if __name__ == "__main__":
    main()
