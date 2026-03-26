"""Filename parser for snapshot image filenames.

Supports multiple naming conventions:

- ``xy_ts``: ``{x}_{y}_{timestamp_ms}.png``
- ``ts_xy``: ``{timestamp_ms}_{x}_{y}.png``
- ``auto``: auto-detect based on first field digit count
- ``custom``: user-provided regex with named groups ``x``, ``y``, ``ts``
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

# Pre-compiled pattern: three groups of digits separated by underscores,
# ending in .png
_THREE_FIELD_RE = re.compile(r"^(\d+)_(\d+)_(\d+)\.png$")


class FnameParser:
    """Parse snapshot filenames into ``(x, y, timestamp_ms)`` tuples.

    Parameters
    ----------
    mode:
        One of ``"auto"``, ``"xy_ts"``, ``"ts_xy"``, or a custom regex
        string containing named groups ``(?P<x>...)``, ``(?P<y>...)``,
        and ``(?P<ts>...)``.
    """

    def __init__(self, mode: str = "auto") -> None:
        self._mode = mode
        self._custom_re: Optional[re.Pattern[str]] = None

        if mode not in ("auto", "xy_ts", "ts_xy"):
            # Treat as custom regex
            self._mode = "custom"
            self._custom_re = re.compile(mode)

    @property
    def mode(self) -> str:
        """Return the active parsing mode."""
        return self._mode

    def parse(self, fname: str) -> Optional[Tuple[int, int, int]]:
        """Parse a filename and return ``(x, y, timestamp_ms)`` or *None*.

        Parameters
        ----------
        fname:
            The filename to parse (e.g. ``"123_456_1700000000000.png"``).

        Returns
        -------
        tuple or None
            ``(x, y, timestamp_ms)`` on success, ``None`` on failure.
        """
        if self._mode == "custom":
            return self._parse_custom(fname)

        m = _THREE_FIELD_RE.match(fname)
        if m is None:
            return None

        a, b, c = m.group(1), m.group(2), m.group(3)

        if self._mode == "xy_ts":
            return int(a), int(b), int(c)

        if self._mode == "ts_xy":
            return int(b), int(c), int(a)

        # Auto-detect: first field has 13 digits -> ts_xy, else xy_ts
        if len(a) >= 13:
            # timestamp first
            return int(b), int(c), int(a)
        else:
            # x, y first
            return int(a), int(b), int(c)

    def _parse_custom(self, fname: str) -> Optional[Tuple[int, int, int]]:
        """Parse using a custom regex with named groups."""
        assert self._custom_re is not None
        m = self._custom_re.match(fname)
        if m is None:
            return None
        try:
            x = int(m.group("x"))
            y = int(m.group("y"))
            ts = int(m.group("ts"))
        except (IndexError, ValueError):
            return None
        return x, y, ts
