# Build and Release

## Checks

From the repository root:

```powershell
python -m compileall src tests
python -m ruff check .
python -m pytest -q
```

## Build executable

From the `src` directory:

```powershell
python -m PyInstaller --clean --noconfirm WindowCaptureConfiguration.spec
```

Output:

```text
src\dist\MERGE-ZOOM-MANAGER.exe
```

## Release checklist

1. Confirm tests and linting pass.
2. Build the executable.
3. Smoke-test the executable against a Zoom Gallery View window.
4. Commit the completed changes.
5. Push the commit and tag.
6. Create a GitHub release and attach `src\dist\MERGE-ZOOM-MANAGER.exe`.

Suggested tag format:

```text
v1.7.0
```
