"""Module 1: Session separation (FR-05).

Splits a time-ordered sequence of FrameFeature objects into sessions based on
a configurable time-gap threshold.
"""
from __future__ import annotations

from typing import List

from snapshot_screener.models import FrameFeature


def separate_sessions(
    features: List[FrameFeature],
    session_gap_ms: int = 900_000,
    eqpid: str = "",
) -> List[FrameFeature]:
    """Assign session IDs and per-session metadata to *features* (in-place).

    Parameters
    ----------
    features:
        FrameFeature list **sorted by timestamp_ms**.
    session_gap_ms:
        If the delta between consecutive frames exceeds this value a new
        session is started.  Default 900 000 ms (15 min).
    eqpid:
        Equipment identifier used as a prefix for session IDs.

    Returns
    -------
    The same *features* list, mutated in place.
    """
    if not features:
        return features

    session_num = 1
    seq = 0
    features[0].session_id = f"{eqpid}_S{session_num:04d}"
    features[0].seq = seq
    features[0].delta_ms = None
    features[0].is_session_start = True
    features[0].is_session_end = False

    for i in range(1, len(features)):
        prev = features[i - 1]
        cur = features[i]

        delta = cur.timestamp_ms - prev.timestamp_ms
        cur.delta_ms = delta

        if delta > session_gap_ms:
            # Close previous session
            prev.is_session_end = True
            # Start new session
            session_num += 1
            assert session_num <= 9999, (
                f"Session count {session_num} exceeds maximum 9999"
            )
            seq = 0
        else:
            seq += 1

        cur.session_id = f"{eqpid}_S{session_num:04d}"
        cur.seq = seq
        cur.is_session_start = (seq == 0)
        cur.is_session_end = False

    # Last frame is always session end
    features[-1].is_session_end = True

    for f in features:
        f._phase_completed = 1

    return features
