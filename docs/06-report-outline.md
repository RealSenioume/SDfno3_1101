# 6. Final report outline — lolping v0.3.0

Skeleton for the final report: each section lists the points to make and the
evidence behind them. Suggested length 6,000–8,000 words excluding appendices,
subject to the course brief. Only measured values from the evidence set may
appear; anything unmeasured is "TBD - measure" until it is replaced.

## Title page

- Title: *lolping: a desktop ping-wheel overlay for Windows*; subtitle
  *Requirements, design, implementation and evaluation of v0.3.0*.
- Authors and student IDs, course and module, supervisor, submission date.
- Version, repository location.

## Abstract (150–250 words)

- Problem: a fast radial label menu for the desktop, inspired by in-game pings.
- Approach: PyQt5 overlay, pynput input hook, eight configurable sectors,
  JSON config and JSONL logs.
- Measured results: latency p95, idle CPU/RAM, cold start (from the evidence).
- Honest limitation: overlays cannot cover exclusive fullscreen or elevated
  windows.

## 1 Introduction

- Radial menus and why direction selection is fast.
- The course prototype `pingWheel_BETA_v01_01.py` and what it lacked.
- Aim, objectives and scope in one paragraph each.
- Report structure.

## 2 Related work

- **darrenprx/lolPing** (MIT): Electron front end with a C++ input helper;
  broader scope, multi-platform and room-based features. Cite
  <https://github.com/darrenprx/lolPing> and its MIT licence.
- Position this project honestly: a smaller, Windows-only, single-user Python/Qt
  implementation with no multi-platform support and no rooms; the comparison is
  about scope, not superiority.
- The course prototype as direct prior art.
- Rejection of generic radial-menu and AutoHotkey-style tools: weak custom
  painting, weak testability, no structured settings or logging.
- Agreement on limitations: lolPing's documented problems with exclusive
  fullscreen and elevated windows match the limits observed here, supporting
  the claim that these are Windows constraints.

## 3 Requirements

- Stakeholders and the ten user stories in one table.
- Functional requirements grouped as in `docs/02-requirements.md`; reference the
  appendix instead of repeating all rows.
- Non-functional requirements and their thresholds, especially NFR-01 to NFR-04.
- Use case: main flow plus the five alternate flows.
- Traceability to `docs/04-test-plan.md`.

## 4 Design

- Three-layer architecture and the file-ownership split that enabled parallel
  development.
- Threading: pynput listener thread → queued Qt signals → GUI thread; supervisor
  thread for listener restarts; why no widget is touched from the hook thread.
- Data flow for one ping: trigger → overlay → hover → commit/cancel → mark →
  JSONL; include a sequence diagram.
- Geometry: clockwise angle convention, 45° sectors, dead-zone radius, logical
  pixels; include a sector-layout diagram.
- Overlay strategy: one window per `QScreen`, frameless/translucent/always-on-top,
  no focus activation, consumes mouse input.
- Configuration (tolerant load, atomic save, clamping) and failure handling
  (supervisor, guarded load, logging).
