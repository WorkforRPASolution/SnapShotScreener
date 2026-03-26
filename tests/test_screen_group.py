"""Tests for analysis.screen_group — screen group assignment (FR-06, FR-07)."""
from __future__ import annotations

import pytest

from snapshot_screener.models import FrameFeature
from snapshot_screener.analysis.screen_group import assign_screen_groups


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_features_with_phash(
    phashes: list[str | None],
    phase: int = 1,
) -> list[FrameFeature]:
    """Create FrameFeatures with given pHash values, pre-set to given phase."""
    features = []
    for i, ph in enumerate(phashes):
        f = FrameFeature(
            eqpid="EQ",
            fname=f"frame_{i}.png",
            timestamp_ms=1000 * i,
            x=100,
            y=200,
            phash=ph,
        )
        f._phase_completed = phase
        features.append(f)
    return features


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAllSamePhash:
    def test_identical_frames_same_group(self):
        """Frames with identical pHash should share one screen group."""
        ph = "a" * 16  # 64-bit hash as 16 hex chars
        features = _make_features_with_phash([ph, ph, ph, ph])
        assign_screen_groups(features)

        group_ids = {f.screen_group_id for f in features}
        assert len(group_ids) == 1
        assert features[0].is_new_screen is True
        assert features[1].is_new_screen is False


class TestAllDifferent:
    def test_very_different_hashes(self):
        """Frames with very different pHashes should get different groups."""
        features = _make_features_with_phash([
            "0000000000000000",
            "ffffffffffffffff",
            "0f0f0f0f0f0f0f0f",
            "f0f0f0f0f0f0f0f0",
        ])
        assign_screen_groups(features)
        group_ids = [f.screen_group_id for f in features]
        assert len(set(group_ids)) == 4
        assert all(f.is_new_screen for f in features)


class TestAlternating:
    def test_a_b_a_canonical_remapping(self, make_phash_pair):
        """A -> B -> A pattern should remap third frame back to first group."""
        hash_a, hash_b = make_phash_pair(distance=10)  # Very different
        features = _make_features_with_phash([hash_a, hash_b, hash_a])
        assign_screen_groups(features, phash_similar_threshold=4)

        # First and third should share a group after canonical remapping
        assert features[0].screen_group_id == features[2].screen_group_id
        # Second should be different
        assert features[1].screen_group_id != features[0].screen_group_id


class TestCanonicalRemapping:
    def test_revisited_screen_gets_same_id(self, make_phash_pair):
        """Going A->B->C->A should remap the final A to the first group."""
        hash_a, hash_b = make_phash_pair(distance=12)
        # hash_c different from both
        hash_c = "0" * 16 if hash_a != "0" * 16 else "f" * 16
        features = _make_features_with_phash([hash_a, hash_b, hash_c, hash_a])
        assign_screen_groups(features, phash_similar_threshold=4)

        assert features[0].screen_group_id == features[3].screen_group_id


class TestNonePhash:
    def test_none_phash_gets_own_group(self):
        """Frames with None phash should each get a unique group."""
        features = _make_features_with_phash([None, None, None])
        assign_screen_groups(features)

        group_ids = [f.screen_group_id for f in features]
        assert len(set(group_ids)) == 3
        assert all(f.phash_dist_prev is None for f in features)

    def test_mixed_none_and_valid(self):
        """None phash mixed with valid should not break distance calc."""
        ph = "a" * 16
        features = _make_features_with_phash([ph, None, ph])
        assign_screen_groups(features)

        assert features[0].phash_dist_prev is None
        assert features[1].phash_dist_prev is None
        assert features[2].phash_dist_prev is None  # prev is None phash


class TestPhaseAssertions:
    def test_entry_assertion_fails(self):
        """Should raise if phase < 1."""
        features = _make_features_with_phash(["a" * 16], phase=0)
        with pytest.raises(AssertionError):
            assign_screen_groups(features)

    def test_phase_set_to_2(self):
        features = _make_features_with_phash(["a" * 16])
        assign_screen_groups(features)
        assert all(f._phase_completed == 2 for f in features)


class TestEmptyInput:
    def test_empty_list(self):
        result = assign_screen_groups([])
        assert result == []


class TestPhashDistPrev:
    def test_first_frame_none(self):
        features = _make_features_with_phash(["a" * 16, "a" * 16])
        assign_screen_groups(features)
        assert features[0].phash_dist_prev is None
        assert features[1].phash_dist_prev == 0
