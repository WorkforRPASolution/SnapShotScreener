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

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EquipmentInfo:
    """Equipment identity with process/model grouping."""

    eqpid: str
    process: str
    model: str


def load_equipment_csv(csv_path: str) -> List[EquipmentInfo]:
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

    with open(csv_path, encoding="utf-8-sig", newline="") as f:
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
                    "Skipping CSV line %d: fewer than 3 columns", line_num
                )
                continue

            process = row[0].strip()
            model = row[1].strip()
            eqpid = row[2].strip()

            if not eqpid:
                logger.warning(
                    "Skipping CSV line %d: empty eqpid", line_num
                )
                continue

            if eqpid in seen:
                logger.warning(
                    "Duplicate eqpid '%s' at line %d "
                    "(first seen at line %d), skipping",
                    eqpid,
                    line_num,
                    seen[eqpid],
                )
                continue

            seen[eqpid] = line_num
            results.append(EquipmentInfo(
                eqpid=eqpid, process=process, model=model,
            ))

    if not results:
        raise ValueError(f"No valid equipment rows found in: {csv_path}")

    logger.info("Loaded %d equipment from CSV: %s", len(results), csv_path)
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
