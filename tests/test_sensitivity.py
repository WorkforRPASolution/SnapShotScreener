"""Tests for analysis.sensitivity — pHash threshold sensitivity sweep (FR-15~17)."""
from __future__ import annotations

import pytest

from snapshot_screener.models import FrameFeature
from snapshot_screener.analysis.sensitivity import run_sensitivity_sweep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pipeline_features(
    phashes: list[str | None],
    n_sessions: int = 1,
    session_gap_ms: int = 900_000,
) -> list[FrameFeature]:
    """Create features that have been through phases 1-5.

    All frames get the same phash within each "session block", which means
    any threshold should produce the same screen groups -> stable output.
    """
    from snapshot_screener.analysis.session import separate_sessions
    from snapshot_screener.analysis.screen_group import assign_screen_groups
    from snapshot_screener.analysis.clustering import cluster_clicks
    from snapshot_screener.analysis.transition import detect_transitions
    from snapshot_screener.analysis.selector import select_representatives

    features: list[FrameFeature] = []
    ts = 0
    for i, ph in enumerate(phashes):
        f = FrameFeature(
            eqpid="EQ",
            fname=f"frame_{i}.png",
            timestamp_ms=ts,
            x=100 + (i % 5) * 10,
            y=200 + (i % 3) * 10,
            phash=ph,
        )
        features.append(f)
        ts += 5000

    separate_sessions(features, eqpid="EQ")
    assign_screen_groups(features)
    cluster_clicks(features)
    detect_transitions(features)
    select_representatives(features)
    return features


def _make_stable_features() -> list[FrameFeature]:
    """Features where changing phash threshold from 3-6 doesn't change groups.

    All frames use the same phash -> any threshold produces 1 group -> same reps.
    """
    same_hash = "aaaaaaaaaaaaaaaa"
    return _make_pipeline_features([same_hash] * 15)


def _make_unstable_features() -> list[FrameFeature]:
    """Features where different thresholds produce very different groups.

    Use hashes at exact distances so that small threshold changes swap groupings.
    """
    # Hash pairs at specific distances:
    # dist 0: identical
    # dist ~4: at threshold boundary
    import random
    rng = random.Random(42)

    def _make_hash_at_distance(base_bits: list[int], dist: int) -> str:
        bits = list(base_bits)
        positions = rng.sample(range(64), dist)
        for p in positions:
            bits[p] = 1 - bits[p]
        hex_chars = []
        for j in range(0, 64, 4):
            nibble = bits[j:j + 4]
            val = sum(b << (3 - k) for k, b in enumerate(nibble))
            hex_chars.append(format(val, "x"))
        return "".join(hex_chars)

    base_bits = [rng.randint(0, 1) for _ in range(64)]
    base_hash = _make_hash_at_distance(base_bits, 0)

    # Create hashes at distances 3, 4, 5, 6 from base
    phashes = []
    for _ in range(4):
        phashes.append(base_hash)
    for dist in [3, 4, 5, 6]:
        h = _make_hash_at_distance(base_bits, dist)
        for _ in range(3):
            phashes.append(h)

    return _make_pipeline_features(phashes)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStableData:
    def test_stable_verdict(self):
        """Identical phashes → same reps at all thresholds → 둔감."""
        features = _make_stable_features()
        result = run_sensitivity_sweep(features, thresholds=[3, 4, 5, 6])

        assert result.sensitivity_verdict == "insensitive"
        assert result.min_jaccard > 0.8

    def test_threshold_values_stored(self):
        features = _make_stable_features()
        result = run_sensitivity_sweep(features, thresholds=[3, 4, 5, 6])
        assert result.threshold_values == [3, 4, 5, 6]


class TestUnstableData:
    def test_unstable_verdict(self):
        """Hashes at boundary distances → different groupings → 민감."""
        # Create hashes that are exactly at distance boundaries
        # Threshold 3 would split what threshold 6 would merge
        import random
        rng = random.Random(99)

        base = [rng.randint(0, 1) for _ in range(64)]

        def bits_to_hash(bits):
            hex_chars = []
            for j in range(0, 64, 4):
                nibble = bits[j:j + 4]
                val = sum(b << (3 - k) for k, b in enumerate(nibble))
                hex_chars.append(format(val, "x"))
            return "".join(hex_chars)

        def flip_n(base_bits, n, seed):
            r = random.Random(seed)
            bits = list(base_bits)
            for p in r.sample(range(64), n):
                bits[p] = 1 - bits[p]
            return bits

        # 20 frames with hashes at various distances from base
        phashes = []
        base_hash = bits_to_hash(base)
        for i in range(5):
            phashes.append(base_hash)
        # Hashes at distance 4 from base (threshold boundary)
        h4 = bits_to_hash(flip_n(base, 4, 10))
        for i in range(5):
            phashes.append(h4)
        # Very different hashes (distance > 10)
        h_far = bits_to_hash(flip_n(base, 20, 20))
        for i in range(5):
            phashes.append(h_far)
        # Another set at distance 3
        h3 = bits_to_hash(flip_n(base, 3, 30))
        for i in range(5):
            phashes.append(h3)

        features = _make_pipeline_features(phashes)
        result = run_sensitivity_sweep(features, thresholds=[2, 3, 4, 7])

        # With thresholds at [2,3,4,7], groupings should change significantly
        # At threshold 2: base, h3, h4, h_far are all separate groups
        # At threshold 7: base+h3+h4 merge, h_far separate
        assert result.sensitivity_verdict in ("sensitive", "moderate")


class TestAllPairsPresent:
    def test_six_pairs_for_four_thresholds(self):
        """C(4,2) = 6 pairs should be in jaccard_pairs."""
        features = _make_stable_features()
        result = run_sensitivity_sweep(features, thresholds=[3, 4, 5, 6])

        assert len(result.jaccard_pairs) == 6
        pair_keys = {(t1, t2) for t1, t2, _ in result.jaccard_pairs}
        assert pair_keys == {(3, 4), (3, 5), (3, 6), (4, 5), (4, 6), (5, 6)}

    def test_three_pairs_for_three_thresholds(self):
        """C(3,2) = 3 pairs."""
        features = _make_stable_features()
        result = run_sensitivity_sweep(features, thresholds=[3, 5, 7])
        assert len(result.jaccard_pairs) == 3


class TestFrameCounts:
    def test_frame_counts_populated(self):
        features = _make_stable_features()
        result = run_sensitivity_sweep(features, thresholds=[3, 4, 5, 6])

        for thr in [3, 4, 5, 6]:
            assert thr in result.frame_counts
            assert result.frame_counts[thr] >= 0


class TestOriginalUnmodified:
    def test_original_features_unchanged(self):
        """The original feature list should not be modified by the sweep."""
        features = _make_stable_features()

        # Record original state
        original_groups = [f.screen_group_id for f in features]
        original_reps = [f.is_representative for f in features]

        run_sensitivity_sweep(features, thresholds=[3, 4, 5, 6])

        # Verify unchanged
        assert [f.screen_group_id for f in features] == original_groups
        assert [f.is_representative for f in features] == original_reps
