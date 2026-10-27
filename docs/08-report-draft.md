# lolping: A Desktop Ping-Wheel Overlay for Windows

**Course:** SD5913 — Semester 1
**Author:** Zhexian Tao
**Student repository:** <https://github.com/RealSenioume/SDfno3_1101>
**Version described:** 0.2.0

---

## Abstract

League of Legends players communicate through a radial ping wheel: hold a
modifier, drag, release on one of eight slices, and a signal appears in the
game. That gesture is fluent, and it is locked inside one application. This
project re-implements the gesture as a standalone Windows desktop overlay so it
can be used while presenting, streaming, tutoring or reviewing a match.

The delivered artefact, `lolping` 0.2.0, is a tray-resident Python/PyQt5
application. It installs global keyboard and mouse hooks, draws a translucent
always-on-top wheel centred on the pointer without stealing focus, animates the
selection with frame-rate-independent exponential smoothing, leaves a fading
mark where the ping was placed, and records every ping as JSON Lines. It is
built from 13 modules totalling roughly 2,400 lines of Python, with 73
automated unit tests covering the geometry, configuration-repair and
input-state-machine logic, plus a packaging pipeline that produces a standalone
executable.

The project deliberately does **not** interact with the League of Legends
client. That boundary removes any anti-cheat or terms-of-service exposure and
makes the system testable without the game installed. The report documents the
engineering: why one overlay window per monitor is the only correct choice on
mixed-DPI hardware, why exponential smoothing replaced keyframed animation, how
a stale-frame artefact inherited from the prototype was diagnosed and fixed, and
what the system cannot do (exclusive-fullscreen and elevated windows).

**Keywords:** radial menu, desktop overlay, PyQt5, global input hooks,
single-instance, Windows, human–computer interaction

---

## 1. Introduction

### 1.1 Background

Radial menus exploit a well-documented property of human motor control: the time
to acquire a target depends on distance and width (Fitts, 1954), and when
directions rather than rectangular targets are used, selection becomes a
*directional* gesture that experts can perform without looking
(Kurtenbach & Buxton, 1993). Empirical comparisons of pie and linear menus found
pie menus faster and more accurate for the same item count (Callahan et al.,
1988). League of Legends builds its entire non-verbal communication on this
principle: a wheel of eight pings, selected in under a second, with the pointer
travel never leaving the screen centre.

That ergonomic quality is application-bound. Outside the game there is no
equivalent gesture: presenting a slide, reviewing a recorded match or coaching a
newer player all require leaving the current window, finding a chat box, and
typing.

### 1.2 Problem statement

There is no lightweight, keyboard-driven way to place a short-lived visual marker
on the Windows desktop. Existing screen-annotation tools are mouse-and-toolbar
driven, heavy, and designed for capture rather than for a split-second gesture.

### 1.3 Aim and objectives

**Aim.** Re-create the League of Legends ping gesture as a standalone desktop
overlay, built from first principles, that is usable as a daily tool.

The objectives were:

1. **O1** — Reproduce the hold-drag-release gesture with eight configurable
   slices and a visual response latency measured (not assumed) against the
   50 ms target.
2. **O2** — Make the tool self-sufficient on a clean Windows machine: tray
   resident, single instance, start with Windows, JSON configuration, settings
   window, no console window.
3. **O3** — Keep the artefact free of any interaction with the game client, so
   it raises no anti-cheat or terms-of-service concern.
4. **O4** — Produce an engineering record that a marker can assess: requirements,
   design decisions with rejected alternatives, an automated test suite, a manual
   test matrix and a discussion of limitations.

### 1.4 Contributions

* A working desktop implementation of a well-studied interaction technique,
  released as a documented Python package rather than a script.
* A per-monitor overlay architecture that stays correct on mixed-DPI hardware,
  with the reasoning for rejecting the simpler spanning-window design.
* A documented fix for a reproducible translucent-window artefact (stale backing
  store on re-show).
* A measurement methodology for trigger-to-first-paint latency that includes the
  cross-thread queue hop, together with an explicit statement of what it does
  *not* include.
* An automated suite of 73 tests over the parts of the system most likely to be
  wrong (angle conventions, hostile configuration, input state transitions).

### 1.5 Report structure

