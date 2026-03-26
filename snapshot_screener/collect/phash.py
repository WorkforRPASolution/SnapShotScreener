"""Phase 2 data collection: pHash computation for all snapshot images.

Reads every image from Cassandra (using the cache to skip previously
computed hashes), computes the perceptual hash, and builds a list of
:class:`FrameFeature` records.

**Important:** Phase 2 reads ALL images for pHash -- not just
representative frames.  One image is kept in memory at a time to
minimise peak memory usage.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from io import BytesIO
from typing import TYPE_CHECKING, Dict, List, Optional

import imagehash
from PIL import Image

from snapshot_screener.db.cache import CacheEntry, PhashCache
from snapshot_screener.models import FrameFeature, SnapshotMeta
from snapshot_screener.utils.progress import get_logger, log_progress

if TYPE_CHECKING:
    from snapshot_screener.config import ScreenerConfig
    from snapshot_screener.db.cassandra_client import CassandraClient

logger = get_logger(__name__)


def _timestamp_ms_to_ymd(timestamp_ms: int) -> tuple[int, int, int]:
    """Convert millisecond timestamp to ``(year, month, day)``."""
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    return dt.year, dt.month, dt.day


def collect_phash(
    client: "CassandraClient",
    cache: PhashCache,
    metas: List[SnapshotMeta],
    config: "ScreenerConfig",
) -> List[FrameFeature]:
    """Collect pHash values (Phase 2) for all snapshot images.

    For each :class:`SnapshotMeta`, looks up the pHash in the local
    SQLite cache.  On cache miss the image is fetched from Cassandra,
    decoded, hashed, and stored in the cache.

    One image is held in memory at a time.  Failed image queries are
    logged and skipped.

    Parameters
    ----------
    client:
        Connected Cassandra client.
    cache:
        SQLite-backed pHash cache.
    metas:
        Metadata records produced by Phase 1 (already sorted).
    config:
        Screener configuration (provides screen dimensions for
        coordinate normalisation).

    Returns
    -------
    list[FrameFeature]
        Feature records sorted by ``timestamp_ms``, same order as
        *metas*.  Entries whose images could not be fetched are omitted.
    """
    if not metas:
        return []

    eqpid = metas[0].eqpid

    # ------------------------------------------------------------------
    # 1. Bulk cache lookup
    # ------------------------------------------------------------------
    all_fnames = [m.fname for m in metas]
    cached: Dict[str, CacheEntry] = cache.get_bulk(eqpid, all_fnames)

    cache_hits = len(cached)
    cache_misses_fnames = [f for f in all_fnames if f not in cached]
    total_misses = len(cache_misses_fnames)

    logger.info(
        "[Phase 2] %s: %d cache hits, %d cache misses",
        eqpid,
        cache_hits,
        total_misses,
    )

    # ------------------------------------------------------------------
    # 2. Fetch & hash cache misses
    # ------------------------------------------------------------------
    # Build a quick lookup from fname -> meta for misses
    meta_by_fname: Dict[str, SnapshotMeta] = {m.fname: m for m in metas}

    for miss_idx, fname in enumerate(cache_misses_fnames, start=1):
        meta = meta_by_fname[fname]
        year, month, day = _timestamp_ms_to_ymd(meta.timestamp_ms)

        # Fetch image from Cassandra
        try:
            b64_text: Optional[str] = client.query_image(
                eqpid, year, month, day, fname
            )
        except Exception as exc:
            logger.warning(
                "[Phase 2] Failed to query image %s/%s: %s",
                eqpid,
                fname,
                exc,
            )
            continue

        if b64_text is None:
            logger.warning(
                "[Phase 2] No image data for %s/%s, skipping",
                eqpid,
                fname,
            )
            continue

        # Decode, hash, release
        try:
            image_bytes = base64.b64decode(b64_text)
            img = Image.open(BytesIO(image_bytes))
            image_w, image_h = img.size
            phash_val = str(imagehash.phash(img))
            img.close()
            del image_bytes, img  # explicit memory release
        except Exception as exc:
            logger.warning(
                "[Phase 2] Failed to decode/hash image %s/%s: %s",
                eqpid,
                fname,
                exc,
            )
            continue

        # Store in cache
        cache.put(eqpid, fname, phash_val, image_w, image_h)
        cached[fname] = CacheEntry(
            phash=phash_val,
            image_w=image_w,
            image_h=image_h,
            cached_at="",  # not used downstream
        )

        # Log progress periodically
        if miss_idx % 50 == 0 or miss_idx == total_misses:
            log_progress(
                logger,
                miss_idx,
                total_misses,
                f"[Phase 2] {eqpid} image hashing",
            )

    # ------------------------------------------------------------------
    # 3. Build FrameFeature list
    # ------------------------------------------------------------------
    screen_w = config.screen_width
    screen_h = config.screen_height

    features: List[FrameFeature] = []
    for meta in metas:
        entry = cached.get(meta.fname)
        if entry is None:
            # Image could not be fetched/hashed -- skip
            logger.debug(
                "[Phase 2] Skipping %s/%s (no cache entry after Phase 2)",
                eqpid,
                meta.fname,
            )
            continue

        # Normalise coordinates using image dimensions if available,
        # falling back to configured screen dimensions.
        norm_w = entry.image_w if entry.image_w else screen_w
        norm_h = entry.image_h if entry.image_h else screen_h

        x_norm = meta.x / norm_w if norm_w else 0.0
        y_norm = meta.y / norm_h if norm_h else 0.0

        features.append(
            FrameFeature(
                eqpid=meta.eqpid,
                fname=meta.fname,
                timestamp_ms=meta.timestamp_ms,
                x=meta.x,
                y=meta.y,
                x_norm=x_norm,
                y_norm=y_norm,
                phash=entry.phash,
                _phase_completed=2,
            )
        )

    logger.info(
        "[Phase 2] Built %d FrameFeature records for %s",
        len(features),
        eqpid,
    )

    return features
