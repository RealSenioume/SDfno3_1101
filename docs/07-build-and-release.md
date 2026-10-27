# Build and release guide

This document explains how to set up a development environment, run the tests,
build the Windows executable, verify it, and publish a release of **lolping
v0.2.0**.

It is written for the build owner and for any teammate who has to reproduce a
release. The short version is at the top, the reasoning and pitfalls follow.

> Status note: this tooling was written while the application source was still
> being completed. The Python tools and the PyInstaller spec have been
> syntax-checked, `build.ps1` has been parser-checked and its early control flow
> exercised under Windows PowerShell 5.1, the latency analyser has been
> exercised on synthetic logs, the offscreen `--self-test` passes against the
> current source, and the `unittest` suite passes. A full PyInstaller build
> still has to be run by a maintainer. Use the
> [release checklist](#12-release-checklist) before tagging.

---

## 0. At a glance

All commands are Windows PowerShell, run from the repository root
(`D:\DSH_workspace\lolping`).

| Task | Command |
| --- | --- |
| Create dev environment | `python -m venv .venv` then `.\.venv\Scripts\Activate.ps1` |
| Install dev dependencies | `python -m pip install -r requirements.txt -r requirements-dev.txt` |
| Run the app from source | `$env:PYTHONPATH = "src"; python -m lolping` |
| Run the tests | `$env:PYTHONPATH = "src"; python -m pytest -q` |
| Headless smoke test | `python tools\smoke_test.py` |
| Live GUI smoke test | `python tools\smoke_test.py --live` |
| Latency report | `python tools\latency_report.py` |
| Full release build | `.\build\build.ps1 -Clean` |
| Build with Python 3.12 | `.\build\build.ps1 -Clean -PythonExe "C:\Python312\python.exe"` |

Output of the build:

* `dist\lolping\lolping.exe` — the application (one-folder build),
* `dist\lolping\_internal\` — Python runtime, Qt5 DLLs and Qt plugins,
* `release\lolping-<version>-win64.zip` — the distributable archive,
* `release\lolping-<version>-win64.zip.sha256` — SHA256 checksum.

The release zip is ignored by git; it is an artifact, not source.

---

## 1. Prerequisites

* Windows 10/11, 64-bit.
* 64-bit CPython **3.12 or 3.14** (the project targets 3.14; 3.12 is the
  conservative fallback — see [section 6](#6-python-314-vs-312)).
* Visual Studio Build Tools are **not** needed: PyQt5, pynput and PyInstaller
  install from wheels.
* No administrator rights. Everything is per-user: the virtual environment
  lives in the repository, and the app writes to `%APPDATA%\lolping-desktop`.
* Network access for `pip install` on the build machine (the app itself never
  uses the network).

The repository uses a `src/` layout (`src/lolping/...`) and ships a
`pyproject.toml`, but the package is not installed by default. Either install it
in editable mode (`python -m pip install -e .`, which also provides the
`lolping` console script) or put `src` on `PYTHONPATH` for ad-hoc commands. The
scripts in `tools/` and `build/build.ps1` set this up themselves, and pytest
reads `pythonpath = ["src"]` from `[tool.pytest.ini_options]`.

---

## 2. Development environment

```powershell
cd D:\DSH_workspace\lolping
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

`requirements.txt` holds the runtime dependencies (PyQt5, pynput).
`requirements-dev.txt` holds test/build tooling only (pytest, pyinstaller); the
application never imports it. (The same tools are also declared as the `dev`
extra in `pyproject.toml`; the build script uses `requirements-dev.txt`.)

Editable install, if you prefer a normal `python -m lolping`:

```powershell
python -m pip install -e .
```

Run the app from source:

```powershell
$env:PYTHONPATH = "src"
python -m lolping              # normal launch (tray icon, global hook)
python -m lolping --debug      # verbose logging to stderr
python -m lolping --latency-probe   # also record latency samples
python -m lolping --version
```

`--self-test` is the headless smoke test: it opens the wheel offscreen,
commits a ping, prints `SELF-TEST OK sector=...` and exits 0. It needs no
visible desktop when `QT_QPA_PLATFORM=offscreen` is set.

### User data locations

| What | Path |
| --- | --- |
| Config | `%APPDATA%\lolping-desktop\config.json` |
| Ping history | `%APPDATA%\lolping-desktop\pings.jsonl` |
| Latency probe log | `%APPDATA%\lolping-desktop\latency.jsonl` |
| Application log | `%APPDATA%\lolping-desktop\lolping.log` (rotating, 3 × 512 KB) |

Never write state next to the executable: a one-folder build's `_internal`
directory is owned by the installer/zip, and an installed copy may live under
`C:\Program Files` where a normal user cannot write.

---

## 3. Tests

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
# or, without installing pytest at all (the tests are unittest.TestCase based):
python -m unittest discover -s tests -v
```

`tests/` is owned by the Lead. If it does not exist yet, the build script only
warns; the release checklist requires it to pass before tagging. The suite is
plain `unittest`, so it also runs with a bare interpreter -- useful on a machine
where `pip install` is unavailable.

Two extra smoke tests sit outside pytest because they need a real interpreter
and (for `--live`) a real desktop:

```powershell
python tools\smoke_test.py            # offscreen --self-test, 60 s timeout
python tools\smoke_test.py --live     # real GUI must survive 5 s, then closes
python tools\smoke_test.py --live --live-seconds 10 --verbose
```

* `--self-test` requires exit code 0 **and** `SELF-TEST OK` on stdout.
* `--live` starts the real GUI, requires the process to still be alive after
  `--live-seconds` (default 5), then asks it to close. On Windows it first
  posts `WM_CLOSE` via `taskkill` (no `/F`); if the tray-only app ignores that,
  it falls back to a hard kill and says so in the output.
* Close any running lolping instance before `--live`: the single-instance guard
  makes a second copy exit immediately, which looks like a crash.
* The script launches the child with `PYTHONDONTWRITEBYTECODE=1`, so no
  `__pycache__` appears in `src/`.

Both tools are standard-library only and exit non-zero on failure, so they can
be used in CI without installing anything.

---

## 4. Latency acceptance criterion

The requirement is **p95 `frame_ms` <= 50 ms** (`frame_ms` = mouse-down hook
callback → first painted wheel frame). Measure it like this:

```powershell
python -m lolping --latency-probe     # leave it running, do ~20 pings
# quit lolping, then:
python tools\latency_report.py
```

The analyser reads `%APPDATA%\lolping-desktop\latency.jsonl` (override with
`--path`, `-` reads stdin), skips malformed/truncated lines, prints
n/min/median/p90/p95/p99/max for both `frame_ms` and `commit_ms`, a
ready-to-paste Markdown table, and a PASS/FAIL verdict for the AC.

* Percentiles are nearest-rank, so with fewer than 20 samples p95 equals the
  maximum — collect at least 20 pings on a quiet machine.
* `frame_ms` can be `null` in the log when the first frame was never observed;
  that line still contributes its `commit_ms`.
* Exit codes: `0` AC passed, `1` AC failed, `2` no usable data / file missing.
  Use the exit code in CI, paste the table and the verdict into the report.
* A different limit can be checked with `--threshold-ms 40`.

---

## 5. Building the release

The build script is the supported way to produce the release. It creates its
own virtual environment so it never touches the system Python:

```powershell
.\build\build.ps1
```

If PowerShell refuses to run the script (`running scripts is disabled on this
system`), use an explicit execution-policy override for this one invocation:

```powershell
# Windows PowerShell 5.1
powershell -NoProfile -ExecutionPolicy Bypass -File .\build\build.ps1

# PowerShell 7
pwsh -NoProfile -ExecutionPolicy Bypass -File .\build\build.ps1
```

The script itself is compatible with both PowerShell 5.1 and 7.

### Parameters

| Parameter | Meaning |
| --- | --- |
| `-PythonExe <path>` | Interpreter used to create `.venv-build` (default: `python` on PATH). |
| `-Clean` | Delete `dist\`, `build\_work\` and the previous release zip first. The virtual environment is kept. |
| `-SkipTests` | Skip pytest and the frozen self-test. Packaging only — never use for a release. |

### What the script does, in order

1. Validates that the repository is complete and that the interpreter is 64-bit.
2. Reads `__version__` from `src/lolping/__init__.py` and derives the zip name.
3. Warns loudly when the interpreter is Python 3.14 (see section 6).
4. Creates `.venv-build` if missing and installs `requirements.txt` +
   `requirements-dev.txt` into it.
5. Runs `pytest -q` from the repository root with `PYTHONPATH=src`.
6. Runs PyInstaller against `build\lolping.spec`:

   ```powershell
   .\.venv-build\Scripts\python.exe -m PyInstaller --noconfirm ^
       --distpath dist --workpath build\_work build\lolping.spec
   ```

7. Copies `README.md` and `LICENSE` (if present) next to `lolping.exe`.
8. Runs `dist\lolping\lolping.exe --self-test` with `QT_QPA_PLATFORM=offscreen`
   and fails the build if the exit code is not 0. A windowed exe has no
   console, so the exit code is the only signal; this catches packaging errors
   such as missing hidden imports before the zip is published.
9. Zips `dist\lolping\` to `release\lolping-<version>-win64.zip` and writes the
   `.sha256` file next to it.

A failed step prints `BUILD FAILED` with a one-line reason and exits 1. Every
native command is checked; nothing is silently skipped.

### Why the spec generates its own entry point

`src/lolping/__main__.py` begins with `from .app import main`. PyInstaller
executes the given script as the top-level `__main__` module, outside its
package, so a frozen app built directly from that file would die with:

```
ImportError: attempted relative import with no known parent package
```

This is PyInstaller issue
[#2560](https://github.com/pyinstaller/pyinstaller/issues/2560), which is still
open. `build\lolping.spec` therefore writes a three-line stub to the temp
directory at build time and uses that as the entry script:

```python
from lolping.__main__ import main
sys.exit(main())
```

The package is imported as a module (with `__package__ = "lolping"`), so the
relative imports work. Keep this in mind if `__main__.py` is ever restructured:
as long as it exposes a callable `main`, the spec keeps working. If it does not,
the frozen `--self-test` step fails the build with a clear message.

### One-folder vs one-file

The spec builds a **one-folder** distribution. A one-file (`--onefile`) build
works too, but every launch must unpack tens of megabytes of Qt DLLs to a temp
directory, which adds seconds to the cold start. For a latency-sensitive
overlay that is the wrong trade-off. Distribute the whole `lolping\` folder,
not just the exe: the exe cannot start without `_internal\`.

---

## 6. Python 3.14 vs 3.12

The project targets Python 3.14 (3.14.5 at the time of writing) with PyQt5
5.15.11 and pynput 1.8.2, which are installed and importable on this machine.

**PyInstaller support for a brand-new CPython release can lag behind CPython.**
At the time of writing, PyPI metadata for PyInstaller 6.22.3 declares support
for Python 3.8–3.15, and `pip index versions pyinstaller` on Python 3.14 offers
6.15.0 and newer — that is why `requirements-dev.txt` pins
`pyinstaller>=6.15,<7`. Older PyInstaller releases (or older `pyinstaller-hooks-contrib`
snapshots) cannot bundle a 3.14 interpreter at all.

If `pip install` or the PyInstaller step fails on 3.14, do not fight it — build
with Python 3.12, which every PyInstaller release supports:

```powershell
# install a 64-bit Python 3.12 somewhere, then:
.\build\build.ps1 -Clean -PythonExe "C:\Python312\python.exe"
```

`.venv-build` remembers the interpreter it was created with; after switching
interpreters always pass `-Clean`, and if the venv itself is stale delete
`.venv-build\` once. The application code itself is 3.10+ syntax and runs on
both versions.

---

## 7. Versioning and tagging

`src/lolping/__init__.py` contains the single source of truth:

```python
__version__ = "0.2.0"
```

It is used by `--version`, the window title, the log banner, and by
`build.ps1` for the zip name (`release\lolping-0.2.0-win64.zip`). To cut a
release:

1. Bump `__version__`.
2. Update version references in `README.md` and the report docs.
3. Run the release checklist (section 12).
4. Commit, then tag and push:

   ```powershell
   git tag -a v0.2.0 -m "lolping v0.2.0"
   git push origin v0.2.0
   ```

5. Attach `release\lolping-0.2.0-win64.zip` and its `.sha256` to the tag/release.

The tag name and `__version__` must match; the build script derives the archive
name from `__version__`, so a stale `__version__` produces a misleading zip.

---

## 8. What the release zip contains

```
lolping-0.2.0-win64.zip
└── lolping/
    ├── lolping.exe          windowed executable, no console
    ├── README.md            copied by build.ps1
    ├── LICENSE              copied by build.ps1 (when the file exists)
    └── _internal/           Python runtime, Qt5 DLLs, Qt plugins, PyQt5, pynput
```

Users extract the zip and run `lolping\lolping.exe`. There is no installer and
no registry write at install time; the only registry use is the optional
per-user `Run` key for "start with Windows" (toggled from Settings).

Verifying a download:

```powershell
Get-FileHash .\lolping-0.2.0-win64.zip -Algorithm SHA256
Get-Content .\lolping-0.2.0-win64.zip.sha256
```

---

## 9. Icon

The spec uses `assets\lolping.ico` **if it exists** and silently falls back to
the default PyInstaller icon otherwise; no build step needs changing. To add or
replace it:

1. Draw or export a square PNG at 256×256 (transparent background looks best
   against the gold theme).
2. Convert it to a multi-size `.ico` (Windows needs 16/32/48/64/128/256):

   ```powershell
   python -m pip install pillow   # dev-only, not added to requirements
   python -c "from PIL import Image; Image.open('assets/lolping.png').convert('RGBA').save('assets/lolping.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
   ```

3. Rebuild with `-Clean`.

The icon is embedded into the exe (Explorer/taskbar icon). The tray icon is
drawn by the app itself and is not affected by this file.

---

## 10. SmartScreen and antivirus false positives

The release exe is **not code-signed**. Windows SmartScreen will show
"Windows protected your PC" for a downloaded zip whose reputation is unknown,
and some antivirus products flag PyInstaller executables as generic packers.
This is normal for a student project; it is not a packaging bug.

What we do to keep false positives down:

* UPX compression is **disabled** in the spec (`upx=False`). Compressed
  executables are a classic heuristic trigger.
* The build is one-folder and contains unmodified, signed-by-publisher Qt
  binaries, which looks less suspicious than a compressed one-file blob.
* The zip's SHA256 is published next to it so users can verify the download.
* Users are told in `README.md` / the manual what to expect and how to report a
  false positive (Microsoft's "Submit a file for malware analysis" form) rather
  than being told to disable their antivirus.

For distribution, either sign the exe with a code-signing certificate (adds
SmartScreen reputation over time) or accept the "More info → Run anyway" step
and document it. Never rename `python*.dll` or strip metadata to dodge a
detection; that makes the situation worse.

Antivirus can also lock files during the build (`Access is denied` while
writing `dist\`). If that happens, exclude the repository folder from real-time
scanning on the build machine, rebuild, and re-enable it afterwards.

---

## 11. Known packaging pitfalls

| Symptom | Cause / fix |
| --- | --- |
| Frozen app starts but the global hook never fires | pynput loads `pynput.keyboard._win32` / `pynput.mouse._win32` lazily inside a helper, so static analysis misses them. They are listed in `hiddenimports` in `build\lolping.spec`; if a future pynput release adds another backend module, add it there and rebuild with `-Clean`. |
| Frozen app dies instantly after a dialog | `--windowed` has no stdout. Check `%APPDATA%\lolping-desktop\lolping.log`; run the source version with `--debug`; or run `dist\lolping\lolping.exe --self-test` from a console with `QT_QPA_PLATFORM=offscreen` and inspect the exit code. |
| A traceback dialog appears on launch | `disable_windowed_traceback=False` keeps PyInstaller's error dialog. Read the first exception in the dialog, then reproduce with `python -m lolping --debug`. |
| Config/log files written next to the exe | The app must use `%APPDATA%\lolping-desktop` (it does). Writing into the install folder fails for non-admin users and is wiped by zip upgrades. |
| "Failed to execute script 'lolping'"? | Usually a missing hidden import or a module the analyser excluded. Rebuild with `-Clean`, then compare `build\_work\lolping\warn-lolping.txt`. |
| Frozen app uses a stale description/size | PyInstaller caches analysis in `build\_work`; always `-Clean` after changing the spec, hidden imports or the Python version. |
| `running scripts is disabled on this system` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\build\build.ps1` (or `pwsh -NoProfile -ExecutionPolicy Bypass -File ...`); alternatively change the policy for the current user. |
| `pip` cannot find PyQt5/PyInstaller on 3.14 | Use the Python 3.12 fallback (section 6). |
| Build path with non-ASCII characters fails deep inside PyInstaller | Keep the checkout at an ASCII path such as `D:\DSH_workspace\lolping`; some tooling still mishandles CJK paths. |
| `lolping.exe` starts a second copy but nothing appears | By design: the single-instance guard exits the second copy. Close the tray icon first. |
| `--self-test` hangs in the build | A modal error dialog is waiting; the script kills the process after 120 s and fails. Reproduce from a console to read the dialog. |

Build artifacts (`dist\`, `build\_work\`, `release\`, `.venv-build\`) must stay
out of git. `dist/`, `release/` and `.venv/` are already in `.gitignore`; if
`git status` shows `.venv-build/` or `build/_work/`, add those two entries.

---

## 12. Release checklist

Run every line from the repository root and keep the output for the report.

- [ ] `python -m pytest -q` passes (with `PYTHONPATH=src`).
- [ ] `python tools\smoke_test.py` prints `RESULT: PASS`.
- [ ] `python tools\smoke_test.py --live` prints `RESULT: PASS` (no other
      instance running).
- [ ] `.\build\build.ps1 -Clean` prints `Build succeeded.` and the frozen
      self-test passed.
- [ ] `dist\lolping\lolping.exe` starts on a clean-ish Windows machine, shows
      the tray icon, opens the wheel and commits a ping.
- [ ] Settings dialog opens, changes persist to
      `%APPDATA%\lolping-desktop\config.json`, "start with Windows" can be toggled.
- [ ] `--latency-probe` run + `python tools\latency_report.py` gives
      `PASS` for p95 `frame_ms` <= 50 ms; paste the Markdown table and verdict
      into the report.
- [ ] Release zip extracted to an empty folder and run from there; README and
      the `--version` output both show `0.2.0`.
- [ ] `Get-FileHash` of the zip matches the published `.sha256`.
- [ ] `__version__` bumped, tag `v0.2.0` created and pushed, zip attached.
- [ ] `docs/07-build-and-release.md` (this file) still matches the script.

---

## 13. Manual build without the script

If the PowerShell script cannot be used, the same steps by hand:

```powershell
cd D:\DSH_workspace\lolping
python -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
$env:PYTHONPATH = "src"
.\.venv-build\Scripts\python.exe -m pytest -q
.\.venv-build\Scripts\python.exe -m PyInstaller --noconfirm --distpath dist --workpath build\_work build\lolping.spec
Copy-Item README.md dist\lolping\
$env:QT_QPA_PLATFORM = "offscreen"
.\dist\lolping\lolping.exe --self-test   # expect exit code 0
Compress-Archive -Path dist\lolping -DestinationPath release\lolping-0.2.0-win64.zip
```

The script is still the reference implementation: it also checks the
interpreter architecture, copies the optional LICENSE, writes the checksum and
cleans stale output.
