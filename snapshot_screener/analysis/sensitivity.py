"""Module 7: pHash threshold sensitivity sweep (FR-15 through FR-17).

Reruns screen-group assignment and representative selection at multiple
pHash thresholds to measure how sensitive the output is to the threshold
choice.
"""
from __future__ import annotations

from itertools import combinations
from typing import List

from snapshot_screener.models import FrameFeature, SensitivityResult


def _copy_features(features: List[FrameFeature]) -> List[FrameFeature]:
    """Create a deep copy of features list.

    FrameFeature uses ``slots=True`` which can complicate ``copy.deepcopy``.
    We explicitly construct new objects instead.
    """
    copies: list[FrameFeature] = []
    for f in features:
        new_f = FrameFeature(
            eqpid=f.eqpid,
            fname=f.fname,
            timestamp_ms=f.timestamp_ms,
            x=f.x,
            y=f.y,
            x_norm=f.x_norm,
            y_norm=f.y_norm,
            session_id=f.session_id,
            seq=f.seq,
            delta_ms=f.delta_ms,
            phash=f.phash,
            phash_dist_prev=f.phash_dist_prev,
            screen_group_id=f.screen_group_id,
            click_cluster_id=f.click_cluster_id,
            is_session_start=f.is_session_start,
            is_session_end=f.is_session_end,
            is_new_screen=f.is_new_screen,
            is_transition_point=f.is_transition_point,
            is_new_click_cluster=f.is_new_click_cluster,
            candidate_score=f.candidate_score,
            candidate_flags=list(f.candidate_flags),
            is_representative=f.is_representative,
        )
        new_f._phase_completed = f._phase_completed
        copies.append(new_f)
    return copies


def run_sensitivity_sweep(
    features: List[FrameFeature],
    thresholds: List[int] | None = None,
) -> SensitivityResult:
    """Run a pHash-threshold sensitivity sweep.

    For each threshold value, re-runs screen-group assignment and simple
    representative selection on a **copy** of *features*, then computes
    pairwise Jaccard similarity of the representative frame sets.

    Parameters
    ----------
    features:
        FrameFeature list with ``_phase_completed >= 5``.
    thresholds:
        pHash distance thresholds to evaluate.  Defaults to ``[3, 4, 5, 6]``.

    Returns
    -------
    A :class:`SensitivityResult` summarising sensitivity.
    """
    # Lazy imports to avoid circular dependencies at module level
    from snapshot_screener.analysis.screen_group import assign_screen_groups
    from snapshot_screener.analysis.selector import select_representatives

    if thresholds is None:
        thresholds = [3, 4, 5, 6]

    # Collect representative fname sets per threshold
    threshold_fnames: dict[int, set[str]] = {}
    frame_counts: dict[int, int] = {}

    for thr in thresholds:
        working = _copy_features(features)

        # Reset phase to allow re-running phases 2 and 5
        # Phase 1 (session) is already done; we need >=1 for screen_group
        for f in working:
            f._phase_completed = 1
            # Reset fields that will be recomputed
            f.screen_group_id = None
            f.phash_dist_prev = None
            f.is_new_screen = False
            f.is_representative = False
            f.candidate_score = 0.0
            f.candidate_flags = []

        assign_screen_groups(working, phash_similar_threshold=thr)

        # Need phase >=4 for selector; set directly since we skip clustering/transition
        for f in working:
            f._phase_completed = 4

        select_representatives(working, selector="simple")

        rep_fnames = {f.fname for f in working if f.is_representative}
        threshold_fnames[thr] = rep_fnames
        frame_counts[thr] = len(rep_fnames)

    # Compute Jaccard for all pairs
    jaccard_pairs: list[tuple[int, int, float]] = []
    for t1, t2 in combinations(thresholds, 2):
        set_a = threshold_fnames[t1]
        set_b = threshold_fnames[t2]
        union = set_a | set_b
        if len(union) == 0:
            jaccard = 0.0
        else:
            jaccard = len(set_a & set_b) / len(union)
        jaccard_pairs.append((t1, t2, jaccard))

    min_jaccard = min(j for _, _, j in jaccard_pairs) if jaccard_pairs else 0.0

    if min_jaccard > 0.8:
        verdict = "둔감"
    elif min_jaccard >= 0.5:
        verdict = "중간"
    else:
        verdict = "민감"

    return SensitivityResult(
        threshold_values=thresholds,
        frame_counts=frame_counts,
        jaccard_pairs=jaccard_pairs,
        min_jaccard=min_jaccard,
        sensitivity_verdict=verdict,
    )
