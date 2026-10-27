"""Tests for the synthesised audio cues.

Playback itself is not exercised: a test suite must not make noise on the
developer's machine. The WAV renderer, which is the part that can be wrong, is
tested directly.
"""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lolping import sounds  # noqa: E402


def _samples(wav: bytes) -> list[int]:
    body = wav[44:]
    count = len(body) // 2
    return [value for (value,) in struct.iter_unpack("<h", body[: count * 2])]


class TestCatalogue(unittest.TestCase):
    def test_cue_names(self) -> None:
        self.assertEqual(set(sounds.CUE_NAMES()), {"open", "hover", "commit", "cancel"})

    def test_unknown_cue_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            sounds.render_wav("explosion")


class TestWavFormat(unittest.TestCase):
    def test_every_cue_is_a_valid_wav(self) -> None:
        for cue in sounds.CUE_NAMES():
            with self.subTest(cue=cue):
                data = sounds.render_wav(cue, volume=0.5, index=2)
                self.assertEqual(data[:4], b"RIFF")
                self.assertEqual(data[8:12], b"WAVE")
                self.assertEqual(data[12:16], b"fmt ")
                declared = struct.unpack("<I", data[4:8])[0]
                self.assertEqual(declared, len(data) - 8)
                self.assertGreater(len(data), 44 + 200)

    def test_cue_lengths_are_short(self) -> None:
        # 22050 Hz, 16 bit mono: keep every cue under 250 ms.
        for cue in sounds.CUE_NAMES():
            with self.subTest(cue=cue):
                data = sounds.render_wav(cue, 0.5, 0)
                milliseconds = (len(data) - 44) / 2 / 22_050 * 1000
                self.assertLess(milliseconds, 250)
                self.assertGreater(milliseconds, 10)

    def test_volume_scales_the_peak(self) -> None:
        quiet = max(abs(value) for value in _samples(sounds.render_wav("commit", 0.2, 0)))
        loud = max(abs(value) for value in _samples(sounds.render_wav("commit", 1.0, 0)))
        self.assertGreater(loud, quiet)
        self.assertLessEqual(loud, 30_000)

    def test_zero_volume_is_silence(self) -> None:
        data = sounds.render_wav("cancel", 0.0, 0)
        self.assertEqual(set(_samples(data)), {0})

    def test_slices_sound_different(self) -> None:
        first = sounds.render_wav("commit", 0.5, 0)
        fifth = sounds.render_wav("commit", 0.5, 4)
        self.assertNotEqual(first, fifth)

    def test_rendering_is_cached(self) -> None:
        first = sounds.render_wav("hover", 0.5, 0)
        second = sounds.render_wav("hover", 0.5, 0)
        self.assertIs(first, second)


class TestPlaybackSafety(unittest.TestCase):
    def test_play_is_a_no_op_without_winsound(self) -> None:
        original = sounds.winsound
        sounds.winsound = None
        try:
            sounds.play("commit", 0.5, 1)  # must not raise
        finally:
            sounds.winsound = original

    def test_play_never_raises_on_bad_cue(self) -> None:
        original = sounds.winsound
        sounds.winsound = None
        try:
            sounds.play("nope", 0.5)  # swallowed and logged, not raised
        finally:
            sounds.winsound = original


if __name__ == "__main__":
    unittest.main()
