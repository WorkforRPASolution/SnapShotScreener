"""Triage-specific screening using 2 signals (no pHash required).

Computes click concentration and session CV from FrameFeature lists
that have completed session separation and DBSCAN clustering, but
have NOT gone through screen group assignment (which requires pHash).
"""
from __future__ import annotations

from typing import List

from snapshot_screener.analysis.screening import (
    click_concentration,
    session_cv,
    verdict as compute_verdict,
)
from snapshot_screener.models import FrameFeature
from snapshot_screener.triage.models import TriageEquipmentResult


def compute_triage_screening(
    features: List[FrameFeature],
    eqpid: str,
    process: str,
    model: str,
    data_days: int,
) -> TriageEquipmentResult:
    """Compute triage screening from 2 available signals.

    Parameters
    ----------
    features:
        FrameFeature list after session separation + DBSCAN clustering.
        Screen group assignment and pHash are NOT required.
    eqpid, process, model:
        Equipment identity for the result record.
    data_days:
        Number of distinct days with data.
    """
    total = len(features)

    cc_val, cc_level = click_concentration(features, total)
    cv_val, cv_level = session_cv(features)

    # Use the existing verdict function with sequence_similarity
    # set to "insufficient_data" (unavailable without pHash).
    vrd = compute_verdict(cc_level, cv_level, "insufficient_data")

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
