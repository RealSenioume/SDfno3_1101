"""Vector icon set for the wheel slices.

Design constraints that shaped this module:

* **No binary assets, no third-party artwork.** Every icon is a set of
  ``QPainterPath`` primitives defined here, so the repository contains no image
  files and no copyrighted ping graphics. This keeps the IP story clean and
  matches design decision D10 in docs/03-design.md.
* **Resolution independent.** Paths live in a unit square (0..1 both axes) and
  are scaled by the painter, so the same icon is crisp at 24 px on a wheel and
  at 96 px inside a mark animation.
* **Cheap at 60 Hz.** The paths are built once at import time and cached; a
  frame only scales and draws them.

Users who want their own artwork can drop a PNG into ``assets/icons/`` and point
``Config.sector_images`` at it; see :func:`load_pixmap`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QTransform

from .config import DEFAULT_SECTOR_ICONS

__all__ = [
    "DEFAULT_ICON_FOR_SECTOR",
    "ICON_IDS",
    "clear_caches",
    "draw_icon",
    "icon_pixmap",
    "load_pixmap",
    "resolve_icon",
]

# --------------------------------------------------------------------------
# Icon geometry. Everything below is authored in a 0..1 square, y downwards.
# --------------------------------------------------------------------------

#: A drawing operation: (path, mode, stroke width in unit space).
Op = tuple[QPainterPath, str, float]

_STROKE = 0.10  # default stroke width, in unit space


def _rotate(path: QPainterPath, degrees: float) -> QPainterPath:
    """Rotate a unit-square path about its centre."""
    transform = QTransform()
    transform.translate(0.5, 0.5)
    transform.rotate(degrees)
    transform.translate(-0.5, -0.5)
    return transform.map(path)


def _arrow_right() -> QPainterPath:
    path = QPainterPath()
    path.moveTo(0.14, 0.37)
    path.lineTo(0.50, 0.37)
    path.lineTo(0.50, 0.18)
    path.lineTo(0.88, 0.50)
    path.lineTo(0.50, 0.82)
    path.lineTo(0.50, 0.63)
    path.lineTo(0.14, 0.63)
    path.closeSubpath()
    return path


def _chevrons() -> QPainterPath:
    path = QPainterPath()
    path.moveTo(0.30, 0.24)
    path.lineTo(0.56, 0.50)
    path.lineTo(0.30, 0.76)
    path.moveTo(0.52, 0.24)
    path.lineTo(0.78, 0.50)
    path.lineTo(0.52, 0.76)
    return path


def _plus() -> QPainterPath:
    path = QPainterPath()
    path.moveTo(0.50, 0.18)
    path.lineTo(0.50, 0.82)
    path.moveTo(0.18, 0.50)
    path.lineTo(0.82, 0.50)
    return path


def _eye() -> QPainterPath:
    path = QPainterPath()
    path.moveTo(0.08, 0.50)
    path.quadTo(0.50, 0.14, 0.92, 0.50)
    path.quadTo(0.50, 0.86, 0.08, 0.50)
    return path


def _pupil() -> QPainterPath:
    path = QPainterPath()
    path.addEllipse(QRectF(0.40, 0.40, 0.20, 0.20))
    return path


def _slash() -> QPainterPath:
    path = QPainterPath()
    path.moveTo(0.16, 0.16)
    path.lineTo(0.84, 0.84)
    return path


def _question() -> QPainterPath:
    """A geometric question mark: hook, stem and a separate dot."""
    path = QPainterPath()
    path.arcMoveTo(QRectF(0.28, 0.12, 0.44, 0.40), 170)
    path.arcTo(QRectF(0.28, 0.12, 0.44, 0.40), 170, -250)
    path.lineTo(0.50, 0.66)
    return path


def _dot_at(x: float, y: float, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addEllipse(QRectF(x - radius, y - radius, radius * 2, radius * 2))
    return path


def _triangle() -> QPainterPath:
    path = QPainterPath()
    path.moveTo(0.50, 0.12)
    path.lineTo(0.92, 0.84)
    path.lineTo(0.08, 0.84)
    path.closeSubpath()
    return path


def _exclamation() -> QPainterPath:
    path = QPainterPath()
    path.moveTo(0.50, 0.36)
    path.lineTo(0.50, 0.60)
    return path


def _bar_and_arrow() -> QPainterPath:
    """Unused placeholder kept out of the registry; see ``_push_arrow``."""
    return QPainterPath()


def _push_arrow() -> QPainterPath:
    """Upward arrow, shrunk, leaving room for the base bar below it."""
    arrow = _rotate(_arrow_right(), -90)
    transform = QTransform()
    transform.translate(0.5, 0.42)
    transform.scale(0.70, 0.70)
    transform.translate(-0.5, -0.5)
    return transform.map(arrow)


def _base_bar() -> QPainterPath:
    path = QPainterPath()
    path.moveTo(0.20, 0.87)
    path.lineTo(0.80, 0.87)
    return path


def _ring() -> QPainterPath:
    path = QPainterPath()
    path.addEllipse(QRectF(0.16, 0.16, 0.68, 0.68))
    return path


#: All icons, in a stable order. Each is a list of drawing operations.
_ICONS: dict[str, tuple[Op, ...]] = {
    "on_my_way": ((_arrow_right(), "fill", 0.0),),
    "all_in": ((_chevrons(), "stroke", 0.12),),
    "assist": ((_plus(), "stroke", 0.16),),
    "vision": ((_eye(), "stroke", _STROKE), (_pupil(), "fill", 0.0)),
    "missing": (
        (_question(), "stroke", 0.12),
        (_dot_at(0.50, 0.82, 0.07), "fill", 0.0),
    ),
    "enemy_vision": (
        (_eye(), "stroke", 0.09),
        (_pupil(), "fill", 0.0),
        (_slash(), "stroke", 0.10),
    ),
    "retreat": ((_rotate(_arrow_right(), 180), "fill", 0.0),),
    "push": ((_push_arrow(), "fill", 0.0), (_base_bar(), "stroke", 0.12)),
    "danger": (
        (_triangle(), "stroke", 0.10),
        (_exclamation(), "stroke", 0.11),
        (_dot_at(0.50, 0.71, 0.055), "fill", 0.0),
    ),
    "generic": ((_ring(), "stroke", 0.10), (_dot_at(0.50, 0.50, 0.12), "fill", 0.0)),
}

#: Icon ids accepted by the configuration and the settings dialog.
ICON_IDS: tuple[str, ...] = tuple(_ICONS)

#: Default icon per slice, clockwise from 3 o'clock, matching DEFAULT_SECTORS.
#: Defined in config.py so the pure-logic layer can validate settings without
#: importing Qt.
DEFAULT_ICON_FOR_SECTOR: tuple[str, ...] = DEFAULT_SECTOR_ICONS


# --------------------------------------------------------------------------
# Drawing
# --------------------------------------------------------------------------
def _ops_for(icon_id: str) -> tuple[Op, ...]:
    try:
        return _ICONS[icon_id]
    except KeyError:
        return _ICONS["generic"]


def draw_icon(
    painter: QPainter,
    icon_id: str,
    rect: QRectF,
    color: QColor,
    stroke_scale: float = 1.0,
) -> None:
    """Draw ``icon_id`` inside ``rect`` in ``color``.

    The painter state is restored before returning, so callers can keep using
    the same painter.
    """
    if rect.width() <= 0 or rect.height() <= 0:
        return
    side = min(rect.width(), rect.height())
    square = QRectF(
        rect.center().x() - side / 2.0, rect.center().y() - side / 2.0, side, side
    )

    painter.save()
    try:
        painter.translate(square.topLeft())
        painter.scale(square.width(), square.height())
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(color)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        for path, mode, width in _ops_for(icon_id):
            if mode == "fill":
                painter.fillPath(path, color)
            elif mode == "stroke":
                pen.setWidthF(max(0.01, width * stroke_scale))
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawPath(path)
    finally:
        painter.restore()


def icon_pixmap(icon_id: str, size: int, color: QColor, dpr: float = 1.0) -> QPixmap:
    """Render an icon to a cached ``QPixmap`` (useful for tray/menu previews)."""
    key = (icon_id, int(size), color.name(), round(float(dpr), 2))
    cached = _PIXMAP_CACHE.get(key)
    if cached is not None:
        return cached

    pixmap = QPixmap(max(1, int(size * dpr)), max(1, int(size * dpr)))
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    try:
        draw_icon(painter, icon_id, QRectF(0, 0, pixmap.width(), pixmap.height()), color)
    finally:
        painter.end()
    pixmap.setDevicePixelRatio(dpr)
    _PIXMAP_CACHE[key] = pixmap
    return pixmap


# --------------------------------------------------------------------------
# Optional user artwork
# --------------------------------------------------------------------------
_PIXMAP_CACHE: dict[tuple, QPixmap] = {}
_FILE_CACHE: dict[tuple, QPixmap | None] = {}


def load_pixmap(path: str, size: int, dpr: float = 1.0) -> QPixmap | None:
    """Load and scale a user-supplied PNG, or ``None`` if it cannot be used.

    Missing files, unreadable files and non-image files are all reported as
    ``None`` so the caller can fall back to the vector icon instead of showing a
    broken slice.
    """
    if not path:
        return None
    key = (str(path), int(size), round(float(dpr), 2))
    if key in _FILE_CACHE:
        return _FILE_CACHE[key]

    source = QPixmap(str(path))
    if source.isNull():
        _FILE_CACHE[key] = None
        return None

    side = max(1, int(size * dpr))
    scaled = source.scaled(
        side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation
    )
    scaled.setDevicePixelRatio(dpr)
    _FILE_CACHE[key] = scaled
    return scaled


def resolve_icon(icons: Iterable[str] | None, index: int) -> str:
    """Return the icon id for slice ``index``, falling back to the default."""
    if icons is not None:
        values = list(icons)
        if 0 <= index < len(values) and values[index] in _ICONS:
            return values[index]
    if 0 <= index < len(DEFAULT_ICON_FOR_SECTOR):
        return DEFAULT_ICON_FOR_SECTOR[index]
    return "generic"


def clear_caches() -> None:
    """Drop cached pixmaps (called when the theme colour changes)."""
    _PIXMAP_CACHE.clear()
    _FILE_CACHE.clear()


def assets_dir() -> Path:
    """Folder where a user may drop their own icons."""
    return Path(__file__).resolve().parents[2] / "assets" / "icons"
