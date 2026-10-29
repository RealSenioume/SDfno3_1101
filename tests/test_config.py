"""Tests for configuration loading, repair and persistence.

Run with ``python -m unittest discover -s tests`` (stdlib only) or with pytest.
"""

from __future__ import annotations

import itertools
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lolping.config import (  # noqa: E402 - after the path bootstrap
    DEFAULT_SECTORS,
    SECTOR_COUNT,
    Config,
    app_data_dir,
    log_path,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CASE_IDS = itertools.count()
_TEMP_ROOT: Path | None = None


def _temp_root() -> Path:
    """Return a writable scratch root, preferring the system temp directory.

    Some sandboxes make the system TEMP directory unwritable, and others make the
    project directory read-only; the first candidate that actually accepts a
    write wins. Verified by writing a probe file rather than trusting ``mkdir``.
    """
    global _TEMP_ROOT
    if _TEMP_ROOT is not None:
        return _TEMP_ROOT

    candidates = [
        Path(tempfile.gettempdir()) / "lolping-tests",
        _PROJECT_ROOT / ".testtmp",
        Path.cwd() / ".testtmp",
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError:
            continue
        _TEMP_ROOT = candidate
        return candidate

    raise unittest.SkipTest("no writable temporary directory is available")


def _make_temp_dir() -> Path:
    """Create a unique scratch directory with plain ``makedirs``.

    ``tempfile.mkdtemp`` produces directories that restrictive Windows sandboxes
    refuse to write into, so the name is generated here instead.
    """
    path = _temp_root() / f"case-{os.getpid()}-{next(_CASE_IDS)}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class TestDefaults(unittest.TestCase):
    def test_defaults_are_consistent(self) -> None:
        config = Config()
        self.assertEqual(config.trigger_modifiers, ["alt"])
        self.assertEqual(config.trigger_mouse_button, "left")
        self.assertEqual(config.sector_count, SECTOR_COUNT)
        self.assertEqual(len(config.sectors), SECTOR_COUNT)
        self.assertEqual(config.sectors[0], "On My Way")
        self.assertEqual(config.sectors, list(DEFAULT_SECTORS))
        self.assertTrue(5 <= config.dead_zone < config.wheel_radius)

    def test_sector_six_matches_the_reference_wheel(self) -> None:
        # The League wheel has Danger at 12 o'clock; the prototype had Retreat.
        self.assertEqual(Config().sectors[6], "Danger")
        self.assertEqual(Config().sector_icons[6], "danger")

    def test_old_quit_hotkey_key_migrates_to_toggle(self) -> None:
        # 0.3.2 and earlier called this setting quit_hotkey; an existing config
        # must keep its shortcut after the rename.
        config = Config.from_dict({"quit_hotkey": "alt+f4"})
        self.assertEqual(config.toggle_hotkey, "alt+f4")

    def test_open_settings_on_start_defaults_on(self) -> None:
        self.assertTrue(Config().open_settings_on_start)
        self.assertFalse(
            Config.from_dict({"open_settings_on_start": False}).open_settings_on_start
        )

    def test_click_places_ping_defaults_on_and_round_trips(self) -> None:
        self.assertTrue(Config().click_places_ping)
        config = Config(click_places_ping=False)
        self.assertFalse(Config.from_dict(config.to_dict()).click_places_ping)
        self.assertTrue(Config.from_dict({"click_places_ping": "yes"}).click_places_ping)

    def test_paths_live_under_one_directory(self) -> None:
        root = _make_temp_dir()
        previous = os.environ.get("APPDATA")
        os.environ["APPDATA"] = str(root)
        try:
            directory = app_data_dir()
            self.assertTrue(directory.exists())
            self.assertEqual(directory.parent, root)
            self.assertEqual(log_path().parent, directory)
        finally:
            if previous is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = previous
            shutil.rmtree(root, ignore_errors=True)


class TestFromDict(unittest.TestCase):
    def test_round_trips_through_dict(self) -> None:
        config = Config()
        self.assertEqual(Config.from_dict(config.to_dict()), config)

    def test_ignores_unknown_keys(self) -> None:
        config = Config.from_dict({"nonsense": 1, "wheel_radius": 150})
        self.assertEqual(config.wheel_radius, 150)

    def test_non_dict_input(self) -> None:
        for payload in (None, [1, 2, 3], "nope"):
            with self.subTest(payload=payload):
                self.assertEqual(Config.from_dict(payload), Config())

    def test_clamps_numbers(self) -> None:
        config = Config.from_dict(
            {"wheel_radius": 10_000, "dead_zone": -5, "animation_tau": 9}
        )
        self.assertEqual(config.wheel_radius, 400)
        self.assertEqual(config.dead_zone, 5)
        self.assertEqual(config.animation_tau, 0.5)

    def test_dead_zone_never_exceeds_the_wheel(self) -> None:
        config = Config.from_dict({"wheel_radius": 80, "dead_zone": 400})
        self.assertEqual(config.dead_zone, 60)  # wheel_radius - 20

    def test_rejects_booleans_as_numbers(self) -> None:
        config = Config.from_dict({"wheel_radius": True, "mark_duration_ms": False})
        self.assertEqual(config.wheel_radius, Config().wheel_radius)
        self.assertEqual(config.mark_duration_ms, Config().mark_duration_ms)

    def test_repairs_empty_modifier_list(self) -> None:
        self.assertEqual(Config.from_dict({"trigger_modifiers": []}).trigger_modifiers, ["alt"])

    def test_filters_unknown_modifiers_and_deduplicates(self) -> None:
        config = Config.from_dict({"trigger_modifiers": ["ALT", "bogus", "alt", "ctrl"]})
        self.assertEqual(config.trigger_modifiers, ["alt", "ctrl"])

    def test_unknown_mouse_button(self) -> None:
        self.assertEqual(
            Config.from_dict({"trigger_mouse_button": "wheel"}).trigger_mouse_button, "left"
        )
        self.assertEqual(
            Config.from_dict({"trigger_mouse_button": "RIGHT"}).trigger_mouse_button, "right"
        )

    def test_sector_list_is_padded_and_truncated(self) -> None:
        short = Config.from_dict({"sectors": ["A", "B"]})
        self.assertEqual(len(short.sectors), SECTOR_COUNT)
        self.assertEqual(short.sectors[:2], ["A", "B"])

        long = Config.from_dict({"sectors": [f"S{i}" for i in range(20)]})
        self.assertEqual(len(long.sectors), SECTOR_COUNT)

    def test_sector_entries_are_cleaned(self) -> None:
        config = Config.from_dict({"sectors": ["", "  ", 42, "Valid"]})
        self.assertEqual(len(config.sectors), SECTOR_COUNT)
        self.assertEqual(config.sectors[0], "Valid")
        self.assertTrue(all(name.strip() for name in config.sectors))

    def test_theme_and_pause_hotkey_fallbacks(self) -> None:
        config = Config.from_dict({"theme": "neon", "toggle_hotkey": "nothing"})
        self.assertEqual(config.theme, "gold")
        self.assertEqual(config.toggle_hotkey, "ctrl+shift+q")

    def test_pause_hotkey_is_normalised(self) -> None:
        config = Config.from_dict({"toggle_hotkey": " Ctrl + Shift + Q "})
        self.assertEqual(config.toggle_hotkey, "ctrl+shift+q")

    def test_flags_require_real_booleans(self) -> None:
        config = Config.from_dict({"sound_enabled": "yes", "show_labels": 0})
        self.assertFalse(config.sound_enabled)
        self.assertTrue(config.show_labels)


class TestPersistence(unittest.TestCase):
    def setUp(self) -> None:
        self.root = _make_temp_dir()

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_save_then_load(self) -> None:
        target = self.root / "nested" / "config.json"
        config = Config(wheel_radius=180, sectors=["A"] * 8, theme="blue")
        written = config.save(target)
        self.assertEqual(written, target)
        self.assertTrue(target.exists())
        self.assertEqual(Config.load(target), config)

    def test_save_is_atomic_and_leaves_no_temp_file(self) -> None:
        target = self.root / "config.json"
        Config().save(target)
        Config().save(target)
        self.assertEqual([path.name for path in self.root.iterdir()], ["config.json"])

    def test_missing_file_gives_defaults(self) -> None:
        self.assertEqual(Config.load(self.root / "absent.json"), Config())

    def test_corrupt_file_gives_defaults(self) -> None:
        target = self.root / "config.json"
        target.write_text("{not json", encoding="utf-8")
        self.assertEqual(Config.load(target), Config())

    def test_json_list_gives_defaults(self) -> None:
        target = self.root / "config.json"
        target.write_text(json.dumps([1, 2]), encoding="utf-8")
        self.assertEqual(Config.load(target), Config())

    def test_partial_file_keeps_defaults_for_missing_fields(self) -> None:
        target = self.root / "config.json"
        target.write_text(json.dumps({"wheel_radius": 200}), encoding="utf-8")
        config = Config.load(target)
        self.assertEqual(config.wheel_radius, 200)
        self.assertEqual(config.theme, "gold")

    def test_unreadable_file_falls_back_to_defaults(self) -> None:
        target = self.root / "config.json"
        target.write_text("{}", encoding="utf-8")
        with mock.patch.object(
            Path, "read_text", side_effect=PermissionError("denied")
        ):
            self.assertEqual(Config.load(target), Config())


if __name__ == "__main__":
    unittest.main()
