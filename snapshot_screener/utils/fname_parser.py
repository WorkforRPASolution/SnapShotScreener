"""Filename parser for snapshot image filenames.

Production format: ``{timestamp_ms}_[{x}][{y}].png``

Example: ``1774568805575_[1338][403].png`` → (x=1338, y=403, ts=1774568805575)
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

# {timestamp}_[x][y].png — production format
_TS_BRACKET_RE = re.compile(r"^(\d+)_\[(\d+)\]\[(\d+)\]\.png$")


class FnameParser:
    """Parse snapshot filenames into ``(x, y, timestamp_ms)`` tuples.

    Parameters
    ----------
    mode:
        ``"auto"`` (default) uses the production format.
        A custom regex string with named groups ``(?P<x>...)``,
        ``(?P<y>...)``, and ``(?P<ts>...)`` is also supported.
    """

    def __init__(self, mode: str = "auto") -> None:
        self._mode = mode
        self._custom_re: Optional[re.Pattern[str]] = None

        if mode not in ("auto",):
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
            The filename to parse (e.g. ``"1774568805575_[1338][403].png"``).

        Returns
        -------
        tuple or None
            ``(x, y, timestamp_ms)`` on success, ``None`` on failure.
        """
        if self._mode == "custom":
            return self._parse_custom(fname)

        m = _TS_BRACKET_RE.match(fname)
        if m is None:
            return None
        return int(m.group(2)), int(m.group(3)), int(m.group(1))

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