Section 2 positions the work against existing tools. Section 3 summarises
requirements. Section 4 presents the design and the decisions behind it.
Section 5 describes implementation details and the defects found along the way.
Section 6 reports testing and evaluation. Sections 7–9 cover limitations,
future work and conclusions.

---

## 2. Related work

### 2.1 The gesture as HCI technique

Pie and marking menus are among the most studied interaction techniques.
Callahan et al. (1988) showed pie menus outperform linear menus in selection
time and error rate, and Kurtenbach and Buxton (1993) showed that with marking
menus expert users can select items by gesture direction alone, without visual
search. Both findings predict the design used here: eight equally sized sectors,
selection by angle rather than by precise distance, and a dead zone at the centre
so the gesture can be aborted.

### 2.2 Existing implementations

`lolPing` (darrenprx, MIT licence) is the closest existing work: an Electron
application with a small C++ helper process that owns the Windows low-level
hooks, plus per-monitor transparent windows, ping and emote wheels, sound, and
optional local-network rooms. It is a mature, cross-platform product.

The present project differs deliberately:

| Aspect | lolPing | lolping 0.2.0 |
| --- | --- | --- |
| Stack | Electron + TypeScript + C++ helper | Python 3.14 + PyQt5 + pynput |
| Input suppression | Helper swallows Alt+drag | Cannot suppress; documented limitation |
| Platforms | Windows, macOS, experimental Linux | Windows only |
| Extras | Rooms, emotes, updates, i18n | None — single-purpose |
| Code size | Tens of thousands of lines | ~2,400 lines |
| Purpose | Product | Coursework artefact, built from scratch |

Its published limitations corroborate two constraints found independently here:
exclusive-fullscreen games draw above any overlay, and elevated windows cannot be
drawn over. Citing an independent implementation reaching the same conclusion
is stronger evidence than asserting it alone.

Two practical consequences are worth recording. First, the reference
implementation keeps its state in `%APPDATA%\lolping`, so this project stores its
own data under `%APPDATA%\lolping-desktop` rather than sharing a directory with an
unrelated installed product. Second, because the reference helper removes the
Alt + drag gesture from the input stream before other hooks see it, the two tools
cannot be exercised on the same desktop at the same time; the evaluation protocol
in Section 6.2 therefore requires the reference implementation to be closed
first.

### 2.3 Screen annotation tools

Tools such as Epic Pen and ZoomIt provide drawing and spotlight modes. They are
toolbar- or hotkey-driven, persistent-session tools: the user enters an
annotation mode, draws with the mouse, then exits. They solve a different
problem — sustained annotation rather than a sub-second communication gesture —
and none of them uses a radial menu.

### 2.4 Technology alternatives

Four candidate stacks were compared before implementation:

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Python + PyQt5 + pynput | Iteration speed; both libraries already present; tests trivially runnable | Cannot suppress input; Python startup cost | **Chosen** |
| Electron + native helper (lolPing approach) | Correct input handling; best visuals | Node.js toolchain, C++ build, far beyond coursework scope | Rejected |
| C# / WPF | Native Windows integration, no runtime dependency | Slower iteration for the author, no existing code to reuse | Rejected |
| AutoHotkey | Trivial global hotkeys | Poor drawing model for a translucent animated wheel | Rejected |

---

## 3. Requirements (summary)

The full specification is in `docs/02-requirements.md`; this section records the
subset that shaped the design.

### 3.1 Stakeholders and user stories

The primary stakeholder is the presenter/streamer who needs to point at
something on screen without breaking flow. Secondary stakeholders: a viewer
watching the shared screen, the course marker, and the developer maintaining the
code. Ten user stories were elicited; the three that drove most decisions:

* *As a presenter, I want to mark a spot with one gesture, so the audience sees
  where I am pointing without me leaving the slide.*
* *As a user, I want the tool to stay out of the way when I am not pinging, so it
  costs me no attention and no CPU.*
* *As a user, I want to change the trigger key and the slice names, because Alt
  is already used by other applications.*

### 3.2 Functional requirements

