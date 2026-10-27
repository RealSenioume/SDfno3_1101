# 4. Test plan — lolping v0.3.0

## 4.1 Purpose and scope

This plan describes how lolping v0.3.0 is verified against
`docs/02-requirements.md`: unit tests of the pure logic, system tests of the
complete application on a documented Windows matrix, and measurement protocols
for the non-functional requirements. Build verification is covered by
`tools/smoke_test.py` and `docs/07-build-and-release.md`.

## 4.2 Objectives

1. Every functional requirement (FR-01 to FR-28) is exercised by at least one
   test case.
2. All eight sectors and all three cancel paths behave correctly.
3. The application survives a hostile config, a second launch, screen changes
   and a dead input listener without crashing.
4. NFR-01 to NFR-04 are measured by a repeatable protocol and reported as
   p50/p95 values.
5. Icon drawing and sound synthesis overhead stay within NFR-13 and NFR-14.

## 4.3 Strategy

| Level | What | Method |
| --- | --- | --- |
| Unit | `geometry`, `config`, `hotkeys` | `pytest`, no Qt, no display |
| Integration | Log formats, config round-trip, single instance, probe mode | Scripted runs with `--config` in a temporary folder |
| System / manual | Gesture, settings, tray, displays | The test cases below on the environment matrix |
| Performance | Wheel latency, idle footprint, cold start | `--latency-probe`, Task Manager, timed launches |
| Robustness | Corrupt config, supervisor restart, monitor changes, soak | Fault injection and an extended run |

The tester is not the author of the module under test. A failure is logged with
the test-case ID, build, environment, reproduction steps and observed result.
**Severity:** S1 crash, data loss or an uncommittable ping; S2 wrong sector, a
broken cancel path or lost settings; S3 functional problem with a workaround;
S4 cosmetic or documentation issue.

## 4.4 Environment matrix

The full product is 3 display modes × 3 DPI settings × 2 monitor counts × 2
elevation states = 36 combinations. Twelve representative environments are
tested; other combinations are sampled when a defect suggests an untested axis.

| ID | Display mode | DPI | Monitors | Target app | Purpose |
| --- | --- | --- | --- | --- | --- |
| E1 | Windowed | 100% | 1 | Normal | Baseline; all functional cases |
| E2 | Windowed | 125% | 1 | Normal | Scaling |
| E3 | Windowed | 150% | 2 (second at 100%) | Normal | Scaling plus second monitor |
| E4 | Borderless | 100% | 2 (extended) | Normal | Borderless placement |
| E5 | Borderless | 125% | 1 | Normal | Borderless plus scaling |
| E6 | Borderless | 150% | 1 | Normal | Borderless plus scaling |
| E7 | Exclusive fullscreen | 100% | 1 | Normal | Record limitation behaviour |
| E8 | Exclusive fullscreen | 125% | 2 | Normal | Record limitation behaviour |
| E9 | Exclusive fullscreen | 150% | 1 | Normal | Record limitation behaviour |
| E10 | Windowed | 100% | 1 | Elevated | UIPI limitation |
| E11 | Borderless | 100% | 1 | Elevated | UIPI limitation |
| E12 | Exclusive fullscreen | 100% | 1 | Elevated | Combined limitation |

Reference machine: Windows 11 x64, Python 3.14, one GPU, AC power, Balanced
power plan, heavy applications closed during measurement.

**Execution rule.** Run every P1 case on E1 first, then the environment-sensitive
cases (TC-25 to TC-29) across E2–E12 as marked. Retest a defect in a second
environment to tell an environmental problem from a general one.

## 4.5 Unit tests

