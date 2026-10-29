"""The lolping settings dialog.

``SettingsDialog`` is a plain modal ``QDialog`` that edits a :class:`Config`.
It never mutates the config it was given: :meth:`edited_config` builds a brand
new object with :func:`dataclasses.replace`, so a cancelled dialog leaves the
running application untouched.

Validation is inline (an error label at the bottom); the OK button refuses to
close the dialog while the form is invalid.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Callable

from PyQt5.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QIntValidator, QPainter
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .assets import ICON_IDS, resolve_icon
from .config import DEFAULT_SECTORS, MODIFIER_NAMES, SECTOR_COUNT, THEMES, Config
from .hotkeys import parse_hotkey

log = logging.getLogger(__name__)

__all__ = ["SettingsDialog"]

MODIFIER_LABELS: dict[str, str] = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "win": "Win",
}

BUTTON_LABELS: dict[str, str] = {
    "left": "Left button",
    "right": "Right button",
    "middle": "Middle button",
    "x1": "Side button 1 (X1)",
    "x2": "Side button 2 (X2)",
}

THEME_LABELS: dict[str, str] = {
    "gold": "Gold",
    "blue": "Blue",
    "red": "Red",
    "lol": "League style (lol)",
}

_RADIUS_MIN = 60
_RADIUS_MAX = 400
_DEAD_MIN = 5
_DEAD_MARGIN = 20
_TAU_MIN_MS = 5
_TAU_MAX_MS = 200
_MARK_MIN_MS = 300
_MARK_MAX_MS = 4000
_SECTOR_MAX_LEN = 24
_ICON_SIZE_MIN = 12
_ICON_SIZE_MAX = 64
_VOLUME_MIN = 0
_VOLUME_MAX = 100


class ToggleSwitch(QCheckBox):
    """A small pill-shaped on/off switch.

    ``QCheckBox`` provides the behaviour (checked state, toggled signal,
    accessibility, keyboard space) and only the indicator is custom-painted, so
    it stays a native widget that tests can drive with ``setChecked``.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(38, 20)
        self.setToolTip("On: the wheel can be triggered. Off: it cannot.")

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt name
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            radius = self.height() / 2.0
            track = QColor(64, 156, 96) if self.isChecked() else QColor(150, 150, 150)
            if not self.isEnabled():
                track.setAlpha(110)
            painter.setPen(Qt.NoPen)
            painter.setBrush(track)
            painter.drawRoundedRect(
                QRectF(0.0, 0.0, float(self.width()), float(self.height())),
                radius,
                radius,
            )
            knob_radius = radius - 3.0
            centre = self.width() - radius if self.isChecked() else radius
            painter.setBrush(QColor(246, 246, 246))
            painter.drawEllipse(QPointF(centre, radius), knob_radius, knob_radius)
        finally:
            painter.end()

    def hitButton(self, pos: QPoint) -> bool:  # noqa: N802 - Qt name
        # QCheckBox only counts clicks inside the style's (tiny) indicator rect;
        # the indicator is custom-painted across the whole widget, so accept
        # every click that lands on the pill.
        return self.rect().contains(pos)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt name
        return QSize(38, 20)


