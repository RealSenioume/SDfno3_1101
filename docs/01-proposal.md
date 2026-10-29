# 1. Proposal — lolping v0.3.4

## 1.1 Background and problem statement

League of Legends communicates intent through a radial ping menu: the player
holds a key, a wheel appears at the cursor, and releasing over a sector sends a
signal to the team. Direction selects meaning and the hand never leaves the
mouse. The same interaction suits any desktop workflow that needs a fast,
glanceable eight-choice menu.

The project starts from the course-provided prototype
`pingWheel_BETA_v01_01.py`, a single-file PyQt5 script that drew a gold-on-grey
wheel and committed a label on mouse release. It proved the interaction but had
hard-coded labels and trigger, no settings, no logging, no error handling and no
tests. v0.3.4 turns it into a documented package against a frozen module
contract (`docs/00-interfaces.md`).

The engineering question is whether a small Python/Qt desktop application can
deliver this interaction with a p95 wheel latency of 50 ms, negligible idle
resource use, predictable behaviour on scaled and multi-monitor desktops, and
local logging — without reading game memory or using the network — while three
developers implement it in parallel in four weeks.

## 1.2 Aim

Deliver lolping v0.3.4, a Windows 11 desktop application that opens an
eight-sector ping wheel at the cursor on a configurable gesture, commits or
cancels correctly, persists settings and a local ping log, and meets the
documented usability and performance requirements within four weeks.

## 1.3 Objectives (SMART)

- **O1 Functional completeness.** By the end of week 3, implement FR-01 to
  FR-22: every sector commits its correct label, all three cancel paths work,
  settings survive a restart, and each commit produces exactly one log line.
  Verified by the P1 manual test cases.
- **O2 Responsiveness and footprint.** By the end of week 4, achieve `frame_ms`
  p95 ≤ 50 ms over 100 gestures per core environment, idle CPU below 1%, idle
  RAM below 120 MB and cold start below 3 s (NFR-01 to NFR-04).
- **O3 Quality.** Unit tests for `geometry`, `config` and `hotkeys` pass, the
  exit criteria in `docs/04-test-plan.md` are met, and no severity 1 or 2 defect
  is open at submission.
- **O4 Usability and documentation.** Deliver the six documents in English, and
  demonstrate that a first-time user can install the application, send a ping,
  change a setting and uninstall it using only `docs/05-user-manual.md`
  (observed walkthrough).

## 1.4 Scope

| In scope (v0.3.4) | Out of scope |
| --- | --- |
| Eight-sector overlay wheel opened by a hold-and-drag gesture | Any interaction with the game client, game memory or Riot API |
| Configurable trigger, commit and cancel behaviours, confirmation mark | Sector counts other than eight |
| Settings dialog, JSON configuration, tray menu, pause, quit hotkey, autostart | Network features, multiplayer, rooms, shared ping history |
| Local JSONL ping and latency logs | Cross-platform support, installer engineering, auto-update |
| DPI- and multi-monitor-aware placement | In-game HUD, voice, champion or cooldown data |

## 1.5 Approach

The package has three layers: pure logic (`geometry`, `config`, `hotkeys`; no Qt
imports, unit-testable), system glue (`input_hook`, `single_instance`,
`autostart`, `sounds`) and presentation (`overlay`, `settings_dialog`, `app`).
The pynput listener emits Qt signals with the cursor position; the overlay
opens on the cursor's screen; release resolves the sector, draws a mark and
appends one JSON line. Signals are queued to the GUI thread, so no widget is
touched from the hook thread, and a supervisor restarts a dead listener.

Development follows file ownership, with `docs/00-interfaces.md` frozen before
implementation. Verification combines unit tests of pure logic, manual system
tests over a display matrix, and measurement protocols for latency and resource
use.

## 1.6 Technology choice

The comparison is qualitative; resource expectations for the paths not built
here come from their runtimes, not from measurements.

| Criterion | Python 3.14 + PyQt5 (chosen) | Electron + C++ helper (lolPing approach) | C# / WPF | AutoHotkey v2 |
| --- | --- | --- | --- | --- |
| Transparent always-on-top overlay | Native Qt flags and `QPainter` | Supported; heavier rendering stack | Native; some flags need Win32 interop | Limited |
| Global mouse/keyboard hook | pynput listener with supervisor | Needs a bundled native helper | Win32 hooks via P/Invoke | Built in |
| Custom 60 Hz painting | `QTimer` + antialiasing, adequate | Capable, but ships a browser runtime | Adequate | Poor for radial animation |
| Idle footprint | Moderate | Larger baseline | Moderate | Small |
| Development cost for this team | Low: prototype exists, team knows Python | High: JS + native addon + packaging | Medium-high: new language and UI stack | Low for a prototype, high for maintainability |
| Testability and packaging | Pure modules testable; PyInstaller | Native helper hard to isolate; electron-builder | xUnit; self-contained exe | Little unit-test tooling |

**Decision:** Python 3.14 with the pinned PyQt5 5.15.11 and pynput 1.8.2.
Qt supplies the frameless translucent window, custom painting, tray icon and
dialogs; pynput supplies global modifier and button detection. No new runtime
dependency is introduced, and the prototype is reused. The costs — Python
start-up and packaging — are covered by NFR-04 and the build documentation
rather than by changing stack.

## 1.7 Risks

| ID | Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- | --- |
| R1 | Overlay blocked by exclusive fullscreen or elevated windows | High | Medium | Document honestly; test borderless; report as a Windows limitation |
| R2 | Global input hook blocked or killed by security software | Medium | High | Supervisor restarts and logs; allow-listing guidance |
| R3 | 50 ms latency target missed | Medium | High | Measure at the end of week 2; pre-create the wheel; timer runs only while visible |
| R4 | DPI or multi-monitor geometry errors | Medium | Medium | Logical pixels per `QScreen`; matrix tests E1–E12 |
| R5 | Scope creep into game or multiplayer features | Medium | Medium | Binding out-of-scope table; no changes after week 3 |
| R6 | Parallel development conflicts | Medium | Low | File ownership and frozen interfaces; daily integration |
| R7 | Packaging differences or failure | Low | Medium | Build in week 3 and smoke-test the packaged build |

## 1.8 Timeline (four weeks)

| Week | Work | Milestone |
| --- | --- | --- |
| 1 | Freeze contract; package skeleton; `geometry` and `config` with unit tests; audit prototype | Contract signed off; pure logic tested |
| 2 | Input hook and supervisor; overlay wheel; commit and cancel; single instance | End-to-end ping sent and logged |
| 3 | Settings dialog; tray; JSONL logging; latency probe; autostart; DPI/multi-monitor; first latency run | Feature-complete build |
| 4 | Test matrix; performance runs; packaging; all documentation; evidence collection | Release candidate and evidence set |

## 1.9 Deliverables and evaluation

Deliverables: the `src/lolping/` package (v0.3.4), tests, build definition and
tools, `README.md` plus `docs/01`–`docs/07`, the evaluation evidence set, and
the final report structured by `docs/06-report-outline.md`.

| Objective | Method | Evidence |
| --- | --- | --- |
| O1 | Manual P1 test cases | Result table, screenshots |
| O2 | `--latency-probe` (100 gestures per environment); Task Manager sampling; five timed cold starts | Raw `latency.jsonl`, percentile table, captures |
| O3 | `pytest`; defect log; exit-criteria checklist | Test output, defect log |
| O4 | Observed walkthrough using only the user manual | Walkthrough notes |

Values not measured before submission are recorded as "TBD - measure" rather
than estimated.
