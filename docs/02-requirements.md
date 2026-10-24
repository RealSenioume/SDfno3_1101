# 2. Requirements — lolping v0.2.0

## 2.1 Purpose and conventions

This document states what lolping v0.2.0 must do. It derives from the frozen
module contract in `docs/00-interfaces.md` and is the reference for the design
(`docs/03-design.md`) and tests (`docs/04-test-plan.md`). "Must" marks a
mandatory requirement. Values that are not fixed yet are written as
**TBD - measure** rather than estimated.

## 2.2 Stakeholders

| Stakeholder | Interest |
| --- | --- |
| End user | A fast, unobtrusive ping wheel that matches the gesture |
| Student team (3 developers) | A specifiable scope deliverable in four weeks |
| Course assessor | Evidence of requirements, design, testing and evaluation |
| Tester / evaluator | Verifiable acceptance criteria and a repeatable matrix |
| Future maintainer | Documented behaviour and known limitations |

## 2.3 User stories

| ID | Story | Acceptance criteria |
| --- | --- | --- |
| US-01 | As a user, I want a radial menu to open where my cursor is. | Alt + left button shows an eight-sector wheel centred on the cursor without changing window focus. |
| US-02 | As a user, I want to send a ping by releasing over a sector. | Release outside the dead zone closes the wheel, shows a mark and logs the name. |
| US-03 | As a user, I want to cancel a ping started by accident. | Release in the dead zone, Esc, or another mouse button closes it with no ping and no log line. |
| US-04 | As a user, I want to rename the sectors. | Eight names are editable in Settings and appear on the wheel and in the log. |
| US-05 | As a user, I want to size the wheel and dead zone to my screen and hand. | Radius 60–400 px and dead zone 5 px to radius − 20 px; changes apply on the next gesture. |
| US-06 | As a user, I want to review what I pinged. | Every commit is appended to `pings.jsonl`; the tray menu opens the file. |
| US-07 | As a user, I want the tool to start with Windows and stay in the tray. | Autostart is optional; there is no main window and no taskbar button. |
| US-08 | As a user, I want to suspend the tool. | Pause makes the trigger inert; Resume restores it without a restart. |
| US-09 | As a user, I want an unambiguous way to quit. | Ctrl+Shift+Q (configurable) and the tray Quit entry terminate the app cleanly. |
| US-10 | As a developer/evaluator, I want to measure how fast the wheel appears. | `--latency-probe` writes `frame_ms` and `commit_ms` to `latency.jsonl`. |

## 2.4 Functional requirements

### 2.4.1 Trigger and wheel

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| FR-01 | `python -m lolping` starts the tray application. A second launch must not create a second instance: the new process exits and the running copy continues. | Two launches give one tray icon and one working instance; the second process ends without opening a wheel or crashing. |
| FR-02 | The wheel opens when every configured trigger modifier is held and the configured mouse button is pressed. Modifiers: Ctrl, Alt, Shift, Win; buttons: left, right, middle, X1, X2. Default: Alt + left. | The default gesture opens the wheel; after rebinding to Ctrl + right, the old gesture stops and the new one works. |
| FR-03 | The wheel has eight sectors: sector 0 at 3 o'clock, then clockwise every 45°, using the configured names. Beyond the dead zone, selection is by cursor angle only; there is no maximum drag distance. | Each clock direction commits the matching name (0 = On My Way … 7 = Push); long and short drags in the same direction commit the same sector. |
| FR-04 | The wheel is drawn in a frameless, translucent, always-on-top window on the screen under the cursor, centred on the cursor in that screen's logical pixels. Opening it must not activate or move focus from the window underneath, and the wheel must consume mouse input rather than being click-through. | With a windowed application focused, opening the wheel leaves it active and clicks over the wheel do not reach it. On two monitors the wheel appears on the cursor's monitor. |
| FR-05 | While the wheel is open, the sector under the cursor is emphasised and the centre disc shows its name. Rim labels are drawn near 0.72 R and can be hidden with `show_labels`. | Moving the cursor across sectors changes the emphasis and centre label; with `show_labels` off, rim text is absent. |

