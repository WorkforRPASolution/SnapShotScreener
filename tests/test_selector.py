"""Tests for analysis.selector — representative frame selection (FR-10)."""
from __future__ import annotations

import pytest

from snapshot_screener.models import FrameFeature
from snapshot_screener.analysis.selector import select_representatives


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_feature(
    *,
    fname: str = "frame.png",
    timestamp_ms: int = 0,
    session_id: str = "EQ_S0001",
    screen_group_id: str = "SG_0001",
    is_session_start: bool = False,
    is_session_end: bool = False,
    is_new_screen: bool = False,
    is_transition_point: bool = False,
    is_new_click_cluster: bool = False,
    phase: int = 4,
) -> FrameFeature:
    f = FrameFeature(
        eqpid="EQ",
        fname=fname,
        timestamp_ms=timestamp_ms,
        x=100,
        y=200,
        session_id=session_id,
        screen_group_id=screen_group_id,
        is_session_start=is_session_start,
        is_session_end=is_session_end,
        is_new_screen=is_new_screen,
        is_transition_point=is_transition_point,
        is_new_click_cluster=is_new_click_cluster,
    )
    f._phase_completed = phase
    return f


# ---------------------------------------------------------------------------
# Tests: Simple selector
# ---------------------------------------------------------------------------


class TestSimpleSelectorBasic:
    def test_first_per_group_selected(self):
        """First frame of each screen group should be representative."""
        features = [
            _make_feature(fname="f1.png", screen_group_id="SG_0001", is_session_start=True),
            _make_feature(fname="f2.png", screen_group_id="SG_0001"),
            _make_feature(fname="f3.png", screen_group_id="SG_0002", is_new_screen=True),
            _make_feature(fname="f4.png", screen_group_id="SG_0002", is_session_end=True),
        ]
        select_representatives(features, selector="simple")

        assert features[0].is_representative is True  # first of SG_0001
        assert features[1].is_representative is False  # duplicate of SG_0001
        assert features[2].is_representative is True  # first of SG_0002
        assert features[3].is_representative is True  # session end

    def test_phase_set_to_5(self):
        features = [_make_feature(fname="f1.png", is_session_start=True, is_session_end=True)]
        select_representatives(features)
        assert all(f._phase_completed == 5 for f in features)


class TestSimpleSelectorSessionBoundaries:
    def test_session_start_end_included(self):
        """Session start and end frames should always be representative."""
        features = [
            _make_feature(fname="start.png", is_session_start=True),
            _make_feature(fname="mid.png"),
            _make_feature(fname="end.png", is_session_end=True),
        ]
        select_representatives(features, selector="simple")
        assert features[0].is_representative is True
        assert features[2].is_representative is True


class TestSimpleSelectorDedup:
    def test_dedup_by_fname(self):
        """A frame that is both first-of-group and session_start should appear once."""
        features = [
            _make_feature(
                fname="same.png",
                screen_group_id="SG_0001",
                is_session_start=True,
                is_session_end=True,
            ),
        ]
        select_representatives(features, selector="simple")
        reps = [f for f in features if f.is_representative]
        assert len(reps) == 1


class TestSimpleSelectorFlags:
    def test_candidate_flags_populated(self):
        features = [
            _make_feature(
                fname="f.png",
                is_session_start=True,
                is_new_screen=True,
                is_session_end=True,
            ),
        ]
        select_representatives(features, selector="simple")
        assert "session_start" in features[0].candidate_flags
        assert "session_end" in features[0].candidate_flags
        assert "new_screen" in features[0].candidate_flags


# ---------------------------------------------------------------------------
# Tests: Scored selector
# ---------------------------------------------------------------------------


class TestScoredSelectorScoring:
    def test_scores_calculated(self):
        """Frames with more flags should have higher scores."""
        features = [
            _make_feature(
                fname="high.png",
                session_id="S1",
                is_session_start=True,
                is_new_screen=True,
                is_transition_point=True,
                is_new_click_cluster=True,
            ),
            _make_feature(fname="low.png", session_id="S1"),
        ]
        select_representatives(features, selector="scored")

        # high: 3 + 4 + 3 + 2 = 12
        assert features[0].candidate_score == 12.0
        assert features[1].candidate_score == 0.0

    def test_top_n_per_session(self):
        """Scored selector picks top N per session."""
        features = [
            _make_feature(fname="a.png", session_id="S1", screen_group_id="SG_0001",
                          is_session_start=True, is_new_screen=True),
            _make_feature(fname="b.png", session_id="S1", screen_group_id="SG_0002"),
            _make_feature(fname="c.png", session_id="S1", screen_group_id="SG_0003"),
        ]
        select_representatives(features, selector="scored")

        # With 3 screen groups: N = max(5, int(3*0.3)) = 5
        # All 3 should be selected since total < N
        reps = [f for f in features if f.is_representative]
        assert len(reps) >= 1  # at least the high-scored one


class TestScoredSelectorFlags:
    def test_all_flags_tracked(self):
        f = _make_feature(
            fname="f.png",
            session_id="S1",
            is_session_start=True,
            is_session_end=True,
            is_new_screen=True,
            is_transition_point=True,
            is_new_click_cluster=True,
        )
        select_representatives([f], selector="scored")
        assert set(f.candidate_flags) == {
            "session_start", "session_end", "new_screen",
            "transition_point", "new_click_cluster",
        }
        assert f.candidate_score == 3 + 3 + 4 + 3 + 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestPhaseAssertions:
    def test_entry_assertion_fails(self):
        features = [_make_feature(phase=3)]
        with pytest.raises(AssertionError):
            select_representatives(features)

    def test_unknown_selector_raises(self):
        features = [_make_feature()]
        with pytest.raises(ValueError, match="Unknown selector"):
            select_representatives(features, selector="magic")


class TestEmptyInput:
    def test_empty_list(self):
        result = select_representatives([])
        assert result == []
