"""Tests for snapshot_screener.triage.screening."""
from __future__ import annotations

from snapshot_screener.analysis.screening import verdict
from snapshot_screener.models import FrameFeature
from snapshot_screener.triage.screening import compute_triage_screening


def _make_features(n: int, cluster_ids=None, session_ids=None) -> list:
    """Create minimal FrameFeature list for triage screening tests."""
    features = []
    for i in range(n):
        f = FrameFeature(
            eqpid="EQ-T",
            fname=f"{1700000000000 + i * 1000}_[{100 + i}][200].png",
            timestamp_ms=1700000000000 + i * 1000,
            x=100 + i,
            y=200,
            x_norm=(100 + i) / 1920,
            y_norm=200 / 1080,
        )
        f.session_id = (session_ids or ["EQ-T_S0001"] * n)[i]
        f.click_cluster_id = (cluster_ids or [0] * n)[i]
        f._phase_completed = 3
        features.append(f)
    return features


class TestTriageVerdict:
    """Test 2-signal verdict (click concentration + session CV)."""

    def test_both_high_gives_high(self):
        assert verdict("high", "high", "insufficient_data") == "high"

    def test_one_high_gives_medium(self):
        assert verdict("high", "medium", "insufficient_data") == "medium"

    def test_both_low_gives_low(self):
        assert verdict("low", "low", "insufficient_data") == "low"

    def test_mixed_gives_medium(self):
        assert verdict("high", "low", "insufficient_data") == "medium"

    def test_both_insufficient_gives_medium(self):
        assert verdict("insufficient_data", "insufficient_data", "insufficient_data") == "medium"


class TestComputeTriageScreening:

    def test_basic_result_fields(self):
        features = _make_features(20, cluster_ids=[0] * 20)
        result = compute_triage_screening(
            features, "EQ-T", "PROC", "MODEL", data_days=5
        )
        assert result.eqpid == "EQ-T"
        assert result.process == "PROC"
        assert result.model == "MODEL"
        assert result.total_clicks == 20
        assert result.data_days == 5
        assert result.error is None
        assert result.click_concentration is not None
        assert result.verdict in ("high", "medium", "low")

    def test_insufficient_data(self):
        features = _make_features(5, cluster_ids=[-1] * 5)
        result = compute_triage_screening(
            features, "EQ-T", "P", "M", data_days=1
        )
        assert result.click_concentration_level == "insufficient_data"

    def test_high_concentration(self):
        # All 20 clicks in clusters → concentration = 1.0 → high
        features = _make_features(20, cluster_ids=[0] * 20)
        result = compute_triage_screening(
            features, "EQ-T", "P", "M", data_days=3
        )
        assert result.click_concentration == 1.0
        assert result.click_concentration_level == "high"
