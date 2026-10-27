"""Tests for the native mouse guard.

The Win32 part cannot be exercised in a test process (a low-level hook needs a
real message loop and real input), so the decision rules - the part that is easy
to get wrong and dangerous to get wrong - are tested as a pure function. A final
group checks that installing and removing the hook does not raise, and that a
guard with no Win32 support degrades to doing nothing.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lolping import mouse_guard  # noqa: E402
from lolping.config import Config  # noqa: E402
from lolping.mouse_guard import EVENTS, MouseGuard, should_suppress  # noqa: E402


class TestDecisionRules(unittest.TestCase):
    def suppress(self, event: str, **overrides) -> bool:
        kwargs = {
            "required_modifiers": ["alt"],
            "held_modifiers": [],
            "wheel_open": False,
            "armed": True,
            "paused": False,
        }
        kwargs.update(overrides)
        return should_suppress(event, **kwargs)

    def test_every_event_name_is_covered(self) -> None:
        for event in EVENTS:
            with self.subTest(event=event):
                self.assertIsInstance(self.suppress(event), bool)

    def test_left_press_is_withheld_when_the_modifier_is_held(self) -> None:
        self.assertTrue(self.suppress("left_down", held_modifiers=["alt"]))

    def test_left_release_is_withheld_when_the_modifier_is_held(self) -> None:
        self.assertTrue(self.suppress("left_up", held_modifiers=["alt"]))

    def test_plain_left_click_passes_through(self) -> None:
        self.assertFalse(self.suppress("left_down"))
        self.assertFalse(self.suppress("left_up"))

    def test_extra_modifiers_do_not_matter(self) -> None:
        self.assertTrue(
            self.suppress("left_down", held_modifiers=["alt", "shift", "ctrl"])
        )

    def test_wrong_modifier_combination_passes_through(self) -> None:
        self.assertFalse(
            self.suppress(
                "left_down",
                required_modifiers=["ctrl", "shift"],
                held_modifiers=["ctrl"],
            )
        )

    def test_multiple_required_modifiers_all_have_to_be_held(self) -> None:
        self.assertTrue(
            self.suppress(
                "left_down",
                required_modifiers=["ctrl", "shift"],
                held_modifiers=["ctrl", "shift"],
            )
        )

    def test_all_buttons_are_withheld_while_the_wheel_is_open(self) -> None:
        for event in EVENTS:
            with self.subTest(event=event):
                self.assertTrue(self.suppress(event, wheel_open=True))

    def test_right_click_passes_through_when_no_gesture_is_active(self) -> None:
        self.assertFalse(self.suppress("right_down", held_modifiers=["alt"]))
        self.assertFalse(self.suppress("middle_down"))

    def test_paused_guard_never_withholds(self) -> None:
        for event in EVENTS:
            with self.subTest(event=event):
                self.assertFalse(
                    self.suppress(
                        event, held_modifiers=["alt"], wheel_open=True, paused=True
                    )
                )

    def test_disarmed_guard_never_withholds(self) -> None:
        self.assertFalse(
            self.suppress("left_down", held_modifiers=["alt"], armed=False)
        )


class TestGuardLifecycle(unittest.TestCase):
    def _guard(self, config: Config | None = None) -> MouseGuard:
        config = config or Config()
        return MouseGuard(
            config_provider=lambda: config,
            paused_provider=lambda: False,
            wheel_open_provider=lambda: False,
        )

    def test_config_default_enables_suppression(self) -> None:
        self.assertTrue(Config().suppress_trigger_gesture)

    def test_config_round_trips_the_flag(self) -> None:
        config = Config(suppress_trigger_gesture=False)
        self.assertFalse(Config.from_dict(config.to_dict()).suppress_trigger_gesture)

    def test_start_stop_does_not_raise(self) -> None:
        guard = self._guard()
        try:
            started = guard.start()
            # On a real Windows session this installs; in a restricted process it
            # may refuse. Either way it must not raise and stop() must be safe.
            self.assertIsInstance(started, bool)
        finally:
            guard.stop()
            guard.stop()  # idempotent

    def test_unavailable_platform_degrades_quietly(self) -> None:
        original = mouse_guard._AVAILABLE
        mouse_guard._AVAILABLE = False
        try:
            guard = self._guard()
            self.assertFalse(guard.available)
            self.assertFalse(guard.start())
            guard.stop()
        finally:
            mouse_guard._AVAILABLE = original

    def test_disabled_config_still_installs_but_decides_not_to_withhold(self) -> None:
        # The flag is checked per event, so toggling it in Settings takes effect
        # without a restart; the hook itself stays installed.
        guard = self._guard(Config(suppress_trigger_gesture=False))
        try:
            guard.start()
            self.assertFalse(
                guard._decide("left_down")  # noqa: SLF001 - decision under test
            )
        finally:
            guard.stop()


if __name__ == "__main__":
    unittest.main()