| ID | Module | Case | Expected |
| --- | --- | --- | --- |
| UT-G01 | geometry | `wrap_degrees` for -90, 0, 360, 450, -720 | Values in [0, 360); 450 → 90 |
| UT-G02 | geometry | `distance(3, 4)`; zero vector | 5.0; 0.0 |
| UT-G03 | geometry | `clamp` below, inside, above | low, value, high |
| UT-G04 | geometry | `sector_index` at 0, 10, 33 px | -1 (dead zone) |
| UT-G05 | geometry | `sector_index` right, down, left, up | 0, 2, 4, 6 |
| UT-G06 | geometry | `sector_index` at and between 45° steps | 0–7 in clockwise order |
| UT-G07 | geometry | `sector_center_angle` for all sectors | 0, 45, …, 315 |
| UT-G08 | geometry | `sector_span` bounds | 45° spans; adjacent spans share one edge; no overlap |
| UT-G09 | geometry | `sector_label_point` at 0.72 R | Point on the expected radius and angle |
| UT-G10 | geometry | `ease_alpha` at 0 and large dt; `approach` converges | 0, near 1; monotonic and snaps |
| UT-C01 | config | Defaults | Match requirements section 2.4.6 |
| UT-C02 | config | Save then load a modified config | Round-trip preserves fields |
| UT-C03 | config | Load a missing file | Defaults, no exception |
| UT-C04 | config | Load truncated or invalid JSON | Defaults, no exception |
| UT-C05 | config | Strings for numbers, radius 9999, dead zone 0, unknown theme | Clamped or defaulted; no exception |
| UT-C06 | config | Three and twelve sector names | Padded or truncated to eight |
| UT-C07 | config | Unknown JSON keys | Ignored; known fields load |
| UT-C08 | config | Atomic save | No temporary file left; clean replace |
| UT-C09 | config | Path helpers with `APPDATA` set | Config and logs under the app data folder |
| UT-C10 | config | v0.3 fields: icon ids, image paths, icon size, volume, cue flags | Defaults applied; bad icon id/path repaired; volume clamped to 0–1; arrays padded to eight |
| UT-H01 | hotkeys | `parse_hotkey("ctrl+shift+q")` | `{"ctrl", "shift", "q"}` |
| UT-H02 | hotkeys | Case and order independence | `"Alt+Q"` and `"q+alt"` equal |
| UT-H03 | hotkeys | `format_hotkey` of the default set | `"Ctrl+Shift+Q"` |
| IT-01 | logging | One commit writes one ping line | Valid JSON with `ts`, `sector`, `name`, `x`, `y`; none on cancel |
| IT-02 | logging | One gesture with `--latency-probe` | One line with `ts`, `frame_ms`, `commit_ms`; absent without the flag |
| IT-03 | logging | Two sessions append | Earlier ping lines preserved |

## 4.6 Manual test cases

### 4.6.1 Wheel interaction

| ID | Pri | Test | Steps | Expected |
| --- | --- | --- | --- | --- |
| TC-01 | P1 | Start-up and CLI | Run `python -m lolping`; check `--help`; run `--self-test`. | Tray icon appears within the cold-start budget; `--help` lists the documented flags; `--self-test` exits 0 after printing `SELF-TEST OK` with no visible overlay; no traceback. |
| TC-02 | P1 | Open at cursor | With a windowed app focused, hold Alt and the left button. | Wheel centred on the cursor, scaling and fading in over about 130 ms; hover matches the drag direction. |
| TC-03 | P1 | Commit every sector | For each clock direction, open, drag out, release, inspect the log. | Matching name and sector index logged; one burst per commit. |
| TC-04 | P1 | Hover feedback | Move the cursor through all sectors and into the dead zone. | Emphasis follows the cursor; centre label matches; no emphasis inside the dead zone. |
| TC-05 | P1 | Dead-zone cancel | Open and release without leaving the dead zone. | Wheel closes; no mark; no new log line. |
| TC-06 | P1 | Esc cancel | Open, drag into a sector, press Esc, then release. | Wheel closes on Esc; nothing logged; release has no effect. |
| TC-07 | P1 | Other-button cancel | Open, drag into a sector, right-click; repeat with middle click. | Wheel closes with no ping both times. |
| TC-08 | P2 | Trigger while open | Open the wheel and press the trigger again while holding. | No second wheel, no movement, no crash; the gesture still completes. |
| TC-09 | P1 | Focus and clicks | Open the wheel over Notepad and click a sector. | Notepad stays active and receives no overlay clicks. |
| TC-10 | P2 | Sector boundary | Approach a boundary from both sides and release repeatedly. | Selection changes once at the boundary; consistent and crash-free. |

