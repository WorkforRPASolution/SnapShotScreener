"""Tests for analysis.clustering — click clustering via DBSCAN (FR-08)."""
from __future__ import annotations

import pytest

from snapshot_screener.models import FrameFeature
from snapshot_screener.analysis.clustering import cluster_clicks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_features(
    coords: list[tuple[int, int]],
    phase: int = 2,
) -> list[FrameFeature]:
    """Create FrameFeatures with given (x, y) coordinates."""
    features = []
    for i, (x, y) in enumerate(coords):
        f = FrameFeature(
            eqpid="EQ",
            fname=f"frame_{i}.png",
            timestamp_ms=1000 * i,
            x=x,
            y=y,
        )
        f._phase_completed = phase
        features.append(f)
    return features


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSparseData:
    def test_fewer_than_10_skips_dbscan(self):
        """With < 10 frames, DBSCAN should be skipped; all get cluster -1."""
        features = _make_features([(100, 100), (200, 200), (300, 300)])
        cluster_clicks(features)
        assert all(f.click_cluster_id == -1 for f in features)
        assert all(f.is_new_click_cluster is False for f in features)

    def test_exactly_9_skips(self):
        coords = [(i * 100, i * 100) for i in range(9)]
        features = _make_features(coords)
        cluster_clicks(features)
        assert all(f.click_cluster_id == -1 for f in features)


class TestSingleCluster:
    def test_tight_cluster(self):
        """Points close together should form a single cluster."""
        # 15 points near (960, 540), using large eps
        coords = [(960 + i, 540 + i) for i in range(15)]
        features = _make_features(coords)
        cluster_clicks(features, config_eps=0.1, config_min_samples=2)

        cluster_ids = {f.click_cluster_id for f in features}
        # All should be in the same cluster (not noise)
        non_noise = {c for c in cluster_ids if c != -1}
        assert len(non_noise) == 1


class TestMultipleClusters:
    def test_two_distinct_clusters(self):
        """Two groups of points far apart should form two clusters."""
        cluster_a = [(100, 100)] * 10
        cluster_b = [(1800, 900)] * 10
        features = _make_features(cluster_a + cluster_b)
        cluster_clicks(features, config_eps=0.05, config_min_samples=2)

        ids_a = {features[i].click_cluster_id for i in range(10)}
        ids_b = {features[i].click_cluster_id for i in range(10, 20)}

        # Each group should form a cluster
        assert len(ids_a) == 1
        assert len(ids_b) == 1
        # The two clusters should be different
        assert ids_a != ids_b


class TestNoisePoints:
    def test_outliers_get_minus_one(self):
        """Isolated points should be noise (cluster_id == -1)."""
        # A tight cluster + 2 outliers
        cluster = [(500, 500)] * 10
        outliers = [(0, 0), (1919, 1079)]
        features = _make_features(cluster + outliers)
        cluster_clicks(features, config_eps=0.02, config_min_samples=3)

        # Outlier features should be noise
        assert features[-1].click_cluster_id == -1
        assert features[-2].click_cluster_id == -1


class TestNewClickCluster:
    def test_flag_set_on_change(self):
        """is_new_click_cluster should be True when cluster changes."""
        cluster_a = [(100, 100)] * 10
        cluster_b = [(1800, 900)] * 10
        features = _make_features(cluster_a + cluster_b)
        cluster_clicks(features, config_eps=0.05, config_min_samples=2)

        # First frame has no previous, so is_new_click_cluster == False
        assert features[0].is_new_click_cluster is False
        # Frame 10 is in cluster_b while frame 9 is in cluster_a
        assert features[10].is_new_click_cluster is True


class TestNormalization:
    def test_x_norm_y_norm_set(self):
        features = _make_features([(960, 540)])
        cluster_clicks(features, screen_width=1920, screen_height=1080)
        assert features[0].x_norm == pytest.approx(0.5)
        assert features[0].y_norm == pytest.approx(0.5)


class TestPhaseAssertions:
    def test_entry_assertion_fails(self):
        features = _make_features([(100, 100)], phase=1)
        with pytest.raises(AssertionError):
            cluster_clicks(features)

    def test_phase_set_to_3(self):
        features = _make_features([(100, 100)])
        cluster_clicks(features)
        assert all(f._phase_completed == 3 for f in features)


class TestEmptyInput:
    def test_empty_list(self):
        result = cluster_clicks([])
        assert result == []
