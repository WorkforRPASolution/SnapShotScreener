"""Tests for snapshot_screener.triage.collector."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from snapshot_screener.config import TriageConfig
from snapshot_screener.triage.collector import (
    _fname_min_for_date,
    collect_triage_metadata,
    count_data_days,
)
from snapshot_screener.models import SnapshotMeta
from snapshot_screener.utils.date_range import iter_monthly_partition_keys


def _make_triage_config(**overrides) -> TriageConfig:
    defaults = dict(
        csv_path="test.csv",
        date_from=date(2026, 3, 15),
        date_to=date(2026, 3, 29),
        db_host="localhost",
        db_keyspace="ars",
    )
    defaults.update(overrides)
    return TriageConfig(**defaults)


class TestFnameMinForDate:

    def test_returns_timestamp_string(self):
        result = _fname_min_for_date(date(2026, 3, 15))
        assert result.isdigit()
        assert int(result) > 0

    def test_earlier_date_gives_smaller_value(self):
        a = _fname_min_for_date(date(2026, 3, 1))
        b = _fname_min_for_date(date(2026, 3, 15))
        assert int(a) < int(b)


class TestIterMonthlyPartitionKeys:

    def test_single_month(self):
        result = list(iter_monthly_partition_keys(date(2026, 3, 15), date(2026, 3, 29)))
        assert result == [(2026, 3)]

    def test_cross_month(self):
        result = list(iter_monthly_partition_keys(date(2026, 2, 25), date(2026, 3, 10)))
        assert result == [(2026, 2), (2026, 3)]

    def test_cross_year(self):
        result = list(iter_monthly_partition_keys(date(2025, 12, 20), date(2026, 1, 5)))
        assert result == [(2025, 12), (2026, 1)]


class TestCollectTriageMetadata:

    def test_basic_collection(self):
        config = _make_triage_config()
        mock_client = MagicMock()
        mock_client.query_snapshotlist.return_value = [
            "1774036800000_[500][300].png",
            "1774036801000_[600][400].png",
        ]
        result = collect_triage_metadata(mock_client, "EQ-TEST", config)
        assert len(result) == 2
        assert result[0].timestamp_ms <= result[1].timestamp_ms

    def test_non_click_filtered(self):
        config = _make_triage_config()
        mock_client = MagicMock()
        mock_client.query_snapshotlist.return_value = [
            "1774036800000_[500][300].png",
            "1774036800000_[9999][1774036820219].png",
            "1774036800000_[100][9999].png",
        ]
        result = collect_triage_metadata(mock_client, "EQ-TEST", config)
        assert len(result) == 1
        assert result[0].x == 500

    def test_empty_result(self):
        config = _make_triage_config()
        mock_client = MagicMock()
        mock_client.query_snapshotlist.return_value = []
        result = collect_triage_metadata(mock_client, "EQ-TEST", config)
        assert result == []

    def test_tombstone_avoidance_query(self):
        """Verify fname_min is passed to query_snapshotlist."""
        config = _make_triage_config()
        mock_client = MagicMock()
        mock_client.query_snapshotlist.return_value = []
        collect_triage_metadata(mock_client, "EQ-TEST", config)
        call_args = mock_client.query_snapshotlist.call_args
        # Should pass fname_min as 4th argument
        assert len(call_args[0]) == 4
        fname_min = call_args[0][3]
        assert fname_min.isdigit()


class TestCountDataDays:

    def test_empty(self):
        assert count_data_days([]) == 0

    def test_single_day(self):
        metas = [
            SnapshotMeta(eqpid="EQ", fname="a.png", timestamp_ms=1774036800000, x=0, y=0),
            SnapshotMeta(eqpid="EQ", fname="b.png", timestamp_ms=1774036801000, x=0, y=0),
        ]
        assert count_data_days(metas) == 1

    def test_multiple_days(self):
        metas = [
            SnapshotMeta(eqpid="EQ", fname="a.png", timestamp_ms=1774036800000, x=0, y=0),
            # +24h
            SnapshotMeta(eqpid="EQ", fname="b.png", timestamp_ms=1774036800000 + 86400000, x=0, y=0),
        ]
        assert count_data_days(metas) == 2
