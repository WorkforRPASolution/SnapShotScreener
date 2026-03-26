"""Tests for snapshot_screener.db.cassandra_client.

Since we cannot connect to a real Cassandra instance in unit tests (and the
cassandra-driver may not be installable on all Python versions), every
external dependency is mocked.
"""
from __future__ import annotations

import importlib
import sys
import types
from datetime import date
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: ensure a mock `cassandra` package is available so we can import
# the client module even when cassandra-driver is not installed.
# ---------------------------------------------------------------------------

_CASSANDRA_AVAILABLE = "cassandra" in sys.modules or importlib.util.find_spec("cassandra") is not None

if not _CASSANDRA_AVAILABLE:
    # Build a minimal stub package tree so that the real module's imports
    # resolve without error.
    cassandra_mod = types.ModuleType("cassandra")
    cassandra_mod.InvalidRequest = type("InvalidRequest", (Exception,), {})
    cassandra_mod.OperationTimedOut = type("OperationTimedOut", (Exception,), {})
    cassandra_mod.ReadTimeout = type("ReadTimeout", (Exception,), {})
    cassandra_mod.Unauthorized = type("Unauthorized", (Exception,), {})
    cassandra_mod.Unavailable = type("Unavailable", (Exception,), {})

    cassandra_auth = types.ModuleType("cassandra.auth")
    cassandra_auth.PlainTextAuthProvider = MagicMock(name="PlainTextAuthProvider")

    cassandra_cluster = types.ModuleType("cassandra.cluster")
    cassandra_cluster.Cluster = MagicMock(name="Cluster")

    cassandra_io = types.ModuleType("cassandra.io")
    cassandra_io_asyncore = types.ModuleType("cassandra.io.asyncorereactor")
    cassandra_io_asyncore.AsyncoreConnection = MagicMock(name="AsyncoreConnection")

    cassandra_policies = types.ModuleType("cassandra.policies")
    cassandra_policies.DCAwareRoundRobinPolicy = MagicMock(name="DCAwareRoundRobinPolicy")
    cassandra_policies.HostDistance = MagicMock(name="HostDistance")
    cassandra_policies.HostDistance.LOCAL = 0
    cassandra_policies.HostDistance.REMOTE = 1
    cassandra_policies.TokenAwarePolicy = MagicMock(name="TokenAwarePolicy")

    cassandra_pool = types.ModuleType("cassandra.pool")
    cassandra_pool.PoolingOptions = MagicMock(name="PoolingOptions")

    cassandra_query = types.ModuleType("cassandra.query")
    cassandra_query.ConsistencyLevel = MagicMock(name="ConsistencyLevel")
    cassandra_query.ConsistencyLevel.LOCAL_ONE = "LOCAL_ONE"

    sys.modules["cassandra"] = cassandra_mod
    sys.modules["cassandra.auth"] = cassandra_auth
    sys.modules["cassandra.cluster"] = cassandra_cluster
    sys.modules["cassandra.io"] = cassandra_io
    sys.modules["cassandra.io.asyncorereactor"] = cassandra_io_asyncore
    sys.modules["cassandra.policies"] = cassandra_policies
    sys.modules["cassandra.pool"] = cassandra_pool
    sys.modules["cassandra.query"] = cassandra_query


# NOW safe to import
from snapshot_screener.config import ScreenerConfig
from snapshot_screener.db.cassandra_client import (
    CassandraClient,
    _Q_FNAMES,
    _Q_IMAGE,
    _MAX_RETRIES,
)

# Re-import exception types from the (possibly stubbed) cassandra package
import cassandra as _cass

OperationTimedOut = _cass.OperationTimedOut
InvalidRequest = _cass.InvalidRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides) -> ScreenerConfig:
    defaults = dict(
        eqpids=["EQ-TEST"],
        date_from=date(2024, 1, 1),
        date_to=date(2024, 1, 31),
        db_host="127.0.0.1",
        db_port=9042,
        db_keyspace="test_ks",
        db_table="test_tbl",
        fname_delay_ms=100,
        read_delay_ms=200,
    )
    defaults.update(overrides)
    return ScreenerConfig(**defaults)


def _make_client_with_mock_session(config=None):
    """Create a CassandraClient and wire up mock internals so we can test
    query methods without a real Cassandra cluster."""
    config = config or _make_config()
    client = CassandraClient(config)

    # Simulate __enter__ wiring without calling the real Cluster
    mock_session = MagicMock()
    client._session = mock_session
    client._prep_fnames = MagicMock(name="prep_fnames")
    client._prep_image = MagicMock(name="prep_image")
    return client, mock_session


# ---------------------------------------------------------------------------
# 1. CQL string: fname query must not contain * or the word 'image'
# ---------------------------------------------------------------------------

