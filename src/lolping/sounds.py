"""Ping sound.

The sound is synthesised in memory so the project ships without binary assets
and without any Riot Games owned audio. A short decaying sine is generated once
and handed to ``winsound`` for asynchronous playback.
"""

from __future__ import annotations

import logging
import math
import struct

__all__ = ["play_ping"]

log = logging.getLogger(__name__)

try:  # pragma: no cover - the project targets Windows
    import winsound
except ImportError:  # pragma: no cover
    winsound = None  # type: ignore[assignment]

_SAMPLE_RATE = 22_050
_BUFFER: bytes | None = None


def _build_wav(frequency: float = 880.0, duration: float = 0.11) -> bytes:
    """Render a softly decaying sine wave as a mono 16-bit PCM WAV."""
    count = max(1, int(_SAMPLE_RATE * duration))
    frames = bytearray()
    for index in range(count):
        t = index / _SAMPLE_RATE
        # 4 ms attack avoids a click at the start, then an exponential decay.
        attack = min(1.0, t / 0.004)
        envelope = attack * math.exp(-t * 26.0)
        sample = int(9000 * envelope * math.sin(2.0 * math.pi * frequency * t))
        frames += struct.pack("<h", max(-32768, min(32767, sample)))

    data = bytes(frames)
    header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, _SAMPLE_RATE, _SAMPLE_RATE * 2, 2, 16)
    header += b"data" + struct.pack("<I", len(data))
    return header + data


def play_ping(enabled: bool = True) -> None:
    """Play the ping sound if sound is enabled and the platform supports it."""
    global _BUFFER
    if not enabled or winsound is None:
        return
    try:
        if _BUFFER is None:
            _BUFFER = _build_wav()
        winsound.PlaySound(
            _BUFFER, winsound.SND_MEMORY | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        )
    except Exception:  # pragma: no cover - audio device trouble must not crash
        log.exception("cannot play the ping sound")
