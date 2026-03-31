"""Render multi-equipment summary report.

Produces a single HTML page comparing multiple equipment analysis results.
"""
from __future__ import annotations

import csv
import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader

from snapshot_screener import __version__
from snapshot_screener.config import ScreenerConfig
from snapshot_screener.i18n import t, get_labels
from snapshot_screener.models import AnalysisResult
from snapshot_screener.report.renderer import _get_template_dir

logger = logging.getLogger(__name__)


def _verdict_to_class(verdict: str) -> str:
    """Map verdict internal key to CSS class."""
    return {"high": "high", "medium": "medium", "low": "low"}.get(verdict, "medium")


def render_summary(
    results: List[AnalysisResult],
    config: ScreenerConfig,
) -> Path:
    """Render a multi-equipment summary HTML report.

    Parameters
    ----------
    results:
        List of AnalysisResult objects for each equipment.
    config:
        Screener configuration.

    Returns
    -------
    Path
        Path to the generated summary HTML file.
    """
    template_dir = _get_template_dir()
    env = Environment(
        loader=FileSystemLoader(str(template_dir), encoding="utf-8"),
        autoescape=False,
    )
    template = env.get_template("summary.html.j2")

    # Classify verdicts
    high_count = 0
    medium_count = 0
    low_count = 0
    high_eqpids: List[str] = []

    _VERDICT_ORDER = {"high": 0, "medium": 1, "low": 2}
    sorted_results = sorted(results, key=lambda r: _VERDICT_ORDER.get(r.screening.verdict, 1))

    comparison_rows: List[Dict[str, Any]] = []
    for r in sorted_results:
        verdict_class = _verdict_to_class(r.screening.verdict)
        if verdict_class == "high":
            high_count += 1
            high_eqpids.append(r.eqpid)
        elif verdict_class == "medium":
            medium_count += 1
        else:
            low_count += 1

        # Build report link (relative)
        date_from_str = str(config.date_from).replace("-", "")
        date_to_str = str(config.date_to).replace("-", "")
        dir_name = f"{r.screening.verdict}_SnapshotScreener_{r.eqpid}_{date_from_str}-{date_to_str}"
        report_link = f"{dir_name}/{dir_name}.html"

        comparison_rows.append(
            {
                "eqpid": r.eqpid,
                "analysis_days": r.analysis_days,
                "total_clicks": r.total_clicks,
                "click_concentration": r.screening.click_concentration,
                "session_cv": r.screening.session_cv,
                "sequence_similarity": r.screening.sequence_similarity,
                "verdict": t("verdict." + r.screening.verdict, config.lang),
                "verdict_class": verdict_class,
                "report_link": report_link,
            }
        )

    labels = get_labels(config.lang)

    context = {
        "equipment_count": len(results),
        "date_from": str(config.date_from),
        "date_to": str(config.date_to),
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": f"v{__version__}",
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": low_count,
        "high_eqpids": high_eqpids,
        "comparison_rows": comparison_rows,
        "lang": config.lang,
        "labels": labels,
    }

    html = template.render(**context)

    # Write output
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    date_from_str = str(config.date_from).replace("-", "")
    date_to_str = str(config.date_to).replace("-", "")
    filename = f"SnapshotScreener_Summary_{date_from_str}-{date_to_str}.html"
    output_path = output_dir / filename

    output_path.write_text(html, encoding="utf-8")
    logger.info("Summary report written to %s", output_path)

    # Write CSV summary
    csv_path = output_dir / f"SnapshotScreener_Summary_{date_from_str}-{date_to_str}.csv"
    _write_summary_csv(csv_path, sorted_results, config)

    return output_path


def _write_summary_csv(
    path: Path,
    results: List[AnalysisResult],
    config: ScreenerConfig,
) -> None:
    """Write flat CSV summary of all equipment results."""
    fieldnames = [
        "eqpid", "analysis_days", "total_clicks", "sessions",
        "click_concentration", "session_cv", "sequence_similarity", "verdict",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            s = r.screening
            writer.writerow({
                "eqpid": r.eqpid,
                "analysis_days": r.analysis_days,
                "total_clicks": r.total_clicks,
                "sessions": r.session_count,
                "click_concentration": (
                    f"{s.click_concentration:.4f}"
                    if s.click_concentration is not None else ""
                ),
                "session_cv": (
                    f"{s.session_cv:.4f}"
                    if s.session_cv is not None else ""
                ),
                "sequence_similarity": (
                    f"{s.sequence_similarity:.4f}"
                    if s.sequence_similarity is not None else ""
                ),
                "verdict": s.verdict,
            })
    logger.info("Summary CSV written to %s", path)