| ID | Requirement |
| --- | --- |
| FR-01 | Configured modifier(s) + mouse button opens the wheel at the pointer |
| FR-02 | Eight slices, clockwise from 3 o'clock, all renameable |
| FR-03 | Release outside the dead zone commits the hovered slice |
| FR-04 | Release inside the dead zone cancels with no side effect |
| FR-05 | Esc and any other mouse button cancel |
| FR-06 | A second trigger while the wheel is open is ignored |
| FR-07 | Settings window edits trigger, radius, dead zone, names, timing, sound, theme |
| FR-08 | Settings persist to JSON and survive a restart |
| FR-09 | Invalid configuration must never prevent start-up |
| FR-10 | Committed ping leaves a visible, fading mark |
| FR-11 | Every ping is appended to a JSON Lines log |
| FR-12 | Optional synthesised ping sound |
| FR-13 | Tray menu: settings, ping log, config folder, pause, quit |
| FR-14 | Configurable global quit hotkey |
| FR-15 | Single instance per desktop session |
| FR-16 | Optional start with Windows |
| FR-17 | Never steal keyboard focus from the active application |
| FR-18 | Optional latency instrumentation to a JSON Lines file |
| FR-19 | Headless self-test mode for CI and packaged builds |

### 3.3 Non-functional requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-01 | Trigger-to-first-paint latency | p95 ≤ 50 ms |
| NFR-02 | Idle CPU | < 1 % |
| NFR-03 | Idle memory | < 120 MB |
| NFR-04 | Cold start | < 3 s |
| NFR-05 | Network use | none |
| NFR-06 | Game-process interaction | none |
| NFR-07 | Survive a dead input hook | restart and report |
| NFR-08 | Configuration corruption | never fatal |
| NFR-09 | Multi-monitor incl. negative coordinates | correct |
| NFR-10 | DPI scaling 100/125/150 % | correct |

---

## 4. Design

### 4.1 Architecture

The system is layered so that everything which can be wrong without a screen is
a pure function:

```
presentation   app.py  overlay.py  settings_dialog.py
system glue    input_hook.py  single_instance.py  autostart.py  sounds.py  logging_setup.py
pure logic     geometry.py  config.py  hotkeys.py            (no Qt imports)
```

`geometry`, `config` and `hotkeys` import nothing from the project and nothing
from Qt, which is what allows 73 unit tests to run in 20 ms with no display, no
hooks and no application object.

Data flow for one gesture:

```
OS → pynput listener thread → InputBridge (Qt signal, queued) → PingApp slot
   → OverlayManager.begin_at(point) → OverlayWindow.show() + synchronous repaint
   → user releases → PingApp slot → OverlayWindow.commit() → mark + JSONL log
```

The hook thread never touches a widget. It emits a Qt signal on an object that
lives in the GUI thread, so Qt converts the emission into a posted event; no
locks are needed around widget state and a slow paint cannot stall the mouse
hook. The cost of that safety is the queue hop, which is precisely what the
latency probe measures instead of hiding.

### 4.2 The trigger state machine

```
Idle ──modifiers held──▶ Armed ──trigger down──▶ WheelOpen
WheelOpen ──release on slice──▶ Idle   (commit)
WheelOpen ──release in dead zone──▶ Idle   (cancel)
WheelOpen ──Esc──▶ Idle   (cancel)
WheelOpen ──other mouse button──▶ Idle   (cancel)
```

Three edge cases were decided explicitly rather than left to chance:

* Releasing the modifier before the mouse button still commits. The gesture was
  completed; cancelling would punish finger order.
* Esc ends the gesture immediately, so the following mouse-up cannot commit.
  This required resetting the hook's `wheel_open` flag on Esc — a bug the test
  suite caught (Section 5.4).
* A second trigger while the wheel is open is ignored. A wheel that re-centres
  mid-drag is worse than a missed click.

### 4.3 Wheel geometry

Screen coordinates grow downwards, so a mathematical positive angle is clockwise
on screen. The project fixes angle 0° at 3 o'clock, growing clockwise, and puts
slice *i* at the centre of `[i·45° − 22.5°, i·45° + 22.5°)`.

Hit testing is then:

```python
if hypot(dx, dy) < dead_zone:          # 34 px by default
    return -1                          # cancel
angle = degrees(atan2(dy, dx)) % 360
return int(((angle + 22.5) % 360) // 45)
```

The `+ 22.5` rotation is what converts "boundaries at i·45°" into "centres at
i·45°". It is the single easiest thing in the project to get wrong, so the test
suite pins it with the half-open-interval property, the exact ±22.4° boundary,
and a sweep of 72 angles. Rendering then has to invert the convention because
Qt's `drawPie` measures in 1/16° **counter-clockwise**; the conversion lives in
exactly one function.

