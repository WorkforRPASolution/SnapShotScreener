"""Internationalization support for SnapshotScreener.

Simple dict-based translation for Korean (ko) and English (en).
"""
from __future__ import annotations

from typing import Dict

SUPPORTED_LANGS = ("ko", "en")

# ---------------------------------------------------------------------------
# Translation strings
# ---------------------------------------------------------------------------
_STRINGS: Dict[str, Dict[str, str]] = {
    "ko": {
        # ---- Verdicts (internal key → display) ----
        "verdict.high": "높음",
        "verdict.medium": "중간",
        "verdict.low": "낮음",
        "sensitivity.insensitive": "둔감",
        "sensitivity.moderate": "중간",
        "sensitivity.sensitive": "민감",

        # ---- Flag labels (renderer) ----
        "flag.session_start": "세션 시작",
        "flag.session_end": "세션 종료",
        "flag.new_screen": "새 화면 그룹 시작",
        "flag.transition_point": "전이점 감지",
        "flag.new_click_cluster": "새 클릭 클러스터 진입",

        # ---- Screening signal verdicts (renderer) ----
        "signal.click_concentration.high": "패턴 가능성 높음 (> 70%)",
        "signal.click_concentration.medium": "중간 수준 (40% ~ 70%)",
        "signal.click_concentration.low": "패턴 가능성 낮음 (< 40%)",
        "signal.session_cv.high": "세션 구조 일정 (< 0.3)",
        "signal.session_cv.medium": "중간 수준 (0.3 ~ 1.0)",
        "signal.session_cv.low": "세션 구조 불규칙 (> 1.0)",
        "signal.sequence_similarity.high": "높은 유사도 (> 0.7)",
        "signal.sequence_similarity.medium": "중간 수준 (0.5 ~ 0.7)",
        "signal.sequence_similarity.low": "낮은 유사도 (< 0.5)",

        # ---- Verdict description parts (renderer) ----
        "desc.click_concentration": "클릭 좌표 집중도 {value:.1f}%",
        "desc.session_cv": "세션 길이 CV {value:.2f}",
        "desc.sequence_similarity": "시퀀스 유사도 {value:.2f}",

        # ---- Pipeline log messages ----
        "log.phase1": "[Phase 1] {eqpid} — 메타데이터 수집",
        "log.phase2": "[Phase 2] {eqpid} — pHash 수집 (캐시 우선)",
        "log.phase3": "[Phase 3] {eqpid} — 분석",
        "log.phase4": "[Phase 4] {eqpid} — 리포트 이미지 수집 ({count}장)",
        "log.phase5": "[Phase 5] {eqpid} — 리포트 및 산출물 생성",
        "log.no_data": "{eqpid}: 데이터 없음",
        "log.no_phash": "{eqpid}: pHash 수집 결과 없음",
        "log.equipment_failed": "장비 {eqpid} 분석 실패: {error}",
        "log.html_report": "HTML 리포트: {path}",
        "log.original_images": "원본 이미지 저장: {path} ({count}장)",
        "log.json_export": "JSON 익스포트: {path}",

        # ---- CLI error messages ----
        "error.config_error": "설정 오류: {e}",
        "error.interrupted": "중단됨 — 캐시를 정리하는 중...",
        "error.cassandra_failed": "Cassandra 연결 실패: {e}",
        "error.analysis_error": "분석 오류: {e}",
        "error.missing_eqpid": "장비 ID가 지정되지 않았습니다 (--eqpid, --eqpid-list, 또는 config의 eqpids 필요)",
        "error.missing_dates": "분석 기간이 지정되지 않았습니다 (--from/--to 또는 config의 date_from/date_to 필요)",
        "error.missing_db_host": "Cassandra 호스트가 지정되지 않았습니다 (--db-host 또는 config의 db_host 필요)",
        "error.missing_db_keyspace": "Cassandra 키스페이스가 지정되지 않았습니다 (--db-keyspace 또는 config의 db_keyspace 필요)",
        "error.missing_db_table": "Cassandra 테이블이 지정되지 않았습니다 (--db-table 또는 config의 db_table 필요)",
        "error.password_warning": "비밀번호를 명령줄 인수로 전달하는 것은 안전하지 않습니다. SS_DB_PASSWORD 환경변수를 사용하세요.",

        # ---- Cassandra client errors ----
        "error.cassandra_connect": "Cassandra 연결 실패 ({host}:{port}): {exc}",
        "error.cassandra_prepare": "Cassandra 쿼리 준비 실패 (keyspace={ks!r}, table={tbl!r}): {exc}",
        "error.cassandra_healthcheck": "Cassandra health-check 실패 ({host}:{port}): {exc}",

        # ---- Report template labels ----
        "report.title": "SnapshotScreener 분석 리포트",
        "report.subtitle": "SnapshotScreener Analysis Report",
        "report.meta.eqpid": "장비 ID",
        "report.meta.period": "분석 기간",
        "report.meta.generated": "생성 일시",
        "report.section.verdict": "종합 판정",
        "report.section.summary": "장비 요약",
        "report.section.frames": "대표 프레임 시퀀스",
        "report.section.signals": "패턴 스크리닝 신호 (레이어 B)",
        "report.section.sensitivity": "파라미터 민감도 분석 (레이어 C)",
        "report.card.total_clicks": "총 클릭 수",
        "report.card.analysis_days": "분석 일수",
        "report.card.days_unit": "일",
        "report.card.sessions": "세션 수",
        "report.card.screen_groups": "화면 그룹",
        "report.card.representative_frames": "대표 프레임",
        "report.card.reduction_rate": "데이터 축소율",
        "report.pattern_label": "패턴 {index}",
        "report.session_count": "({count}개 세션)",
        "report.clicks_count": "클릭 {count}회",
        "report.rep_frames_count": "대표 프레임 {count}개",
        "report.no_image": "이미지 없음",
        "report.click_coord": "클릭 좌표:",
        "report.no_frames": "대표 프레임이 선택되지 않았습니다",
        "report.signal.click_concentration": "클릭 좌표 집중도",
        "report.signal.session_cv": "세션 길이 변동계수 (CV)",
        "report.signal.sequence_similarity": "세션 간 화면 시퀀스 유사도 (LCS)",
        "report.sensitivity.threshold_pair": "Threshold 쌍",
        "report.sensitivity.frame_count": "대표 프레임 수",
        "report.sensitivity.jaccard": "Jaccard 유사도",
        "report.sensitivity.verdict": "판정",
        "report.sensitivity.stable": "안정",
        "report.sensitivity.moderate": "중간",
        "report.sensitivity.unstable": "불안정",
        "report.sensitivity.min_jaccard": "최소 Jaccard 유사도",
        "report.sensitivity.disabled": "민감도 분석이 비활성화되어 있습니다",
        "report.footer": "대표 스냅샷 추출기 {version} &middot; 이 리포트는 SnapshotScreener에 의해 자동 생성되었으며, 최종 판단은 사람이 대표 프레임을 육안 검토한 후 확정해야 합니다.",
        "report.zoom_alt": "확대 보기",

        # ---- Summary template labels ----
        "summary.title": "SnapshotScreener 종합 요약 리포트",
        "summary.subtitle": "Multi-Equipment Summary Report",
        "summary.meta.equipment_count": "분석 장비 수",
        "summary.meta.period": "분석 기간",
        "summary.meta.generated": "생성 일시",
        "summary.section.verdict_summary": "판정 요약",
        "summary.card.high": "높음",
        "summary.card.medium": "중간",
        "summary.card.low": "낮음",
        "summary.card.unit": "대",
        "summary.section.high_equipment": "패턴 가능성 높은 장비",
        "summary.high_recommendation": "Vision AI 투입 대상 권장 ({count}대)",
        "summary.section.comparison": "장비 비교 테이블",
        "summary.table.eqpid": "장비 ID",
        "summary.table.days": "분석 일수",
        "summary.table.clicks": "총 클릭",
        "summary.table.concentration": "집중도",
        "summary.table.cv": "CV",
        "summary.table.similarity": "유사도",
        "summary.table.verdict": "판정",
        "summary.table.report": "리포트",
        "summary.detail_link": "상세 리포트",
        "summary.footer": "대표 스냅샷 추출기 {version} &middot; 이 리포트는 SnapshotScreener에 의해 자동 생성되었으며, 최종 판단은 사람이 대표 프레임을 육안 검토한 후 확정해야 합니다.",
    },

    "en": {
        # ---- Verdicts ----
        "verdict.high": "High",
        "verdict.medium": "Medium",
        "verdict.low": "Low",
        "sensitivity.insensitive": "Insensitive",
        "sensitivity.moderate": "Moderate",
        "sensitivity.sensitive": "Sensitive",

        # ---- Flag labels ----
        "flag.session_start": "Session Start",
        "flag.session_end": "Session End",
        "flag.new_screen": "New Screen Group",
        "flag.transition_point": "Transition Point",
        "flag.new_click_cluster": "New Click Cluster",

        # ---- Screening signal verdicts ----
        "signal.click_concentration.high": "High likelihood (> 70%)",
        "signal.click_concentration.medium": "Moderate (40% ~ 70%)",
        "signal.click_concentration.low": "Low likelihood (< 40%)",
        "signal.session_cv.high": "Consistent sessions (< 0.3)",
        "signal.session_cv.medium": "Moderate (0.3 ~ 1.0)",
        "signal.session_cv.low": "Irregular sessions (> 1.0)",
        "signal.sequence_similarity.high": "High similarity (> 0.7)",
        "signal.sequence_similarity.medium": "Moderate (0.5 ~ 0.7)",
        "signal.sequence_similarity.low": "Low similarity (< 0.5)",

        # ---- Verdict description parts ----
        "desc.click_concentration": "Click concentration {value:.1f}%",
        "desc.session_cv": "Session length CV {value:.2f}",
        "desc.sequence_similarity": "Sequence similarity {value:.2f}",

        # ---- Pipeline log messages ----
        "log.phase1": "[Phase 1] {eqpid} — Metadata collection",
        "log.phase2": "[Phase 2] {eqpid} — pHash collection (cache-first)",
        "log.phase3": "[Phase 3] {eqpid} — Analysis",
        "log.phase4": "[Phase 4] {eqpid} — Report image collection ({count} frames)",
        "log.phase5": "[Phase 5] {eqpid} — Report and output generation",
        "log.no_data": "{eqpid}: No data found",
        "log.no_phash": "{eqpid}: No pHash results",
        "log.equipment_failed": "Equipment {eqpid} analysis failed: {error}",
        "log.html_report": "HTML report: {path}",
        "log.original_images": "Original images saved: {path} ({count} frames)",
        "log.json_export": "JSON export: {path}",

        # ---- CLI error messages ----
        "error.config_error": "Configuration error: {e}",
        "error.interrupted": "Interrupted — cleaning up cache...",
        "error.cassandra_failed": "Cassandra connection failed: {e}",
        "error.analysis_error": "Analysis error: {e}",
        "error.missing_eqpid": "No equipment ID specified (--eqpid, --eqpid-list, or eqpids in config required)",
        "error.missing_dates": "No analysis period specified (--from/--to or date_from/date_to in config required)",
        "error.missing_db_host": "No Cassandra host specified (--db-host or db_host in config required)",
        "error.missing_db_keyspace": "No Cassandra keyspace specified (--db-keyspace or db_keyspace in config required)",
        "error.missing_db_table": "No Cassandra table specified (--db-table or db_table in config required)",
        "error.password_warning": "Passing password via CLI argument is insecure. Use SS_DB_PASSWORD environment variable.",

        # ---- Cassandra client errors ----
        "error.cassandra_connect": "Cassandra connection failed ({host}:{port}): {exc}",
        "error.cassandra_prepare": "Cassandra query preparation failed (keyspace={ks!r}, table={tbl!r}): {exc}",
        "error.cassandra_healthcheck": "Cassandra health-check failed ({host}:{port}): {exc}",

        # ---- Report template labels ----
        "report.title": "SnapshotScreener Analysis Report",
        "report.subtitle": "SnapshotScreener Analysis Report",
        "report.meta.eqpid": "Equipment ID",
        "report.meta.period": "Analysis Period",
        "report.meta.generated": "Generated",
        "report.section.verdict": "Overall Verdict",
        "report.section.summary": "Equipment Summary",
        "report.section.frames": "Representative Frame Sequence",
        "report.section.signals": "Pattern Screening Signals (Layer B)",
        "report.section.sensitivity": "Parameter Sensitivity Analysis (Layer C)",
        "report.card.total_clicks": "Total Clicks",
        "report.card.analysis_days": "Analysis Days",
        "report.card.days_unit": "days",
        "report.card.sessions": "Sessions",
        "report.card.screen_groups": "Screen Groups",
        "report.card.representative_frames": "Representative Frames",
        "report.card.reduction_rate": "Data Reduction Rate",
        "report.pattern_label": "Pattern {index}",
        "report.session_count": "({count} sessions)",
        "report.clicks_count": "{count} clicks",
        "report.rep_frames_count": "{count} representative frames",
        "report.no_image": "No image",
        "report.click_coord": "Click coord:",
        "report.no_frames": "No representative frames selected",
        "report.signal.click_concentration": "Click Coordinate Concentration",
        "report.signal.session_cv": "Session Length CV",
        "report.signal.sequence_similarity": "Session Sequence Similarity (LCS)",
        "report.sensitivity.threshold_pair": "Threshold Pair",
        "report.sensitivity.frame_count": "Frame Count",
        "report.sensitivity.jaccard": "Jaccard Similarity",
        "report.sensitivity.verdict": "Verdict",
        "report.sensitivity.stable": "Stable",
        "report.sensitivity.moderate": "Moderate",
        "report.sensitivity.unstable": "Unstable",
        "report.sensitivity.min_jaccard": "Min Jaccard Similarity",
        "report.sensitivity.disabled": "Sensitivity analysis is disabled",
        "report.footer": "SnapshotScreener {version} &middot; This report was auto-generated. Final judgment must be confirmed by human review of representative frames.",
        "report.zoom_alt": "Zoom view",

        # ---- Summary template labels ----
        "summary.title": "SnapshotScreener Summary Report",
        "summary.subtitle": "Multi-Equipment Summary Report",
        "summary.meta.equipment_count": "Equipment Count",
        "summary.meta.period": "Analysis Period",
        "summary.meta.generated": "Generated",
        "summary.section.verdict_summary": "Verdict Summary",
        "summary.card.high": "High",
        "summary.card.medium": "Medium",
        "summary.card.low": "Low",
        "summary.card.unit": "units",
        "summary.section.high_equipment": "High-Pattern Equipment",
        "summary.high_recommendation": "Recommended for Vision AI ({count} units)",
        "summary.section.comparison": "Equipment Comparison",
        "summary.table.eqpid": "Equipment ID",
        "summary.table.days": "Days",
        "summary.table.clicks": "Clicks",
        "summary.table.concentration": "Concentration",
        "summary.table.cv": "CV",
        "summary.table.similarity": "Similarity",
        "summary.table.verdict": "Verdict",
        "summary.table.report": "Report",
        "summary.detail_link": "Detail Report",
        "summary.footer": "SnapshotScreener {version} &middot; This report was auto-generated. Final judgment must be confirmed by human review of representative frames.",
    },
}


