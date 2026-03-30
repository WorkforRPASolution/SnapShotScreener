"""Tests for snapshot_screener.triage.pipeline and CLI integration."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from snapshot_screener.config import TriageConfig
from snapshot_screener.triage.models import TriageEquipmentResult
from snapshot_screener.triage.pipeline import _analyze_single_equipment, run_triage
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


class TestAnalyzeSingleEquipment:

    def test_no_data_returns_error(self, tmp_path):
        config = _make_triage_config(tmp_path)
        mock_client = MagicMock()
        mock_client.query_snapshotlist.return_value = []
        eq = EquipmentInfo(eqpid="EQ-001", process="P1", model="M1")

        result = _analyze_single_equipment(mock_client, eq, config)

        assert result.error == "no_data"
        assert result.eqpid == "EQ-001"

    def test_with_data_returns_screening(self, tmp_path):
        config = _make_triage_config(tmp_path)
        mock_client = MagicMock()
        # Generate enough fnames for meaningful analysis
        fnames = [
            f"177403680{i:04d}_[{100 + (i % 5) * 50}][{200 + (i % 3) * 30}].png"
            for i in range(100)
        ]
        mock_client.query_snapshotlist.return_value = fnames
        eq = EquipmentInfo(eqpid="EQ-001", process="P1", model="M1")

        result = _analyze_single_equipment(mock_client, eq, config)

        assert result.error is None
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


class TestRunTriage:

    @patch("snapshot_screener.triage.pipeline._analyze_single_equipment")
    @patch("snapshot_screener.triage.pipeline.CassandraClient")
    def test_full_pipeline(self, MockClient, mock_analyze, tmp_path):
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
    @patch("snapshot_screener.triage.pipeline.CassandraClient")
    def test_journal_created(self, MockClient, mock_analyze, tmp_path):
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
    @patch("snapshot_screener.triage.pipeline.CassandraClient")
    def test_circuit_breaker(self, MockClient, mock_analyze, tmp_path):
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
