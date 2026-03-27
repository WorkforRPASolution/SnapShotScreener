"""Module 5: Representative frame selection (FR-10).

Picks a subset of frames to represent the full click sequence.  Two strategies
are available: ``simple`` (first-per-group + session boundaries) and
``scored`` (weighted scoring with per-session top-N selection).
"""
from __future__ import annotations

from collections import defaultdict
from typing import List

from snapshot_screener.models import FrameFeature


def select_representatives(
    features: List[FrameFeature],
    selector: str = "simple",
) -> List[FrameFeature]:
    """Select representative frames from *features* (in-place).

    Parameters
    ----------
    features:
        FrameFeature list with ``_phase_completed >= 4``.
    selector:
        ``"simple"`` or ``"scored"``.

    Returns
    -------
    The same *features* list, mutated in place.
    """
    if not features:
        return features

    assert all(f._phase_completed >= 4 for f in features), (
        "All features must have completed phase 4 (transition detection)"
    )

    # Reset selection state
    for f in features:
        f.is_representative = False
        f.candidate_score = 0.0
        f.candidate_flags = []

    if selector == "simple":
        _simple_selector(features)
    elif selector == "scored":
        _scored_selector(features)
    else:
        raise ValueError(f"Unknown selector: {selector!r}")

    for f in features:
        f._phase_completed = 5

    return features


def _simple_selector(features: List[FrameFeature]) -> None:
    """First frame per unique screen_group_id per session + session boundaries, deduped."""
    selected_fnames: set[str] = set()

    # First frame per unique screen_group_id PER SESSION
    session_seen: dict[str, set[str | None]] = defaultdict(set)
    for f in features:
        if f.screen_group_id not in session_seen[f.session_id]:
            session_seen[f.session_id].add(f.screen_group_id)
            selected_fnames.add(f.fname)

    # Session start/end frames
    for f in features:
        if f.is_session_start or f.is_session_end:
            selected_fnames.add(f.fname)

    # Mark representatives and assign flags/scores
    for f in features:
        if f.fname in selected_fnames:
            f.is_representative = True
            flags = []
            if f.is_session_start:
                flags.append("session_start")
            if f.is_session_end:
                flags.append("session_end")
            if f.is_new_screen:
                flags.append("new_screen")
            f.candidate_flags = flags
            f.candidate_score = float(len(flags))


def _scored_selector(features: List[FrameFeature]) -> None:
    """Weighted scoring with per-session top-N selection."""
    # Score all frames
    for f in features:
        score = 0.0
        flags: list[str] = []
        if f.is_session_start:
            score += 3
            flags.append("session_start")
        if f.is_session_end:
            score += 3
            flags.append("session_end")
        if f.is_new_screen:
            score += 4
            flags.append("new_screen")
        if f.is_transition_point:
            score += 3
            flags.append("transition_point")
        if f.is_new_click_cluster:
            score += 2
            flags.append("new_click_cluster")
        f.candidate_score = score
        f.candidate_flags = flags

    # Group by session_id
    session_frames: dict[str, list[FrameFeature]] = defaultdict(list)
    for f in features:
        session_frames[f.session_id].append(f)

    # Count screen groups per session
    for session_id, frames in session_frames.items():
        session_groups = len({f.screen_group_id for f in frames})
        n = max(5, int(session_groups * 0.3))
        # Select top N by score (stable sort preserves timestamp order for ties)
        ranked = sorted(frames, key=lambda f: f.candidate_score, reverse=True)
        for f in ranked[:n]:
            f.is_representative = True
