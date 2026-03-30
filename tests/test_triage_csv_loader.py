"""Tests for snapshot_screener.triage.csv_loader."""
from __future__ import annotations

import pytest

from snapshot_screener.triage.csv_loader import load_equipment_csv, group_by_process_model


class TestLoadEquipmentCSV:

    def test_basic_load(self, tmp_path):
        csv_file = tmp_path / "eq.csv"
        csv_file.write_text(
            "process,model,eqpid\n"
            "P1,M1,EQ-001\n"
            "P1,M1,EQ-002\n"
            "P2,M2,EQ-003\n",
            encoding="utf-8",
        )
        result = load_equipment_csv(str(csv_file))
        assert len(result) == 3
        assert result[0].eqpid == "EQ-001"
        assert result[0].process == "P1"
        assert result[0].model == "M1"

    def test_order_based_parsing(self, tmp_path):
        """Column names don't matter — order is: process, model, eqpid."""
        csv_file = tmp_path / "eq.csv"
        csv_file.write_text(
            "col_a,col_b,col_c\n"
            "PROC,MOD,EQ-X\n",
            encoding="utf-8",
        )
        result = load_equipment_csv(str(csv_file))
        assert result[0].process == "PROC"
        assert result[0].model == "MOD"
        assert result[0].eqpid == "EQ-X"

    def test_bom_handling(self, tmp_path):
        csv_file = tmp_path / "eq.csv"
        csv_file.write_bytes(
            b"\xef\xbb\xbfprocess,model,eqpid\nP1,M1,EQ-001\n"
        )
        result = load_equipment_csv(str(csv_file))
        assert len(result) == 1
        assert result[0].process == "P1"

    def test_duplicate_eqpid_skipped(self, tmp_path):
        csv_file = tmp_path / "eq.csv"
        csv_file.write_text(
            "p,m,e\n"
            "P1,M1,EQ-001\n"
            "P2,M2,EQ-001\n"
            "P1,M1,EQ-002\n",
            encoding="utf-8",
        )
        result = load_equipment_csv(str(csv_file))
        assert len(result) == 2
        eqpids = [r.eqpid for r in result]
        assert "EQ-001" in eqpids
        assert "EQ-002" in eqpids

    def test_blank_lines_skipped(self, tmp_path):
        csv_file = tmp_path / "eq.csv"
        csv_file.write_text(
            "p,m,e\n"
            "P1,M1,EQ-001\n"
            "\n"
            "  \n"
            "P1,M1,EQ-002\n",
            encoding="utf-8",
        )
        result = load_equipment_csv(str(csv_file))
        assert len(result) == 2

    def test_empty_file_raises(self, tmp_path):
        csv_file = tmp_path / "eq.csv"
        csv_file.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="empty"):
            load_equipment_csv(str(csv_file))

    def test_header_only_raises(self, tmp_path):
        csv_file = tmp_path / "eq.csv"
        csv_file.write_text("p,m,e\n", encoding="utf-8")
        with pytest.raises(ValueError, match="No valid"):
            load_equipment_csv(str(csv_file))

    def test_fewer_than_3_columns_raises(self, tmp_path):
        csv_file = tmp_path / "eq.csv"
        csv_file.write_text("a,b\nP1,M1\n", encoding="utf-8")
        with pytest.raises(ValueError, match="at least 3"):
            load_equipment_csv(str(csv_file))

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_equipment_csv("/nonexistent/file.csv")

    def test_whitespace_stripped(self, tmp_path):
        csv_file = tmp_path / "eq.csv"
        csv_file.write_text(
            "p,m,e\n"
            "  P1 , M1 , EQ-001 \n",
            encoding="utf-8",
        )
        result = load_equipment_csv(str(csv_file))
        assert result[0].process == "P1"
        assert result[0].model == "M1"
        assert result[0].eqpid == "EQ-001"


class TestGroupByProcessModel:

    def test_grouping(self, tmp_path):
        csv_file = tmp_path / "eq.csv"
        csv_file.write_text(
            "p,m,e\n"
            "P1,M1,EQ-001\n"
            "P1,M1,EQ-002\n"
            "P2,M2,EQ-003\n",
            encoding="utf-8",
        )
        equipment = load_equipment_csv(str(csv_file))
        groups = group_by_process_model(equipment)
        assert len(groups) == 2
        assert len(groups[("P1", "M1")]) == 2
        assert len(groups[("P2", "M2")]) == 1
