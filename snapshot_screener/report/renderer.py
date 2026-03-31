"""Render individual equipment analysis reports.

Uses Jinja2 to produce a self-contained HTML file from an AnalysisResult
and pre-collected images.
"""
from __future__ import annotations

import datetime
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from snapshot_screener import __version__
from snapshot_screener.config import ScreenerConfig
from snapshot_screener.i18n import t, get_labels
from snapshot_screener.models import AnalysisResult, FrameFeature

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flag -> display mapping
# ---------------------------------------------------------------------------

def _get_flag_labels(lang: str) -> Dict[str, str]:
    return {
        "session_start": t("flag.session_start", lang),
        "session_end": t("flag.session_end", lang),
        "new_screen": t("flag.new_screen", lang),
        "transition_point": t("flag.transition_point", lang),
        "new_click_cluster": t("flag.new_click_cluster", lang),
    }

_FLAG_TAG_CLASSES: Dict[str, str] = {
    "session_start": "tag-session",
    "session_end": "tag-session",
    "new_screen": "tag-screen",
    "transition_point": "tag-transition",
    "new_click_cluster": "tag-cluster",
}


def _get_template_dir() -> Path:
    """Locate the templates directory, supporting both installed packages and PyInstaller."""
    # Try importlib.resources first (Python 3.10+)
    try:
        from importlib.resources import files

        pkg_dir = files("snapshot_screener.report.templates")
        # Convert to a path — this works for regular installs
        template_path = Path(str(pkg_dir))
        if template_path.is_dir():
            return template_path
    except Exception:
        pass

    # Fallback for PyInstaller
    if hasattr(sys, "_MEIPASS"):
        meipass_path = Path(sys._MEIPASS) / "snapshot_screener" / "report" / "templates"  # type: ignore[attr-defined]
        if meipass_path.is_dir():
            return meipass_path

    # Fallback: relative to this file
    fallback = Path(__file__).parent / "templates"
    return fallback


def _level_to_color(level: str) -> str:
    """Map a level string (high/medium/low) to a CSS color name."""
    mapping = {"high": "green", "medium": "amber", "low": "red"}
    return mapping.get(level, "amber")


def _level_to_verdict_class(level: str) -> str:
    """Map a level string to a CSS verdict class."""
    mapping = {"high": "high", "medium": "mid", "low": "low"}
    return mapping.get(level, "mid")


def _build_screening_context(result: AnalysisResult, lang: str = "ko") -> Dict[str, Any]:
    """Build the screening section context from ScreeningResult."""
    s = result.screening

    ctx: Dict[str, Any] = {
        "click_concentration": s.click_concentration,
        "click_concentration_level": s.click_concentration_level,
        "click_concentration_color": _level_to_color(s.click_concentration_level),
        "click_concentration_verdict_class": _level_to_verdict_class(
            s.click_concentration_level
        ),
        "session_cv": s.session_cv,
        "session_cv_level": s.session_cv_level,
        "session_cv_color": _level_to_color(s.session_cv_level),
        "session_cv_verdict_class": _level_to_verdict_class(s.session_cv_level),
        "sequence_similarity": s.sequence_similarity,
        "sequence_similarity_level": s.sequence_similarity_level,
        "sequence_similarity_color": _level_to_color(s.sequence_similarity_level),
        "sequence_similarity_verdict_class": _level_to_verdict_class(
            s.sequence_similarity_level
        ),
    }

    # Human-readable verdict strings for each signal
    if s.click_concentration is not None:
        ctx["click_concentration_verdict"] = t(
            f"signal.click_concentration.{s.click_concentration_level}", lang
        )

    if s.session_cv is not None:
        ctx["session_cv_verdict"] = t(
            f"signal.session_cv.{s.session_cv_level}", lang
        )

    if s.sequence_similarity is not None:
        ctx["sequence_similarity_verdict"] = t(
            f"signal.sequence_similarity.{s.sequence_similarity_level}", lang
        )

    return ctx


