# Transparent Window

A small Windows tray utility that punches a mouse-following circular opening in the top-level window under the pointer, revealing windows below it. Clicks in the opening pass through to the underlying window.

- Hold either **Ctrl** key to reveal a circular area centered on the pointer; releasing Ctrl restores the window.
- A translucent acrylic-style ring highlights the aperture edge; the circle itself remains clear.
- Click and edit through the opening while the clipped top window stays visually in front. The underlying app can receive focus so it can accept keyboard input.
- Set the opening radius from the tray menu's **Settings…** item.
- The selected window stays locked while the pointer is within its bounds; leaving it restores that window before selecting another.

## Run from source

Requires Windows and Python 3.10 or newer.

```powershell
python -m pip install -e ".[dev]"
python -m transparent_window
```

The app lives in the system tray. Right-click its icon to open settings or exit. The menu also reminds you to hold Ctrl to reveal. Ctrl state is polled globally every 30 ms, so release normally restores the window within one polling interval. The top window is kept in front without forcing foreground activation; the underlying app may still receive keyboard focus so it can accept typing. Exact z-order restoration is best-effort if other apps change the window order while the effect is active.

## Build a Windows executable

Build on Windows with Python 3.10 or newer. From the repository root, install the app and PyInstaller packaging extra, then create a single-file GUI executable:

```powershell
python -m pip install -e ".[packaging]"
python -m PyInstaller --noconfirm --clean --onefile --windowed --name TransparentWindow --paths src freeze_entry.py
```

The executable is written to `dist/TransparentWindow.exe`. It runs as a tray app without opening a console window. The `.exe` is not an installer and is not code-signed.

## Development checks

```powershell
python -m pytest
python -m pytest tests/test_controller.py -k test_disable_restores_and_releases_snapshot
python -m ruff check .
python -m build
```

The state machine/geometry tests run without Windows APIs. Real region clipping, click-through behavior, Ctrl polling, acrylic-style overlay alignment, z-order restoration, DPI/multi-monitor behavior, and windows at another integrity level need manual verification on Windows. The ring is a translucent gradient effect, not a true backdrop blur.

## Limitations

The app alters another application's native window region. It attempts to restore the original region during normal shutdown and handled errors; a forced termination may leave the window changed until it closes. Elevated/protected windows, some custom-shaped or GPU-rendered windows, and exclusive-fullscreen apps may not work as expected. Passing clicks through the opening can activate or reorder the window underneath.