### 2.4.2 Commit and cancel

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| FR-06 | Releasing the trigger outside the dead zone commits the sector under the cursor at release: the wheel closes, a mark (expanding ring, dot, label) is drawn at the centre and fades over `mark_duration_ms`, and the commit is recorded. | Each sector commits its name; one mark per commit; the mark disappears after the configured duration. |
| FR-07 | Releasing the trigger inside the dead zone (default radius 34 px) cancels: no ping, no mark, no log line. | Press the trigger and release without dragging; `pings.jsonl` is unchanged. |
| FR-08 | Pressing Esc while the wheel is open cancels immediately: no ping, no log. Releasing the button afterwards has no effect. | Drag into a sector, press Esc: the wheel closes and nothing is logged. |
| FR-09 | Pressing the right or middle mouse button while the wheel is open cancels without committing, regardless of cursor position. | Drag into a sector while holding the trigger and right-click: the wheel closes and nothing is logged. |

### 2.4.3 Settings and configuration

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| FR-10 | Settings… opens a modal dialog with: trigger modifier checkboxes, mouse-button selector, radius slider, dead-zone slider, eight sector-name fields, animation-speed control, mark-duration control, sound checkbox, show-labels checkbox, quit-hotkey field, start-with-Windows checkbox, theme selector and Reset to defaults. OK applies, Cancel discards. | Every listed control is present and labelled; Cancel changes nothing; OK persists the edits. |
| FR-11 | Invalid input is handled in the dialog: numeric values clamp to documented ranges, malformed sector names or quit hotkeys give inline feedback, and the dialog never crashes. Reset to defaults restores section 2.4.5. | Slider extremes clamp; a malformed hotkey shows an inline message; Reset restores defaults. |
| FR-12 | Settings are stored as JSON at `%APPDATA%\lolping\config.json` (or `--config PATH`), saved atomically. Loading never raises: unknown keys ignored, wrong types defaulted, numbers clamped, sector list padded or truncated to eight. A missing or corrupt file starts with defaults. | Deleting or corrupting the file still starts the app; a save produces valid JSON; a three-name config loads with eight. |
| FR-13 | Accepted settings apply without a restart, including trigger and quit hotkeys. | Change the trigger to Ctrl + right: it works immediately. |
| FR-14 | A configurable global quit hotkey (default Ctrl+Shift+Q) quits cleanly; hotkey text is parsed and shown canonically. | Ctrl+Shift+Q exits the app; the tray icon disappears; no traceback. |
| FR-15 | When `start_with_windows` is enabled, the app registers to start at login; disabling removes the registration. Applied outside the dialog. Default off. | Enable, sign out and in: app starts in the tray; disable: no entry remains. |
| FR-16 | When `sound_enabled` is true (default off), a short cue plays on commit; cancelling is silent. | Sound on: commit cues, cancel does not; sound off: neither does. |

### 2.4.4 Logging, diagnostics and desktop integration

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| FR-17 | Every commit appends exactly one JSON object to `pings.jsonl` with `ts` (ISO 8601 local time with offset), `sector` (0–7), `name`, `x`, `y` (global logical cursor position). Cancels write nothing. | Three commits to three sectors give three correct lines; restart appends rather than truncates. |
| FR-18 | Only with `--latency-probe`, each gesture appends one line to `latency.jsonl` with `ts`, `frame_ms` (mouse-down callback to first painted frame) and `commit_ms` (mouse-down to mouse-up). Without the flag the file is not written. | With the flag, three gestures give three lines of positive values; without it the file is unchanged. |
| FR-19 | The CLI accepts `--config PATH`, `--latency-probe`, `--debug` and `--self-test`. `--debug` gives verbose logs; `--self-test` runs the built-in headless self-test (opens the wheel offscreen, commits a test ping, prints `SELF-TEST OK`) and exits before the tray application starts; unknown arguments produce a clear error. | Each flag behaves as described; `--self-test` exits with code 0 after printing `SELF-TEST OK`; `--help` lists the documented flags; an unknown flag is rejected with a readable message. |
| FR-20 | The tray icon offers Settings…, Ping history log, Open config folder, Pause/Resume and Quit. While paused, the trigger must not open the wheel; the menu entry shows the current state. | Pause: the gesture does nothing; Resume: it works; the other entries open the log and config folder. |
| FR-21 | Overlays are created lazily, one per screen, using each screen's logical geometry, and re-fitted when screens are added, removed or rescaled. The wheel opens on the cursor's screen. | On two monitors with different scaling the wheel is centred and correctly sized on the right monitor; disconnecting a monitor does not crash the app. |
| FR-22 | The `theme` setting selects the wheel palette: `gold` (default), `blue` or `red`. | Colour changes apply; the choice survives a restart. |

