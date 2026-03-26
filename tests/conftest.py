"""Shared pytest fixtures for SnapshotScreener tests."""
from __future__ import annotations

import random
from typing import List, Optional, Tuple

import pytest

from snapshot_screener.models import FrameFeature, SnapshotMeta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hex_to_bits(hex_str: str) -> list[int]:
    """Convert a hex string to a list of bits."""
    return [int(b) for h in hex_str for b in format(int(h, 16), "04b")]


def _bits_to_hex(bits: list[int]) -> str:
    """Convert a list of bits back to a hex string."""
    hex_chars = []
    for i in range(0, len(bits), 4):
        nibble = bits[i : i + 4]
        val = sum(b << (3 - j) for j, b in enumerate(nibble))
        hex_chars.append(format(val, "x"))
    return "".join(hex_chars)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_phash_pair():
    """Factory fixture: generate two pHash hex strings with exact Hamming distance.

    Usage::

        hash_a, hash_b = make_phash_pair(distance=3)
    """

    def _factory(distance: int) -> Tuple[str, str]:
        # 64-bit pHash = 16 hex chars
        n_bits = 64
        assert 0 <= distance <= n_bits

        rng = random.Random(42)  # deterministic
        base_bits = [rng.randint(0, 1) for _ in range(n_bits)]
        flipped_bits = list(base_bits)

        # Choose *distance* distinct positions to flip
        positions = rng.sample(range(n_bits), distance)
        for pos in positions:
            flipped_bits[pos] = 1 - flipped_bits[pos]

        return _bits_to_hex(base_bits), _bits_to_hex(flipped_bits)

    return _factory


@pytest.fixture
def make_snapshot_meta():
    """Factory fixture: generate a list of :class:`SnapshotMeta`.

    Usage::

        metas = make_snapshot_meta(eqpid="EQ-TEST", n=100)
    """

    def _factory(
        eqpid: str = "EQ-TEST",
        n: int = 100,
        base_ts: int = 1_700_000_000_000,
        ts_step_ms: int = 5_000,
        x_range: Tuple[int, int] = (100, 1800),
        y_range: Tuple[int, int] = (100, 900),
        seed: int = 42,
    ) -> List[SnapshotMeta]:
        rng = random.Random(seed)
        metas: List[SnapshotMeta] = []
        ts = base_ts
        for i in range(n):
            x = rng.randint(*x_range)
            y = rng.randint(*y_range)
            fname = f"{x}_{y}_{ts}.png"
            metas.append(
                SnapshotMeta(
                    eqpid=eqpid,
                    fname=fname,
                    timestamp_ms=ts,
                    x=x,
                    y=y,
                )
            )
            ts += ts_step_ms
        return metas

    return _factory


@pytest.fixture
def make_frame_features():
    """Factory fixture: convert :class:`SnapshotMeta` list to :class:`FrameFeature` list.

    Optionally populates synthetic pHash values.

    Usage::

        features = make_frame_features(metas, with_phash=True)
    """

    def _factory(
        metas: List[SnapshotMeta],
        with_phash: bool = False,
        seed: int = 123,
    ) -> List[FrameFeature]:
        rng = random.Random(seed)
        features: List[FrameFeature] = []
        for meta in metas:
            phash: Optional[str] = None
            if with_phash:
                # Generate a random 16-char hex string (64-bit hash)
                phash = "".join(format(rng.randint(0, 15), "x") for _ in range(16))

            features.append(
                FrameFeature(
                    eqpid=meta.eqpid,
                    fname=meta.fname,
                    timestamp_ms=meta.timestamp_ms,
                    x=meta.x,
                    y=meta.y,
                    phash=phash,
                )
            )
        return features

    return _factory
