"""Triage-specific screening using session CV as primary signal.

Click concentration is reported but excluded from verdict because
fixed-UI equipment shows ~0.99 concentration regardless of
manual vs. automated operation (no discriminative power).

Session CV alone determines the verdict. Thresholds are configurable
via cv_high_threshold / cv_low_threshold in TriageConfig (default 0.3 / 1.0).
"""
from __future__ import annotations

from typing import List

from snapshot_screener.analysis.screening import click_concentration, session_cv
from snapshot_screener.models import FrameFeature
from snapshot_screener.triage.models import TriageEquipmentResult


def _triage_session_cv(
    features: List[FrameFeature],
    cv_high: float = 0.3,
    cv_low: float = 1.0,
) -> tuple[float | None, str]:
    """Session CV with configurable thresholds."""
    import statistics
    from collections import defaultdict

    session_counts: dict[str, int] = defaultdict(int)
    for f in features:
        session_counts[f.session_id] += 1

    valid_counts = [c for c in session_counts.values() if c >= 3]

    if len(valid_counts) < 2:
        return None, "insufficient_data"

    mean_val = statistics.mean(valid_counts)
    std_val = statistics.stdev(valid_counts)
    cv = std_val / mean_val

    if cv < cv_high:
        level = "high"
    elif cv <= cv_low:
        level = "medium"
    else:
        level = "low"
    return cv, level


def _triage_verdict(cv_level: str) -> str:
    """Verdict based on session CV alone.

    Triage is a pre-filter — errs on the side of caution (FN minimisation).
    """
    if cv_level == "insufficient_data":
        return "medium"
    return cv_level


def compute_triage_screening(
    features: List[FrameFeature],
    eqpid: str,
    process: str,
    model: str,
    data_days: int,
    *,
    skip_clustering: bool = False,
    cv_high: float = 0.3,
    cv_low: float = 1.0,
) -> TriageEquipmentResult:
    """Compute triage screening.

    Parameters
    ----------
    features:
        FrameFeature list after session separation.
        DBSCAN clustering is optional (see *skip_clustering*).
    eqpid, process, model:
        Equipment identity for the result record.
    data_days:
        Number of distinct days with data.
    skip_clustering:
        If True, skip click_concentration (set to None).
        Used when click count is too large for DBSCAN.
    cv_high, cv_low:
        Session CV thresholds for verdict level.
    """
    total = len(features)

    # Click concentration — reported only, not used in verdict
    if skip_clustering:
        cc_val, cc_level = None, "skipped"
    else:
        cc_val, cc_level = click_concentration(features, total)

    # Session CV — primary verdict signal
    cv_val, cv_level = _triage_session_cv(features, cv_high, cv_low)

    vrd = _triage_verdict(cv_level)

    session_ids = set(f.session_id for f in features)

    return TriageEquipmentResult(
        eqpid=eqpid,
        process=process,
        model=model,
        total_clicks=total,
        session_count=len(session_ids),
        data_days=data_days,
        click_concentration=cc_val,
        click_concentration_level=cc_level,
        session_cv=cv_val,
        session_cv_level=cv_level,
        verdict=vrd,
    )
