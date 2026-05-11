# MERGE-ZOOM-MANAGER

MERGE-ZOOM-MANAGER is a Windows desktop helper for capturing Zoom Gallery View, detecting participant tiles dynamically, and pinning one or more participants into separate live windows.

The current version replaces fixed-coordinate tile selection with continuous participant rectangle detection and stable tracking IDs. Pinned windows now follow the selected participant tiles as Zoom is resized, participants join or leave, or the gallery layout changes.

## Quick Start

1. Install Python 3.10 or newer on Windows.
2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt -r requirements-dev.txt
   ```

3. In Zoom video settings, set **Video Rendering Method** to **Direct3D11** or **GDI**.
4. Start or join a Zoom meeting and switch to Gallery View.
5. Run the app:

   ```powershell
   cd src
   python WindowCaptureConfiguration.py
   ```

6. Search for the Zoom meeting window, select it, then click **RENDER**.
7. Right-click a detected participant tile to pin it.

## Documentation

- [Setup](docs/setup.md)
- [Usage](docs/usage.md)
- [Architecture](docs/architecture.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Build and release](docs/release.md)

## Build

Create the redistributable executable from the `src` directory:

```powershell
cd src
python -m PyInstaller --clean --noconfirm WindowCaptureConfiguration.spec
```

The executable is written to `src\dist\MERGE-ZOOM-MANAGER.exe`.

## Notes

Window capture depends on Windows GDI capture behavior and Zoom's selected rendering mode. Minimized Zoom windows may not produce usable frames, so keep the Zoom meeting visible when possible.
