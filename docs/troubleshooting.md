# Troubleshooting

## No participant tiles detected

- Confirm Zoom is in Gallery View.
- Confirm each selected row is the active Zoom meeting window, not the Zoom launcher or settings window.
- In Zoom video settings, switch **Video Rendering Method** between **Direct3D11** and **GDI**, then restart Zoom.
- Right-click the render window and choose **Show Detection Debug Overlay**.

## A Zoom session is missing from the merged gallery

- Confirm the session has its own row in the setup window.
- Click **ADD** for each additional Zoom app session that should be merged.
- Refresh the window list, then re-select the missing Zoom meeting window.
- Click the row preview to confirm that the correct Gallery View is being captured.
- Keep every selected Zoom meeting window visible enough for Windows capture to return current frames.

## Capture is blank

- Keep each Zoom meeting visible. Minimized windows often cannot be captured reliably through GDI.
- Try resizing the affected Zoom window once after selecting it.
- Re-select the affected Zoom window in the setup screen and refresh the preview.

## Pinned participant disappeared

The participant may have left, Zoom may have hidden the tile, or detection may have failed for a few frames. The pin window shows a searching message until the tracker sees that participant again. If Zoom completely reorders participants with very similar-looking tiles, re-pin the participant from the main render window.

## Low FPS

- Close unnecessary preview windows.
- Keep each captured Zoom window size reasonable.
- Avoid running multiple high-resolution screen capture tools at the same time.
- Watch the capture FPS overlay in the render window. The target is 30 FPS when possible, with 24 FPS as the practical minimum for smooth pins.

## Build fails

- Reinstall dependencies:

  ```powershell
  python -m pip install -r requirements.txt -r requirements-dev.txt
  ```

- Build from the `src` directory:

  ```powershell
  cd src
  python -m PyInstaller --clean --noconfirm WindowCaptureConfiguration.spec
  ```
