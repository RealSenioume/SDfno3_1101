# 5. User manual — lolping v0.3.0

## 5.1 What lolping is

lolping is a Windows desktop tool that opens a radial menu of eight labelled,
icon-bearing sectors — a "ping wheel" in the style of League of Legends — at the
mouse cursor. You hold a key combination, drag the mouse toward a label, and
release. The wheel closes, a short burst confirms the choice, and the choice is
written to a local log file.

lolping does not connect to League of Legends: it does not read game memory,
does not use the Riot API and does not use the network. It only draws an overlay
and records what you selected.

All slice icons are original vector drawings and all sound cues are synthesised
by the application at run time; no Riot Games artwork or audio is included.

## 5.2 Installation

### From source

1. Install **Python 3.14** from python.org. During installation, select "Add
   python.exe to PATH".
2. Open a terminal in the repository folder (the one you cloned).
3. Create and activate a virtual environment, then install the pinned
   dependencies:

   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

   This installs PyQt5 5.15.11 and pynput 1.8.2.
4. Start the application:

   ```bat
   python -m lolping
   ```

No administrator rights are needed for normal use. See
`docs/07-build-and-release.md` for the packaged executable if you do not want to
install Python.

## 5.3 First run

After starting, lolping has no main window. It appears as an icon in the Windows
notification area (the tray). The first time it runs, it uses the built-in
defaults listed in section 5.6; `config.json` is created the first time you
press OK in the Settings dialog.

The tray icon is the only permanent part of the interface. If you cannot see
it, click the small arrow in the tray to show hidden icons.

## 5.4 Sending a ping

1. Hold **Alt** and press the **left mouse button** anywhere on the desktop.
2. The wheel opens centred on the cursor with a short scale-and-fade. Drag away
   from the centre. The sector under the cursor is emphasised, its icon grows
   and its name appears in the middle.
3. Release the mouse button outside the dead zone to send the ping. A burst
   (two rings, five streaks along the slice direction, an icon pop and the
   name) confirms it at the wheel centre, and one line is added to
   `pings.jsonl`.
4. To cancel, do any of the following while the wheel is open:
   - release the mouse button within the dead zone (the inner circle,
     34 px by default);
   - press **Esc**;
   - click the right mouse button.

The wheel has eight sectors, clockwise from 3 o'clock:

| Sector | Position | Default label |
| --- | --- | --- |
| 0 | 3 o'clock | On My Way |
| 1 | 4:30 | All-In |
| 2 | 6 o'clock | Assist Me |
| 3 | 7:30 | Need Vision |
| 4 | 9 o'clock | Enemy Missing |
| 5 | 10:30 | Enemy Vision |
| 6 | 12 o'clock | Retreat |
| 7 | 1:30 | Push |

Only the direction matters: after leaving the dead zone, releasing at any
distance commits the sector in that direction. On a multi-monitor setup the
wheel opens on the monitor where the cursor is.

All eight names can be changed in Settings.

## 5.5 The tray menu

