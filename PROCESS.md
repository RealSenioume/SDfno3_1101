English | [简体中文](PROCESS.zh-CN.md)

# An initial idea for creating a LOLping tool outside the game.
- Using DeepSeek to build the foundation of this app,
but it didn't provide any variable-modification interface.
All I can do is change the variable inside the raw code.
And after running the raw code, there is no quick-exit hotkey or interface to exit.

- 10.22.2026

# Testing BETA v01
- When pressing Alt alone, nothing happens. Tapping Alt lightly also has no side effects.

- Alt + left-click: The roulette wheel appears at the clicked position.
Hold down the left button and drag the mouse: the highlighted sector will follow. At this point, release Alt, and the wheel should continue to display.
Release the left button: The terminal prints the corresponding signal name, and the roulette wheel disappears.
Alt + left-click and release without dragging: In the dead zone, no signal is triggered.

- Rapidly and consecutively clicking the left button (holding down Alt): It will only activate on the first click, and the second click will not activate repeatedly; it will be submitted once when released.
Press the left button first and then Alt: The roulette wheel should not be triggered (because is_alt_held() is still False when on_click is triggered).
Meanwhile, I noticed a bug: sometimes the wheel appears one frame in the previous position when I wake it up.

# BETA v01_01
- This is not a bug in the drawing logic, but a timing issue with the display of the Windows Composer (DWM).

- self.show() will make the window "visible" first, and then Qt will dispatch the paintEvent. Between these two events, there is a short period of time where the window displays the previous backing store content (the roulette wheel in its old position), and then the new frame will overwrite it. I first change self.center in start_at(), and then call show(), but show() does not guarantee synchronous redrawing, so the old content will leak out for 1 frame.

- At meantime, I asked Deepseek WEB to add one more function - when the wheel is aweak, mouse stop interactive with other thing. However, this version that Deepseek provided didn't work.

- Due to pynput's support for keyboard event suppression on Windows but not for mouse event suppression, there is a window of a few milliseconds for mouse events before the wheel is activated. When the user quickly clicks with Alt+left button, the underlying application may receive an input of "pressed but not released". The program minimizes this gap by compressing the event polling interval to 2ms, but it cannot be completely eliminated. This is a platform limitation of third-party input monitoring libraries, rather than a logical flaw in the program.

- 10.22.2026

# DSH intervenes in development
For more details during development, check out the docs.

- 10.24.2026

# V0.3.0 Update
- Now it has animations and sound effects that can be used for demonstrations. However, to avoid potential copyright issues, animations, textures, sound effects, and other related content are all generated using DSH (DeepSeek Harness).

- By the way, I adjusted the temporary storage path left in the document when DSH runs locally.

- 10.27.2026

# V0.3.1 Update
- Woooooooow, Major update is here. Now, trigger gesture will not affect other object, icon, etc on the windows.

- Fixed the biggest usability problem: the trigger gesture no longer touches anything on the desktop. It took three attempts, and the first two were wrong in a useful way.

- Attempt 1: as soon as the wheel opened I called SetCapture so that the window underneath would get WM_CAPTURECHANGED and cancel whatever it started. This helped sometimes but not always.

- Attempt 2: I measured the first wheel of a session at 103.57 ms against about 5 ms for every later one, so the desktop had ~100 ms to start a rubber-band selection or an icon drag before my capture arrived. I moved that cost to start-up by pre-creating and pre-painting one window per screen at launch. The first gesture became as fast as the others, but the bug was still there: with a 1000 Hz mouse, even a 2 ms window still gets a move event. This is the point where "just make it faster" stopped being a valid plan.

- Attempt 3 (the fix): a native low-level mouse hook (WH_MOUSE_LL) that returns 1 and drops the events before any window sees them. It has to be installed BEFORE pynput, because Windows calls the most recently installed hook first - so pynput still sees the gesture and the guard removes it from everything below. The cost is that Alt + click is now reserved for lolping while it runs; there is a "Reserve the trigger for lolping" checkbox in Settings to turn this off and go back to the old behaviour.

- Also fixed: sound never played. winsound refuses SND_MEMORY together with SND_ASYNC ("Cannot play asynchronously from memory"), and playing synchronously from memory would freeze the wheel, so the generated WAV is now written once to a temp cache file and played by filename.

- Also fixed: a tray double-click opened two settings windows stacked on each other, because Windows sends Trigger and then DoubleClick. Now only DoubleClick opens the window, and the handler refuses to re-enter.

- Moved the data folder from %APPDATA%\lolping to %APPDATA%\lolping-desktop, because the installed reference app already owns the old folder name. Also rewrote the README quick start: no hard-coded local path any more, and it now includes the PYTHONPATH step that the old one was missing (the old instructions actually did not run).

- Version strings in the docs were a mess (some still said 0.2.0), so everything now says 0.3.1. Unit tests: 134, all passing.

- 10.27.2026

# The importance of information synchronization!!!

- Some additional content that I want to roast, there are some restricted content (such as some specific files that can only be modified through me) or content that has undergone additional manual modification. 
- If these are not raised or synchronized with DSH at the beginning, DSH may perform overwrite operations during subsequent intervention. And these inconspicuous behaviors, if not intervened in a timely manner, may gradually accumulate into the "code mountain of sh*t" that we often mention.

- 10.27.2026

