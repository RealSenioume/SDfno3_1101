#!/usr/bin/env python
"""Summarise the latency probe log written by ``python -m lolping --latency-probe``.

The probe appends one JSON object per line to
``%APPDATA%\\lolping-desktop\\latency.jsonl``::

    {"ts": "2026-10-24T12:00:00.123+08:00", "frame_ms": 12.4, "commit_ms": 840.2}

``frame_ms`` is the time from the mouse-down hook callback to the first painted
wheel frame, ``commit_ms`` the time from mouse-down to mouse-up.  See
docs/00-interfaces.md section 9 for the contract.

This tool prints, for both metrics, the sample count, min, median, p90, p95,
p99 and max, a ready-to-paste Markdown table for the report, and the verdict
for the acceptance criterion "p95 frame_ms <= 50 ms".

Robustness: malformed or truncated lines are skipped and counted, never fatal
(a probe that is killed mid-write leaves a partial last line).  ``frame_ms``
may legitimately be ``null`` in the log; only ``commit_ms`` is then counted for
that line.  Percentiles use the nearest-rank method, which is the conservative
choice for a small sample (with fewer than 20 samples p95 is the maximum).

Standard library only.

Exit codes: 0 = AC passed, 1 = AC failed, 2 = no usable data or I/O problem.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Iterable, Sequence, TextIO

METRICS: tuple[str, ...] = ("frame_ms", "commit_ms")
DEFAULT_P95_MAX_MS = 50.0


# --------------------------------------------------------------------------- io
def _harden_console() -> None:
    """Avoid UnicodeEncodeError if a path is not representable in the console."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (OSError, ValueError):
                pass


def default_latency_path() -> Path:
    """Return ``%APPDATA%\\lolping-desktop\\latency.jsonl`` (Windows) or a best guess.

    The folder name is owned by :mod:`lolping.config`; asking the package first
    means this tool cannot drift out of sync with the application again. The
    import is optional: the analyser still works as a standalone stdlib script
    when the package is not on ``PYTHONPATH``.
    """
    try:
        from lolping.config import latency_path as _app_latency_path

        return _app_latency_path()
    except Exception:  # pragma: no cover - standalone use without the package
        pass

    preferred = os.environ.get("APPDATA")
    if preferred:
        return Path(preferred) / "lolping-desktop" / "latency.jsonl"
    # Non-Windows or a stripped environment: mirror the usual location.
    return Path.home() / "AppData" / "Roaming" / "lolping-desktop" / "latency.jsonl"


