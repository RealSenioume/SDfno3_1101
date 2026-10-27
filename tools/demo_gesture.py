r"""Manual end-to-end check: drive one ping gesture with synthetic input.

Why this exists
---------------
The automated suite drives the hook's callbacks directly and the GUI with the
offscreen platform, so neither proves that the *installed OS hooks* receive real
input. That can only be checked on an interactive desktop, and this script does
it without a human: it presses Alt, presses and moves the mouse, releases, and
expects one ping in the log.

Usage
-----
1. Start the app with the latency probe enabled::

       set PYTHONPATH=src
       python -m lolping --latency-probe --debug

2. In a second terminal run::

       python tools\demo_gesture.py

3. The app should draw the wheel, leave a mark, and append one line to
   ``%APPDATA%\\lolping-desktop\\pings.jsonl`` and one to ``latency.jsonl``.

Options
-------
``--sector N``  aim at sector N (0 = 3 o'clock, growing clockwise)
``--wait S``    idle seconds before the gesture (default 1.0)
``--x/--y``     override the target point (default: empty taskbar strip)

Safety: the pointer is moved to an empty part of the taskbar first, so the
swallowed click cannot press a button in another application.
"""

from __future__ import annotations

import argparse
import sys
import time


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send one synthetic ping gesture.")
    parser.add_argument("--sector", type=int, default=0, help="target sector, 0-7")
    parser.add_argument("--wait", type=float, default=1.0, help="idle seconds first")
    parser.add_argument("--distance", type=int, default=200, help="drag distance in px")
    parser.add_argument("--x", type=int, default=None, help="override target x")
    parser.add_argument("--y", type=int, default=None, help="override target y")
    return parser.parse_args(argv)


def target_point(args: argparse.Namespace) -> tuple[int, int]:
    if args.x is not None and args.y is not None:
        return args.x, args.y
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    rect = app.primaryScreen().geometry()
    # Middle of the bottom edge: taskbar background, no button under it.
    return rect.width() // 2, rect.y() + rect.height() - 8


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        from pynput.keyboard import Controller as KeyController
        from pynput.keyboard import Key
        from pynput.mouse import Button, Controller
    except ImportError:
        print("pynput is not installed: pip install -r requirements.txt", file=sys.stderr)
        return 2

    import math

    x, y = target_point(args)
    angle = math.radians(args.sector * 45.0)
    dx = int(round(args.distance * math.cos(angle)))
    dy = int(round(args.distance * math.sin(angle)))

    mouse = Controller()
    keyboard = KeyController()

    print(f"target ({x}, {y}) -> sector {args.sector} offset ({dx}, {dy})")
    time.sleep(max(0.0, args.wait))

    mouse.position = (x, y)
    time.sleep(0.2)
    keyboard.press(Key.alt)
    time.sleep(0.15)
    mouse.press(Button.left)
    time.sleep(0.2)
    for step in range(1, 11):  # move in steps so the wheel animates
        mouse.position = (x + dx * step // 10, y + dy * step // 10)
        time.sleep(0.02)
    time.sleep(0.2)
    mouse.release(Button.left)
    time.sleep(0.05)
    keyboard.release(Key.alt)

    print("gesture sent; check %APPDATA%\\lolping-desktop\\pings.jsonl for one new line")
    return 0


if __name__ == "__main__":
    sys.exit(main())
