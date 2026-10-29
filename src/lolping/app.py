"""Application shell: tray icon, wiring, ping log, latency probe.

The interesting logic lives in the modules around this one; this file is the
glue that turns hook signals into wheel behaviour and persisted records.

Design decisions worth knowing while reading:

* The hook thread only emits signals. Every widget touch happens here, in the
  GUI thread, through queued connections.
* Latency is measured from the hook callback timestamp to the first paint of an
  overlay window (``frame_ms``) and to the mouse-up (``commit_ms``).
* A failure to install the global hook is reported through the tray icon instead
  of a stack trace, because a windowed build has no console.
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import json
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Any

from PyQt5.QtCore import QEvent, QObject, QPoint, QTimer, Qt
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtGui import QColor, QCursor, QIcon, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

from . import __version__, assets, autostart, sounds
from .config import Config, app_data_dir, latency_path, log_path
from .hotkeys import format_hotkey
from .input_hook import InputBridge, InputHook
from .logging_setup import install_excepthook, setup_logging
from .mouse_guard import MouseGuard
from .overlay import OverlayManager
from .settings_dialog import SettingsDialog
from .single_instance import SingleInstance

log = logging.getLogger(__name__)

__all__ = ["PingApp", "main", "run_self_test"]

_TRIGGER_HINT = "Hold {keys} + {button} click, drag, release to ping"


def _apply_dpi_attributes() -> None:
    """Must run before QApplication exists."""
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    policy = getattr(Qt, "HighDpiScaleFactorRoundingPolicy", None)
    if policy is not None:
        try:
            QApplication.setHighDpiScaleFactorRoundingPolicy(policy.PassThrough)
        except (AttributeError, TypeError):  # pragma: no cover - Qt < 5.14
            pass


def _set_app_user_model_id() -> None:
    """Give the process its own taskbar identity (no console grouping)."""
    try:  # pragma: no cover - Windows only
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            f"lolping.{__version__}"
        )
    except Exception:
        log.debug("could not set the app user model id", exc_info=True)


def _tray_icon() -> QIcon:
    """Draw the tray icon so the project ships without binary assets."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(30, 30, 30, 235))
        painter.setPen(QPen(QColor(220, 180, 60), 4))
        painter.drawEllipse(6, 6, 52, 52)
        painter.setBrush(QColor(220, 180, 60))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(24, 24, 16, 16)
    finally:
        painter.end()
    return QIcon(pixmap)


class _FirstFrameWatcher(QObject):
    """Application-wide filter that reports the first overlay paint.

    Instrumentation only: it never changes behaviour, it just gives the latency
    probe a timestamp that includes actual painting rather than only ``show()``.
    """

    def __init__(self) -> None:
        super().__init__()
        self._armed = False
        self._callback = None
        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)

    def arm(self, callback) -> None:
        self._callback = callback
        self._armed = True

    def disarm(self) -> None:
        self._armed = False
        self._callback = None

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt name
        if self._armed and event.type() == QEvent.Paint:
            if obj.__class__.__name__ == "OverlayWindow":
                self._armed = False
                callback = self._callback
                if callback is not None:
                    callback(time.perf_counter())
        return False


