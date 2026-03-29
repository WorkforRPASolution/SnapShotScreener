"""Phase 1 data collection: filename metadata from Cassandra.

Iterates over date partitions, queries filenames, parses each into
``SnapshotMeta`` records containing (x, y, timestamp_ms).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from snapshot_screener.models import SnapshotMeta
from snapshot_screener.utils.fname_parser import FnameParser
from snapshot_screener.utils.date_range import iter_partition_keys
from snapshot_screener.utils.progress import get_logger, log_progress

if TYPE_CHECKING:
    from snapshot_screener.config import ScreenerConfig
    from snapshot_screener.db.cassandra_client import CassandraClient

logger = get_logger(__name__)


def collect_metadata(
    client: "CassandraClient",
    eqpid: str,
    config: "ScreenerConfig",
) -> List[SnapshotMeta]:
    """Collect snapshot metadata (Phase 1) for a single equipment ID.

    For every day in the configured date range, queries Cassandra for
    filenames, parses each filename to extract click coordinates and
    timestamp, and returns a sorted list of :class:`SnapshotMeta`.

    Parameters
    ----------
    client:
        Connected Cassandra client.
    eqpid:
        Equipment identifier to query.
    config:
        Screener configuration (provides date range and fname pattern).

    Returns
    -------
    list[SnapshotMeta]
        Metadata records sorted by ``timestamp_ms`` ascending.
    """
    parser = FnameParser(config.fname_pattern)

    partition_keys = list(
        iter_partition_keys(eqpid, config.date_from, config.date_to)
    )
    total_days = len(partition_keys)

    results: List[SnapshotMeta] = []

    for day_idx, (_eqpid, year, month, day) in enumerate(partition_keys, start=1):
        date_str = f"{year:04d}-{month:02d}-{day:02d}"

        # Query filenames for this partition
        try:
            fnames = client.query_fnames(eqpid, year, month, day)
        except Exception as exc:
            logger.warning(
                "[Phase 1] Failed to query fnames for %s %s: %s",
                eqpid,
                date_str,
                exc,
            )
            continue

        # Parse each filename
        for fname in fnames:
            parsed = parser.parse(fname)
            if parsed is None:
                logger.warning(
                    "[Phase 1] Failed to parse fname '%s' for %s, skipping",
                    fname,
                    eqpid,
                )
                continue

            x, y, timestamp_ms = parsed

            # x or y >= 9999 means non-click snapshot (e.g. periodic capture)
            if x >= 9999 or y >= 9999:
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
                    partition_day=day,
                )
            )

        log_progress(
            logger,
            day_idx,
            total_days,
            f"[Phase 1] [{day_idx}/{total_days} days] {eqpid} {date_str}",
        )

    # Sort by timestamp
    results.sort(key=lambda m: m.timestamp_ms)

    logger.info(
        "[Phase 1] Collected %d snapshots for %s over %d days",
        len(results),
        eqpid,
        total_days,
    )

    return results
