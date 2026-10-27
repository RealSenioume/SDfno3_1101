"""Tests for the vector icon engine.

Qt needs a display for pixmap work, so the offscreen platform is forced before
the first import. Every test here must pass without a visible desktop.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PyQt5.QtCore import QRectF  # noqa: E402
from PyQt5.QtGui import QColor, QImage, QPainter  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from lolping import assets  # noqa: E402
from lolping.config import DEFAULT_SECTOR_ICONS  # noqa: E402

_APP = None


def setUpModule() -> None:  # noqa: N802 - unittest hook
    global _APP
    _APP = QApplication.instance() or QApplication([])


class TestRegistry(unittest.TestCase):
    def test_ids_are_unique_and_non_empty(self) -> None:
        self.assertGreaterEqual(len(assets.ICON_IDS), 8)
        self.assertEqual(len(set(assets.ICON_IDS)), len(assets.ICON_IDS))

    def test_default_sector_icons_exist(self) -> None:
        self.assertEqual(len(assets.DEFAULT_ICON_FOR_SECTOR), 8)
        for icon_id in assets.DEFAULT_ICON_FOR_SECTOR:
            self.assertIn(icon_id, assets.ICON_IDS)

    def test_config_defaults_match_the_registry(self) -> None:
        self.assertEqual(tuple(DEFAULT_SECTOR_ICONS), assets.DEFAULT_ICON_FOR_SECTOR)


class TestResolve(unittest.TestCase):
    def test_resolves_list_entry(self) -> None:
        icons = ["danger"] * 8
        self.assertEqual(assets.resolve_icon(icons, 3), "danger")

    def test_unknown_id_falls_back_to_sector_default(self) -> None:
        self.assertEqual(assets.resolve_icon(["bogus"] * 8, 2), "assist")

    def test_short_list_falls_back(self) -> None:
        self.assertEqual(assets.resolve_icon(["danger"], 5), "enemy_vision")

    def test_none_uses_defaults(self) -> None:
        self.assertEqual(assets.resolve_icon(None, 0), "on_my_way")


class TestDrawing(unittest.TestCase):
    def _paint(self, icon_id: str, size: int = 64) -> QImage:
        image = QImage(size, size, QImage.Format_ARGB32)
        image.fill(QColor(0, 0, 0, 0))
        painter = QPainter(image)
        try:
            assets.draw_icon(painter, icon_id, QRectF(0, 0, size, size), QColor(220, 180, 60))
        finally:
            painter.end()
        return image

    def test_every_icon_paints_something(self) -> None:
        for icon_id in assets.ICON_IDS:
            with self.subTest(icon=icon_id):
                image = self._paint(icon_id)
                opaque = sum(
                    1
                    for y in range(image.height())
                    for x in range(image.width())
                    if image.pixelColor(x, y).alpha() > 0
                )
                # A real glyph covers several hundred pixels at 64x64.
                self.assertGreater(opaque, 50, f"{icon_id} painted almost nothing")

    def test_unknown_icon_still_draws(self) -> None:
        image = self._paint("does_not_exist")
        self.assertGreater(image.pixelColor(32, 32).alpha() + 1, 1)

    def test_zero_size_rect_is_a_no_op(self) -> None:
        image = QImage(8, 8, QImage.Format_ARGB32)
        image.fill(QColor(0, 0, 0, 0))
        painter = QPainter(image)
        try:
            assets.draw_icon(painter, "vision", QRectF(0, 0, 0, 0), QColor("white"))
        finally:
            painter.end()
        self.assertEqual(image.pixelColor(4, 4).alpha(), 0)

    def test_icon_pixmap_is_cached(self) -> None:
        first = assets.icon_pixmap("danger", 32, QColor(255, 255, 255))
        second = assets.icon_pixmap("danger", 32, QColor(255, 255, 255))
        self.assertFalse(first.isNull())
        self.assertIs(first, second)

    def test_clear_caches_drops_pixmaps(self) -> None:
        first = assets.icon_pixmap("vision", 24, QColor(255, 255, 255))
        assets.clear_caches()
        second = assets.icon_pixmap("vision", 24, QColor(255, 255, 255))
        self.assertIsNot(first, second)


class TestUserImages(unittest.TestCase):
    def test_missing_file_returns_none(self) -> None:
        self.assertIsNone(assets.load_pixmap("", 32))
        self.assertIsNone(assets.load_pixmap(str(Path("no-such-file.png")), 32))

    def test_assets_dir_is_below_the_project_root(self) -> None:
        path = assets.assets_dir()
        self.assertEqual(path.name, "icons")
        self.assertEqual(path.parent.name, "assets")


if __name__ == "__main__":
    unittest.main()
