"""Tests for snapshot_screener.triage.screening."""
from __future__ import annotations

from snapshot_screener.models import FrameFeature
from snapshot_screener.triage.screening import (
    _triage_session_cv,
    _triage_verdict,
    compute_triage_screening,
)


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


class TestTriageSessionCV:
    """Test triage-specific session CV thresholds."""

    def test_high_uniform_sessions(self):
        """Sessions with nearly identical click counts → high."""
        # 4 sessions, each with exactly 5 clicks → CV ≈ 0
        sessions = ["S1"] * 5 + ["S2"] * 5 + ["S3"] * 5 + ["S4"] * 5
        features = _make_features(20, session_ids=sessions)
        cv_val, level = _triage_session_cv(features)
        assert level == "high"
        assert cv_val is not None and cv_val < 0.25

    def test_low_variable_sessions(self):
        """Sessions with very different click counts → low."""
        # 3 sessions: 3, 5, 50 clicks → CV > 1.0
        sessions = ["S1"] * 3 + ["S2"] * 5 + ["S3"] * 50
        features = _make_features(58, session_ids=sessions)
        cv_val, level = _triage_session_cv(features)
        assert level == "low"
        assert cv_val is not None and cv_val > 1.0

    def test_insufficient_data(self):
        """Single session → insufficient data."""
        features = _make_features(10, session_ids=["S1"] * 10)
        cv_val, level = _triage_session_cv(features)
        assert level == "insufficient_data"
        assert cv_val is None


class TestTriageVerdict:
    """Test session-CV-only verdict logic."""

    def test_high_cv_gives_high(self):
        assert _triage_verdict("high") == "high"

    def test_medium_cv_gives_medium(self):
        assert _triage_verdict("medium") == "medium"

    def test_low_cv_gives_low(self):
        assert _triage_verdict("low") == "low"

    def test_insufficient_gives_medium(self):
        assert _triage_verdict("insufficient_data") == "medium"


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

    def test_high_concentration_reported_but_not_in_verdict(self):
        """Concentration is reported but does not affect verdict."""
        # All clicks clustered → concentration high, but single session → CV insufficient
        features = _make_features(20, cluster_ids=[0] * 20)
        result = compute_triage_screening(
            features, "EQ-T", "P", "M", data_days=3
        )
        assert result.click_concentration == 1.0
        assert result.click_concentration_level == "high"
        # Verdict is medium (from insufficient CV), not high
        assert result.verdict == "medium"

    def test_verdict_follows_session_cv(self):
        """Verdict follows session CV, not concentration."""
        # 4 uniform sessions (CV ≈ 0) + all clustered
        sessions = ["S1"] * 5 + ["S2"] * 5 + ["S3"] * 5 + ["S4"] * 5
        features = _make_features(20, cluster_ids=[0] * 20, session_ids=sessions)
        result = compute_triage_screening(
            features, "EQ-T", "P", "M", data_days=3
        )
        assert result.verdict == "high"
        assert result.session_cv_level == "high"
