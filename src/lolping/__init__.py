"""lolping -- a League of Legends style ping wheel for the Windows desktop.

The package is split into three layers:

* pure logic    -- ``geometry``, ``config``, ``hotkeys`` (no Qt)
* system glue   -- ``input_hook``, ``autostart``, ``single_instance``, ``sounds``
* presentation  -- ``overlay``, ``settings_dialog``, ``app``

It never reads or writes the League of Legends client. It only draws an overlay
and records what the user chose.
"""

from __future__ import annotations

__version__ = "0.3.0"
__all__ = ["__version__"]
