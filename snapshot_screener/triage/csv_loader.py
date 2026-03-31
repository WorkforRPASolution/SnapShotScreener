"""Load equipment hierarchy from CSV file.

CSV format (order-based, header row skipped):
  Column 1: process
  Column 2: model
  Column 3: eqpid
"""
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

from snapshot_screener.i18n import t

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EquipmentInfo:
    """Equipment identity with process/model grouping."""

    eqpid: str
    process: str
    model: str


def _detect_csv_encoding(csv_path: str) -> str:
    """Detect CSV file encoding by BOM and trial decoding."""
    with open(csv_path, "rb") as f:
        raw = f.read(4)

    # BOM detection
    if raw[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"

    # Try UTF-8 full decode
    try:
        with open(csv_path, encoding="utf-8", newline="") as f:
            f.read()
        return "utf-8"
    except UnicodeDecodeError:
        pass

    # Korean Windows default
    return "cp949"


def load_equipment_csv(csv_path: str, *, lang: str = "ko") -> List[EquipmentInfo]:
    """Parse the equipment hierarchy CSV and return a list of entries.

    The CSV is parsed by column position (not header name):
    column 0 = process, column 1 = model, column 2 = eqpid.
    The first row is treated as a header and skipped.

    Raises
    ------
    FileNotFoundError
        If *csv_path* does not exist.
    ValueError
        If the CSV has fewer than 3 columns or no data rows.
    """
    results: List[EquipmentInfo] = []
    seen: Dict[str, int] = {}

    encoding = _detect_csv_encoding(csv_path)

    with open(csv_path, encoding=encoding, newline="") as f:
        reader = csv.reader(f)

        # Skip header row
        header = next(reader, None)
        if header is None:
            raise ValueError(f"CSV file is empty: {csv_path}")
        if len(header) < 3:
            raise ValueError(
                f"CSV must have at least 3 columns "
                f"(process, model, eqpid), got {len(header)}: {csv_path}"
            )

        for line_num, row in enumerate(reader, start=2):
            if not row or all(c.strip() == "" for c in row):
                continue
            if len(row) < 3:
                logger.warning(
                    t("triage.log.csv_short", lang).format(
                        line=line_num, row=row,
                    )
                )
                continue

            process = row[0].strip()
            model = row[1].strip()
            eqpid = row[2].strip()

            if not eqpid:
                logger.warning(
                    t("triage.log.csv_blank", lang).format(line=line_num)
                )
                continue

            if eqpid in seen:
                logger.warning(
                    t("triage.log.csv_duplicate", lang).format(
                        eqpid=eqpid, line=line_num,
                    )
                )
                continue

            seen[eqpid] = line_num
            results.append(EquipmentInfo(
                eqpid=eqpid, process=process, model=model,
            ))

    if not results:
        raise ValueError(f"No valid equipment rows found in: {csv_path}")

    logger.info(
        t("triage.log.csv_loaded", lang).format(
            count=len(results), path=csv_path,
        )
    )
    return results


def group_by_process_model(
    equipment: List[EquipmentInfo],
) -> Dict[Tuple[str, str], List[EquipmentInfo]]:
    """Group equipment list by (process, model) key."""
    groups: Dict[Tuple[str, str], List[EquipmentInfo]] = {}
    for eq in equipment:
        key = (eq.process, eq.model)
        groups.setdefault(key, []).append(eq)
    return groups
