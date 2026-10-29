"""Tests for tools/check_docs_sync.py.

The tool guards the English/Chinese document pairs against silent drift; these
tests pin its structural fingerprinting and its exit codes.

Scratch folders are created inside the repository (``.testtmp/``) rather than in
the system temp directory, because the sandbox used for development refuses to
delete directories it created under TEMP.
"""

from __future__ import annotations

import contextlib
import io
import itertools
import os
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import check_docs_sync as sync  # noqa: E402

_SCRATCH_ROOT = ROOT / ".testtmp"
_CASE_IDS = itertools.count()

EN = """# Title

Intro paragraph.

## Features

- one
- two

| a | b |
| --- | --- |
| 1 | 2 |

```text
not a heading
# inside a fence
```
"""

ZH = """# 标题

介绍段落。

## 功能

- 一
- 二

| 甲 | 乙 |
| --- | --- |
| 1 | 2 |

```text
不是标题
# 在代码块内
```
"""


def _scratch() -> Path:
    path = _SCRATCH_ROOT / f"docs-sync-{os.getpid()}-{next(_CASE_IDS)}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class _ScratchCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = _scratch()

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


class TestInspect(_ScratchCase):
    def _write(self, name: str, content: str) -> Path:
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_counts_headings_fences_and_table_rows(self) -> None:
        shape = sync.inspect(self._write("a.md", EN))
        self.assertEqual(shape.headings, [1, 2])
        self.assertEqual(shape.fences, 2)
        # header + separator + one data row
        self.assertEqual(shape.table_rows, 3)

    def test_headings_inside_a_fence_are_ignored(self) -> None:
        shape = sync.inspect(self._write("a.md", EN))
        self.assertEqual(shape.headings.count(1), 1, "the fenced # must not count")

    def test_missing_file_is_an_empty_shape(self) -> None:
        shape = sync.inspect(self.root / "definitely-missing.md")
        self.assertEqual(shape.headings, [])
        self.assertEqual(shape.lines, 0)


class TestCompare(unittest.TestCase):
    def test_identical_shapes_have_no_problems(self) -> None:
        shape = sync.DocumentShape(headings=[1, 2], fences=2, table_rows=3)
        self.assertEqual(sync.compare_shapes(shape, shape), [])

    def test_heading_mismatch_is_reported(self) -> None:
        english = sync.DocumentShape(headings=[1, 2, 2], fences=0, table_rows=0)
        translated = sync.DocumentShape(headings=[1, 2], fences=0, table_rows=0)
        problems = sync.compare_shapes(english, translated)
        self.assertEqual(len(problems), 1)
        self.assertIn("heading", problems[0])

    def test_fence_and_table_mismatches_are_reported(self) -> None:
        english = sync.DocumentShape(headings=[1], fences=4, table_rows=6)
        translated = sync.DocumentShape(headings=[1], fences=2, table_rows=3)
        problems = sync.compare_shapes(english, translated)
        self.assertEqual(len(problems), 2)
        self.assertTrue(any("fence" in problem for problem in problems))
        self.assertTrue(any("table" in problem for problem in problems))


class TestCommandLine(_ScratchCase):
    def _tree(self, en: str, zh: str | None) -> Path:
        (self.root / "README.md").write_text(en, encoding="utf-8")
        if zh is not None:
            (self.root / "README.zh-CN.md").write_text(zh, encoding="utf-8")
        return self.root

    def test_matching_pair_exits_zero(self) -> None:
        root = self._tree(EN, ZH)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sync.main(["--root", str(root)]), 0)

    def test_mismatched_pair_exits_one(self) -> None:
        root = self._tree(EN, ZH.replace("## 功能", ""))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sync.main(["--root", str(root)]), 1)

    def test_missing_translation_exits_one(self) -> None:
        root = self._tree(EN, None)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sync.main(["--root", str(root)]), 1)

    def test_missing_english_file_is_skipped(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sync.main(["--root", str(self.root)]), 0)




class TestDocsMatchTheCode(unittest.TestCase):
    """The bilingual checker compares shape, not content; these catch drift."""

    def _read(self, name: str) -> str:
        return (ROOT / name).read_text(encoding="utf-8")

    def _version(self) -> str:
        text = (ROOT / "src" / "lolping" / "__init__.py").read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("__version__"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
        self.fail("no __version__ in the package")

    def test_readme_version_matches_the_package(self) -> None:
        version = self._version()
        self.assertIn(f"Version: **{version}**", self._read("README.md"))
        self.assertIn(f"版本：**{version}**", self._read("README.zh-CN.md"))

    def test_readme_lists_the_real_default_sectors(self) -> None:
        for name in (
            "On My Way",
            "All-In",
            "Assist Me",
            "Need Vision",
            "Enemy Missing",
            "Enemy Vision",
            "Danger",
            "Push",
        ):
            self.assertIn(name, self._read("README.md"))
            self.assertIn(name, self._read("README.zh-CN.md"))

    def test_readme_no_longer_offers_retreat_as_a_default(self) -> None:
        for name in ("README.md", "README.zh-CN.md"):
            self.assertNotIn("Retreat", self._read(name))

    def test_requirements_defaults_match_the_code(self) -> None:
        text = self._read("docs/02-requirements.md")
        for line in text.splitlines():
            if line.startswith("| `sectors`"):
                self.assertIn("Danger", line)
                self.assertNotIn("Retreat", line)
            elif line.startswith("| `sector_icons`"):
                self.assertIn("`danger`", line)
                self.assertNotIn("`retreat`", line)
            elif line.startswith("| `theme`"):
                self.assertIn("lol", line)


if __name__ == "__main__":
    unittest.main()