### 2.4.5 Documented defaults

| Setting | Default | Allowed values |
| --- | --- | --- |
| `trigger_modifiers` | `["alt"]` | Subset of Ctrl, Alt, Shift, Win |
| `trigger_mouse_button` | `left` | left, right, middle, x1, x2 |
| `wheel_radius` | 130 | 60–400 (logical px) |
| `dead_zone` | 34 | 5 to `wheel_radius − 20` |
| `sector_count` | 8 | fixed at 8 in v0.2.0 |
| `sectors` | On My Way, All-In, Assist Me, Need Vision, Enemy Missing, Enemy Vision, Retreat, Push | eight names |
| `animation_tau` | 0.035 | 0.005–0.5 |
| `mark_duration_ms` | 900 | 300–4000 |
| `sound_enabled` | false | true / false |
| `quit_hotkey` | `ctrl+shift+q` | modifiers + key |
| `start_with_windows` | false | true / false |
| `show_labels` | true | true / false |
| `theme` | `gold` | gold, blue, red |

## 2.5 Non-functional requirements

| ID | Requirement | Verification |
| --- | --- | --- |
| NFR-01 | `frame_ms` p95 ≤ 50 ms over 100 gestures in every core environment. | `--latency-probe`, protocol in `docs/04-test-plan.md`. |
| NFR-02 | Idle CPU below 1% average over a 60 s sample with only the tray icon present. | Task Manager / Resource Monitor. |
| NFR-03 | Idle RAM below 120 MB working set under the same conditions. | Task Manager. |
| NFR-04 | Cold start below 3 s from launch to a usable tray icon. | Five timed launches; median. |
| NFR-05 | No network access at runtime: no sockets, HTTP, DNS or telemetry. | Code review; network monitor. |
| NFR-06 | No interaction with the game process: no memory access, injection, Riot API or game-window reading. | Code review; contract. |
| NFR-07 | Robustness: hostile config never prevents start; a dead input listener is restarted and logged; screen changes, sleep/resume and rapid gestures do not crash. | Fault injection TC-20; supervisor review; soak PT-04. |
| NFR-08 | Compatibility: Windows 11; 100/125/150% scaling; one or two monitors; windowed, borderless and exclusive-fullscreen targets; normal and elevated targets. | Matrix E1–E12. |
| NFR-09 | Usability: all settings in one dialog with visible labels; Cancel changes nothing; user-visible strings in English. | Inspection; walkthrough. |
| NFR-10 | Privacy: data stays local; logs are plain files the user can inspect and delete; no telemetry. | Inspection; network monitor. |
| NFR-11 | Maintainability: public functions typed and documented; modules importable alone; pure logic free of Qt; `logging` instead of `print()`. | Code review; unit-test imports. |
| NFR-12 | Accessibility: Esc cancels from the keyboard; rim labels can be hidden without losing the centre label. | TC-06, TC-11. |

## 2.6 Use cases

**UC-01 — Send a ping (main success scenario).** Actor: user. Preconditions:
lolping is running, not paused, in an active desktop session.

1. The user holds Alt and presses the left mouse button.
2. The input hook recognises the trigger and reports the cursor position.
3. The overlay opens on the cursor's screen, centred on the cursor, without
   changing the focused window.
4. The user drags out; the hovered sector is emphasised and its name appears in
   the centre.
5. The user releases outside the dead zone.
6. The overlay resolves the sector, closes the wheel and draws a mark.
7. The application appends one JSON line and plays the sound if enabled.
8. Focus remains as it was in step 1.

