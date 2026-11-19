"""System-tray controls for the reveal state and settings dialog."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from .controller import RevealController
from .settings import Preferences, SettingsDialog


class TrayController:
    def __init__(
        self,
        controller: RevealController,
        preferences: Preferences,
    ) -> None:
        self.controller = controller
        self.preferences = preferences
        self.tray = QSystemTrayIcon(
            QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        )
        self.tray.setToolTip("Transparent Window")

        self.menu = QMenu()
        menu = self.menu
        self.hold_action = QAction("Hold Ctrl to reveal", menu)
        self.hold_action.setEnabled(False)
        menu.addAction(self.hold_action)
        settings_action = QAction("Settings…", menu)
        settings_action.triggered.connect(self._show_settings)
        menu.addAction(settings_action)
        menu.addSeparator()
        exit_action = QAction("Exit", menu)
        exit_action.triggered.connect(self._quit)
        menu.addAction(exit_action)

        self.tray.setContextMenu(menu)
        self.tray.setToolTip("Transparent Window — hold Ctrl to reveal")
        self.menu.aboutToShow.connect(self._update_status)
        self.settings_action = settings_action
        self.exit_action = exit_action
        self.settings_dialog: SettingsDialog | None = None
        self._last_shown_error: str | None = None
        self.status_timer = QTimer(self.tray)
        self.status_timer.setInterval(500)
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start()

    def show(self) -> None:
        self.tray.show()

    def show_message(self, title: str, message: str) -> None:
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 4000)

    def close(self) -> None:
        self.status_timer.stop()
        self.tray.hide()

    def _update_status(self) -> None:
        if self.controller.last_error:
            self.tray.setToolTip(f"Transparent Window: {self.controller.last_error}")
            if self._last_shown_error != self.controller.last_error:
                self._last_shown_error = self.controller.last_error
                self.show_message("Window operation failed", self.controller.last_error)
        else:
            self._last_shown_error = None
            self.tray.setToolTip("Transparent Window — hold Ctrl to reveal")

    def _show_settings(self) -> None:
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self.preferences)
            self.settings_dialog.radius_changed.connect(self.controller.set_radius)
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def _quit(self) -> None:
        QApplication.quit()
