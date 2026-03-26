"""Tests for analysis.session — session separation (FR-05)."""
from __future__ import annotations

import pytest

from snapshot_screener.models import FrameFeature
from snapshot_screener.analysis.session import separate_sessions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_features(timestamps: list[int], eqpid: str = "EQ") -> list[FrameFeature]:
    """Create minimal FrameFeatures from a list of timestamps."""
    return [
        FrameFeature(
            eqpid=eqpid,
            fname=f"frame_{i}.png",
            timestamp_ms=ts,
            x=100,
            y=200,
        )
        for i, ts in enumerate(timestamps)
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSingleSession:
    def test_all_frames_same_session(self):
        """Frames within the gap should all share one session."""
        features = _make_features([1000, 2000, 3000, 4000])
        result = separate_sessions(features, session_gap_ms=5000, eqpid="EQ")

        assert all(f.session_id == "EQ_S0001" for f in result)
        assert result[0].is_session_start is True
        assert result[-1].is_session_end is True
        # Middle frames are not session boundaries
        assert result[1].is_session_start is False
        assert result[1].is_session_end is False

    def test_seq_is_zero_based(self):
        features = _make_features([100, 200, 300])
        separate_sessions(features, eqpid="X")
        assert [f.seq for f in features] == [0, 1, 2]

    def test_delta_ms_values(self):
        features = _make_features([1000, 3000, 7000])
        separate_sessions(features, eqpid="X")
        assert features[0].delta_ms is None
        assert features[1].delta_ms == 2000
        assert features[2].delta_ms == 4000

    def test_phase_completed(self):
        features = _make_features([100])
        separate_sessions(features, eqpid="X")
        assert all(f._phase_completed == 1 for f in features)


class TestMultipleSessions:
    def test_gap_splits_sessions(self):
        """A gap larger than threshold creates a new session."""
        # Gap of 10_000 between frame 2 and 3, threshold 5_000
        features = _make_features([1000, 2000, 3000, 13001, 14000])
        separate_sessions(features, session_gap_ms=5000, eqpid="EQ")

        assert features[0].session_id == "EQ_S0001"
        assert features[2].session_id == "EQ_S0001"
        assert features[3].session_id == "EQ_S0002"
        assert features[4].session_id == "EQ_S0002"

        # Session boundaries
        assert features[0].is_session_start is True
        assert features[2].is_session_end is True
        assert features[3].is_session_start is True
        assert features[4].is_session_end is True

    def test_seq_resets_per_session(self):
        features = _make_features([100, 200, 10000, 10100])
        separate_sessions(features, session_gap_ms=1000, eqpid="X")

        assert features[0].seq == 0
        assert features[1].seq == 1
        assert features[2].seq == 0  # new session
        assert features[3].seq == 1

    def test_three_sessions(self):
        features = _make_features([0, 100, 20000, 20100, 40000])
        separate_sessions(features, session_gap_ms=1000, eqpid="E")
        session_ids = [f.session_id for f in features]
        assert session_ids == ["E_S0001", "E_S0001", "E_S0002", "E_S0002", "E_S0003"]


class TestGapAtThreshold:
    def test_exact_threshold_no_split(self):
        """Delta == gap should NOT trigger a new session (> not >=)."""
        features = _make_features([0, 5000])
        separate_sessions(features, session_gap_ms=5000, eqpid="X")
        assert features[0].session_id == features[1].session_id

    def test_one_over_threshold_splits(self):
        features = _make_features([0, 5001])
        separate_sessions(features, session_gap_ms=5000, eqpid="X")
        assert features[0].session_id != features[1].session_id


class TestEmptyInput:
    def test_empty_list(self):
        result = separate_sessions([], eqpid="X")
        assert result == []

    def test_single_frame(self):
        features = _make_features([42])
        separate_sessions(features, eqpid="X")
        assert features[0].is_session_start is True
        assert features[0].is_session_end is True
        assert features[0].session_id == "X_S0001"
        assert features[0]._phase_completed == 1


class TestReturnsMutatedList:
    def test_returns_same_object(self):
        features = _make_features([1, 2, 3])
        result = separate_sessions(features, eqpid="X")
        assert result is features
