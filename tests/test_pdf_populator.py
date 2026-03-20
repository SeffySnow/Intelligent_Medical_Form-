"""Tests for PDFPopulator — mocking pypdf to avoid real PDF I/O."""

import pytest
from unittest.mock import MagicMock, patch, call

from form_filler.pdf_populator import PDFPopulator, PopulationReport, _to_str


class TestToStr:
    def test_none(self):
        assert _to_str(None) == ""

    def test_string(self):
        assert _to_str("hello") == "hello"

    def test_int(self):
        assert _to_str(42) == "42"

    def test_float(self):
        assert _to_str(3.14) == "3.14"


class TestPDFPopulator:
    def _run_populate(self, schema, answers, pdf_fields=None):
        """Helper: run populate() with mocked pypdf."""
        populator = PDFPopulator()
        pdf_fields = pdf_fields or {}

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = pdf_fields
        mock_reader.pages = [MagicMock()]

        mock_writer = MagicMock()
        mock_writer.pages = [MagicMock()]

        with patch("form_filler.pdf_populator.PdfReader", return_value=mock_reader), \
             patch("form_filler.pdf_populator.PdfWriter", return_value=mock_writer), \
             patch("builtins.open", MagicMock()):
            return populator.populate("form.pdf", schema, answers, "out.pdf")

    def test_text_field_filled(self):
        schema = {
            "patient_name": {
                "type": "text",
                "pdf_name": "APS1.PatientName",
            }
        }
        answers = {"patient_name": {"value": "Alice", "confidence": 0.9}}
        pdf_fields = {"APS1.PatientName": {}}

        _, report = self._run_populate(schema, answers, pdf_fields)
        assert "patient_name" in report.filled
        assert report.filled["patient_name"] == "Alice"

    def test_non_text_field_skipped(self):
        schema = {
            "submit_btn": {"type": "button", "pdf_name": "APS1.Submit"}
        }
        answers = {"submit_btn": {"value": "yes", "confidence": 0.9}}

        _, report = self._run_populate(schema, answers, {"APS1.Submit": {}})
        assert "submit_btn" in report.skipped

    def test_empty_value_skipped(self):
        schema = {"name": {"type": "text", "pdf_name": "APS1.Name"}}
        answers = {"name": {"value": "", "confidence": 0.9}}

        _, report = self._run_populate(schema, answers, {"APS1.Name": {}})
        assert "name" in report.skipped

    def test_missing_pdf_field_recorded(self):
        schema = {"name": {"type": "text", "pdf_name": "APS1.Name"}}
        answers = {"name": {"value": "Alice", "confidence": 0.9}}
        # pdf_fields is empty — APS1.Name not in form

        _, report = self._run_populate(schema, answers, pdf_fields={})
        assert "name" in report.missing_pdf_fields

    def test_null_value_skipped(self):
        schema = {"name": {"type": "text", "pdf_name": "APS1.Name"}}
        answers = {"name": {"value": None, "confidence": 0.0}}

        _, report = self._run_populate(schema, answers, {"APS1.Name": {}})
        assert "name" in report.skipped


class TestPopulationReport:
    def test_empty_report(self):
        report = PopulationReport()
        assert report.filled == {}
        assert report.skipped == {}
        assert report.missing_pdf_fields == {}