class SettingsDialog(QDialog):
    """Edit every user-tunable field of :class:`~lolping.config.Config`."""

    def __init__(
        self,
        config: Config,
        parent: QWidget | None = None,
        pause_state_getter: Callable[[], bool] | None = None,
        pause_toggled: Callable[[bool], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._base_config = config
        # The trigger switch shows run-time state, which lives in the
        # application rather than in the config, so it is read through a
        # callback and written back through another one.
        self._pause_state_getter = pause_state_getter
        self._pause_toggled = pause_toggled
        self._updating_switch = False
        self._modifier_boxes: dict[str, QCheckBox] = {}
        self._sector_edits: list[QLineEdit] = []
        self._sector_icon_combos: list[QComboBox] = []
        self._icon_widgets: list[QWidget] = []

        self.setWindowTitle("lolping settings")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setFixedSize(660, 840)

        self._build_ui()
        self._connect_signals()
        self._load_config(config)
        if self._pause_state_getter is not None:
            # Poll instead of relying on a signal: the application can change
            # state from the hotkey thread while this modal dialog is open.
            self._switch_timer = QTimer(self)
            self._switch_timer.setInterval(200)
            self._switch_timer.timeout.connect(self._sync_trigger_switch)
            self._switch_timer.start()

    # ------------------------------------------------------------------ public
    def edited_config(self) -> Config:
        """Return a new :class:`Config` built from the current widget values.

        Only meaningful after :meth:`accept`: values are validated at that
        point, and sector names that are left blank fall back to the defaults.
        """
        sectors: list[str] = []
        for index, edit in enumerate(self._sector_edits):
            text = edit.text().strip()[:_SECTOR_MAX_LEN]
            sectors.append(text or DEFAULT_SECTORS[index % len(DEFAULT_SECTORS)])

        radius = int(self._radius_slider.value())
        dead_zone = int(min(self._dead_slider.value(), max(_DEAD_MIN, radius - _DEAD_MARGIN)))

        return replace(
            self._base_config,
            trigger_modifiers=[
                name for name in MODIFIER_NAMES if self._modifier_boxes[name].isChecked()
            ],
            trigger_mouse_button=str(
                self._button_combo.currentData() or self._base_config.trigger_mouse_button
            ),
            suppress_trigger_gesture=bool(self._suppress_check.isChecked()),
            click_places_ping=bool(self._click_ping_check.isChecked()),
            wheel_radius=radius,
            dead_zone=dead_zone,
            sector_count=SECTOR_COUNT,
            sectors=sectors,
            animation_tau=round(self._tau_slider.value() / 1000.0, 3),
            mark_duration_ms=int(self._mark_spin.value()),
            sound_enabled=bool(self._sound_check.isChecked()),
            sound_volume=round(self._volume_slider.value() / 100.0, 2),
            sound_hover_ticks=bool(self._hover_ticks_check.isChecked()),
            toggle_hotkey=self._toggle_hotkey_edit.text().strip().lower().replace(" ", ""),
            open_settings_on_start=bool(self._start_settings_check.isChecked()),
            start_with_windows=bool(self._autostart_check.isChecked()),
            show_labels=bool(self._labels_check.isChecked()),
            theme=str(self._theme_combo.currentData() or self._base_config.theme),
            show_icons=bool(self._icons_check.isChecked()),
            sector_icons=[
                str(combo.currentData() or resolve_icon(None, index))
                for index, combo in enumerate(self._sector_icon_combos)
            ],
            icon_size=int(self._icon_size_slider.value()),
        )

    @staticmethod
    def edit(
        config: Config,
        parent: QWidget | None = None,
        pause_state_getter: Callable[[], bool] | None = None,
        pause_toggled: Callable[[bool], None] | None = None,
    ) -> Config | None:
        """Show the dialog modally; return the edited config or ``None``."""
        dialog = SettingsDialog(config, parent, pause_state_getter, pause_toggled)
        try:
            accepted = dialog.exec_() == QDialog.Accepted
            return dialog.edited_config() if accepted else None
        finally:
            dialog.deleteLater()

    # -------------------------------------------------------------------- setup
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 12)
        outer.setSpacing(8)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 2, 8, 2)
        content_layout.setSpacing(8)

        content_layout.addWidget(self._build_trigger_group(content))
        content_layout.addWidget(self._build_wheel_group(content))
        content_layout.addWidget(self._build_sectors_group(content))
        content_layout.addWidget(self._build_feedback_group(content))
        content_layout.addWidget(self._build_system_group(content))
        content_layout.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        self._error_label = QLabel("", self)
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet("color: #cc3333;")
        self._error_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._error_label.setVisible(False)
        outer.addWidget(self._error_label)

        bottom_row = QHBoxLayout()
        self._reset_button = QPushButton("Reset to defaults", self)
        bottom_row.addWidget(self._reset_button)
        bottom_row.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        if ok_button is not None:
            ok_button.setText("OK")
            ok_button.setDefault(True)
        cancel_button = buttons.button(QDialogButtonBox.Cancel)
        if cancel_button is not None:
            cancel_button.setText("Cancel")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        bottom_row.addWidget(buttons)
        outer.addLayout(bottom_row)

    def _build_trigger_group(self, parent: QWidget) -> QGroupBox:
        group = QGroupBox("Trigger", parent)
        layout = QVBoxLayout(group)

        modifier_row = QHBoxLayout()
        modifier_row.addWidget(QLabel("Hold:", group))
        for name in MODIFIER_NAMES:
            box = QCheckBox(MODIFIER_LABELS.get(name, name.capitalize()), group)
            self._modifier_boxes[name] = box
            modifier_row.addWidget(box)
        modifier_row.addStretch(1)
        layout.addLayout(modifier_row)

        button_row = QHBoxLayout()
        button_row.addWidget(QLabel("Mouse button:", group))
        self._button_combo = QComboBox(group)
        for name in ("left", "right", "middle", "x1", "x2"):
            self._button_combo.addItem(BUTTON_LABELS.get(name, name.capitalize()), name)
        self._button_combo.setMinimumWidth(170)
        button_row.addWidget(self._button_combo, 1)
        layout.addLayout(button_row)

        self._suppress_check = QCheckBox("Reserve the trigger for lolping", group)
        self._suppress_check.setToolTip(
            "Withhold the gesture from other windows so that dragging over the "
            "desktop cannot start a selection or an icon drag. While this is on, "
            "the trigger combination (Alt + click by default) does nothing in "
            "other applications."
        )
        layout.addWidget(self._suppress_check)

        self._click_ping_check = QCheckBox("Click without dragging sends a basic ping", group)
        self._click_ping_check.setToolTip(
            "A press and release without moving places the centre ping. Turn this "
            "off if a click should always cancel the wheel instead."
        )
        layout.addWidget(self._click_ping_check)
        return group

    def _build_wheel_group(self, parent: QWidget) -> QGroupBox:
        group = QGroupBox("Wheel", parent)
        layout = QVBoxLayout(group)

        self._radius_slider = QSlider(Qt.Horizontal, group)
        self._radius_slider.setRange(_RADIUS_MIN, _RADIUS_MAX)
        self._radius_slider.setPageStep(10)
        self._radius_value = QLabel("", group)
        self._radius_value.setMinimumWidth(60)
        self._radius_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addLayout(
            self._slider_row("Radius:", self._radius_slider, self._radius_value, group)
        )

        self._dead_slider = QSlider(Qt.Horizontal, group)
        self._dead_slider.setRange(_DEAD_MIN, _RADIUS_MAX - _DEAD_MARGIN)
        self._dead_slider.setPageStep(5)
        self._dead_value = QLabel("", group)
        self._dead_value.setMinimumWidth(60)
        self._dead_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addLayout(
            self._slider_row("Dead zone:", self._dead_slider, self._dead_value, group)
        )
        self._dead_slider.setToolTip(
            "Clicks released inside the dead zone cancel the ping."
        )

        options_row = QHBoxLayout()
        options_row.addWidget(QLabel("Theme:", group))
        self._theme_combo = QComboBox(group)
        for name in THEMES:
            self._theme_combo.addItem(THEME_LABELS.get(name, name.capitalize()), name)
        options_row.addWidget(self._theme_combo)
        options_row.addSpacing(12)
        self._labels_check = QCheckBox("Show labels", group)
        options_row.addWidget(self._labels_check)
        options_row.addSpacing(8)
        self._icons_check = QCheckBox("Show icons", group)
        self._icons_check.setToolTip("Draw a vector icon (or your own image) on every slice.")
        options_row.addWidget(self._icons_check)
        options_row.addStretch(1)
        layout.addLayout(options_row)

        self._icon_size_slider = QSlider(Qt.Horizontal, group)
        self._icon_size_slider.setRange(_ICON_SIZE_MIN, _ICON_SIZE_MAX)
        self._icon_size_slider.setPageStep(4)
        self._icon_size_value = QLabel("", group)
        self._icon_size_value.setMinimumWidth(60)
        self._icon_size_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addLayout(
            self._slider_row(
                "Icon size:", self._icon_size_slider, self._icon_size_value, group
            )
        )
        return group

    def _build_sectors_group(self, parent: QWidget) -> QGroupBox:
        group = QGroupBox("Slices", parent)
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        columns = 2
        for index in range(SECTOR_COUNT):
            edit = QLineEdit(group)
            edit.setMaxLength(_SECTOR_MAX_LEN)
            default = DEFAULT_SECTORS[index % len(DEFAULT_SECTORS)]
            edit.setPlaceholderText(default)
            self._sector_edits.append(edit)

            combo = QComboBox(group)
            combo.setToolTip(f"Icon for slice {index + 1}.")
            for icon_id in ICON_IDS:
                combo.addItem(icon_id.replace("_", " ").title(), icon_id)
            combo.setMinimumWidth(112)
            self._sector_icon_combos.append(combo)

            row = index // columns
            column = (index % columns) * 3
            grid.addWidget(QLabel(f"{index + 1}.", group), row, column)
            grid.addWidget(edit, row, column + 1)
            grid.addWidget(combo, row, column + 2)
            grid.setColumnStretch(column + 1, 1)
        return group

    def _build_feedback_group(self, parent: QWidget) -> QGroupBox:
        group = QGroupBox("Ping feedback", parent)
        layout = QVBoxLayout(group)

        self._tau_slider = QSlider(Qt.Horizontal, group)
        self._tau_slider.setRange(_TAU_MIN_MS, _TAU_MAX_MS)
        self._tau_slider.setPageStep(10)
        self._tau_value = QLabel("", group)
        self._tau_value.setMinimumWidth(60)
        self._tau_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addLayout(
            self._slider_row("Fade-in speed:", self._tau_slider, self._tau_value, group)
        )

        mark_row = QHBoxLayout()
        mark_row.addWidget(QLabel("Mark duration:", group))
        self._mark_spin = QSpinBox(group)
        self._mark_spin.setRange(_MARK_MIN_MS, _MARK_MAX_MS)
        self._mark_spin.setSingleStep(50)
        self._mark_spin.setSuffix(" ms")
        self._mark_spin.lineEdit().setValidator(
            QIntValidator(_MARK_MIN_MS, _MARK_MAX_MS, self._mark_spin)
        )
        self._mark_spin.setMinimumWidth(110)
        mark_row.addWidget(self._mark_spin)
        mark_row.addSpacing(10)
        mark_row.addWidget(QLabel("Volume:", group))
        self._volume_slider = QSlider(Qt.Horizontal, group)
        self._volume_slider.setRange(_VOLUME_MIN, _VOLUME_MAX)
        self._volume_slider.setPageStep(5)
        self._volume_value = QLabel("", group)
        self._volume_value.setMinimumWidth(50)
        self._volume_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        mark_row.addWidget(self._volume_slider, 1)
        mark_row.addWidget(self._volume_value)
        layout.addLayout(mark_row)

        sound_row = QHBoxLayout()
        self._sound_check = QCheckBox("Enable sounds", group)
        sound_row.addWidget(self._sound_check)
        sound_row.addSpacing(12)
        self._hover_ticks_check = QCheckBox("Hover ticks", group)
        self._hover_ticks_check.setToolTip(
            "Play a short tick when the highlighted slice changes."
        )
        sound_row.addWidget(self._hover_ticks_check)
        sound_row.addStretch(1)
        layout.addLayout(sound_row)
        return group

    def _build_system_group(self, parent: QWidget) -> QGroupBox:
        group = QGroupBox("System", parent)
        layout = QVBoxLayout(group)

        trigger_row = QHBoxLayout()
        self._trigger_switch = ToggleSwitch(group)
        self._trigger_switch.setToolTip(
            "Turn the ping wheel trigger on or off. This is the same state as the "
            "pause hotkey and the tray entry, and it applies immediately - Cancel "
            "does not undo it."
        )
        trigger_row.addWidget(self._trigger_switch)
        trigger_row.addWidget(QLabel("Ping wheel enabled", group))
        trigger_row.addStretch(1)
        layout.addLayout(trigger_row)

        hotkey_row = QHBoxLayout()
        hotkey_row.addWidget(QLabel("Pause hotkey:", group))
        self._toggle_hotkey_edit = QLineEdit(group)
        self._toggle_hotkey_edit.setPlaceholderText("Ctrl+Shift+Q")
        self._toggle_hotkey_edit.setMaxLength(64)
        hotkey_row.addWidget(self._toggle_hotkey_edit, 1)
        layout.addLayout(hotkey_row)
        self._toggle_hotkey_edit.setToolTip(
            "Modifiers plus one key, for example Ctrl+Shift+Q. Pressing it pauses "
            "or resumes pinging; quitting is done from the tray menu."
        )

        self._autostart_check = QCheckBox("Start with Windows", group)
        layout.addWidget(self._autostart_check)

        self._start_settings_check = QCheckBox("Open settings when lolping starts", group)
        layout.addWidget(self._start_settings_check)
        return group

    @staticmethod
    def _slider_row(
        label: str, slider: QSlider, value_label: QLabel, parent: QWidget
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        caption = QLabel(label, parent)
        caption.setMinimumWidth(110)
        row.addWidget(caption)
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        return row

    def _connect_signals(self) -> None:
        self._icon_widgets = [
            self._icon_size_slider,
            self._icon_size_value,
            *self._sector_icon_combos,
        ]

        self._radius_slider.valueChanged.connect(self._on_radius_changed)
        self._dead_slider.valueChanged.connect(self._on_dead_zone_changed)
        self._tau_slider.valueChanged.connect(self._on_tau_changed)
        self._icon_size_slider.valueChanged.connect(self._on_icon_size_changed)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        self._icons_check.toggled.connect(self._on_icons_toggled)

        for box in self._modifier_boxes.values():
            box.toggled.connect(self._clear_error)
        for edit in self._sector_edits:
            edit.textChanged.connect(self._clear_error)
        for combo in self._sector_icon_combos:
            combo.currentIndexChanged.connect(self._clear_error)
        self._toggle_hotkey_edit.textChanged.connect(self._clear_error)
        self._trigger_switch.toggled.connect(self._on_trigger_switch_toggled)
        self._button_combo.currentIndexChanged.connect(self._clear_error)
        self._theme_combo.currentIndexChanged.connect(self._clear_error)
        self._sound_check.toggled.connect(self._clear_error)
        self._hover_ticks_check.toggled.connect(self._clear_error)
        self._autostart_check.toggled.connect(self._clear_error)
        self._labels_check.toggled.connect(self._clear_error)
        self._mark_spin.valueChanged.connect(self._clear_error)
        self._reset_button.clicked.connect(self._reset_to_defaults)

    # --------------------------------------------------------------- load/store
    def _load_config(self, config: Config) -> None:
        """Populate every widget from ``config``, clamping to widget ranges."""
        selected = {str(name).lower() for name in config.trigger_modifiers}
        for name, box in self._modifier_boxes.items():
            box.setChecked(name in selected)

        button_index = self._button_combo.findData(config.trigger_mouse_button)
        self._button_combo.setCurrentIndex(button_index if button_index >= 0 else 0)

        self._suppress_check.setChecked(bool(config.suppress_trigger_gesture))
        self._click_ping_check.setChecked(bool(config.click_places_ping))

        radius = min(max(int(config.wheel_radius), _RADIUS_MIN), _RADIUS_MAX)
        self._radius_slider.setValue(radius)
        self._dead_slider.setMaximum(max(_DEAD_MIN, radius - _DEAD_MARGIN))
        dead_zone = min(max(int(config.dead_zone), _DEAD_MIN), self._dead_slider.maximum())
        self._dead_slider.setValue(dead_zone)

        for index, edit in enumerate(self._sector_edits):
            if index < len(config.sectors):
                edit.setText(str(config.sectors[index]))
            else:
                edit.setText(DEFAULT_SECTORS[index % len(DEFAULT_SECTORS)])

        tau_ms = int(round(float(config.animation_tau) * 1000.0))
        self._tau_slider.setValue(min(max(tau_ms, _TAU_MIN_MS), _TAU_MAX_MS))

        self._mark_spin.setValue(
            min(max(int(config.mark_duration_ms), _MARK_MIN_MS), _MARK_MAX_MS)
        )
        self._sound_check.setChecked(bool(config.sound_enabled))
        self._toggle_hotkey_edit.setText(str(config.toggle_hotkey))
        self._sync_trigger_switch()
        self._autostart_check.setChecked(bool(config.start_with_windows))
        self._labels_check.setChecked(bool(config.show_labels))
        self._icons_check.setChecked(bool(config.show_icons))

        icon_size = min(max(int(config.icon_size), _ICON_SIZE_MIN), _ICON_SIZE_MAX)
        self._icon_size_slider.setValue(icon_size)
        for index, combo in enumerate(self._sector_icon_combos):
            icon_id = resolve_icon(config.sector_icons, index)
            position = combo.findData(icon_id)
            combo.setCurrentIndex(position if position >= 0 else 0)

        volume = int(round(float(config.sound_volume) * 100.0))
        self._volume_slider.setValue(min(max(volume, _VOLUME_MIN), _VOLUME_MAX))
        self._hover_ticks_check.setChecked(bool(config.sound_hover_ticks))

        theme_index = self._theme_combo.findData(config.theme)
        self._theme_combo.setCurrentIndex(theme_index if theme_index >= 0 else 0)

        # Setting slider values above fires the handlers, but call them once more
        # so the labels are correct even when the value did not change.
        self._on_radius_changed(self._radius_slider.value())
        self._on_dead_zone_changed(self._dead_slider.value())
        self._on_tau_changed(self._tau_slider.value())
        self._on_icon_size_changed(self._icon_size_slider.value())
        self._on_volume_changed(self._volume_slider.value())
        self._on_icons_toggled(self._icons_check.isChecked())
        self._clear_error()

    def _reset_to_defaults(self) -> None:
        log.debug("resetting settings dialog to defaults")
        self._load_config(Config())

    # ------------------------------------------------------------------ handlers
    def _on_radius_changed(self, value: int) -> None:
        value = int(value)
        self._radius_value.setText(f"{value} px")
        max_dead = max(_DEAD_MIN, value - _DEAD_MARGIN)
        self._dead_slider.setMaximum(max_dead)
        if self._dead_slider.value() > max_dead:
            self._dead_slider.setValue(max_dead)
        self._clear_error()

    def _on_dead_zone_changed(self, value: int) -> None:
        self._dead_value.setText(f"{int(value)} px")
        self._clear_error()

    def _on_tau_changed(self, value: int) -> None:
        self._tau_value.setText(f"{int(value)} ms")
        self._clear_error()

    def _on_icon_size_changed(self, value: int) -> None:
        self._icon_size_value.setText(f"{int(value)} px")
        self._clear_error()

    def _on_volume_changed(self, value: int) -> None:
        self._volume_value.setText(f"{int(value)} %")
        self._clear_error()

    def _on_icons_toggled(self, checked: bool) -> None:
        for widget in self._icon_widgets:
            widget.setEnabled(bool(checked))
        self._clear_error()

    def _on_trigger_switch_toggled(self, enabled: bool) -> None:
        """Forward a user toggle to the application (ignoring programmatic ones)."""
        if self._updating_switch or self._pause_toggled is None:
            return
        self._pause_toggled(bool(enabled))

    def _sync_trigger_switch(self) -> None:
        """Mirror the application's paused state without echoing a signal."""
        if self._pause_state_getter is None:
            return
        enabled = not bool(self._pause_state_getter())
        if self._trigger_switch.isChecked() == enabled:
            return
        self._updating_switch = True
        try:
            self._trigger_switch.setChecked(enabled)
        finally:
            self._updating_switch = False

    # ---------------------------------------------------------------- validation
    def _validate(self) -> str | None:
        """Return an error message, or ``None`` when the form is valid."""
        if not any(box.isChecked() for box in self._modifier_boxes.values()):
            return "Pick at least one trigger modifier (Ctrl, Alt, Shift or Win)."

        hotkey = self._toggle_hotkey_edit.text().strip()
        if not hotkey:
            return "Enter a pause hotkey, for example Ctrl+Shift+Q."
        try:
            keys = parse_hotkey(hotkey)
        except ValueError as exc:
            log.debug("rejected pause hotkey %r: %s", hotkey, exc)
            return f"Invalid pause hotkey: {exc}. Example: Ctrl+Shift+Q."
        except (TypeError, AttributeError):  # pragma: no cover - defensive
            log.exception("pause hotkey parser failed on %r", hotkey)
            return "The pause hotkey could not be validated. Example: Ctrl+Shift+Q."
        if not keys:
            return "Invalid pause hotkey. Example: Ctrl+Shift+Q."

        radius = int(self._radius_slider.value())
        if int(self._dead_slider.value()) > radius - _DEAD_MARGIN:
            return "The dead zone must be at least 20 px smaller than the wheel radius."
        return None

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def _clear_error(self, *_args: object) -> None:
        if self._error_label.isVisible() or self._error_label.text():
            self._error_label.clear()
            self._error_label.setVisible(False)

    def accept(self) -> None:
        """Only close the dialog when the current values are valid."""
        problem = self._validate()
        if problem is not None:
            self._show_error(problem)
            return
        self._clear_error()
        super().accept()