Alternate flows:

- **A1 Commit.** Release outside the dead zone over sector *i*: ping *i* is
  logged; no maximum drag distance applies.
- **A2 Release inside the dead zone.** The wheel closes with no ping, mark or
  log line.
- **A3 Cancel with Esc.** The wheel closes immediately; a later release has no
  effect.
- **A4 Cancel with the right button.** Right or middle click closes the wheel
  without a ping, wherever the cursor is.
- **A5 Trigger while the wheel is open.** No second wheel appears and the
  existing one does not move; the extra press is ignored until the current
  gesture ends.

**UC-02 — Change a setting.** The user opens Settings, edits the radius and a
sector name and presses OK. `config.json` is saved atomically and the next
gesture uses the new values. Cancel saves nothing.

**UC-03 — Pause and resume.** Pause makes the trigger inert and the menu offers
Resume; Resume restores it. The ping log is unaffected.

**UC-04 — Quit.** Tray Quit or the quit hotkey stops timers, closes overlays,
stops the input listener and exits cleanly.

## 2.7 Scope

| Included | Excluded |
| --- | --- |
| Eight-sector wheel with configurable trigger | Game client integration, memory access, Riot API |
| Commit/cancel semantics and confirmation marks | Sector counts other than eight |
| Settings, JSON configuration, reset | Network, multiplayer, rooms, shared logs |
| Tray menu, pause/resume, quit hotkey, autostart | Cross-platform builds, installer, auto-update |
| Local ping and latency logs | In-game HUD, voice, champion or cooldown data |
| DPI- and multi-monitor-aware placement | Windows versions other than Windows 11 |

## 2.8 Constraints

- **C1:** Windows 11 x64 only.
- **C2:** Python 3.14, PyQt5 5.15.11, pynput 1.8.2; no new runtime dependencies.
- **C3:** No network access and no game-process interaction.
- **C4:** Normal operation needs no administrator rights; elevated targets remain
  a documented limitation.
- **C5:** Four-week delivery, three developers in parallel, file ownership and
  interfaces frozen in `docs/00-interfaces.md`.
- **C6:** All user-visible strings and documentation in English.
- **C7:** Overlay capability is bounded by Windows (UIPI, exclusive fullscreen).

## 2.9 Assumptions

- **A1:** Python 3.14 and the pinned packages are installed on test machines.
- **A2:** The app runs in an interactive desktop session, not as a service.
- **A3:** `%APPDATA%` is writable with space for the JSONL logs.
- **A4:** The default trigger is acceptable or the user remaps it.
- **A5:** Users expecting the overlay over a fullscreen application run that
  application in borderless or windowed mode.
- **A6:** Elevated targets are a known limitation, not a supported case.
- **A7:** Timestamps use local time and record its offset.

## 2.10 Glossary

| Term | Meaning |
| --- | --- |
| Commit | Releasing outside the dead zone to send the hovered sector's ping. |
| Dead zone | Inner circle around the centre (default 34 px); releasing inside cancels. |
| DPI scaling / logical pixels | Windows scaling (100/125/150%); Qt geometry uses scaled logical pixels. |
| Global hook | System-wide input listener (pynput) working regardless of focus. |
| JSONL | One JSON object per line. |
| `frame_ms` / `commit_ms` | Mouse-down to first painted frame / mouse-down to mouse-up. |
| Overlay | Frameless, translucent, always-on-top window drawing the wheel or a mark. |
| Ping | The chosen label recorded in the log. |
| Sector | One of eight 45° slices, numbered 0–7 clockwise from 3 o'clock. |
| Trigger | The configured modifier and mouse-button combination that opens the wheel. |
| UIPI | User Interface Privilege Isolation: lower-integrity processes cannot draw over or receive input from higher-integrity windows. |
| Exclusive fullscreen | A mode where an application owns the display, blocking desktop overlays. |

## 2.11 Traceability

Every FR and NFR is covered by test cases in `docs/04-test-plan.md`, which ends
with a requirement-to-test-case table. Unmeasured performance values remain
"TBD - measure" until that protocol has been executed.
