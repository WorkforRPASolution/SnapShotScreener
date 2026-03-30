"""Triage pipeline orchestration.

Processes 10,000+ equipment sequentially using the snapshotlist table,
computing lightweight screening signals (click concentration + session CV)
without reading images.

Resilience features:
- JSONL journal for incremental result persistence
- Circuit breaker to abort on sustained Cassandra failures
- SIGINT handler to write partial results on interruption
- ETA-aware progress reporting
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from snapshot_screener.analysis.clustering import cluster_clicks
from snapshot_screener.analysis.session import separate_sessions
from snapshot_screener.i18n import t
from snapshot_screener.models import FrameFeature
from snapshot_screener.triage.collector import (
    collect_triage_metadata,
    count_data_days,
)
from snapshot_screener.triage.csv_loader import EquipmentInfo, load_equipment_csv
from snapshot_screener.triage.models import TriageEquipmentResult, TriageReport
from snapshot_screener.triage.screening import compute_triage_screening
from snapshot_screener.utils.progress import get_logger, setup_logging

if TYPE_CHECKING:
    from snapshot_screener.config import TriageConfig
    from snapshot_screener.db.cassandra_client import CassandraClient

logger = get_logger(__name__)


def _result_to_dict(r: TriageEquipmentResult) -> dict:
    """Serialise a result to a JSON-safe dict for the JSONL journal."""
    return {
        "eqpid": r.eqpid,
        "process": r.process,
        "model": r.model,
        "total_clicks": r.total_clicks,
        "session_count": r.session_count,
        "data_days": r.data_days,
        "click_concentration": r.click_concentration,
        "click_concentration_level": r.click_concentration_level,
        "session_cv": r.session_cv,
        "session_cv_level": r.session_cv_level,
        "verdict": r.verdict,
        "error": r.error,
    }


def _analyze_single_equipment(
    client: "CassandraClient",
    eq: EquipmentInfo,
    config: "TriageConfig",
) -> TriageEquipmentResult:
    """Run triage analysis for a single equipment."""
    # Phase T2: Collect metadata from snapshotlist
    metas = collect_triage_metadata(client, eq.eqpid, config)

    if not metas:
        return TriageEquipmentResult(
            eqpid=eq.eqpid,
            process=eq.process,
            model=eq.model,
            error="no_data",
        )

    data_days = count_data_days(metas)

    # Phase T3: Build FrameFeature (no phash)
    features: List[FrameFeature] = []
    for meta in metas:
        norm_w = config.screen_width
        norm_h = config.screen_height
        features.append(
            FrameFeature(
                eqpid=meta.eqpid,
                fname=meta.fname,
                timestamp_ms=meta.timestamp_ms,
                x=meta.x,
                y=meta.y,
                partition_year=meta.partition_year,
                partition_month=meta.partition_month,
                x_norm=meta.x / norm_w if norm_w else 0.0,
                y_norm=meta.y / norm_h if norm_h else 0.0,
                phash=None,
                _phase_completed=0,
            )
        )

    # Session separation (phase 0 → 1)
    separate_sessions(features, config.session_gap_ms, eq.eqpid)

    # Skip screen_group (needs pHash) — override phase to 2
    for f in features:
        f._phase_completed = 2

    # DBSCAN click clustering (phase 2 → 3)
    cluster_clicks(
        features,
        config.dbscan_eps,
        config.dbscan_min_samples,
        config.screen_width,
        config.screen_height,
    )

    # Triage screening
    return compute_triage_screening(
        features, eq.eqpid, eq.process, eq.model, data_days
    )


def _log_progress(
    lang: str,
    current: int,
    total: int,
    failed: int,
    start_time: float,
) -> None:
    """Log progress with ETA estimation."""
    elapsed = time.monotonic() - start_time
    if current > 0:
        avg = elapsed / current
        eta_s = avg * (total - current)
        eta_min = eta_s / 60
        pct = current / total * 100
        logger.info(
            t("triage.log.progress", lang).format(
                current=current, total=total, pct=pct,
                failed=failed, eta=eta_min,
            )
        )


def run_triage(config: "TriageConfig") -> Optional[TriageReport]:
    """Run the triage pipeline for all equipment in the CSV.

    Returns a :class:`TriageReport` or ``None`` if no results.
    """
    setup_logging(config.verbose)
    lang = config.lang

    from snapshot_screener.db.cassandra_client import CassandraClient

    # T1: Load equipment CSV
    equipment_list = load_equipment_csv(config.csv_path, lang=lang)
    total = len(equipment_list)
    logger.info(t("triage.log.loaded", lang).format(count=total))

    results: List[TriageEquipmentResult] = []
    failed_count = 0
    consecutive_failures = 0
    start_time = time.monotonic()

    # JSONL journal for incremental persistence
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    date_from_str = str(config.date_from).replace("-", "")
    date_to_str = str(config.date_to).replace("-", "")
    journal_path = output_dir / f"triage_{date_from_str}-{date_to_str}.jsonl"

    with CassandraClient(
        config,
        snapshotlist_table=config.db_snapshotlist_table,
    ) as client:
        journal_file = open(journal_path, "w", buffering=1, encoding="utf-8")
        try:
            for idx, eq in enumerate(equipment_list, start=1):
                try:
                    result = _analyze_single_equipment(client, eq, config)
                    consecutive_failures = 0
                except Exception as exc:
                    error_str = f"{type(exc).__name__}: {exc}"
                    logger.warning(
                        t("triage.log.failed", lang).format(
                            eqpid=eq.eqpid, error=error_str,
                        )
                    )
                    result = TriageEquipmentResult(
                        eqpid=eq.eqpid,
                        process=eq.process,
                        model=eq.model,
                        error=error_str,
                    )
                    consecutive_failures += 1

                results.append(result)

                # Write to journal immediately
                journal_file.write(
                    json.dumps(_result_to_dict(result), ensure_ascii=False)
                    + "\n"
                )

                if result.error:
                    failed_count += 1

                # Circuit breaker
                if consecutive_failures >= config.circuit_breaker_threshold:
                    logger.warning(
                        t("triage.log.circuit_breaker", lang).format(
                            count=consecutive_failures,
                        )
                    )
                    if not client.health_check():
                        logger.error(
                            t("triage.log.health_failed", lang).format(
                                idx=idx, total=total, failed=failed_count,
                            )
                        )
                        break
                    # Health check passed — reset and continue
                    logger.info(t("triage.log.health_passed", lang))
                    consecutive_failures = 0

                # Periodic health check
                if (
                    idx % config.health_check_interval == 0
                    and consecutive_failures == 0
                ):
                    client.health_check()

                # Progress reporting
                if idx % 100 == 0 or idx == total:
                    _log_progress(lang, idx, total, failed_count, start_time)

        except KeyboardInterrupt:
            logger.warning(
                t("triage.log.interrupted", lang).format(
                    done=len(results), total=total,
                )
            )
        finally:
            journal_file.close()

    elapsed = time.monotonic() - start_time

    if not results:
        logger.warning(t("triage.log.no_results", lang))
        return None

    # T4: Build report
    from snapshot_screener.triage.report import build_triage_report

    report = build_triage_report(results, config, elapsed)

    logger.info(
        t("triage.log.complete", lang).format(
            count=len(results),
            elapsed=elapsed,
            high=report.high_count,
            medium=report.medium_count,
            low=report.low_count,
            error=report.error_count,
        )
    )

    return report
