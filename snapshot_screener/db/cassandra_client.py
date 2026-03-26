"""Safe, rate-limited Cassandra client for SnapshotScreener."""
from __future__ import annotations

import logging
import time
from typing import List, Optional, TYPE_CHECKING

from cassandra import (
    InvalidRequest,
    OperationTimedOut,
    ReadTimeout,
    Unauthorized,
    Unavailable,
)
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster
from cassandra.io.asyncorereactor import AsyncoreConnection
from cassandra.policies import (
    DCAwareRoundRobinPolicy,
    HostDistance,
    TokenAwarePolicy,
)
from cassandra.pool import PoolingOptions
from cassandra.query import ConsistencyLevel

from snapshot_screener.config import ScreenerConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardcoded CQL queries (SELECT only) — format templates filled at prepare
# ---------------------------------------------------------------------------
_Q_FNAMES = (
    "SELECT fname FROM {ks}.{tbl} "
    "WHERE eqpid=? AND year=? AND month=? AND day=?"
)
_Q_IMAGE = (
    "SELECT image FROM {ks}.{tbl} "
    "WHERE eqpid=? AND year=? AND month=? AND day=? AND fname=?"
)

# Transient errors worth retrying
_TRANSIENT_ERRORS = (OperationTimedOut, ReadTimeout, Unavailable)

_MAX_RETRIES = 3
_BACKOFF_BASE_S = 1  # 1s, 2s, 4s


class CassandraClient:
    """Rate-limited, retry-aware Cassandra client.

    Usage::

        with CassandraClient(config) as db:
            fnames = db.query_fnames("EQ-01", 2024, 1, 15)
            image  = db.query_image("EQ-01", 2024, 1, 15, fnames[0])
    """

    def __init__(self, config: ScreenerConfig) -> None:
        self._config = config

        # Pooling — keep connections minimal
        opts = PoolingOptions()
        opts.set_core_connections_per_host(HostDistance.LOCAL, 1)
        opts.set_max_connections_per_host(HostDistance.LOCAL, 1)
        opts.set_core_connections_per_host(HostDistance.REMOTE, 0)
        opts.set_max_connections_per_host(HostDistance.REMOTE, 0)

        # Auth (optional)
        auth_provider = None
        if config.db_username and config.db_password:
            auth_provider = PlainTextAuthProvider(
                username=config.db_username,
                password=config.db_password,
            )

        # Cluster (not connected yet — deferred to __enter__)
        self._cluster = Cluster(
            contact_points=[config.db_host],
            port=config.db_port,
            load_balancing_policy=TokenAwarePolicy(DCAwareRoundRobinPolicy()),
            pooling_options=opts,
            auth_provider=auth_provider,
            connect_timeout=10,
            connection_class=AsyncoreConnection,
        )

        self._session = None
        self._prep_fnames = None
        self._prep_image = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "CassandraClient":
        self._session = self._cluster.connect()
        self._session.default_timeout = 15.0

        # Prepare statements (keyspace/table filled once here)
        ks = self._config.db_keyspace
        tbl = self._config.db_table

        self._prep_fnames = self._session.prepare(
            _Q_FNAMES.format(ks=ks, tbl=tbl)
        )
        self._prep_fnames.consistency_level = ConsistencyLevel.LOCAL_ONE

        self._prep_image = self._session.prepare(
            _Q_IMAGE.format(ks=ks, tbl=tbl)
        )
        self._prep_image.consistency_level = ConsistencyLevel.LOCAL_ONE

        # Health check
        try:
            self._session.execute("SELECT release_version FROM system.local")
        except Exception as exc:
            self._cluster.shutdown()
            raise ConnectionError(
                f"Cassandra health-check failed ({self._config.db_host}:"
                f"{self._config.db_port}): {exc}"
            ) from exc

        logger.info(
            "Connected to Cassandra at %s:%s",
            self._config.db_host,
            self._config.db_port,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        if self._cluster:
            self._cluster.shutdown()
            logger.info("Cassandra connection closed.")

    # ------------------------------------------------------------------
    # Public query methods
    # ------------------------------------------------------------------

    def query_fnames(
        self, eqpid: str, year: int, month: int, day: int
    ) -> List[str]:
        """Return filenames for the given equipment + date partition."""
        rows = self._execute_with_retry(
            self._prep_fnames, (eqpid, year, month, day)
        )
        result = [row.fname for row in rows]
        time.sleep(self._config.fname_delay_ms / 1000)
        return result

    def query_image(
        self,
        eqpid: str,
        year: int,
        month: int,
        day: int,
        fname: str,
    ) -> Optional[str]:
        """Return Base64-encoded image text, or *None* if not found."""
        rows = self._execute_with_retry(
            self._prep_image, (eqpid, year, month, day, fname)
        )
        result = rows.one() if hasattr(rows, "one") else next(iter(rows), None)
        time.sleep(self._config.read_delay_ms / 1000)
        if result is None:
            return None
        return result.image

    # ------------------------------------------------------------------
    # Retry logic (private)
    # ------------------------------------------------------------------

    def _execute_with_retry(self, prepared, params):  # type: ignore[no-untyped-def]
        """Execute a prepared statement with exponential-backoff retry.

        Only transient errors (``OperationTimedOut``, ``ReadTimeout``,
        ``Unavailable``) are retried.  Non-transient errors such as
        ``InvalidRequest`` or ``Unauthorized`` propagate immediately.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES):
            try:
                return self._session.execute(prepared, params)
            except _TRANSIENT_ERRORS as exc:
                last_exc = exc
                backoff = _BACKOFF_BASE_S * (2 ** attempt)
                logger.warning(
                    "Transient Cassandra error (attempt %d/%d), "
                    "retrying in %ds: %s",
                    attempt + 1,
                    _MAX_RETRIES,
                    backoff,
                    exc,
                )
                time.sleep(backoff)
        # All retries exhausted — re-raise last transient error
        raise last_exc  # type: ignore[misc]