### 4.4 Rendering and animation

Each slice carries a weight in `[0, 1]` that chases its target every frame:

```
α = 1 − exp(−dt / τ)        τ = 35 ms by default
w ← w + (w_target − w)·α
```

Exponential smoothing was chosen over a keyframed tween for three reasons:
it is frame-rate independent (identical feel at 60 and 144 Hz), it is
interruptible (reversing direction changes only the target), and it is
stall-safe because `dt` is clamped to 50 ms. A slice snaps exactly to 0 or 1 once
within 5 ms of target, so the painter stops doing sub-pixel work.

Paint order is: glow pass, slice bodies **sorted by weight ascending** (so the
highlighted slice is drawn last and its 8 px radius growth is not clipped), the
centre disc with the hovered name, then the per-slice labels at 0.72 R. Slice
geometries never move; only radius, colour and alpha change. This avoids the
classic radial-menu defect where slices swap places mid-drag.

### 4.5 Multi-monitor and DPI

Two architectures were considered:

| Approach | Assessment |
| --- | --- |
| One window spanning the virtual desktop | Wrong on mixed DPI: Qt 5 scales a window by one factor, so the wheel is mis-sized on the second monitor; also repaints screens that never show anything |
| One window per `QScreen`, created lazily | **Chosen** — each window inherits its own screen's scale, is fitted to `screen.geometry()`, and only the screen under the pointer paints |

`OverlayManager.begin_at()` resolves the screen under the cursor and shows only
that screen's window. Windows are keyed by `(screen.name(), id(screen))` because
duplicate or empty monitor names occur in practice. High-DPI attributes are set
*before* `QApplication` is constructed, with `PassThrough` rounding so fractional
125/150 % scales are preserved; with scaling on, `QCursor.pos()`,
`QScreen.geometry()` and widget geometry all share one logical pixel space, so
the geometry module needs no DPI awareness at all.

### 4.6 Configuration

