# Usage

## Select Zoom sessions

1. Start or join one or more Zoom meetings.
2. Switch each Zoom meeting window to Gallery View.
3. Open MERGE-ZOOM-MANAGER.
4. Use **Window Search** to filter visible windows.
5. Select the first Zoom meeting window from the row dropdown.
6. Click **ADD** to add another capture row when you want to combine another Zoom app session.
7. Select the correct Zoom meeting window in each added row.
8. Click each preview tile to refresh and inspect that row's capture.

The app can be used with one Zoom session, or with multiple Zoom sessions at the same time. Multiple sessions are useful when Zoom Gallery View is limited to about 49 visible participants per window and you want to combine participants from Session 1, Session 2, and any other selected sessions into one managed view.

![Setup capture window](images/setup-capture-window.png)

For a no-Zoom test run, use the [live demo](demo.md). It opens synthetic Zoom-like Gallery View windows that can be selected and merged by the normal capture workflow.

## Render the gallery

Click **RENDER** to open the full-screen combined gallery window. The app continuously captures every selected Zoom window, detects participant rectangles in each Gallery View, assigns stable participant IDs, and renders one merged gallery from all sources.

The overlay in the upper-left shows detected tile count and measured capture FPS.

## Pin participants

Right-click a detected participant tile in the render window. The participant can come from any captured Zoom session:

- **Pin Selected Participant** reuses the main pin window for one participant.
- **Pin Selected In New Window** opens another live pin window for that participant.
- **Add Selected To Group Pin** adds the participant to a multi-participant pin window.
- **Open Group Pin Window** opens the current group pin set.
- **Clear Group Pins** clears the group pin list.

Pinned views stay linked to tracked participant IDs and source windows, so they update when Zoom rearranges, resizes, or moves tiles in any captured session. If a pinned participant is temporarily missing, the pin window shows a searching message instead of crashing or freezing on invalid coordinates.

## Debug detection

Right-click the render window and choose **Show Detection Debug Overlay** to inspect the latest detected rectangles. A reference overlay looks like this:

![Detection debug overlay reference](images/detection-debug-reference.png)
