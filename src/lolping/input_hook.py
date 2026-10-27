"""Global input capture.

A ``pynput`` listener thread owns the OS hooks; it must never touch widgets, so
every reaction is turned into a Qt signal on :class:`InputBridge`. Because the
bridge object lives in the GUI thread, Qt delivers the emissions as queued
events and the hook thread stays free.

Limitations that are part of the design (see docs/03-design.md):

* ``pynput`` can observe but cannot *suppress* input, so the click that opens the
  wheel still reaches the window underneath as well.
* Windows hides input from processes at a higher integrity level, so a target
  running as administrator cannot be sensed while this app runs normally.
"""

from __future__ import annotations

import logging
import threading
import time

from PyQt5.QtCore import QObject, pyqtSignal

from .config import Config
from .hotkeys import MODIFIER_NAMES, parse_hotkey

log = logging.getLogger(__name__)

try:
    from pynput import keyboard, mouse
except ImportError:  # pragma: no cover - reported by the app at start-up
    keyboard = None  # type: ignore[assignment]
    mouse = None  # type: ignore[assignment]

__all__ = ["InputBridge", "InputHook"]


class InputBridge(QObject):
    """Signals emitted from the hook thread, consumed in the GUI thread."""

    trigger_down = pyqtSignal(int, int, float)  # x, y, perf_counter timestamp
    trigger_up = pyqtSignal(float)  # perf_counter timestamp
    cancel = pyqtSignal()  # Esc pressed
    other_click = pyqtSignal(int, int)  # right/middle click while the wheel is open
    quit_requested = pyqtSignal()  # configured quit hotkey
    health_changed = pyqtSignal(bool)  # hook listeners alive?


# --------------------------------------------------------------------- mappings
def _build_map() -> tuple[dict[object, str], dict[str, object]]:
    if keyboard is None:  # pragma: no cover
        return {}, {}

    modifiers: dict[object, str] = {}
    for attr, token in (
        ("alt_l", "alt"),
        ("alt_r", "alt"),
        ("alt_gr", "alt"),
        ("ctrl_l", "ctrl"),
        ("ctrl_r", "ctrl"),
        ("shift", "shift"),
        ("shift_l", "shift"),
        ("shift_r", "shift"),
        ("cmd", "win"),
        ("cmd_l", "win"),
        ("cmd_r", "win"),
    ):
        key = getattr(keyboard.Key, attr, None)
        if key is not None:
            modifiers[key] = token

    named: dict[object, str] = {}
    for attr in (
        "space",
        "tab",
        "enter",
        "esc",
        "backspace",
        "delete",
        "insert",
        "home",
        "end",
        "page_up",
        "page_down",
        "up",
        "down",
        "left",
        "right",
        "print_screen",
        "pause",
        "caps_lock",
    ):
        key = getattr(keyboard.Key, attr, None)
        if key is not None:
            named[key] = attr.replace("page_up", "pageup").replace("page_down", "pagedown")
    for index in range(1, 13):
        key = getattr(keyboard.Key, f"f{index}", None)
        if key is not None:
            named[key] = f"f{index}"

    return modifiers, named


_MODIFIER_KEYS, _NAMED_KEYS = _build_map()
_ALIAS = {
    "pageup": "pageup",
    "pagedown": "pagedown",
    "printscreen": "printscreen",
    "capslock": "capslock",
    "escape": "esc",
    "return": "enter",
    "page_up": "pageup",
    "page_down": "pagedown",
}


def _keyboard_token(key: object) -> str | None:
    """Normalise a pynput key into the vocabulary used by hotkeys.py."""
    if keyboard is None:  # pragma: no cover
        return None

    # KeyCode is checked before the dict lookups: its __hash__/__eq__ raise on a
    # None virtual key, so a KeyCode must never be used as a dict key.
    if isinstance(key, keyboard.KeyCode):
        vk = getattr(key, "vk", None)
        # With Ctrl held pynput reports a control character, so the virtual key
        # code is the reliable source of the letter/digit.
        if isinstance(vk, int):
            if 65 <= vk <= 90:
                return chr(vk).lower()
            if 48 <= vk <= 57:
                return chr(vk)
        char = getattr(key, "char", None)
        if isinstance(char, str) and len(char) == 1 and char.isprintable():
            lowered = char.lower()
            return _ALIAS.get(lowered, lowered)
        return None

    token = _MODIFIER_KEYS.get(key)
    if token is not None:
        return token
    token = _NAMED_KEYS.get(key)
    if token is not None:
        return token
    return None


def _mouse_button(name: str):
    if mouse is None:  # pragma: no cover
        return None
    mapping = {
        "left": mouse.Button.left,
        "right": mouse.Button.right,
        "middle": mouse.Button.middle,
    }
    for extra in ("x1", "x2"):
        button = getattr(mouse.Button, extra, None)
        if button is not None:
            mapping[extra] = button
    return mapping.get(name, mouse.Button.left)


# ------------------------------------------------------------------------ hook
class _State:
    """Mutable state shared between the pynput callbacks and the supervisor."""

    def __init__(self, config: Config) -> None:
        self.lock = threading.Lock()
        self.pressed: set[str] = set()
        self.modifiers: set[str] = set()
        self.required_modifiers: frozenset[str] = frozenset(config.trigger_modifiers)
        self.trigger_button = _mouse_button(config.trigger_mouse_button)
        self.quit_keys: frozenset[str] = frozenset()
        self.wheel_open = False
        self.down_at = 0.0
        self.update_hotkeys(config)

    def update_hotkeys(self, config: Config) -> None:
        try:
            self.quit_keys = parse_hotkey(config.quit_hotkey)
        except ValueError:
            log.warning("invalid quit hotkey %r, using Ctrl+Shift+Q", config.quit_hotkey)
            self.quit_keys = parse_hotkey("ctrl+shift+q")
        self.required_modifiers = frozenset(config.trigger_modifiers)
        self.trigger_button = _mouse_button(config.trigger_mouse_button)


