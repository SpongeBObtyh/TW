from __future__ import annotations

from dataclasses import dataclass

from transparent_window.controller import RevealController, WindowTarget


@dataclass
class Snapshot:
    name: str


class FakeBackend:
    def __init__(self) -> None:
        self.point = (50, 50)
        self.candidates: dict[tuple[int, int], WindowTarget | None] = {}
        self.calls: list[tuple] = []
        self.invalid: set[int] = set()
        self.fail_apply = False
        self.fail_restore = False
        self.front_calls: list[int] = []

    def cursor_position(self):
        return self.point

    def target_at(self, point):
        self.calls.append(("target_at", point))
        target = self.candidates.get(point)
        return None if target and target.hwnd in self.invalid else target

    def refresh_target(self, target):
        self.calls.append(("refresh", target.hwnd))
        return None if target.hwnd in self.invalid else target

    def capture_region(self, target):
        snapshot = Snapshot(str(target.hwnd))
        self.calls.append(("capture", target.hwnd, snapshot))
        return snapshot

    def apply_aperture(self, target, snapshot, point, radius):
        self.calls.append(("apply", target.hwnd, point, radius))
        if self.fail_apply:
            raise OSError("apply failed")

    def restore_region(self, target, snapshot):
        self.calls.append(("restore", target.hwnd, snapshot.name))
        if self.fail_restore:
            raise OSError("restore failed")

    def release_snapshot(self, snapshot):
        self.calls.append(("release", snapshot.name))

    def keep_target_front(self, target, snapshot):
        self.front_calls.append(target.hwnd)


def target(hwnd: int, rect=(0, 0, 100, 100)) -> WindowTarget:
    return WindowTarget(hwnd, hwnd + 1000, hwnd + 2000, rect)


def test_enable_tracks_pointer_without_retargeting_inside_locked_window():
    backend = FakeBackend()
    first, behind = target(1), target(2)
    backend.candidates[(50, 50)] = first
    backend.candidates[(60, 50)] = behind
    controller = RevealController(backend, radius=80)

    controller.enable()
    backend.point = (60, 50)
    controller.tick()

    assert controller.target == first
    assert backend.front_calls[-1] == first.hwnd
    assert [call for call in backend.calls if call[0] == "target_at"] == [
        ("target_at", (50, 50))
    ]
    assert backend.calls[-1] == ("apply", 1, (60, 50), 80)


def test_leaving_target_restores_before_selecting_next_target():
    backend = FakeBackend()
    first = target(1, (0, 0, 100, 100))
    second = target(2, (100, 0, 200, 100))
    backend.candidates[(50, 50)] = first
    backend.candidates[(110, 50)] = second
    controller = RevealController(backend)
    controller.enable()
    backend.point = (110, 50)

    controller.tick()

    calls = backend.calls
    restore_index = next(i for i, call in enumerate(calls) if call[0] == "restore")
    lookup_index = max(i for i, call in enumerate(calls) if call[0] == "target_at")
    assert restore_index < lookup_index
    assert controller.target == second


def test_disable_restores_and_releases_snapshot():
    backend = FakeBackend()
    backend.candidates[(50, 50)] = target(1)
    controller = RevealController(backend)
    controller.enable()
    snapshot = controller._snapshot

    controller.disable()

    assert not controller.enabled
    assert controller.target is None
    assert ("restore", 1, snapshot.name) in backend.calls
    assert ("release", snapshot.name) in backend.calls


def test_failed_apply_restores_target_and_reports_error():
    backend = FakeBackend()
    backend.candidates[(50, 50)] = target(1)
    backend.fail_apply = True
    controller = RevealController(backend)

    controller.enable()

    assert controller.target is None
    assert controller.last_error == "apply failed"
    assert any(call[0] == "restore" for call in backend.calls)


def test_failed_restore_keeps_target_for_later_retry():
    backend = FakeBackend()
    backend.candidates[(50, 50)] = target(1)
    controller = RevealController(backend)
    controller.enable()
    backend.fail_restore = True

    controller.disable()

    assert not controller.enabled
    assert controller.target is not None
    assert "Could not restore" in controller.last_error

    backend.fail_restore = False
    controller.tick()
    assert controller.target is None


def test_invalid_target_is_restored_before_forget():
    backend = FakeBackend()
    backend.candidates[(50, 50)] = target(1)
    controller = RevealController(backend)
    controller.enable()
    backend.invalid.add(1)

    controller.tick()

    assert controller.target is None
    assert any(call[0] == "restore" for call in backend.calls)


def test_radius_change_reapplies_at_same_position():
    backend = FakeBackend()
    backend.candidates[(50, 50)] = target(1)
    controller = RevealController(backend)
    controller.enable()
    controller.set_radius(200)
    controller.tick()

    assert backend.calls[-1] == ("apply", 1, (50, 50), 200)

