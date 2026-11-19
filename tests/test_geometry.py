from __future__ import annotations

from transparent_window.geometry import aperture_bounds


def test_aperture_coordinates_are_window_relative_on_negative_monitor():
    assert aperture_bounds((-1500, 300), 75, (-1920, 100)) == (345, 125, 495, 275)


def test_aperture_can_extend_past_window_edges():
    assert aperture_bounds((5, 10), 20, (0, 0)) == (-15, -10, 25, 30)
