"""Command-line interface for SnapshotScreener.

Full argparse CLI matching PRD Section 6.
Supports YAML config file via ``--config`` with CLI overrides.
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from snapshot_screener.config import ScreenerConfig, TriageConfig
from snapshot_screener.i18n import t
from snapshot_screener.utils.progress import get_logger, setup_logging

logger = get_logger(__name__)


# Python 3.14 removed SecurityWarning from builtins.  Define it locally so
# that a ``warnings.warn(... SecurityWarning)`` still works regardless of
# Python version.
try:
    SecurityWarning  # type: ignore[used-before-def]
except NameError:

    class SecurityWarning(UserWarning):  # type: ignore[no-redef]
        """Warning for security-related issues (e.g. passwords on CLI)."""


def _parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD date string."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"날짜 형식이 올바르지 않습니다: {value!r} (YYYY-MM-DD 형식 필요)"
        )


def _read_eqpid_list(path: str) -> List[str]:
    """Read equipment IDs from a file, one per line."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        raise argparse.ArgumentTypeError(f"장비 목록 파일을 찾을 수 없습니다: {path!r}")
    except OSError as exc:
        raise argparse.ArgumentTypeError(f"장비 목록 파일 읽기 실패: {exc}")
    if not lines:
        raise argparse.ArgumentTypeError(f"장비 목록 파일이 비어 있습니다: {path!r}")
    return lines


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv:
        Argument list to parse.  Defaults to ``sys.argv[1:]``.

    Returns
    -------
    argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        prog="snapshot-screener",
        description="SnapshotScreener — 자동화 스크린샷 분석 도구",
    )

    # ---- Config file ----
    parser.add_argument(
        "--config",
        type=str,
        metavar="FILE",
        help="YAML 설정 파일 경로 (CLI 인자가 config 값을 오버라이드)",
    )

    # ---- Required: mutually exclusive eqpid group ----
    eqpid_group = parser.add_mutually_exclusive_group(required=False)
    eqpid_group.add_argument(
        "--eqpid",
        type=str,
        help="단일 장비 ID",
    )
    eqpid_group.add_argument(
        "--eqpid-list",
        type=str,
        metavar="FILE",
        help="장비 ID 목록 파일 (한 줄에 하나)",
    )

    # ---- Required: dates ----
    parser.add_argument(
        "--from",
        type=_parse_date,
        required=False,
        dest="date_from",
        metavar="YYYY-MM-DD",
        help="분석 시작 날짜",
    )
    parser.add_argument(
        "--to",
        type=_parse_date,
        required=False,
        dest="date_to",
        metavar="YYYY-MM-DD",
        help="분석 종료 날짜",
    )

    # ---- Required: Cassandra connection ----
    parser.add_argument(
        "--db-host",
        type=str,
        required=False,
        help="Cassandra 호스트",
    )
    parser.add_argument(
        "--db-keyspace",
        type=str,
        required=False,
        help="Cassandra 키스페이스",
    )
    parser.add_argument(
        "--db-table",
        type=str,
        required=False,
        help="Cassandra 테이블 이름",
    )

    # ---- Optional: Cassandra ----
    parser.add_argument(
        "--db-port",
        type=int,
        default=9042,
        help="Cassandra 포트 (기본값: 9042)",
    )
    parser.add_argument(
        "--db-username",
        type=str,
        default=None,
        help="Cassandra 사용자 이름",
    )
    parser.add_argument(
        "--db-password",
        type=str,
        default=None,
        help="Cassandra 비밀번호 (보안을 위해 SS_DB_PASSWORD 환경변수 권장)",
    )
    parser.add_argument(
        "--read-delay-ms",
        type=int,
        default=200,
        help="이미지 읽기 간격 (ms, 기본값: 200)",
    )
    parser.add_argument(
        "--fname-delay-ms",
        type=int,
        default=100,
        help="파일명 쿼리 간격 (ms, 기본값: 100)",
    )
    parser.add_argument(
        "--max-connections",
        type=int,
        default=2,
        help="최대 Cassandra 연결 수 (기본값: 2)",
    )

    # ---- Optional: Analysis ----
    parser.add_argument(
        "--session-gap-ms",
        type=int,
        default=900_000,
        help="세션 분리 임계값 (ms, 기본값: 900000)",
    )
    parser.add_argument(
        "--phash-similar-threshold",
        type=int,
        default=4,
        help="pHash 유사 판정 임계값 (기본값: 4)",
    )
    parser.add_argument(
        "--phash-transition-threshold",
        type=int,
        default=8,
        help="pHash 전이 판정 임계값 (기본값: 8)",
    )
    parser.add_argument(
        "--delta-spike-ms",
        type=int,
        default=30_000,
        help="시간 간격 스파이크 임계값 (ms, 기본값: 30000)",
    )
    parser.add_argument(
        "--dbscan-eps",
        type=float,
        default=0.03,
        help="DBSCAN epsilon (기본값: 0.03)",
    )
    parser.add_argument(
        "--dbscan-min-samples",
        type=int,
        default=2,
        help="DBSCAN min_samples (기본값: 2)",
    )
    parser.add_argument(
        "--screen-width",
        type=int,
        default=1920,
        help="화면 너비 (px, 기본값: 1920)",
    )
    parser.add_argument(
        "--screen-height",
        type=int,
        default=1080,
        help="화면 높이 (px, 기본값: 1080)",
    )
    parser.add_argument(
        "--selector",
        type=str,
        choices=["simple", "scored"],
        default="simple",
        help="대표 프레임 선택 전략 (기본값: simple)",
    )
    parser.add_argument(
        "--sensitivity-sweep",
        action="store_true",
        default=False,
        help="pHash 임계값 민감도 분석 실행",
    )
    parser.add_argument(
        "--fname-pattern",
        type=str,
        default="auto",
        help="파일명 패턴 (auto 또는 커스텀 정규식, 기본값: auto)",
    )

    # ---- Optional: Cache/Output ----
    parser.add_argument(
        "--cache-dir",
        type=str,
        default=".",
        help="캐시 디렉토리 (기본값: 현재 디렉토리)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="출력 디렉토리 (기본값: 현재 디렉토리)",
    )
    parser.add_argument(
        "--invalidate-cache",
        action="store_true",
        default=False,
        help="기존 캐시 무효화",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="디버그 로깅 활성화",
    )
    parser.add_argument(
        "--lang",
        type=str,
        choices=["ko", "en"],
        default="ko",
        help="출력 언어 (ko/en, 기본값: ko)",
    )

    # ---- Triage mode ----
    parser.add_argument(
        "--triage",
        action="store_true",
        default=False,
        help="트리아지 모드 활성화 (경량 fleet-wide 스크리닝)",
    )
    parser.add_argument(
        "--csv",
        type=str,
        metavar="FILE",
        help="장비 계층 CSV 파일 경로 (열 순서: process, model, eqpid)",
    )
    parser.add_argument(
        "--db-snapshotlist-table",
        type=str,
        default="snapshotlist",
        help="snapshotlist 테이블명 (기본값: snapshotlist)",
    )

    return parser.parse_args(argv), parser


