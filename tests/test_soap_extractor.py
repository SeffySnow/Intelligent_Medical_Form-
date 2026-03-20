"""Tests for SOAPExtractor — deterministic path only (LLM disabled)."""

import pytest
from form_filler.extractors.soap import SOAPExtractor, _extract_section, _shorten_dx


class TestHelpers:
    def test_extract_section_assessment(self):
        text = "Assessment:\n1. Stable angina\n2. Hypertension\n\nPlan:\n- Aspirin"
        section = _extract_section(text, "Assessment:")
        assert "Stable angina" in section
        assert "Plan" not in section

    def test_extract_section_missing(self):
        assert _extract_section("no sections here", "Assessment:") == ""

    def test_shorten_dx_strips_likely(self):
        assert _shorten_dx("Likely stable angina") == "stable angina"

    def test_shorten_dx_stops_at_dash(self):
        result = _shorten_dx("Hypertension — borderline control")
        assert result == "Hypertension"

    def test_shorten_dx_stops_at_semicolon(self):
        result = _shorten_dx("GERD; chronic condition")
        assert result == "GERD"


class TestSOAPExtractor:
    def test_source_name(self, extraction_config, soap_file):
        extractor = SOAPExtractor(soap_file, extraction_config)
        assert extractor.source_name == "soap_notes.txt"

    def test_primary_diagnosis_extracted(self, extraction_config, soap_file, sample_schema):
        extractor = SOAPExtractor(soap_file, extraction_config)
        result = extractor.extract(schema=sample_schema)
        assert "primary_1" in result
        val = result["primary_1"]["value"]
        assert val is not None
        assert "angina" in val.lower()

    def test_secondary_diagnosis_extracted(self, extraction_config, soap_file, sample_schema):
        extractor = SOAPExtractor(soap_file, extraction_config)
        result = extractor.extract(schema=sample_schema)
        assert result.get("secondary_and_or_complications_1", {}).get("value") is not None

    def test_nitroglycerin_extracted(self, extraction_config, soap_file, sample_schema):
        extractor = SOAPExtractor(soap_file, extraction_config)
        result = extractor.extract(schema=sample_schema)
        assert result["medication_1_name"]["value"] == "nitroglycerin"
        assert result["medication_1_name"]["confidence"] == 0.8

    def test_nitroglycerin_frequency(self, extraction_config, soap_file, sample_schema):
        extractor = SOAPExtractor(soap_file, extraction_config)
        result = extractor.extract(schema=sample_schema)
        assert "PRN" in result["medication_1_often"]["value"]

    def test_completion_only_skips_filled(self, extraction_config, soap_file, sample_schema):
        already = {
            "primary_1": {"value": "existing dx", "confidence": 0.99},
            "medication_1_name": {"value": "aspirin", "confidence": 0.99},
        }
        extractor = SOAPExtractor(soap_file, extraction_config)
        result = extractor.extract(schema=sample_schema, already_filled=already)
        # These keys were already filled → should NOT appear in result
        assert "primary_1" not in result
        assert "medication_1_name" not in result

    def test_llm_disabled(self, extraction_config, soap_file, sample_schema):
        # use_llm_fallback=False — no torch import should be triggered
        extractor = SOAPExtractor(soap_file, extraction_config)
        result = extractor.extract(schema=sample_schema)
        # Just verify it runs without error
        assert isinstance(result, dict)

    def test_source_tagged(self, extraction_config, soap_file, sample_schema):
        extractor = SOAPExtractor(soap_file, extraction_config)
        result = extractor.extract(schema=sample_schema)
        for entry in result.values():
            assert entry.get("source") == "soap_notes.txt"
