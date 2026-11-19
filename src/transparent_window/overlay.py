"""Click-through acrylic-style rim shown around the active aperture."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from . import win32
from .controller import RevealController

RING_WIDTH = 12
RING_GAP = 2
RING_MARGIN = RING_GAP + RING_WIDTH + 8


class ApertureRingOverlay(QWidget):
    def __init__(self, parent=None) -> None:
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        super().__init__(parent, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._radius = 120
        self._visible = False
        hwnd = int(self.winId())
        try:
            win32.Win32Backend.configure_click_through(hwnd)
        except Exception:
            self.close()
            raise

    def follow_controller(self, controller: RevealController) -> None:
        """Mirror the controller's applied aperture; target discovery stays in the backend."""
        point = controller.aperture_point
        target = controller.target
        if point is None or target is None:
            if self._visible:
                self.hide()
                self._visible = False
            return

        self._radius = controller.radius
        # Include the outer glow and pen extents so the strokes are not clipped.
        diameter = 2 * (self._radius + RING_MARGIN) + 1
        left = point[0] - self._radius - RING_MARGIN
        top = point[1] - self._radius - RING_MARGIN
        self.setGeometry(QRect(left, top, diameter, diameter))
        self.update()
        if not self._visible:
            self.show()
            self._visible = True
        self.raise_()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self.rect().center()
        radius = self._radius

        # Layered translucent strokes suggest acrylic; this is not a captured backdrop blur.
        for offset, color, width in (
            (RING_GAP + (RING_WIDTH + 8) / 2, QColor(35, 145, 220, 24), RING_WIDTH + 8),
            (RING_GAP + RING_WIDTH / 2, QColor(110, 205, 255, 68), RING_WIDTH),
            (RING_GAP + 0.75, QColor(235, 250, 255, 175), 1.5),
        ):
            painter.setPen(QPen(color, width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius + offset, radius + offset)
        painter.end()
