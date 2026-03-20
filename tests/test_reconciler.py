"""Tests for Reconciler."""

import pytest
from form_filler.reconciler import Reconciler


@pytest.fixture
def reconciler():
    return Reconciler()


class TestReconciler:
    def test_empty_merge(self, reconciler):
        assert reconciler.merge() == {}

    def test_single_dict(self, reconciler):
        data = {"name": {"value": "Alice", "confidence": 0.9}}
        result = reconciler.merge(data)
        assert result == data

    def test_no_conflict(self, reconciler):
        a = {"name": {"value": "Alice", "confidence": 0.9}}
        b = {"age": {"value": "30", "confidence": 0.8}}
        result = reconciler.merge(a, b)
        assert "name" in result
        assert "age" in result

    def test_higher_confidence_wins(self, reconciler):
        a = {"name": {"value": "Alice", "confidence": 0.9}}
        b = {"name": {"value": "Bob", "confidence": 0.7}}
        result = reconciler.merge(a, b)
        assert result["name"]["value"] == "Alice"

    def test_later_higher_confidence_wins(self, reconciler):
        a = {"name": {"value": "Alice", "confidence": 0.5}}
        b = {"name": {"value": "Bob", "confidence": 0.9}}
        result = reconciler.merge(a, b)
        assert result["name"]["value"] == "Bob"

    def test_equal_confidence_keeps_first(self, reconciler):
        a = {"name": {"value": "Alice", "confidence": 0.8}}
        b = {"name": {"value": "Bob", "confidence": 0.8}}
        result = reconciler.merge(a, b)
        assert result["name"]["value"] == "Alice"

    def test_three_way_merge(self, reconciler):
        a = {"x": {"value": "low", "confidence": 0.3}}
        b = {"x": {"value": "mid", "confidence": 0.6}}
        c = {"x": {"value": "high", "confidence": 0.95}}
        result = reconciler.merge(a, b, c)
        assert result["x"]["value"] == "high"

    def test_does_not_mutate_inputs(self, reconciler):
        a = {"name": {"value": "Alice", "confidence": 0.9}}
        b = {"name": {"value": "Bob", "confidence": 0.7}}
        reconciler.merge(a, b)
        assert a["name"]["value"] == "Alice"
        assert b["name"]["value"] == "Bob"
