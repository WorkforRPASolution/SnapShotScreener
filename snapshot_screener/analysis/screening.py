"""Module 6: Screening metrics and verdict (FR-11 through FR-14).

Computes click concentration, session CV, LCS-based sequence similarity, and
produces a final verdict string.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from itertools import combinations
from typing import List

from snapshot_screener.models import FrameFeature, ScreeningResult


def _lcs_length(a: list, b: list) -> int:
    """Compute the length of the Longest Common Subsequence using DP (space-optimised)."""
    n = len(b)
    dp = [0] * (n + 1)
    for item in a:
        prev = 0
        for j in range(1, n + 1):
            temp = dp[j]
            dp[j] = prev + 1 if item == b[j - 1] else max(dp[j], dp[j - 1])
            prev = temp
    return dp[n]


def compute_screening(features: List[FrameFeature]) -> ScreeningResult:
    """Compute screening metrics and verdict from *features*.

    Parameters
    ----------
    features:
        FrameFeature list with ``_phase_completed >= 5``.

    Returns
    -------
    A :class:`ScreeningResult` summarising the analysis.
    """
    assert all(f._phase_completed >= 5 for f in features), (
        "All features must have completed phase 5 (representative selection)"
    )

    total = len(features)

    # --- FR-11: Click concentration ---
    click_concentration, click_concentration_level = _click_concentration(features, total)

    # --- FR-12: Session CV ---
    session_cv, session_cv_level = _session_cv(features)

    # --- FR-13: LCS Similarity ---
    sequence_similarity, sequence_similarity_level = _sequence_similarity(features)

    # --- FR-14: Verdict ---
    verdict = _verdict(
        click_concentration_level,
        session_cv_level,
        sequence_similarity_level,
    )

    return ScreeningResult(
        click_concentration=click_concentration,
        click_concentration_level=click_concentration_level,
        session_cv=session_cv,
        session_cv_level=session_cv_level,
        sequence_similarity=sequence_similarity,
        sequence_similarity_level=sequence_similarity_level,
        verdict=verdict,
    )


def _click_concentration(
    features: List[FrameFeature], total: int
) -> tuple[float | None, str]:
    if total < 10:
        return None, "insufficient_data"
    clustered = sum(1 for f in features if f.click_cluster_id != -1)
    concentration = clustered / total
    if concentration > 0.7:
        level = "high"
    elif concentration >= 0.4:
        level = "medium"
    else:
        level = "low"
    return concentration, level


def _session_cv(features: List[FrameFeature]) -> tuple[float | None, str]:
    session_counts: dict[str, int] = defaultdict(int)
    for f in features:
        session_counts[f.session_id] += 1

    # Filter sessions with >= 3 clicks
    valid_counts = [c for c in session_counts.values() if c >= 3]

    if len(valid_counts) < 2:
        return None, "insufficient_data"

    mean_val = statistics.mean(valid_counts)
    std_val = statistics.stdev(valid_counts)  # ddof=1 by default
    cv = std_val / mean_val

    if cv < 0.3:
        level = "high"
    elif cv <= 1.0:
        level = "medium"
    else:
        level = "low"
    return cv, level


def _sequence_similarity(features: List[FrameFeature]) -> tuple[float | None, str]:
    # Build screen_group_id sequence per session
    session_seqs: dict[str, list[str | None]] = defaultdict(list)
    for f in features:
        session_seqs[f.session_id].append(f.screen_group_id)

    session_ids = list(session_seqs.keys())
    if len(session_ids) < 2:
        return None, "insufficient_data"

    _MAX_PAIRS = 200
    all_pairs = list(combinations(session_ids, 2))
    if len(all_pairs) > _MAX_PAIRS:
        import random
        all_pairs = random.Random(42).sample(all_pairs, _MAX_PAIRS)

    similarities: list[float] = []
    for s1, s2 in all_pairs:
        seq_a = session_seqs[s1]
        seq_b = session_seqs[s2]
        max_len = max(len(seq_a), len(seq_b))
        if max_len == 0:
            similarities.append(0.0)
        else:
            lcs_len = _lcs_length(seq_a, seq_b)
            similarities.append(lcs_len / max_len)

    mean_sim = statistics.mean(similarities)

    if mean_sim > 0.7:
        level = "high"
    elif mean_sim >= 0.5:
        level = "medium"
    else:
        level = "low"
    return mean_sim, level


def _verdict(
    click_level: str,
    cv_level: str,
    seq_level: str,
) -> str:
    """FN-minimisation verdict (FR-14)."""
    active = [
        lvl
        for lvl in [click_level, cv_level, seq_level]
        if lvl != "insufficient_data"
    ]

    if not active:
        return "중간"

    high_count = sum(1 for lvl in active if lvl == "high")
    if high_count >= 2:
        return "높음"
    if all(lvl == "low" for lvl in active):
        return "낮음"
    return "중간"