### 4.6.2 Settings and configuration

| ID | Pri | Test | Steps | Expected |
| --- | --- | --- | --- | --- |
| TC-11 | P1 | Settings dialog | Inspect every control, including Show icons, Icon size, the per-slice icon choosers, Volume and Hover ticks; change radius, labels, theme, an icon and a name; OK. | All documented controls labelled; changes apply on the next wheel; the new name and icon are used. |
| TC-12 | P2 | Validation | Set slider extremes; enter a malformed quit hotkey; OK. | Values clamp to documented ranges; inline feedback; no crash. |
| TC-13 | P2 | Reset to defaults | Change settings, press Reset to defaults, OK. | All values return to the documented defaults. |
| TC-14 | P1 | Live rebind | Change the trigger to Ctrl + right; try the old and new gesture. | Only the new gesture works; no restart needed. |
| TC-15 | P1 | Quit hotkey | Press Ctrl+Shift+Q while another app has focus. | lolping exits; other app unaffected. |
| TC-16 | P2 | Cancel dialog | Change the radius, Cancel, reopen Settings. | Radius unchanged; no save. |
| TC-17 | P1 | Persistence | Change settings, quit, restart. | Values restored from `config.json`. |

### 4.6.3 Logs, diagnostics and tray

| ID | Pri | Test | Steps | Expected |
| --- | --- | --- | --- | --- |
| TC-18 | P1 | Ping log | Commit three pings to different sectors; inspect `pings.jsonl`. | Three well-formed lines with correct values and ISO 8601 timestamp with offset. |
| TC-19 | P1 | Latency probe | Run without the flag and commit; then run with `--latency-probe` and commit three. | File not written without the flag; three lines with positive values with it. |
| TC-20 | P1 | Corrupt config | Truncate `config.json`; start; replace with a JSON array; start. | Defaults used both times; no crash; valid file rewritten on next save. |
| TC-21 | P2 | Tray entries | Use Ping history log and Open config folder. | Log opens in the default viewer; config folder opens in Explorer. |
| TC-22 | P2 | Pause/resume | Pause, gesture, Resume, gesture. | Nothing opens while paused; the menu shows Resume; gesture restored. |
| TC-23 | P1 | Single instance | Launch a second `python -m lolping` while running. | Second process exits; one tray icon; running instance unaffected. |
| TC-24 | P2 | Sound cues | Enable sound; open, hover, commit and cancel; disable sound and repeat. | Each enabled cue plays once per event (hover once per slice change); the master switch silences all cues. |

### 4.6.4 Displays and robustness

| ID | Pri | Test | Steps | Expected |
| --- | --- | --- | --- | --- |
| TC-25 | P1 | Two monitors | On E4, open the wheel on each monitor in turn. | Wheel appears on the cursor's monitor, centred and correctly scaled. |
| TC-26 | P1 | DPI scaling | Repeat TC-02/TC-03 on E2, E3 and E6. | Wheel uses the configured radius and stays circular; record any clipping near screen edges. |
| TC-27 | P1 | Windowed and borderless | On E1 and E4, open and commit over a windowed and a borderless application. | Wheel and marks visible and correctly positioned. |
| TC-28 | P1 | Exclusive fullscreen | On E7–E9, start a fullscreen application and attempt the gesture. | Behaviour recorded (wheel visible or not); no crash or stuck wheel; limitation documented from this evidence. |
| TC-29 | P2 | Elevated target | On E10–E12, focus an elevated window and attempt the gesture; repeat with lolping elevated. | Behaviour recorded; no crash; documented as a limitation. |
| TC-30 | P2 | Autostart | Enable, sign out and in; disable and inspect the startup list. | App starts in the tray; disabling removes the entry. |

