"""Logging bootstrap.

A windowed (``--noconsole``) build has nowhere to print, so everything that
matters goes to a rotating file under ``%APPDATA%\\lolping``. ``--debug`` also
mirrors the log to stderr and to a console window when one exists.
"""

from __future__ import annotations

import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import app_data_dir

__all__ = ["install_excepthook", "log_file", "setup_logging"]

_LOG_NAME = "lolping.log"


def log_file() -> Path:
    return app_data_dir() / _LOG_NAME


def setup_logging(debug: bool = False) -> Path:
    """Configure the root logger and return the log file path."""
    path = log_file()
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    try:
        file_handler = RotatingFileHandler(
            path, maxBytes=512 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:  # pragma: no cover - read-only profile
        pass

    if debug or sys.stderr is not None:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(formatter)
        stream.setLevel(logging.DEBUG if debug else logging.WARNING)
        root.addHandler(stream)

    logging.getLogger("lolping").info("--- lolping starting (debug=%s) ---", debug)
    return path


def install_excepthook() -> None:
    """Log uncaught exceptions instead of dying silently in a windowed build."""

    def _hook(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logging.getLogger("lolping").critical(
            "uncaught exception\n%s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )

    sys.excepthook = _hook
