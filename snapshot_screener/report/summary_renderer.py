"""Render multi-equipment summary report.

Produces a single HTML page comparing multiple equipment analysis results.
"""
from __future__ import annotations

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
        loader=FileSystemLoader(str(template_dir)),
        autoescape=False,
    )
    template = env.get_template("summary.html.j2")

    # Classify verdicts
    high_count = 0
    medium_count = 0
    low_count = 0
    high_eqpids: List[str] = []

    comparison_rows: List[Dict[str, Any]] = []
    for r in results:
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
        report_link = f"SnapshotScreener_{r.eqpid}_{date_from_str}-{date_to_str}.html"

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
    return output_path
