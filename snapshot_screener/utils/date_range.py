"""Date range iteration utilities for Cassandra partition keys."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterator, Tuple


def iter_partition_keys(
    eqpid: str,
    date_from: date,
    date_to: date,
) -> Iterator[Tuple[str, int, int, int]]:
    """Yield ``(eqpid, year, month, day)`` for each day in the range.

    The range is inclusive on both ends: ``[date_from, date_to]``.

    Parameters
    ----------
    eqpid:
        Equipment identifier.
    date_from:
        Start date (inclusive).
    date_to:
        End date (inclusive).

    Yields
    ------
    tuple
        ``(eqpid, year, month, day)`` for each day in the range.
    """
    current = date_from
    while current <= date_to:
        yield eqpid, current.year, current.month, current.day
        current += timedelta(days=1)