- Alternatives considered (Electron, C#/WPF, AutoHotkey) and the decision.

## 5 Implementation

- Sector resolution and angle wrapping; converting clockwise screen angles to
  Qt's counter-clockwise `drawPie` units.
- Wheel painting: antialiasing, per-sector weight animation, glow, centre disc,
  labels near 0.72 R, 60 Hz timer only while visible.
- Mark animation and fade over `mark_duration_ms`.
- Input hook: modifier/button matching, rebinding, supervisor.
- Settings dialog, validation and live application of changes.
- Bootstrap: DPI attributes, single instance, tray, ping logging, sound,
  `--latency-probe`, `--self-test`.
- Build and packaging; differences between packaged and script versions.
- Difficulties encountered and how they were resolved.

## 6 Testing and Evaluation

- Strategy and matrix E1–E12 summarised from `docs/04-test-plan.md`.
- Unit-test results and coverage of the pure modules.
- Manual results, defects by severity, fixes and residual issues.
- Latency: p50/p95/max `frame_ms` per environment against the 50 ms threshold;
  `commit_ms` reported separately.
- Resources: idle CPU, idle RAM, cold-start median, extended-run trend.
- Objective-by-objective table: target, measured value, verdict.
- Threats to validity: one reference machine, 95 samples per environment,
  stopwatch resolution, human variability, fullscreen not achievable.

## 7 Limitations

- Exclusive fullscreen and elevated windows (drawing and input restrictions).
- Dependence on a global hook; interference from security software; shortcut
  conflicts.
- Windows-only, Python start-up cost, fixed eight sectors, no game awareness.
- Evaluation limits: small samples, single machine.

## 8 Future work

- Configurable sector count and per-application profiles.
- Alternative overlay back ends for fullscreen scenarios.
- Cross-platform support and native packaging; installer, auto-update and code
  signing.
- Optional room or team features, separated from the core overlay.
- Ping-log analysis, keyboard-driven selection, font scaling, localisation.

## 9 Conclusion

- Whether the aim was met, citing the objective table.
- What was learned about overlay constraints, latency and parallel development
  against a frozen contract.
- Honest summary: a small, documented, tested Windows tool, not a product.

## References

Numbered in citation order, consistent style:

1. darrenprx, *lolPing*, GitHub, MIT licence,
   <https://github.com/darrenprx/lolPing>.
2. Riot Games, *League of Legends* (in-game pings as design inspiration),
   <https://www.leagueoflegends.com/>.
3. Riverbank Computing, *PyQt5 Reference Guide*,
   <https://www.riverbankcomputing.com/static/Docs/PyQt5/>.
4. *pynput documentation*, <https://pynput.readthedocs.io/>.
5. Python Software Foundation, *Python 3.14 documentation*,
   <https://docs.python.org/3.14/>.
6. Microsoft, *User Interface Privilege Isolation*,
   <https://learn.microsoft.com/en-us/windows/win32/secauthz/user-interface-privilege-isolation>.
7. The Qt Company, *QScreen* and *QPainter* references,
   <https://doc.qt.io/qt-5/>.
8. Course-provided prototype `pingWheel_BETA_v01_01.py` (unpublished course
   material).
9. Project repository: `README.md` and `docs/00`–`docs/07` (cited where the
   report would otherwise repeat them).

## Appendices

- **A** — Frozen interface contract (`docs/00-interfaces.md`).
- **B** — Full requirement tables.
- **C** — Manual test cases and completed results.
- **D** — Latency and resource data (summary tables plus raw JSONL).
- **E** — Build/run instructions and smoke-test output.
- **F** — User-walkthrough notes from the usability evaluation.

## Evidence to capture

| Evidence | Report section | Format / storage | When |
| --- | --- | --- | --- |
| Frozen interface contract | 4, Appendix A | `docs/00-interfaces.md` | End of week 1 |
| Architecture and sequence diagrams | 4 | `docs/figures/` (PNG/SVG) | During design |
| Unit-test output | 6, Appendix C | `evidence/unit-tests.txt` | Final run before submission |
| Manual results and defect log | 6, Appendix C | `evidence/manual-results.md`, `evidence/defects.md` | End of week 4 |
| Raw `latency.jsonl` and percentile summary | 6, Appendix D | `evidence/latency/` | Weeks 3–4 |
| CPU/RAM captures and cold-start sheet | 6, Appendix D | `evidence/perf/` | Week 4 |
| Screenshots: wheel, hover, mark, settings | 5–6 | `evidence/screens/` | Weeks 3–4 |
| Fullscreen and elevated-window observations | 6–7 | `evidence/limitations/` | Week 4 |
| User-walkthrough notes | 6.5, Appendix F | `evidence/walkthrough.md` | Week 4 |
| Packaged-build smoke-test output | 5, Appendix E | `evidence/smoke.txt` | Week 4 |

Two new pieces of evidence belong in this set: an icon sheet screenshot showing
all ten vector icons, and a waveform capture of the four synthesised cues.
Latency figures carried over from v0.2.0 must be re-measured on v0.3.0 before
they are cited.

## Writing notes

- Past tense for work done, present tense for delivered behaviour; "we" for the
  team.
- Insert numbers only from the evidence set; list any remaining "TBD - measure"
  in a short unresolved-items note.
- Number figures and tables and refer to them in the text; keep screenshots free
  of personal data.
- Never describe the tool as an in-game assistant, an API client or a
  communications service; it is a local overlay.
- Keep related work comparative and modest: explain scope differences, cite
  lolPing rather than paraphrasing it unattributed.
