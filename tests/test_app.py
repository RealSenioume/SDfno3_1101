"""Regression tests for the application shell.

Two defects reported from a manual test session are pinned here:

1. A tray **double-click** produced two stacked settings dialogs. Windows sends
   ``Trigger`` before ``DoubleClick``, so both branches opened the modal dialog;
   the first one blocked inside ``exec_()`` while the queued second call opened
   another.
2. (Audio is covered separately in test_sounds.py: playing from memory is not
   allowed asynchronously, so cues are played from generated files.)

The tests drive the slot methods directly; no tray icon, hook or dialog is
actually shown.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon  # noqa: E402

from lolping import app as app_module  # noqa: E402
from lolping.config import Config  # noqa: E402
from lolping.settings_dialog import SettingsDialog  # noqa: E402

_APP = None


class _FakeInstance:
    def __init__(self) -> None:
        self.released = False

    def try_acquire(self) -> bool:  # pragma: no cover - not used here
        return True

    def release(self) -> None:
        self.released = True


class TestSettingsActivation(unittest.TestCase):
    def setUp(self) -> None:
        global _APP
        _APP = QApplication.instance() or QApplication([])
        self.controller = app_module.PingApp(
            _APP, Config(), None, _FakeInstance()  # type: ignore[arg-type]
        )
        self.opened: list[int] = []
        self._original_edit = SettingsDialog.edit

        controller = self.controller

        def fake_edit(config, parent=None):
            self.opened.append(1)
            # Simulate a queued second activation arriving while the first modal
            # dialog is still open: the guard must swallow it.
            controller._open_settings()
            return None

        SettingsDialog.edit = staticmethod(fake_edit)  # type: ignore[assignment]

    def tearDown(self) -> None:
        SettingsDialog.edit = self._original_edit  # type: ignore[assignment]
        self.controller._tray.hide()

    def test_single_click_does_not_open_settings(self) -> None:
        self.controller._on_tray_activated(QSystemTrayIcon.Trigger)
        self.assertEqual(self.opened, [])

    def test_double_click_opens_settings_exactly_once(self) -> None:
        # Windows emits both signals for one double-click.
        self.controller._on_tray_activated(QSystemTrayIcon.Trigger)
        self.controller._on_tray_activated(QSystemTrayIcon.DoubleClick)
        self.assertEqual(len(self.opened), 1)

    def test_reentrant_open_is_ignored(self) -> None:
        self.controller._on_tray_activated(QSystemTrayIcon.DoubleClick)
        self.assertEqual(len(self.opened), 1, "a second dialog must not stack")


class TestCueRouting(unittest.TestCase):
    def setUp(self) -> None:
        global _APP
        _APP = QApplication.instance() or QApplication([])
        self.controller = app_module.PingApp(
            _APP, Config(), None, _FakeInstance()  # type: ignore[arg-type]
        )
        self.played: list[tuple[str, float, int]] = []
        self._original_play = app_module.sounds.play
        app_module.sounds.play = lambda cue, volume=0.5, index=0: self.played.append(
            (cue, volume, index)
        )

    def tearDown(self) -> None:
        app_module.sounds.play = self._original_play
        self.controller._tray.hide()

    def test_sound_disabled_plays_nothing(self) -> None:
        self.controller._config.sound_enabled = False
        self.controller._play("commit", 2)
        self.assertEqual(self.played, [])

    def test_commit_uses_the_slice_index(self) -> None:
        self.controller._config.sound_enabled = True
        self.controller._play("commit", 5)
        self.assertEqual(self.played, [("commit", 0.5, 5)])

    def test_hover_ticks_can_be_switched_off_alone(self) -> None:
        self.controller._config.sound_enabled = True
        self.controller._config.sound_hover_ticks = False
        self.controller._on_hover_changed(3)
        self.assertEqual(self.played, [])
        self.controller._on_hover_changed(-1)  # dead zone is never a cue
        self.assertEqual(self.played, [])

    def test_hover_tick_plays_when_enabled(self) -> None:
        self.controller._config.sound_enabled = True
        self.controller._on_hover_changed(3)
        self.assertEqual(self.played, [("hover", 0.5, 3)])


class TestPauseToggle(unittest.TestCase):
    """The global hotkey flips the paused state, like the tray entry does."""

    def setUp(self) -> None:
        global _APP
        _APP = QApplication.instance() or QApplication([])
        self.controller = app_module.PingApp(
            _APP, Config(), None, _FakeInstance()  # type: ignore[arg-type]
        )

    def tearDown(self) -> None:
        self.controller._tray.hide()

    def test_hotkey_toggles_pause_and_the_menu_text(self) -> None:
        self.assertFalse(self.controller._paused)
        self.controller._toggle_pause()
        self.assertTrue(self.controller._paused)
        self.assertEqual(self.controller._action_pause.text(), "Resume")
        self.controller._toggle_pause()
        self.assertFalse(self.controller._paused)
        self.assertEqual(self.controller._action_pause.text(), "Pause")


if __name__ == "__main__":
    unittest.main()
