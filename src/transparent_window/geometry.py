"""Small pure helpers for screen-to-window aperture coordinates."""


def aperture_bounds(
    point: tuple[int, int], radius: int, window_origin: tuple[int, int]
) -> tuple[int, int, int, int]:
    """Return the ellipse bounds relative to a target window's origin."""
    x = point[0] - window_origin[0]
    y = point[1] - window_origin[1]
    return x - radius, y - radius, x + radius, y + radius
