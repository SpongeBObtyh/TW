"""Application startup and timer-driven reveal lifecycle."""

from __future__ import annotations

import sys

from . import __version__
from .controller import RevealController


def main() -> int:
    if sys.platform != "win32":
        print("Transparent Window is a Windows-only application.", file=sys.stderr)
        return 1

    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication

        from .hold import CtrlHoldBinding
        from .overlay import ApertureRingOverlay
        from .settings import Preferences
        from .tray import TrayController
        from .win32 import Win32Backend, is_ctrl_pressed, set_per_monitor_dpi_awareness
    except ImportError as exc:
        print(f"Could not load a required Windows/UI dependency: {exc}", file=sys.stderr)
        return 1

    # Native window regions and Qt overlay geometry must share physical-pixel coordinates.
    set_per_monitor_dpi_awareness()
    app = QApplication(sys.argv)
    app.setApplicationName("Transparent Window")
    app.setOrganizationName("TransparentWindow")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)

    preferences = Preferences()
    backend = Win32Backend()
    controller = RevealController(backend, preferences.radius)
    hold_binding = CtrlHoldBinding(controller, is_ctrl_pressed)
    overlay = ApertureRingOverlay()
    tray = TrayController(controller, preferences)
    timer = QTimer(app)
    timer.setInterval(30)
    # Polling keeps the held aperture moving; the same cadence synchronizes the ring with it.
    timer.timeout.connect(hold_binding.poll)
    timer.timeout.connect(lambda: overlay.follow_controller(controller))
    timer.start()

    # Restore the foreign window before tearing down the ring and tray UI.
    app.aboutToQuit.connect(controller.close)
    app.aboutToQuit.connect(overlay.close)
    app.aboutToQuit.connect(tray.close)
    tray.show()
    tray.show_message("Ready", "Hold either Ctrl key to reveal through a circular opening.")
    return app.exec()
