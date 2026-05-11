# Live Demo

The live demo creates synthetic Zoom Gallery View windows so MERGE-ZOOM-MANAGER can be tested without joining real Zoom meetings. Each demo window is a normal Windows window titled like a Zoom meeting, so the capture setup screen can discover it through the existing **Window Search** workflow.

The demo includes:

- Multiple Zoom-like session windows.
- Camera-on participant tiles with subtle motion.
- Camera-off tiles with low-contrast dark layouts and small name badges.
- Active-speaker green borders that move between participants.
- Resizable windows so detection can be tested against layout changes.

![Live demo session](images/live-demo-session.png)

## Run the demo sources

From the repository root:

```powershell
cd src
python demo_live_zoom_sessions.py --sessions 2 --participants 9 --fps 24
```

This opens:

- `Zoom Meeting - Demo Session 1`
- `Zoom Meeting - Demo Session 2`
- `MERGE-ZOOM-MANAGER Live Demo Controls`

Keep the demo session windows visible. Minimized windows may not produce usable capture frames.

## Merge the demo sessions

Open a second terminal from the repository root:

```powershell
cd src
python WindowCaptureConfiguration.py
```

Then:

1. Search for `zoom meeting`.
2. Select `Zoom Meeting - Demo Session 1` in the first capture row.
3. Click **ADD**.
4. Select `Zoom Meeting - Demo Session 2` in the added row.
5. Click each preview tile to confirm that both demo sessions are being captured.
6. Click **RENDER**.
7. Right-click detected participant tiles in the merged gallery to test single or group pin windows.

## Useful variations

Run a larger demo:

```powershell
python demo_live_zoom_sessions.py --sessions 3 --participants 16 --fps 24
```

Run a smaller, faster smoke test:

```powershell
python demo_live_zoom_sessions.py --sessions 1 --participants 6 --fps 30
```

Resize a demo session window while the merged gallery is running to verify that participant rectangles update as the Gallery View layout changes.
