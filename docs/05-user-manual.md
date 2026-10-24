# 5. User manual — lolping v0.2.0

## 5.1 What lolping is

lolping is a Windows desktop tool that opens a radial menu of eight labels — a
"ping wheel" in the style of League of Legends — at the mouse cursor. You hold
a key combination, drag the mouse toward a label, and release. The wheel closes
and the choice is written to a local log file.

lolping does not connect to League of Legends: it does not read game memory,
does not use the Riot API and does not use the network. It only draws an overlay
and records what you selected.

## 5.2 Installation

### From source

1. Install **Python 3.14** from python.org. During installation, select "Add
   python.exe to PATH".
2. Open a terminal in the project folder, for example
   `D:\DSH_workspace\lolping`.
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
2. The wheel opens centred on the cursor. Drag away from the centre. The sector
   under the cursor is emphasised and its name appears in the middle.
3. Release the mouse button outside the dead zone to send the ping. A short
   mark confirms it at the wheel centre and one line is added to `pings.jsonl`.
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
| Open config folder | Opens `%APPDATA%\lolping\` in File Explorer. |
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
| Animation speed | Slider | 0.035 (`animation_tau`) | How quickly sectors and the wheel animate; lower values are snappier, higher values softer. Range 0.005 to 0.5. |
| Mark duration | Slider | 900 ms | How long the confirmation mark stays visible after a commit; 300 to 4000 ms. |
| Sound | Checkbox | Off | Plays a short cue when a ping is committed. Cancelling is always silent. |
| Quit hotkey | Text field | Ctrl+Shift+Q | Global shortcut that closes lolping. Enter it with plus signs, for example `Ctrl+Shift+Q`. |
| Start with Windows | Checkbox | Off | Registers lolping to start when you sign in to Windows. |
| Theme | Drop-down | Gold | Palette of the wheel: gold, blue or red. |
| Show labels | Checkbox | On | Draws the sector names around the rim. The centre label of the hovered sector stays visible. |
| Reset to defaults | Button | — | Restores all defaults in this table. |

If you want to edit settings without the interface, quit lolping and edit
`%APPDATA%\lolping\config.json`. Unknown or invalid values are ignored and
replaced by defaults the next time the file is loaded.

## 5.7 Command line

```text
python -m lolping [--config PATH] [--latency-probe] [--debug] [--self-test]
```

| Flag | Use |
| --- | --- |
| `--config PATH` | Load and save settings from `PATH` instead of `%APPDATA%\lolping\config.json`. Useful for testing or for a portable copy. |
| `--latency-probe` | Writes one line per gesture to `latency.jsonl` with the frame and commit times. Use it only for measurements; leaving it off keeps normal use lighter. |
| `--debug` | Writes more detailed diagnostic logging. Use it when reporting a problem. |
| `--self-test` | Runs the built-in headless self-test (the wheel is exercised offscreen, a test ping is committed and `SELF-TEST OK` is printed) and exits. Useful after installation to check that the configuration and overlay can start. |

## 5.8 Files and logs

All user data is stored in `%APPDATA%\lolping\` (normally
`C:\Users\<you>\AppData\Roaming\lolping\`):

| File | Contents |
| --- | --- |
| `config.json` | Your settings. Safe to back up or copy to another machine. |
| `pings.jsonl` | One line per committed ping: timestamp, sector number, name and cursor position. Cancelled gestures are not recorded. |
| `latency.jsonl` | Created only with `--latency-probe`: timestamp, `frame_ms` and `commit_ms` per gesture. |
| `lolping.log` | Rolling diagnostic log; attach it when reporting a problem. |

The files are plain text; you can open them in any editor, and you can delete
them at any time. The ping log contains the names you pinged, the time and the
screen position of each commit.

## 5.9 Troubleshooting

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
| No sound on commit. | Sound is off by default. Enable it in Settings and check the Windows volume mixer for the application. |
| Higher CPU or memory use than expected. | Measure while idle with only the tray icon present; close other copies in Task Manager. Report the numbers from Task Manager if the values exceed the documented limits. |
| Antivirus warns about a global keyboard hook. | Global input hooks are sometimes flagged heuristically. lolping is open source, uses no network and can be allow-listed; the warning is about the hook, not about modifying other programs. |

## 5.10 Uninstalling

1. Open the tray menu and choose **Settings…**; untick **Start with Windows**
   and press OK. Then choose **Quit**.
2. Delete the project folder (for example `D:\DSH_workspace\lolping`), or the
   folder containing the packaged executable.
3. Optionally delete `%APPDATA%\lolping\` to remove your settings and ping
   logs. Copy `pings.jsonl` first if you want to keep it.
4. If you removed the application before unticking "Start with Windows", open
   **Settings → Apps → Startup** (or Task Manager → Startup apps) and remove
   the lolping entry.

## 5.11 Privacy

lolping works entirely offline. It does not send telemetry, does not contact
any server and does not access the game. The only data it writes is what is
listed in section 5.8, and it stays on your machine.

## 5.12 Known limitations

- Exclusive-fullscreen applications and elevated windows can prevent the
  overlay from appearing (see Troubleshooting).
- lolping has eight fixed sectors in v0.2.0.
- Windows 11 only.
- It does not know about the game: the labels are generic and nothing is sent to
  teammates.