# V0.3.1 Latency Re-measurement
- Re-measured the trigger-to-first-paint latency on the 0.3.1 build, now that the start-up warm-up and the native mouse guard are in. Same harness as before: one machine, 30 scripted gestures.

- The first gesture of a session used to cost 103.57 ms. It now costs 15.05 ms, a 6.9x reduction. That 100 ms was never a property of the system, it was a cost I had simply not paid at the right time: the first wheel had to create the native surface and load the font database and the glyph cache while the user was already waiting. Paying it at launch took it out of the gesture.

- Steady state is unchanged: 28 of the 30 samples sit between 4.54 and 6.08 ms, median 5.20 ms. p95 is 15.05 ms with the first gesture included and 6.08 ms without it, against a 50 ms target.

- Two samples still sit near 15 ms: the first gesture, and the one immediately after a cancelled gesture. Both are still three times under the target. I did not chase the second one; it looks like the first paint occasionally lands while the window is still compositing the previous state.

- The comparison with the 0.3.0 run is only meaningful for the first gesture. The steady-state p95 moved from 5.49 to 6.08 ms, which is inside run-to-run noise, so I am not claiming it as a regression - the extra mouse-hook callback is the only new work on that path.

- Kept both old runs as control data: latency-v0.3.0.jsonl (before the warm-up) and latency-v0.2.0.jsonl (before the icons and audio). They are what makes the "103.57 -> 15.05 ms" claim checkable instead of just asserted.

- 10.27.2026

# V0.3.2 Update
- Reworked the wheel's appearance against the in-game reference I use every day: a barely-there disc, eight gold separators, light beams that spill past the rim, and a centre medallion with PING and a BACK hint. It ships as an optional `lol` theme; the original three themes are untouched.

- The icons were the part I could not simply copy. The reference art belongs to Riot, and this project has promised since the first commit to ship no third-party artwork. So the mechanism ships and the artwork does not: slice icons load from `assets/icons/<id>.png` on my own disk, that folder is git-ignored, and a missing file falls back to the vector icon. A fresh clone still works; it just looks like ours rather than theirs.

- Moved the default sectors to match the reference layout: 12 o'clock is Danger now, not Retreat. Same eight positions, so the muscle memory from the game transfers instead of fighting me.

- Added the interaction the wheel was actually missing: a click without dragging sends the basic centre ping. The threshold is measured on the greatest distance the pointer travelled, not on where it was released, otherwise a drag that comes back to the middle would be mistaken for a click.

- Measured the new skin rather than assuming it was free: p95 7.41 ms against 6.08 ms before, so the eight additive gradients cost about one millisecond at the tail. That is 6.7x inside the 50 ms target, which means the static-layer cache I had planned was not worth writing.

- 150 tests at this point; the renderer, the icon fallback chain, the click threshold and the sector defaults all have a test.

- 10.29.2026

# V0.3.3 Update
- Changed Ctrl+Shift+Q from quitting to pausing. Quitting is a once-per-session action; silencing the pings is the one I actually press while working. The tray menu still quits.

- Pausing also releases the mouse guard, so while paused the desktop behaves normally again instead of having Alt + click swallowed by a tool I am not using.

- The hotkey now announces itself: a tray message says "Pings paused." or "Pings enabled.", and the menu entry flips between Pause and Resume. A silent global shortcut is a shortcut I cannot debug.

- Old configs keep working: the setting used to be called `quit_hotkey`, so the loader accepts that name and writes the new one on the next save.

- The settings window opens once at start-up, because launching and then immediately changing the trigger is what I do every day. There is a checkbox for people who disagree, which is also my way of admitting I might.

- 153 tests now; the toggle and the old-key migration are pinned so a later rename cannot quietly break someone's config.

- 10.29.2026

# V0.3.4 Update
- Added a switch above the pause hotkey that turns the ping wheel trigger on and off, and it follows the hotkey live: press Ctrl+Shift+Q while the dialog is open and the switch moves with it. A setting that can disagree with the thing it controls is worse than no setting.

- The first version looked right but was only clickable on the native indicator square; the rest of the pill swallowed clicks. A custom-painted button does not inherit a custom hit area, so the whole rectangle has to be accepted explicitly.

- It applies immediately, so Cancel does not undo it - matching the hotkey, which has never asked for confirmation.

- 157 tests; the live sync, the fact that an automatic update does not bounce back into the app, and a click on the right-hand side of the pill are all pinned.

- 10.29.2026

# Hotfix - wheel offset on scaled displays

- Someone ran lolping on another PC and the wheel appeared away from the cursor: exact at the top-left corner, then growing towards the bottom-right by roughly twice the cursor distance. That is the fingerprint of two coordinate spaces being mixed, not of a drawing bug.

- pynput's hook reports physical pixels, while Qt with High-DPI scaling works in logical pixels, and the wheel centre was taken straight from the hook. At 100% scaling the two coincide, which is why it never showed on my machine. The centre now comes from QCursor.pos() - the same space as the painting, the hit test and the hover logic; hook pixels are kept only for the log and the latency probe.

- Replaced guesswork with a diagnostic: the start-up log now lists each screen's geometry and dpr, and when the hook and Qt coordinates differ the trigger line prints both, so a scaled display can be read from the log instead of inferred.

- Pushed without a version bump so it can be tried on other machines before being called fixed. 158 tests.

- 10.29.2026
