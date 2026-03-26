"""Tests for the CLI + pipeline integration layer."""
from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from snapshot_screener.cli import SecurityWarning, build_config, main, parse_args
from snapshot_screener.config import ScreenerConfig
from snapshot_screener.models import (
    AnalysisResult,
    FrameFeature,
    ScreeningResult,
    SnapshotMeta,
)
from snapshot_screener.pipeline import run_pipeline, run_single_equipment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(
    eqpids: Optional[List[str]] = None,
    output_dir: str = ".",
    cache_dir: str = ".",
    **overrides,
) -> ScreenerConfig:
    """Create a minimal ScreenerConfig for testing."""
    defaults = dict(
        eqpids=eqpids or ["EQ-TEST"],
        date_from=date(2024, 1, 1),
        date_to=date(2024, 1, 7),
        db_host="127.0.0.1",
        db_keyspace="test_ks",
        db_table="test_tbl",
        db_port=9042,
        read_delay_ms=1,
        fname_delay_ms=1,
        max_connections=1,
        session_gap_ms=900_000,
        phash_similar_threshold=4,
        phash_transition_threshold=8,
        delta_spike_ms=30_000,
        dbscan_eps=0.03,
        dbscan_min_samples=2,
        screen_width=1920,
        screen_height=1080,
        selector="simple",
        sensitivity_sweep=False,
        fname_pattern="auto",
        cache_dir=cache_dir,
        output_dir=output_dir,
        invalidate_cache=False,
        verbose=False,
    )
    defaults.update(overrides)
    return ScreenerConfig(**defaults)


def _make_metas(eqpid: str = "EQ-TEST", n: int = 20) -> List[SnapshotMeta]:
    """Generate n SnapshotMeta records."""
    import random
    rng = random.Random(42)
    base_ts = 1_700_000_000_000
    metas = []
    ts = base_ts
    for i in range(n):
        x = rng.randint(100, 1800)
        y = rng.randint(100, 900)
        fname = f"{x}_{y}_{ts}.png"
        metas.append(
            SnapshotMeta(eqpid=eqpid, fname=fname, timestamp_ms=ts, x=x, y=y)
        )
        ts += 5000
    return metas


def _make_features_from_metas(metas: List[SnapshotMeta]) -> List[FrameFeature]:
    """Convert metas to FrameFeature list with synthetic pHash values."""
    import random
    rng = random.Random(123)
    features = []
    for meta in metas:
        phash = "".join(format(rng.randint(0, 15), "x") for _ in range(16))
        features.append(
            FrameFeature(
                eqpid=meta.eqpid,
                fname=meta.fname,
                timestamp_ms=meta.timestamp_ms,
                x=meta.x,
                y=meta.y,
                x_norm=meta.x / 1920,
                y_norm=meta.y / 1080,
                phash=phash,
                _phase_completed=2,
            )
        )
    return features


def _run_analysis_on_features(features: List[FrameFeature], eqpid: str = "EQ-TEST") -> None:
    """Run the full analysis pipeline phases 1-5 on features in-place."""
    from snapshot_screener.analysis import (
        assign_screen_groups,
        cluster_clicks,
        compute_screening,
        detect_transitions,
        select_representatives,
        separate_sessions,
    )
    separate_sessions(features, 900_000, eqpid)
    assign_screen_groups(features, 4)
    cluster_clicks(features, 0.03, 2, 1920, 1080)
    detect_transitions(features, 8, 30_000, 4)
    select_representatives(features, "simple")


def _make_analysis_result(
    eqpid: str = "EQ-TEST",
    features: Optional[List[FrameFeature]] = None,
) -> AnalysisResult:
    """Create a valid AnalysisResult for testing."""
    if features is None:
        metas = _make_metas(eqpid, 20)
        features = _make_features_from_metas(metas)
        _run_analysis_on_features(features, eqpid)

    from snapshot_screener.analysis import compute_screening
    screening = compute_screening(features)

    representative_features = [f for f in features if f.is_representative]
    sessions = set(f.session_id for f in features)
    screen_groups = set(f.screen_group_id for f in features if f.screen_group_id)

    return AnalysisResult(
        eqpid=eqpid,
        config_summary={"phash_similar_threshold": 4},
        all_features=features,
        representative_features=representative_features,
        screening=screening,
        sensitivity=None,
        total_clicks=len(features),
        analysis_days=7,
        session_count=len(sessions),
        screen_group_count=len(screen_groups),
        representative_count=len(representative_features),
        reduction_rate=1 - len(representative_features) / len(features) if features else 0,
    )


