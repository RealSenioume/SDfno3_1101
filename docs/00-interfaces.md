# Module interface contract — lolping v0.3.3

This file is the single source of truth for module boundaries. Read it before
writing code. Do **not** change a signature without telling the Lead: other
files are being written in parallel against it.

Project root: the repository root (the folder that contains `src/`)
Package root: `src/lolping`

Target: Python 3.14 + PyQt5 5.15.11 + pynput 1.8.2, Windows 11. No new runtime
dependencies. No network access at runtime. No reading/writing game memory.

---

## 1. Module ownership

Each module has exactly one owner and one write boundary, so the layers can be
implemented and reviewed independently:

| Layer | Modules |
| --- | --- |
| Pure logic (no Qt, unit-tested) | `geometry.py`, `config.py`, `hotkeys.py` |
| System glue | `input_hook.py`, `single_instance.py`, `autostart.py`, `sounds.py`, `logging_setup.py` |
| Presentation | `overlay.py`, `settings_dialog.py` |
| Application shell | `app.py`, `__main__.py`, `__init__.py` |
| Verification | `tests/*`, `tools/*`, `build/*` |

The contract below is frozen before the presentation layer starts: it is what
lets the pure-logic modules, the overlay and the build scripts be developed
against the same API surface without renegotiating signatures.

---

## 2. `geometry.py` (pure math, no Qt import)

```python
def wrap_degrees(angle: float) -> float            # -> [0, 360)
def distance(dx: float, dy: float) -> float
def clamp(value: float, low: float, high: float) -> float
def sector_index(dx: float, dy: float, dead_zone: float = 34.0,
                 count: int = 8) -> int            # -1 inside the dead zone
def sector_center_angle(index: int, count: int = 8) -> float   # degrees
def sector_span(index: int, count: int = 8) -> tuple[float, float]
def sector_label_point(cx: float, cy: float, index: int, radius: float,
                       count: int = 8) -> tuple[float, float]
def ease_alpha(dt: float, tau: float) -> float     # 1 - exp(-dt/tau)
def approach(current: float, target: float, dt: float, tau: float,
             snap: float = 0.005) -> float
```

