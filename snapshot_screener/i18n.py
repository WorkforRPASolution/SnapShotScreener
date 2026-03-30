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

        # ---- Triage log messages ----
        "triage.log.loaded": "[트리아지] 장비 {count}대 로드 완료, 스캔 시작",
        "triage.log.failed": "[트리아지] {eqpid} 실패: {error}",
        "triage.log.circuit_breaker": "[트리아지] 연속 {count}회 실패, 헬스체크 실행 중...",
        "triage.log.health_failed": "[트리아지] 헬스체크 실패 — {idx}/{total} 장비 후 중단 (실패 {failed}건)",
        "triage.log.health_passed": "[트리아지] 헬스체크 통과, 계속 진행",
        "triage.log.progress": "[트리아지] [{current}/{total}] {pct:.1f}% | 실패 {failed}건 | 예상 잔여 {eta:.0f}분",
        "triage.log.equipment_done": "[트리아지] {eqpid}: 클릭 {clicks}건, 세션 {sessions}개, 판정={verdict}",
        "triage.log.interrupted": "[트리아지] 중단됨. 부분 결과 저장 ({done}/{total} 완료)",
        "triage.log.no_results": "[트리아지] 수집된 결과 없음",
        "triage.log.complete": "[트리아지] 완료: {count}대 / {elapsed:.1f}초 (높음={high}, 중간={medium}, 낮음={low}, 오류={error})",
        "triage.log.csv_report": "[트리아지] CSV 리포트: {path}",
        "triage.log.json_report": "[트리아지] JSON 리포트: {path}",
        "triage.log.html_report": "[트리아지] HTML 리포트: {path}",
        "triage.log.csv_loaded": "CSV에서 장비 {count}대 로드: {path}",
        "triage.log.csv_duplicate": "중복 eqpid '{eqpid}' 무시 (행 {line})",
        "triage.log.csv_blank": "빈 행 무시 (행 {line})",
        "triage.log.csv_short": "열 부족 행 무시 (행 {line}): {row}",
        "triage.log.fname_parse_fail": "fname 파싱 실패, 건너뜀: {fname}",

        # ---- Triage report template labels ----
        "triage.report.title": "SnapshotScreener 트리아지 리포트",
        "triage.report.total": "전체",
        "triage.report.high": "높음",
        "triage.report.medium": "중간",
        "triage.report.low": "낮음",
        "triage.report.error": "오류",
        "triage.report.guide_title": "리포트 해석 가이드",
        "triage.report.guide_toggle": "클릭하여 펼치기",
        "triage.report.columns": "컬럼 설명",
        "triage.report.col_header": "컬럼",
        "triage.report.col_meaning": "의미",
        "triage.report.col_note": "비고",
        "triage.report.col_clicks": "클릭 수",
        "triage.report.col_clicks_desc": "분석 기간 내 총 클릭 수",
        "triage.report.col_sessions": "세션 수",
        "triage.report.col_sessions_desc": "세션 수 (15분 간격으로 분리)",
        "triage.report.col_days": "데이터 일수",
        "triage.report.col_days_desc": "데이터가 존재하는 일수",
        "triage.report.col_concentration": "집중도",
        "triage.report.col_concentration_desc": "DBSCAN 클러스터 소속 비율 — 클릭이 특정 좌표에 집중된 정도",
        "triage.report.col_concentration_note": "참고용. 고정 UI 장비는 자동화 여부와 무관하게 0.95 이상",
        "triage.report.col_cv": "CV",
        "triage.report.col_cv_desc": "세션별 클릭 수의 변동계수 — 세션 길이의 균일도",
        "triage.report.col_cv_note": "판정 기준 신호",
        "triage.report.verdict_title": "판정 기준 (세션 CV 기반)",
        "triage.report.cv_range": "CV 범위",
        "triage.report.verdict": "판정",
        "triage.report.meaning": "의미",
        "triage.report.verdict_high_desc": "세션 간 클릭 수가 거의 동일 — 자동화 패턴 의심. 정밀 분석 우선 대상",
        "triage.report.verdict_medium_desc": "중간 수준의 균일도 — 추가 확인 필요",
        "triage.report.verdict_low_desc": "세션 간 편차가 큼 — 일반적인 수동 조작 패턴",
        "triage.report.verdict_insufficient_desc": "데이터 부족 (유효 세션 2개 미만, 클릭 3회 이상 세션 기준)",
        "triage.report.limitations": "제한 사항",
        "triage.report.limitations_text": "트리아지는 세션 CV만으로 판정합니다. 클릭 좌표 집중도는 고정 UI 장비에서 변별력이 없어 판정에 사용하지 않습니다. 시퀀스 유사도(pHash 기반)는 이미지 데이터 없이 계산할 수 없습니다.",
        "triage.report.limitations_data": "데이터 소스는 snapshotlist 테이블 (TTL 15일)입니다. 트리아지 '높음' 판정은 정밀 분석 후보이며, 최종 판단이 아닙니다.",
        "triage.report.workflow": "권장 워크플로우",
        "triage.report.workflow_step1": "트리아지 (1만 대 이상)",
        "triage.report.workflow_step2": "높음 판정 필터링",
        "triage.report.workflow_step3": "정밀 분석 (3신호)",
        "triage.report.groups_title": "프로세스 / 모델 그룹",
        "triage.report.equipment": "장비",
        "triage.report.models": "모델",
        "triage.report.eqpid": "장비ID",
        "triage.report.footer": "SnapshotScreener 트리아지 모드 — 전체 장비 목록은 CSV 출력에서 확인",

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

        # ---- Triage log messages ----
        "triage.log.loaded": "[Triage] Loaded {count} equipment, starting scan",
        "triage.log.failed": "[Triage] {eqpid} failed: {error}",
        "triage.log.circuit_breaker": "[Triage] {count} consecutive failures, running health check...",
        "triage.log.health_failed": "[Triage] Health check failed — aborting after {idx}/{total} equipment ({failed} failed)",
        "triage.log.health_passed": "[Triage] Health check passed, continuing",
        "triage.log.progress": "[Triage] [{current}/{total}] {pct:.1f}% | {failed} failed | ETA {eta:.0f}m",
        "triage.log.equipment_done": "[Triage] {eqpid}: {clicks} clicks, {sessions} sessions, verdict={verdict}",
        "triage.log.interrupted": "[Triage] Interrupted. Saving partial results ({done}/{total} completed)",
        "triage.log.no_results": "[Triage] No results collected",
        "triage.log.complete": "[Triage] Complete: {count} equipment / {elapsed:.1f}s (high={high}, medium={medium}, low={low}, error={error})",
        "triage.log.csv_report": "[Triage] CSV report: {path}",
        "triage.log.json_report": "[Triage] JSON report: {path}",
        "triage.log.html_report": "[Triage] HTML report: {path}",
        "triage.log.csv_loaded": "Loaded {count} equipment from CSV: {path}",
        "triage.log.csv_duplicate": "Duplicate eqpid '{eqpid}' ignored (row {line})",
        "triage.log.csv_blank": "Blank row ignored (row {line})",
        "triage.log.csv_short": "Short row ignored (row {line}): {row}",
        "triage.log.fname_parse_fail": "fname parse failed, skipping: {fname}",

        # ---- Triage report template labels ----
        "triage.report.title": "SnapshotScreener Triage Report",
        "triage.report.total": "Total",
        "triage.report.high": "High",
        "triage.report.medium": "Medium",
        "triage.report.low": "Low",
        "triage.report.error": "Error",
        "triage.report.guide_title": "How to Read This Report",
        "triage.report.guide_toggle": "click to expand",
        "triage.report.columns": "Columns",
        "triage.report.col_header": "Column",
        "triage.report.col_meaning": "Meaning",
        "triage.report.col_note": "Note",
        "triage.report.col_clicks": "Clicks",
        "triage.report.col_clicks_desc": "Total click count in the analysis period",
        "triage.report.col_sessions": "Sessions",
        "triage.report.col_sessions_desc": "Number of sessions (separated by 15-min gap)",
        "triage.report.col_days": "Days",
        "triage.report.col_days_desc": "Number of distinct days with data",
        "triage.report.col_concentration": "Concentration",
        "triage.report.col_concentration_desc": "DBSCAN cluster membership ratio — how concentrated clicks are at specific coordinates",
        "triage.report.col_concentration_note": "Reference only. Fixed-UI equipment typically shows > 0.95 regardless of automation",
        "triage.report.col_cv": "CV",
        "triage.report.col_cv_desc": "Coefficient of Variation of clicks per session — how uniform session lengths are",
        "triage.report.col_cv_note": "Primary verdict signal",
        "triage.report.verdict_title": "Verdict (based on Session CV)",
        "triage.report.cv_range": "CV Range",
        "triage.report.verdict": "Verdict",
        "triage.report.meaning": "Meaning",
        "triage.report.verdict_high_desc": "Sessions have nearly identical click counts — automation pattern suspected. Prioritize for full analysis",
        "triage.report.verdict_medium_desc": "Moderate uniformity — review if resources allow",
        "triage.report.verdict_low_desc": "High variance between sessions — normal human operation",
        "triage.report.verdict_insufficient_desc": "Insufficient data (< 2 valid sessions with 3+ clicks)",
        "triage.report.limitations": "Limitations",
        "triage.report.limitations_text": "Triage uses session CV only. Click concentration is not used in verdict because fixed-UI equipment shows high concentration regardless of automation. Sequence similarity (pHash-based) is unavailable without image data.",
        "triage.report.limitations_data": "Data source is the snapshotlist table (TTL 15 days). A triage 'high' verdict is a candidate for full analysis, not a final determination.",
        "triage.report.workflow": "Recommended Workflow",
        "triage.report.workflow_step1": "Triage (10,000+ equipment)",
        "triage.report.workflow_step2": "Filter high verdict",
        "triage.report.workflow_step3": "Full analysis (3-signal)",
        "triage.report.groups_title": "Process / Model Groups",
        "triage.report.equipment": "equipment",
        "triage.report.models": "models",
        "triage.report.eqpid": "EqpID",
        "triage.report.footer": "SnapshotScreener Triage Mode — full equipment list available in CSV output",

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
        if key.startswith(("report.", "summary.", "triage.report.",
                           "flag.", "signal.", "sensitivity.",
                           "verdict.", "desc.")):
            # Convert dotted key to underscore for Jinja2: "report.title" -> "report_title"
            label_key = key.replace(".", "_")
            labels[label_key] = value
    return labels