# ---------------------------------------------------------------------------
# CLI parse_args tests
# ---------------------------------------------------------------------------


class TestParseArgs:
    """Tests for parse_args()."""

    def test_minimal_args(self):
        args = parse_args([
            "--eqpid", "EQ-01",
            "--from", "2024-01-01",
            "--to", "2024-01-31",
            "--db-host", "10.0.0.1",
            "--db-keyspace", "my_ks",
            "--db-table", "my_tbl",
        ])
        assert args.eqpid == "EQ-01"
        assert args.eqpid_list is None
        assert args.date_from == date(2024, 1, 1)
        assert args.date_to == date(2024, 1, 31)
        assert args.db_host == "10.0.0.1"
        assert args.db_keyspace == "my_ks"
        assert args.db_table == "my_tbl"

    def test_defaults(self):
        args = parse_args([
            "--eqpid", "EQ-01",
            "--from", "2024-01-01",
            "--to", "2024-01-31",
            "--db-host", "10.0.0.1",
            "--db-keyspace", "ks",
            "--db-table", "tbl",
        ])
        assert args.db_port == 9042
        assert args.read_delay_ms == 200
        assert args.fname_delay_ms == 100
        assert args.max_connections == 2
        assert args.session_gap_ms == 900_000
        assert args.phash_similar_threshold == 4
        assert args.phash_transition_threshold == 8
        assert args.delta_spike_ms == 30_000
        assert args.dbscan_eps == 0.03
        assert args.dbscan_min_samples == 2
        assert args.screen_width == 1920
        assert args.screen_height == 1080
        assert args.selector == "simple"
        assert args.sensitivity_sweep is False
        assert args.fname_pattern == "auto"
        assert args.cache_dir == "."
        assert args.output_dir == "."
        assert args.invalidate_cache is False
        assert args.verbose is False

    def test_eqpid_list_flag(self, tmp_path):
        eqpid_file = tmp_path / "eqpids.txt"
        eqpid_file.write_text("EQ-01\nEQ-02\nEQ-03\n")
        args = parse_args([
            "--eqpid-list", str(eqpid_file),
            "--from", "2024-01-01",
            "--to", "2024-01-31",
            "--db-host", "10.0.0.1",
            "--db-keyspace", "ks",
            "--db-table", "tbl",
        ])
        assert args.eqpid is None
        assert args.eqpid_list == str(eqpid_file)

    def test_mutually_exclusive_eqpid(self, tmp_path):
        eqpid_file = tmp_path / "eqpids.txt"
        eqpid_file.write_text("EQ-01\n")
        with pytest.raises(SystemExit):
            parse_args([
                "--eqpid", "EQ-01",
                "--eqpid-list", str(eqpid_file),
                "--from", "2024-01-01",
                "--to", "2024-01-31",
                "--db-host", "10.0.0.1",
                "--db-keyspace", "ks",
                "--db-table", "tbl",
            ])

    def test_missing_required(self):
        with pytest.raises(SystemExit):
            parse_args(["--eqpid", "EQ-01"])

    def test_invalid_date_format(self):
        with pytest.raises(SystemExit):
            parse_args([
                "--eqpid", "EQ-01",
                "--from", "01-01-2024",
                "--to", "2024-01-31",
                "--db-host", "10.0.0.1",
                "--db-keyspace", "ks",
                "--db-table", "tbl",
            ])

    def test_invalid_selector_choice(self):
        with pytest.raises(SystemExit):
            parse_args([
                "--eqpid", "EQ-01",
                "--from", "2024-01-01",
                "--to", "2024-01-31",
                "--db-host", "10.0.0.1",
                "--db-keyspace", "ks",
                "--db-table", "tbl",
                "--selector", "invalid",
            ])

    def test_all_optional_args(self):
        args = parse_args([
            "--eqpid", "EQ-01",
            "--from", "2024-01-01",
            "--to", "2024-01-31",
            "--db-host", "10.0.0.1",
            "--db-keyspace", "ks",
            "--db-table", "tbl",
            "--db-port", "9999",
            "--db-username", "user",
            "--db-password", "pass",
            "--read-delay-ms", "500",
            "--fname-delay-ms", "200",
            "--max-connections", "4",
            "--session-gap-ms", "600000",
            "--phash-similar-threshold", "5",
            "--phash-transition-threshold", "10",
            "--delta-spike-ms", "50000",
            "--dbscan-eps", "0.05",
            "--dbscan-min-samples", "3",
            "--screen-width", "2560",
            "--screen-height", "1440",
            "--selector", "scored",
            "--sensitivity-sweep",
            "--fname-pattern", "xy_ts",
            "--cache-dir", "/tmp/cache",
            "--output-dir", "/tmp/output",
            "--invalidate-cache",
            "--verbose",
        ])
        assert args.db_port == 9999
        assert args.db_username == "user"
        assert args.db_password == "pass"
        assert args.read_delay_ms == 500
        assert args.fname_delay_ms == 200
        assert args.max_connections == 4
        assert args.session_gap_ms == 600_000
        assert args.phash_similar_threshold == 5
        assert args.phash_transition_threshold == 10
        assert args.delta_spike_ms == 50_000
        assert args.dbscan_eps == 0.05
        assert args.dbscan_min_samples == 3
        assert args.screen_width == 2560
        assert args.screen_height == 1440
        assert args.selector == "scored"
        assert args.sensitivity_sweep is True
        assert args.fname_pattern == "xy_ts"
        assert args.cache_dir == "/tmp/cache"
        assert args.output_dir == "/tmp/output"
        assert args.invalidate_cache is True
        assert args.verbose is True


