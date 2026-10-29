English | [简体中文](README.zh-CN.md)

# lolping

A desktop ping-wheel overlay for Windows 11, in the visual style of the League
of Legends ping wheel. Hold a modifier key and a mouse button, drag toward one
of eight labelled sectors, and release. The wheel closes, a short burst confirms
the choice, and the ping is appended to a local log file.

**lolping is not an in-game tool.** It does not read or write League of Legends
memory, does not inject into or communicate with the game process, does not use
the Riot API, and opens no network connections. It is an ordinary desktop
overlay: it draws a translucent wheel at the mouse cursor and records the ping
the user picked in a local JSONL file.

The project ships no third-party artwork or audio. Slice icons are original
vector `QPainterPath` geometry generated in `src/lolping/assets.py`, and the
sound cues are synthesised in `src/lolping/sounds.py`, so the repository
contains no Riot Games assets and no binary media files.

- Version: **0.3.4**
- Platform: **Windows 11** (64-bit)
- Runtime: **Python 3.14**, **PyQt5 5.15.11**, **pynput 1.8.2**
- No other runtime dependencies, no network access at runtime
## Download

**Windows v0.3.4** - `lolping-0.3.4-win64.zip`, 36.3 MB, SHA-256
`f62ac07d6db020a5a1b8e2176fe5f018ea53c0c04ae1c64eb1f584b14925ead0`.
Unzip it into an empty folder and run `lolping\lolping.exe`; the `_internal`
folder must stay next to it. The executable is unsigned, so Windows SmartScreen
may ask for confirmation.

- [Download lolping-0.3.4-win64.zip](release/lolping-0.3.4-win64.zip)



## Features

- Two wheel skins: the original grey-and-gold look and a League-inspired
  `lol` theme (gold separators, outward light beams, centre medallion with
  PING / BACK). Slice icons may be replaced by local PNG files; the
  repository ships none (see `assets/icons/ICONS.md`).
- A click without dragging sends the centre (basic) ping; dragging and
  releasing inside the dead zone still cancels.
- Eight-sector radial menu, opened at the mouse cursor by a hold-and-drag
  gesture (default: hold **Alt + left mouse button**).
- Default sectors, clockwise from 3 o'clock: On My Way, All-In, Assist Me, Need
  Vision, Enemy Missing, Enemy Vision, Danger, Push. All eight are
  renameable.
- Every slice shows a vector icon: a default icon per sector, a choice of ten
  icon ids, and an optional custom PNG per slice. No Riot Games art is used.
- Short wheel-open animation (scale and fade over 130 ms). Committing plays a
  layered burst: two expanding rings, five directional streaks, an icon pop and
  the sector name.
- Four synthesised sound cues — open, hover tick, commit chime and cancel sweep.
  Sound is off by default; volume starts at 50%.
- Release outside the dead zone to commit; release inside the 34 px dead zone,
  press **Esc**, or click another mouse button to cancel.
- Configurable trigger: any combination of Ctrl/Alt/Shift/Win plus left, right,
  middle, X1 or X2 mouse button.
- Translucent, frameless, always-on-top wheel that does not steal focus from
  the window underneath. One overlay per monitor, positioned under the cursor.
- Settings dialog: wheel radius, dead zone, sector names, per-slice icon choice,
  icon size, show icons, animation speed, mark duration, sound, volume, hover
  ticks, a trigger on/off switch, pause hotkey, open settings at start-up, start with Windows, theme, reset to defaults.
- System-tray menu: Settings, Ping history log, Open config folder,
  Pause/Resume, Quit.
- Local JSONL log of every committed ping and an optional latency-probe mode.
- Tolerant configuration loading: a corrupt or hand-edited config falls back to
  defaults instead of preventing start-up.
- Single instance; optional start with Windows.

## Quick start

```powershell
git clone https://github.com/RealSenioume/SDfno3_1101
cd SDfno3_1101

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:PYTHONPATH = "src"   # run from the source tree without installing it
python -m lolping
```

Already have the files? Skip the first two lines and `cd` into the folder that
contains `src`, `requirements.txt` and `pyproject.toml`.

lolping starts in the system tray. Hold **Alt**, press and hold the **left
mouse button**, drag away from the cursor position, and release over the sector
you want. Press **Esc**, click the right mouse button, or release within the
dead zone to cancel. **Ctrl+Shift+Q** pauses or resumes pinging; quit from the tray menu.

A packaged executable can be built from source as described in
`docs/07-build-and-release.md`.

