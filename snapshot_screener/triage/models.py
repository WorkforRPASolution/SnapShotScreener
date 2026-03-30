"""Data models for triage mode results."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TriageEquipmentResult:
    """Screening result for a single equipment in triage mode."""

    eqpid: str
    process: str
    model: str
    total_clicks: int = 0
    session_count: int = 0
    data_days: int = 0
    click_concentration: Optional[float] = None
    click_concentration_level: str = "insufficient_data"
    session_cv: Optional[float] = None
    session_cv_level: str = "insufficient_data"
    verdict: str = "medium"
    error: Optional[str] = None


@dataclass
class TriageGroupSummary:
    """Aggregated summary for a (process, model) group."""

    process: str
    model: str
    equipment_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    error_count: int = 0
    results: List[TriageEquipmentResult] = field(default_factory=list)


@dataclass
class TriageReport:
    """Complete triage report covering all equipment."""

    date_from: str
    date_to: str
    generated_at: str
    scan_duration_s: float
    total_equipment: int
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    error_count: int = 0
    groups: List[TriageGroupSummary] = field(default_factory=list)
    all_results: List[TriageEquipmentResult] = field(default_factory=list)
