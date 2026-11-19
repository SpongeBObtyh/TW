"""Press-and-hold input bindings for the reveal controller."""

from __future__ import annotations

from collections.abc import Callable

from .controller import RevealController

KEY_DOWN_MASK = 0x8000


def any_ctrl_pressed(left_state: int, right_state: int) -> bool:
    """Check the high-order key-down bit for either Ctrl key."""
    return bool((left_state | right_state) & KEY_DOWN_MASK)


class CtrlHoldBinding:
    """Drive a reveal controller while a global Ctrl-state reader is held."""

    def __init__(
        self,
        controller: RevealController,
        is_pressed: Callable[[], bool],
    ) -> None:
        self.controller = controller
        self.is_pressed = is_pressed
        self._pressed = False

    def poll(self) -> None:
        """Translate sampled key state into controller transitions and retry cleanup."""
        pressed = bool(self.is_pressed())
        if pressed:
            if self.controller.target is not None and not self.controller.enabled:
                # A failed release disables new reveals but retains the restoration lease.
                self.controller.tick()
            elif not self.controller.enabled:
                self.controller.enable()
            else:
                self.controller.tick()
        elif self._pressed:
            self.controller.disable()
        else:
            # A failed release restoration remains pending for a later poll.
            self.controller.tick()
        self._pressed = pressed