class InputHook:
    """Owns the two pynput listeners and keeps them alive."""

    def __init__(self, config: Config, bridge: InputBridge) -> None:
        self._bridge = bridge
        self._state = _State(config)
        self._keyboard_listener = None
        self._mouse_listener = None
        self._supervisor: threading.Thread | None = None
        self._stop = threading.Event()

    # ------------------------------------------------------------------ public
    def start(self) -> None:
        if keyboard is None or mouse is None:  # pragma: no cover
            raise RuntimeError("pynput is not installed")
        self._stop.clear()
        self._start_listeners()
        self._supervisor = threading.Thread(
            target=self._supervise, name="lolping-hook-supervisor", daemon=True
        )
        self._supervisor.start()

    def stop(self) -> None:
        self._stop.set()
        self._stop_listeners()
        supervisor = self._supervisor
        self._supervisor = None
        if supervisor is not None and supervisor.is_alive():
            supervisor.join(timeout=1.0)

    def rebind(self, config: Config) -> None:
        with self._state.lock:
            self._state.update_hotkeys(config)

    @property
    def healthy(self) -> bool:
        return self._listeners_alive()

    @property
    def wheel_open(self) -> bool:
        """Whether a gesture is in progress (the mouse guard needs this)."""
        with self._state.lock:
            return self._state.wheel_open

    # ----------------------------------------------------------------- private
    def _listeners_alive(self) -> bool:
        keyboard_ok = self._keyboard_listener is not None and self._keyboard_listener.is_alive()
        mouse_ok = self._mouse_listener is not None and self._mouse_listener.is_alive()
        return bool(keyboard_ok and mouse_ok)

    def _start_listeners(self) -> None:
        # pynput blocks in the constructor when it fails to install a hook, so run
        # the construction and start in a short-lived helper is not needed: the
        # exceptions surface immediately on Windows.
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._keyboard_listener.start()
        self._mouse_listener = mouse.Listener(on_click=self._on_click)
        self._mouse_listener.start()
        deadline = time.perf_counter() + 1.0
        while time.perf_counter() < deadline:
            if self._listeners_alive():
                break
            time.sleep(0.02)
        self._bridge.health_changed.emit(self._listeners_alive())
        log.info("input hook started (healthy=%s)", self._listeners_alive())

    def _stop_listeners(self) -> None:
        for listener in (self._keyboard_listener, self._mouse_listener):
            if listener is None:
                continue
            try:
                listener.stop()
            except Exception:  # pragma: no cover - already dead
                log.debug("listener stop failed", exc_info=True)
        self._keyboard_listener = None
        self._mouse_listener = None

    def _supervise(self) -> None:
        """Restart dead listeners; a silently lost hook is the worst failure mode."""
        while not self._stop.wait(1.0):
            if self._listeners_alive():
                continue
            log.error("input hook died, restarting")
            try:
                self._stop_listeners()
                self._start_listeners()
            except Exception:
                log.exception("cannot restart the input hook")
            finally:
                self._bridge.health_changed.emit(self._listeners_alive())

    # -------------------------------------------------------------- callbacks
    def _on_press(self, key) -> None:
        try:
            token = _keyboard_token(key)
            if token is None:
                return
            emit_cancel = False
            emit_quit = False
            with self._state.lock:
                already = token in self._state.pressed
                self._state.pressed.add(token)
                if token in MODIFIER_NAMES:
                    self._state.modifiers.add(token)
                if token == "esc":
                    # Esc ends the gesture outright: the wheel is already closed
                    # in the GUI, so the following mouse-up must not commit.
                    emit_cancel = True
                    self._state.wheel_open = False
                keys = self._state.quit_keys
                if keys and not already and keys <= self._state.pressed:
                    if token not in MODIFIER_NAMES:
                        emit_quit = True
            if emit_quit:
                log.info("quit hotkey pressed")
                self._bridge.quit_requested.emit()
                return
            if emit_cancel:
                self._bridge.cancel.emit()
        except Exception:  # pragma: no cover - a callback must never raise
            log.exception("keyboard press handler failed")

    def _on_release(self, key) -> None:
        try:
            token = _keyboard_token(key)
            if token is None:
                return
            with self._state.lock:
                self._state.pressed.discard(token)
                if token in MODIFIER_NAMES:
                    self._state.modifiers.discard(token)
        except Exception:  # pragma: no cover
            log.exception("keyboard release handler failed")

    def _on_click(self, x, y, button, pressed) -> None:
        try:
            now = time.perf_counter()
            emit_down = False
            emit_up = False
            emit_other = False
            with self._state.lock:
                is_trigger = button == self._state.trigger_button
                modifiers_ok = self._state.required_modifiers <= self._state.modifiers
                if pressed:
                    if is_trigger and modifiers_ok and not self._state.wheel_open:
                        self._state.wheel_open = True
                        self._state.down_at = now
                        emit_down = True
                    elif self._state.wheel_open and not is_trigger:
                        self._state.wheel_open = False
                        emit_other = True
                else:
                    if self._state.wheel_open and is_trigger:
                        self._state.wheel_open = False
                        emit_up = True
            if emit_down:
                self._bridge.trigger_down.emit(int(x), int(y), now)
            elif emit_other:
                self._bridge.other_click.emit(int(x), int(y))
            elif emit_up:
                self._bridge.trigger_up.emit(now)
        except Exception:  # pragma: no cover
            log.exception("mouse handler failed")