## Sending a ping

1. Hold **Alt** and press the **left mouse button**. The wheel appears where the
   cursor is.
2. Drag away from the centre. The sector under the cursor is emphasised, its
   icon grows and its name is shown in the centre.
3. Release the mouse button to commit. A burst is drawn at the wheel centre and
   one line is written to `pings.jsonl`.
4. To cancel, release the button within the dead zone (34 px by default), press
   **Esc**, or click the right mouse button while the wheel is open.

| Sector | Clock position | Default label | Default icon |
| --- | --- | --- | --- |
| 0 | 3 o'clock | On My Way | `on_my_way` |
| 1 | 4:30 | All-In | `all_in` |
| 2 | 6 o'clock | Assist Me | `assist` |
| 3 | 7:30 | Need Vision | `vision` |
| 4 | 9 o'clock | Enemy Missing | `missing` |
| 5 | 10:30 | Enemy Vision | `enemy_vision` |
| 6 | 12 o'clock | Danger | `danger` |
| 7 | 1:30 | Push | `push` |

The icon ids `danger` and `generic` are also available and can be assigned to
any slice in Settings. A custom PNG can replace a slice's icon; see
`docs/05-user-manual.md`.

## Command line

```text
python -m lolping [--config PATH] [--latency-probe] [--debug] [--self-test]
```

| Flag | Meaning |
| --- | --- |
| `--config PATH` | Use `PATH` instead of `%APPDATA%\lolping-desktop\config.json`. |
| `--latency-probe` | Record one line per gesture in `latency.jsonl` (`frame_ms`, `commit_ms`). Intended for measurements, not normal use. |
| `--debug` | Enable verbose diagnostic logging. |
| `--self-test` | Run the built-in headless self-test and exit; useful after installation. |

## Files

All user data lives in `%APPDATA%\lolping-desktop\`:

| File | Contents |
| --- | --- |
| `config.json` | Settings written by the Settings dialog. Created on first save; loaded tolerantly. |
| `pings.jsonl` | One JSON object per committed ping: `ts`, `sector`, `name`, `x`, `y`. |
| `latency.jsonl` | Written only with `--latency-probe`: `ts`, `frame_ms`, `commit_ms`. |
| `lolping.log` | Rolling diagnostic log; attach it when reporting a problem. |

## Documentation

| Document | Purpose |
| --- | --- |
| `docs/00-interfaces.md` | Frozen module interface contract (internal). |
| `docs/01-proposal.md` | Problem, objectives, scope, technology choice, risks, plan. |
| `docs/02-requirements.md` | User stories, functional and non-functional requirements, use cases. |
| `docs/03-design.md` | Design rationale and module descriptions (maintainers). |
| `docs/04-test-plan.md` | Test strategy, matrix, test cases, measurement protocols. |
| `docs/05-user-manual.md` | Installation, gesture, settings reference, troubleshooting. |
| `docs/06-report-outline.md` | Outline and evidence plan for the final report. |
| `docs/07-build-and-release.md` | Packaging and release steps. |
| `docs/08-report-draft.md` | Full report draft, with measurement placeholders marked TBD. |

## Limitations

- **Exclusive fullscreen.** Windows desktop overlays cannot normally be shown
  over an application that holds the display in exclusive fullscreen mode.
  Run the game in borderless or windowed mode if the wheel must be visible.
- **Elevated windows.** Under Windows User Interface Privilege Isolation, a
  normal-privilege lolping cannot draw over, or receive input from, windows
  running as administrator. Run lolping at the same or a higher integrity level
  when this is required.
- **Global input hooks.** Some security software restricts global mouse and
  keyboard hooks. lolping supervises and restarts a dead listener, but the
  application may need to be allow-listed.
- **Trigger conflicts.** Alt + left mouse button is used by some applications
  for their own shortcuts. The trigger is configurable; change it in Settings.
- **Sound overlap.** The Windows `winsound` API plays one asynchronous sound at
  a time, so a newer cue interrupts the previous one. For short cues this is a
  deliberate trade-off, not a defect.
- **Scope.** Windows only, fixed eight sectors in v0.3.4, no game awareness, no
  team or room features, no cross-platform support.

## License

MIT License. See the `LICENSE` file in the repository root.

## Riot Games disclaimer

This lolping is not endorsed by Riot Games and does not reflect the views or
opinions of Riot Games or anyone officially involved in producing or managing
League of Legends. League of Legends and Riot Games are trademarks or
registered trademarks of Riot Games, Inc.