**Angle convention (important).** Screen coordinates: x right, y **down**.
Angle 0° points right (3 o'clock) and grows **clockwise**.
Sector `i` is centred on `i * 45°` and spans `[i*45 - 22.5, i*45 + 22.5)`.
So sector 0 = 3 o'clock, sector 2 = 6 o'clock, sector 4 = 9 o'clock,
sector 6 = 12 o'clock. Qt's `drawPie` measures in 1/16 degrees
**counter-clockwise** from 3 o'clock, so a sector that spans
`[start, end]` clockwise must be drawn as
`drawPie(..., angle=-int((start + span)) * 16, span * 16)` — see the original
`pingWheel_BETA_v01_01.py` `paintEvent` for the working formula.

## 3. `config.py` (persistence)

```python
@dataclass
class Config:
    trigger_modifiers: list[str]       # subset of ("ctrl","alt","shift","win")
    trigger_mouse_button: str          # "left" | "right" | "middle" | "x1" | "x2"
    wheel_radius: int                  # 60..400, default 130
    dead_zone: int                     # 5..wheel_radius-20, default 34
    sector_count: int                  # fixed 8 in v0.3.3
    sectors: list[str]                 # length == sector_count
    animation_tau: float               # 0.005..0.5, default 0.035
    mark_duration_ms: int              # 300..4000, default 900
    sound_enabled: bool                # default False
    quit_hotkey: str                   # "ctrl+shift+q"
    start_with_windows: bool           # default False
    show_labels: bool                  # default True
    theme: str                         # "gold" | "blue" | "red"
```

```python
def app_data_dir() -> Path                 # %APPDATA%\lolping-desktop
def config_path() -> Path                  # app_data_dir()/config.json
def log_path() -> Path                     # app_data_dir()/pings.jsonl
def latency_path() -> Path                 # app_data_dir()/latency.jsonl

class Config:
    @classmethod
    def load(cls, path: Path | None = None) -> "Config"    # never raises; bad file -> defaults
    def save(self, path: Path | None = None) -> Path        # atomic tmp+replace
    def to_dict(self) -> dict
    @classmethod
    def from_dict(cls, data: dict) -> "Config"              # tolerant, clamps, repairs
```

`from_dict` must never raise on hostile input: unknown keys ignored, wrong
types -> default, `sectors` padded/truncated to `sector_count`.

## 4. `hotkeys.py` (parsing)

```python
def parse_hotkey(text: str) -> frozenset[str]        # {"ctrl","shift","q"}
def format_hotkey(keys: frozenset[str] | set[str]) -> str   # "Ctrl+Shift+Q"
MODIFIER_NAMES: tuple[str, ...]                       # ("ctrl","alt","shift","win")
```

## 5. `input_hook.py` (system glue)

```python
class InputBridge(QObject):
    trigger_down = pyqtSignal(int, int)   # global cursor x, y (logical px)
    trigger_up = pyqtSignal()
    cancel = pyqtSignal()                 # Esc pressed
    quit_requested = pyqtSignal()         # configured quit hotkey
    other_click = pyqtSignal(int, int)    # right/middle click while wheel open -> cancel

class InputHook:
    def __init__(self, config: Config, bridge: InputBridge): ...
    def start(self) -> None
    def stop(self) -> None
    def rebind(self, config: Config) -> None   # apply new trigger after settings change
    @property
    def healthy(self) -> bool
```

Behaviour: `trigger_down` fires only when the configured modifiers are all
held **and** the configured mouse button is pressed. Signals are emitted from
the pynput listener thread; Qt queues them to the GUI thread automatically
(they are emitted on a QObject that lives in the main thread, so use a
plain `pyqtSignal` emit — do **not** touch widgets from the hook thread).
A supervisor thread restarts dead listeners and logs the exception.

## 6. `overlay.py` (presentation)

```python
class OverlayWindow(QWidget):
    committed = pyqtSignal(str)     # sector name; emitted on successful commit
    cancelled = pyqtSignal()        # emitted when the wheel closes without a ping

    def __init__(self, screen: QScreen, config: Config, parent=None)
    def set_config(self, config: Config) -> None
    def begin(self, global_pos: QPoint) -> None
        # show window, reset weights, start 60 Hz timer, no focus steal
    def cancel(self) -> None
        # animate out, hide, emit cancelled (only if it was open)
    def commit(self) -> str | None
        # resolve hovered sector at this instant; if none -> cancel(); else drop a
        # mark at the wheel centre, hide the wheel, emit committed(name), return name
    def add_mark(self, name: str, global_pos: QPoint) -> None
    def is_open(self) -> bool

class OverlayManager(QObject):
    committed = pyqtSignal(str, object)   # (sector name, QPoint global centre)
    def __init__(self, config: Config, parent=None)
    def set_config(self, config: Config) -> None
    def begin_at(self, global_pos: QPoint) -> None   # picks the QScreen under the cursor
    def cancel(self) -> None
    def commit(self) -> str | None
    def is_open(self) -> bool
    def shutdown(self) -> None                       # stop timers, close windows
```

Rules for the renderer:
- One `OverlayWindow` per `QScreen`, created lazily, geometry = that
  screen's `geometry()` in logical pixels, re-fitted when screens change.
- Window flags/attributes: frameless, always-on-top, tool window, no drop
  shadow, translucent, `WA_ShowWithoutActivating`, and it **must swallow the
  mouse** (do not set `WA_TransparentForMouseEvents`) so the click that opens
  the wheel does not also activate the app underneath.
- Paint with `QPainter` + antialiasing, gold-on-grey palette, pie sectors
  whose radius grows with a per-sector weight, a 12 px glow pass, a dark
  centre disc with the hovered label, and per-sector text labels near
  0.72 R (auto-shrinking, hidden when `config.show_labels` is False).
- 60 Hz `QTimer` only while the window is visible; stop it and `hide()` when
  the wheel is closed and no mark is animating.
- Marks: expanding ring + dot + label that fades over
  `config.mark_duration_ms`.
- Never block: no `repaint()` storms, no `time.sleep`, no synchronous disk IO.

## 7. `settings_dialog.py` (presentation)

```python
class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent=None)
    def edited_config(self) -> Config      # valid only after accept()
    @staticmethod
    def edit(config: Config, parent=None) -> Config | None   # None if cancelled
```

Edits: trigger modifiers (checkboxes) + mouse button combo, wheel radius
slider, dead zone slider, sector name line edits (8), animation speed,
mark duration, sound checkbox, quit hotkey field, "start with Windows"
checkbox, theme combo, and a **Reset to defaults** button.
`start_with_windows` is applied by the Lead's `autostart.py`, not by the
dialog. Validation errors must be shown inline, never crash.

## 8. `app.py` (application shell)

Owns: `QApplication` bootstrap, DPI attributes, single instance, logging,
tray icon and menu (Settings…, Ping history log, Open config folder,
Pause/Resume, Quit), wiring `InputHook` <-> `OverlayManager`, ping logging
(JSONL), optional sound, `--latency-probe` mode.

CLI: `python -m lolping [--config PATH] [--latency-probe] [--debug]`

## 9. Log formats (the analyser in `tools/` reads these)

`%APPDATA%\lolping-desktop\pings.jsonl`, one JSON object per line:

```json
{"ts": "2026-10-24T12:00:00.123+08:00", "sector": 2, "name": "Assist Me", "x": 960, "y": 540}
```

`%APPDATA%\lolping-desktop\latency.jsonl` (only with `--latency-probe`):

```json
{"ts": "2026-10-24T12:00:00.123+08:00", "frame_ms": 12.4, "commit_ms": 840.2}
```

`frame_ms` = time from the mouse-down hook callback to the first frame of the
wheel being painted. `commit_ms` = time from mouse-down to mouse-up.

## 10. Style rules

- Python 3.10+ syntax (`from __future__ import annotations`, `X | None`).
- Type hints on every public function; docstrings in English.
- No `print()` for diagnostics — use `logging.getLogger(__name__)`.
- No bare `except:`; catch specific exceptions and log them.
- English comments and identifiers; the UI strings stay English (assignment
  is English), Chinese only in chat.
- Every module must be importable on its own (`import lolping.config` works).
- Do not create `.pyc`, `__pycache__`, or build output inside the repo.
