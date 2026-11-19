"""Narrow ctypes bindings for the Windows APIs used by the reveal effect."""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

from .controller import WindowTarget
from .geometry import aperture_bounds
from .hold import any_ctrl_pressed

if sys.platform != "win32":
    raise RuntimeError("The window reveal backend is only available on Windows.")

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

HWND = wintypes.HWND
HRGN = wintypes.HANDLE
HGDIOBJ = wintypes.HANDLE

GA_ROOT = 2
RGN_DIFF = 4
RGN_COPY = 5
ERROR = 0
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
GW_HWNDPREV = 3
GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
HWND_TOP = 0
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_NOOWNERZORDER = 0x0200
SWP_NOSENDCHANGING = 0x0400
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000
EXCLUDED_CLASSES = {
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow",
}


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


def _declare(dll: ctypes.WinDLL, name: str, restype: object, *argtypes: object) -> None:
    function = getattr(dll, name)
    function.restype = restype
    function.argtypes = list(argtypes)


_declare(
    user32,
    "SetProcessDpiAwarenessContext",
    wintypes.BOOL,
    ctypes.c_void_p,
)
_declare(user32, "GetCursorPos", wintypes.BOOL, ctypes.POINTER(POINT))
_declare(user32, "WindowFromPoint", HWND, POINT)
_declare(user32, "GetAncestor", HWND, HWND, wintypes.UINT)
_declare(user32, "IsWindow", wintypes.BOOL, HWND)
_declare(user32, "IsWindowVisible", wintypes.BOOL, HWND)
_declare(user32, "IsIconic", wintypes.BOOL, HWND)
_declare(user32, "GetWindowRect", wintypes.BOOL, HWND, ctypes.POINTER(RECT))
_declare(user32, "GetWindowThreadProcessId", wintypes.DWORD, HWND, ctypes.POINTER(wintypes.DWORD))
_declare(user32, "GetClassNameW", ctypes.c_int, HWND, wintypes.LPWSTR, ctypes.c_int)
_declare(user32, "SetWindowRgn", ctypes.c_int, HWND, HRGN, wintypes.BOOL)
_declare(user32, "GetWindow", HWND, HWND, wintypes.UINT)
_declare(user32, "GetAsyncKeyState", ctypes.c_short, ctypes.c_int)
_declare(
    user32,
    "SetWindowPos",
    wintypes.BOOL,
    HWND,
    HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
)
_get_window_long_ptr = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
_get_window_long_ptr.restype = ctypes.c_ssize_t
_get_window_long_ptr.argtypes = [HWND, ctypes.c_int]
_set_window_long_ptr = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
_set_window_long_ptr.restype = ctypes.c_ssize_t
_set_window_long_ptr.argtypes = [HWND, ctypes.c_int, ctypes.c_ssize_t]
_declare(gdi32, "CreateRectRgn", HRGN, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int)
_declare(gdi32, "CreateEllipticRgn", HRGN, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int)
_declare(gdi32, "CombineRgn", ctypes.c_int, HRGN, HRGN, HRGN, ctypes.c_int)
_declare(user32, "GetWindowRgn", ctypes.c_int, HWND, HRGN)
_declare(gdi32, "DeleteObject", wintypes.BOOL, HGDIOBJ)


def set_per_monitor_dpi_awareness() -> None:
    """Request physical-pixel coordinates before any Qt windows are created."""
    # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 is the pseudo-handle -4.
    if not user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
        error = ctypes.get_last_error()
        if error not in (0, 5):  # Access denied means awareness was already established.
            message = ctypes.FormatError(error).strip()
            raise OSError(error, f"Could not set per-monitor DPI awareness: {message}")


def _last_error(action: str) -> OSError:
    error = ctypes.get_last_error()
    return OSError(error, f"{action} failed: {ctypes.FormatError(error).strip()}")


def _set_window_pos(hwnd: int, insert_after: int | HWND) -> None:
    insert_handle = insert_after if isinstance(insert_after, HWND) else HWND(insert_after)
    flags = (
        SWP_NOMOVE
        | SWP_NOSIZE
        | SWP_NOACTIVATE
        | SWP_NOOWNERZORDER
        | SWP_NOSENDCHANGING
    )
    if not user32.SetWindowPos(HWND(hwnd), insert_handle, 0, 0, 0, 0, flags):
        raise _last_error("SetWindowPos")


def is_ctrl_pressed() -> bool:
    """Return whether either physical Ctrl key is currently held."""
    left_state = int(user32.GetAsyncKeyState(VK_LCONTROL))
    right_state = int(user32.GetAsyncKeyState(VK_RCONTROL))
    return any_ctrl_pressed(left_state, right_state)


def _window_identity(hwnd: int) -> tuple[int, int] | None:
    """Pair process/thread IDs with HWNDs to guard against handle reuse."""
    if not hwnd or not user32.IsWindow(HWND(hwnd)):
        return None
    process_id = wintypes.DWORD()
    thread_id = user32.GetWindowThreadProcessId(HWND(hwnd), ctypes.byref(process_id))
    if not thread_id or not process_id.value:
        return None
    return int(process_id.value), int(thread_id)


