"""Command-line interface for SnapshotScreener.

Full argparse CLI matching PRD Section 6.
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings
from datetime import date, datetime
from typing import List, Optional

from snapshot_screener.config import ScreenerConfig
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

    # ---- Required: mutually exclusive eqpid group ----
    eqpid_group = parser.add_mutually_exclusive_group(required=True)
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
        required=True,
        dest="date_from",
        metavar="YYYY-MM-DD",
        help="분석 시작 날짜",
    )
    parser.add_argument(
        "--to",
        type=_parse_date,
        required=True,
        dest="date_to",
        metavar="YYYY-MM-DD",
        help="분석 종료 날짜",
    )

    # ---- Required: Cassandra connection ----
    parser.add_argument(
        "--db-host",
        type=str,
        required=True,
        help="Cassandra 호스트",
    )
    parser.add_argument(
        "--db-keyspace",
        type=str,
        required=True,
        help="Cassandra 키스페이스",
    )
    parser.add_argument(
        "--db-table",
        type=str,
        required=True,
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
        help="파일명 패턴 (auto|xy_ts|ts_xy|custom regex, 기본값: auto)",
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

    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> ScreenerConfig:
    """Transform parsed CLI arguments into a frozen :class:`ScreenerConfig`.

    Parameters
    ----------
    args:
        Namespace from :func:`parse_args`.

    Returns
    -------
    ScreenerConfig
    """
    # Resolve equipment IDs
    if args.eqpid:
        eqpids = [args.eqpid]
    else:
        eqpids = _read_eqpid_list(args.eqpid_list)

    # Resolve password: CLI > environment variable
    db_password = args.db_password
    if db_password is not None:
        warnings.warn(
            "비밀번호를 명령줄 인수로 전달하는 것은 안전하지 않습니다. "
            "SS_DB_PASSWORD 환경변수를 사용하세요.",
            SecurityWarning,
            stacklevel=2,
        )
    else:
        db_password = os.environ.get("SS_DB_PASSWORD")

    return ScreenerConfig(
        eqpids=eqpids,
        date_from=args.date_from,
        date_to=args.date_to,
        db_host=args.db_host,
        db_port=args.db_port,
        db_keyspace=args.db_keyspace,
        db_table=args.db_table,
        db_username=args.db_username,
        db_password=db_password,
        read_delay_ms=args.read_delay_ms,
        fname_delay_ms=args.fname_delay_ms,
        max_connections=args.max_connections,
        session_gap_ms=args.session_gap_ms,
        phash_similar_threshold=args.phash_similar_threshold,
        phash_transition_threshold=args.phash_transition_threshold,
        delta_spike_ms=args.delta_spike_ms,
        dbscan_eps=args.dbscan_eps,
        dbscan_min_samples=args.dbscan_min_samples,
        screen_width=args.screen_width,
        screen_height=args.screen_height,
        selector=args.selector,
        sensitivity_sweep=args.sensitivity_sweep,
        fname_pattern=args.fname_pattern,
        cache_dir=args.cache_dir,
        output_dir=args.output_dir,
        invalidate_cache=args.invalidate_cache,
        verbose=args.verbose,
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
    # Lazy import to avoid circular dependency at module level
    from snapshot_screener.pipeline import run_pipeline

    args = parse_args(argv)
    setup_logging(args.verbose)

    try:
        config = build_config(args)
    except (ValueError, argparse.ArgumentTypeError) as e:
        logger.error(f"설정 오류: {e}")
        return 1

    try:
        run_pipeline(config)
        return 0
    except KeyboardInterrupt:
        logger.info("중단됨 — 캐시를 정리하는 중...")
        return 130
    except ConnectionError as e:
        logger.error(f"Cassandra 연결 실패: {e}")
        return 3
    except ValueError as e:
        logger.error(f"설정 오류: {e}")
        return 1
    except Exception as e:
        logger.error(f"분석 오류: {e}")
        return 2
