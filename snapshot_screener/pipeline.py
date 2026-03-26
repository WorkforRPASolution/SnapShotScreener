"""Pipeline orchestration for SnapshotScreener.

Orchestrates the full 5-phase analysis pipeline:

1. Metadata collection (filenames from Cassandra)
2. pHash collection (image hashing with cache)
3. Analysis (session, screen group, clustering, transition, selection, screening)
4. Report image collection (representative frame images)
5. Report generation (HTML output)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

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
                logger.error(f"장비 {eqpid} 분석 실패: {e}")
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
    logger.info(f"[Phase 1] {eqpid} — 메타데이터 수집")
    metas = collect_metadata(client, eqpid, config)
    if not metas:
        logger.warning(f"{eqpid}: 데이터 없음")
        return None

    # Phase 2: pHash collection
    logger.info(f"[Phase 2] {eqpid} — pHash 수집 (캐시 우선)")
    with PhashCache(config.cache_dir) as cache:
        if config.invalidate_cache:
            cache.invalidate(eqpid)
        features = collect_phash(client, cache, metas, config)

    if not features:
        logger.warning(f"{eqpid}: pHash 수집 결과 없음")
        return None

    # Phase 3: Analysis
    logger.info(f"[Phase 3] {eqpid} — 분석")
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
    logger.info(
        f"[Phase 4] {eqpid} — 리포트 이미지 수집 ({len(representative_features)}장)"
    )
    images = collect_report_images(client, representative_features, eqpid, config)

    # Phase 5: Report generation
    logger.info(f"[Phase 5] {eqpid} — 리포트 생성")
    report_path = render_report(result, images, config)
    logger.info(f"리포트 생성 완료: {report_path}")

    return result
