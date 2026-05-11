# Setup

## Requirements

- Windows 10 or Windows 11.
- Python 3.10 or newer.
- Zoom desktop app.
- A Zoom meeting window using Gallery View.

## Install dependencies

From the repository root:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Runtime dependencies are listed in `requirements.txt`. Build and test tools are listed in `requirements-dev.txt`.

## Zoom video setting

In Zoom, open video settings and set **Video Rendering Method** to **Direct3D11** or **GDI**. If capture shows a blank or stale frame, switch between these two modes and restart Zoom.

## Run from source

```powershell
cd src
python WindowCaptureConfiguration.py
```

The setup window lets you search visible windows, select the Zoom meeting window, preview the capture, and launch the combined render window.