class TestCqlStrings:
    def test_fnames_query_no_star(self):
        assert "*" not in _Q_FNAMES

    def test_fnames_query_no_image_column(self):
        # The fname query should NOT select the image column
        assert "image" not in _Q_FNAMES.lower()

    def test_image_query_selects_image(self):
        # Conversely, the image query DOES reference image
        assert "image" in _Q_IMAGE.lower()

    # -----------------------------------------------------------------------
    # 2. Both queries reference all 4 partition key bind markers
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("query", [_Q_FNAMES, _Q_IMAGE])
    def test_partition_key_components_present(self, query):
        for component in ("eqpid=?", "year=?", "month=?", "day=?"):
            assert component in query, f"{component!r} missing from: {query}"


# ---------------------------------------------------------------------------
# 3. Rate-limiting delays
# ---------------------------------------------------------------------------

class TestRateLimiting:
    @patch("snapshot_screener.db.cassandra_client.time.sleep")
    def test_fname_query_sleeps_after_execution(self, mock_sleep):
        config = _make_config(fname_delay_ms=150)
        client, mock_session = _make_client_with_mock_session(config)
        mock_session.execute.return_value = []

        client.query_fnames("EQ-01", 2024, 1, 15)

        mock_sleep.assert_called_once_with(150 / 1000)

    @patch("snapshot_screener.db.cassandra_client.time.sleep")
    def test_image_query_sleeps_after_execution(self, mock_sleep):
        config = _make_config(read_delay_ms=250)
        client, mock_session = _make_client_with_mock_session(config)
        # Return an empty result set
        mock_result = MagicMock()
        mock_result.one.return_value = None
        mock_session.execute.return_value = mock_result

        client.query_image("EQ-01", 2024, 1, 15, "some_file.png")

        mock_sleep.assert_called_once_with(250 / 1000)


# ---------------------------------------------------------------------------
# 4. Retry on transient error
# ---------------------------------------------------------------------------

class TestRetry:
    @patch("snapshot_screener.db.cassandra_client.time.sleep")
    def test_retry_on_transient_then_succeed(self, mock_sleep):
        client, mock_session = _make_client_with_mock_session()

        # First call raises transient error, second succeeds
        mock_session.execute.side_effect = [
            OperationTimedOut("timed out"),
            MagicMock(name="result_set"),  # success on 2nd attempt
        ]

        result = client._execute_with_retry(client._prep_fnames, ("EQ", 2024, 1, 1))

        assert mock_session.execute.call_count == 2
        # Backoff sleep should have been called with 1s (2^0)
        mock_sleep.assert_any_call(1)
        assert result is not None

    @patch("snapshot_screener.db.cassandra_client.time.sleep")
    def test_retry_exhausted_raises(self, mock_sleep):
        client, mock_session = _make_client_with_mock_session()

        mock_session.execute.side_effect = OperationTimedOut("always fails")

        with pytest.raises(OperationTimedOut):
            client._execute_with_retry(client._prep_fnames, ("EQ", 2024, 1, 1))

        assert mock_session.execute.call_count == _MAX_RETRIES
        # Backoff sleeps: 1s, 2s, 4s
        assert mock_sleep.call_args_list == [call(1), call(2), call(4)]

    # -----------------------------------------------------------------------
    # 5. Immediate failure on non-transient error
    # -----------------------------------------------------------------------

    @patch("snapshot_screener.db.cassandra_client.time.sleep")
    def test_no_retry_on_invalid_request(self, mock_sleep):
        client, mock_session = _make_client_with_mock_session()

        mock_session.execute.side_effect = InvalidRequest("bad query")

        with pytest.raises(InvalidRequest):
            client._execute_with_retry(client._prep_fnames, ("EQ", 2024, 1, 1))

        # Should fail immediately — only 1 call, no backoff sleep
        assert mock_session.execute.call_count == 1
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# 6. Context manager calls shutdown
# ---------------------------------------------------------------------------

class TestContextManager:
    def test_exit_calls_shutdown(self):
        config = _make_config()
        client = CassandraClient(config)
        # Replace internal cluster with a mock
        mock_cluster = MagicMock()
        client._cluster = mock_cluster

        client.__exit__(None, None, None)

        mock_cluster.shutdown.assert_called_once()

    def test_enter_calls_connect_and_health_check(self):
        config = _make_config()
        client = CassandraClient(config)

        mock_cluster = MagicMock()
        mock_session = MagicMock()
        mock_cluster.connect.return_value = mock_session
        client._cluster = mock_cluster

        result = client.__enter__()

        mock_cluster.connect.assert_called_once()
        # Health check query must have been issued
        mock_session.execute.assert_called_once_with(
            "SELECT release_version FROM system.local"
        )
        assert result is client

    def test_enter_raises_connection_error_on_health_failure(self):
        config = _make_config()
        client = CassandraClient(config)

        mock_cluster = MagicMock()
        mock_session = MagicMock()
        mock_session.execute.side_effect = Exception("refused")
        mock_cluster.connect.return_value = mock_session
        client._cluster = mock_cluster

        with pytest.raises(ConnectionError, match="health-check failed"):
            client.__enter__()

        # Cluster should be shut down on failure
        mock_cluster.shutdown.assert_called_once()
