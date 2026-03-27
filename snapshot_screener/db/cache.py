"""SQLite-backed pHash cache for SnapshotScreener.

Stores computed pHash values so that images do not need to be re-read from
Cassandra on subsequent runs.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

_EXPECTED_SCHEMA_VERSION = "1"

_CREATE_SQL = """\
CREATE TABLE IF NOT EXISTS phash_cache (
    eqpid     TEXT NOT NULL,
    fname     TEXT NOT NULL,
    phash     TEXT NOT NULL,
    image_w   INTEGER,
    image_h   INTEGER,
    cached_at TEXT NOT NULL,
    PRIMARY KEY (eqpid, fname)
);
CREATE INDEX IF NOT EXISTS idx_phash_cache_eqpid ON phash_cache(eqpid);
CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT OR IGNORE INTO _meta (key, value) VALUES ('schema_version', '1');
"""


@dataclass
class CacheEntry:
    """A single cached pHash record."""

    phash: str
    image_w: Optional[int]
    image_h: Optional[int]
    cached_at: str


class PhashCache:
    """SQLite-backed pHash cache.

    Parameters
    ----------
    cache_dir:
        Directory where ``phash_cache.db`` will be created/opened.
    """

    def __init__(self, cache_dir: str = ".") -> None:
        db_path = os.path.join(cache_dir, "phash_cache.db")
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_CREATE_SQL)
        self._conn.commit()
        self._check_schema_version()

    # ------------------------------------------------------------------
    # Schema version guard
    # ------------------------------------------------------------------

    def _check_schema_version(self) -> None:
        cur = self._conn.execute(
            "SELECT value FROM _meta WHERE key = ?", ("schema_version",)
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(
                "Cache schema version mismatch: expected '1', got None"
            )
        version = row[0]
        if version != _EXPECTED_SCHEMA_VERSION:
            raise ValueError(
                f"Cache schema version mismatch: expected '1', got '{version}'"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, eqpid: str, fname: str) -> Optional[CacheEntry]:
        """Look up a single cache entry.

        Returns ``None`` if no cached value exists.
        """
        cur = self._conn.execute(
            "SELECT phash, image_w, image_h, cached_at "
            "FROM phash_cache WHERE eqpid = ? AND fname = ?",
            (eqpid, fname),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return CacheEntry(
            phash=row[0],
            image_w=row[1],
            image_h=row[2],
            cached_at=row[3],
        )

    def put(
        self,
        eqpid: str,
        fname: str,
        phash: str,
        image_w: Optional[int] = None,
        image_h: Optional[int] = None,
    ) -> None:
        """Insert or replace a cache entry.

        ``cached_at`` is set automatically to the current UTC time in
        ISO 8601 format.
        """
        cached_at = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT OR REPLACE INTO phash_cache "
            "(eqpid, fname, phash, image_w, image_h, cached_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (eqpid, fname, phash, image_w, image_h, cached_at),
        )
        self._conn.commit()

    def put_bulk(
        self,
        entries: Sequence[Tuple[str, str, str, Optional[int], Optional[int]]],
    ) -> None:
        """Insert or replace multiple cache entries in a single transaction.

        Each entry is a tuple of ``(eqpid, fname, phash, image_w, image_h)``.
        """
        if not entries:
            return
        cached_at = datetime.now(timezone.utc).isoformat()
        self._conn.executemany(
            "INSERT OR REPLACE INTO phash_cache "
            "(eqpid, fname, phash, image_w, image_h, cached_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(*e, cached_at) for e in entries],
        )
        self._conn.commit()

    # SQLite variable limit (safe for all versions)
    _BATCH_SIZE = 900

    def get_bulk(
        self, eqpid: str, fnames: List[str]
    ) -> Dict[str, CacheEntry]:
        """Batch lookup for a single equipment ID.

        Returns a dict keyed by ``fname`` containing only the entries that
        were found in the cache (misses are simply omitted).

        Queries are batched to stay within SQLite's variable limit.
        """
        if not fnames:
            return {}

        results: Dict[str, CacheEntry] = {}

        for start in range(0, len(fnames), self._BATCH_SIZE):
            batch = fnames[start : start + self._BATCH_SIZE]
            placeholders = ",".join("?" for _ in batch)
            cur = self._conn.execute(
                f"SELECT fname, phash, image_w, image_h, cached_at "
                f"FROM phash_cache WHERE eqpid = ? AND fname IN ({placeholders})",
                [eqpid, *batch],
            )
            for row in cur.fetchall():
                results[row[0]] = CacheEntry(
                    phash=row[1],
                    image_w=row[2],
                    image_h=row[3],
                    cached_at=row[4],
                )

        return results

    def invalidate(self, eqpid: Optional[str] = None) -> int:
        """Delete cached entries.

        Parameters
        ----------
        eqpid:
            If provided, only delete entries for this equipment ID.
            If ``None``, delete **all** cached entries.

        Returns
        -------
        int
            Number of rows deleted.
        """
        if eqpid is not None:
            cur = self._conn.execute(
                "DELETE FROM phash_cache WHERE eqpid = ?", (eqpid,)
            )
        else:
            cur = self._conn.execute("DELETE FROM phash_cache")
        self._conn.commit()
        return cur.rowcount

    def close(self) -> None:
        """Close the underlying database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Context manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> "PhashCache":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.close()