The configuration is a JSON file under `%APPDATA%\lolping-desktop\`. Its loader is a
*total* function: every field is repaired independently — wrong type → default,
out-of-range → clamp, unknown key → ignore, wrong list length → pad or truncate.
The design goal is that no edit to the file, and no corrupted file, can stop the
application from starting. Saving is atomic (temporary file plus `os.replace`),
so a crash mid-write cannot leave a half-written config.

The most important repair is the one that is easy to miss: an empty
`trigger_modifiers` list would otherwise make *every* mouse click open a wheel.
The loader rejects it and falls back to `["alt"]`.

### 4.7 Robustness

Three failure modes received explicit design attention:

1. **A silently dead hook.** The worst possible state: the tray icon looks fine
   and nothing works. A supervisor thread checks listener liveness once per
   second, restarts anything dead, logs it and raises a tray warning.
2. **A second instance.** Two overlays would fight over the same hooks. A
   one-byte `msvcrt.locking()` file lock answers "am I first?" without pulling
   `QtNetwork` into the frozen build, and the OS releases it if the process dies.
3. **A crash with no console.** A windowed build has nowhere to print, so
   everything goes to a rotating log file and `sys.excepthook` records uncaught
   exceptions instead of dying silently.

### 4.8 Design decisions

| # | Decision | Alternative rejected | Consequence accepted |
| --- | --- | --- | --- |
| D1 | PyQt5 | PySide6, PyQt6 | GPL/commercial licence; Qt 5 per-window DPI limits |
| D2 | `pynput` listeners | Raw `SetWindowsHookEx` via `ctypes` | Cannot suppress input |
| D3 | One window per screen | One spanning window | More windows, screen add/remove handling |
| D4 | Timer-driven animation | Event-driven on cursor motion | 60 Hz timer while visible only |
| D5 | Exponential smoothing | Keyframed tween | Feels less "designed" than an easing curve |
| D6 | JSON file | `QSettings`, registry, TOML | Manual atomic-write code |
| D7 | Total repair-on-load | Strict validation | Silent clamping can surprise the user |
| D8 | File lock | `QLocalServer`, named mutex | Windows-specific |
| D9 | Swallow the trigger click | Click-through overlay | A click is consumed by the wheel window |
| D10 | Generate icon and sound in code | Ship PNG/WAV assets | Less polished assets; no binary files in the repo |

---

## 5. Implementation

### 5.1 Module inventory

| Module | Lines | Responsibility |
| --- | --- | --- |
| `geometry.py` | 111 | Sector hit testing, angles, easing |
| `config.py` | 214 | Schema, repair, atomic persistence, paths |
| `hotkeys.py` | 145 | Parse and format `"ctrl+shift+q"` |
| `input_hook.py` | 346 | OS hooks, key normalisation, supervisor |
| `overlay.py` | 796 | Per-screen windows, painting, marks |
| `settings_dialog.py` | 459 | Settings UI with validation |
| `app.py` | 502 | Bootstrap, tray, wiring, logs, CLI |
| `single_instance.py` | 76 | File-lock instance guard |
| `autostart.py` | 70 | `HKCU\...\Run` integration |
| `sounds.py` | 58 | Synthesised asynchronous ping tone |
| `logging_setup.py` | 71 | Rotating log, excepthook |
| `__init__.py`, `__main__.py` | 31 | Package metadata and entry point |

### 5.2 Input hook

`pynput` delivers callbacks on its own listener threads. Two implementation
details decide whether the feature works at all:

**Virtual key codes, not characters.** With Ctrl held, `pynput` reports the
*control character* (`"\x11"` for Q), so matching a quit hotkey against
`key.char` fails exactly in the case that matters. The implementation derives
letters and digits from `key.vk` instead, and only falls back to `char` for keys
with no virtual code.

**KeyCode is checked before the lookup tables.** `pynput`'s `KeyCode` defines
hashing that raises when `vk` is `None`, so using one as a dictionary key
produces `TypeError` on unmappable keys. The token function therefore tests
`isinstance(key, KeyCode)` first. A test covers this regression.

### 5.3 Overlay and the stale-frame defect

The prototype exhibited a visible one-frame artefact: a translucent,
always-on-top window re-shown at a new position could present the *previous*
gesture's pixels before the new frame arrived. Qt keeps the widget's backing
store across `hide()`/`show()`.

The fix is to clear the render state and force a synchronous repaint *before*
hiding, so the next `show()` has nothing stale to present:

```python
self._weights = [0.0] * count
self._hover = -1
self.repaint()       # fully transparent now
self.hide()
```

The same ordering is used on open, so the first visible frame is already
correct. This is a small change with a large perceptual effect, and it is the
kind of defect that would be hard to justify without a diagnosis.

### 5.4 Defects found by the test suite

The 73 tests were not written after the fact; three real defects surfaced while
writing them:

1. **Esc left the hook's `wheel_open` flag set**, so the next trigger could be
   ignored and the pending mouse-up was still treated as a commit candidate.
   Fixed by clearing the flag when Esc cancels.
2. **`KeyCode` as a dictionary key** raised `TypeError` for unmappable keys,
   which would have crashed the keyboard callback on unusual keyboards.
   Fixed by ordering the type checks.
3. **A test-side regression**: the temp-directory strategy assumed the system
   TEMP directory was writable. Fixed to probe candidates and fall back, which
   also makes the suite runnable in restricted environments.

### 5.5 Packaging

`build/lolping.spec` produces a one-folder, windowed build. One-folder rather
than one-file is a deliberate latency decision: a one-file build unpacks tens of
megabytes of Qt DLLs into a temporary directory on every launch, adding seconds
to a cold start in a tool whose whole value is speed. UPX compression is off
because compressed executables are a well-known source of antivirus and
SmartScreen false positives.

One packaging trap is documented in the spec: PyInstaller executes the entry
script as a top-level module, where a relative import fails, so the build uses a
generated stub that imports the package entry point.

---

## 6. Testing and evaluation

### 6.1 Automated tests

| Suite | Tests | What it pins |
| --- | --- | --- |
| `test_geometry.py` | ~27 | Dead zone, eight cardinal directions, exact boundary behaviour, angle sweep, span contiguity, easing convergence |
| `test_config.py` | ~24 | Round-trip, hostile inputs, clamping, sector padding, atomic save, corrupt/missing file |
| `test_hotkeys.py` | ~12 | Modifier aliases, canonical formatting, rejection of ambiguous combos |
| `test_input_hook.py` | ~22 | Trigger, commit, cancels, quit hotkey, modifier edge cases, key tokens |

Result: **73 tests, all passing** (`python -m unittest discover -s tests`), in
about 20 ms, with no display and no hooks installed.

Two further automated checks exist: `--self-test` drives one complete
wheel-open/commit cycle offscreen and prints `SELF-TEST OK`, and
`tools/smoke_test.py` fails the build if that string is missing.

### 6.2 Manual test matrix

The full matrix is in `docs/04-test-plan.md` (30 cases across display mode, DPI,
monitor count and target integrity). The four environmental axes are:

* windowed / borderless / exclusive-fullscreen target application,
* 100 % / 125 % / 150 % display scaling,
* single and dual monitor, including a monitor with negative coordinates,
* target application running normally and as administrator.

Two of the resulting expectations are *failures by design* — no overlay can draw
over exclusive-fullscreen D3D or above an elevated window — and are recorded as
expected results rather than defects.

| # | Case | Expected |
| --- | --- | --- |
| TC-01 | Alt + drag, release on a slice | Wheel appears at pointer, mark left, one log line |
| TC-05 | Alt + click, release at centre | Wheel closes, no mark, no log line |
| TC-08 | Esc during drag | Wheel closes immediately, release commits nothing |
| TC-12 | Right-click during drag | Wheel closes, no mark |
| TC-18 | Edit settings, restart | Values persist |
| TC-21 | Delete/corrupt `config.json` | Starts with defaults |
| TC-24 | Launch twice | Second process exits, one tray icon |
| TC-26 | Kill hook (debugger) | Supervisor restarts it, tray warning |
| TC-28 | Exclusive-fullscreen game | **Expected failure** — overlay hidden |
| TC-30 | Elevated window underneath | **Expected failure** — overlay hidden |

Figures 1–3 were captured on the target machine during the measurement session.

![Figure 1: the wheel mid-gesture](figures/fig1-wheel.png)

*Figure 1 — the wheel open at the pointer with the "Enemy Missing" slice
highlighted: eight labelled slices, a gold glow on the hovered slice, and the
centre disc repeating the current selection.*

![Figure 2: the mark left after release](figures/fig2-mark.png)

*Figure 2 — the mark left on screen after release: an expanding ring, a dot
anchoring the exact point, and the slice name drawn above it with a dark halo so
it stays legible over bright desktop content.*

![Figure 3: the settings window](figures/fig3-settings.png)

*Figure 3 — the settings window: trigger, wheel, slices, feedback and system
groups, with validation errors shown inline.*

### 6.3 Latency measurement

`--latency-probe` records, per gesture, `frame_ms` (mouse-down hook timestamp →
first paint of the overlay window) and `commit_ms` (mouse-down → mouse-up).
`tools/latency_report.py` computes n / min / median / p90 / p95 / p99 / max and
returns a pass/fail verdict against the 50 ms target.

**Test conditions.** Windows 11 desktop session, Python 3.14.5, PyQt5 5.15.11, a
single display running at a scaled logical resolution, with the reference
implementation closed (Section 2.2) and no other hook-owning tool active. The 48
gestures were issued by `tools/demo_gesture.py`, which sends the same
Alt + press + drag + release sequence a human performs.

| Metric | n | min | median | p90 | p95 | p99 | max | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `frame_ms` — all samples | 48 | 2.91 | 5.40 | 13.72 | 14.48 | 105.48 | 105.48 | PASS |
| `frame_ms` — warm-up excluded | 47 | 2.91 | 5.40 | 13.10 | **13.81** | 15.47 | 15.47 | **PASS** |
| `commit_ms` — button hold time, not latency | 48 | 73 | 137 | 1880 | 2958 | 4441 | 4441 | n/a |

**Interpretation.**

1. The steady-state p95 is **13.81 ms**, roughly 3.6 times under the 50 ms target
   of NFR-01, with a median of 5.40 ms.
2. Exactly one of the 48 samples exceeds 50 ms: 105.48 ms, on the first wheel of
   the session. The first paint of a translucent Qt window is where the font
   database, the glyph cache and window composition are first touched; afterwards
   the distribution is tight (maximum 15.47 ms). Both views are reported because
   hiding the outlier and quoting it as typical would each be dishonest.
3. Even adding one full 60 Hz frame (~16.7 ms) of compositor presentation to every
   sample, the steady-state p95 stays near 30 ms and the requirement still holds.
4. `commit_ms` is the time the button was held, not a latency. The 137 ms median
   is a natural drag; the 4.4 s maximum corresponds to gestures deliberately held
   while screenshots were captured. It is reported because the probe records it,
   not because it says anything about responsiveness.

**Data-collection caveat.** The harness anchors the gesture on an empty strip of
the taskbar so that the swallowed click cannot activate another application.
Because that anchor sits near the bottom screen edge, downward drags are clipped
by the boundary and end inside the dead zone: of 47 completed gestures, 40
committed and 7 cancelled. The latency metric is sampled at the first paint and
therefore does not depend on which slice is chosen; the skew affects only the
recorded sector distribution, not the measurement.

**Threats to validity, stated plainly.** `frame_ms` ends when Qt has painted
into its backing store, *not* when the display presents the pixel; real perceived
latency is higher by up to one refresh interval (roughly 8–17 ms). It measures
the first frame only, which is the worst case of a gesture. Offscreen runs are
not comparable to a real desktop session, and the numbers are from one machine,
so they describe this configuration rather than all configurations.

### 6.4 Resource and start-up measurements

| Metric | Target | Measured | Verdict |
| --- | --- | --- | --- |
| Idle CPU, no wheel open | < 1 % | < 0.01 % (no CPU-time tick in a 10 s sample) | PASS |
| Idle working set | < 120 MB | 41 MB | PASS |
| Cold start, process spawn → tray ready | < 3 s | 0.42 s | PASS |
| Idle animation timers | 0 | 0 | PASS |

Measurement method: the working set was read from the live process
(`WorkingSet64`), idle CPU was computed as the change in process CPU time over a
10-second window with no user interaction, and start-up was timed from process
spawn to the moment the application logged that it was ready. The measurement
process is the real interpreter, not the Windows Store `python.exe` launcher: an
early attempt that sampled the launcher reported 15 MB and 0 % and was discarded
as invalid, which is a reminder that process-level measurements need the right
process.

The idle-timer row is a structural guarantee rather than an observation: the
60 Hz timer is started only when a window is shown and stopped as soon as neither
a wheel nor a mark needs drawing, so an idle lolping has no animation work
scheduled at all. This is what makes the sub-0.01 % idle CPU figure possible.

### 6.5 Discussion

The automated suite tests the logic that is hard to verify by hand (angle
conventions, hostile configuration) and is deliberately blind to the logic that
cannot be tested without an OS: whether the installed low-level hooks receive
real input. That gap is closed by a manual protocol and by a synthetic-gesture
script (`tools/demo_gesture.py`), and it is the honest boundary of this
evaluation.

The most valuable lesson from the project is that the specification of
"instantaneous" is worthless without an instrument. Writing the probe first — and
then being explicit that it excludes compositor presentation — turned a vague
goal into a number and an argument.

---

## 7. Limitations

1. **Exclusive fullscreen.** A D3D swap chain bypasses the compositor; the
   overlay cannot appear. Users must run the game borderless or windowed. The
   same limitation is documented independently by `lolPing`.
2. **Elevated windows.** Windows User Interface Privilege Isolation prevents a
   normal-integrity process from hooking or drawing over an administrator
   window.
3. **No input suppression.** `pynput` observes but cannot swallow input. The
   overlay window is on top for the duration of the gesture, so the click is
   consumed, but a third-party hook running earlier in the chain could still
   see it.
4. **Mixed-DPI multi-monitor.** Correct on the screen where the wheel opens;
   marks stay on that screen.
5. **Windows only.** `msvcrt`, `winreg` and `winsound` are used directly.
6. **No fullscreen auto-pause.** Pausing is manual in 0.2.0.
7. **Single-author evaluation.** The latency and usability data describe one
   machine and one user.

---

## 8. Future work

1. Fullscreen auto-pause via foreground-window state query.
2. Application profiles: different slice sets when presenting versus reviewing.
3. A native input helper that can suppress the trigger gesture, which would also
   remove limitation 3.
4. Per-monitor DPI v2 and a Qt 6 port.
5. A ping-history viewer with a heat map over the screen.
6. Accessibility: high-contrast theme, keyboard-only slice commit, and screen
   reader announcement of the committed slice.

---

## 9. Conclusion

This project re-implemented a well-studied interaction technique as a standalone
Windows tool. The gesture itself is simple; the engineering difficulty lay in the
edges — angle conventions that are easy to invert, a translucent window that
keeps stale pixels, a control character that defeats a hotkey comparison, a
mixed-DPI desktop that breaks the obvious window architecture, and a global hook
that fails silently by design.

The result is a 2,400-line Python application with a documented architecture,
ten explicit design decisions with rejected alternatives, 73 automated tests, a
formal manual test matrix, a packaging pipeline and a measured latency
methodology. It honours every objective set out in Section 1.3: the gesture is
reproduced, the tool is self-sufficient on a clean machine, the game client is
never touched, and the engineering record is complete enough to be assessed.

Two failure modes are documented rather than hidden, because a tool that clearly
states what it cannot do is more trustworthy than one that does not.

---

## References

1. Callahan, J., Hopkins, D., Weiser, M., & Shneiderman, B. (1988). An empirical
   comparison of pie vs. linear menus. *Proceedings of CHI '88*, 95–100.
2. Fitts, P. M. (1954). The information capacity of the human motor system in
   controlling the amplitude of movement. *Journal of Experimental Psychology*,
   47(6), 381–391.
3. Kurtenbach, G., & Buxton, W. (1993). The limits of expert performance using
   hierarchic marking menus. *Proceedings of CHI '93*, 482–487.
4. darrenprx. *lolPing — League of Legends ping wheel for your desktop*.
   GitHub, MIT licence. <https://github.com/darrenprx/lolPing>
5. Riot Games. *League of Legends* — in-client ping and communication system.
   <https://www.leagueoflegends.com>
6. Qt Company. *Qt 5 documentation*: QWidget, QScreen, QPainter.
   <https://doc.qt.io/qt-5/>
7. Moses Palmér. *pynput — monitor and control input devices*.
   <https://pynput.readthedocs.io>
8. PyInstaller Development Team. *PyInstaller manual*.
   <https://pyinstaller.org/en/stable/>
9. Microsoft. *User Interface Privilege Isolation* and *Desktop Window Manager*
   documentation. Microsoft Learn.
10. Python Software Foundation. *Python 3.14 documentation*.
    <https://docs.python.org/3.14/>

---

## Appendices

### Appendix A — Repository layout

```
src/lolping/     13 modules: geometry, config, hotkeys, input_hook, overlay,
                 settings_dialog, app, single_instance, autostart, sounds,
                 logging_setup, __init__, __main__
