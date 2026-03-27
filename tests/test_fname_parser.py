"""Tests for snapshot_screener.utils.fname_parser."""
from __future__ import annotations

import pytest

from snapshot_screener.utils.fname_parser import FnameParser


# -------------------------------------------------------------------------
# Production format: {timestamp}_[x][y].png
# -------------------------------------------------------------------------


class TestProductionFormat:
    """Tests for the production ``{ts}_[x][y].png`` format."""

    def test_basic(self):
        parser = FnameParser("auto")
        result = parser.parse("1774568805575_[1338][403].png")
        assert result == (1338, 403, 1774568805575)

    def test_small_coords(self):
        parser = FnameParser("auto")
        result = parser.parse("1700000000000_[0][0].png")
        assert result == (0, 0, 1700000000000)

    def test_large_coords(self):
        parser = FnameParser("auto")
        result = parser.parse("9999999999999_[1920][1080].png")
        assert result == (1920, 1080, 9999999999999)

    def test_single_digit_coords(self):
        parser = FnameParser("auto")
        result = parser.parse("1700000000000_[5][9].png")
        assert result == (5, 9, 1700000000000)

    def test_returns_x_y_ts_order(self):
        parser = FnameParser("auto")
        result = parser.parse("1774568805575_[1338][403].png")
        assert result is not None
        x, y, ts = result
        assert x == 1338
        assert y == 403
        assert ts == 1774568805575

    def test_mode_defaults_to_auto(self):
        parser = FnameParser()
        assert parser.mode == "auto"

    def test_auto_mode_property(self):
        parser = FnameParser("auto")
        assert parser.mode == "auto"


# -------------------------------------------------------------------------
# custom mode
# -------------------------------------------------------------------------


class TestCustomMode:
    """Tests for custom regex mode."""

    def test_custom_regex(self):
        pattern = r"snap_(?P<x>\d+)_(?P<y>\d+)_(?P<ts>\d+)\.png"
        parser = FnameParser(pattern)
        result = parser.parse("snap_100_200_1700000000000.png")
        assert result == (100, 200, 1700000000000)

    def test_custom_mode_property(self):
        pattern = r"(?P<ts>\d+)-(?P<x>\d+)-(?P<y>\d+)\.png"
        parser = FnameParser(pattern)
        assert parser.mode == "custom"

    def test_custom_different_order(self):
        """Custom regex with ts-x-y order separated by dashes."""
        pattern = r"(?P<ts>\d+)-(?P<x>\d+)-(?P<y>\d+)\.png"
        parser = FnameParser(pattern)
        result = parser.parse("1700000000000-500-300.png")
        assert result == (500, 300, 1700000000000)

    def test_custom_no_match(self):
        pattern = r"snap_(?P<x>\d+)_(?P<y>\d+)_(?P<ts>\d+)\.png"
        parser = FnameParser(pattern)
        result = parser.parse("other_format.png")
        assert result is None


# -------------------------------------------------------------------------
# Edge cases
# -------------------------------------------------------------------------


class TestEdgeCases:
    """Edge-case and error-handling tests."""

    def test_missing_png_extension(self):
        parser = FnameParser("auto")
        result = parser.parse("1700000000000_[100][200].jpg")
        assert result is None

    def test_no_extension(self):
        parser = FnameParser("auto")
        result = parser.parse("1700000000000_[100][200]")
        assert result is None

    def test_non_numeric_values(self):
        parser = FnameParser("auto")
        result = parser.parse("abc_[200][300].png")
        assert result is None

    def test_empty_string(self):
        parser = FnameParser("auto")
        result = parser.parse("")
        assert result is None

    def test_missing_brackets(self):
        parser = FnameParser("auto")
        result = parser.parse("1700000000000_100_200.png")
        assert result is None

    def test_partial_brackets(self):
        parser = FnameParser("auto")
        result = parser.parse("1700000000000_[100]200.png")
        assert result is None

    def test_whitespace_in_filename(self):
        parser = FnameParser("auto")
        result = parser.parse(" 1700000000000_[100][200].png")
        assert result is None

    def test_uppercase_extension(self):
        parser = FnameParser("auto")
        result = parser.parse("1700000000000_[100][200].PNG")
        assert result is None

    def test_extra_fields(self):
        parser = FnameParser("auto")
        result = parser.parse("1700000000000_[100][200]_extra.png")
        assert result is None