# ---------------------------------------------------------------------------
# CLI build_config tests
# ---------------------------------------------------------------------------


class TestBuildConfig:
    """Tests for build_config()."""

    def test_single_eqpid(self):
        args = parse_args([
            "--eqpid", "EQ-01",
            "--from", "2024-01-01",
            "--to", "2024-01-31",
            "--db-host", "10.0.0.1",
            "--db-keyspace", "ks",
            "--db-table", "tbl",
        ])
        config = build_config(args)
        assert isinstance(config, ScreenerConfig)
        assert config.eqpids == ["EQ-01"]
        assert config.date_from == date(2024, 1, 1)
        assert config.date_to == date(2024, 1, 31)

    def test_eqpid_list_file(self, tmp_path):
        eqpid_file = tmp_path / "eqpids.txt"
        eqpid_file.write_text("EQ-01\nEQ-02\nEQ-03\n")
        args = parse_args([
            "--eqpid-list", str(eqpid_file),
            "--from", "2024-01-01",
            "--to", "2024-01-31",
            "--db-host", "10.0.0.1",
            "--db-keyspace", "ks",
            "--db-table", "tbl",
        ])
        config = build_config(args)
        assert config.eqpids == ["EQ-01", "EQ-02", "EQ-03"]

    def test_password_from_env(self, monkeypatch):
        monkeypatch.setenv("SS_DB_PASSWORD", "env_secret")
        args = parse_args([
            "--eqpid", "EQ-01",
            "--from", "2024-01-01",
            "--to", "2024-01-31",
            "--db-host", "10.0.0.1",
            "--db-keyspace", "ks",
            "--db-table", "tbl",
        ])
        config = build_config(args)
        assert config.db_password == "env_secret"

    def test_password_cli_warns(self):
        args = parse_args([
            "--eqpid", "EQ-01",
            "--from", "2024-01-01",
            "--to", "2024-01-31",
            "--db-host", "10.0.0.1",
            "--db-keyspace", "ks",
            "--db-table", "tbl",
            "--db-password", "cli_secret",
        ])
        with pytest.warns(SecurityWarning):
            config = build_config(args)
        assert config.db_password == "cli_secret"

    def test_frozen_config(self):
        args = parse_args([
            "--eqpid", "EQ-01",
            "--from", "2024-01-01",
            "--to", "2024-01-31",
            "--db-host", "10.0.0.1",
            "--db-keyspace", "ks",
            "--db-table", "tbl",
        ])
        config = build_config(args)
        with pytest.raises(AttributeError):
            config.eqpids = ["changed"]  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------


