"""Pipeline orchestration for SnapshotScreener.

Orchestrates the full 5-phase analysis pipeline:

1. Metadata collection (filenames from Cassandra)
2. pHash collection (image hashing with cache)
3. Analysis (session, screen group, clustering, transition, selection, screening)
4. Report image collection (representative frame images)
5. Report generation (HTML output)
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from snapshot_screener.i18n import t
from snapshot_screener.analysis import (
    assign_screen_groups,
    cluster_clicks,
    compute_screening,
    detect_transitions,
    run_sensitivity_sweep,
    select_representatives,
    separate_sessions,
)
from snapshot_screener.collect.metadata import collect_metadata
from snapshot_screener.collect.phash import collect_phash
from snapshot_screener.db.cache import PhashCache
from snapshot_screener.models import AnalysisResult
from snapshot_screener.report.image_collector import collect_report_images
from snapshot_screener.report.renderer import render_report
from snapshot_screener.report.summary_renderer import render_summary
from snapshot_screener.utils.progress import get_logger, setup_logging

if TYPE_CHECKING:
    from snapshot_screener.config import ScreenerConfig
    from snapshot_screener.db.cassandra_client import CassandraClient

logger = get_logger(__name__)


def run_pipeline(config: "ScreenerConfig") -> None:
    """Orchestrate the full 5-phase pipeline for all equipment IDs.

    Parameters
    ----------
    config:
        Frozen screener configuration.
    """
    setup_logging(config.verbose)

    # Runtime import to avoid hard dependency on cassandra-driver at module level
    from snapshot_screener.db.cassandra_client import CassandraClient

    results: List[AnalysisResult] = []

    with CassandraClient(config) as client:
        for eqpid in config.eqpids:
            try:
                result = run_single_equipment(client, eqpid, config)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(t("log.equipment_failed", config.lang).format(eqpid=eqpid, error=e))
                continue

    # Multi-equipment summary
    if len(results) > 1:
        render_summary(results, config)


def run_single_equipment(
    client: "CassandraClient",
    eqpid: str,
    config: "ScreenerConfig",
) -> Optional[AnalysisResult]:
    """Run the full analysis pipeline for a single equipment ID.

    Parameters
    ----------
    client:
        Connected Cassandra client.
    eqpid:
        Equipment identifier.
    config:
        Screener configuration.

    Returns
    -------
    AnalysisResult or None
        Analysis result, or None if no data found.
    """
    # Phase 1: Metadata collection
    logger.info(t("log.phase1", config.lang).format(eqpid=eqpid))
    metas = collect_metadata(client, eqpid, config)
    if not metas:
        logger.warning(t("log.no_data", config.lang).format(eqpid=eqpid))
        return None

    # Phase 2: pHash collection
    logger.info(t("log.phase2", config.lang).format(eqpid=eqpid))
    with PhashCache(config.cache_dir) as cache:
        if config.invalidate_cache:
            cache.invalidate(eqpid)
        features = collect_phash(client, cache, metas, config)

    if not features:
        logger.warning(t("log.no_phash", config.lang).format(eqpid=eqpid))
        return None

    # Phase 3: Analysis
    logger.info(t("log.phase3", config.lang).format(eqpid=eqpid))
    separate_sessions(features, config.session_gap_ms, eqpid)
    assign_screen_groups(features, config.phash_similar_threshold)
    cluster_clicks(
        features,
        config.dbscan_eps,
        config.dbscan_min_samples,
        config.screen_width,
        config.screen_height,
    )
    detect_transitions(
        features,
        config.phash_transition_threshold,
        config.delta_spike_ms,
        config.phash_similar_threshold,
    )
    select_representatives(features, config.selector)
    screening = compute_screening(features)

    sensitivity = None
    if config.sensitivity_sweep:
        sensitivity = run_sensitivity_sweep(features)

    # Build AnalysisResult
    representative_features = [f for f in features if f.is_representative]
    sessions = set(f.session_id for f in features)
    screen_groups = set(
        f.screen_group_id for f in features if f.screen_group_id
    )

    config_summary = {
        "phash_similar_threshold": config.phash_similar_threshold,
        "phash_transition_threshold": config.phash_transition_threshold,
        "session_gap_ms": config.session_gap_ms,
        "dbscan_eps": config.dbscan_eps,
        "selector": config.selector,
        "sensitivity_sweep": config.sensitivity_sweep,
    }

    result = AnalysisResult(
        eqpid=eqpid,
        config_summary=config_summary,
        all_features=features,
        representative_features=representative_features,
        screening=screening,
        sensitivity=sensitivity,
        total_clicks=len(features),
        analysis_days=(config.date_to - config.date_from).days + 1,
        session_count=len(sessions),
        screen_group_count=len(screen_groups),
        representative_count=len(representative_features),
        reduction_rate=(
            1 - len(representative_features) / len(features) if features else 0
        ),
    )

    # Phase 4: Report image collection
    logger.info(t("log.phase4", config.lang).format(eqpid=eqpid, count=len(representative_features)))
    collected = collect_report_images(client, representative_features, eqpid, config)

    # Phase 5: Report generation + original image export + JSON export
    logger.info(t("log.phase5", config.lang).format(eqpid=eqpid))

    output_dir = Path(config.output_dir)
    date_from_str = str(config.date_from).replace("-", "")
    date_to_str = str(config.date_to).replace("-", "")
    base_name = f"SnapshotScreener_{eqpid}_{date_from_str}-{date_to_str}"

    # 5a: HTML report (thumbnails)
    report_path = render_report(result, collected.thumbnails, config)
    logger.info(t("log.html_report", config.lang).format(path=report_path))

    # 5b: Save original images to frames/ directory
    frames_dir = output_dir / base_name / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    saved_count = 0
    for feat in representative_features:
        raw_b64 = collected.originals.get(feat.fname)
        if raw_b64 is None:
            continue
        # Save as original PNG
        img_bytes = base64.b64decode(raw_b64)
        img_path = frames_dir / feat.fname
        img_path.write_bytes(img_bytes)
        saved_count += 1
    logger.info(t("log.original_images", config.lang).format(path=frames_dir, count=saved_count))

    # 5c: JSON export (machine-readable analysis result)
    json_path = output_dir / f"{base_name}.json"
    json_data = _build_json_export(result, config)
    json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(t("log.json_export", config.lang).format(path=json_path))

    return result


def _build_json_export(result: AnalysisResult, config: "ScreenerConfig") -> Dict[str, Any]:
    """Build a machine-readable JSON export of the analysis result."""
    s = result.screening

    def _native(v: Any) -> Any:
        """Convert numpy types to native Python for JSON serialization."""
        if hasattr(v, 'item'):
            return v.item()
        return v

    representative_frames = []
    for f in result.representative_features:
        representative_frames.append({
            "fname": f.fname,
            "timestamp_ms": f.timestamp_ms,
            "x": _native(f.x),
            "y": _native(f.y),
            "session_id": f.session_id,
            "screen_group_id": f.screen_group_id,
            "click_cluster_id": _native(f.click_cluster_id),
            "is_transition_point": bool(f.is_transition_point),
            "candidate_score": _native(f.candidate_score),
            "candidate_flags": list(f.candidate_flags),
        })

    return {
        "version": "1.1",
        "eqpid": result.eqpid,
        "date_from": str(config.date_from),
        "date_to": str(config.date_to),
        "summary": {
            "total_clicks": result.total_clicks,
            "analysis_days": result.analysis_days,
            "session_count": result.session_count,
            "screen_group_count": result.screen_group_count,
            "representative_count": result.representative_count,
            "reduction_rate": round(result.reduction_rate, 4),
        },
        "screening": {
            "click_concentration": _native(s.click_concentration),
            "click_concentration_level": s.click_concentration_level,
            "session_cv": _native(s.session_cv),
            "session_cv_level": s.session_cv_level,
            "sequence_similarity": _native(s.sequence_similarity),
            "sequence_similarity_level": s.sequence_similarity_level,
            "verdict": s.verdict,
        },
        "sensitivity": {
            "threshold_values": result.sensitivity.threshold_values,
            "min_jaccard": result.sensitivity.min_jaccard,
            "sensitivity_verdict": result.sensitivity.sensitivity_verdict,
            "jaccard_pairs": [
                {"t1": p[0], "t2": p[1], "jaccard": round(p[2], 4)}
                for p in result.sensitivity.jaccard_pairs
            ],
        } if result.sensitivity else None,
        "config": result.config_summary,
        "representative_frames": representative_frames,
    }
