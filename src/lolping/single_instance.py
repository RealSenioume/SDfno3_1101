"""Single-instance guard.

Two overlays on top of each other would fight over the same global hooks, so the
second launch must exit quietly. Implemented with a one-byte OS file lock rather
than a named Qt server: ``msvcrt.locking`` needs no extra Qt module (QtNetwork is
excluded from the frozen build) and the lock is released automatically if the
process dies.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

try:  # pragma: no cover - the project targets Windows
    import msvcrt
except ImportError:  # pragma: no cover
    msvcrt = None  # type: ignore[assignment]

__all__ = ["SingleInstance"]

log = logging.getLogger(__name__)


class SingleInstance:
    """A best-effort, crash-safe single-instance lock."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._handle = None

    def try_acquire(self) -> bool:
        """Return ``True`` if this process is the only instance."""
        if msvcrt is None:  # pragma: no cover - non-Windows developer machine
            return True
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            handle = open(self._path, "a+")  # noqa: SIM115 - kept open on purpose
        except OSError as exc:
            log.warning("cannot open lock file %s: %s", self._path, exc)
            return True  # fail open: running twice is better than not running

        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            handle.close()
            return False

        self._handle = handle
        try:
            handle.seek(0)
            handle.truncate()
            handle.write(str(os.getpid()))
            handle.flush()
        except OSError:
            pass
        return True

    def release(self) -> None:
        """Release the lock. Safe to call twice."""
        handle = self._handle
        self._handle = None
        if handle is None or msvcrt is None:
            return
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        finally:
            try:
                handle.close()
            except OSError:
                pass
