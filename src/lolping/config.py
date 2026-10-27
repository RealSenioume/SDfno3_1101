"""Persistent user configuration for lolping.

The config is a plain JSON file in ``%APPDATA%\\lolping-desktop\\config.json``. Loading
is deliberately forgiving: a missing, truncated or hand-edited file must never
stop the app from starting, it just falls back to the defaults for the broken
fields.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .geometry import clamp

log = logging.getLogger(__name__)

APP_NAME = "lolping-desktop"

MODIFIER_NAMES: tuple[str, ...] = ("ctrl", "alt", "shift", "win")
MOUSE_BUTTONS: tuple[str, ...] = ("left", "right", "middle", "x1", "x2")
THEMES: tuple[str, ...] = ("gold", "blue", "red")

SECTOR_COUNT = 8

# Clockwise from 3 o'clock, matching the original prototype's layout.
DEFAULT_SECTORS: tuple[str, ...] = (
    "On My Way",
    "All-In",
    "Assist Me",
    "Need Vision",
    "Enemy Missing",
    "Enemy Vision",
    "Retreat",
    "Push",
)

#: Vector icon per slice, in the same order as DEFAULT_SECTORS. The ids are
#: resolved by ``lolping.assets``; unknown ids fall back to a generic ring there,
#: so this module stays free of Qt and of the icon registry.
DEFAULT_SECTOR_ICONS: tuple[str, ...] = (
    "on_my_way",
    "all_in",
    "assist",
    "vision",
    "missing",
    "enemy_vision",
    "retreat",
    "push",
)


def app_data_dir() -> Path:
    """Return the per-user data directory, creating it if needed."""
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".config"
    path = root / APP_NAME
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:  # pragma: no cover - only on exotic broken profiles
        log.warning("cannot create %s, falling back to temp dir", path)
        path = Path(tempfile.gettempdir()) / APP_NAME
        path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return app_data_dir() / "config.json"


def log_path() -> Path:
    return app_data_dir() / "pings.jsonl"


def latency_path() -> Path:
    return app_data_dir() / "latency.jsonl"


@dataclass
class Config:
    """User-tunable settings. See ``docs/00-interfaces.md`` section 3."""

    trigger_modifiers: list[str] = field(default_factory=lambda: ["alt"])
    trigger_mouse_button: str = "left"
    wheel_radius: int = 130
    dead_zone: int = 34
    sector_count: int = SECTOR_COUNT
    sectors: list[str] = field(default_factory=lambda: list(DEFAULT_SECTORS))
    animation_tau: float = 0.035
    mark_duration_ms: int = 900
    sound_enabled: bool = False
    quit_hotkey: str = "ctrl+shift+q"
    start_with_windows: bool = False
    show_labels: bool = True
    theme: str = "gold"

    # ---- slice artwork (v0.3) ----
    show_icons: bool = True
    sector_icons: list[str] = field(default_factory=lambda: list(DEFAULT_SECTOR_ICONS))
    sector_images: list[str] = field(default_factory=lambda: [""] * SECTOR_COUNT)
    icon_size: int = 30

    # ---- sound (v0.3) ----
    sound_volume: float = 0.5
    sound_hover_ticks: bool = True
    sound_on_open: bool = True
    sound_on_commit: bool = True
    sound_on_cancel: bool = True

    # ---------------------------------------------------------------- mapping
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> "Config":
        """Build a config from a possibly broken dict, repairing every field."""
        config = cls()
        if not isinstance(data, dict):
            return config

        config.trigger_modifiers = _clean_modifiers(
            data.get("trigger_modifiers"), config.trigger_modifiers
        )
        config.trigger_mouse_button = _choice(
            data.get("trigger_mouse_button"), MOUSE_BUTTONS, config.trigger_mouse_button
        )
        config.wheel_radius = int(
            _number(data.get("wheel_radius"), 60, 400, config.wheel_radius)
        )
        config.dead_zone = int(
            _number(data.get("dead_zone"), 5, config.wheel_radius - 20, config.dead_zone)
        )
        config.sector_count = SECTOR_COUNT
        config.sectors = _clean_sectors(data.get("sectors"), SECTOR_COUNT)
        config.animation_tau = _number(
            data.get("animation_tau"), 0.005, 0.5, config.animation_tau
        )
        config.mark_duration_ms = int(
            _number(data.get("mark_duration_ms"), 300, 4000, config.mark_duration_ms)
        )
        config.sound_enabled = _flag(data.get("sound_enabled"), config.sound_enabled)
        config.quit_hotkey = _hotkey(data.get("quit_hotkey"), config.quit_hotkey)
        config.start_with_windows = _flag(
            data.get("start_with_windows"), config.start_with_windows
        )
        config.show_labels = _flag(data.get("show_labels"), config.show_labels)
        config.theme = _choice(data.get("theme"), THEMES, config.theme)

        config.show_icons = _flag(data.get("show_icons"), config.show_icons)
        config.sector_icons = _clean_icon_ids(
            data.get("sector_icons"), DEFAULT_SECTOR_ICONS, SECTOR_COUNT
        )
        config.sector_images = _clean_paths(data.get("sector_images"), SECTOR_COUNT)
        config.icon_size = int(_number(data.get("icon_size"), 12, 64, config.icon_size))

        config.sound_volume = _number(
            data.get("sound_volume"), 0.0, 1.0, config.sound_volume
        )
        config.sound_hover_ticks = _flag(
            data.get("sound_hover_ticks"), config.sound_hover_ticks
        )
        config.sound_on_open = _flag(data.get("sound_on_open"), config.sound_on_open)
        config.sound_on_commit = _flag(
            data.get("sound_on_commit"), config.sound_on_commit
        )
        config.sound_on_cancel = _flag(
            data.get("sound_on_cancel"), config.sound_on_cancel
        )
        return config

    # ------------------------------------------------------------------- disk
    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        """Load the config; any failure yields the defaults, never an exception."""
        target = Path(path) if path is not None else config_path()
        try:
            raw = target.read_text(encoding="utf-8")
        except FileNotFoundError:
            return cls()
        except OSError as exc:
            log.warning("cannot read %s: %s", target, exc)
            return cls()

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            log.warning("invalid JSON in %s: %s", target, exc)
            return cls()

        try:
            return cls.from_dict(data)
        except Exception:  # pragma: no cover - defensive, from_dict is total
            log.exception("unexpected failure parsing %s", target)
            return cls()

    def save(self, path: Path | None = None) -> Path:
        """Write the config atomically and return the path written."""
        target = Path(path) if path is not None else config_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, target)
        return target


# --------------------------------------------------------------------- helpers
def _number(value: Any, low: float, high: float, fallback: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return fallback
    return clamp(float(value), low, high)


def _flag(value: Any, fallback: bool) -> bool:
    return value if isinstance(value, bool) else fallback


def _choice(value: Any, allowed: tuple[str, ...], fallback: str) -> str:
    if isinstance(value, str) and value.lower() in allowed:
        return value.lower()
    return fallback


def _hotkey(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        text = value.strip().lower().replace(" ", "")
        if "+" in text and all(part for part in text.split("+")):
            return text
    return fallback


def _clean_modifiers(value: Any, fallback: list[str]) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return list(fallback)
    cleaned = [str(item).lower() for item in value if isinstance(item, str)]
    cleaned = [item for item in cleaned if item in MODIFIER_NAMES]
    # De-duplicate while keeping order.
    seen: dict[str, None] = {}
    for item in cleaned:
        seen.setdefault(item, None)
    ordered = list(seen)
    if not ordered:
        # An empty trigger would fire on every click -- never allow that.
        return list(fallback)
    return ordered


def _clean_sectors(value: Any, count: int) -> list[str]:
    names: list[str] = []
    if isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, str) and item.strip():
                names.append(item.strip()[:24])
    names = names[:count]
    while len(names) < count:
        names.append(DEFAULT_SECTORS[len(names) % len(DEFAULT_SECTORS)])
    return names


def _clean_icon_ids(
    value: Any, defaults: tuple[str, ...], count: int
) -> list[str]:
    """Keep well-formed icon ids; unknown ids are left for assets.py to repair."""
    ids: list[str] = []
    if isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, str):
                token = item.strip().lower()
                if token and len(token) <= 32:
                    ids.append(token)
                else:
                    ids.append("")
            else:
                ids.append("")
    ids = ids[:count]
    while len(ids) < count:
        index = len(ids)
        ids.append(defaults[index] if index < len(defaults) else "generic")
    for index, token in enumerate(ids):
        if not token:
            ids[index] = defaults[index] if index < len(defaults) else "generic"
    return ids


def _clean_paths(value: Any, count: int) -> list[str]:
    """Keep image paths as strings; whether a file exists is decided at draw time."""
    paths: list[str] = []
    if isinstance(value, (list, tuple)):
        for item in value:
            paths.append(item.strip()[:260] if isinstance(item, str) else "")
    paths = paths[:count]
    while len(paths) < count:
        paths.append("")
    return paths
