"""Tests for snapshot_screener.db.cache — PhashCache."""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from snapshot_screener.db.cache import CacheEntry, PhashCache


# ---------------------------------------------------------------------------
# 1. put + get round-trip
# ---------------------------------------------------------------------------


def test_put_and_get(tmp_path):
    """Create cache, put entry, get it back — verify all fields."""
    with PhashCache(cache_dir=str(tmp_path)) as cache:
        cache.put("EQ-001", "img_001.png", "abcdef1234567890", image_w=1920, image_h=1080)
        entry = cache.get("EQ-001", "img_001.png")

    assert entry is not None
    assert entry.phash == "abcdef1234567890"
    assert entry.image_w == 1920
    assert entry.image_h == 1080
    assert entry.cached_at  # non-empty


# ---------------------------------------------------------------------------
# 2. get_bulk with mix of hits and misses
# ---------------------------------------------------------------------------


def test_get_bulk_hits_and_misses(tmp_path):
    """get_bulk returns only cached entries; misses are omitted."""
    with PhashCache(cache_dir=str(tmp_path)) as cache:
        cache.put("EQ-001", "a.png", "aaaa", image_w=100, image_h=100)
        cache.put("EQ-001", "b.png", "bbbb", image_w=200, image_h=200)

        result = cache.get_bulk("EQ-001", ["a.png", "b.png", "c.png"])

    assert set(result.keys()) == {"a.png", "b.png"}
    assert "c.png" not in result
    assert result["a.png"].phash == "aaaa"
    assert result["b.png"].phash == "bbbb"


# ---------------------------------------------------------------------------
# 3. put overwrites existing entry (INSERT OR REPLACE)
# ---------------------------------------------------------------------------


def test_put_overwrites_existing(tmp_path):
    """A second put for the same (eqpid, fname) replaces the row."""
    with PhashCache(cache_dir=str(tmp_path)) as cache:
        cache.put("EQ-001", "img.png", "old_hash", image_w=100, image_h=100)
        cache.put("EQ-001", "img.png", "new_hash", image_w=200, image_h=200)
        entry = cache.get("EQ-001", "img.png")

    assert entry is not None
    assert entry.phash == "new_hash"
    assert entry.image_w == 200
    assert entry.image_h == 200


# ---------------------------------------------------------------------------
# 4. invalidate with eqpid — only deletes that equipment
# ---------------------------------------------------------------------------


def test_invalidate_with_eqpid(tmp_path):
    """invalidate(eqpid=...) removes only that equipment's entries."""
    with PhashCache(cache_dir=str(tmp_path)) as cache:
        cache.put("EQ-001", "a.png", "hash1")
        cache.put("EQ-001", "b.png", "hash2")
        cache.put("EQ-002", "c.png", "hash3")

        deleted = cache.invalidate(eqpid="EQ-001")

    assert deleted == 2
    # Re-open to verify persistent state
    with PhashCache(cache_dir=str(tmp_path)) as cache:
        assert cache.get("EQ-001", "a.png") is None
        assert cache.get("EQ-001", "b.png") is None
        assert cache.get("EQ-002", "c.png") is not None


# ---------------------------------------------------------------------------
# 5. invalidate without eqpid — deletes everything
# ---------------------------------------------------------------------------


def test_invalidate_all(tmp_path):
    """invalidate() with no arguments deletes all rows."""
    with PhashCache(cache_dir=str(tmp_path)) as cache:
        cache.put("EQ-001", "a.png", "h1")
        cache.put("EQ-002", "b.png", "h2")

        deleted = cache.invalidate()

    assert deleted == 2
    with PhashCache(cache_dir=str(tmp_path)) as cache:
        assert cache.get("EQ-001", "a.png") is None
        assert cache.get("EQ-002", "b.png") is None


# ---------------------------------------------------------------------------
# 6. get returns None for non-existent entry
# ---------------------------------------------------------------------------


def test_get_returns_none_for_missing(tmp_path):
    """get() returns None when the key does not exist."""
    with PhashCache(cache_dir=str(tmp_path)) as cache:
        assert cache.get("EQ-NONE", "nope.png") is None


# ---------------------------------------------------------------------------
# 7. Schema version mismatch raises ValueError
# ---------------------------------------------------------------------------


def test_schema_version_mismatch(tmp_path):
    """Opening a DB with wrong schema_version raises ValueError."""
    # Create a valid cache first, then tamper with the version
    cache = PhashCache(cache_dir=str(tmp_path))
    cache._conn.execute("UPDATE _meta SET value = '99' WHERE key = 'schema_version'")
    cache._conn.commit()
    cache.close()

    with pytest.raises(ValueError, match="schema version mismatch"):
        PhashCache(cache_dir=str(tmp_path))


# ---------------------------------------------------------------------------
# 8. Context manager — verify close is called
# ---------------------------------------------------------------------------


def test_context_manager_calls_close(tmp_path):
    """__exit__ delegates to close()."""
    cache = PhashCache(cache_dir=str(tmp_path))
    with patch.object(cache, "close", wraps=cache.close) as mock_close:
        with cache:
            cache.put("EQ-001", "a.png", "h")
        mock_close.assert_called_once()


# ---------------------------------------------------------------------------
# 9. WAL mode is enabled
# ---------------------------------------------------------------------------


def test_wal_mode_enabled(tmp_path):
    """The database should be in WAL journal mode."""
    with PhashCache(cache_dir=str(tmp_path)) as cache:
        cur = cache._conn.execute("PRAGMA journal_mode")
        mode = cur.fetchone()[0]
    assert mode.lower() == "wal"


# ---------------------------------------------------------------------------
# 10. cached_at is auto-populated with ISO 8601 format
# ---------------------------------------------------------------------------


def test_cached_at_is_iso8601(tmp_path):
    """put() auto-sets cached_at to a valid ISO 8601 UTC timestamp."""
    with PhashCache(cache_dir=str(tmp_path)) as cache:
        cache.put("EQ-001", "a.png", "hash")
        entry = cache.get("EQ-001", "a.png")

    assert entry is not None
    # ISO 8601 with timezone: e.g. 2026-03-26T12:34:56.123456+00:00
    iso_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    assert re.match(iso_pattern, entry.cached_at), (
        f"cached_at does not look like ISO 8601: {entry.cached_at}"
    )


# ---------------------------------------------------------------------------
# Extra: get_bulk with empty list
# ---------------------------------------------------------------------------


def test_get_bulk_empty_list(tmp_path):
    """get_bulk with an empty fname list returns an empty dict."""
    with PhashCache(cache_dir=str(tmp_path)) as cache:
        result = cache.get_bulk("EQ-001", [])
    assert result == {}
