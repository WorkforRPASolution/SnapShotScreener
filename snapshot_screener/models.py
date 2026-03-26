"""Core data models for SnapshotScreener."""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any


@dataclass
class SnapshotMeta:
    """Metadata for a single snapshot image."""

    eqpid: str
    fname: str
    timestamp_ms: int
    x: int
    y: int


@dataclass(slots=True)
class FrameFeature:
    """Feature vector for a single frame in the analysis pipeline.

    Fields are populated incrementally across pipeline phases.
    Use ``_phase_completed`` to track which phase last wrote to this object.
    """

    # Identity (required)
    eqpid: str
    fname: str
    timestamp_ms: int
    x: int
    y: int

    # Normalized coords
    x_norm: float = 0.0
    y_norm: float = 0.0

    # Session
    session_id: str = ""
    seq: int = 0
    delta_ms: Optional[int] = None

    # pHash
    phash: Optional[str] = None
    phash_dist_prev: Optional[int] = None

    # Groups
    screen_group_id: Optional[str] = None
    click_cluster_id: Optional[int] = None

    # Flags
    is_session_start: bool = False
    is_session_end: bool = False
    is_new_screen: bool = False
    is_transition_point: bool = False
    is_new_click_cluster: bool = False

    # Selection
    candidate_score: float = 0.0
    candidate_flags: List[str] = field(default_factory=list)
    is_representative: bool = False

    # Phase tracking
    _phase_completed: int = field(default=0, repr=False, compare=False)


@dataclass
class ScreeningResult:
    """Screening metrics and verdict for an equipment ID."""

    click_concentration: Optional[float]
    click_concentration_level: str  # "high"|"medium"|"low"|"insufficient_data"
    session_cv: Optional[float]
    session_cv_level: str
    sequence_similarity: Optional[float]
    sequence_similarity_level: str
    verdict: str


@dataclass
class SensitivityResult:
    """Results from a pHash threshold sensitivity sweep."""

    threshold_values: List[int]
    frame_counts: Dict[int, int]
    jaccard_pairs: List[Tuple[int, int, float]]  # All 6 pairs
    min_jaccard: float
    sensitivity_verdict: str


@dataclass
class AnalysisResult:
    """Complete analysis result for a single equipment ID."""

    eqpid: str
    config_summary: Dict[str, Any]  # No DB credentials
    all_features: List[FrameFeature]
    representative_features: List[FrameFeature]
    screening: ScreeningResult
    sensitivity: Optional[SensitivityResult]
    total_clicks: int
    analysis_days: int
    session_count: int
    screen_group_count: int
    representative_count: int
    reduction_rate: float