class TestRunSingleEquipment:
    """Tests for run_single_equipment()."""

    def test_full_pipeline_single_equipment(self, tmp_path):
        """Test full pipeline with single equipment (mock all Cassandra calls)."""
        config = _make_config(
            eqpids=["EQ-TEST"],
            output_dir=str(tmp_path),
            cache_dir=str(tmp_path),
        )
        metas = _make_metas("EQ-TEST", 20)
        features = _make_features_from_metas(metas)

        mock_client = MagicMock()
        # query_fnames returns filenames for each date partition
        mock_client.query_fnames.return_value = [m.fname for m in metas]
        # query_image returns None (images not available) — this is fine for testing
        mock_client.query_image.return_value = None

        with patch("snapshot_screener.pipeline.collect_metadata", return_value=metas), \
             patch("snapshot_screener.pipeline.collect_phash", return_value=features), \
             patch("snapshot_screener.pipeline.collect_report_images", return_value={}), \
             patch("snapshot_screener.pipeline.render_report", return_value=tmp_path / "report.html"):

            result = run_single_equipment(mock_client, "EQ-TEST", config)

        assert result is not None
        assert isinstance(result, AnalysisResult)
        assert result.eqpid == "EQ-TEST"
        assert result.total_clicks == 20
        assert result.representative_count > 0
        assert 0 <= result.reduction_rate <= 1
        assert result.screening is not None

    def test_empty_metadata_skips_gracefully(self, tmp_path):
        """Test equipment with no data returns None."""
        config = _make_config(
            eqpids=["EQ-EMPTY"],
            output_dir=str(tmp_path),
            cache_dir=str(tmp_path),
        )
        mock_client = MagicMock()

        with patch("snapshot_screener.pipeline.collect_metadata", return_value=[]):
            result = run_single_equipment(mock_client, "EQ-EMPTY", config)

        assert result is None

    def test_empty_features_skips_gracefully(self, tmp_path):
        """Test equipment with metas but no features (all images failed) returns None."""
        config = _make_config(
            eqpids=["EQ-NOPHASH"],
            output_dir=str(tmp_path),
            cache_dir=str(tmp_path),
        )
        metas = _make_metas("EQ-NOPHASH", 5)
        mock_client = MagicMock()

        with patch("snapshot_screener.pipeline.collect_metadata", return_value=metas), \
             patch("snapshot_screener.pipeline.collect_phash", return_value=[]):
            result = run_single_equipment(mock_client, "EQ-NOPHASH", config)

        assert result is None


