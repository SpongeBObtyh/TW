# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Windows-only Python tray application that shows a mouse-following circular opening in the top-level window under the cursor while either Ctrl key is held. Releasing Ctrl restores the window. The opening reveals underlying windows and allows input through it, while a translucent acrylic-style ring surrounds its edge. The tray Settings dialog controls the radius in physical pixels. While the pointer remains within a selected target's bounds it stays locked to that window; moving outside restores it before selecting another. The app keeps the clipped window visually in front without forcing it to remain foreground; the underlying app may take keyboard focus, and exact z-order restoration is best-effort.

## Commands

Run from the repository root with Python 3.10+ on Windows:

- Install editable app and dev tools: `python -m pip install -e ".[dev]"`
- Run: `python -m transparent_window` (or installed `transparent-window` command)
- Run all tests: `python -m pytest`
- Run one test file: `python -m pytest tests/test_controller.py`
- Run one test: `python -m pytest tests/test_controller.py -k test_disable_restores_and_releases_snapshot`
- Lint: `python -m ruff check .`
- Build wheel: `python -m build`
- Build Windows executable: `python -m pip install -e ".[packaging]"`, then `python -m PyInstaller --noconfirm --clean --onefile --windowed --name TransparentWindow --paths src freeze_entry.py` (output: `dist/TransparentWindow.exe`)

## Architecture

- `src/transparent_window/app.py` owns Qt startup, DPI-awareness setup, the 30 ms Ctrl-state polling timer, tray UI, and the acrylic-style aperture overlay. `__main__.py` and the console script both enter `app.main()`; `hold.py` converts global Ctrl state into controller press/hold/release transitions.
- `controller.py` is a UI-independent state machine. Its `WindowBackend` protocol isolates target selection, region capture/application/restoration, z-order maintenance, and snapshot cleanup so transitions can be tested without Windows APIs.
- `win32.py` implements the backend with `ctypes`: cursor/window lookup, Ctrl key-state polling, target identity checks, region snapshots, aperture subtraction/restoration, and non-activating z-order maintenance. `geometry.py` provides pure screen-to-window coordinate conversion.
- `overlay.py` paints a click-through acrylic-style edge ring; `tray.py` exposes hold instructions, settings, and exit; `settings.py` persists radius using `QSettings`.
- `tests/` covers geometry, hold transitions, and mocked controller transitions. Native window-region behavior, click-through, overlay alignment, z-order restoration, mixed-DPI and elevated-window cases require interactive Windows verification.

## Platform constraints

The Win32 backend intentionally cannot import on non-Windows platforms. `SetWindowRgn` changes another process's window and success transfers ownership of region handles to Windows. Normal shutdown and handled failures restore the captured region, but forced termination may leave a target altered until it closes. Elevated/protected and some custom/GPU/full-screen windows may reject or behave differently. Click-through input can give keyboard focus to the underlying app while the clipped window is maintained visually in front; exact prior z-order restoration is best-effort. The ring uses a translucent gradient rather than true backdrop blur. Global Ctrl state is polled through `GetAsyncKeyState` every 30 ms.
