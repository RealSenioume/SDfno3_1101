"""Start-with-Windows support via the per-user Run registry key.

Only ``HKCU`` is touched, so no administrator rights are needed and turning the
feature off is a plain value delete.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

__all__ = ["VALUE_NAME", "is_enabled", "launch_command", "set_enabled"]

log = logging.getLogger(__name__)

VALUE_NAME = "lolping"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

try:  # pragma: no cover - the project targets Windows
    import winreg
except ImportError:  # pragma: no cover
    winreg = None  # type: ignore[assignment]


def launch_command() -> str:
    """Command line Windows should run at login."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    if pythonw.exists():
        python = pythonw
    return f'"{python}" -m lolping'


def is_enabled() -> bool:
    """Return whether the Run entry exists (any value, not just ours)."""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except FileNotFoundError:
        return False
    except OSError as exc:  # pragma: no cover
        log.warning("cannot read autostart state: %s", exc)
        return False


def set_enabled(enabled: bool) -> bool:
    """Create or remove the Run entry. Returns whether the state matches."""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, launch_command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError as exc:
        log.warning("cannot change autostart: %s", exc)
        return False
