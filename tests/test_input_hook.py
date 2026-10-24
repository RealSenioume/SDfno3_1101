"""Tests for the input state machine.

The OS-level hooks cannot be exercised from a test process (and Windows hides
injected input from sandboxed processes), so the callbacks are driven directly.
That is exactly where the decisions live: the pynput thread only forwards to
``_on_press`` / ``_on_click``.

No ``QApplication`` is created: Qt signals fired on the same thread reach a
directly connected Python callable without an event loop.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lolping.config import Config  # noqa: E402
from lolping.input_hook import InputBridge, InputHook  # noqa: E402

try:  # pragma: no cover - pynput is a runtime dependency
    from pynput import keyboard, mouse
except ImportError:  # pragma: no cover
    keyboard = None  # type: ignore[assignment]
    mouse = None  # type: ignore[assignment]


@unittest.skipIf(keyboard is None or mouse is None, "pynput is not installed")
class HookTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config()
        self.bridge = InputBridge()
        self.hook = InputHook(self.config, self.bridge)
        self.events: list[tuple] = []
        self.bridge.trigger_down.connect(
            lambda x, y, t: self.events.append(("down", x, y))
        )
        self.bridge.trigger_up.connect(lambda t: self.events.append(("up",)))
        self.bridge.cancel.connect(lambda: self.events.append(("cancel",)))
        self.bridge.other_click.connect(
            lambda x, y: self.events.append(("other", x, y))
        )
        self.bridge.quit_requested.connect(lambda: self.events.append(("quit",)))

    def tearDown(self) -> None:
        # The listeners were never started, so only the state needs dropping.
        self.hook.stop()

    def tap_alt(self) -> None:
        self.hook._on_press(keyboard.Key.alt_l)

    def click(self, pressed: bool, x: int = 500, y: int = 400, button="left") -> None:
        self.hook._on_click(x, y, getattr(mouse.Button, button), pressed)

    def kinds(self) -> list[str]:
        return [event[0] for event in self.events]


class TestTriggerGesture(HookTestBase):
    def test_alt_plus_left_opens_the_wheel(self) -> None:
        self.tap_alt()
        self.click(pressed=True)
        self.assertEqual(self.kinds(), ["down"])
        self.assertEqual(self.events[0][1:], (500, 400))

    def test_release_commits(self) -> None:
        self.tap_alt()
        self.click(pressed=True)
        self.click(pressed=False)
        self.assertEqual(self.kinds(), ["down", "up"])

    def test_click_without_modifier_does_nothing(self) -> None:
        self.click(pressed=True)
        self.assertEqual(self.kinds(), [])

    def test_wrong_modifier_combination_does_nothing(self) -> None:
        self.config.trigger_modifiers = ["ctrl", "shift"]
        self.hook.rebind(self.config)
        self.tap_alt()
        self.click(pressed=True)
        self.assertEqual(self.kinds(), [])

    def test_extra_modifiers_are_allowed(self) -> None:
        self.tap_alt()
        self.hook._on_press(keyboard.Key.shift_l)
        self.click(pressed=True)
        self.assertEqual(self.kinds(), ["down"])

    def test_releasing_the_modifier_first_still_commits(self) -> None:
        self.tap_alt()
        self.click(pressed=True)
        self.hook._on_release(keyboard.Key.alt_l)
        self.click(pressed=False)
        self.assertEqual(self.kinds(), ["down", "up"])

    def test_second_press_while_open_is_ignored(self) -> None:
        self.tap_alt()
        self.click(pressed=True)
        self.click(pressed=True)
        self.assertEqual(self.kinds(), ["down"])

    def test_release_without_open_does_not_emit(self) -> None:
        self.click(pressed=False)
        self.assertEqual(self.kinds(), [])


class TestCancelPaths(HookTestBase):
    def test_escape_cancels(self) -> None:
        self.tap_alt()
        self.click(pressed=True)
        self.hook._on_press(keyboard.Key.esc)
        self.assertEqual(self.kinds(), ["down", "cancel"])

    def test_right_click_cancels_and_suppresses_commit(self) -> None:
        self.tap_alt()
        self.click(pressed=True)
        self.click(pressed=True, button="right")
        self.click(pressed=False)  # left release after a cancel must be silent
        self.assertEqual(self.kinds(), ["down", "other"])

    def test_cancel_then_trigger_again_works(self) -> None:
        self.tap_alt()
        self.click(pressed=True)
        self.hook._on_press(keyboard.Key.esc)
        self.click(pressed=False)  # releasing after Esc must stay silent
        self.click(pressed=True)
        self.assertEqual(self.kinds(), ["down", "cancel", "down"])


class TestQuitHotkey(HookTestBase):
    def test_ctrl_shift_q_quits(self) -> None:
        self.hook._on_press(keyboard.Key.ctrl_l)
        self.hook._on_press(keyboard.Key.shift_l)
        self.hook._on_press(keyboard.KeyCode.from_vk(0x51))  # Q
        self.assertEqual(self.kinds(), ["quit"])

    def test_q_alone_does_not_quit(self) -> None:
        self.hook._on_press(keyboard.KeyCode.from_vk(0x51))
        self.assertEqual(self.kinds(), [])

    def test_partial_combo_does_not_quit(self) -> None:
        self.hook._on_press(keyboard.KeyCode.from_vk(0x11))  # ctrl
        self.hook._on_press(keyboard.KeyCode.from_vk(0x51))  # Q
        self.assertEqual(self.kinds(), [])

    def test_custom_quit_hotkey(self) -> None:
        self.config.quit_hotkey = "alt+f4"
        self.hook.rebind(self.config)
        self.hook._on_press(keyboard.Key.alt_l)
        self.hook._on_press(keyboard.Key.f4)
        self.assertEqual(self.kinds(), ["quit"])

    def test_letter_uses_virtual_key_when_ctrl_is_held(self) -> None:
        # With Ctrl down pynput may report a control character; the virtual key
        # code still identifies Q, which is what makes the hotkey usable.
        self.hook._on_press(keyboard.Key.ctrl_l)
        self.hook._on_press(keyboard.Key.shift_l)
        self.hook._on_press(keyboard.KeyCode(vk=0x51, char="\x11"))
        self.assertEqual(self.kinds(), ["quit"])


class TestKeyTokens(HookTestBase):
    def test_modifier_tokens(self) -> None:
        from lolping.input_hook import _keyboard_token

        self.assertEqual(_keyboard_token(keyboard.Key.alt_l), "alt")
        self.assertEqual(_keyboard_token(keyboard.Key.ctrl_r), "ctrl")
        self.assertEqual(_keyboard_token(keyboard.Key.shift), "shift")
        self.assertEqual(_keyboard_token(keyboard.Key.cmd_l), "win")

    def test_named_tokens(self) -> None:
        from lolping.input_hook import _keyboard_token

        self.assertEqual(_keyboard_token(keyboard.Key.esc), "esc")
        self.assertEqual(_keyboard_token(keyboard.Key.page_up), "pageup")
        self.assertEqual(_keyboard_token(keyboard.Key.f7), "f7")

    def test_letter_and_digit_tokens(self) -> None:
        from lolping.input_hook import _keyboard_token

        self.assertEqual(_keyboard_token(keyboard.KeyCode.from_char("a")), "a")
        self.assertEqual(_keyboard_token(keyboard.KeyCode.from_char("Q")), "q")
        self.assertEqual(_keyboard_token(keyboard.KeyCode.from_vk(0x31)), "1")

    def test_unmappable_key_is_ignored(self) -> None:
        from lolping.input_hook import _keyboard_token

        self.assertIsNone(_keyboard_token(keyboard.KeyCode(vk=None, char=None)))


if __name__ == "__main__":
    unittest.main()