tests/           4 unittest suites, 73 tests
tools/           smoke_test.py, latency_report.py, demo_gesture.py
build/           lolping.spec (PyInstaller), build.ps1
docs/            00 module contract, 01 proposal, 02 requirements,
                 03 design, 04 test plan, 05 user manual,
                 06 report outline, 07 build and release
Early_test/      prototype iterations (v01, v01_01) kept as process evidence
```

### Appendix B — Reproducing the results

```powershell
# tests
$env:PYTHONPATH="src"; python -m unittest discover -s tests -v

# headless smoke test
python tools\smoke_test.py

# latency data (interactive; 100 gestures recommended)
python -m lolping --latency-probe --debug
python tools\latency_report.py

# packaged build
powershell -NoProfile -ExecutionPolicy Bypass -File .\build\build.ps1 -Clean
```

### Appendix C — Declaration of AI assistance

> Delete or adapt this appendix according to the course policy. The project was
> developed with AI assistance for drafting, code generation and review. State
> honestly which parts: for example, that the architecture, module interfaces,
> tests and documentation drafts were produced with an AI assistant, and that
> every artefact was reviewed, executed and verified by the author before
> submission. Keep this consistent with the course's academic-integrity rules.

### Appendix D — Evidence checklist for the final submission

| Evidence | Where it goes |
| --- | --- |
| Wheel open, mid-drag, hovered slice | §6.2, Figure 1 |
| Mark left after commit | §6.2, Figure 2 |
| Settings window | §5, Figure 3 |
| `latency.jsonl` summary table | §6.3, Table 6 |
| CPU / memory screenshots | §6.4 |
| `git log --oneline` showing iterations | §5, Figure 4 |
| 30–60 s screen recording | link from §6 |