### 4.6.5 Slice icons, animations and sound

| ID | Pri | Test | Steps | Expected |
| --- | --- | --- | --- | --- |
| TC-31 | P1 | Every slice shows its icon | Open the wheel on E1 and inspect all eight slices. | Each slice shows its configured vector icon; the eight default icons are visually distinct; the hovered icon grows slightly. |
| TC-32 | P1 | Change an icon in Settings | In Settings assign `danger` to slice 0 and press OK; reopen the wheel and commit over slice 0. | Slice 0 shows the warning triangle immediately after OK; the burst icon pop shows the same icon. |
| TC-33 | P1 | Broken custom image | Quit, set `sector_images[3]` to a non-existent PNG, start and open the wheel; then repeat with a valid 64×64 PNG. | Missing file: slice 3 falls back to its vector icon with no crash and no blank slice. Valid file: the PNG appears clipped to a circle. |
| TC-34 | P2 | Hover ticks | Enable sound and Hover ticks, then move through five slices, pausing on each. | Exactly one tick per slice change (including entering the dead zone), not one per frame; disabling Hover ticks removes only the tick. |
| TC-35 | P1 | Volume 0 | Set volume to 0, then open, hover, commit and cancel. | No audible output from any cue; the wheel behaves normally. |
| TC-36 | P2 | Burst direction | Commit four pings in four different sectors and watch the burst each time. | The five streaks point outward along the committed slice's direction; two rings are visible, with the icon pop and the name above them. |

## 4.7 Performance protocols

### 4.7.1 Wheel latency (PT-01, NFR-01)

- **Measured values.** `frame_ms` (mouse-down hook callback to first painted
  wheel frame) and `commit_ms` (mouse-down to mouse-up), as defined in section 9
  of `docs/00-interfaces.md`.
- **Environments.** E1, E2, E4 and E6.
- **Sample.** 100 complete gestures per environment, about one every 3 s,
  covering all sectors; discard the first five as warm-up (95 measured).
- **Reporting.** p50, p95 and maximum of `frame_ms`; p50 and p95 of
  `commit_ms`, by nearest rank.
- **Acceptance.** `frame_ms` p95 ≤ 50 ms in every measured environment. No
  threshold applies to `commit_ms` (it contains human drag time); it is
  reported and sanity-checked to be no smaller than `frame_ms`.
- **Repeat rule.** Re-run a failing environment once on an idle machine; if it
  fails twice, record a failure with both raw files.

### 4.7.2 Idle footprint (PT-02, NFR-02 and NFR-03)

Start the app normally and leave it idle for 60 s without opening the wheel.
Record the CPU percentage at the end of the interval and the working-set memory
three times; keep the maximum. Acceptance: CPU below 1% average, memory below
120 MB. Screenshot the process with both columns.

### 4.7.3 Cold start (PT-03, NFR-04)

Five launches from the same state. Measure from pressing Enter on
`python -m lolping` to the tray icon becoming visible; use the `--debug` ready
marker if one exists, otherwise a stopwatch. Report the median (acceptance below
3 s) and the timing resolution (±0.2 s for a stopwatch).

### 4.7.4 Extended run (PT-04)

Run for 30 minutes while committing 50 pings at random intervals and switching
between applications. Record the working set every 5 minutes and note crashes,
stuck wheels or missing log lines. No numeric threshold; report the growth trend
and crash count.

### 4.7.5 Icon and sound cost (PT-05, NFR-13 and NFR-14)

- **Icon frame cost.** Open the wheel on E1 with `--latency-probe` and record 20
  gestures with `show_icons` on and 20 with it off; the p95 difference in
  `frame_ms` is the icon cost, which must stay within 5 ms. A frame-timing
  harness in a debug build may be used instead of the user-visible probe.
