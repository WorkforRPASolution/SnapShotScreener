"""Module 4: Transition detection (FR-09).

Identifies frames that represent meaningful transitions between screens or
interaction states using a compound condition.
"""
from __future__ import annotations

from typing import List

from snapshot_screener.models import FrameFeature


def detect_transitions(
    features: List[FrameFeature],
    phash_transition_threshold: int = 8,
    delta_spike_ms: int = 30_000,
    phash_similar_threshold: int = 4,
) -> List[FrameFeature]:
    """Mark transition points on *features* (in-place).

    The compound condition is:

    * ``is_new_screen``  **OR**
    * phash distance to previous frame > *phash_transition_threshold*  **OR**
    * ``is_new_click_cluster``  **OR**
    * large time gap (``delta_ms > delta_spike_ms``) **AND** the frame also
      shows visual change (``is_new_screen`` or phash dist > *phash_similar_threshold*).

    Parameters
    ----------
    features:
        FrameFeature list with ``_phase_completed >= 3``.

    Returns
    -------
    The same *features* list, mutated in place.
    """
    if not features:
        return features

    assert all(f._phase_completed >= 3 for f in features), (
        "All features must have completed phase 3 (click clustering)"
    )

    for frame in features:
        is_transition = (
            frame.is_new_screen
            or (
                frame.phash_dist_prev is not None
                and frame.phash_dist_prev > phash_transition_threshold
            )
            or frame.is_new_click_cluster
            or (
                frame.delta_ms is not None
                and frame.delta_ms > delta_spike_ms
                and (
                    frame.is_new_screen
                    or (
                        frame.phash_dist_prev is not None
                        and frame.phash_dist_prev > phash_similar_threshold
                    )
                )
            )
        )
        frame.is_transition_point = is_transition

    for f in features:
        f._phase_completed = 4

    return features
