"""Module 2: Screen-group assignment (FR-06, FR-07).

Groups consecutive frames with similar pHash values and performs canonical
remapping so that revisited screens share the same group ID.
"""
from __future__ import annotations

from typing import List

import imagehash

from snapshot_screener.models import FrameFeature


def assign_screen_groups(
    features: List[FrameFeature],
    phash_similar_threshold: int = 4,
) -> List[FrameFeature]:
    """Assign screen group IDs to *features* (in-place).

    Parameters
    ----------
    features:
        FrameFeature list with ``_phase_completed >= 1``.
    phash_similar_threshold:
        Maximum Hamming distance to consider two pHashes as the same screen.

    Returns
    -------
    The same *features* list, mutated in place.
    """
    if not features:
        return features

    assert all(f._phase_completed >= 1 for f in features), (
        "All features must have completed phase 1 (session separation)"
    )

    group_num = 0

    for i, frame in enumerate(features):
        if frame.phash is None:
            # Skip distance calculation; assign unique group
            frame.phash_dist_prev = None
            group_num += 1
            frame.screen_group_id = f"SG_{group_num:04d}"
            frame.is_new_screen = True
            continue

        if i == 0:
            frame.phash_dist_prev = None
        else:
            prev = features[i - 1]
            if prev.phash is None:
                frame.phash_dist_prev = None
            else:
                dist = imagehash.hex_to_hash(frame.phash) - imagehash.hex_to_hash(prev.phash)
                frame.phash_dist_prev = dist

        # Sequential assignment
        if frame.phash_dist_prev is None or frame.phash_dist_prev > phash_similar_threshold:
            group_num += 1
            frame.screen_group_id = f"SG_{group_num:04d}"
            frame.is_new_screen = True
        else:
            frame.screen_group_id = features[i - 1].screen_group_id
            frame.is_new_screen = False

    # Canonical remapping: revisited screens get the same group ID
    canonical: dict[str, tuple[str, imagehash.ImageHash]] = {}  # sg_id -> (sg_id, parsed_hash)
    for frame in features:
        if frame.phash is None:
            continue
        frame_hash = imagehash.hex_to_hash(frame.phash)
        matched = False
        for known_ph_key, (canon_id, known_hash) in canonical.items():
            if frame_hash - known_hash <= phash_similar_threshold:
                frame.screen_group_id = canon_id
                frame.is_new_screen = False  # returning to known screen
                matched = True
                break
        if not matched:
            canonical[frame.phash] = (frame.screen_group_id, frame_hash)

    for f in features:
        f._phase_completed = 2

    return features
