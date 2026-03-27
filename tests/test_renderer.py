"""Tests for the report generation package.

Covers image_processor, renderer, summary_renderer, and edge cases
(empty frames, sensitivity disabled).
"""
from __future__ import annotations

import base64
import io
import tempfile
from datetime import date
from pathlib import Path
from typing import Dict, List

import pytest
from PIL import Image

from snapshot_screener.config import ScreenerConfig
from snapshot_screener.models import (
    AnalysisResult,
    FrameFeature,
    ScreeningResult,
    SensitivityResult,
)
from snapshot_screener.report.image_processor import process_image_for_report
from snapshot_screener.report.renderer import render_report
from snapshot_screener.report.summary_renderer import render_summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_image_b64(width: int = 800, height: int = 600, color: str = "red") -> str:
    """Create a base64-encoded PNG image for testing."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _make_config(output_dir: str = ".") -> ScreenerConfig:
    """Create a minimal ScreenerConfig for testing."""
    return ScreenerConfig(
        eqpids=["EQ-TEST"],
        date_from=date(2026, 3, 1),
        date_to=date(2026, 3, 15),
        db_host="localhost",
        output_dir=output_dir,
        screen_width=1920,
        screen_height=1080,
    )


def _make_frame_feature(
    fname: str = "1742698872000_285_124.png",
    timestamp_ms: int = 1742698872000,
    x: int = 285,
    y: int = 124,
    session_id: str = "EQ-TEST_S0001",
    candidate_flags: List[str] | None = None,
    candidate_score: float = 7.0,
    is_representative: bool = True,
) -> FrameFeature:
    """Create a FrameFeature for testing."""
    return FrameFeature(
        eqpid="EQ-TEST",
        fname=fname,
        timestamp_ms=timestamp_ms,
        x=x,
        y=y,
        session_id=session_id,
        candidate_flags=candidate_flags or ["session_start", "new_screen"],
        candidate_score=candidate_score,
        is_representative=is_representative,
    )


def _make_screening_result(
    verdict: str = "패턴 존재 가능성 — 높음",
) -> ScreeningResult:
    """Create a ScreeningResult for testing."""
    return ScreeningResult(
        click_concentration=78.3,
        click_concentration_level="high",
        session_cv=0.24,
        session_cv_level="high",
        sequence_similarity=0.63,
        sequence_similarity_level="medium",
        verdict=verdict,
    )


def _make_sensitivity_result() -> SensitivityResult:
    """Create a SensitivityResult for testing."""
    return SensitivityResult(
        threshold_values=[3, 4, 5, 6],
        frame_counts={3: 25, 4: 23, 5: 21, 6: 17},
        jaccard_pairs=[(3, 4, 0.87), (4, 5, 0.82), (5, 6, 0.68)],
        min_jaccard=0.68,
        sensitivity_verdict="파라미터에 둔감 — 구조 명확",
    )


def _make_analysis_result(
    representative_features: List[FrameFeature] | None = None,
    all_features: List[FrameFeature] | None = None,
    sensitivity: SensitivityResult | None = None,
    screening: ScreeningResult | None = None,
) -> AnalysisResult:
    """Create a complete AnalysisResult for testing."""
    if representative_features is None:
        representative_features = [
            _make_frame_feature(),
            _make_frame_feature(
                fname="1742699077000_180_246.png",
                timestamp_ms=1742699077000,
                x=180,
                y=246,
                candidate_flags=["new_screen", "transition_point"],
            ),
        ]
    if all_features is None:
        all_features = representative_features.copy()

    return AnalysisResult(
        eqpid="EQ-TEST",
        config_summary={"session_gap_ms": 900000},
        all_features=all_features,
        representative_features=representative_features,
        screening=screening or _make_screening_result(),
        sensitivity=sensitivity,
        total_clicks=42847,
        analysis_days=14,
        session_count=127,
        screen_group_count=18,
        representative_count=len(representative_features),
        reduction_rate=99.9,
    )


# ---------------------------------------------------------------------------
# Test: image_processor
# ---------------------------------------------------------------------------


class TestImageProcessor:
    """Tests for process_image_for_report."""

    def test_resize_and_compress(self) -> None:
        """Image is resized and output is valid base64 JPEG."""
        original_b64 = _make_test_image_b64(1920, 1080)
        result = process_image_for_report(original_b64, max_width=640, max_height=360)

        # Result should be valid base64
        raw = base64.b64decode(result)
        img = Image.open(io.BytesIO(raw))
        assert img.format == "JPEG"
        assert img.size[0] <= 640
        assert img.size[1] <= 360

    def test_maintains_aspect_ratio(self) -> None:
        """Thumbnail should maintain the aspect ratio."""
        # 16:9 input
        original_b64 = _make_test_image_b64(1600, 900)
        result = process_image_for_report(original_b64, max_width=640, max_height=360)

        raw = base64.b64decode(result)
        img = Image.open(io.BytesIO(raw))
        assert img.size == (640, 360)

    def test_small_image_not_upscaled(self) -> None:
        """Images smaller than max dimensions should not be upscaled."""
        original_b64 = _make_test_image_b64(320, 200)
        result = process_image_for_report(original_b64, max_width=640, max_height=360)

        raw = base64.b64decode(result)
        img = Image.open(io.BytesIO(raw))
        assert img.size == (320, 200)

    def test_rgba_image_converted(self) -> None:
        """RGBA images should be converted to RGB for JPEG."""
        img = Image.new("RGBA", (800, 600), color=(255, 0, 0, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        original_b64 = base64.b64encode(buf.read()).decode("ascii")

        result = process_image_for_report(original_b64)
        raw = base64.b64decode(result)
        out_img = Image.open(io.BytesIO(raw))
        assert out_img.mode == "RGB"
        assert out_img.format == "JPEG"


# ---------------------------------------------------------------------------
# Test: renderer
# ---------------------------------------------------------------------------


class TestRenderer:
    """Tests for render_report."""

    def test_render_basic_report(self, tmp_path: Path) -> None:
        """Render a report and verify it contains key sections."""
        config = _make_config(output_dir=str(tmp_path))
        result = _make_analysis_result(sensitivity=_make_sensitivity_result())

        # Create a simple image for one frame
        img_b64 = _make_test_image_b64(320, 200)
        images: Dict[str, str] = {
            "1742698872000_285_124.png": process_image_for_report(img_b64),
        }

        output_path = render_report(result, images, config)

        assert output_path.exists()
        html = output_path.read_text(encoding="utf-8")

        # Check key sections exist
        assert "장비 요약" in html
        assert "대표 프레임 시퀀스" in html
        assert "패턴 스크리닝 신호" in html
        assert "파라미터 민감도 분석" in html
        assert "종합 판정" in html

        # Check metadata
        assert "EQ-TEST" in html
        assert "42,847" in html  # formatted total_clicks
        assert "99.9" in html  # reduction_rate

        # Check frame data
        assert "세션 시작" in html
        assert "새 화면 그룹 시작" in html
        assert "전이점 감지" in html

        # Check screening signals
        assert "78.3" in html  # click_concentration
        assert "0.24" in html  # session_cv

        # Check sensitivity data
        assert "3 vs 4" in html
        assert "0.87" in html

        # Check it's a valid HTML file
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_render_with_click_dot(self, tmp_path: Path) -> None:
        """Verify click dot CSS overlay is present in output."""
        config = _make_config(output_dir=str(tmp_path))
        result = _make_analysis_result()
        img_b64 = _make_test_image_b64(320, 200)
        images = {"1742698872000_285_124.png": process_image_for_report(img_b64)}

        output_path = render_report(result, images, config)
        html = output_path.read_text(encoding="utf-8")

        # Check that click-dot is rendered via CSS, not canvas
        assert "click-dot" in html
        assert 'class="click-dot"' in html
        # Should not have canvas (JavaScript is OK for zoom modal)
        assert "<canvas" not in html

    def test_output_filename_format(self, tmp_path: Path) -> None:
        """Output filename follows expected pattern."""
        config = _make_config(output_dir=str(tmp_path))
        result = _make_analysis_result()

        output_path = render_report(result, {}, config)
        assert output_path.name == "SnapshotScreener_EQ-TEST_20260301-20260315.html"

    def test_empty_frames_message(self, tmp_path: Path) -> None:
        """Zero representative frames shows placeholder message."""
        config = _make_config(output_dir=str(tmp_path))
        result = _make_analysis_result(
            representative_features=[],
            all_features=[
                _make_frame_feature(is_representative=False),
            ],
        )

        output_path = render_report(result, {}, config)
        html = output_path.read_text(encoding="utf-8")

        assert "대표 프레임이 선택되지 않았습니다" in html

    def test_sensitivity_disabled_message(self, tmp_path: Path) -> None:
        """When sensitivity is None, placeholder is shown."""
        config = _make_config(output_dir=str(tmp_path))
        result = _make_analysis_result(sensitivity=None)

        output_path = render_report(result, {}, config)
        html = output_path.read_text(encoding="utf-8")

        assert "민감도 분석이 비활성화되어 있습니다" in html
        # Sections should still be numbered 1-5
        assert '<span class="num">4</span>' in html
        assert '<span class="num">5</span>' in html

    def test_missing_image_shows_placeholder(self, tmp_path: Path) -> None:
        """Frames without images show '이미지 없음' placeholder."""
        config = _make_config(output_dir=str(tmp_path))
        result = _make_analysis_result()

        # Provide no images at all
        output_path = render_report(result, {}, config)
        html = output_path.read_text(encoding="utf-8")

        assert "이미지 없음" in html

    def test_system_font_stack(self, tmp_path: Path) -> None:
        """CSS should use system font stack, not Google Fonts."""
        config = _make_config(output_dir=str(tmp_path))
        result = _make_analysis_result()

        output_path = render_report(result, {}, config)
        html = output_path.read_text(encoding="utf-8")

        assert "Malgun Gothic" in html
        assert "Apple SD Gothic Neo" in html
        assert "fonts.googleapis.com" not in html
        assert "Consolas" in html

    def test_mobile_aspect_ratio(self, tmp_path: Path) -> None:
        """Mobile media query should use 16/9 aspect ratio."""
        config = _make_config(output_dir=str(tmp_path))
        result = _make_analysis_result()

        output_path = render_report(result, {}, config)
        html = output_path.read_text(encoding="utf-8")

        assert "aspect-ratio: 16/9" in html
        assert "aspect-ratio: 16/10" not in html


# ---------------------------------------------------------------------------
# Test: summary_renderer
# ---------------------------------------------------------------------------


class TestSummaryRenderer:
    """Tests for render_summary."""

    def test_render_summary_basic(self, tmp_path: Path) -> None:
        """Render a summary with multiple equipment and verify table."""
        config = _make_config(output_dir=str(tmp_path))

        results = [
            _make_analysis_result(
                screening=_make_screening_result("패턴 존재 가능성 — 높음"),
            ),
            AnalysisResult(
                eqpid="EQ-TEST2",
                config_summary={},
                all_features=[],
                representative_features=[],
                screening=ScreeningResult(
                    click_concentration=35.0,
                    click_concentration_level="low",
                    session_cv=0.8,
                    session_cv_level="low",
                    sequence_similarity=0.3,
                    sequence_similarity_level="low",
                    verdict="패턴 존재 가능성 — 낮음",
                ),
                sensitivity=None,
                total_clicks=1234,
                analysis_days=7,
                session_count=5,
                screen_group_count=3,
                representative_count=0,
                reduction_rate=100.0,
            ),
        ]

        output_path = render_summary(results, config)

        assert output_path.exists()
        html = output_path.read_text(encoding="utf-8")

        # Check summary page has right content
        assert "종합 요약 리포트" in html
        assert "EQ-TEST" in html
        assert "EQ-TEST2" in html

        # Aggregate counts
        assert "판정 요약" in html

        # Comparison table
        assert "장비 비교 테이블" in html
        assert "42,847" in html
        assert "1,234" in html

        # Links to individual reports
        assert "SnapshotScreener_EQ-TEST_20260301-20260315.html" in html
        assert "SnapshotScreener_EQ-TEST2_20260301-20260315.html" in html

    def test_summary_output_filename(self, tmp_path: Path) -> None:
        """Summary filename follows expected pattern."""
        config = _make_config(output_dir=str(tmp_path))
        results = [_make_analysis_result()]

        output_path = render_summary(results, config)
        assert output_path.name == "SnapshotScreener_Summary_20260301-20260315.html"

    def test_summary_high_equipment_highlighted(self, tmp_path: Path) -> None:
        """Equipment with '높음' verdict should appear in highlighted block."""
        config = _make_config(output_dir=str(tmp_path))
        results = [
            _make_analysis_result(
                screening=_make_screening_result("패턴 존재 가능성 — 높음"),
            ),
        ]

        output_path = render_summary(results, config)
        html = output_path.read_text(encoding="utf-8")

        assert "패턴 가능성 높은 장비" in html
        assert "Vision AI 투입 대상 권장" in html
        assert "EQ-TEST" in html

    def test_summary_no_images(self, tmp_path: Path) -> None:
        """Summary should not contain any image data."""
        config = _make_config(output_dir=str(tmp_path))
        results = [_make_analysis_result()]

        output_path = render_summary(results, config)
        html = output_path.read_text(encoding="utf-8")

        assert "data:image" not in html