def _verdict_to_color(verdict: str) -> str:
    """Map a verdict string to a color name."""
    return {"high": "green", "medium": "amber", "low": "red"}.get(verdict, "amber")


def _build_sessions_context(
    result: AnalysisResult,
    images: Dict[str, str],
    config: ScreenerConfig,
    frames_rel_dir: str = "",
    lang: str = "ko",
) -> List[Dict[str, Any]]:
    """Build session list context from representative features."""
    # Group by session_id
    session_groups: Dict[str, List[FrameFeature]] = defaultdict(list)
    for feat in result.representative_features:
        session_groups[feat.session_id].append(feat)

    # Count clicks per session from all features
    session_click_counts: Dict[str, int] = defaultdict(int)
    for feat in result.all_features:
        session_click_counts[feat.session_id] += 1

    sessions: List[Dict[str, Any]] = []
    for sid in sorted(session_groups.keys()):
        frames_data = sorted(session_groups[sid], key=lambda f: f.timestamp_ms)

        # Time range
        if frames_data:
            t_start = datetime.datetime.fromtimestamp(
                frames_data[0].timestamp_ms / 1000, tz=datetime.timezone.utc
            )
            t_end = datetime.datetime.fromtimestamp(
                frames_data[-1].timestamp_ms / 1000, tz=datetime.timezone.utc
            )
            time_range = f"{t_start.strftime('%H:%M')} ~ {t_end.strftime('%H:%M')}"
        else:
            time_range = ""

        frames: List[Dict[str, Any]] = []
        for feat in frames_data:
            dt = datetime.datetime.fromtimestamp(
                feat.timestamp_ms / 1000, tz=datetime.timezone.utc
            )
            time_str = dt.strftime("%H:%M:%S")

            # Tags and descriptions from candidate_flags
            flag_labels = _get_flag_labels(lang)
            tags: List[str] = []
            tag_classes: List[str] = []
            desc_parts: List[str] = []
            for flag in feat.candidate_flags:
                label = flag_labels.get(flag, flag)
                cls = _FLAG_TAG_CLASSES.get(flag, "tag-screen")
                tags.append(label)
                tag_classes.append(cls)
                desc_parts.append(label)

            desc = ", ".join(desc_parts) if desc_parts else ""

            # Compute click position percentage relative to screen dimensions
            x_pct = (feat.x / config.screen_width) * 100 if config.screen_width else 0
            y_pct = (
                (feat.y / config.screen_height) * 100 if config.screen_height else 0
            )

            # Relative path to original image in frames/ directory
            original_path = ""
            if frames_rel_dir:
                original_path = f"{frames_rel_dir}/{feat.fname}"

            frames.append(
                {
                    "time": time_str,
                    "fname": feat.fname,
                    "b64": images.get(feat.fname),
                    "original_path": original_path,
                    "x_pct": round(x_pct, 2),
                    "y_pct": round(y_pct, 2),
                    "x": feat.x,
                    "y": feat.y,
                    "tags": tags,
                    "tag_classes": tag_classes,
                    "desc": desc,
                    "score": feat.candidate_score,
                }
            )

        # Screen group sequence for this session (from ALL features, not just reps)
        sg_sequence = []
        for feat in sorted(
            [f for f in result.all_features if f.session_id == sid],
            key=lambda f: f.timestamp_ms,
        ):
            sg = feat.screen_group_id or "?"
            if not sg_sequence or sg_sequence[-1] != sg:
                sg_sequence.append(sg)

        sessions.append(
            {
                "id": sid,
                "click_count": session_click_counts.get(sid, 0),
                "time_range": time_range,
                "frame_count": len(frames),
                "frames": frames,
                "sg_sequence": sg_sequence,
                "sg_sequence_key": " → ".join(sg_sequence),
            }
        )

    # Group sessions by screen_group sequence pattern
    pattern_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for sess in sessions:
        pattern_groups[sess["sg_sequence_key"]].append(sess)

    grouped: List[Dict[str, Any]] = []
    for pattern_key, group_sessions in sorted(
        pattern_groups.items(), key=lambda kv: -len(kv[1])
    ):
        grouped.append(
            {
                "pattern": pattern_key,
                "count": len(group_sessions),
                "sessions": group_sessions,
            }
        )

    return grouped