def t(key: str, lang: str = "ko") -> str:
    """Look up a translation string.

    Parameters
    ----------
    key:
        Dotted key like ``"verdict.high"`` or ``"log.phase1"``.
    lang:
        Language code (``"ko"`` or ``"en"``).

    Returns
    -------
    str
        Translated string.  Falls back to Korean, then to the raw key.
    """
    strings = _STRINGS.get(lang, _STRINGS["ko"])
    result = strings.get(key)
    if result is not None:
        return result
    # Fallback to Korean
    result = _STRINGS["ko"].get(key)
    if result is not None:
        return result
    return key


def get_labels(lang: str = "ko") -> Dict[str, str]:
    """Return all report/summary template labels for the given language.

    Keys are simplified (dots replaced with underscores) for easier
    access in Jinja2 templates: ``{{ labels.report_title }}``.

    Returns
    -------
    dict
        Flat dict of label key -> translated string.
    """
    strings = _STRINGS.get(lang, _STRINGS["ko"])
    labels: Dict[str, str] = {}
    for key, value in strings.items():
        if key.startswith(("report.", "summary.", "flag.", "signal.",
                           "sensitivity.", "verdict.", "desc.")):
            # Convert dotted key to underscore for Jinja2: "report.title" -> "report_title"
            label_key = key.replace(".", "_")
            labels[label_key] = value
    return labels