def _load_yaml_config(path: str) -> Dict[str, Any]:
    """Load a YAML config file and return a flat dict of settings."""
    p = Path(path)
    if not p.exists():
        raise argparse.ArgumentTypeError(f"설정 파일을 찾을 수 없습니다: {path!r}")
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise argparse.ArgumentTypeError(f"설정 파일이 올바른 YAML이 아닙니다: {path!r}")
    return data


def _merge_config(yaml_cfg: Dict[str, Any], args: argparse.Namespace, parser: argparse.ArgumentParser) -> Dict[str, Any]:
    """Merge YAML config with CLI args.  CLI args override YAML values.

    Only CLI args that were explicitly provided by the user override YAML.
    Default values from argparse do NOT override YAML.
    """
    merged = dict(yaml_cfg)

    # Detect which CLI args were explicitly provided (not defaults)
    defaults = {k: v for k, v in vars(parser.parse_args([])).items() if k != "config"}

    for key, cli_val in vars(args).items():
        if key == "config":
            continue
        # CLI overrides YAML only if explicitly provided (different from default)
        if cli_val != defaults.get(key):
            merged[key] = cli_val

    return merged


def build_config(args: argparse.Namespace, parser: argparse.ArgumentParser = None) -> ScreenerConfig:
    """Transform parsed CLI arguments (optionally merged with YAML) into a frozen :class:`ScreenerConfig`.

    Parameters
    ----------
    args:
        Namespace from :func:`parse_args`.
    parser:
        The ArgumentParser instance (needed to detect explicit CLI overrides).

    Returns
    -------
    ScreenerConfig
    """
    # Load YAML if provided
    if args.config:
        yaml_cfg = _load_yaml_config(args.config)
        if parser is not None:
            cfg = _merge_config(yaml_cfg, args, parser)
        else:
            cfg = yaml_cfg
    else:
        cfg = vars(args)

    # Resolve equipment IDs
    eqpid = cfg.get("eqpid")
    eqpid_list = cfg.get("eqpid_list")
    eqpids_raw = cfg.get("eqpids")  # YAML can specify as list directly

    lang = cfg.get("lang", "ko")

    if eqpids_raw and isinstance(eqpids_raw, list):
        eqpids = eqpids_raw
    elif eqpid:
        eqpids = [eqpid]
    elif eqpid_list:
        eqpids = _read_eqpid_list(eqpid_list)
    else:
        raise ValueError(t("error.missing_eqpid", lang))

    # Resolve dates (YAML may provide as string)
    date_from = cfg.get("date_from")
    date_to = cfg.get("date_to")
    if isinstance(date_from, str):
        date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
    if isinstance(date_to, str):
        date_to = datetime.strptime(date_to, "%Y-%m-%d").date()
    if date_from is None or date_to is None:
        raise ValueError(t("error.missing_dates", lang))

    # Resolve password: CLI > YAML > environment variable
    db_password = cfg.get("db_password")
    if db_password is not None and getattr(args, "db_password", None) is not None:
        warnings.warn(
            t("error.password_warning", lang),
            SecurityWarning,
            stacklevel=2,
        )
    if db_password is None:
        db_password = os.environ.get("SS_DB_PASSWORD")

    db_host = cfg.get("db_host")
    if not db_host:
        raise ValueError(t("error.missing_db_host", lang))

    db_keyspace = cfg.get("db_keyspace")
    if not db_keyspace:
        raise ValueError(t("error.missing_db_keyspace", lang))

    db_table = cfg.get("db_table")
    if not db_table:
        raise ValueError(t("error.missing_db_table", lang))

    return ScreenerConfig(
        eqpids=eqpids,
        date_from=date_from,
        date_to=date_to,
        db_host=db_host,
        db_port=cfg.get("db_port", 9042),
        db_keyspace=db_keyspace,
        db_table=db_table,
        db_username=cfg.get("db_username"),
        db_password=db_password,
        read_delay_ms=cfg.get("read_delay_ms", 200),
        fname_delay_ms=cfg.get("fname_delay_ms", 100),
        max_connections=cfg.get("max_connections", 2),
        session_gap_ms=cfg.get("session_gap_ms", 900_000),
        phash_similar_threshold=cfg.get("phash_similar_threshold", 4),
        phash_transition_threshold=cfg.get("phash_transition_threshold", 8),
        delta_spike_ms=cfg.get("delta_spike_ms", 30_000),
        dbscan_eps=cfg.get("dbscan_eps", 0.03),
        dbscan_min_samples=cfg.get("dbscan_min_samples", 2),
        screen_width=cfg.get("screen_width", 1920),
        screen_height=cfg.get("screen_height", 1080),
        selector=cfg.get("selector", "simple"),
        sensitivity_sweep=cfg.get("sensitivity_sweep", False),
        fname_pattern=cfg.get("fname_pattern", "auto"),
        cache_dir=cfg.get("cache_dir", "."),
        output_dir=cfg.get("output_dir", "."),
        invalidate_cache=cfg.get("invalidate_cache", False),
        verbose=cfg.get("verbose", False),
        lang=cfg.get("lang", "ko"),
    )


