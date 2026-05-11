# MERGE-ZOOM-MANAGER

MERGE-ZOOM-MANAGER is a Windows desktop helper for combining one or more Zoom App Gallery View sessions into a single merged participant gallery. It captures each selected Zoom meeting window, detects participant tiles dynamically, and lets you pin one or more participants into separate live windows.

Zoom Gallery View can only show a limited number of visible participants per gallery page, commonly up to about 49 participants. This project is designed for larger workflows where multiple Zoom app sessions are open at the same time, such as Session 1 showing one Gallery View and Session 2 showing another. MERGE-ZOOM-MANAGER combines those captured galleries into one managed window so participants from all selected sessions can be viewed, pinned, and tracked together.

The current version replaces fixed-coordinate tile selection with continuous participant rectangle detection and stable tracking IDs. Pinned windows now follow the selected participant tiles as Zoom windows are resized, participants join or leave, or gallery layouts change.

## Quick Start

1. Install Python 3.10 or newer on Windows.
2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt -r requirements-dev.txt
   ```

3. In each Zoom app session, set **Video Rendering Method** to **Direct3D11** or **GDI**.
4. Start or join one or more Zoom meetings and switch each meeting window to Gallery View.
5. Run the app:

   ```powershell
   cd src
   python WindowCaptureConfiguration.py
   ```

6. Search for a Zoom meeting window and select it. Use **ADD** to include more Zoom session windows when you want to merge multiple galleries.
7. Click **RENDER** to open the combined gallery window.
8. Right-click a detected participant tile from any captured Zoom session to pin it.

## Participant Detection

The detector is built for Zoom Gallery View layouts with dynamic participant counts from 1 to 49 visible tiles per page. It reconstructs participant rectangles from OpenCV signals instead of relying on fixed screen coordinates.

Important detection rules:

- The selected ROI is the detection boundary. Neon border, badge, edge, texture, and inferred-grid searches stay inside that ROI.
- Zoom's green active-speaker border is treated as the strongest tile-size signal. Fragmented neon borders are rebuilt into the full participant rectangle.
- Returned participant rectangles are landscape-oriented Zoom tiles, not name badges or near-square fragments.
- Blank, black, camera-off, low-contrast, and open-camera tiles can be inferred from gallery grid structure, name badges, texture, or vertical band changes.
- Inferred tiles follow Zoom-like gallery placement: near-square rows, equal spacing, and centered incomplete rows.
- Final participant rectangles are pruned to avoid meaningful overlap. Only tiny edge slop from border/rounding noise is allowed.

## Documentation

- [Setup](docs/setup.md)
- [Usage](docs/usage.md)
- [Live demo](docs/demo.md)
- [Screenshots](docs/screenshots.md)
- [Architecture](docs/architecture.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Build and release](docs/release.md)

## Live Demo

You can test the merge workflow without real Zoom meetings by running synthetic Zoom-like Gallery View windows:

```powershell
cd src
python demo_live_zoom_sessions.py --sessions 2 --participants 9 --fps 24
```

Then run `WindowCaptureConfiguration.py`, search for `zoom meeting`, add both demo sessions, and click **RENDER**.

Demo recording: [live-demo-session.mp4](docs/videos/live-demo-session.mp4)

## Build

Create the redistributable executable from the `src` directory:

```powershell
cd src
python -m PyInstaller --clean --noconfirm WindowCaptureConfiguration.spec
```

The executable is written to `src\dist\MERGE-ZOOM-MANAGER.exe`.

## Notes

Window capture depends on Windows GDI capture behavior and Zoom's selected rendering mode. Minimized Zoom windows may not produce usable frames, so keep each selected Zoom meeting visible when possible.
