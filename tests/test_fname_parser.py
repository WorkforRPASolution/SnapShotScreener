"""Tests for snapshot_screener.utils.fname_parser."""
from __future__ import annotations

import pytest

from snapshot_screener.utils.fname_parser import FnameParser


# -------------------------------------------------------------------------
# xy_ts mode
# -------------------------------------------------------------------------


class TestXyTsMode:
    """Tests for explicit ``xy_ts`` mode."""

    def test_basic(self):
        parser = FnameParser("xy_ts")
        result = parser.parse("100_200_1700000000000.png")
        assert result == (100, 200, 1700000000000)

    def test_small_coords(self):
        parser = FnameParser("xy_ts")
        result = parser.parse("0_0_1234567890123.png")
        assert result == (0, 0, 1234567890123)

    def test_large_coords(self):
        parser = FnameParser("xy_ts")
        result = parser.parse("1920_1080_9999999999999.png")
        assert result == (1920, 1080, 9999999999999)


# -------------------------------------------------------------------------
# ts_xy mode
# -------------------------------------------------------------------------


class TestTsXyMode:
    """Tests for explicit ``ts_xy`` mode."""

    def test_basic(self):
        parser = FnameParser("ts_xy")
        result = parser.parse("1700000000000_500_300.png")
        assert result == (500, 300, 1700000000000)

    def test_returns_x_y_ts_order(self):
        parser = FnameParser("ts_xy")
        result = parser.parse("9999999999999_1920_1080.png")
        assert result is not None
        x, y, ts = result
        assert x == 1920
        assert y == 1080
        assert ts == 9999999999999


# -------------------------------------------------------------------------
# auto mode
# -------------------------------------------------------------------------


class TestAutoMode:
    """Tests for auto-detection mode."""

    def test_auto_detects_ts_xy_when_first_field_13_digits(self):
        """First field has 13 digits -> ts_xy."""
        parser = FnameParser("auto")
        result = parser.parse("1700000000000_100_200.png")
        assert result == (100, 200, 1700000000000)

    def test_auto_detects_xy_ts_when_first_field_short(self):
        """First field has <= 4 digits -> xy_ts."""
        parser = FnameParser("auto")
        result = parser.parse("100_200_1700000000000.png")
        assert result == (100, 200, 1700000000000)

    def test_auto_detects_xy_ts_single_digit(self):
        """Single-digit first field -> xy_ts."""
        parser = FnameParser("auto")
        result = parser.parse("5_10_1700000000000.png")
        assert result == (5, 10, 1700000000000)

    def test_auto_detects_ts_xy_long_first_field(self):
        """First field >= 13 digits (e.g., 14 digits) -> ts_xy."""
        parser = FnameParser("auto")
        result = parser.parse("17000000000001_100_200.png")
        assert result == (100, 200, 17000000000001)

    def test_auto_mode_property(self):
        parser = FnameParser("auto")
        assert parser.mode == "auto"

    def test_auto_xy_ts_4_digit_first_field(self):
        """Exactly 4-digit first field -> xy_ts."""
        parser = FnameParser("auto")
        result = parser.parse("1920_1080_1700000000000.png")
        assert result == (1920, 1080, 1700000000000)


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
        parser = FnameParser("xy_ts")
        result = parser.parse("100_200_1700000000000.jpg")
        assert result is None

    def test_no_extension(self):
        parser = FnameParser("xy_ts")
        result = parser.parse("100_200_1700000000000")
        assert result is None

    def test_non_numeric_values(self):
        parser = FnameParser("xy_ts")
        result = parser.parse("abc_200_1700000000000.png")
        assert result is None

    def test_empty_string(self):
        parser = FnameParser("xy_ts")
        result = parser.parse("")
        assert result is None

    def test_too_few_fields(self):
        parser = FnameParser("xy_ts")
        result = parser.parse("100_200.png")
        assert result is None

    def test_too_many_fields(self):
        parser = FnameParser("xy_ts")
        result = parser.parse("100_200_300_1700000000000.png")
        assert result is None

    def test_whitespace_in_filename(self):
        parser = FnameParser("xy_ts")
        result = parser.parse(" 100_200_1700000000000.png")
        assert result is None

    def test_uppercase_extension(self):
        parser = FnameParser("xy_ts")
        result = parser.parse("100_200_1700000000000.PNG")
        assert result is None

    def test_mode_defaults_to_auto(self):
        parser = FnameParser()
        assert parser.mode == "auto"