class PingApp:
    """Owns the tray, the hook, the overlay and the persisted records."""

    def __init__(
        self,
        application: QApplication,
        config: Config,
        config_file: Path | None,
        instance: SingleInstance,
        latency_probe: bool = False,
        debug: bool = False,
    ) -> None:
        self._app = application
        self._config = config
        self._config_file = config_file
        self._instance = instance
        self._latency_probe = latency_probe
        self._debug = debug

        self._paused = False
        self._settings_open = False
        self._t_down = 0.0
        self._frame_ms: float | None = None
        self._wheel_centre = QPoint()

        self._overlay = OverlayManager(config)
        self._bridge = InputBridge()
        self._hook = InputHook(config, self._bridge)
        self._watcher = _FirstFrameWatcher()
        # The native hook must be installed before the pynput listeners so that
        # pynput still observes the gesture and the guard withholds it from every
        # window afterwards (see mouse_guard.py for the hook-chain reasoning).
        self._mouse_guard = MouseGuard(
            config_provider=lambda: self._config,
            paused_provider=lambda: self._paused,
            wheel_open_provider=self._gesture_in_progress,
        )

        # Neither PingApp nor QSystemTrayIcon's parent may be a plain Python
        # object: Qt requires a QObject parent, and the tray keeps its own
        # reference here so it outlives the constructor.
        self._tray = QSystemTrayIcon(_tray_icon())
        self._tray.setToolTip(self._tooltip_text())
        self._build_menu()
        self._connect()

        self._sync_autostart()

    # ------------------------------------------------------------------ public
    def run(self) -> int:
        if self._config.suppress_trigger_gesture:
            if not self._mouse_guard.start():
                self._tray.showMessage(
                    "lolping",
                    "The trigger gesture cannot be kept away from other windows; "
                    "mouse clicks will reach the app underneath.",
                    QSystemTrayIcon.Warning,
                    6000,
                )
        try:
            self._hook.start()
        except Exception:
            log.exception("cannot install the global input hook")
            self._tray.showMessage(
                "lolping",
                "Global keyboard/mouse capture could not start. "
                "The wheel will not open. See the log for details.",
                QSystemTrayIcon.Critical,
                8000,
            )
        else:
            self._tray.showMessage(
                "lolping",
                f"Running. {self._trigger_hint()}",
                QSystemTrayIcon.Information,
                5000,
            )

        self._tray.show()
        # Pay the first-gesture cost now, while no gesture is in flight: it keeps
        # the mouse-capture race window at a few milliseconds instead of ~100 ms.
        self._overlay.warm_up()
        if self._config.open_settings_on_start:
            QTimer.singleShot(250, self._open_settings)
        for screen in QGuiApplication.screens():
            geometry = screen.geometry()
            log.info(
                "screen %s geometry=%s,%s %sx%s dpr=%.2f",
                screen.name(),
                geometry.x(),
                geometry.y(),
                geometry.width(),
                geometry.height(),
                screen.devicePixelRatio(),
            )
        log.info("lolping %s ready (%s)", __version__, self._trigger_hint())
        return self._app.exec_()

    def quit(self) -> None:
        log.info("quit requested")
        self._watcher.disarm()
        self._mouse_guard.stop()
        try:
            self._hook.stop()
        except Exception:  # pragma: no cover
            log.exception("stopping the hook failed")
        try:
            self._overlay.shutdown()
        except Exception:  # pragma: no cover
            log.exception("shutting the overlay down failed")
        sounds.cleanup()
        self._tray.hide()
        self._instance.release()
        self._app.quit()

    # --------------------------------------------------------------- wiring
    def _connect(self) -> None:
        self._bridge.trigger_down.connect(self._on_trigger_down)
        self._bridge.trigger_up.connect(self._on_trigger_up)
        self._bridge.cancel.connect(self._on_cancel)
        self._bridge.other_click.connect(self._on_other_click)
        self._bridge.toggle_requested.connect(self._toggle_pause)
        self._bridge.health_changed.connect(self._on_health)
        self._overlay.committed.connect(self._on_committed)
        self._overlay.hover_changed.connect(self._on_hover_changed)

    # ----------------------------------------------------------------- sound
    def _play(self, cue: str, index: int = 0) -> None:
        """Play one cue if sound is on and that cue is individually enabled."""
        config = self._config
        if not config.sound_enabled:
            return
        enabled = {
            "open": config.sound_on_open,
            "hover": config.sound_hover_ticks,
            "commit": config.sound_on_commit,
            "cancel": config.sound_on_cancel,
        }.get(cue, True)
        if enabled:
            sounds.play(cue, config.sound_volume, index)

    def _on_hover_changed(self, index: int) -> None:
        if index >= 0:
            self._play("hover", index)

    def _gesture_in_progress(self) -> bool:
        """True between the trigger press and its release (mouse guard input)."""
        return self._hook.wheel_open or self._overlay.is_open()

    def _on_trigger_down(self, x: int, y: int, pressed_at: float) -> None:
        if self._paused:
            return
        if self._overlay.is_open():
            return
        self._t_down = pressed_at
        self._frame_ms = None
        # pynput's hook reports physical pixels, while Qt (High-DPI scaling on)
        # works in logical pixels. Mixing them puts the wheel at roughly
        # (scale - 1) x position on a scaled display - zero at the top-left
        # corner, growing towards the bottom-right. Ask Qt for the pointer so
        # the centre, the painting and the hit-testing share one coordinate
        # space; the hook value is kept for the log and the latency probe.
        pointer = QCursor.pos()
        self._wheel_centre = QPoint(pointer.x(), pointer.y())
        self._watcher.arm(self._on_first_frame)
        if (int(x), int(y)) != (pointer.x(), pointer.y()):
            log.debug(
                "trigger hook=(%s, %s) qt=(%s, %s) - display scaling differs",
                x,
                y,
                pointer.x(),
                pointer.y(),
            )
        else:
            log.debug("trigger at (%s, %s)", x, y)
        self._overlay.begin_at(self._wheel_centre)
        self._play("open")

    def _on_first_frame(self, painted_at: float) -> None:
        if self._t_down:
            self._frame_ms = max(0.0, (painted_at - self._t_down) * 1000.0)

    def _on_trigger_up(self, released_at: float) -> None:
        if not self._overlay.is_open():
            self._watcher.disarm()
            return
        name = self._overlay.commit()
        self._watcher.disarm()
        if self._latency_probe and self._t_down:
            self._record_latency(self._frame_ms, max(0.0, (released_at - self._t_down) * 1000.0))
        if name is None:
            log.debug("wheel cancelled by releasing inside the dead zone")

    def _on_cancel(self) -> None:
        if self._overlay.is_open():
            self._watcher.disarm()
            self._overlay.cancel()
            self._play("cancel")

    def _on_other_click(self, x: int, y: int) -> None:
        if self._overlay.is_open():
            log.debug("wheel cancelled by an extra click at (%s, %s)", x, y)
            self._watcher.disarm()
            self._overlay.cancel()
            self._play("cancel")

    def _on_committed(self, name: str, position: object) -> None:
        point = position if isinstance(position, QPoint) else self._wheel_centre
        log.info("ping: %s at (%s, %s)", name, point.x(), point.y())
        self._play("commit", self._sector_index(name))
        self._append_ping(name, point)
        if self._tray.isVisible():
            self._tray.setToolTip(f"lolping \u2014 last ping: {name}")

    def _on_health(self, healthy: bool) -> None:
        if healthy:
            return
        log.error("input hook reported unhealthy")
        if self._tray.isVisible():
            self._tray.showMessage(
                "lolping",
                "Keyboard/mouse capture stopped and is being restarted.",
                QSystemTrayIcon.Warning,
                5000,
            )

    # ---------------------------------------------------------------- records
    def _append_ping(self, name: str, position: QPoint) -> None:
        record: dict[str, Any] = {
            "ts": dt.datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "sector": self._sector_index(name),
            "name": name,
            "x": position.x(),
            "y": position.y(),
        }
        try:
            with open(log_path(), "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            log.exception("cannot append to the ping log")

    def _record_latency(self, frame_ms: float | None, commit_ms: float) -> None:
        record = {
            "ts": dt.datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "frame_ms": round(frame_ms, 2) if frame_ms is not None else None,
            "commit_ms": round(commit_ms, 2),
        }
        try:
            with open(latency_path(), "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
        except OSError:
            log.exception("cannot append to the latency log")
        log.info("latency frame_ms=%s commit_ms=%s", record["frame_ms"], record["commit_ms"])

    def _sector_index(self, name: str) -> int:
        try:
            return self._config.sectors.index(name)
        except ValueError:
            return -1

    # ------------------------------------------------------------------- tray
    def _build_menu(self) -> None:
        menu = QMenu()

        header = QAction(f"lolping {__version__}", menu)
        header.setEnabled(False)
        menu.addAction(header)
        menu.addSeparator()

        self._action_settings = QAction("Settings\u2026", menu)
        self._action_settings.setShortcut("")
        self._action_settings.triggered.connect(self._open_settings)
        menu.addAction(self._action_settings)

        self._action_pause = QAction("Pause", menu)
        self._action_pause.setCheckable(True)
        self._action_pause.toggled.connect(self._set_paused)
        menu.addAction(self._action_pause)

        menu.addSeparator()

        action_log = QAction("Ping history log", menu)
        action_log.triggered.connect(lambda: self._open_path(log_path()))
        menu.addAction(action_log)

        action_folder = QAction("Open config folder", menu)
        action_folder.triggered.connect(lambda: self._open_path(app_data_dir()))
        menu.addAction(action_folder)

        if self._latency_probe:
            action_latency = QAction("Open latency log", menu)
            action_latency.triggered.connect(lambda: self._open_path(latency_path()))
            menu.addAction(action_latency)

        menu.addSeparator()

        action_quit = QAction("Quit", menu)
        action_quit.triggered.connect(self.quit)
        menu.addAction(action_quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason: int) -> None:
        # Windows reports a double-click as Trigger first and DoubleClick second.
        # Opening the dialog on both events is what produced two stacked windows.
        if reason == QSystemTrayIcon.DoubleClick:
            self._open_settings()

    def _toggle_pause(self) -> None:
        """Flip the paused state; driven by the global hotkey and the tray menu."""
        self._action_pause.setChecked(not self._paused)

    def _set_trigger_enabled(self, enabled: bool) -> None:
        """Apply the settings switch to the run-time paused state."""
        if self._paused == (not enabled):
            return
        self._action_pause.setChecked(not enabled)

    def _set_paused(self, paused: bool) -> None:
        self._paused = bool(paused)
        self._action_pause.setText("Resume" if self._paused else "Pause")
        self._tray.setToolTip(self._tooltip_text())
        self._tray.showMessage(
            "lolping",
            "Pings paused." if self._paused else "Pings enabled.",
            QSystemTrayIcon.Information,
            2500,
        )
        log.info("paused=%s", self._paused)

    def _open_settings(self) -> None:
        if self._settings_open:
            # A queued second activation must not stack another modal dialog on
            # top of the first one.
            return
        self._settings_open = True
        try:
            edited = SettingsDialog.edit(
                self._config,
                None,
                pause_state_getter=lambda: self._paused,
                pause_toggled=self._set_trigger_enabled,
            )
        finally:
            self._settings_open = False
        if edited is None:
            return
        if edited.start_with_windows != autostart.is_enabled():
            autostart.set_enabled(edited.start_with_windows)
        self._config = edited
        try:
            edited.save(self._config_file)
        except OSError:
            log.exception("cannot save the configuration")
            self._tray.showMessage(
                "lolping", "Settings could not be saved to disk.", QSystemTrayIcon.Warning, 5000
            )
        # Pixmaps cache the old accent colour and icon size.
        assets.clear_caches()
        self._overlay.set_config(edited)
        self._hook.rebind(edited)
        self._tray.setToolTip(self._tooltip_text())
        log.info("settings applied")

    def _sync_autostart(self) -> None:
        want = self._config.start_with_windows
        if want != autostart.is_enabled():
            autostart.set_enabled(want)

    @staticmethod
    def _open_path(path: Path) -> None:
        try:
            import os

            os.startfile(str(path))  # noqa: S606 - opening a known local path
        except OSError:
            log.exception("cannot open %s", path)

    # ------------------------------------------------------------------ helpers
    def _trigger_hint(self) -> str:
        keys = format_hotkey(set(self._config.trigger_modifiers))
        return _TRIGGER_HINT.format(keys=keys, button=self._config.trigger_mouse_button)

    def _tooltip_text(self) -> str:
        state = "paused" if self._paused else "ready"
        return f"lolping {__version__} \u2014 {state} \u2014 {self._trigger_hint()}"


# --------------------------------------------------------------------- self test
def run_self_test() -> int:
    """Headless smoke test used by tools/smoke_test.py and CI."""
    _apply_dpi_attributes()
    application = QApplication(sys.argv[:1])
    application.setApplicationName("lolping")
    application.setQuitOnLastWindowClosed(False)

    config = Config()
    overlay = OverlayManager(config)
    captured: dict[str, str] = {}
    overlay.committed.connect(lambda name, _pos: captured.setdefault("name", name))

    cursor = QCursor.pos()
    centre = QPoint(cursor.x() - 160, cursor.y() - 160)
    overlay.begin_at(centre)
    opened = overlay.is_open()

    QTimer.singleShot(120, overlay.commit)
    QTimer.singleShot(400, application.quit)
    application.exec_()
    overlay.shutdown()

    ok = bool(opened and captured)
    if ok:
        print(f"SELF-TEST OK sector={captured.get('name')}")
        return 0
    print(f"SELF-TEST FAILED opened={opened} committed={captured}")
    return 1


# -------------------------------------------------------------------------- cli
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lolping",
        description="League of Legends style ping wheel for the Windows desktop.",
    )
    parser.add_argument("--config", type=Path, default=None, help="use a different config file")
    parser.add_argument(
        "--latency-probe", action="store_true", help="record trigger-to-paint latency"
    )
    parser.add_argument("--debug", action="store_true", help="verbose logging to stderr")
    parser.add_argument("--self-test", action="store_true", help="run a headless smoke test and exit")
    parser.add_argument("--version", action="version", version=f"lolping {__version__}")
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    setup_logging(args.debug)
    install_excepthook()
    log.info("lolping %s", __version__)

    _apply_dpi_attributes()
    _set_app_user_model_id()

    application = QApplication(sys.argv[:1])
    application.setApplicationName("lolping")
    application.setApplicationDisplayName("lolping")
    application.setApplicationVersion(__version__)
    application.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        log.warning("no system tray available; quitting will need the lock file release")

    instance = SingleInstance(app_data_dir() / "lolping.lock")
    if not instance.try_acquire():
        log.info("another instance is already running, exiting")
        return 0

    config = Config.load(args.config)
    if not config.sectors:
        config = Config()

    controller = PingApp(
        application,
        config,
        args.config,
        instance,
        latency_probe=args.latency_probe,
        debug=args.debug,
    )

    # Keep Python's signal handling responsive while Qt owns the main loop.
    heartbeat = QTimer()
    heartbeat.start(250)
    heartbeat.timeout.connect(lambda: None)
    signal.signal(signal.SIGINT, lambda *_: controller.quit())

    try:
        return controller.run()
    except Exception:
        log.exception("fatal error in the main loop")
        return 1
    finally:
        instance.release()
