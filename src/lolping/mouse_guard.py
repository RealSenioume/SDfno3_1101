"""Native mouse-hook guard: withhold the trigger gesture from other windows.

Why this exists
---------------
A global *observer* (``pynput``) cannot stop an event: by the time the wheel is
visible, the window underneath has already received the button-down and - because
the mouse reports at up to 1000 Hz - the first moves as well. Explorer then
starts its rubber-band selection or its OLE drag-and-drop, and neither can be
undone from outside. Taking the mouse capture afterwards only helps when no move
arrives in the few-millisecond gap, which is a coin flip at best.

The reliable fix is to remove the events from the input stream *before* any
window sees them, which is what a ``WH_MOUSE_LL`` hook returning 1 does.

How it is wired
---------------
The guard is installed **before** the ``pynput`` listeners. Windows calls the
most recently installed hook first, so the order is:

``pynput (sees the gesture) -> this guard (withholds it) -> target window``

That is deliberate: the guard must never be the reason the application misses its
own trigger.

What is withheld
----------------
* Left button, while the configured trigger modifiers are held: the press, the
  release and everything between. This is what makes "Alt + drag" invisible to
  the desktop.
* Any mouse button, while the wheel is open: a stray right-click must not open a
  context menu in the middle of a gesture.

Everything else (plain clicks, drags without the modifiers, mouse wheel, movement
when no modifier is held) passes straight through with one ``CallNextHookEx``.

Cost and risks
--------------
While lolping runs and the modifiers are held, **Alt + click is reserved system
wide**: other applications will not see it. That is the price of the technique,
it is what the reference implementation's native helper does too, and it is
exposed as ``Config.suppress_trigger_gesture`` so it can be turned off. The
callback runs on a dedicated thread, does no allocation and no logging on the
pass-through path, and the hook is uninstalled on exit. If it cannot install, the
guard does nothing and the application keeps working.
"""

from __future__ import annotations

import ctypes
import logging
import threading
from collections.abc import Callable, Iterable

from .config import Config

__all__ = ["EVENTS", "MouseGuard", "should_suppress"]

log = logging.getLogger(__name__)

#: Logical event names used by the pure decision function.
EVENTS: tuple[str, ...] = (
    "left_down",
    "left_up",
    "right_down",
    "right_up",
    "middle_down",
    "middle_up",
)

# Win32 constants
_WH_MOUSE_LL = 14
_WM_LBUTTONDOWN = 0x0201
_WM_LBUTTONUP = 0x0202
_WM_RBUTTONDOWN = 0x0204
_WM_RBUTTONUP = 0x0205
_WM_MBUTTONDOWN = 0x0207
_WM_MBUTTONUP = 0x0208
_WM_QUIT = 0x0012

_MESSAGE_NAMES = {
    _WM_LBUTTONDOWN: "left_down",
    _WM_LBUTTONUP: "left_up",
    _WM_RBUTTONDOWN: "right_down",
    _WM_RBUTTONUP: "right_up",
    _WM_MBUTTONDOWN: "middle_down",
    _WM_MBUTTONUP: "middle_up",
}

#: Virtual-key codes for the trigger modifiers.
_VK = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B}

