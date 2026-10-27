"""The ping wheel overlay: one transparent always-on-top window per screen.

``OverlayManager`` owns a lazily created ``OverlayWindow`` for every ``QScreen``
and drives it with global (logical pixel) cursor positions.  A window draws two
things:

* the wheel itself, eight pie sectors whose radius and colour follow a smoothed
  per-sector weight (port of the accepted ``pingWheel_BETA`` prototype), with
  optional slice icons and a 0.13 s ease-out open animation, and
* the burst left behind by a committed ping: two expanding rings, five
  directional streaks, a popping slice icon and the sector name, fading out
  over ``config.mark_duration_ms``.

The module is presentation only: it never inspects the input devices.  ``app.py``
turns hook events into ``begin_at`` / ``commit`` / ``cancel`` calls.

Threading: every method must run on the GUI thread.  The 60 Hz timer is only
alive while a window is visible, so an idle overlay costs nothing.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from functools import partial

from PyQt5.QtCore import QObject, QPoint, QPointF, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QScreen,
)
from PyQt5.QtWidgets import QWidget

from . import assets
from .config import Config
from .geometry import (
    approach,
    clamp,
    sector_center_angle,
    sector_index,
    sector_label_point,
    sector_span,
)

log = logging.getLogger(__name__)

__all__ = ["OverlayManager", "OverlayWindow", "THEME_ACCENTS"]

#: Accent colour per ``Config.theme`` value.
THEME_ACCENTS: dict[str, tuple[int, int, int]] = {
    "gold": (220, 180, 60),
    "blue": (90, 160, 240),
    "red": (230, 90, 80),
}

_DEFAULT_ACCENT = THEME_ACCENTS["gold"]

_FRAME_INTERVAL_MS = 16  # ~60 Hz
_MAX_FRAME_DT = 0.05  # clamp dt so a stalled frame does not jump the animation
_RADIUS_GROWTH = 8.0  # extra radius of a fully highlighted sector
_GLOW_WIDTH = 12.0  # width of the translucent halo behind the hovered sector
_CENTRE_RADIUS = 42.0
_CENTRE_TEXT_WIDTH = 68.0
_LABEL_RADIUS_FACTOR = 0.72
_LABEL_RADIUS_WITH_ICONS = 0.80
_LABEL_POINT_SIZE = 8
_CENTRE_POINT_SIZE = 10
_MARK_LABEL_POINT_SIZE = 9
_MARK_LABEL_MAX_WIDTH = 160.0
_MIN_POINT_SIZE = 6

# --- v0.3 wheel open animation -------------------------------------------------
_OPEN_DURATION = 0.13  # seconds from "invisible small wheel" to full size
_OPEN_START_SCALE = 0.70  # sector radius at the first frame, as a fraction of R

# --- v0.3 slice icons ----------------------------------------------------------
_ICON_RADIUS_FACTOR = 0.60  # icon centre, as a fraction of the slice radius
_ICON_HOVER_GROWTH = 0.10  # hovered icon is 10 % bigger
_ICON_IDLE_COLOUR = (235, 235, 235)
_ICON_IDLE_ALPHA = 200

# --- v0.3 release burst --------------------------------------------------------
_BURST_ANGLES = (-18.0, -9.0, 0.0, 9.0, 18.0)  # degrees around the slice centre
_BURST_START_RADIUS = 46.0
_BURST_MAX_RADIUS = 92.0
_BURST_LINE_LENGTH = 26.0
_BURST_LINE_ALPHA = 220


@dataclass
class _Mark:
    """One burst left behind by a committed ping."""

    name: str
    pos: QPoint
    start: float
    duration: float
    sector: int = -1


class OverlayWindow(QWidget):
    """A full-screen transparent wheel window for a single ``QScreen``.

    The window never takes focus and never lets the opening click reach the
    application underneath (``WA_TransparentForMouseEvents`` is deliberately
    *not* set).
    """

    committed = pyqtSignal(str)  # sector name
    cancelled = pyqtSignal()
    hover_changed = pyqtSignal(int)  # hovered slice index, -1 in the dead zone

    def __init__(self, screen: QScreen, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._screen: QScreen | None = screen
        self._config = config
        self._count = max(1, int(config.sector_count))
        self._weights: list[float] = [0.0] * self._count
        self._center = QPoint()
        self._hover = -1
        self._open = False
        self._marks: list[_Mark] = []
        self._last_tick = time.perf_counter()
        self._opened_at = 0.0

        self._setup_window()

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.setInterval(_FRAME_INTERVAL_MS)
        self._timer.timeout.connect(self.tick)

        self._apply_geometry()
        self.hide()

    # ------------------------------------------------------------------- setup
    def _setup_window(self) -> None:
        """Apply the flags/attributes required by docs/00-interfaces.md section 6."""
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setWindowTitle("lolping overlay")
        # Not setting WA_TransparentForMouseEvents: the window must swallow the
        # click that opened it so the game/app below does not also react.

    def target_screen(self) -> QScreen | None:
        """Return the screen this window was created for (may have gone stale)."""
        return self._screen

    def refit(self) -> None:
        """Re-apply ``screen.geometry()``; harmless when the screen is gone."""
        self._apply_geometry()

    def _screen_rect(self) -> QRect | None:
        """Best-effort geometry of our screen, never raising on a stale object."""
        screen = self._screen
        if screen is not None:
            try:
                rect = screen.geometry()
            except RuntimeError:  # the C++ QScreen was destroyed under us
                self._screen = None
                log.debug("overlay screen disappeared, falling back to the primary screen")
            else:
                if rect.width() > 0 and rect.height() > 0:
                    return rect

        candidates: list[QScreen | None] = []
        try:
            candidates.append(QGuiApplication.screenAt(QPoint(self._center)))
        except (TypeError, AttributeError, RuntimeError):
            log.debug("QGuiApplication.screenAt unavailable", exc_info=True)
        candidates.append(QGuiApplication.primaryScreen())
        for candidate in candidates:
            if candidate is None or candidate is screen:
                continue
            try:
                rect = candidate.geometry()
            except RuntimeError:
                continue
            if rect.width() > 0 and rect.height() > 0:
                return rect
        return None

    def _apply_geometry(self) -> None:
        rect = self._screen_rect()
        if rect is None:
            return
        try:
            if self.geometry() != rect:
                self.setGeometry(rect)
        except RuntimeError:  # pragma: no cover - window already destroyed
            log.debug("cannot apply overlay geometry", exc_info=True)

    # ----------------------------------------------------------------- public
    def set_config(self, config: Config) -> None:
        """Apply new settings; a wheel that is already open updates in place."""
        self._config = config
        count = max(1, int(config.sector_count))
        if count != self._count:
            self._count = count
            self._weights = [0.0] * count
        if self._open:
            self._hover = self._hovered_sector()
            self.update()

    def begin(self, global_pos: QPoint) -> None:
        """Show the wheel centred on ``global_pos`` and start the animation."""
        self._apply_geometry()
        self._center = QPoint(global_pos)
        self._open = True
        self._hover = -1
        self._weights = [0.0] * self._count
        self._last_tick = time.perf_counter()
        self._opened_at = self._last_tick  # drives the 0.13 s open animation

        # Show without activating: no showNormal/activateWindow/focus call here.
        self.show()
        self.raise_()
        # Paint the first frame synchronously: the latency probe measures the
        # time from mouse-down to the first painted frame.
        self.repaint()
        if not self._timer.isActive():
            self._timer.start()

    def cancel(self) -> None:
        """Close the wheel without a ping; emits ``cancelled`` if it was open."""
        if not self._open:
            return
        self._open = False
        self._hover = -1
        self._weights = [0.0] * self._count
        self.cancelled.emit()
        self._finish_if_idle()

    def commit(self) -> str | None:
        """Resolve the sector under the cursor right now and ping it.

        Returns the sector name, or ``None`` when the cursor is inside the dead
        zone (which cancels the wheel, like the prototype did).
        """
        if not self._open:
            return None
        index = self._hovered_sector()
        if index < 0:
            self.cancel()
            return None

        name = self._sector_name(index)
        centre = QPoint(self._center)

        # Drop the burst first so the window stays busy animating it, then clear
        # the wheel state and repaint once so the wheel vanishes immediately.
        self.add_mark(name, centre, index)
        self._open = False
        self._hover = -1
        self._weights = [0.0] * self._count
        self.repaint()
        self.committed.emit(name)
        return name

    def add_mark(self, name: str, global_pos: QPoint, sector: int = -1) -> None:
        """Animate a ping burst at ``global_pos``.

        ``sector`` is the committed slice index (used for the directional
        streaks and the icon pop); it is optional so callers from v0.2 that pass
        only ``(name, global_pos)`` keep working.
        """
        duration = max(0.05, float(self._config.mark_duration_ms) / 1000.0)
        self._marks.append(
            _Mark(
                name=str(name),
                pos=QPoint(global_pos),
                start=time.perf_counter(),
                duration=duration,
                sector=int(sector),
            )
        )
        self._apply_geometry()
        if not self.isVisible():
            # A mark may outlive the last visible frame; make sure it is seen.
            self.show()
            self.raise_()
        if not self._timer.isActive():
            self._last_tick = time.perf_counter()
            self._timer.start()
        self.update()

    def is_open(self) -> bool:
        return self._open

    # --------------------------------------------------------------- animation
    def tick(self) -> None:
        """Advance weights/marks by one frame; called by the 60 Hz timer."""
        now = time.perf_counter()
        dt = clamp(now - self._last_tick, 0.0, _MAX_FRAME_DT)
        self._last_tick = now

        if not self.isVisible():
            self._timer.stop()
            return

        # Screen hot-plug/resolution changes are cheap to notice here and far
        # more robust than keeping QScreen signal connections alive.
        self._apply_geometry()

        if self._open:
            hover = self._hovered_sector()
            if hover != self._hover:
                self._hover = hover
                # Sound layer in app.py listens to this; emit only on changes.
                self.hover_changed.emit(hover)
            tau = max(float(self._config.animation_tau), 0.001)
            weights = self._weights
            for index in range(self._count):
                target = 1.0 if index == self._hover else 0.0
                weights[index] = approach(weights[index], target, dt, tau)

        if self._marks:
            self._marks = [mark for mark in self._marks if now - mark.start < mark.duration]

        if self._open or self._marks:
            self.update()
        else:
            self._finish_if_idle()

    def _finish_if_idle(self) -> None:
        """Stop the timer and hide once neither the wheel nor a mark is left."""
        if self._open or self._marks:
            return
        self._timer.stop()
        if self.isVisible():
            # Clear the backing store before hiding, like the prototype did,
            # otherwise a stale wheel can flash on screen again.
            self.update()
            self.repaint()
            self.hide()

    # ------------------------------------------------------------- Qt overrides
    def showEvent(self, event) -> None:  # noqa: N802 - Qt name
        self._last_tick = time.perf_counter()
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt name
        self._timer.stop()
        self._open = False
        self._hover = -1
        self._weights = [0.0] * self._count
        self._marks.clear()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt name
        self._timer.stop()
        self._open = False
        self._marks.clear()
        super().closeEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt name
        # Swallow the trigger click; the global hook owns the gesture.
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt name
        event.accept()

    def shutdown(self) -> None:
        """Stop all activity and release the native window (manager cleanup)."""
        self._timer.stop()
        self._open = False
        self._hover = -1
        self._marks.clear()
        self._weights = [0.0] * self._count
        try:
            self.hide()
            self.close()
        except RuntimeError:  # pragma: no cover - already destroyed
            return
        self.deleteLater()

    # ------------------------------------------------------------------ helpers
    def _hovered_sector(self) -> int:
        """Hit-test the global cursor against the wheel using ``geometry``."""
        cursor = QCursor.pos()
        dx = float(cursor.x() - self._center.x())
        dy = float(cursor.y() - self._center.y())
        try:
            return sector_index(dx, dy, float(self._config.dead_zone), self._count)
        except ValueError:  # pragma: no cover - config is clamped by config.py
            log.debug("invalid sector maths input; treating the cursor as dead centre")
            return -1

    def _sector_name(self, index: int) -> str:
        sectors = self._config.sectors
        if 0 <= index < len(sectors):
            name = str(sectors[index]).strip()
            if name:
                return name
        return f"Sector {index + 1}"

    def _accent(self) -> QColor:
        rgb = THEME_ACCENTS.get(str(self._config.theme).lower(), _DEFAULT_ACCENT)
        return QColor(rgb[0], rgb[1], rgb[2])

    def _sector_arc(self, index: int) -> tuple[int, int]:
        """Qt ``drawPie`` start/span in 1/16 degree (counter-clockwise)."""
        start, end = sector_span(index, self._count)
        span = end - start
        return int(round(-(start + span) * 16.0)), int(round(span * 16.0))

    @staticmethod
    def _pie_rect(cx: float, cy: float, radius: float) -> QRect:
        r = max(1, int(round(radius)))
        return QRect(int(round(cx)) - r, int(round(cy)) - r, r * 2, r * 2)

    # ------------------------------------------------- v0.3 animation/icon aids
    def _open_ease(self, now: float) -> float:
        """Ease-out progress of the wheel open animation, in ``[0, 1]``."""
        if not self._open:
            return 1.0
        progress = clamp((now - self._opened_at) / _OPEN_DURATION, 0.0, 1.0)
        return 1.0 - (1.0 - progress) ** 3

    @staticmethod
    def _ease_out_back(progress: float) -> float:
        """Overshooting ease-out used by the icon pop (peaks near 1.1)."""
        c1 = 1.70158
        c3 = c1 + 1.0
        shifted = progress - 1.0
        return 1.0 + c3 * shifted**3 + c1 * shifted**2

    def _device_pixel_ratio(self) -> float:
        try:
            return float(self.devicePixelRatioF())
        except AttributeError:  # pragma: no cover - Qt < 5.6
            return 1.0

    def _draw_slice_icon(
        self,
        painter: QPainter,
        index: int,
        cx: float,
        cy: float,
        size: float,
        colour: QColor,
        opacity: float = 1.0,
    ) -> None:
        """Draw slice ``index``'s user image or vector icon, centred and masked.

        A user-supplied image is clipped to a circle so a rectangular PNG still
        reads as a slice icon; a missing or broken image falls back to the
        vector icon from :mod:`lolping.assets`.
        """
        if size < 1.0:
            return

        config = self._config
        images = config.sector_images or []
        path = str(images[index]).strip() if 0 <= index < len(images) else ""
        if path:
            pixmap = assets.load_pixmap(
                path, max(1, int(round(size))), self._device_pixel_ratio()
            )
            if pixmap is not None and not pixmap.isNull():
                ratio = float(pixmap.devicePixelRatio()) or 1.0
                width = pixmap.width() / ratio
                height = pixmap.height() / ratio
                painter.save()
                try:
                    painter.setOpacity(clamp(opacity, 0.0, 1.0))
                    clip = QPainterPath()
                    clip.addEllipse(QRectF(cx - size / 2.0, cy - size / 2.0, size, size))
                    painter.setClipPath(clip)
                    painter.drawPixmap(
                        QPointF(cx - width / 2.0, cy - height / 2.0), pixmap
                    )
                finally:
                    painter.restore()
                return

        assets.draw_icon(
            painter,
            assets.resolve_icon(config.sector_icons, index),
            QRectF(cx - size / 2.0, cy - size / 2.0, size, size),
            colour,
        )

    # ------------------------------------------------------------------- paint
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt name
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.TextAntialiasing, True)
            # Transparent frame: explicitly clear the backing store so hiding a
            # window can never resurrect pixels from a previous frame.
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

            now = time.perf_counter()
            if self._open:
                self._paint_wheel(painter, now)
            if self._marks:
                for mark in self._marks:
                    self._paint_mark(painter, mark, now)
        finally:
            painter.end()

    def _paint_wheel(self, painter: QPainter, now: float) -> None:
        config = self._config
        count = self._count
        centre = self.mapFromGlobal(self._center)
        cx = float(centre.x())
        cy = float(centre.y())
        ease = self._open_ease(now)
        base_radius = max(20.0, float(config.wheel_radius))
        accent = self._accent()
        gray = (60.0, 60.0, 60.0)
        weights = self._weights
        # Open animation: grow from 70 % to 100 % of the radius and fade in.
        radius_scale = _OPEN_START_SCALE + (1.0 - _OPEN_START_SCALE) * ease
        radii = [
            (base_radius + _RADIUS_GROWTH * weights[index]) * radius_scale
            for index in range(count)
        ]

        # 1) Translucent glow pass behind every visible sector.
        painter.setPen(Qt.NoPen)
        for index in range(count):
            weight = weights[index]
            if weight < 0.02:
                continue
            radius = radii[index] + _GLOW_WIDTH
            start16, span16 = self._sector_arc(index)
            glow = QColor(accent)
            glow.setAlpha(int(round(90 * weight * ease)))
            painter.setBrush(glow)
            painter.drawPie(self._pie_rect(cx, cy, radius), start16, span16)

        # 2) Sectors, lightest first so the hovered one ends up on top.
        for index in sorted(range(count), key=lambda item: weights[item]):
            weight = weights[index]
            radius = radii[index]
            start16, span16 = self._sector_arc(index)

            fill = QColor(
                int(round(gray[0] + (accent.red() - gray[0]) * weight)),
                int(round(gray[1] + (accent.green() - gray[1]) * weight)),
                int(round(gray[2] + (accent.blue() - gray[2]) * weight)),
            )
            fill.setAlpha(int(round((110 + (240 - 110) * weight) * ease)))

            pen_colour = QColor(255, 255, 255)
            pen_colour.setAlpha(int(round((80 + (255 - 80) * weight) * ease)))

            painter.setBrush(fill)
            painter.setPen(QPen(pen_colour, 1.0 + 2.0 * weight))
            painter.drawPie(self._pie_rect(cx, cy, radius), start16, span16)

        # 3) Slice icons on the 0.60 R circle, when enabled.
        if config.show_icons:
            icon_base = float(config.icon_size)
            for index in range(count):
                weight = weights[index]
                size = icon_base * (1.0 + _ICON_HOVER_GROWTH * weight) * ease
                if size < 1.0:
                    continue
                angle = math.radians(sector_center_angle(index, count))
                icon_radius = radii[index] * _ICON_RADIUS_FACTOR
                icon_x = cx + icon_radius * math.cos(angle)
                icon_y = cy + icon_radius * math.sin(angle)
                if weight > 0.5:
                    colour = QColor(accent)
                    colour.setAlpha(int(round(255 * ease)))
                else:
                    colour = QColor(*_ICON_IDLE_COLOUR)
                    colour.setAlpha(int(round(_ICON_IDLE_ALPHA * ease)))
                self._draw_slice_icon(painter, index, icon_x, icon_y, size, colour, ease)

        # 4) Sector labels, pushed outwards when the icons claim the inner ring.
        #    Hidden while the cursor sits in the dead zone.
        if config.show_labels and 0 <= self._hover < count:
            label_factor = (
                _LABEL_RADIUS_WITH_ICONS if config.show_icons else _LABEL_RADIUS_FACTOR
            )
            for index in range(count):
                label_x, label_y = sector_label_point(
                    cx, cy, index, radii[index] * label_factor, count
                )
                colour = QColor(255, 255, 255)
                colour.setAlpha(
                    int(round((255 if index == self._hover else 190) * ease))
                )
                max_width = max(28.0, radii[index] * 0.60)
                self._draw_centred_text(
                    painter,
                    self._sector_name(index),
                    label_x,
                    label_y,
                    _LABEL_POINT_SIZE,
                    max_width,
                    colour,
                )

        # 5) Dark centre disc with the current sector name. It fades to 25 % of
        #    its alpha instead of zero so the wheel never blinks out completely.
        disc = max(0.25, ease)
        painter.setBrush(QColor(30, 30, 30, int(round(230 * disc))))
        painter.setPen(QPen(QColor(255, 255, 255, int(round(255 * disc))), 2.0))
        painter.drawEllipse(QPointF(cx, cy), _CENTRE_RADIUS, _CENTRE_RADIUS)

        text = self._sector_name(self._hover) if self._hover >= 0 else "Caution"
        text_colour = QColor(255, 255, 255) if self._hover < 0 else QColor(accent)
        text_colour.setAlpha(int(round(255 * disc)))
        self._draw_centred_text(
            painter,
            text,
            cx,
            cy,
            _CENTRE_POINT_SIZE,
            _CENTRE_TEXT_WIDTH,
            text_colour,
        )

    def _paint_mark(self, painter: QPainter, mark: _Mark, now: float) -> None:
        elapsed = now - mark.start
        duration = max(mark.duration, 0.001)
        progress = clamp(elapsed / duration, 0.0, 1.0)
        if progress >= 1.0:
            return

        point = self.mapFromGlobal(mark.pos)
        px = float(point.x())
        py = float(point.y())
        accent = self._accent()
        outer_radius = 18.0

        # a) Two expanding rings, the second one slightly delayed.
        for delay in (0.0, 0.14):
            if progress < delay:
                continue
            window = max(0.001, 1.0 - delay)
            local = clamp((progress - delay) / window, 0.0, 1.0)
            radius = 18.0 + 78.0 * (1.0 - (1.0 - local) ** 2)
            outer_radius = max(outer_radius, radius)
            ring_colour = QColor(accent)
            ring_colour.setAlpha(int(round(235 * (1.0 - local))))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(ring_colour, 4.0 - 3.0 * local))
            painter.drawEllipse(QPointF(px, py), radius, radius)

        # b) Five short streaks flying outwards along the committed slice.
        if mark.sector >= 0:
            flight = clamp((progress - 0.05) / 0.50, 0.0, 1.0)
            if progress >= 0.05 and flight < 1.0:
                eased = 1.0 - (1.0 - flight) ** 2
                inner = _BURST_START_RADIUS + (
                    _BURST_MAX_RADIUS - _BURST_LINE_LENGTH - _BURST_START_RADIUS
                ) * eased
                inner = min(inner, _BURST_MAX_RADIUS - _BURST_LINE_LENGTH)
                outer = min(_BURST_MAX_RADIUS, inner + _BURST_LINE_LENGTH)
                streak_colour = QColor(accent)
                streak_colour.setAlpha(int(round(_BURST_LINE_ALPHA * (1.0 - flight))))
                painter.setPen(QPen(streak_colour, 3.0, Qt.SolidLine, Qt.RoundCap))
                centre_angle = sector_center_angle(mark.sector, self._count)
                for offset in _BURST_ANGLES:
                    angle = math.radians(centre_angle + offset)
                    cos_angle = math.cos(angle)
                    sin_angle = math.sin(angle)
                    painter.drawLine(
                        QPointF(px + cos_angle * inner, py + sin_angle * inner),
                        QPointF(px + cos_angle * outer, py + sin_angle * outer),
                    )

        # c) The committed slice icon pops at the centre, then fades out.
        tail = clamp((1.0 - progress) / 0.40, 0.0, 1.0)
        if mark.sector >= 0 and tail > 0.01:
            pop = min(1.12, max(0.0, self._ease_out_back(clamp(progress / 0.30, 0.0, 1.0))))
            icon_size = float(self._config.icon_size) * pop
            if icon_size >= 1.0:
                icon_colour = QColor(accent)
                icon_colour.setAlpha(int(round(255 * tail)))
                self._draw_slice_icon(
                    painter, mark.sector, px, py, icon_size, icon_colour, tail
                )

        # d) Name above the outer ring, fading with the same tail.
        if mark.name and tail > 0.02:
            font, metrics = self._fitted_font(
                painter, mark.name, _MARK_LABEL_POINT_SIZE, _MARK_LABEL_MAX_WIDTH
            )
            width = metrics.horizontalAdvance(mark.name)
            baseline = py - outer_radius - 14.0 + metrics.ascent() / 2.0
            left = px - width / 2.0
            painter.setFont(font)
            halo = QColor(0, 0, 0, int(round(170 * tail)))
            painter.setPen(halo)
            for offset_x, offset_y in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                painter.drawText(QPointF(left + offset_x, baseline + offset_y), mark.name)
            label = QColor(255, 255, 255)
            label.setAlpha(int(round(255 * tail)))
            painter.setPen(label)
            painter.drawText(QPointF(left, baseline), mark.name)

    # -------------------------------------------------------------- text helpers
    @staticmethod
    def _fitted_font(
        painter: QPainter, text: str, point_size: int, max_width: float
    ) -> tuple[QFont, QFontMetrics]:
        """Return a bold font (and its metrics) small enough for ``max_width``."""
        font = QFont("Arial", point_size, QFont.Bold)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        while metrics.horizontalAdvance(text) > max_width and font.pointSize() > _MIN_POINT_SIZE:
            font.setPointSize(font.pointSize() - 1)
            painter.setFont(font)
            metrics = painter.fontMetrics()
        return font, metrics

    def _draw_centred_text(
        self,
        painter: QPainter,
        text: str,
        x: float,
        y: float,
        point_size: int,
        max_width: float,
        colour: QColor,
    ) -> None:
        font, metrics = self._fitted_font(painter, text, point_size, max_width)
        painter.setFont(font)
        painter.setPen(colour)
        baseline = y + (metrics.ascent() - metrics.descent()) / 2.0
        painter.drawText(QPointF(x - metrics.horizontalAdvance(text) / 2.0, baseline), text)


class OverlayManager(QObject):
    """Owns one ``OverlayWindow`` per screen and relays its public signals."""

    committed = pyqtSignal(str, object)  # (sector name, global QPoint centre)
    hover_changed = pyqtSignal(int)  # hovered slice index of the active wheel

    def __init__(self, config: Config, parent: QObject | None = None) -> None:
        # app.py passes its controller (a plain object) as parent in one place;
        # tolerate that instead of failing to start the tray app.
        if parent is not None and not isinstance(parent, QObject):
            log.debug("ignoring non-QObject overlay parent %r", type(parent).__name__)
            parent = None
        super().__init__(parent)

        self._config = config
        # Keyed by (screen name, id(screen)): the name is the readable key and
        # object identity breaks ties for duplicate/empty screen names.
        self._windows: dict[tuple[str, int], OverlayWindow] = {}
        self._centres: dict[OverlayWindow, QPoint] = {}
        self._active: OverlayWindow | None = None
        self._app: QGuiApplication | None = None

        application = QGuiApplication.instance()
        if isinstance(application, QGuiApplication):
            self._app = application
            try:
                application.screenAdded.connect(self._on_screen_added)
                application.screenRemoved.connect(self._on_screen_removed)
            except (TypeError, RuntimeError):  # pragma: no cover - exotic Qt
                log.debug("cannot connect to QGuiApplication screen signals", exc_info=True)

    # ------------------------------------------------------------------ public
    def set_config(self, config: Config) -> None:
        """Store the config and let every live window pick it up immediately."""
        self._config = config
        for key, window in list(self._windows.items()):
            try:
                window.set_config(config)
            except RuntimeError:  # pragma: no cover - window died with its screen
                self._drop_window(key, window)

    def begin_at(self, global_pos: QPoint) -> None:
        """Open the wheel centred on ``global_pos`` on the screen under it."""
        position = QPoint(global_pos)
        screen = self._screen_at(position)
        if screen is None:
            log.warning(
                "no screen found at (%s, %s); cannot open the wheel",
                position.x(),
                position.y(),
            )
            return

        previous = self._active
        if previous is not None and previous.is_open():
            self._active = None
            try:
                previous.cancel()
            except RuntimeError:  # pragma: no cover
                log.debug("previous overlay window vanished", exc_info=True)

        window = self._window_for(screen)
        window.set_config(self._config)
        self._centres[window] = position
        self._active = window
        window.begin(position)

    def cancel(self) -> None:
        """Close whichever wheel is open, without emitting ``committed``."""
        active = self._active
        if active is not None:
            self._active = None
            try:
                active.cancel()
            except RuntimeError:  # pragma: no cover
                log.debug("overlay window vanished during cancel", exc_info=True)
            return
        for window in list(self._windows.values()):
            try:
                if window.is_open():
                    window.cancel()
            except RuntimeError:  # pragma: no cover
                continue

    def commit(self) -> str | None:
        """Commit the active wheel; returns the sector name or ``None``."""
        window = self._active
        if window is None:
            return None
        try:
            name = window.commit()
        except RuntimeError:  # pragma: no cover - window died mid-gesture
            log.debug("overlay window vanished during commit", exc_info=True)
            self._active = None
            return None
        if name is None:
            self._active = None
        return name

    def is_open(self) -> bool:
        if self._active is None:
            return False
        try:
            return self._active.is_open()
        except RuntimeError:  # pragma: no cover
            self._active = None
            return False

    def shutdown(self) -> None:
        """Release all overlay windows and disconnect from the screen signals."""
        for key, window in list(self._windows.items()):
            self._drop_window(key, window)
        self._windows.clear()
        self._centres.clear()
        self._active = None

        application = self._app
        self._app = None
        if application is None:
            return
        try:
            signals = (
                (application.screenAdded, self._on_screen_added),
                (application.screenRemoved, self._on_screen_removed),
            )
        except RuntimeError:  # pragma: no cover - application already destroyed
            log.debug("application vanished before the overlay shutdown", exc_info=True)
            return
        for signal, slot in signals:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):  # pragma: no cover - already gone
                log.debug("screen signal already disconnected", exc_info=True)

    # ----------------------------------------------------------------- internal
    @staticmethod
    def _screen_at(position: QPoint) -> QScreen | None:
        try:
            screen = QGuiApplication.screenAt(position)
        except (TypeError, AttributeError, RuntimeError):
            screen = None
            log.debug("QGuiApplication.screenAt failed", exc_info=True)
        if screen is not None:
            return screen

        try:
            screens = QGuiApplication.screens()
        except (AttributeError, RuntimeError):  # pragma: no cover - no GUI at all
            screens = []
        for candidate in screens:
            try:
                if candidate.geometry().contains(position):
                    return candidate
            except RuntimeError:
                continue
        return QGuiApplication.primaryScreen()

    @staticmethod
    def _screen_key(screen: QScreen) -> tuple[str, int]:
        name = ""
        try:
            name = str(screen.name() or "")
        except RuntimeError:  # pragma: no cover - destroyed screen wrapper
            log.debug("cannot read QScreen.name()", exc_info=True)
        return (name, id(screen))

    def _window_for(self, screen: QScreen) -> OverlayWindow:
        """Lazily create (or reuse) the window belonging to ``screen``."""
        key = self._screen_key(screen)
        window = self._windows.get(key)
        if window is not None and window.target_screen() is screen:
            return window

        # A screen may be re-registered under a different name; reuse by identity.
        for other_key, other in list(self._windows.items()):
            if other.target_screen() is screen:
                self._windows.pop(other_key, None)
                self._windows[key] = other
                return other

        window = OverlayWindow(screen, self._config)
        window.committed.connect(partial(self._relay_committed, window))
        window.cancelled.connect(self._clear_active)
        window.hover_changed.connect(partial(self._relay_hover, window))
        self._windows[key] = window
        log.debug("created overlay window for screen %r", key[0])
        return window

    def _relay_committed(self, window: OverlayWindow, name: str) -> None:
        centre = self._centres.get(window)
        centre = QPoint(centre) if centre is not None else QPoint()
        if self._active is window:
            self._active = None
        self.committed.emit(str(name), centre)

    def _relay_hover(self, window: OverlayWindow, hover: int) -> None:
        """Only the wheel that is currently open may drive the hover signal."""
        if self._active is window and window.is_open():
            self.hover_changed.emit(int(hover))

    def _clear_active(self) -> None:
        active = self._active
        if active is not None and not active.is_open():
            self._active = None

    def _drop_window(self, key: tuple[str, int], window: OverlayWindow) -> None:
        self._windows.pop(key, None)
        self._centres.pop(window, None)
        if self._active is window:
            self._active = None
        try:
            window.shutdown()
        except RuntimeError:  # pragma: no cover - already destroyed
            log.debug("overlay window already destroyed", exc_info=True)

    # ------------------------------------------------------------- screen events
    def _on_screen_added(self, screen: QScreen) -> None:
        log.debug("screen added")
        self._refit_all()

    def _on_screen_removed(self, screen: QScreen) -> None:
        log.debug("screen removed")
        for key, window in list(self._windows.items()):
            if window.target_screen() is screen:
                self._drop_window(key, window)
        self._refit_all()

    def _refit_all(self) -> None:
        for key, window in list(self._windows.items()):
            try:
                window.refit()
            except RuntimeError:  # pragma: no cover - window died with its screen
                self._drop_window(key, window)