| Entry | What it does |
| --- | --- |
| Settings… | Opens the settings dialog (5.6). |
| Ping history log | Opens `pings.jsonl` in your default text editor. |
| Open config folder | Opens `%APPDATA%\lolping-desktop\` in File Explorer. |
| Pause / Resume | Stops or restores the trigger gesture. The menu shows the next action. |
| Quit | Closes lolping, including its overlay and input listener. |

The configured quit hotkey (default **Ctrl+Shift+Q**) also closes the
application from any window.

## 5.6 Settings

Open **Settings…** from the tray menu. Changes are applied when you press OK;
Cancel discards them. **Reset to defaults** restores every value below.

| Setting | Control | Default | Explanation |
| --- | --- | --- | --- |
| Trigger modifiers | Checkboxes: Ctrl, Alt, Shift, Win | Alt | The wheel opens only while every ticked modifier is held. |
| Trigger button | Mouse-button selector | Left | The button that opens the wheel: left, right, middle, X1 or X2. |
| Wheel radius | Slider | 130 | Outer radius of the wheel in logical pixels; 60 to 400. |
| Dead zone | Slider | 34 | Radius of the inner circle in logical pixels; releasing inside it cancels. Range 5 to the wheel radius minus 20. |
| Sector names | Eight text fields | On My Way … Push | The labels shown on the wheel and written to the log. Keep them short for legibility. |
| Slice icons | One chooser per slice | arrow, double chevron, plus, eye, question mark, slashed eye, back arrow, push arrow | The vector icon for each slice. Ten ids are available: `on_my_way`, `all_in`, `assist`, `vision`, `missing`, `enemy_vision`, `retreat`, `push`, `danger`, `generic`. |
| Show icons | Checkbox | On | Draws slice icons. Turning it off hides both the vector and custom icons and moves the rim labels inward. |
| Icon size | Slider | 30 | Icon size in logical pixels; 12 to 64. |
| Animation speed | Slider | 0.035 (`animation_tau`) | How quickly sectors and the wheel animate; lower values are snappier, higher values softer. Range 0.005 to 0.5. |
| Mark duration | Slider | 900 ms | How long the confirmation mark stays visible after a commit; 300 to 4000 ms. |
| Enable sounds | Checkbox | Off | Master switch for all sound cues. |
| Volume | Slider | 50 % | Loudness of every cue; 0 % is silent. |
| Hover ticks | Checkbox | On | Plays the short tick when the highlighted slice changes. |
| Quit hotkey | Text field | Ctrl+Shift+Q | Global shortcut that closes lolping. Enter it with plus signs, for example `Ctrl+Shift+Q`. |
| Start with Windows | Checkbox | Off | Registers lolping to start when you sign in to Windows. |
| Theme | Drop-down | Gold | Palette of the wheel: gold, blue or red. |
| Show labels | Checkbox | On | Draws the sector names around the rim. The centre label of the hovered sector stays visible. |
| Reset to defaults | Button | — | Restores all defaults in this table. |

If you want to edit settings without the interface, quit lolping and edit
`%APPDATA%\lolping-desktop\config.json`. Unknown or invalid values are ignored and
replaced by defaults the next time the file is loaded.

## 5.7 Custom slice icons

The vector icons cover the common cases; if you want your own artwork on a
slice, point its `sector_images` entry at a PNG file. The settings dialog edits
the vector icon choice, not the PNG path, so this is a small `config.json` edit.

1. Make or choose a square PNG, ideally 64 × 64 px. Larger images are scaled
   down and transparency is supported; the image is clipped to a circle.
2. Quit lolping so it cannot overwrite your edit when it saves settings.
3. Open `%APPDATA%\lolping-desktop\config.json` in a text editor.
4. Set the entry for the slice in `sector_images` (0–7, clockwise from
   3 o'clock) to the full path of the file. Use doubled backslashes because the
   file is JSON:

   ```json
   "sector_images": ["", "", "C:\\Users\\you\\Pictures\\assist.png", "", "", "", "", ""]
   ```

   This example replaces the icon of slice 2 (Assist Me).
5. Start lolping and open the wheel. The PNG is drawn at the slice's icon
   position, clipped to a circle, and is also used in the burst when that slice
   is committed.
6. To go back to the vector icon, set the entry to `""` again.

Relative paths are resolved against lolping's working directory, so absolute
paths are recommended. If a path is wrong, the file is unreadable or it is not
an image, the slice falls back to its vector icon; nothing crashes and no slice
is left blank. Custom images are only drawn while **Show icons** is ticked.

## 5.8 Sound

lolping can play four short cues, all generated by the application; no audio
files are installed:

| Cue | When it plays | Character |
| --- | --- | --- |
| Open | the wheel opens | short rising blip |
| Hover | the highlighted slice changes | very short high tick |
| Commit | a ping is committed | two-note chime; the pitch follows the slice |
| Cancel | a gesture is cancelled | downward sweep |

Sound is off by default. In Settings, **Enable sounds** is the master switch,
**Volume** sets the loudness of all cues (0 % is silent), and **Hover ticks**
switches only the hover cue; clearing it keeps the open, commit and cancel
cues. The advanced keys `sound_on_open`, `sound_on_commit` and
`sound_on_cancel` in `config.json` switch the other cues individually.

The Windows `winsound` API plays one asynchronous cue at a time: starting a new
cue stops the previous one. With cues of a few tens of milliseconds this is
intentional and normally inaudible; it is not a fault.

## 5.9 Command line

```text
python -m lolping [--config PATH] [--latency-probe] [--debug] [--self-test]
```

| Flag | Use |
| --- | --- |
| `--config PATH` | Load and save settings from `PATH` instead of `%APPDATA%\lolping-desktop\config.json`. Useful for testing or for a portable copy. |
| `--latency-probe` | Writes one line per gesture to `latency.jsonl` with the frame and commit times. Use it only for measurements; leaving it off keeps normal use lighter. |
| `--debug` | Writes more detailed diagnostic logging. Use it when reporting a problem. |
| `--self-test` | Runs the built-in headless self-test (the wheel is exercised offscreen, a test ping is committed and `SELF-TEST OK` is printed) and exits. Useful after installation to check that the configuration and overlay can start. |

## 5.10 Files and logs

All user data is stored in `%APPDATA%\lolping-desktop\` (normally
`C:\Users\<you>\AppData\Roaming\lolping-desktop\`):

| File | Contents |
| --- | --- |
| `config.json` | Your settings. Safe to back up or copy to another machine. |
| `pings.jsonl` | One line per committed ping: timestamp, sector number, name and cursor position. Cancelled gestures are not recorded. |
| `latency.jsonl` | Created only with `--latency-probe`: timestamp, `frame_ms` and `commit_ms` per gesture. |
| `lolping.log` | Rolling diagnostic log; attach it when reporting a problem. |

The files are plain text; you can open them in any editor, and you can delete
them at any time. The ping log contains the names you pinged, the time and the
screen position of each commit.

## 5.11 Troubleshooting

| Problem | Cause and what to do |
| --- | --- |
| Nothing appears over a fullscreen game. | Desktop overlays cannot be drawn over exclusive-fullscreen applications. Set the game to borderless or windowed mode. This is a documented limitation, not a fault in your settings. |
| Nothing appears over an administrator window. | Windows User Interface Privilege Isolation blocks normal-privilege overlays over elevated windows and their input. Run lolping with the same or higher privileges as the target, or use a non-elevated window. |
| The trigger works in some applications but not others. | The other window is probably elevated (see above). Close it or run lolping elevated, then try again in a normal window to confirm lolping itself works. |
| Alt + left click conflicts with an application shortcut. | Open Settings and choose another trigger (for example Ctrl + right button or a side mouse button). |
| The quit hotkey or another Windows shortcut conflicts. | Choose a different quit hotkey in Settings. Some Windows-key combinations are reserved by the operating system and cannot be overridden. |
| The wheel opens but no ping is logged. | Only commits are logged. Make sure you release outside the dead zone and that `%APPDATA%` is writable. Check `pings.jsonl` in the config folder. |
| Starting lolping a second time does nothing. | Only one instance runs. The existing copy is already in the tray; use its menu. |
| The tray icon is missing. | It may be in the hidden-icons overflow. If the process is not in Task Manager, start lolping again. |
| The mouse or keyboard stops responding to lolping. | The input listener is supervised and restarted automatically. If it still fails (for example after a UAC prompt or sleep), quit and restart lolping. Security software that blocks global hooks may need lolping allow-listed. |
| Settings do not survive a restart. | The config folder may not be writable, or `config.json` is corrupt and was replaced by defaults. Check the folder permissions; delete the file to start from defaults. |
| The wheel opens on the wrong monitor or at the wrong size. | Open the wheel with the cursor on the intended monitor; scaling is read per monitor. If the problem persists, note your display layout, scaling percentages and monitor count when reporting it. |
| No sound at all. | Sound is off by default; enable it in Settings and set Volume above 0 %. Also check that Windows has an audio output device and that lolping is not muted in the Windows volume mixer. |
| A slice shows the vector icon instead of my custom PNG. | The `sector_images` path is wrong, the file is not a readable PNG, or the index is not the slice you meant. Use a full absolute path with doubled backslashes in `config.json`; a broken path falls back to the vector icon by design. |
| Sound cues cut each other off. | Windows `winsound` plays one asynchronous cue at a time: a new cue stops the previous one. This is a documented trade-off, not a fault. |
| Higher CPU or memory use than expected. | Measure while idle with only the tray icon present; close other copies in Task Manager. Report the numbers from Task Manager if the values exceed the documented limits. |
| Antivirus warns about a global keyboard hook. | Global input hooks are sometimes flagged heuristically. lolping is open source, uses no network and can be allow-listed; the warning is about the hook, not about modifying other programs. |

## 5.12 Uninstalling

1. Open the tray menu and choose **Settings…**; untick **Start with Windows**
   and press OK. Then choose **Quit**.
2. Delete the project folder (the one you cloned), or the
   folder containing the packaged executable.
3. Optionally delete `%APPDATA%\lolping-desktop\` to remove your settings and ping
   logs. Copy `pings.jsonl` first if you want to keep it.
4. If you removed the application before unticking "Start with Windows", open
   **Settings → Apps → Startup** (or Task Manager → Startup apps) and remove
   the lolping entry.

## 5.13 Privacy

lolping works entirely offline. It does not send telemetry, does not contact
any server and does not access the game. The only data it writes is what is
listed in section 5.10, and it stays on your machine.

## 5.14 Known limitations

- Exclusive-fullscreen applications and elevated windows can prevent the
  overlay from appearing (see Troubleshooting).
- lolping has eight fixed sectors in v0.3.0.
- Sound cues cannot overlap: a new cue stops the previous one (see section 5.8).
- Windows 11 only.
- It does not know about the game: the labels are generic and nothing is sent to
  teammates.