class TestRunPipeline:
    """Tests for run_pipeline()."""

    @staticmethod
    def _mock_cassandra_client():
        """Create a mock CassandraClient context manager and patch the import."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        # Create a mock module so that the local import inside run_pipeline succeeds
        mock_module = MagicMock()
        mock_module.CassandraClient = MagicMock(return_value=mock_client)
        return mock_client, mock_module

    def test_multi_equipment_produces_summary(self, tmp_path):
        """Test multi-equipment run produces summary."""
        config = _make_config(
            eqpids=["EQ-01", "EQ-02"],
            output_dir=str(tmp_path),
            cache_dir=str(tmp_path),
        )

        result1 = _make_analysis_result("EQ-01")
        result2 = _make_analysis_result("EQ-02")

        mock_client, mock_module = self._mock_cassandra_client()

        with patch.dict("sys.modules", {"snapshot_screener.db.cassandra_client": mock_module}), \
             patch("snapshot_screener.pipeline.run_single_equipment", side_effect=[result1, result2]) as mock_run, \
             patch("snapshot_screener.pipeline.render_summary") as mock_summary:

            run_pipeline(config)

        assert mock_run.call_count == 2
        mock_summary.assert_called_once()
        call_args = mock_summary.call_args
        assert len(call_args[0][0]) == 2  # two results

    def test_equipment_failure_doesnt_stop_others(self, tmp_path):
        """Test that one equipment failure doesn't stop processing of others."""
        config = _make_config(
            eqpids=["EQ-FAIL", "EQ-OK"],
            output_dir=str(tmp_path),
            cache_dir=str(tmp_path),
        )

        result_ok = _make_analysis_result("EQ-OK")

        mock_client, mock_module = self._mock_cassandra_client()

        def side_effect(client, eqpid, cfg):
            if eqpid == "EQ-FAIL":
                raise RuntimeError("Simulated failure")
            return result_ok

        with patch.dict("sys.modules", {"snapshot_screener.db.cassandra_client": mock_module}), \
             patch("snapshot_screener.pipeline.run_single_equipment", side_effect=side_effect):

            # Should not raise even though EQ-FAIL errors
            run_pipeline(config)

    def test_single_equipment_no_summary(self, tmp_path):
        """Test single equipment does not produce summary."""
        config = _make_config(
            eqpids=["EQ-ONLY"],
            output_dir=str(tmp_path),
            cache_dir=str(tmp_path),
        )

        result = _make_analysis_result("EQ-ONLY")

        mock_client, mock_module = self._mock_cassandra_client()

        with patch.dict("sys.modules", {"snapshot_screener.db.cassandra_client": mock_module}), \
             patch("snapshot_screener.pipeline.run_single_equipment", return_value=result), \
             patch("snapshot_screener.pipeline.render_summary") as mock_summary:

            run_pipeline(config)

        mock_summary.assert_not_called()


# ---------------------------------------------------------------------------
# CLI main() exit code tests
# ---------------------------------------------------------------------------


class TestMainExitCodes:
    """Tests for main() exit codes."""

    def test_success_exit_code(self, tmp_path):
        """Test exit code 0 on success."""
        with patch("snapshot_screener.pipeline.run_pipeline") as mock_run:
            mock_run.return_value = None
            code = main([
                "--eqpid", "EQ-01",
                "--from", "2024-01-01",
                "--to", "2024-01-31",
                "--db-host", "10.0.0.1",
                "--db-keyspace", "ks",
                "--db-table", "tbl",
            ])
        assert code == 0

    def test_connection_failure_exit_code(self):
        """Test exit code 3 on ConnectionError."""
        with patch("snapshot_screener.pipeline.run_pipeline") as mock_run:
            mock_run.side_effect = ConnectionError("Cannot connect")
            code = main([
                "--eqpid", "EQ-01",
                "--from", "2024-01-01",
                "--to", "2024-01-31",
                "--db-host", "10.0.0.1",
                "--db-keyspace", "ks",
                "--db-table", "tbl",
            ])
        assert code == 3

    def test_value_error_exit_code(self):
        """Test exit code 1 on ValueError."""
        with patch("snapshot_screener.pipeline.run_pipeline") as mock_run:
            mock_run.side_effect = ValueError("Bad config")
            code = main([
                "--eqpid", "EQ-01",
                "--from", "2024-01-01",
                "--to", "2024-01-31",
                "--db-host", "10.0.0.1",
                "--db-keyspace", "ks",
                "--db-table", "tbl",
            ])
        assert code == 1

    def test_generic_exception_exit_code(self):
        """Test exit code 2 on generic Exception."""
        with patch("snapshot_screener.pipeline.run_pipeline") as mock_run:
            mock_run.side_effect = RuntimeError("Analysis failed")
            code = main([
                "--eqpid", "EQ-01",
                "--from", "2024-01-01",
                "--to", "2024-01-31",
                "--db-host", "10.0.0.1",
                "--db-keyspace", "ks",
                "--db-table", "tbl",
            ])
        assert code == 2

    def test_keyboard_interrupt_exit_code(self):
        """Test exit code 130 on KeyboardInterrupt."""
        with patch("snapshot_screener.pipeline.run_pipeline") as mock_run:
            mock_run.side_effect = KeyboardInterrupt()
            code = main([
                "--eqpid", "EQ-01",
                "--from", "2024-01-01",
                "--to", "2024-01-31",
                "--db-host", "10.0.0.1",
                "--db-keyspace", "ks",
                "--db-table", "tbl",
            ])
        assert code == 130
