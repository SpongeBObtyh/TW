"""Radius preferences and the compact settings dialog."""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import QDialog, QFormLayout, QSpinBox, QVBoxLayout


class Preferences:
    """Persist user preferences across application launches via the OS settings store."""

    def __init__(self) -> None:
        self._settings = QSettings("TransparentWindow", "TransparentWindow")

    @property
    def radius(self) -> int:
        return max(10, min(1000, self._settings.value("radius", 120, type=int)))

    @radius.setter
    def radius(self, value: int) -> None:
        self._settings.setValue("radius", max(10, min(1000, int(value))))


class SettingsDialog(QDialog):
    radius_changed = Signal(int)

    def __init__(self, preferences: Preferences, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Transparent Window Settings")
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        radius = QSpinBox(self)
        radius.setRange(10, 1000)
        radius.setSuffix(" px")
        radius.setToolTip("The radius is measured in physical screen pixels.")
        radius.setValue(preferences.radius)
        radius.valueChanged.connect(lambda value: setattr(preferences, "radius", value))
        radius.valueChanged.connect(self.radius_changed)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Circular opening radius:", radius)
        layout.addLayout(form)
