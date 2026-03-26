"""Collect and process images for the HTML report.

Queries Cassandra for representative frame images, resizes/compresses them,
and returns a mapping of fname -> base64 JPEG strings.
"""
from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Dict, List

from snapshot_screener.report.image_processor import process_image_for_report

if TYPE_CHECKING:
    from snapshot_screener.config import ScreenerConfig
    from snapshot_screener.db.cassandra_client import CassandraClient
    from snapshot_screener.models import FrameFeature

logger = logging.getLogger(__name__)


def collect_report_images(
    client: "CassandraClient",
    representative_features: List["FrameFeature"],
    eqpid: str,
    config: "ScreenerConfig",
) -> Dict[str, str]:
    """Collect and process images for representative frames.

    Groups features by date, queries Cassandra for each image,
    processes them for the report, and returns a dict of fname -> base64 JPEG.

    Parameters
    ----------
    client:
        Cassandra client instance for image queries.
    representative_features:
        List of FrameFeature objects that were selected as representative.
    eqpid:
        Equipment ID.
    config:
        Screener configuration.

    Returns
    -------
    dict
        Mapping of fname -> processed base64 JPEG string.
        Missing images are silently skipped.
    """
    images: Dict[str, str] = {}

    # Group features by date (extract from timestamp_ms)
    date_groups: Dict[datetime.date, List["FrameFeature"]] = {}
    for feat in representative_features:
        dt = datetime.datetime.fromtimestamp(
            feat.timestamp_ms / 1000, tz=datetime.timezone.utc
        )
        d = dt.date()
        date_groups.setdefault(d, []).append(feat)

    for d, features in sorted(date_groups.items()):
        year, month, day = d.year, d.month, d.day
        for feat in features:
            if feat.fname in images:
                continue  # already collected

            try:
                raw_b64 = client.query_image(eqpid, year, month, day, feat.fname)
                if raw_b64 is None:
                    logger.warning(
                        "Image not found for %s/%s — skipping", eqpid, feat.fname
                    )
                    continue

                processed = process_image_for_report(raw_b64)
                images[feat.fname] = processed
            except Exception:
                logger.warning(
                    "Failed to process image %s/%s — skipping",
                    eqpid,
                    feat.fname,
                    exc_info=True,
                )

    logger.info(
        "Collected %d/%d images for %s",
        len(images),
        len(representative_features),
        eqpid,
    )
    return images