def _class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    length = user32.GetClassNameW(HWND(hwnd), buffer, len(buffer))
    return buffer.value if length else ""


class RegionSnapshot:
    """Owns a target's original region and temporary z-order state."""

    def __init__(
        self,
        region: int | None,
        original_topmost: bool,
        above_hwnd: int | None,
        above_identity: tuple[int, int] | None,
    ) -> None:
        self.region = region
        self.original_topmost = original_topmost
        self.above_hwnd = above_hwnd
        self.above_identity = above_identity

    def close(self) -> None:
        """Free our saved copy; SetWindowRgn receives separate owned copies."""
        if self.region:
            gdi32.DeleteObject(HGDIOBJ(self.region))
            self.region = None


class Win32Backend:
    """Window discovery, region mutation, and global input state operations."""

    def __init__(self, excluded_hwnds: set[int] | None = None) -> None:
        self.excluded_hwnds = excluded_hwnds or set()
        self._own_process_id = os.getpid()

    @staticmethod
    def cursor_position() -> tuple[int, int]:
        point = POINT()
        if not user32.GetCursorPos(ctypes.byref(point)):
            raise _last_error("GetCursorPos")
        return int(point.x), int(point.y)

    def target_at(self, point: tuple[int, int]) -> WindowTarget | None:
        """Resolve the cursor's top-level window, excluding our own UI and shell."""
        hwnd = user32.WindowFromPoint(POINT(*point))
        if not hwnd:
            return None
        # Promote child controls to the top-level window before changing its region.
        hwnd = user32.GetAncestor(hwnd, GA_ROOT) or hwnd
        handle = int(hwnd)
        identity = _window_identity(handle)
        if (
            identity is None
            or handle in self.excluded_hwnds
            or identity[0] == self._own_process_id
            or not user32.IsWindowVisible(HWND(handle))
            or user32.IsIconic(HWND(handle))
            or _class_name(handle) in EXCLUDED_CLASSES
        ):
            return None

        rect = RECT()
        if not user32.GetWindowRect(HWND(handle), ctypes.byref(rect)):
            return None
        if rect.right <= rect.left or rect.bottom <= rect.top:
            return None
        process_id, thread_id = identity
        return WindowTarget(
            handle,
            process_id,
            thread_id,
            (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)),
        )

    @staticmethod
    def refresh_target(target: WindowTarget) -> WindowTarget | None:
        identity = _window_identity(target.hwnd)
        if identity != (target.process_id, target.thread_id):
            return None
        if not user32.IsWindowVisible(HWND(target.hwnd)) or user32.IsIconic(HWND(target.hwnd)):
            return None
        rect = RECT()
        if not user32.GetWindowRect(HWND(target.hwnd), ctypes.byref(rect)):
            return None
        if rect.right <= rect.left or rect.bottom <= rect.top:
            return None
        return WindowTarget(
            target.hwnd,
            target.process_id,
            target.thread_id,
            (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)),
        )

    @staticmethod
    def capture_region(target: WindowTarget) -> RegionSnapshot:
        """Save region and same-band z-order context before mutating the window."""
        if _window_identity(target.hwnd) != (target.process_id, target.thread_id):
            raise OSError("The target window is no longer available.")
        ex_style = _get_window_long_ptr(HWND(target.hwnd), GWL_EXSTYLE)
        above = user32.GetWindow(HWND(target.hwnd), GW_HWNDPREV)
        above_hwnd = int(above) if above else None
        above_identity = _window_identity(above_hwnd) if above_hwnd else None
        if above_hwnd and above_identity:
            above_style = _get_window_long_ptr(HWND(above_hwnd), GWL_EXSTYLE)
            if bool(above_style & WS_EX_TOPMOST) != bool(ex_style & WS_EX_TOPMOST):
                above_hwnd = None
                above_identity = None
        region = gdi32.CreateRectRgn(0, 0, 0, 0)
        if not region:
            raise _last_error("CreateRectRgn")
        # ERROR plus a zero last-error means the window has no custom region to save.
        ctypes.set_last_error(0)
        result = user32.GetWindowRgn(HWND(target.hwnd), HRGN(region))
        if result == ERROR:
            error = ctypes.get_last_error()
            gdi32.DeleteObject(HGDIOBJ(region))
            if error != 0:
                raise OSError(error, f"GetWindowRgn failed: {ctypes.FormatError(error).strip()}")
            region_value = None
        else:
            region_value = int(region)
        try:
            return RegionSnapshot(
                region_value,
                bool(ex_style & WS_EX_TOPMOST),
                above_hwnd,
                above_identity,
            )
        except Exception:
            if region_value:
                gdi32.DeleteObject(HGDIOBJ(region_value))
            raise

    @staticmethod
    def _create_aperture_region(
        target: WindowTarget,
        snapshot: RegionSnapshot,
        point: tuple[int, int],
        radius: int,
    ) -> int:
        left, top, right, bottom = target.rect
        width, height = right - left, bottom - top
        # Windows reports no custom region as NULL; start from the full window in that case.
        base = (
            gdi32.CreateRectRgn(0, 0, width, height)
            if snapshot.region is None
            else gdi32.CreateRectRgn(0, 0, 0, 0)
        )
        if not base:
            raise _last_error("CreateRectRgn")
        if snapshot.region is not None:
            copied = gdi32.CombineRgn(
                HRGN(base), HRGN(snapshot.region), HRGN(snapshot.region), RGN_COPY
            )
            if copied == ERROR:
                gdi32.DeleteObject(HGDIOBJ(base))
                raise _last_error("CopyWindowRegion")

        # Translate the physical screen-space cursor into this window's region coordinates.
        hole_left, hole_top, hole_right, hole_bottom = aperture_bounds(
            point, radius, (left, top)
        )
        hole = gdi32.CreateEllipticRgn(hole_left, hole_top, hole_right, hole_bottom)
        if not hole:
            gdi32.DeleteObject(HGDIOBJ(base))
            raise _last_error("CreateEllipticRgn")
        result = gdi32.CombineRgn(HRGN(base), HRGN(base), HRGN(hole), RGN_DIFF)
        gdi32.DeleteObject(HGDIOBJ(hole))
        if result == ERROR:
            gdi32.DeleteObject(HGDIOBJ(base))
            raise _last_error("CombineRgn")
        return int(base)

    @classmethod
    def apply_aperture(
        cls,
        target: WindowTarget,
        snapshot: RegionSnapshot,
        point: tuple[int, int],
        radius: int,
    ) -> None:
        if _window_identity(target.hwnd) != (target.process_id, target.thread_id):
            raise OSError("The target window is no longer available.")
        region = cls._create_aperture_region(target, snapshot, point, radius)
        if not user32.SetWindowRgn(HWND(target.hwnd), HRGN(region), True):
            gdi32.DeleteObject(HGDIOBJ(region))
            raise _last_error("SetWindowRgn")
        # On success Windows owns the region handle.

    @staticmethod
    def restore_region(target: WindowTarget, snapshot: RegionSnapshot) -> None:
        """Restore a copy of the saved region, then best-effort original z-order."""
        if _window_identity(target.hwnd) != (target.process_id, target.thread_id):
            return
        region = None
        if snapshot.region is not None:
            # SetWindowRgn transfers ownership, so keep the snapshot and pass Windows a copy.
            region = gdi32.CreateRectRgn(0, 0, 0, 0)
            if not region:
                raise _last_error("CreateRectRgn")
            if gdi32.CombineRgn(
                HRGN(region), HRGN(snapshot.region), HRGN(snapshot.region), RGN_COPY
            ) == ERROR:
                gdi32.DeleteObject(HGDIOBJ(region))
                raise _last_error("CopyWindowRegion")
        if not user32.SetWindowRgn(HWND(target.hwnd), HRGN(region) if region else None, True):
            if region:
                gdi32.DeleteObject(HGDIOBJ(region))
            raise _last_error("SetWindowRgn")
        # Windows owns the copied region on success; None clears our custom region.
        Win32Backend._restore_z_order(target, snapshot)

    @staticmethod
    def keep_target_front(target: WindowTarget, snapshot: RegionSnapshot) -> None:
        if _window_identity(target.hwnd) != (target.process_id, target.thread_id):
            return
        # Keep the target above newly activated windows in its original z-order band.
        insert_after = (
            HWND_TOPMOST if snapshot.original_topmost else HWND_TOP
        )
        # Preserve foreground focus and avoid moving/resizing the target while reordering it.
        if not user32.SetWindowPos(
            HWND(target.hwnd),
            insert_after,
            0,
            0,
            0,
            0,
            SWP_NOMOVE
            | SWP_NOSIZE
            | SWP_NOACTIVATE
            | SWP_NOOWNERZORDER
            | SWP_NOSENDCHANGING,
        ):
            raise _last_error("Maintain target z-order")

    @staticmethod
    def _restore_z_order(target: WindowTarget, snapshot: RegionSnapshot) -> None:
        """Use a still-valid same-band anchor, falling back to the original band top."""
        anchor = snapshot.above_hwnd
        if (
            anchor
            and _window_identity(anchor) == snapshot.above_identity
            and bool(_get_window_long_ptr(HWND(anchor), GWL_EXSTYLE) & WS_EX_TOPMOST)
            == snapshot.original_topmost
        ):
            _set_window_pos(target.hwnd, anchor)
            return

        _set_window_pos(
            target.hwnd,
            HWND_TOPMOST if snapshot.original_topmost else HWND_TOP,
        )

    @staticmethod
    def release_snapshot(snapshot: RegionSnapshot) -> None:
        """Free the saved GDI region once the controller has restored the target."""
        snapshot.close()

    @staticmethod
    def configure_click_through(hwnd: int) -> None:
        """Make the rim non-activating and pass pointer input through to windows below."""
        style = _get_window_long_ptr(HWND(hwnd), GWL_EXSTYLE)
        _set_window_long_ptr(
            HWND(hwnd),
            GWL_EXSTYLE,
            style | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE,
        )
        if not user32.SetWindowPos(
            HWND(hwnd),
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED,
        ):
            raise _last_error("Configure overlay click-through")