- **Synthesis cost.** In a Python session, call `sounds.render_wav` for each cue
  after `sounds.clear_cache()` and time the first call; repeat the call to time
  the cached path. The cold call must be below 5 ms and the cached call
  effectively free. Record both tables in the evidence set.

## 4.8 Evidence to capture

| ID | Evidence | Produced by | Storage |
| --- | --- | --- | --- |
| EVID-01 | Unit-test output (all pass) | `pytest` | `evidence/unit-tests.txt` |
| EVID-02 | Manual results table with dates and environment IDs | Tester | `evidence/manual-results.md` |
| EVID-03 | Screenshots: wheel, hover, burst, settings | Tester | `evidence/screens/` |
| EVID-04 | Raw `latency.jsonl` per environment plus percentile summary | Probe, `tools/latency_report.py` | `evidence/latency/` |
| EVID-05 | Task Manager CPU/RAM captures and cold-start sheet | Tester | `evidence/perf/` |
| EVID-06 | Sample `pings.jsonl` with 20+ commits | Application | `evidence/logs/` |
| EVID-07 | Screenshots and notes for E7–E12 | Tester | `evidence/limitations/` |
| EVID-08 | Smoke-test output of the packaged build | `tools/smoke_test.py` | `evidence/smoke.txt` |
| EVID-09 | Optional screen recording of the gesture | Tester | `evidence/gesture.mp4` |
| EVID-10 | Icon sheet screenshot: all ten vector icons at default and large size | Tester | `evidence/screens/icons.png` |
| EVID-11 | Waveform capture of the four synthesised cues | Audio editor or generated plot | `evidence/audio/cues.png` |

Files and screenshots are named with the environment ID and date (for example
`E2-wheel-125dpi.png`). The evidence folder is collected for the report and is
not part of the source deliverable.

## 4.9 Entry and exit criteria

**Entry:** the build starts on E1 and the tray icon works; the interface contract
is frozen; the matrix machines are available; the unit tests exist and run; this
plan has been reviewed.

**Exit:** all P1 cases pass; no S1 or S2 defect is open; every S3 defect has a
documented workaround; NFR-01 to NFR-04 and NFR-13/NFR-14 are measured and meet
their thresholds; the evidence checklist is complete; results are summarised for
section 6 of the report.

## 4.10 Traceability

| Requirements | Test cases |
| --- | --- |
| FR-01, FR-19 | TC-01, TC-19, TC-23 |
| FR-02, FR-03, FR-04, FR-05 | TC-02, TC-03, TC-04, TC-10, TC-25, TC-26 |
| FR-06 | TC-03 |
| FR-07, FR-08, FR-09 | TC-05, TC-06, TC-07 |
| FR-10, FR-11, FR-13 | TC-11, TC-12, TC-13, TC-14, TC-16 |
| FR-12 | TC-17, TC-20 |
| FR-14 | TC-15 |
| FR-15 | TC-30 |
| FR-16 | TC-24 |
| FR-17, FR-18 | TC-18, TC-19; IT-01, IT-02 |
| FR-20 | TC-21, TC-22 |
| FR-21 | TC-25, TC-26 |
| FR-22 | TC-11 |
| NFR-01 | PT-01 (4.7.1) |
| NFR-02, NFR-03 | PT-02 (4.7.2) |
| NFR-04 | PT-03 (4.7.3) |
| NFR-05, NFR-06 | Code review and process/network inspection during TC-03 |
| NFR-07 | TC-08, TC-20, PT-04 |
| NFR-08 | E1–E12 across TC-25 to TC-29 |
| NFR-09, NFR-10 | Inspection during TC-11 and TC-21 |
| NFR-11 | UT-G01 to UT-H03, IT-01 to IT-03 |
| NFR-12 | TC-06, TC-11 |
| FR-23, FR-24 | TC-31, TC-32, TC-33 |
| FR-25 | TC-02 |
| FR-26 | TC-03, TC-36 |
| FR-27 | TC-24, TC-34 |
| FR-28 | TC-35 |
| NFR-13, NFR-14 | PT-05 (4.7.5) |
