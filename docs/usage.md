# Usage

## Select Zoom

1. Start or join a Zoom meeting.
2. Switch Zoom to Gallery View.
3. Open MERGE-ZOOM-MANAGER.
4. Use **Window Search** to filter visible windows.
5. Select the Zoom meeting window from the row dropdown.
6. Click the preview tile to refresh and inspect the capture.

## Render the gallery

Click **RENDER** to open the full-screen combined gallery window. The app continuously captures the selected Zoom window, detects participant rectangles, assigns stable participant IDs, and renders the current gallery.

The overlay in the upper-left shows detected tile count and measured capture FPS.

## Pin participants

Right-click a detected participant tile in the render window:

- **Pin Selected Participant** reuses the main pin window for one participant.
- **Pin Selected In New Window** opens another live pin window for that participant.
- **Add Selected To Group Pin** adds the participant to a multi-participant pin window.
- **Open Group Pin Window** opens the current group pin set.
- **Clear Group Pins** clears the group pin list.

Pinned views stay linked to tracked participant IDs, so they update when Zoom rearranges, resizes, or moves tiles. If a pinned participant is temporarily missing, the pin window shows a searching message instead of crashing or freezing on invalid coordinates.

## Debug detection

Right-click the render window and choose **Show Detection Debug Overlay** to inspect the latest detected rectangles. A reference overlay looks like this:

![Detection debug overlay reference](images/detection-debug-reference.png)
