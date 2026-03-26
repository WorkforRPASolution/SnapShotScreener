"""Tests for snapshot_screener.collect (metadata + phash modules)."""
from __future__ import annotations

import base64
import io
from datetime import date
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from snapshot_screener.collect.metadata import collect_metadata
from snapshot_screener.collect.phash import collect_phash
from snapshot_screener.config import ScreenerConfig
from snapshot_screener.db.cache import PhashCache
from snapshot_screener.models import FrameFeature, SnapshotMeta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    date_from: date = date(2026, 3, 13),
    date_to: date = date(2026, 3, 15),
    fname_pattern: str = "auto",
    screen_width: int = 1920,
    screen_height: int = 1080,
) -> ScreenerConfig:
    """Create a minimal ScreenerConfig for testing."""
    return ScreenerConfig(
        eqpids=["EQ-2471"],
        date_from=date_from,
        date_to=date_to,
        db_host="localhost",
        db_port=9042,
        fname_pattern=fname_pattern,
        screen_width=screen_width,
        screen_height=screen_height,
        cache_dir=".",
    )


def _make_tiny_png_b64(width: int = 4, height: int = 4) -> str:
    """Create a tiny PNG image and return its Base64-encoded string."""
    img = Image.new("RGB", (width, height), color=(128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img.close()
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ---------------------------------------------------------------------------
# Phase 1: collect_metadata
# ---------------------------------------------------------------------------


class TestCollectMetadata:
    """Tests for collect_metadata (Phase 1)."""

    def test_basic_collection_and_sorting(self) -> None:
        """Filenames are parsed and results are sorted by timestamp_ms."""
        config = _make_config(
            date_from=date(2026, 3, 13),
            date_to=date(2026, 3, 14),
        )

        # Day 1 returns two fnames (out of timestamp order)
        # Day 2 returns one fname with an earlier timestamp
        mock_client = MagicMock()
        mock_client.query_fnames.side_effect = [
            # Day 2026-03-13: two files, second has earlier ts
            [
                "500_300_1710300000000.png",  # ts = 1710300000000
                "100_200_1710200000000.png",  # ts = 1710200000000
            ],
            # Day 2026-03-14: one file with ts between the two above
            [
                "400_250_1710250000000.png",  # ts = 1710250000000
            ],
        ]

        result = collect_metadata(mock_client, "EQ-2471", config)

        assert len(result) == 3
        # Verify sorted by timestamp
        assert result[0].timestamp_ms == 1710200000000
        assert result[1].timestamp_ms == 1710250000000
        assert result[2].timestamp_ms == 1710300000000

        # Verify fields
        assert result[0].eqpid == "EQ-2471"
        assert result[0].fname == "100_200_1710200000000.png"
        assert result[0].x == 100
        assert result[0].y == 200

    def test_parse_failures_skipped(self) -> None:
        """Unparseable filenames are skipped with a warning."""
        config = _make_config(
            date_from=date(2026, 3, 13),
            date_to=date(2026, 3, 13),
        )

        mock_client = MagicMock()
        mock_client.query_fnames.return_value = [
            "100_200_1710000000000.png",  # valid
            "bad_filename.txt",  # invalid
            "no_match.png",  # invalid (only 2 fields)
            "300_400_1710000001000.png",  # valid
        ]

        result = collect_metadata(mock_client, "EQ-2471", config)

        assert len(result) == 2
        fnames = [m.fname for m in result]
        assert "100_200_1710000000000.png" in fnames
        assert "300_400_1710000001000.png" in fnames

    def test_query_failure_skips_day(self) -> None:
        """If query_fnames raises, that day is skipped."""
        config = _make_config(
            date_from=date(2026, 3, 13),
            date_to=date(2026, 3, 15),
        )

        mock_client = MagicMock()
        mock_client.query_fnames.side_effect = [
            ["100_200_1710000000000.png"],  # day 13 OK
            RuntimeError("Cassandra timeout"),  # day 14 fails
            ["300_400_1710000002000.png"],  # day 15 OK
        ]

        result = collect_metadata(mock_client, "EQ-2471", config)

        assert len(result) == 2

    def test_empty_range(self) -> None:
        """Single-day range with no files returns empty list."""
        config = _make_config(
            date_from=date(2026, 3, 13),
            date_to=date(2026, 3, 13),
        )

        mock_client = MagicMock()
        mock_client.query_fnames.return_value = []

        result = collect_metadata(mock_client, "EQ-2471", config)

        assert result == []


# ---------------------------------------------------------------------------
# Phase 2: collect_phash
# ---------------------------------------------------------------------------


class TestCollectPhash:
    """Tests for collect_phash (Phase 2)."""

    def test_cache_hit(self, tmp_path) -> None:
        """Entries already in cache should not trigger image queries."""
        config = _make_config()
        cache = PhashCache(cache_dir=str(tmp_path))

        # Pre-populate cache
        cache.put("EQ-2471", "100_200_1710000000000.png", "abcdef0123456789", 1920, 1080)

        metas = [
            SnapshotMeta(
                eqpid="EQ-2471",
                fname="100_200_1710000000000.png",
                timestamp_ms=1710000000000,
                x=100,
                y=200,
            ),
        ]

        mock_client = MagicMock()

        features = collect_phash(mock_client, cache, metas, config)

        assert len(features) == 1
        assert features[0].phash == "abcdef0123456789"
        # No image queries should have been made
        mock_client.query_image.assert_not_called()

        cache.close()

    def test_cache_miss_fetches_and_caches(self, tmp_path) -> None:
        """Cache misses trigger image fetch, hash, and cache storage."""
        config = _make_config()
        cache = PhashCache(cache_dir=str(tmp_path))

        b64_img = _make_tiny_png_b64(4, 4)

        metas = [
            SnapshotMeta(
                eqpid="EQ-2471",
                fname="100_200_1710000000000.png",
                timestamp_ms=1710000000000,
                x=100,
                y=200,
            ),
        ]

        mock_client = MagicMock()
        mock_client.query_image.return_value = b64_img

        features = collect_phash(mock_client, cache, metas, config)

        assert len(features) == 1
        assert features[0].phash is not None
        assert len(features[0].phash) == 16  # 64-bit pHash = 16 hex chars

        # Verify it was cached
        entry = cache.get("EQ-2471", "100_200_1710000000000.png")
        assert entry is not None
        assert entry.phash == features[0].phash
        assert entry.image_w == 4
        assert entry.image_h == 4

        cache.close()

    def test_mixed_cache_hits_and_misses(self, tmp_path) -> None:
        """Mix of cache hits and misses: only misses trigger queries."""
        config = _make_config()
        cache = PhashCache(cache_dir=str(tmp_path))

        # Pre-cache one entry
        cache.put("EQ-2471", "100_200_1710000000000.png", "aaaa000000000000", 1920, 1080)

        b64_img = _make_tiny_png_b64(8, 8)

        metas = [
            SnapshotMeta(
                eqpid="EQ-2471",
                fname="100_200_1710000000000.png",
                timestamp_ms=1710000000000,
                x=100,
                y=200,
            ),
            SnapshotMeta(
                eqpid="EQ-2471",
                fname="300_400_1710000001000.png",
                timestamp_ms=1710000001000,
                x=300,
                y=400,
            ),
        ]

        mock_client = MagicMock()
        mock_client.query_image.return_value = b64_img

        features = collect_phash(mock_client, cache, metas, config)

        assert len(features) == 2
        # First one from cache
        assert features[0].phash == "aaaa000000000000"
        # Second one freshly computed
        assert features[1].phash is not None

        # Only one image query (for the miss)
        mock_client.query_image.assert_called_once()

        cache.close()

    def test_base64_decoding_pipeline(self, tmp_path) -> None:
        """End-to-end test: real tiny PNG -> base64 -> decode -> pHash."""
        # Create a specific image with known content
        img = Image.new("RGB", (16, 16), color=(255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img.close()
        b64_text = base64.b64encode(buf.getvalue()).decode("ascii")

        # Decode and hash -- verify the pipeline works
        decoded = base64.b64decode(b64_text)
        img2 = Image.open(io.BytesIO(decoded))
        assert img2.size == (16, 16)

        import imagehash
        phash_val = str(imagehash.phash(img2))
        img2.close()

        assert len(phash_val) == 16  # 64-bit hash = 16 hex chars
        assert all(c in "0123456789abcdef" for c in phash_val)

    def test_query_image_failure_skips(self, tmp_path) -> None:
        """If query_image raises, the entry is skipped gracefully."""
        config = _make_config()
        cache = PhashCache(cache_dir=str(tmp_path))

        metas = [
            SnapshotMeta(
                eqpid="EQ-2471",
                fname="100_200_1710000000000.png",
                timestamp_ms=1710000000000,
                x=100,
                y=200,
            ),
            SnapshotMeta(
                eqpid="EQ-2471",
                fname="300_400_1710000001000.png",
                timestamp_ms=1710000001000,
                x=300,
                y=400,
            ),
        ]

        mock_client = MagicMock()
        b64_img = _make_tiny_png_b64(4, 4)
        # First image query fails, second succeeds
        mock_client.query_image.side_effect = [
            RuntimeError("Cassandra error"),
            b64_img,
        ]

        features = collect_phash(mock_client, cache, metas, config)

        # Only the second entry survives
        assert len(features) == 1
        assert features[0].fname == "300_400_1710000001000.png"

        cache.close()

    def test_query_image_returns_none_skips(self, tmp_path) -> None:
        """If query_image returns None, the entry is skipped."""
        config = _make_config()
        cache = PhashCache(cache_dir=str(tmp_path))

        metas = [
            SnapshotMeta(
                eqpid="EQ-2471",
                fname="100_200_1710000000000.png",
                timestamp_ms=1710000000000,
                x=100,
                y=200,
            ),
        ]

        mock_client = MagicMock()
        mock_client.query_image.return_value = None

        features = collect_phash(mock_client, cache, metas, config)

        assert len(features) == 0

        cache.close()

    def test_empty_metas_returns_empty(self, tmp_path) -> None:
        """Empty metas list returns empty features list."""
        config = _make_config()
        cache = PhashCache(cache_dir=str(tmp_path))
        mock_client = MagicMock()

        features = collect_phash(mock_client, cache, [], config)

        assert features == []

        cache.close()

    def test_normalization_uses_image_dimensions(self, tmp_path) -> None:
        """When image dimensions are in cache, use them for normalization."""
        config = _make_config(screen_width=1920, screen_height=1080)
        cache = PhashCache(cache_dir=str(tmp_path))

        # Cache with specific image dimensions
        cache.put("EQ-2471", "960_540_1710000000000.png", "abcdef0123456789", 3840, 2160)

        metas = [
            SnapshotMeta(
                eqpid="EQ-2471",
                fname="960_540_1710000000000.png",
                timestamp_ms=1710000000000,
                x=960,
                y=540,
            ),
        ]

        mock_client = MagicMock()

        features = collect_phash(mock_client, cache, metas, config)

        assert len(features) == 1
        # Should use image dimensions (3840x2160), not config (1920x1080)
        assert features[0].x_norm == pytest.approx(960 / 3840)
        assert features[0].y_norm == pytest.approx(540 / 2160)

        cache.close()

    def test_normalization_fallback_to_config(self, tmp_path) -> None:
        """When image dimensions are absent, fall back to config screen size."""
        config = _make_config(screen_width=1920, screen_height=1080)
        cache = PhashCache(cache_dir=str(tmp_path))

        # Cache without image dimensions
        cache.put("EQ-2471", "960_540_1710000000000.png", "abcdef0123456789", None, None)

        metas = [
            SnapshotMeta(
                eqpid="EQ-2471",
                fname="960_540_1710000000000.png",
                timestamp_ms=1710000000000,
                x=960,
                y=540,
            ),
        ]

        mock_client = MagicMock()

        features = collect_phash(mock_client, cache, metas, config)

        assert len(features) == 1
        # Should fall back to config dimensions (1920x1080)
        assert features[0].x_norm == pytest.approx(960 / 1920)
        assert features[0].y_norm == pytest.approx(540 / 1080)

        cache.close()

    def test_output_sorted_same_as_metas(self, tmp_path) -> None:
        """Output features maintain the same order as input metas."""
        config = _make_config()
        cache = PhashCache(cache_dir=str(tmp_path))
        b64_img = _make_tiny_png_b64(4, 4)

        metas = [
            SnapshotMeta(
                eqpid="EQ-2471",
                fname=f"100_200_{ts}.png",
                timestamp_ms=ts,
                x=100,
                y=200,
            )
            for ts in [1710000000000, 1710000001000, 1710000002000]
        ]

        mock_client = MagicMock()
        mock_client.query_image.return_value = b64_img

        features = collect_phash(mock_client, cache, metas, config)

        assert len(features) == 3
        assert [f.timestamp_ms for f in features] == [
            1710000000000,
            1710000001000,
            1710000002000,
        ]

        cache.close()
