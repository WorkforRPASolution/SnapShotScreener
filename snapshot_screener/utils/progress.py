"""Logging and progress utilities.

Named ``progress.py`` (not ``logging.py``) to avoid shadowing the stdlib
``logging`` module.
"""
import logging


def setup_logging(verbose: bool = False) -> None:
    """Configure root logging with ``[HH:MM:SS] message`` format.

    Parameters
    ----------
    verbose:
        If *True*, set level to DEBUG; otherwise INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "[%(asctime)s] %(message)s"
    datefmt = "%H:%M:%S"

    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, force=True)

    # Suppress cassandra-driver internal logs (connection retries, protocol downgrades, stacktraces).
    # We catch and re-raise all errors with clean Korean messages.
    logging.getLogger("cassandra").setLevel(logging.CRITICAL)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger.

    Parameters
    ----------
    name:
        Logger name, typically ``__name__`` of the calling module.
    """
    return logging.getLogger(name)


def log_progress(
    logger: logging.Logger,
    current: int,
    total: int,
    prefix: str = "",
) -> None:
    """Log a progress message like ``[Phase 1] [3/14] 21.4%``.

    Parameters
    ----------
    logger:
        Logger instance to use.
    current:
        Current step (1-based).
    total:
        Total number of steps.
    prefix:
        Optional prefix such as ``"[Phase 1]"``.
    """
    if total > 0:
        pct = current / total * 100
    else:
        pct = 0.0

    parts: list[str] = []
    if prefix:
        parts.append(prefix)
    parts.append(f"[{current}/{total}]")
    parts.append(f"{pct:.1f}%")

    logger.info(" ".join(parts))
