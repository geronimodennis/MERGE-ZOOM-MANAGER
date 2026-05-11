# Architecture

The app is organized around multiple Zoom session captures, detection, tracking, merged rendering, and pin windows.

```mermaid
flowchart LR
    A1["Zoom Session 1 Gallery View"] --> B1["WindowCapture"]
    A2["Zoom Session 2 Gallery View"] --> B2["WindowCapture"]
    AX["Additional Zoom Sessions"] --> BX["WindowCapture"]
    B1 --> C["CaptureProcessor"]
    B2 --> C
    BX --> C
    C --> D["ZoomGalleryDetector"]
    D --> E["ParticipantTracker"]
    E --> F["CaptureRunnerOnThread"]
    F --> G["Merged Gallery Renderer"]
    F --> H["Single Pin Windows"]
    F --> I["Group Pin Window"]
```

## Purpose

MERGE-ZOOM-MANAGER combines one or more Zoom App Gallery View sessions into a single managed participant gallery. This is intended for workflows where Zoom's visible Gallery View is limited per session, commonly to about 49 participants, and multiple Zoom windows are used to cover a larger participant set. Each configured Zoom window is captured independently, then all detected participant tiles are merged into one render stream.

## Modules

- `WindowCaptureConfiguration.py` manages one or more Zoom session capture rows and passes the selected windows into the renderer.
- `windowCaptureHandler.py` captures each selected Zoom window with Win32/GDI and recreates capture resources when the window size changes.
- `participant_detection.py` detects participant rectangles with projection and edge-based passes instead of fixed coordinates.
- `participant_tracking.py` assigns stable IDs using overlap, position, size, and visual descriptors.
- `CaptureProcessor.py` coordinates capture, detection, tracking, and debug overlays across all configured Zoom session sources.
- `captureRunnerOnThread.py` runs one bounded 30 FPS capture loop and exposes immutable snapshots to the Tk renderers.
- `WindowRenderer.py` displays the merged gallery and maps clicks back to live tile metadata from any captured source.
- `WindowRendererPreview.py` displays one pinned participant window.
- `WindowRendererGroupPreview.py` displays multiple pinned participants.
- `image_utils.py` contains shared image sizing, Tk conversion, blank-frame, composite, and cell-mapping helpers.

## Detection

Detection is dynamic per frame and per source window. The detector estimates the Zoom background from border samples, builds a foreground mask, segments likely gallery rows and columns, and supplements that with edge contours. Candidates are filtered by size, aspect ratio, area, and overlap.

The result is a list of `ParticipantTile` objects with:

- source window key
- rectangle in the Zoom capture
- crop image
- confidence score
- visual descriptor

## Tracking

Tracking does not depend on a fixed list index or on a participant's position inside one Zoom session. Each new frame is matched against current tracks using:

- rectangle overlap
- visual descriptor similarity
- center movement
- size similarity

This keeps pins stable when tiles move or resize within any captured Zoom session. Tracks are retained briefly through detection failures so temporary layout changes do not immediately discard pinned participants.

## Performance

The capture loop targets 30 FPS and keeps frame queues bounded to avoid memory growth. It logs measured capture FPS every few seconds so performance can be verified while the app is running.
