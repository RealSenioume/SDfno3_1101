# An initial idea for creating a LOLping tool outside the game.
Using DeepSeek to build the foundation of this app,
but it didn't provide any variable-modification interface.
All I can do is change the variable inside the raw code.
And after running the raw code, there is no quick-exit hotkey or interface to exit.

- 10.22.2026

# Testing BETA v01
When pressing Alt alone, nothing happens. Tapping Alt lightly also has no side effects.
Alt + left-click: The roulette wheel appears at the clicked position.
Hold down the left button and drag the mouse: the highlighted sector will follow. At this point, release Alt, and the wheel should continue to display.
Release the left button: The terminal prints the corresponding signal name, and the roulette wheel disappears.
Alt + left-click and release without dragging: In the dead zone, no signal is triggered.
Rapidly and consecutively clicking the left button (holding down Alt): It will only activate on the first click, and the second click will not activate repeatedly; it will be submitted once when released.
Press the left button first and then Alt: The roulette wheel should not be triggered (because is_alt_held() is still False when on_click is triggered).
Meanwhile, I noticed a bug: sometimes the wheel appears one frame in the previous position when I wake it up.

# BETA v01_01
This is not a bug in the drawing logic, but a timing issue with the display of the Windows Composer (DWM).
self.show() will make the window "visible" first, and then Qt will dispatch the paintEvent. Between these two events, there is a short period of time where the window displays the previous backing store content (the roulette wheel in its old position), and then the new frame will overwrite it. You first change self.center in start_at(), and then call show(), but show() does not guarantee synchronous redrawing, so the old content will leak out for 1 frame.
At meantime, I asked Deepseek WEB to add one more function - when the wheel is aweak, mouse stop interactive with other thing. However, this version that Deepseek provided didn't work.

Due to pynput's support for keyboard event suppression on Windows but not for mouse event suppression, there is a window of a few milliseconds for mouse events before the wheel is activated. When the user quickly clicks with Alt+left button, the underlying application may receive an input of "pressed but not released". The program minimizes this gap by compressing the event polling interval to 2ms, but it cannot be completely eliminated. This is a platform limitation of third-party input monitoring libraries, rather than a logical flaw in the program.

- 10.22.2026

# DSH intervenes in development
For more details during development, check out the docs.

- 10.24.2026

# V.0.3.0 Update
Now it has animations and sound effects that can be used for demonstrations. However, to avoid potential copyright issues, animations, textures, sound effects, and other related content are all generated using DSH (DeepSeek Harness).
By the way, I adjusted the temporary storage path left in the document when DSH runs locally.