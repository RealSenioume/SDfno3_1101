"""Synthesised sound cues for the wheel.

Every cue is generated in code at start-up and cached as a WAV byte string, so
the project ships no audio files and no third-party (Riot Games) sound assets.
Playback goes through ``winsound`` with ``SND_MEMORY | SND_ASYNC``: no temporary
files, no blocking of the GUI thread.

Cue lengths are deliberately short. The wheel is a ~100 ms interaction; anything
longer than ~200 ms would still be playing during the next gesture.

Note on mixing: ``winsound`` plays one asynchronous sound at a time, so a new cue
replaces the previous one. For a tick-per-hover design that is acceptable and
keeps the module dependency-free; it is documented as a limitation in
docs/03-design.md.
"""

from __future__ import annotations

import logging
import math
import struct

__all__ = ["CUE_NAMES", "clear_cache", "play", "render_wav"]

log = logging.getLogger(__name__)

try:  # pragma: no cover - the project targets Windows
    import winsound
except ImportError:  # pragma: no cover
    winsound = None  # type: ignore[assignment]

_RATE = 22_050
_MAX_AMPLITUDE = 30_000
_VOLUME_STEPS = 10
_CUE_NAMES: tuple[str, ...] = ("open", "hover", "commit", "cancel")

#: Pentatonic scale, one note per slice, so every slice sounds slightly different.
_SCALE = (392.00, 440.00, 493.88, 523.25, 587.33, 659.25, 783.99, 880.00)

_CACHE: dict[tuple[str, int, int], bytes] = {}
_PLAYING: dict[int, bytes] = {}  # keeps buffers alive while winsound plays them


def CUE_NAMES() -> tuple[str, ...]:
    """All cue names accepted by :func:`play`."""
    return _CUE_NAMES


# --------------------------------------------------------------------- synthesis
def _sine(
    frequency: float,
    duration: float,
    *,
    decay: float = 20.0,
    attack: float = 0.004,
    sweep: float = 0.0,
    harmonic: float = 0.0,
) -> list[float]:
    """A decaying (optionally swept) sine, plus an optional 2nd harmonic."""
    count = max(1, int(_RATE * duration))
    samples: list[float] = []
    phase = 0.0
    for index in range(count):
        t = index / _RATE
        freq = frequency + sweep * t
        phase += 2.0 * math.pi * freq / _RATE
        envelope = math.exp(-decay * t)
        if attack > 0.0:
            envelope *= min(1.0, t / attack)
        value = math.sin(phase)
        if harmonic:
            value += harmonic * math.sin(2.0 * phase)
        samples.append(envelope * value)
    return samples


def _mix_into(
    target: list[float], source: list[float], offset: int, gain: float = 1.0
) -> None:
    for index, value in enumerate(source):
        position = offset + index
        if position >= len(target):
            break
        target[position] += value * gain


def _samples_for(cue: str, index: int) -> list[float]:
    """Build the raw float samples for one cue."""
    if cue == "open":
        # A soft upward blip: "the wheel is here".
        return _sine(420.0, 0.075, decay=34.0, sweep=520.0, harmonic=0.18)

    if cue == "hover":
        # Very short high tick: the radial-menu click.
        return _sine(1500.0, 0.028, decay=110.0, attack=0.001, harmonic=0.35)

    if cue == "commit":
        note = _SCALE[index % len(_SCALE)]
        buffer = [0.0] * int(_RATE * 0.20)
        _mix_into(buffer, _sine(note, 0.13, decay=24.0, harmonic=0.25), 0, 0.85)
        _mix_into(
            buffer,
            _sine(note * 1.5, 0.16, decay=20.0, harmonic=0.15),
            int(_RATE * 0.055),
            0.55,
        )
        return buffer

    if cue == "cancel":
        # Downward sweep: "never mind".
        return _sine(340.0, 0.095, decay=30.0, sweep=-1600.0)

    raise ValueError(f"unknown cue {cue!r}, expected one of {_CUE_NAMES}")


def _to_wav(samples: list[float], volume: float) -> bytes:
    """Quantise float samples into a mono 16-bit PCM WAV byte string."""
    peak = max((abs(value) for value in samples), default=0.0)
    scale = (volume * _MAX_AMPLITUDE) / peak if peak > 0.0 else 0.0
    frames = bytearray()
    for value in samples:
        sample = int(max(-32768, min(32767, value * scale)))
        frames += struct.pack("<h", sample)

    data = bytes(frames)
    header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, _RATE, _RATE * 2, 2, 16)
    header += b"data" + struct.pack("<I", len(data))
    return header + data


def render_wav(cue: str, volume: float = 0.5, index: int = 0) -> bytes:
    """Return the WAV bytes for ``cue``; results are cached by volume step."""
    if cue not in _CUE_NAMES:
        raise ValueError(f"unknown cue {cue!r}, expected one of {_CUE_NAMES}")
    step = max(0, min(_VOLUME_STEPS, int(round(volume * _VOLUME_STEPS))))
    key = (cue, index % 8, step)
    cached = _CACHE.get(key)
    if cached is None:
        cached = _to_wav(_samples_for(cue, index), step / _VOLUME_STEPS)
        _CACHE[key] = cached
    return cached


# --------------------------------------------------------------------- playback
def play(cue: str, volume: float = 0.5, index: int = 0) -> None:
    """Play a cue asynchronously. Never raises: audio failure is not fatal."""
    if winsound is None:
        return
    try:
        data = render_wav(cue, volume, index)
        _PLAYING[id(data)] = data  # keep the buffer alive for the async player
        winsound.PlaySound(
            data, winsound.SND_MEMORY | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        )
        # Bound the reference table: only a handful of cues is ever live.
        if len(_PLAYING) > 16:
            for stale in list(_PLAYING)[:-8]:
                _PLAYING.pop(stale, None)
    except Exception:  # pragma: no cover - device trouble must not crash the app
        log.exception("cannot play cue %s", cue)


def clear_cache() -> None:
    """Drop generated buffers (used by tests)."""
    _CACHE.clear()
