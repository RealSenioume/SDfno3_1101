"""Hotkey string parsing shared by the config, the hook and the settings UI.

A hotkey is written as ``"ctrl+shift+q"``: zero or more modifiers plus exactly
one key. Parsing is the only place that knows about spellings, so the hook and
the dialog can stay dumb.
"""

from __future__ import annotations

__all__ = ["MODIFIER_NAMES", "format_hotkey", "is_valid_hotkey", "parse_hotkey"]

MODIFIER_NAMES: tuple[str, ...] = ("ctrl", "alt", "shift", "win")

_ALIASES: dict[str, str] = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "ctl": "ctrl",
    "alt": "alt",
    "option": "alt",
    "opt": "alt",
    "shift": "shift",
    "win": "win",
    "windows": "win",
    "meta": "win",
    "super": "win",
    "cmd": "win",
}

# Keys that are not a single character. Kept small on purpose: the hook maps
# pynput key names onto these tokens.
_NAMED_KEYS = frozenset(
    {
        "space",
        "tab",
        "enter",
        "esc",
        "backspace",
        "delete",
        "insert",
        "home",
        "end",
        "pageup",
        "pagedown",
        "up",
        "down",
        "left",
        "right",
        "printscreen",
        "pause",
        "capslock",
        "f1",
        "f2",
        "f3",
        "f4",
        "f5",
        "f6",
        "f7",
        "f8",
        "f9",
        "f10",
        "f11",
        "f12",
    }
)

_DISPLAY = {
    "pageup": "PageUp",
    "pagedown": "PageDown",
    "printscreen": "PrintScreen",
    "capslock": "CapsLock",
    "backspace": "Backspace",
    "esc": "Esc",
}


def _parse_token(token: str) -> str:
    token = token.strip().lower()
    if not token:
        raise ValueError("empty key in hotkey")
    if token in _ALIASES:
        return _ALIASES[token]
    if len(token) == 1 and (token.isalnum()):
        return token
    if token in _NAMED_KEYS:
        return token
    raise ValueError(f"unsupported key {token!r} in hotkey")


def parse_hotkey(text: str, require_modifier: bool = True) -> frozenset[str]:
    """Parse ``"Ctrl+Shift+Q"`` into ``frozenset({"ctrl", "shift", "q"})``.

    Raises ``ValueError`` for anything ambiguous so the settings dialog can show
    the message instead of silently accepting a broken hotkey.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("hotkey is empty")

    raw_parts = text.split("+")
    parts = [_parse_token(part) for part in raw_parts]

    if len(set(parts)) != len(parts):
        raise ValueError("hotkey contains a duplicate key")

    modifiers = [part for part in parts if part in MODIFIER_NAMES]
    keys = [part for part in parts if part not in MODIFIER_NAMES]

    if len(keys) != 1:
        raise ValueError("hotkey needs exactly one non-modifier key")
    if require_modifier and not modifiers:
        raise ValueError("hotkey needs at least one modifier (Ctrl, Alt, Shift or Win)")

    return frozenset(parts)


def format_hotkey(keys: frozenset[str] | set[str]) -> str:
    """Render a key set in canonical order, e.g. ``"Ctrl+Shift+Q"``."""
    present = {str(key).lower() for key in keys}
    ordered = [name for name in MODIFIER_NAMES if name in present]
    ordered += sorted(key for key in present if key not in MODIFIER_NAMES)
    label = {
        "ctrl": "Ctrl",
        "alt": "Alt",
        "shift": "Shift",
        "win": "Win",
    }
    rendered = []
    for token in ordered:
        if token in label:
            rendered.append(label[token])
        elif token in _DISPLAY:
            rendered.append(_DISPLAY[token])
        elif len(token) == 1:
            rendered.append(token.upper())
        else:
            rendered.append(token.capitalize())
    return "+".join(rendered)


def is_valid_hotkey(text: str) -> bool:
    """Convenience wrapper used by the settings dialog for live validation."""
    try:
        parse_hotkey(text)
    except ValueError:
        return False
    return True
