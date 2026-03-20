"""Tests for extraction utility functions."""

import pytest
from form_filler.extractors.utils import (
    format_address,
    is_filled,
    make_entry,
    parse_date,
    parse_phone,
)


class TestParseDate:
    def test_valid_iso(self):
        result = parse_date("1960-04-15")
        assert result == {"day": "15", "month": "04", "year": "1960"}

    def test_zero_padded(self):
        result = parse_date("1960-01-05")
        assert result["day"] == "05"
        assert result["month"] == "01"

    def test_invalid_returns_empty(self):
        result = parse_date("not-a-date")
        assert result == {"day": "", "month": "", "year": ""}

    def test_wrong_format(self):
        result = parse_date("15/04/1960")
        assert result["day"] == ""


class TestParsePhone:
    def test_10_digit(self):
        result = parse_phone("6136565890")
        assert result == {"area_code": "613", "first3": "656", "last4": "5890"}

    def test_11_digit_with_country_code(self):
        result = parse_phone("16136565890")
        assert result == {"area_code": "613", "first3": "656", "last4": "5890"}

    def test_formatted_standard(self):
        result = parse_phone("647-666-8888")
        assert result["area_code"] == "647"
        assert result["first3"] == "666"
        assert result["last4"] == "8888"

    def test_non_standard_dashed(self):
        # "613-6565-890" — non-standard Canadian format from demographics
        result = parse_phone("613-6565-890")
        assert result["area_code"] == "613"
        assert len(result["first3"]) == 3
        assert len(result["last4"]) == 4

    def test_unrecognised_returns_empty(self):
        result = parse_phone("123")
        assert result == {"area_code": "", "first3": "", "last4": ""}


class TestFormatAddress:
    def test_full_address(self):
        addr = {"street": "45 Maple Ave", "city": "Toronto", "province": "ON", "postal_code": "K7L 3V8"}
        assert format_address(addr) == "45 Maple Ave, Toronto, ON, K7L 3V8"

    def test_partial_address(self):
        addr = {"street": "10 King St", "city": "Ottawa"}
        assert format_address(addr) == "10 King St, Ottawa"

    def test_empty_address(self):
        assert format_address({}) == ""


class TestIsFilled:
    def test_filled_field(self):
        already = {"name": {"value": "Alice", "confidence": 0.9}}
        assert is_filled("name", already) is True

    def test_null_value(self):
        already = {"name": {"value": None, "confidence": 0.9}}
        assert is_filled("name", already) is False

    def test_empty_string(self):
        already = {"name": {"value": "  ", "confidence": 0.9}}
        assert is_filled("name", already) is False

    def test_missing_key(self):
        assert is_filled("nonexistent", {"other": {"value": "x"}}) is False

    def test_none_already_filled(self):
        assert is_filled("name", None) is False


class TestMakeEntry:
    def test_basic(self):
        entry = make_entry("Alice", "test.json", "direct", 0.9)
        assert entry["value"] == "Alice"
        assert entry["source"] == "test.json"
        assert entry["confidence"] == 0.9
        assert entry["evidence"] is None

    def test_with_evidence(self):
        entry = make_entry("Alice", "test.json", "direct", 0.9, evidence="Patient: Alice")
        assert entry["evidence"] == "Patient: Alice"
