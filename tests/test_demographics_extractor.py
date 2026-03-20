"""Tests for DemographicsExtractor."""

import pytest
from form_filler.extractors.demographics import DemographicsExtractor


class TestDemographicsExtractor:
    def test_source_name(self, extraction_config, demographics_file):
        extractor = DemographicsExtractor(demographics_file, extraction_config)
        assert extractor.source_name == "demographics.json"

    def test_patient_name_extracted(self, extraction_config, demographics_file, sample_schema):
        extractor = DemographicsExtractor(demographics_file, extraction_config)
        result = extractor.extract(schema=sample_schema)
        assert "patient_name_last_first_middle_initial" in result
        assert result["patient_name_last_first_middle_initial"]["value"] == "Peter Julius Fern"
        assert result["patient_name_last_first_middle_initial"]["confidence"] == 0.95

    def test_dob_split(self, extraction_config, demographics_file, sample_schema):
        extractor = DemographicsExtractor(demographics_file, extraction_config)
        result = extractor.extract(schema=sample_schema)
        assert result["date_of_birth_dd"]["value"] == "15"
        assert result["date_of_birth_mm"]["value"] == "04"
        assert result["date_of_birth_yyyy"]["value"] == "1960"

    def test_home_phone_split(self, extraction_config, demographics_file, sample_schema):
        extractor = DemographicsExtractor(demographics_file, extraction_config)
        result = extractor.extract(schema=sample_schema)
        assert result["home_phone_area_code"]["value"] == "613"
        assert result["home_phone_first3"]["value"] == "656"
        assert result["home_phone_last4"]["value"] == "5890"

    def test_cell_phone_split(self, extraction_config, demographics_file, sample_schema):
        extractor = DemographicsExtractor(demographics_file, extraction_config)
        result = extractor.extract(schema=sample_schema)
        assert result["cell_phone_area_code"]["value"] == "647"
        assert result["cell_phone_first3"]["value"] == "666"
        assert result["cell_phone_last4"]["value"] == "8888"

    def test_address_formatted(self, extraction_config, demographics_file, sample_schema):
        extractor = DemographicsExtractor(demographics_file, extraction_config)
        result = extractor.extract(schema=sample_schema)
        addr = result["address_street_city_province_postal_code"]["value"]
        assert "Toronto" in addr
        assert "Maple Ave" in addr

    def test_source_tagged(self, extraction_config, demographics_file, sample_schema):
        extractor = DemographicsExtractor(demographics_file, extraction_config)
        result = extractor.extract(schema=sample_schema)
        for entry in result.values():
            assert entry["source"] == "demographics.json"

    def test_field_not_in_schema_ignored(self, extraction_config, demographics_file):
        extractor = DemographicsExtractor(demographics_file, extraction_config)
        result = extractor.extract(schema={})  # empty schema → nothing matches
        assert result == {}

    def test_already_filled_still_extracted(self, extraction_config, demographics_file, sample_schema):
        # DemographicsExtractor doesn't skip already-filled (it's always first / highest confidence)
        already = {"patient_name_last_first_middle_initial": {"value": "Old Name", "confidence": 0.5}}
        extractor = DemographicsExtractor(demographics_file, extraction_config)
        result = extractor.extract(schema=sample_schema, already_filled=already)
        assert "patient_name_last_first_middle_initial" in result
