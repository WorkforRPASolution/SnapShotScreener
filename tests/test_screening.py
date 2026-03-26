"""Tests for analysis.screening — screening metrics and verdict (FR-11~14)."""
from __future__ import annotations

import pytest

from snapshot_screener.models import FrameFeature
from snapshot_screener.analysis.screening import compute_screening, _lcs_length


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_feature(
    *,
    session_id: str = "S1",
    click_cluster_id: int = 0,
    screen_group_id: str = "SG_0001",
    phase: int = 5,
) -> FrameFeature:
    f = FrameFeature(
        eqpid="EQ",
        fname="f.png",
        timestamp_ms=0,
        x=0,
        y=0,
        session_id=session_id,
        click_cluster_id=click_cluster_id,
        screen_group_id=screen_group_id,
    )
    f._phase_completed = phase
    return f


def _make_high_pattern_features() -> list[FrameFeature]:
    """Create features that should produce verdict '높음'.

    - High click concentration (> 0.7): most clicks in clusters
    - High session CV (consistent, CV < 0.3): equal-sized sessions
    - High sequence similarity (> 0.7): identical screen sequences
    """
    features = []
    # 3 sessions, each with exactly 5 frames, same screen sequence
    screen_seq = ["SG_0001", "SG_0002", "SG_0003", "SG_0004", "SG_0005"]
    for s_idx in range(3):
        session_id = f"S{s_idx}"
        for i, sg in enumerate(screen_seq):
            f = FrameFeature(
                eqpid="EQ",
                fname=f"f_{s_idx}_{i}.png",
                timestamp_ms=s_idx * 10000 + i * 100,
                x=100,
                y=100,
                session_id=session_id,
                click_cluster_id=0,  # all clustered
                screen_group_id=sg,
            )
            f._phase_completed = 5
            features.append(f)
    return features


def _make_low_pattern_features() -> list[FrameFeature]:
    """Create features that should produce verdict '낮음'.

    - Low click concentration: most clicks are noise
    - Low session CV (inconsistent, CV > 1.0): wildly different session sizes
    - Low sequence similarity: very different screen sequences per session
    """
    features = []
    # Session 1: 3 frames
    for i in range(3):
        f = FrameFeature(
            eqpid="EQ",
            fname=f"f_0_{i}.png",
            timestamp_ms=i * 100,
            x=100,
            y=100,
            session_id="S0",
            click_cluster_id=-1,  # noise
            screen_group_id=f"SG_{i:04d}",
        )
        f._phase_completed = 5
        features.append(f)

    # Session 2: 30 frames, all noise, all different screens
    for i in range(30):
        f = FrameFeature(
            eqpid="EQ",
            fname=f"f_1_{i}.png",
            timestamp_ms=10000 + i * 100,
            x=100,
            y=100,
            session_id="S1",
            click_cluster_id=-1,
            screen_group_id=f"SG_{100 + i:04d}",
        )
        f._phase_completed = 5
        features.append(f)

    return features


# ---------------------------------------------------------------------------
# Tests: LCS correctness
# ---------------------------------------------------------------------------


class TestLCS:
    def test_identical(self):
        assert _lcs_length([1, 2, 3], [1, 2, 3]) == 3

    def test_empty(self):
        assert _lcs_length([], [1, 2, 3]) == 0
        assert _lcs_length([1, 2, 3], []) == 0

    def test_no_common(self):
        assert _lcs_length([1, 2, 3], [4, 5, 6]) == 0

    def test_partial(self):
        assert _lcs_length([1, 3, 4, 5], [1, 2, 4, 5]) == 3

    def test_subsequence(self):
        assert _lcs_length([1, 2, 3, 4, 5], [2, 4]) == 2

    def test_classic_example(self):
        # "ABCBDAB" vs "BDCAB" → LCS = 4 ("BCAB")
        a = list("ABCBDAB")
        b = list("BDCAB")
        assert _lcs_length(a, b) == 4


# ---------------------------------------------------------------------------
# Tests: Click concentration (FR-11)
# ---------------------------------------------------------------------------


class TestClickConcentration:
    def test_high_concentration(self):
        # 15 clustered frames
        features = [_make_feature(click_cluster_id=0) for _ in range(15)]
        result = compute_screening(features)
        assert result.click_concentration == pytest.approx(1.0)
        assert result.click_concentration_level == "high"

    def test_insufficient_data(self):
        features = [_make_feature() for _ in range(5)]  # < 10
        result = compute_screening(features)
        assert result.click_concentration is None
        assert result.click_concentration_level == "insufficient_data"

    def test_low_concentration(self):
        # 8 noise + 2 clustered = 0.2
        features = [_make_feature(click_cluster_id=-1) for _ in range(8)]
        features += [_make_feature(click_cluster_id=0) for _ in range(2)]
        result = compute_screening(features)
        assert result.click_concentration == pytest.approx(0.2)
        assert result.click_concentration_level == "low"


# ---------------------------------------------------------------------------
# Tests: Session CV (FR-12)
# ---------------------------------------------------------------------------


class TestSessionCV:
    def test_consistent_sessions(self):
        """Equal-sized sessions should have low CV (high consistency)."""
        features = []
        for s in range(3):
            for i in range(5):
                features.append(
                    _make_feature(session_id=f"S{s}", click_cluster_id=0)
                )
        result = compute_screening(features)
        assert result.session_cv == pytest.approx(0.0)
        assert result.session_cv_level == "high"

    def test_insufficient_sessions(self):
        """Only 1 session → insufficient data."""
        features = [_make_feature(session_id="S0") for _ in range(10)]
        result = compute_screening(features)
        assert result.session_cv is None
        assert result.session_cv_level == "insufficient_data"


# ---------------------------------------------------------------------------
# Tests: Sequence similarity (FR-13)
# ---------------------------------------------------------------------------


class TestSequenceSimilarity:
    def test_identical_sequences(self):
        """Same screen sequence in all sessions → high similarity."""
        features = _make_high_pattern_features()
        result = compute_screening(features)
        assert result.sequence_similarity == pytest.approx(1.0)
        assert result.sequence_similarity_level == "high"

    def test_insufficient_sessions(self):
        features = [_make_feature(session_id="S0") for _ in range(10)]
        result = compute_screening(features)
        assert result.sequence_similarity is None
        assert result.sequence_similarity_level == "insufficient_data"


# ---------------------------------------------------------------------------
# Tests: Verdict (FR-14)
# ---------------------------------------------------------------------------


class TestVerdict:
    def test_high_verdict(self):
        """High pattern data should yield '높음'."""
        features = _make_high_pattern_features()
        result = compute_screening(features)
        assert result.verdict == "높음"

    def test_low_verdict(self):
        """Low pattern data should yield '낮음'."""
        features = _make_low_pattern_features()
        result = compute_screening(features)
        assert result.verdict == "낮음"

    def test_all_insufficient_yields_medium(self):
        """When all signals are insufficient, default to '중간'."""
        # < 10 frames, 1 session → all insufficient
        features = [_make_feature(session_id="S0") for _ in range(5)]
        result = compute_screening(features)
        assert result.verdict == "중간"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestPhaseAssertions:
    def test_entry_assertion(self):
        features = [_make_feature(phase=4)]
        with pytest.raises(AssertionError):
            compute_screening(features)
