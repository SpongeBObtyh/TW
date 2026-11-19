"""Platform-independent state machine for the circular reveal effect."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class WindowTarget:
    hwnd: int
    process_id: int
    thread_id: int
    rect: tuple[int, int, int, int]


class WindowBackend(Protocol):
    def cursor_position(self) -> tuple[int, int]: ...

    def target_at(self, point: tuple[int, int]) -> WindowTarget | None: ...

    def refresh_target(self, target: WindowTarget) -> WindowTarget | None: ...

    def capture_region(self, target: WindowTarget) -> object: ...

    def apply_aperture(
        self,
        target: WindowTarget,
        snapshot: object,
        point: tuple[int, int],
        radius: int,
    ) -> None: ...

    def restore_region(self, target: WindowTarget, snapshot: object) -> None: ...

    def release_snapshot(self, snapshot: object) -> None: ...

    def keep_target_front(self, target: WindowTarget, snapshot: object) -> None: ...


class RevealController:
    """Tracks one window at a time and restores its original region on release."""

    def __init__(self, backend: WindowBackend, radius: int = 120) -> None:
        self.backend = backend
        self.radius = max(1, int(radius))
        self.enabled = False
        self.target: WindowTarget | None = None
        self._snapshot: object | None = None
        self._last_point: tuple[int, int] | None = None
        self._last_rect: tuple[int, int, int, int] | None = None
        self.last_error: str | None = None

    def enable(self) -> None:
        self.enabled = True
        self.last_error = None
        self.tick()

    def disable(self) -> None:
        self.enabled = False
        self._last_point = None
        self._release_target()

    def set_radius(self, radius: int) -> None:
        radius = max(1, int(radius))
        if radius != self.radius:
            self.radius = radius
            # tick() uses this sentinel to reapply even when the cursor has not moved.
            self._last_point = None

    def tick(self) -> None:
        """Refresh the locked window, or restore it before looking for another target."""
        if not self.enabled:
            if self.target is not None:
                self._release_target()
            return

        try:
            point = self.backend.cursor_position()
            if self.target is not None:
                refreshed = self.backend.refresh_target(self.target)
                if refreshed is None:
                    if not self._release_target():
                        return
                else:
                    self.target = refreshed
                    if self._contains(refreshed.rect, point):
                        # Keep the selected window stable while the pointer stays inside it.
                        self.backend.keep_target_front(refreshed, self._snapshot)
                        if point != self._last_point or refreshed.rect != self._last_rect:
                            self._apply(point)
                        return
                    # Restore before hit-testing again; otherwise the modified region can
                    # affect which window WindowFromPoint considers beneath the cursor.
                    if not self._release_target():
                        return

            candidate = self.backend.target_at(point)
            if candidate is not None:
                self._acquire(candidate, point)
        except Exception as exc:
            error = str(exc)
            self.last_error = error
            if self.target is not None and self._release_target():
                self.last_error = error

    @property
    def aperture_point(self) -> tuple[int, int] | None:
        """Return the last successfully applied center for the independent ring overlay."""
        return self._last_point if self.target is not None else None

    def close(self) -> None:
        """Best-effort cleanup for application shutdown."""
        self.enabled = False
        self._last_point = None
        if self.target is not None:
            self._release_target()

    @staticmethod
    def _contains(rect: tuple[int, int, int, int], point: tuple[int, int]) -> bool:
        left, top, right, bottom = rect
        x, y = point
        return left <= x < right and top <= y < bottom

    def _acquire(self, target: WindowTarget, point: tuple[int, int]) -> None:
        # Capture before either changing the region or z-order so both can be restored.
        snapshot = self.backend.capture_region(target)
        self.target = target
        self._snapshot = snapshot
        self._last_point = None
        try:
            self.backend.keep_target_front(target, snapshot)
            self._apply(point)
            self.last_error = None
        except Exception as exc:
            error = str(exc)
            restored = self._release_target()
            if restored:
                self.last_error = error

    def _apply(self, point: tuple[int, int]) -> None:
        assert self.target is not None and self._snapshot is not None
        self.backend.apply_aperture(self.target, self._snapshot, point, self.radius)
        self._last_point = point
        self._last_rect = self.target.rect

    def _release_target(self) -> bool:
        if self.target is None:
            return True
        target, snapshot = self.target, self._snapshot
        try:
            if snapshot is not None:
                self.backend.restore_region(target, snapshot)
        except Exception as exc:
            # Retain target and snapshot: a later timer tick can retry the restoration.
            self.enabled = False
            self.last_error = f"Could not restore window: {exc}"
            return False

        self._forget_target()
        return True

    def _forget_target(self) -> None:
        snapshot = self._snapshot
        self.target = None
        self._snapshot = None
        self._last_point = None
        self._last_rect = None
        self.last_error = None
        if snapshot is not None:
            # The saved native region is only safe to free after restoration succeeded.
            try:
                self.backend.release_snapshot(snapshot)
            except Exception as exc:
                self.enabled = False
                self.last_error = f"Could not release saved window region: {exc}"
