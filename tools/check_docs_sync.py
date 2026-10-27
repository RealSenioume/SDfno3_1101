"""Check that a document and its translation have the same shape.

Two language versions of the same document drift apart silently: a section is
added to one, a table is extended in the other, and nobody notices until a reader
does. Comparing the translated *text* is not possible without a translation
service, but comparing the *structure* is: the headings, code fences and table
rows must line up, because a translation preserves them.

Usage::

    python tools/check_docs_sync.py            # check every known pair
    python tools/check_docs_sync.py --root DIR # check a different checkout

Exit codes: 0 all pairs consistent, 1 at least one mismatch, 2 usage error.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["DocumentShape", "compare_shapes", "inspect", "PAIRS"]

#: (English file, translated file) relative to the repository root.
PAIRS: tuple[tuple[str, str], ...] = (
    ("README.md", "README.zh-CN.md"),
    ("PROCESS.md", "PROCESS.zh-CN.md"),
)

_HEADING = re.compile(r"^(#{1,6})\s+\S")
_FENCE = re.compile(r"^\s*```")
_TABLE_ROW = re.compile(r"^\s*\|")
_BULLET = re.compile(r"^\s*[-*]\s")


@dataclass
class DocumentShape:
    """Structural fingerprint of one Markdown file."""

    headings: list[int] = field(default_factory=list)
    fences: int = 0
    table_rows: int = 0
    lines: int = 0
    non_empty: int = 0
    bullets: int = 0

    def summary(self) -> str:
        levels = "".join(str(level) for level in self.headings)
        return (
            f"{self.lines} lines, headings [{levels}], {self.bullets} bullets, "
            f"{self.fences} fences, {self.table_rows} table rows"
        )


def inspect(path: Path) -> DocumentShape:
    """Read a Markdown file and return its structural fingerprint."""
    shape = DocumentShape()
    in_fence = False
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return shape

    for line in text.splitlines():
        shape.lines += 1
        if line.strip():
            shape.non_empty += 1
        if _FENCE.match(line):
            shape.fences += 1
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = _HEADING.match(line)
        if heading:
            shape.headings.append(len(heading.group(1)))
            continue
        if _TABLE_ROW.match(line):
            shape.table_rows += 1
            continue
        if _BULLET.match(line):
            shape.bullets += 1
    return shape


def compare_shapes(english: DocumentShape, translated: DocumentShape) -> list[str]:
    """Return human-readable problems; an empty list means the shapes match."""
    problems: list[str] = []
    if english.headings != translated.headings:
        problems.append(
            "heading levels differ: "
            f"en={english.headings} translated={translated.headings}"
        )
    if english.fences != translated.fences:
        problems.append(
            f"code fence count differs: en={english.fences} "
            f"translated={translated.fences}"
        )
    if english.table_rows != translated.table_rows:
        problems.append(
            f"table row count differs: en={english.table_rows} "
            f"translated={translated.table_rows}"
        )
    # Bullets are preserved one-for-one by a translation, so a mismatch means a
    # point was added to one language and forgotten in the other. This catches
    # the drift that the heading and table checks cannot see.
    if english.bullets != translated.bullets:
        problems.append(
            f"bullet count differs: en={english.bullets} "
            f"translated={translated.bullets}"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check document/translation parity.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (default: the folder containing tools/)",
    )
    args = parser.parse_args(argv)
    root: Path = args.root

    failures = 0
    for english_name, translated_name in PAIRS:
        english_path = root / english_name
        translated_path = root / translated_name
        if not english_path.exists():
            print(f"SKIP {english_name}: not present")
            continue
        if not translated_path.exists():
            print(f"MISSING {translated_name}: no translation of {english_name}")
            failures += 1
            continue

        english = inspect(english_path)
        translated = inspect(translated_path)
        problems = compare_shapes(english, translated)
        if problems:
            failures += 1
            print(f"FAIL {english_name} <-> {translated_name}")
            print(f"     en: {english.summary()}")
            print(f"     zh: {translated.summary()}")
            for problem in problems:
                print(f"     - {problem}")
        else:
            print(f"ok   {english_name} <-> {translated_name} ({english.summary()})")

    if failures:
        print(f"\n{failures} pair(s) out of sync - update the translation.")
        return 1
    print("\nall document pairs are structurally in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
