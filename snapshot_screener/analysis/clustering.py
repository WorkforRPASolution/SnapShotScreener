"""Module 3: Click clustering via DBSCAN (FR-08).

Clusters click coordinates using DBSCAN so that spatially related clicks can
be identified.
"""
from __future__ import annotations

from typing import List

import numpy as np
from sklearn.cluster import DBSCAN

from snapshot_screener.models import FrameFeature


def cluster_clicks(
    features: List[FrameFeature],
    config_eps: float = 0.03,
    config_min_samples: int = 2,
    screen_width: int = 1920,
    screen_height: int = 1080,
) -> List[FrameFeature]:
    """Cluster click coordinates with DBSCAN and assign IDs (in-place).

    Parameters
    ----------
    features:
        FrameFeature list with ``_phase_completed >= 2``.
    config_eps:
        DBSCAN epsilon (in normalised coordinate space).
    config_min_samples:
        DBSCAN min_samples.
    screen_width, screen_height:
        Used to normalise raw pixel coordinates to [0, 1].

    Returns
    -------
    The same *features* list, mutated in place.
    """
    if not features:
        return features

    assert all(f._phase_completed >= 2 for f in features), (
        "All features must have completed phase 2 (screen group assignment)"
    )

    # Normalise coordinates
    for f in features:
        f.x_norm = f.x / screen_width
        f.y_norm = f.y / screen_height

    if len(features) < 10:
        for f in features:
            f.click_cluster_id = -1
            f.is_new_click_cluster = False
            f._phase_completed = 3
        return features

    coords = np.array([[f.x_norm, f.y_norm] for f in features])
    db = DBSCAN(eps=config_eps, min_samples=config_min_samples).fit(coords)
    labels = db.labels_

    prev_cluster: int | None = None
    for i, f in enumerate(features):
        f.click_cluster_id = int(labels[i])
        f.is_new_click_cluster = (f.click_cluster_id != prev_cluster) if prev_cluster is not None else False
        prev_cluster = f.click_cluster_id

    for f in features:
        f._phase_completed = 3

    return features
