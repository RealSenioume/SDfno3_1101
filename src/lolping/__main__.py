"""Module entry point for ``python -m lolping``.

An absolute import is used on purpose: PyInstaller executes the frozen entry
script as a top-level module, where a relative import fails with "attempted
relative import with no known parent package".
"""

from __future__ import annotations

import sys

from lolping.app import main

if __name__ == "__main__":
    sys.exit(main())