def _build_sensitivity_context(
    result: AnalysisResult,
) -> Optional[Dict[str, Any]]:
    """Build sensitivity section context."""
    if result.sensitivity is None:
        return None

    s = result.sensitivity
    return {
        "threshold_values": s.threshold_values,
        "frame_counts": s.frame_counts,
        "jaccard_pairs": s.jaccard_pairs,
        "min_jaccard": s.min_jaccard,
        "sensitivity_verdict": s.sensitivity_verdict,
    }


def render_report(
    result: AnalysisResult,
    images: Dict[str, str],
    config: ScreenerConfig,
) -> Path:
    """Render an HTML analysis report for a single equipment.

    Parameters
    ----------
    result:
        Complete analysis result.
    images:
        Mapping of fname -> base64 JPEG string.
    config:
        Screener configuration (used for output_dir, date range, etc.).

    Returns
    -------
    Path
        Path to the generated HTML file.
    """
    template_dir = _get_template_dir()
    env = Environment(
        loader=FileSystemLoader(str(template_dir), encoding="utf-8"),
        autoescape=False,
    )
    template = env.get_template("report.html.j2")

    # Verdict
    verdict = result.screening.verdict
    verdict_color = _verdict_to_color(verdict)
    verdict_display = t("verdict." + verdict, config.lang)

    # Labels for Jinja2 template
    labels = get_labels(config.lang)

    # Build description from screening signals
    parts: List[str] = []
    s = result.screening
    if s.click_concentration is not None:
        parts.append(
            t("desc.click_concentration", config.lang).format(
                value=s.click_concentration * 100
            )
        )
    if s.session_cv is not None:
        parts.append(
            t("desc.session_cv", config.lang).format(value=s.session_cv)
        )
    if s.sequence_similarity is not None:
        parts.append(
            t("desc.sequence_similarity", config.lang).format(
                value=s.sequence_similarity
            )
        )
    verdict_desc = ", ".join(parts) + "." if parts else ""

    # Equipment directory and relative path from HTML to frames/
    date_from_str = str(config.date_from).replace("-", "")
    date_to_str = str(config.date_to).replace("-", "")
    base_name = f"{result.screening.verdict}_SnapshotScreener_{result.eqpid}_{date_from_str}-{date_to_str}"
    frames_rel_dir = "frames"

    context = {
        "eqpid": result.eqpid,
        "date_from": str(config.date_from),
        "date_to": str(config.date_to),
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": f"v{__version__}",
        "total_clicks": result.total_clicks,
        "analysis_days": result.analysis_days,
        "session_count": result.session_count,
        "screen_group_count": result.screen_group_count,
        "representative_count": result.representative_count,
        "reduction_rate": result.reduction_rate,
        "pattern_groups": _build_sessions_context(
            result, images, config, frames_rel_dir, lang=config.lang,
        ),
        "screening": _build_screening_context(result, lang=config.lang),
        "sensitivity": _build_sensitivity_context(result),
        "verdict": verdict_display,
        "verdict_color": verdict_color,
        "verdict_desc": verdict_desc,
        "lang": config.lang,
        "labels": labels,
    }

    html = template.render(**context)

    # Write output inside equipment directory
    equip_dir = Path(config.output_dir) / base_name
    equip_dir.mkdir(parents=True, exist_ok=True)
    output_path = equip_dir / f"{base_name}.html"

    output_path.write_text(html, encoding="utf-8")
    logger.info("Report written to %s", output_path)
    return output_path