def build_triage_config(
    args: argparse.Namespace, parser: argparse.ArgumentParser = None
) -> TriageConfig:
    """Build a :class:`TriageConfig` from CLI args (optionally merged with YAML)."""
    if args.config:
        yaml_cfg = _load_yaml_config(args.config)
        if parser is not None:
            cfg = _merge_config(yaml_cfg, args, parser)
        else:
            cfg = yaml_cfg
    else:
        cfg = vars(args)

    lang = cfg.get("lang", "ko")

    csv_path = cfg.get("csv")
    if not csv_path:
        raise ValueError("트리아지 모드에서 --csv 는 필수입니다")

    # Resolve CSV path relative to config file directory
    if args.config and not Path(csv_path).is_absolute():
        config_dir = Path(args.config).resolve().parent
        resolved = config_dir / csv_path
        if resolved.exists():
            csv_path = str(resolved)

    # Resolve dates — auto-default to last 14 days if not specified
    date_from = cfg.get("date_from")
    date_to = cfg.get("date_to")
    if isinstance(date_from, str):
        date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
    if isinstance(date_to, str):
        date_to = datetime.strptime(date_to, "%Y-%m-%d").date()
    if date_from is None or date_to is None:
        from datetime import timedelta
        date_to = date_to or (date.today() - timedelta(days=1))
        date_from = date_from or (date_to - timedelta(days=13))

    db_host = cfg.get("db_host")
    if not db_host:
        raise ValueError(t("error.missing_db_host", lang))
    db_keyspace = cfg.get("db_keyspace")
    if not db_keyspace:
        raise ValueError(t("error.missing_db_keyspace", lang))

    db_password = cfg.get("db_password")
    if db_password is None:
        db_password = os.environ.get("SS_DB_PASSWORD")

    return TriageConfig(
        csv_path=csv_path,
        date_from=date_from,
        date_to=date_to,
        db_host=db_host,
        db_keyspace=db_keyspace,
        db_snapshotlist_table=cfg.get("db_snapshotlist_table", "snapshotlist"),
        db_port=cfg.get("db_port", 9042),
        db_username=cfg.get("db_username"),
        db_password=db_password,
        fname_delay_ms=cfg.get("fname_delay_ms", 50),
        read_delay_ms=cfg.get("read_delay_ms", 50),
        db_table=cfg.get("db_snapshotlist_table", "snapshotlist"),
        max_connections=cfg.get("max_connections", 2),
        session_gap_ms=cfg.get("session_gap_ms", 900_000),
        dbscan_eps=cfg.get("dbscan_eps", 0.03),
        dbscan_min_samples=cfg.get("dbscan_min_samples", 2),
        screen_width=cfg.get("screen_width", 1920),
        screen_height=cfg.get("screen_height", 1080),
        fname_pattern=cfg.get("fname_pattern", "auto"),
        output_dir=cfg.get("output_dir", "."),
        circuit_breaker_threshold=cfg.get("circuit_breaker_threshold", 10),
        health_check_interval=cfg.get("health_check_interval", 500),
        verbose=cfg.get("verbose", False),
        lang=lang,
    )


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the snapshot-screener CLI.

    Parameters
    ----------
    argv:
        Argument list to parse.  Defaults to ``sys.argv[1:]``.

    Returns
    -------
    int
        Exit code: 0 success, 1 user error, 2 analysis error, 3 connection failure.
    """
    args, parser = parse_args(argv)
    setup_logging(args.verbose)

    lang = getattr(args, "lang", "ko")

    # ---- Triage mode (CLI flag or config file) ----
    triage_from_config = False
    if args.config and not getattr(args, "triage", False):
        _peek = _load_yaml_config(args.config)
        triage_from_config = _peek.get("triage", False)

    if getattr(args, "triage", False) or triage_from_config:
        from snapshot_screener.triage.pipeline import run_triage

        try:
            triage_config = build_triage_config(args, parser)
            lang = triage_config.lang
        except (ValueError, argparse.ArgumentTypeError) as e:
            logger.error(t("error.config_error", lang).format(e=e))
            return 1

        try:
            run_triage(triage_config)
            return 0
        except KeyboardInterrupt:
            logger.info(t("error.interrupted", lang))
            return 130
        except ConnectionError as e:
            logger.error(t("error.cassandra_failed", lang).format(e=e))
            return 3
        except Exception as e:
            logger.error(t("error.analysis_error", lang).format(e=e))
            return 2

    # ---- Normal mode ----
    from snapshot_screener.pipeline import run_pipeline

    try:
        config = build_config(args, parser)
        lang = config.lang
    except (ValueError, argparse.ArgumentTypeError) as e:
        logger.error(t("error.config_error", lang).format(e=e))
        return 1

    try:
        run_pipeline(config)
        return 0
    except KeyboardInterrupt:
        logger.info(t("error.interrupted", lang))
        return 130
    except ConnectionError as e:
        logger.error(t("error.cassandra_failed", lang).format(e=e))
        return 3
    except ValueError as e:
        logger.error(t("error.config_error", lang).format(e=e))
        return 1
    except Exception as e:
        logger.error(t("error.analysis_error", lang).format(e=e))
        return 2
