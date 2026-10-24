"""Tests for hotkey parsing and rendering.

Run with ``python -m unittest discover -s tests`` (stdlib only) or with pytest.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lolping.hotkeys import format_hotkey, is_valid_hotkey, parse_hotkey  # noqa: E402


class TestParse(unittest.TestCase):
    def test_simple_combo(self) -> None:
        self.assertEqual(parse_hotkey("ctrl+shift+q"), frozenset({"ctrl", "shift", "q"}))

    def test_case_and_spacing(self) -> None:
        self.assertEqual(
            parse_hotkey("  Ctrl + Shift + Q  "), frozenset({"ctrl", "shift", "q"})
        )

    def test_aliases(self) -> None:
        self.assertEqual(parse_hotkey("control+option+p"), frozenset({"ctrl", "alt", "p"}))
        self.assertEqual(parse_hotkey("meta+f5"), frozenset({"win", "f5"}))

    def test_win_key(self) -> None:
        self.assertEqual(parse_hotkey("win+space"), frozenset({"win", "space"}))

    def test_modifier_order_does_not_matter(self) -> None:
        self.assertEqual(parse_hotkey("shift+ctrl+a"), parse_hotkey("ctrl+shift+a"))

    def test_requires_a_modifier_by_default(self) -> None:
        with self.assertRaises(ValueError):
            parse_hotkey("q")
        self.assertEqual(parse_hotkey("q", require_modifier=False), frozenset({"q"}))

    def test_rejects_invalid(self) -> None:
        for text in ["", "   ", "+", "ctrl+", "ctrl+shift", "ctrl+a+b", "ctrl+bogus", "ctrl+ctrl+q"]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_hotkey(text)

    def test_rejects_non_string(self) -> None:
        with self.assertRaises(ValueError):
            parse_hotkey(None)  # type: ignore[arg-type]

    def test_named_keys(self) -> None:
        self.assertEqual(parse_hotkey("ctrl+pageup"), frozenset({"ctrl", "pageup"}))
        self.assertEqual(parse_hotkey("alt+esc"), frozenset({"alt", "esc"}))
        self.assertEqual(parse_hotkey("alt+f12"), frozenset({"alt", "f12"}))


class TestFormat(unittest.TestCase):
    def test_canonical_order(self) -> None:
        self.assertEqual(format_hotkey({"q", "shift", "ctrl"}), "Ctrl+Shift+Q")

    def test_all_modifiers(self) -> None:
        self.assertEqual(
            format_hotkey({"win", "shift", "alt", "ctrl", "k"}), "Ctrl+Alt+Shift+Win+K"
        )

    def test_named_key_label(self) -> None:
        self.assertEqual(format_hotkey({"ctrl", "pageup"}), "Ctrl+PageUp")

    def test_round_trip(self) -> None:
        for text in ("ctrl+shift+q", "alt+f4", "win+space"):
            with self.subTest(text=text):
                self.assertEqual(
                    parse_hotkey(format_hotkey(parse_hotkey(text))), parse_hotkey(text)
                )


class TestIsValid(unittest.TestCase):
    def test_matches_parse(self) -> None:
        self.assertTrue(is_valid_hotkey("ctrl+q"))
        self.assertFalse(is_valid_hotkey("q"))
        self.assertFalse(is_valid_hotkey("ctrl+"))


if __name__ == "__main__":
    unittest.main()
