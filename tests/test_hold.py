from __future__ import annotations

from dataclasses import dataclass

from transparent_window.controller import RevealController, WindowTarget
from transparent_window.hold import CtrlHoldBinding, any_ctrl_pressed


@dataclass
class Snapshot:
    name: str


class FakeBackend:
    def __init__(self) -> None:
        self.point = (50, 50)
        self.pressed = False
        self.calls: list[tuple] = []
        self.fail_restore = False

    def cursor_position(self):
        return self.point

    def target_at(self, point):
        self.calls.append(("target_at", point))
        return WindowTarget(1, 2, 3, (0, 0, 100, 100))

    def refresh_target(self, target):
        return target

    def capture_region(self, target):
        self.calls.append(("capture", target.hwnd))
        return Snapshot("saved")

    def apply_aperture(self, target, snapshot, point, radius):
        self.calls.append(("apply", target.hwnd, point, radius))

    def restore_region(self, target, snapshot):
        self.calls.append(("restore", target.hwnd))
        if self.fail_restore:
            raise OSError("restore failed")

    def release_snapshot(self, snapshot):
        self.calls.append(("release", snapshot.name))

    def keep_target_front(self, target, snapshot):
        self.calls.append(("front", target.hwnd))


def test_any_ctrl_pressed_checks_only_key_down_bits():
    assert any_ctrl_pressed(0x8000, 0)
    assert any_ctrl_pressed(0, 0x8000)
    assert not any_ctrl_pressed(0x0001, 0x0001)
    assert not any_ctrl_pressed(0, 0)


def test_ctrl_hold_enables_once_updates_and_restores_on_release():
    backend = FakeBackend()
    controller = RevealController(backend)
    binding = CtrlHoldBinding(controller, lambda: backend.pressed)

    backend.pressed = True
    binding.poll()
    binding.poll()
    assert controller.enabled
    assert len([call for call in backend.calls if call[0] == "capture"]) == 1

    backend.pressed = False
    binding.poll()
    assert not controller.enabled
    assert controller.target is None
    assert ("restore", 1) in backend.calls


def test_ctrl_release_restore_is_retried():
    backend = FakeBackend()
    controller = RevealController(backend)
    binding = CtrlHoldBinding(controller, lambda: backend.pressed)
    backend.pressed = True
    binding.poll()

    backend.pressed = False
    backend.fail_restore = True
    binding.poll()
    assert controller.target is not None

    backend.fail_restore = False
    binding.poll()
    assert controller.target is None


def test_hold_does_not_acquire_without_cursor_target():
    backend = FakeBackend()
    backend.target_at = lambda point: None
    controller = RevealController(backend)
    binding = CtrlHoldBinding(controller, lambda: True)

    binding.poll()

    assert controller.enabled
    assert controller.target is None
