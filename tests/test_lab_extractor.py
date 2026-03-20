"""Tests for LabExtractor — mocking fitz to avoid real PDF I/O."""

import pytest
from unittest.mock import MagicMock, patch

from form_filler.extractors.lab import (
    LabExtractor,
    _find_existing_slot,
    _find_next_slot,
    _norm_name,
    _parse_medication_lines,
)


LAB_TEXT = """\
Lab Result Report

Medication:
• Aspirin 81 mg once a day
• Metformin 500 mg twice daily

Notes: follow up.
"""


class TestHelpers:
    def test_norm_name(self):
        assert _norm_name("Aspirin") == "aspirin"
        assert _norm_name("Metformin HCL") == "metformin hcl"

    def test_parse_medication_lines(self):
        meds = _parse_medication_lines(LAB_TEXT)
        assert len(meds) == 2
        names = [m[0] for m in meds]
        assert "Aspirin" in names
        assert "Metformin" in names

    def test_parse_medication_dose(self):
        meds = _parse_medication_lines(LAB_TEXT)
        aspirin = next(m for m in meds if m[0] == "Aspirin")
        assert aspirin[1] == "81"

    def test_parse_medication_freq(self):
        meds = _parse_medication_lines(LAB_TEXT)
        aspirin = next(m for m in meds if m[0] == "Aspirin")
        assert "once" in aspirin[2].lower() or "day" in aspirin[2].lower()

    def test_find_next_slot_empty(self):
        assert _find_next_slot({}, {}) == 1

    def test_find_next_slot_skips_filled(self):
        already = {"medication_1_name": {"value": "aspirin", "confidence": 0.8}}
        assert _find_next_slot(already, {}) == 2

    def test_find_existing_slot(self):
        already = {"medication_1_name": {"value": "aspirin", "confidence": 0.8}}
        assert _find_existing_slot("aspirin", already, {}) == 1
        assert _find_existing_slot("metformin", already, {}) is None


class TestLabExtractor:
    def _make_extractor(self, extraction_config, tmp_path) -> tuple:
        p = tmp_path / "lab_result.pdf"
        p.write_bytes(b"%PDF-1.4 fake")  # placeholder bytes
        return LabExtractor(str(p), extraction_config), str(p)

    def test_source_name(self, extraction_config, tmp_path):
        extractor, _ = self._make_extractor(extraction_config, tmp_path)
        assert extractor.source_name == "lab_result.pdf"

    def test_medications_extracted(self, extraction_config, tmp_path, sample_schema):
        extractor, _ = self._make_extractor(extraction_config, tmp_path)

        mock_page = MagicMock()
        mock_page.get_text.return_value = LAB_TEXT
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_doc.__getitem__ = lambda self, i: mock_page

        with patch("fitz.open", return_value=mock_doc):
            result = extractor.extract(schema=sample_schema)

        assert "medication_1_name" in result or "medication_2_name" in result

    def test_no_text_returns_empty(self, extraction_config, tmp_path, sample_schema):
        extractor, _ = self._make_extractor(extraction_config, tmp_path)

        mock_page = MagicMock()
        mock_page.get_text.return_value = ""
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_doc.__getitem__ = lambda self, i: mock_page

        with patch("fitz.open", return_value=mock_doc):
            result = extractor.extract(schema=sample_schema)

        assert result == {}
