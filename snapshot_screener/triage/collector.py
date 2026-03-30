"""Triage data collection from snapshotlist table.

Queries the ``snapshotlist`` table (monthly partitions) instead of the
main snapshot table.  Uses ``fname >= ?`` to skip tombstoned rows from
expired TTL entries.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, List, Set

from snapshot_screener.i18n import t
from snapshot_screener.models import SnapshotMeta
from snapshot_screener.utils.date_range import iter_monthly_partition_keys
from snapshot_screener.utils.fname_parser import FnameParser
from snapshot_screener.utils.progress import get_logger

if TYPE_CHECKING:
    from snapshot_screener.config import TriageConfig
    from snapshot_screener.db.cassandra_client import CassandraClient

logger = get_logger(__name__)


def _fname_min_for_date(d: date) -> str:
    """Return the minimum possible fname prefix for a given date.

    Since fnames are ``{timestamp_ms}_[x][y].png`` and sorted ASC,
    using this as ``fname >= ?`` skips all rows before *d*.
    """
    ts_ms = int(
        datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()
        * 1000
    )
    return str(ts_ms)


def collect_triage_metadata(
    client: "CassandraClient",
    eqpid: str,
    config: "TriageConfig",
) -> List[SnapshotMeta]:
    """Collect fname metadata from the snapshotlist table for triage.

    Returns a sorted list of :class:`SnapshotMeta` records for *eqpid*
    within the configured date range.
    """
    parser = FnameParser(config.fname_pattern)
    fname_min = _fname_min_for_date(config.date_from)

    # Compute upper bound timestamp to filter fnames within date range
    # date_to 23:59:59.999
    ts_max = int(
        datetime(
            config.date_to.year,
            config.date_to.month,
            config.date_to.day,
            23, 59, 59, 999_000,
            tzinfo=timezone.utc,
        ).timestamp()
        * 1000
    )

    results: List[SnapshotMeta] = []

    for year, month in iter_monthly_partition_keys(
        config.date_from, config.date_to
    ):
        try:
            fnames = client.query_snapshotlist(
                eqpid, year, month, fname_min
            )
        except Exception as exc:
            logger.warning(
                t("triage.log.fname_parse_fail", config.lang).format(
                    fname=f"{eqpid}/{year:04d}-{month:02d}: {exc}",
                )
            )
            continue

        for fname in fnames:
            parsed = parser.parse(fname)
            if parsed is None:
                continue

            x, y, timestamp_ms = parsed

            # Skip non-click snapshots
            if x >= 9999 or y >= 9999:
                continue

            # Skip fnames outside the requested date range
            if timestamp_ms > ts_max:
                continue

            results.append(
                SnapshotMeta(
                    eqpid=eqpid,
                    fname=fname,
                    timestamp_ms=timestamp_ms,
                    x=x,
                    y=y,
                    partition_year=year,
                    partition_month=month,
                )
            )

    results.sort(key=lambda m: m.timestamp_ms)
    return results


def count_data_days(metas: List[SnapshotMeta]) -> int:
    """Count the number of distinct calendar days with data."""
    if not metas:
        return 0
    days: Set[int] = set()
    for m in metas:
        # Convert timestamp_ms to day ordinal
        dt = datetime.fromtimestamp(m.timestamp_ms / 1000, tz=timezone.utc)
        days.add(dt.toordinal())
    return len(days)
