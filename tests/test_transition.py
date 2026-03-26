"""Tests for analysis.transition — transition detection (FR-09)."""
from __future__ import annotations

import pytest

from snapshot_screener.models import FrameFeature
from snapshot_screener.analysis.transition import detect_transitions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_feature(
    *,
    is_new_screen: bool = False,
    phash_dist_prev: int | None = None,
    is_new_click_cluster: bool = False,
    delta_ms: int | None = None,
    phase: int = 3,
) -> FrameFeature:
    """Create a minimal FrameFeature with specified flags."""
    f = FrameFeature(
        eqpid="EQ",
        fname="frame.png",
        timestamp_ms=0,
        x=0,
        y=0,
        is_new_screen=is_new_screen,
        phash_dist_prev=phash_dist_prev,
        is_new_click_cluster=is_new_click_cluster,
        delta_ms=delta_ms,
    )
    f._phase_completed = phase
    return f


# ---------------------------------------------------------------------------
# Tests: Each condition independently
# ---------------------------------------------------------------------------


class TestNewScreenCondition:
    def test_new_screen_is_transition(self):
        features = [_make_feature(is_new_screen=True)]
        detect_transitions(features)
        assert features[0].is_transition_point is True

    def test_not_new_screen_alone_not_transition(self):
        features = [_make_feature()]
        detect_transitions(features)
        assert features[0].is_transition_point is False


class TestPhashDistCondition:
    def test_high_phash_dist_is_transition(self):
        features = [_make_feature(phash_dist_prev=10)]
        detect_transitions(features, phash_transition_threshold=8)
        assert features[0].is_transition_point is True

    def test_low_phash_dist_not_transition(self):
        features = [_make_feature(phash_dist_prev=5)]
        detect_transitions(features, phash_transition_threshold=8)
        assert features[0].is_transition_point is False

    def test_none_phash_dist_not_transition(self):
        features = [_make_feature(phash_dist_prev=None)]
        detect_transitions(features)
        assert features[0].is_transition_point is False


class TestNewClickClusterCondition:
    def test_new_click_cluster_is_transition(self):
        features = [_make_feature(is_new_click_cluster=True)]
        detect_transitions(features)
        assert features[0].is_transition_point is True


class TestCompoundDeltaCondition:
    def test_high_delta_with_new_screen(self):
        """Large delta + new screen = transition."""
        features = [_make_feature(delta_ms=35000, is_new_screen=True)]
        detect_transitions(features, delta_spike_ms=30000)
        assert features[0].is_transition_point is True

    def test_high_delta_with_phash_change(self):
        """Large delta + phash dist above similar threshold = transition."""
        features = [_make_feature(delta_ms=35000, phash_dist_prev=5)]
        detect_transitions(
            features,
            delta_spike_ms=30000,
            phash_transition_threshold=8,
            phash_similar_threshold=4,
        )
        assert features[0].is_transition_point is True

    def test_high_delta_alone_not_transition(self):
        """Large delta without visual change is NOT a transition."""
        features = [_make_feature(delta_ms=35000, phash_dist_prev=2)]
        detect_transitions(
            features,
            delta_spike_ms=30000,
            phash_transition_threshold=8,
            phash_similar_threshold=4,
        )
        assert features[0].is_transition_point is False

    def test_high_delta_none_phash_not_transition(self):
        """Large delta + None phash dist (no visual change info) = not transition via compound."""
        features = [_make_feature(delta_ms=35000, phash_dist_prev=None)]
        detect_transitions(features, delta_spike_ms=30000)
        assert features[0].is_transition_point is False


class TestNoTransitions:
    def test_all_quiet(self):
        """No flags set → no transitions."""
        features = [
            _make_feature(phash_dist_prev=1, delta_ms=1000)
            for _ in range(5)
        ]
        detect_transitions(features)
        assert all(f.is_transition_point is False for f in features)


class TestPhaseAssertions:
    def test_entry_assertion_fails(self):
        features = [_make_feature(phase=2)]
        with pytest.raises(AssertionError):
            detect_transitions(features)

    def test_phase_set_to_4(self):
        features = [_make_feature()]
        detect_transitions(features)
        assert features[0]._phase_completed == 4


class TestEmptyInput:
    def test_empty_list(self):
        result = detect_transitions([])
        assert result == []
