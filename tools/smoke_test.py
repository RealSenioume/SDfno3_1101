#!/usr/bin/env python
"""Smoke tests for lolping.

Two checks are provided:

``--self-test`` (default)
    Runs ``python -m lolping --self-test`` in an offscreen Qt platform with
    ``PYTHONPATH`` pointing at ``src``, waits up to 60 seconds for it to
    finish and requires exit code 0 plus ``SELF-TEST OK`` on stdout.

``--live``
    Starts the real GUI (no offscreen platform) for a few seconds, verifies
    that the process stays alive instead of crashing on startup, then shuts
    it down as gently as Windows allows.

Standard library only: this file must run with the plain ``python`` on PATH
even when pytest / PyInstaller are not installed.

Exit code: 0 when the selected check passes, 1 when it fails.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import IO, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC_DIR = REPO_ROOT / "src"
APP_MODULE = "lolping"
SELF_TEST_MARKER = "SELF-TEST OK"


# --------------------------------------------------------------------------- io
def _harden_console() -> None:
    """Avoid UnicodeEncodeError if a path or traceback is not ASCII."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (OSError, ValueError):
                pass


def _child_env(src_dir: Path, *, offscreen: bool) -> dict[str, str]:
    """Environment for the child interpreter.

    PYTHONPATH makes the src layout importable, PYTHONDONTWRITEBYTECODE keeps
    ``__pycache__`` out of the repository (see docs/00-interfaces.md, rule 10)
    and PYTHONUNBUFFERED makes sure a crash log survives an abrupt shutdown.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(src_dir) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    if offscreen:
        env["QT_QPA_PLATFORM"] = "offscreen"
    else:
        env.pop("QT_QPA_PLATFORM", None)
    return env


def _print_output(label: str, text: str, max_lines: int = 30) -> None:
    lines = [line for line in text.splitlines() if line.strip()]
    _print_lines(label, lines, max_lines)


def _print_lines(label: str, lines: Sequence[str], max_lines: int = 30) -> None:
    if not lines:
        return
    print(f"    {label}:")
    for line in lines[:max_lines]:
        print(f"      {line}")
    if len(lines) > max_lines:
        print(f"      ... ({len(lines) - max_lines} more lines)")


def _drain(stream: IO[bytes] | None, sink: list[str]) -> None:
    """Collect a child process stream line by line, so PIPE buffers never fill."""
    if stream is None:
        return
    try:
        for raw in iter(stream.readline, b""):
            sink.append(raw.decode("utf-8", errors="replace").rstrip("\r\n"))
    except (OSError, ValueError):
        pass
    finally:
        try:
            stream.close()
        except OSError:
            pass


# ------------------------------------------------------------------- self-test
def run_self_test(
    python: str,
    src_dir: Path,
    timeout: float,
    *,
    verbose: bool = False,
) -> bool:
    """Run the offscreen ``--self-test`` and report PASS/FAIL."""
    command = [python, "-m", APP_MODULE, "--self-test"]
    print(f"[smoke] self-test: {' '.join(command)}")
    print(f"[smoke]   PYTHONPATH={src_dir}")
    print("[smoke]   QT_QPA_PLATFORM=offscreen")

    env = _child_env(src_dir, offscreen=True)
    try:
        completed = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        print(f"[smoke] FAIL: could not start interpreter {python!r}.")
        return False
    except subprocess.TimeoutExpired:
        print(f"[smoke] FAIL: --self-test did not finish within {timeout:g} s.")
        return False

    ok = completed.returncode == 0 and SELF_TEST_MARKER in completed.stdout
    if ok:
        print(f"[smoke] PASS: --self-test (exit code 0, {SELF_TEST_MARKER!r} on stdout)")
        if verbose:
            _print_output("stdout", completed.stdout)
            _print_output("stderr", completed.stderr)
        return True

    print(
        "[smoke] FAIL: --self-test returned "
        f"exit code {completed.returncode} and stdout "
        f"{'contains' if SELF_TEST_MARKER in completed.stdout else 'does not contain'} "
        f"{SELF_TEST_MARKER!r}."
    )
    _print_output("stdout", completed.stdout)
    _print_output("stderr", completed.stderr)
    return False


# ------------------------------------------------------------------------ live
def _shutdown(process: subprocess.Popen[bytes], grace_seconds: float = 10.0) -> str:
    """Try a graceful shutdown, then fall back to a hard kill.

    On Windows ``taskkill`` without ``/F`` posts WM_CLOSE to the process'
    windows, which lets Qt exit through its normal shutdown path.  Tray-only
    applications may ignore WM_CLOSE, in which case ``taskkill /F`` is used.
    Returns ``"graceful"`` or ``"forced"``.
    """
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid)],
                capture_output=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            process.terminate()
        except OSError:
            pass

    try:
        process.wait(timeout=grace_seconds)
        return "graceful"
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        return "forced"


def run_live(
    python: str,
    src_dir: Path,
    seconds: float,
    *,
    verbose: bool = False,
) -> bool:
    """Start the real GUI and check that it stays alive for ``seconds``."""
    command = [python, "-m", APP_MODULE]
    print(f"[smoke] live: {' '.join(command)}")
    print(f"[smoke]   PYTHONPATH={src_dir}")
    print(f"[smoke]   keeping the GUI alive for {seconds:g} s ...")

    env = _child_env(src_dir, offscreen=False)
    try:
        process = subprocess.Popen(
            command,
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        print(f"[smoke] FAIL: could not start interpreter {python!r}: {exc}")
        return False

    # Drain both pipes in the background: a full pipe would block the child
    # (and make a healthy GUI look frozen).  No temporary files are needed.
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    readers = [
        threading.Thread(target=_drain, args=(process.stdout, stdout_lines), daemon=True),
        threading.Thread(target=_drain, args=(process.stderr, stderr_lines), daemon=True),
    ]
    for reader in readers:
        reader.start()

    early_exit: int | None = None
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        early_exit = process.poll()
        if early_exit is not None:
            break
        time.sleep(0.1)

    if early_exit is not None:
        print(f"[smoke] FAIL: the GUI exited on its own with code {early_exit}.")
        for reader in readers:
            reader.join(timeout=2.0)
        _print_lines("stdout", stdout_lines)
        _print_lines("stderr", stderr_lines)
        return False

    print("[smoke]   GUI is alive, shutting it down ...")
    how = _shutdown(process)
    for reader in readers:
        reader.join(timeout=2.0)

    print(f"[smoke] PASS: --live (GUI survived {seconds:g} s, shutdown was {how})")
    if verbose:
        _print_lines("stdout", stdout_lines)
        _print_lines("stderr", stderr_lines)
    return True


# ------------------------------------------------------------------------ main
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smoke_test.py",
        description="Run lolping smoke tests (offscreen self-test or live GUI check).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="start the real GUI for --live-seconds instead of running --self-test",
    )
    parser.add_argument(
        "--live-seconds",
        type=float,
        default=5.0,
        metavar="SECONDS",
        help="how long the live GUI must stay alive (default: 5)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        metavar="SECONDS",
        help="timeout for --self-test (default: 60)",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        metavar="EXE",
        help="interpreter used to launch lolping (default: this interpreter)",
    )
    parser.add_argument(
        "--src-dir",
        type=Path,
        default=DEFAULT_SRC_DIR,
        metavar="PATH",
        help="directory that contains the lolping package (default: <repo>/src)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="also print the child process output when the test passes",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _harden_console()
    args = _build_parser().parse_args(argv)
    src_dir = args.src_dir.resolve()

    entry_point = src_dir / APP_MODULE / "__main__.py"
    if not entry_point.is_file():
        print(f"[smoke] FAIL: {entry_point} not found.")
        print("[smoke]   The src layout is incomplete; nothing to test yet.")
        return 1

    python = args.python
    if os.path.sep in python or (os.altsep and os.altsep in python):
        resolved = Path(python).expanduser()
        if not resolved.is_file():
            print(f"[smoke] FAIL: interpreter not found: {python}")
            return 1
        python = str(resolved)
    elif shutil.which(python) is None:
        print(f"[smoke] FAIL: interpreter not found on PATH: {python}")
        return 1

    print(f"[smoke] lolping smoke test (repo: {REPO_ROOT})")
    if args.live:
        passed = run_live(python, src_dir, args.live_seconds, verbose=args.verbose)
    else:
        passed = run_self_test(python, src_dir, args.timeout, verbose=args.verbose)

    print(f"[smoke] RESULT: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
