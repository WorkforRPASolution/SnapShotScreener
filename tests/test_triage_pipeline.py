"""Tests for snapshot_screener.triage.pipeline and CLI integration."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from snapshot_screener.config import TriageConfig
from snapshot_screener.triage.models import TriageEquipmentResult
from snapshot_screener.triage.csv_loader import EquipmentInfo


def _make_triage_config(tmp_path, **overrides) -> TriageConfig:
    csv_file = tmp_path / "eq.csv"
    csv_file.write_text(
        "p,m,e\n"
        "P1,M1,EQ-001\n"
        "P1,M1,EQ-002\n"
        "P2,M2,EQ-003\n",
        encoding="utf-8",
    )
    defaults = dict(
        csv_path=str(csv_file),
        date_from=date(2026, 3, 15),
        date_to=date(2026, 3, 29),
        db_host="localhost",
        db_keyspace="ars",
        output_dir=str(tmp_path / "output"),
    )
    defaults.update(overrides)
    return TriageConfig(**defaults)


class TestTriageAnalysisFlow:
    """Test triage analysis flow using collector + screening directly
    (avoids importing cassandra_client which requires cassandra-driver)."""

    def test_no_data_gives_no_result(self, tmp_path):
        """Empty snapshotlist query → empty metadata → no screening."""
        config = _make_triage_config(tmp_path)
        mock_client = MagicMock()
        mock_client.query_snapshotlist.return_value = []

        from snapshot_screener.triage.collector import collect_triage_metadata
        metas = collect_triage_metadata(mock_client, "EQ-001", config)
        assert metas == []

    def test_full_analysis_flow(self, tmp_path):
        """Verify collector → session → clustering → screening flow."""
        config = _make_triage_config(tmp_path)
        mock_client = MagicMock()
        fnames = [
            f"177403680{i:04d}_[{100 + (i % 5) * 50}][{200 + (i % 3) * 30}].png"
            for i in range(100)
        ]
        mock_client.query_snapshotlist.return_value = fnames

        from snapshot_screener.triage.collector import collect_triage_metadata, count_data_days
        from snapshot_screener.triage.screening import compute_triage_screening
        from snapshot_screener.analysis.session import separate_sessions
        from snapshot_screener.analysis.clustering import cluster_clicks
        from snapshot_screener.models import FrameFeature

        metas = collect_triage_metadata(mock_client, "EQ-001", config)
        assert len(metas) == 100

        features = [
            FrameFeature(
                eqpid=m.eqpid, fname=m.fname, timestamp_ms=m.timestamp_ms,
                x=m.x, y=m.y,
                x_norm=m.x / 1920, y_norm=m.y / 1080,
            )
            for m in metas
        ]
        separate_sessions(features, config.session_gap_ms, "EQ-001")
        for f in features:
            f._phase_completed = 2
        cluster_clicks(features, config.dbscan_eps, config.dbscan_min_samples, 1920, 1080)

        result = compute_triage_screening(features, "EQ-001", "P1", "M1", count_data_days(metas))
        assert result.total_clicks == 100
        assert result.verdict in ("high", "medium", "low")
        assert result.click_concentration is not None


def _mock_analyze(results_map):
    """Return a function that replaces _analyze_single_equipment."""
    def _analyze(client, eq, config):
        if eq.eqpid in results_map:
            return results_map[eq.eqpid]
        return TriageEquipmentResult(
            eqpid=eq.eqpid, process=eq.process, model=eq.model,
            total_clicks=100, session_count=10, data_days=7,
            click_concentration=0.8, click_concentration_level="high",
            session_cv=0.2, session_cv_level="high", verdict="high",
        )
    return _analyze


def _has_real_cassandra():
    """Check if the real cassandra-driver package is installed (not a test stub)."""
    try:
        from cassandra.cluster import Cluster  # noqa: F401
        return not isinstance(Cluster, MagicMock)
    except Exception:
        return False


@pytest.mark.skipif(not _has_real_cassandra(), reason="cassandra-driver not installed")
class TestRunTriage:

    @patch("snapshot_screener.triage.pipeline._analyze_single_equipment")
    @patch("snapshot_screener.triage.pipeline.CassandraClient", create=True)
    def test_full_pipeline(self, MockClient, mock_analyze, tmp_path):
        from snapshot_screener.triage.pipeline import run_triage

        config = _make_triage_config(tmp_path)

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.health_check.return_value = True
        MockClient.return_value = mock_instance

        mock_analyze.side_effect = _mock_analyze({})

        report = run_triage(config)

        assert report is not None
        assert report.total_equipment == 3
        assert report.high_count + report.medium_count + report.low_count + report.error_count == 3

        # Check output files exist
        output_dir = Path(config.output_dir)
        csv_files = list(output_dir.glob("TriageReport_*.csv"))
        json_files = list(output_dir.glob("TriageReport_*.json"))
        html_files = list(output_dir.glob("TriageReport_*.html"))
        assert len(csv_files) == 1
        assert len(json_files) == 1
        assert len(html_files) == 1

        # Verify JSON structure
        json_data = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert json_data["version"] == "1.0"
        assert json_data["mode"] == "triage"
        assert len(json_data["equipment"]) == 3

    @patch("snapshot_screener.triage.pipeline._analyze_single_equipment")
    @patch("snapshot_screener.triage.pipeline.CassandraClient", create=True)
    def test_journal_created(self, MockClient, mock_analyze, tmp_path):
        from snapshot_screener.triage.pipeline import run_triage

        config = _make_triage_config(tmp_path)

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.health_check.return_value = True
        MockClient.return_value = mock_instance

        mock_analyze.return_value = TriageEquipmentResult(
            eqpid="X", process="P", model="M", error="no_data",
        )

        run_triage(config)

        journal_files = list(Path(config.output_dir).glob("triage_*.jsonl"))
        assert len(journal_files) == 1
        lines = journal_files[0].read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3  # 3 equipment

    @patch("snapshot_screener.triage.pipeline._analyze_single_equipment")
    @patch("snapshot_screener.triage.pipeline.CassandraClient", create=True)
    def test_circuit_breaker(self, MockClient, mock_analyze, tmp_path):
        from snapshot_screener.triage.pipeline import run_triage

        config = _make_triage_config(tmp_path, circuit_breaker_threshold=2)

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.health_check.return_value = False
        MockClient.return_value = mock_instance

        mock_analyze.side_effect = RuntimeError("DB down")

        report = run_triage(config)

        # Circuit breaker should stop after 2 consecutive failures
        assert report is not None
        assert report.total_equipment == 2  # stopped early


class TestTriageCLI:

    def test_triage_flag_parsed(self):
        from snapshot_screener.cli import parse_args
        args, _ = parse_args([
            "--triage",
            "--csv", "test.csv",
            "--from", "2026-03-15",
            "--to", "2026-03-29",
            "--db-host", "localhost",
            "--db-keyspace", "ars",
        ])
        assert args.triage is True
        assert args.csv == "test.csv"

    def test_build_triage_config(self, tmp_path):
        from snapshot_screener.cli import build_triage_config, parse_args
        csv_file = tmp_path / "eq.csv"
        csv_file.write_text("p,m,e\nP1,M1,EQ-001\n", encoding="utf-8")

        args, parser = parse_args([
            "--triage",
            "--csv", str(csv_file),
            "--from", "2026-03-15",
            "--to", "2026-03-29",
            "--db-host", "localhost",
            "--db-keyspace", "ars",
        ])
        config = build_triage_config(args, parser)
        assert isinstance(config, TriageConfig)
        assert config.csv_path == str(csv_file)
        # fname_delay_ms comes from argparse default (100) when not explicitly set
        assert config.fname_delay_ms in (50, 100)

    def test_triage_auto_dates(self, tmp_path):
        """When --from/--to are omitted in triage, auto-default to last 14 days."""
        from snapshot_screener.cli import build_triage_config, parse_args
        csv_file = tmp_path / "eq.csv"
        csv_file.write_text("p,m,e\nP1,M1,EQ-001\n", encoding="utf-8")

        args, parser = parse_args([
            "--triage",
            "--csv", str(csv_file),
            "--db-host", "localhost",
            "--db-keyspace", "ars",
        ])
        config = build_triage_config(args, parser)
        assert config.date_from is not None
        assert config.date_to is not None
        assert (config.date_to - config.date_from).days == 13

    @pytest.mark.skipif(not _has_real_cassandra(), reason="cassandra-driver not installed")
    def test_triage_via_config_file(self, tmp_path):
        """triage: true in YAML config activates triage mode without --triage flag."""
        from snapshot_screener.cli import main

        csv_file = tmp_path / "eq.csv"
        csv_file.write_text("p,m,e\nP1,M1,EQ-001\n", encoding="utf-8")

        config_file = tmp_path / "triage.yaml"
        config_file.write_text(
            f"triage: true\n"
            f"csv: eq.csv\n"
            f"date_from: '2026-03-15'\n"
            f"date_to: '2026-03-29'\n"
            f"db_host: localhost\n"
            f"db_keyspace: ars\n"
            f"output_dir: '{tmp_path / 'output'}'\n",
            encoding="utf-8",
        )

        # Should dispatch to triage mode (will fail at Cassandra connect,
        # but we verify it reaches triage path by checking exit code 3)
        result = main(["--config", str(config_file)])
        assert result == 3  # ConnectionError = triage tried to connect

    def test_csv_relative_to_config(self, tmp_path):
        """CSV path is resolved relative to config file directory."""
        from snapshot_screener.cli import build_triage_config, parse_args

        sub = tmp_path / "configs"
        sub.mkdir()
        csv_file = sub / "eq.csv"
        csv_file.write_text("p,m,e\nP1,M1,EQ-001\n", encoding="utf-8")

        config_file = sub / "my.yaml"
        config_file.write_text(
            "triage: true\n"
            "csv: eq.csv\n"
            "date_from: '2026-03-15'\n"
            "date_to: '2026-03-29'\n"
            "db_host: localhost\n"
            "db_keyspace: ars\n",
            encoding="utf-8",
        )

        args, parser = parse_args(["--triage", "--config", str(config_file)])
        config = build_triage_config(args, parser)
        assert config.csv_path == str(csv_file)
