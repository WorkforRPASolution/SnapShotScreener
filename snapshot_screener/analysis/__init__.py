"""Analysis engine for SnapshotScreener.

Provides 7 pipeline modules that operate on ``List[FrameFeature]`` with
in-place mutation, each advancing ``_phase_completed``.
"""
from snapshot_screener.analysis.session import separate_sessions
from snapshot_screener.analysis.screen_group import assign_screen_groups
from snapshot_screener.analysis.clustering import cluster_clicks
from snapshot_screener.analysis.transition import detect_transitions
from snapshot_screener.analysis.selector import select_representatives
from snapshot_screener.analysis.screening import compute_screening
from snapshot_screener.analysis.sensitivity import run_sensitivity_sweep

__all__ = [
    "separate_sessions",
    "assign_screen_groups",
    "cluster_clicks",
    "detect_transitions",
    "select_representatives",
    "compute_screening",
    "run_sensitivity_sweep",
]
