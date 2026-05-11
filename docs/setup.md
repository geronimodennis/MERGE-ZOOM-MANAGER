# Setup

## Requirements

- Windows 10 or Windows 11.
- Python 3.10 or newer.
- Zoom desktop app.
- One or more Zoom meeting windows using Gallery View.

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

The setup window lets you search visible windows, select Zoom meeting windows, preview each capture, and launch the combined render window.

## Configure one or more Zoom sessions

MERGE-ZOOM-MANAGER can capture a single Zoom Gallery View or merge several Zoom app sessions into one combined gallery. This is useful when each Zoom session can only show a limited Gallery View page, commonly up to about 49 visible participants, and you need to manage participants across more than one Zoom window.

1. Start each Zoom app session or meeting window.
2. Switch every Zoom window that you want to capture to Gallery View.
3. In MERGE-ZOOM-MANAGER, select the first Zoom window in the first row.
4. Click **ADD** for each additional Zoom session that should be included.
5. Select the correct Zoom meeting window in each added row.
6. Click each preview tile if you need to confirm that the selected row is capturing the expected Zoom Gallery View.
7. Click **RENDER** to merge all selected Zoom Gallery Views into one live gallery window.

Each selected row is treated as a separate source. Participant tiles detected from all sources are combined into the rendered gallery and can be pinned from the same right-click workflow.
