"""Shared fixtures for all tests."""

from __future__ import annotations

import json
import pytest
from form_filler.config import ExtractionConfig


@pytest.fixture
def extraction_config() -> ExtractionConfig:
    return ExtractionConfig(
        demographics_confidence=0.95,
        soap_confidence=0.75,
        lab_confidence=0.70,
        use_llm_fallback=False,  # never load a real model in tests
        use_ocr_fallback=False,
    )


@pytest.fixture
def sample_schema() -> dict:
    """Minimal schema covering all field groups used in tests."""
    return {
        "patient_name_last_first_middle_initial": {
            "label": "Patient Name",
            "type": "text",
            "pdf_name": "APS1.PatientName",
            "group": None,
            "part": None,
        },
        "date_of_birth_dd": {
            "label": "DOB Day",
            "type": "text",
            "pdf_name": "APS1.Date_of_birth_d",
            "group": "date_of_birth",
            "part": "day",
        },
        "date_of_birth_mm": {
            "label": "DOB Month",
            "type": "text",
            "pdf_name": "APS1.Date_of_birth_m",
            "group": "date_of_birth",
            "part": "month",
        },
        "date_of_birth_yyyy": {
            "label": "DOB Year",
            "type": "text",
            "pdf_name": "APS1.Date_of_birth_y",
            "group": "date_of_birth",
            "part": "year",
        },
        "home_phone_area_code": {
            "label": "Home Phone (Area Code)",
            "type": "text",
            "pdf_name": "APS1.areacode",
            "group": "home_phone",
            "part": "area_code",
        },
        "home_phone_first3": {
            "label": "Home Phone (First 3)",
            "type": "text",
            "pdf_name": "APS1.first3",
            "group": "home_phone",
            "part": "first3",
        },
        "home_phone_last4": {
            "label": "Home Phone (Last 4)",
            "type": "text",
            "pdf_name": "APS1.last4",
            "group": "home_phone",
            "part": "last4",
        },
        "cell_phone_area_code": {
            "label": "Cell Phone (Area Code)",
            "type": "text",
            "pdf_name": "APS1.cellareacode",
            "group": "cell_phone",
            "part": "area_code",
        },
        "cell_phone_first3": {
            "label": "Cell Phone (First 3)",
            "type": "text",
            "pdf_name": "APS1.cellfirst3",
            "group": "cell_phone",
            "part": "first3",
        },
        "cell_phone_last4": {
            "label": "Cell Phone (Last 4)",
            "type": "text",
            "pdf_name": "APS1.celllast4",
            "group": "cell_phone",
            "part": "last4",
        },
        "address_street_city_province_postal_code": {
            "label": "Address",
            "type": "text",
            "pdf_name": "APS1.Address",
            "group": None,
            "part": None,
        },
        "primary_1": {
            "label": "Primary Diagnosis 1",
            "type": "text",
            "pdf_name": "APS2.Diagnosis_Primary1",
            "group": None,
            "part": None,
        },
        "primary_2": {
            "label": "Primary Diagnosis 2",
            "type": "text",
            "pdf_name": "APS2.Diagnosis_Primary2",
            "group": None,
            "part": None,
        },
        "secondary_and_or_complications_1": {
            "label": "Secondary Diagnosis 1",
            "type": "text",
            "pdf_name": "APS2.Diagnosis_Secondary1",
            "group": None,
            "part": None,
        },
        "medication_1_name": {
            "label": "Medication 1 Name",
            "type": "text",
            "pdf_name": "APS1.Medication1",
            "group": "medication_1",
            "part": "name",
        },
        "medication_1_dose": {
            "label": "Medication 1 Dose",
            "type": "text",
            "pdf_name": "APS1.Dose1",
            "group": "medication_1",
            "part": "dose",
        },
        "medication_1_often": {
            "label": "Medication 1 Frequency",
            "type": "text",
            "pdf_name": "APS1.Often1",
            "group": "medication_1",
            "part": "often",
        },
        "medication_2_name": {
            "label": "Medication 2 Name",
            "type": "text",
            "pdf_name": "APS1.Medication2",
            "group": "medication_2",
            "part": "name",
        },
        "medication_2_dose": {
            "label": "Medication 2 Dose",
            "type": "text",
            "pdf_name": "APS1.Dose2",
            "group": "medication_2",
            "part": "dose",
        },
        "medication_2_often": {
            "label": "Medication 2 Frequency",
            "type": "text",
            "pdf_name": "APS1.Often2",
            "group": "medication_2",
            "part": "often",
        },
    }


@pytest.fixture
def demographics_data() -> dict:
    return {
        "patient_name": "Peter Julius Fern",
        "dob": "1960-04-15",
        "phone_home": "6136565890",
        "phone_mobile": "6476668888",
        "address": {
            "street": "45 Maple Ave",
            "city": "Toronto",
            "province": "ON",
            "postal_code": "K7L 3V8",
        },
    }


@pytest.fixture
def demographics_file(tmp_path, demographics_data) -> str:
    p = tmp_path / "demographics.json"
    p.write_text(json.dumps(demographics_data))
    return str(p)


SOAP_TEXT = """\
Subjective:
Peter Fern, 62M, presents with exertional chest tightness.

Objective:
BP 148/90, HR 72.

Assessment:
1. Likely stable angina given exertional pattern and resolution w/ rest
2. Hypertension — borderline control
3. GERD — chronic, unlikely cause

Plan:
- Continue antihypertensives as directed
- Provide nitroglycerin SL for exertional discomfort
- Lipid panel
"""


@pytest.fixture
def soap_file(tmp_path) -> str:
    p = tmp_path / "soap_notes.txt"
    p.write_text(SOAP_TEXT)
    return str(p)


LAB_TEXT = """\
Lab Result Report

Patient: Peter Fern

Medication:
• Aspirin 81 mg once a day
• Metformin 500 mg twice daily

Notes: Follow up in 2 weeks.
"""


@pytest.fixture
def lab_pdf_text() -> str:
    return LAB_TEXT
