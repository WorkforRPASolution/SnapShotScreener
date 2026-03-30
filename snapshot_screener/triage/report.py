"""Triage report generation (CSV + JSON + HTML)."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Tuple

from jinja2 import Environment, FileSystemLoader, PackageLoader

from snapshot_screener.i18n import get_labels, t
from snapshot_screener.triage.models import (
    TriageEquipmentResult,
    TriageModelSummary,
    TriageProcessSummary,
    TriageReport,
)
from snapshot_screener.utils.progress import get_logger

if TYPE_CHECKING:
    from snapshot_screener.config import TriageConfig

logger = get_logger(__name__)


def build_triage_report(
    results: List[TriageEquipmentResult],
    config: "TriageConfig",
    elapsed_s: float,
) -> TriageReport:
    """Aggregate individual results into a full triage report and write outputs."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    # Aggregate counts
    high = sum(1 for r in results if r.verdict == "high" and not r.error)
    medium = sum(1 for r in results if r.verdict == "medium" and not r.error)
    low = sum(1 for r in results if r.verdict == "low" and not r.error)
    errors = sum(1 for r in results if r.error)

    # Build hierarchical groups: Process → Model → Equipment
    proc_model_map: Dict[str, Dict[str, List[TriageEquipmentResult]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in results:
        proc_model_map[r.process][r.model].append(r)

    processes: List[TriageProcessSummary] = []
    for process in sorted(proc_model_map):
        model_map = proc_model_map[process]
        model_summaries: List[TriageModelSummary] = []
        for model in sorted(model_map):
            members = model_map[model]
            model_summaries.append(TriageModelSummary(
                model=model,
                equipment_count=len(members),
                high_count=sum(1 for r in members if r.verdict == "high" and not r.error),
                medium_count=sum(1 for r in members if r.verdict == "medium" and not r.error),
                low_count=sum(1 for r in members if r.verdict == "low" and not r.error),
                error_count=sum(1 for r in members if r.error),
                results=members,
            ))
        processes.append(TriageProcessSummary(
            process=process,
            equipment_count=sum(m.equipment_count for m in model_summaries),
            high_count=sum(m.high_count for m in model_summaries),
            medium_count=sum(m.medium_count for m in model_summaries),
            low_count=sum(m.low_count for m in model_summaries),
            error_count=sum(m.error_count for m in model_summaries),
            models=model_summaries,
        ))

    report = TriageReport(
        date_from=str(config.date_from),
        date_to=str(config.date_to),
        generated_at=now,
        scan_duration_s=round(elapsed_s, 1),
        total_equipment=len(results),
        high_count=high,
        medium_count=medium,
        low_count=low,
        error_count=errors,
        processes=processes,
        all_results=results,
    )

    # Write outputs
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    date_from_str = str(config.date_from).replace("-", "")
    date_to_str = str(config.date_to).replace("-", "")
    base = f"TriageReport_{date_from_str}-{date_to_str}"

    lang = config.lang
    _write_csv(report, output_dir / f"{base}.csv", lang)
    _write_json(report, output_dir / f"{base}.json", lang)
    _write_html(report, output_dir / f"{base}.html", config)

    return report


def _write_csv(report: TriageReport, path: Path, lang: str = "ko") -> None:
    """Write flat CSV output."""
    fieldnames = [
        "process", "model", "eqpid",
        "total_clicks", "session_count", "data_days",
        "click_concentration", "session_cv", "verdict", "error",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in report.all_results:
            writer.writerow({
                "process": r.process,
                "model": r.model,
                "eqpid": r.eqpid,
                "total_clicks": r.total_clicks,
                "session_count": r.session_count,
                "data_days": r.data_days,
                "click_concentration": (
                    f"{r.click_concentration:.4f}"
                    if r.click_concentration is not None else ""
                ),
                "session_cv": (
                    f"{r.session_cv:.4f}"
                    if r.session_cv is not None else ""
                ),
                "verdict": r.verdict,
                "error": r.error or "",
            })
    logger.info(t("triage.log.csv_report", lang).format(path=path))


def _write_json(report: TriageReport, path: Path, lang: str = "ko") -> None:
    """Write structured JSON output."""

    def _result_dict(r: TriageEquipmentResult) -> dict:
        return {
            "process": r.process,
            "model": r.model,
            "eqpid": r.eqpid,
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

    data = {
        "version": "1.0",
        "mode": "triage",
        "date_from": report.date_from,
        "date_to": report.date_to,
        "generated_at": report.generated_at,
        "scan_duration_s": report.scan_duration_s,
        "total_equipment": report.total_equipment,
        "summary": {
            "high_count": report.high_count,
            "medium_count": report.medium_count,
            "low_count": report.low_count,
            "error_count": report.error_count,
        },
        "processes": [
            {
                "process": p.process,
                "equipment_count": p.equipment_count,
                "high_count": p.high_count,
                "medium_count": p.medium_count,
                "low_count": p.low_count,
                "error_count": p.error_count,
                "models": [
                    {
                        "model": m.model,
                        "equipment_count": m.equipment_count,
                        "high_count": m.high_count,
                        "medium_count": m.medium_count,
                        "low_count": m.low_count,
                        "error_count": m.error_count,
                    }
                    for m in p.models
                ],
            }
            for p in report.processes
        ],
        "equipment": [_result_dict(r) for r in report.all_results],
    }

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(t("triage.log.json_report", lang).format(path=path))


def _write_html(
    report: TriageReport, path: Path, config: "TriageConfig"
) -> None:
    """Write self-contained HTML report."""
    try:
        env = Environment(
            loader=PackageLoader(
                "snapshot_screener", "report/templates"
            ),
            autoescape=True,
        )
    except Exception:
        env = Environment(
            loader=FileSystemLoader(
                str(Path(__file__).resolve().parent.parent / "report" / "templates")
            ),
            autoescape=True,
        )

    labels = get_labels(config.lang)
    template = env.get_template("triage.html.j2")
    html = template.render(report=report, config=config, L=labels)
    path.write_text(html, encoding="utf-8")
    logger.info(t("triage.log.html_report", config.lang).format(path=path))