def _coerce_number(value: object) -> float | None:
    """Return a finite, non-negative float, or None if the value is unusable."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        return None
    return number


def load_samples(
    stream: TextIO,
    source: str,
) -> tuple[dict[str, list[float]], int, list[str]]:
    """Parse a latency log.

    Returns ``(samples, skipped_count, notes)`` where ``samples`` maps each
    metric name to its list of values and ``notes`` holds up to five
    human-readable descriptions of the skipped lines.
    """
    samples: dict[str, list[float]] = {metric: [] for metric in METRICS}
    skipped = 0
    notes: list[str] = []

    for line_number, raw_line in enumerate(stream, start=1):
        line = raw_line.strip()
        if not line:
            continue  # blank line: harmless, not reported

        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            skipped += 1
            if len(notes) < 5:
                notes.append(f"line {line_number}: invalid JSON ({exc.msg})")
            continue

        if not isinstance(record, dict):
            skipped += 1
            if len(notes) < 5:
                notes.append(f"line {line_number}: expected a JSON object")
            continue

        accepted = 0
        for metric in METRICS:
            number = _coerce_number(record.get(metric))
            if number is not None:
                samples[metric].append(number)
                accepted += 1

        if accepted == 0:
            skipped += 1
            if len(notes) < 5:
                notes.append(
                    f"line {line_number}: no usable frame_ms/commit_ms value"
                )

    return samples, skipped, notes


# ------------------------------------------------------------------- statistics
def percentile(sorted_values: Sequence[float], quantile: float) -> float:
    """Return the nearest-rank percentile of an already sorted sequence.

    The result is the smallest value such that at least ``quantile`` of the
    samples are less than or equal to it.  This never interpolates and never
    invents a value between two samples, so with n < 20 the p95 equals the
    maximum -- deliberately conservative for an acceptance test.
    """
    if not sorted_values:
        raise ValueError("percentile() of an empty sequence")
    if not 0.0 < quantile <= 1.0:
        raise ValueError("quantile must be in (0, 1]")
    rank = max(1, math.ceil(quantile * len(sorted_values)))
    return sorted_values[rank - 1]


def summarise(values: Iterable[float]) -> dict[str, float | int]:
    """Compute n / min / median / p90 / p95 / p99 / max for one metric."""
    numbers = sorted(values)
    count = len(numbers)
    if count == 0:
        return {"n": 0}
    if count % 2:
        median = numbers[count // 2]
    else:
        median = (numbers[count // 2 - 1] + numbers[count // 2]) / 2.0
    return {
        "n": count,
        "min": numbers[0],
        "median": median,
        "p90": percentile(numbers, 0.90),
        "p95": percentile(numbers, 0.95),
        "p99": percentile(numbers, 0.99),
        "max": numbers[-1],
    }


# ---------------------------------------------------------------------- output
def _format_ms(value: float | int) -> str:
    return f"{float(value):.2f}"


def print_stats_line(metric: str, stats: dict[str, float | int]) -> None:
    if not stats.get("n"):
        print(f"  {metric:<10} no samples")
        return
    cells = "  ".join(
        f"{key}={_format_ms(stats[key])}"
        for key in ("min", "median", "p90", "p95", "p99", "max")
    )
    print(f"  {metric:<10} n={stats['n']}  {cells}")


def print_markdown_table(summaries: dict[str, dict[str, float | int]]) -> None:
    print("| Metric | n | min | median | p90 | p95 | p99 | max |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for metric in METRICS:
        stats = summaries[metric]
        if not stats.get("n"):
            print(f"| {metric} | 0 | - | - | - | - | - | - |")
            continue
        cells = " | ".join(
            _format_ms(stats[key])
            for key in ("min", "median", "p90", "p95", "p99", "max")
        )
        print(f"| {metric} (ms) | {stats['n']} | {cells} |")


def report(
    samples: dict[str, list[float]],
    skipped: int,
    notes: Sequence[str],
    source: str,
    threshold_ms: float,
) -> int:
    """Print the human, Markdown and AC sections; return the process exit code."""
    summaries = {metric: summarise(samples[metric]) for metric in METRICS}
    frame_stats = summaries["frame_ms"]
    commit_stats = summaries["commit_ms"]

    print("lolping latency report")
    print(f"  source : {source}")
    print(
        "  samples: "
        + ", ".join(f"{metric}={summaries[metric]['n']}" for metric in METRICS)
        + (f"  (skipped {skipped} malformed line(s))" if skipped else "  (no malformed lines)")
    )
    if notes:
        for note in notes:
            print(f"    skipped {note}")

    print()
    print(
        "  frame_ms = mouse-down -> first wheel frame; "
        "commit_ms = mouse-down -> mouse-up"
    )
    for metric in METRICS:
        print_stats_line(metric, summaries[metric])

    print()
    print("Markdown table (paste into the report):")
    print()
    print_markdown_table(summaries)

    print()
    print(f"Acceptance criterion: p95 frame_ms <= {threshold_ms:g} ms")
    if not frame_stats.get("n"):
        print("  measured p95 frame_ms = n/a  ->  FAIL (no frame_ms samples)")
        return 2

    measured_p95 = float(frame_stats["p95"])
    passed = measured_p95 <= threshold_ms
    verdict = "PASS" if passed else "FAIL"
    print(f"  measured p95 frame_ms = {_format_ms(measured_p95)} ms  ->  {verdict}")
    if not passed:
        print(
            "  hint: collect at least 20 samples on a quiet machine and check "
            "for a debugger, screen recorder or power-saving mode slowing the "
            "first paint; see docs/07-build-and-release.md."
        )
    if commit_stats.get("n"):
        print(
            f"  (context: commit_ms median = {_format_ms(commit_stats['median'])} ms, "
            f"p95 = {_format_ms(commit_stats['p95'])} ms)"
        )
    return 0 if passed else 1


# ------------------------------------------------------------------------ main
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="latency_report.py",
        # argparse interpolates '%' in help strings (but not in the parser
        # description), so only the --path help below needs doubled signs.
        description=(
            "Summarise %APPDATA%\\lolping-desktop\\latency.jsonl and check the "
            "'p95 frame_ms <= 50 ms' acceptance criterion."
        ),
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "latency.jsonl to analyse "
            "(default: %%APPDATA%%\\lolping-desktop\\latency.jsonl; '-' reads stdin)"
        ),
    )
    parser.add_argument(
        "--threshold-ms",
        type=float,
        default=DEFAULT_P95_MAX_MS,
        metavar="MS",
        help=f"p95 frame_ms limit for the AC verdict (default: {DEFAULT_P95_MAX_MS:g})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _harden_console()
    args = _build_parser().parse_args(argv)

    path: Path | None = args.path
    if path is not None and str(path) == "-":
        samples, skipped, notes = load_samples(sys.stdin, "<stdin>")
        return report(samples, skipped, notes, "<stdin>", args.threshold_ms)

    source_path = path if path is not None else default_latency_path()
    try:
        # utf-8-sig also accepts a BOM, in case the log was written by an
        # editor or a shell redirection rather than by the app itself.
        with source_path.open("r", encoding="utf-8-sig", errors="replace") as stream:
            samples, skipped, notes = load_samples(stream, str(source_path))
    except FileNotFoundError:
        print(f"error: latency log not found: {source_path}", file=sys.stderr)
        print(
            "hint: run the app with --latency-probe first, then ping a few "
            "times: python -m lolping --latency-probe",
            file=sys.stderr,
        )
        return 2
    except OSError as exc:
        print(f"error: cannot read {source_path}: {exc}", file=sys.stderr)
        return 2

    if not any(samples[metric] for metric in METRICS):
        print(f"error: no usable latency samples in {source_path}", file=sys.stderr)
        return 2

    return report(samples, skipped, notes, str(source_path), args.threshold_ms)


if __name__ == "__main__":
    sys.exit(main())