try:  # pragma: no cover - the project targets Windows
    from ctypes import wintypes

    _USER32 = ctypes.WinDLL("user32", use_last_error=True)
    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _HOOKPROC = ctypes.WINFUNCTYPE(
        ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
    )

    _USER32.SetWindowsHookExW.argtypes = [
        ctypes.c_int,
        _HOOKPROC,
        wintypes.HINSTANCE,
        wintypes.DWORD,
    ]
    _USER32.SetWindowsHookExW.restype = ctypes.c_void_p
    _USER32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
    _USER32.UnhookWindowsHookEx.restype = wintypes.BOOL
    _USER32.CallNextHookEx.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    _USER32.CallNextHookEx.restype = ctypes.c_ssize_t
    _USER32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    _USER32.GetAsyncKeyState.restype = ctypes.c_short
    _USER32.PostThreadMessageW.argtypes = [
        wintypes.DWORD,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    _USER32.GetMessageW.argtypes = [
        ctypes.POINTER(wintypes.MSG),
        wintypes.HWND,
        wintypes.UINT,
        wintypes.UINT,
    ]
    _KERNEL32.GetModuleHandleW.restype = wintypes.HMODULE
    _KERNEL32.GetCurrentThreadId.restype = wintypes.DWORD
    _AVAILABLE = True
except (ImportError, AttributeError, OSError):  # pragma: no cover
    _USER32 = None
    _KERNEL32 = None
    _HOOKPROC = None
    _AVAILABLE = False


# --------------------------------------------------------------------------
# Pure decision logic (unit-tested without touching Win32)
# --------------------------------------------------------------------------
def should_suppress(
    event: str,
    *,
    required_modifiers: Iterable[str],
    held_modifiers: Iterable[str],
    wheel_open: bool,
    armed: bool,
    paused: bool,
) -> bool:
    """Decide whether one mouse event must be withheld from other windows."""
    if paused or not armed:
        return False

    if event.startswith("left"):
        if wheel_open:
            return True
        return set(required_modifiers) <= set(held_modifiers)

    # Any other button only matters while a gesture is in progress, so that a
    # stray right-click cannot open a context menu underneath the wheel.
    return wheel_open


# --------------------------------------------------------------------------
# Win32 plumbing
# --------------------------------------------------------------------------
class MouseGuard:
    """Installs a low-level mouse hook on its own thread.

    The three providers are callables, so the guard never has to know about the
    application object: it asks for the current config, whether lolping is
    paused, and whether the wheel is open.
    """

    def __init__(
        self,
        config_provider: Callable[[], Config],
        paused_provider: Callable[[], bool],
        wheel_open_provider: Callable[[], bool],
    ) -> None:
        self._config_provider = config_provider
        self._paused_provider = paused_provider
        self._wheel_open_provider = wheel_open_provider
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._hook = None
        self._proc = None
        self._ready = threading.Event()
        self._running = False
        self._left_down_withheld = False

    # ------------------------------------------------------------------ public
    @property
    def available(self) -> bool:
        return _AVAILABLE

    @property
    def running(self) -> bool:
        return self._running and self._hook is not None

    def start(self) -> bool:
        """Install the hook. Returns whether it is running afterwards."""
        if not _AVAILABLE:
            log.warning("low-level mouse hooks are not available on this platform")
            return False
        if self._thread is not None:
            return self.running

        self._thread = threading.Thread(
            target=self._run, name="lolping-mouse-guard", daemon=True
        )
        self._thread.start()
        self._ready.wait(timeout=2.0)
        if not self.running:
            log.error("the low-level mouse hook did not install")
            return False
        log.info("mouse guard installed (the trigger gesture is withheld while armed)")
        return True

    def stop(self) -> None:
        """Uninstall the hook and stop its thread. Safe to call twice."""
        thread_id = self._thread_id
        thread = self._thread
        self._thread = None
        self._thread_id = None
        if thread_id is not None and _AVAILABLE:
            try:
                _USER32.PostThreadMessageW(thread_id, _WM_QUIT, 0, 0)
            except Exception:  # pragma: no cover
                log.debug("cannot post WM_QUIT to the mouse guard", exc_info=True)
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        self._running = False
        self._left_down_withheld = False

    # ----------------------------------------------------------------- private
    def _run(self) -> None:  # pragma: no cover - requires a message loop
        try:
            self._thread_id = _KERNEL32.GetCurrentThreadId()
            self._proc = _HOOKPROC(self._callback)
            module = _KERNEL32.GetModuleHandleW(None)
            self._hook = _USER32.SetWindowsHookExW(
                _WH_MOUSE_LL, self._proc, module, 0
            )
            if not self._hook:
                log.error("SetWindowsHookExW failed: %s", ctypes.get_last_error())
                return
            self._running = True
            self._ready.set()

            message = wintypes.MSG()
            while _USER32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                _USER32.TranslateMessage(ctypes.byref(message))
                _USER32.DispatchMessageW(ctypes.byref(message))
        except Exception:  # pragma: no cover
            log.exception("mouse guard thread failed")
        finally:
            self._running = False
            self._ready.set()
            if self._hook and _AVAILABLE:
                try:
                    _USER32.UnhookWindowsHookEx(self._hook)
                except Exception:  # pragma: no cover
                    pass
            self._hook = None

    def _callback(self, n_code: int, w_param: int, l_param: int) -> int:  # pragma: no cover
        if n_code < 0:
            return self._call_next(n_code, w_param, l_param)
        try:
            name = _MESSAGE_NAMES.get(int(w_param))
            if name is not None and self._decide(name):
                if name == "left_down":
                    self._left_down_withheld = True
                elif name == "left_up":
                    self._left_down_withheld = False
                return 1  # withhold: no window and no later hook sees this event
        except Exception:
            log.debug("mouse guard callback failed", exc_info=True)
        return self._call_next(n_code, w_param, l_param)

    def _decide(self, event: str) -> bool:
        config = self._config_provider()
        if not getattr(config, "suppress_trigger_gesture", True):
            return False
        if self._left_down_withheld and event == "left_up":
            return True  # never leave a press without its release
        wheel_open = False
        try:
            wheel_open = bool(self._wheel_open_provider())
        except Exception:  # pragma: no cover
            wheel_open = False
        try:
            paused = bool(self._paused_provider())
        except Exception:  # pragma: no cover
            paused = False
        return should_suppress(
            event,
            required_modifiers=config.trigger_modifiers,
            held_modifiers=self._held_modifiers(),
            wheel_open=wheel_open,
            armed=True,
            paused=paused,
        )

    @staticmethod
    def _held_modifiers() -> set[str]:
        held: set[str] = set()
        if not _AVAILABLE:  # pragma: no cover
            return held
        for name, vk in _VK.items():
            try:
                if _USER32.GetAsyncKeyState(vk) & 0x8000:
                    held.add(name)
            except Exception:  # pragma: no cover
                pass
        return held

    @staticmethod
    def _call_next(n_code: int, w_param: int, l_param: int) -> int:  # pragma: no cover
        return _USER32.CallNextHookEx(None, n_code, w_param, l_param)
