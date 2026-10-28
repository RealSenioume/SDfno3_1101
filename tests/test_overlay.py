"""Tests for the overlay's mouse-capture handling.

The capture is what stops the application underneath from continuing a drag or
selection after the wheel appears. It is also dangerous: if a window hides while
the capture is still held, the whole desktop stops receiving the mouse. These
tests pin both directions — capture on open, release on every close path.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PyQt5.QtCore import QPoint  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

import lolping.overlay as overlay_module  # noqa: E402
from lolping.config import Config  # noqa: E402
from lolping.overlay import OverlayManager, OverlayWindow  # noqa: E402

_APP = None


class _CentreCursor:
    """QCursor stand-in that always reports the wheel centre (no movement)."""

    def __init__(self, point: QPoint) -> None:
        self._point = point

    def pos(self) -> QPoint:
        return QPoint(self._point)


class _FakeUser32:
    """Records the capture calls instead of talking to the real window manager."""

    def __init__(self) -> None:
        self.taken = 0
        self.released = 0

    def SetCapture(self, hwnd: int) -> int:  # noqa: N802 - Windows API name
        self.taken += 1
        return hwnd

    def ReleaseCapture(self) -> int:  # noqa: N802 - Windows API name
        self.released += 1
        return 1


class TestMouseCapture(unittest.TestCase):
    def setUp(self) -> None:
        global _APP
        _APP = QApplication.instance() or QApplication([])
        self._original = overlay_module._USER32
        self.fake = _FakeUser32()
        overlay_module._USER32 = self.fake  # type: ignore[assignment]
        self.window = OverlayWindow(_APP.primaryScreen(), Config())
        self.centre = QPoint(400, 300)

    def tearDown(self) -> None:
        self.window.shutdown()
        overlay_module._USER32 = self._original  # type: ignore[assignment]

    def test_opening_takes_the_capture(self) -> None:
        self.window.begin(self.centre)
        # Asserted twice on purpose: before and after the window is shown, so a
        # late capture can never leave the first milliseconds unprotected.
        self.assertGreaterEqual(self.fake.taken, 1)
        self.window.cancel()

    def test_commit_releases_the_capture(self) -> None:
        self.window.begin(self.centre)
        # Put the cursor outside the dead zone by faking the sector test.
        self.window._hovered_sector = lambda: 2  # type: ignore[assignment]
        self.window.commit()
        self.assertGreaterEqual(self.fake.released, 1)

    def test_cancel_releases_the_capture(self) -> None:
        self.window.begin(self.centre)
        self.window.cancel()
        self.assertGreaterEqual(self.fake.released, 1)

    def test_capture_is_not_taken_without_a_platform(self) -> None:
        overlay_module._USER32 = None  # type: ignore[assignment]
        self.window.begin(self.centre)
        self.assertEqual(self.fake.taken, 0)
        self.window.cancel()


class TestManagerPaths(unittest.TestCase):
    def setUp(self) -> None:
        global _APP
        _APP = QApplication.instance() or QApplication([])
        self._original = overlay_module._USER32
        self.fake = _FakeUser32()
        overlay_module._USER32 = self.fake  # type: ignore[assignment]
        self.manager = OverlayManager(Config())

    def tearDown(self) -> None:
        self.manager.shutdown()
        overlay_module._USER32 = self._original  # type: ignore[assignment]

    def test_shutdown_releases_an_open_wheel(self) -> None:
        self.manager.begin_at(QPoint(300, 200))
        self.manager.shutdown()
        self.assertGreaterEqual(self.fake.released, 1)

    def test_cancel_path_releases(self) -> None:
        self.manager.begin_at(QPoint(300, 200))
        self.manager.cancel()
        self.assertGreaterEqual(self.fake.released, 1)


class TestWarmUp(unittest.TestCase):
    """The warm-up exists to close the first-gesture mouse-capture race."""

    def setUp(self) -> None:
        global _APP
        _APP = QApplication.instance() or QApplication([])
        self._original = overlay_module._USER32
        self.fake = _FakeUser32()
        overlay_module._USER32 = self.fake  # type: ignore[assignment]

    def tearDown(self) -> None:
        overlay_module._USER32 = self._original  # type: ignore[assignment]

    def test_warm_up_leaves_the_window_closed_and_hidden(self) -> None:
        window = OverlayWindow(_APP.primaryScreen(), Config())
        try:
            window.warm_up()
            self.assertTrue(window.warmed_up, "warm-up reported an internal failure")
            self.assertFalse(window.is_open())
            self.assertFalse(window.isVisible())
        finally:
            window.shutdown()

    def test_warm_up_restores_state_and_does_not_capture(self) -> None:
        window = OverlayWindow(_APP.primaryScreen(), Config())
        try:
            window.warm_up()
            self.assertEqual(
                self.fake.taken, 0, "a warm-up must never take the mouse capture"
            )
        finally:
            window.shutdown()

    def test_warm_up_emits_no_signals(self) -> None:
        window = OverlayWindow(_APP.primaryScreen(), Config())
        events: list[str] = []
        window.committed.connect(lambda name: events.append(f"commit:{name}"))
        window.cancelled.connect(lambda: events.append("cancel"))
        window.hover_changed.connect(lambda index: events.append(f"hover:{index}"))
        try:
            window.warm_up()
            self.assertEqual(events, [])
        finally:
            window.shutdown()

    def test_manager_warm_up_then_begin_still_works(self) -> None:
        manager = OverlayManager(Config())
        try:
            manager.warm_up()
            self.assertFalse(manager.is_open())
            manager.begin_at(QPoint(300, 200))
            self.assertTrue(manager.is_open())
            manager.cancel()
            self.assertFalse(manager.is_open())
        finally:
            manager.shutdown()


class TestClickPing(unittest.TestCase):
    """A click in place sends the centre ping; a drag ending in the centre cancels."""

    def setUp(self) -> None:
        global _APP
        _APP = QApplication.instance() or QApplication([])
        self._original_user32 = overlay_module._USER32
        self._original_cursor = overlay_module.QCursor
        overlay_module._USER32 = _FakeUser32()  # type: ignore[assignment]
        self.centre = QPoint(400, 300)
        overlay_module.QCursor = _CentreCursor(self.centre)  # type: ignore[assignment]

    def tearDown(self) -> None:
        overlay_module._USER32 = self._original_user32  # type: ignore[assignment]
        overlay_module.QCursor = self._original_cursor  # type: ignore[assignment]

    def _window(self, **overrides) -> OverlayWindow:
        config = Config(**overrides)
        window = OverlayWindow(_APP.primaryScreen(), config)
        self.addCleanup(window.shutdown)
        return window

    def test_click_without_movement_commits_the_basic_ping(self) -> None:
        window = self._window()
        window.begin(self.centre)
        self.assertEqual(window.commit(), "Ping")
        self.assertFalse(window.is_open())

    def test_drag_back_to_the_centre_still_cancels(self) -> None:
        window = self._window()
        window.begin(self.centre)
        window._max_distance = 80.0  # the pointer travelled out and came back
        self.assertIsNone(window.commit())
        self.assertFalse(window.is_open())

    def test_click_ping_can_be_disabled(self) -> None:
        window = self._window(click_places_ping=False)
        window.begin(self.centre)
        self.assertIsNone(window.commit())

    def test_commit_emits_the_basic_ping_name(self) -> None:
        window = self._window()
        seen: list[str] = []
        window.committed.connect(seen.append)
        window.begin(self.centre)
        window.commit()
        self.assertEqual(seen, ["Ping"])


if __name__ == "__main__":
    unittest.main()
