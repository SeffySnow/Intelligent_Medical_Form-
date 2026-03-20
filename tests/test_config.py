"""Tests for PipelineConfig and ExtractionConfig."""

import os
import pytest
from form_filler.config import ExtractionConfig, PipelineConfig
from pathlib import Path


def test_extraction_config_defaults():
    cfg = ExtractionConfig()
    assert cfg.demographics_confidence == 0.95
    assert cfg.soap_confidence == 0.75
    assert cfg.lab_confidence == 0.70
    assert cfg.use_llm_fallback is True
    assert cfg.use_ocr_fallback is True
    assert cfg.ocr_dpi == 200


def test_pipeline_config_defaults():
    cfg = PipelineConfig()
    assert cfg.form_pdf == Path("inputs/form_fillable.pdf")
    assert cfg.log_level == "INFO"
    assert cfg.log_format == "console"


def test_from_env_defaults(monkeypatch):
    # Clear any relevant env vars
    for key in ["FORM_PDF", "LOG_LEVEL", "DEMOGRAPHICS_CONFIDENCE", "USE_LLM_FALLBACK"]:
        monkeypatch.delenv(key, raising=False)
    cfg = PipelineConfig.from_env()
    assert cfg.form_pdf == Path("inputs/form_fillable.pdf")
    assert cfg.log_level == "INFO"
    assert cfg.extraction.demographics_confidence == 0.95


def test_from_env_custom(monkeypatch):
    monkeypatch.setenv("FORM_PDF", "my_form.pdf")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DEMOGRAPHICS_CONFIDENCE", "0.99")
    monkeypatch.setenv("USE_LLM_FALLBACK", "false")
    monkeypatch.setenv("OCR_DPI", "300")

    cfg = PipelineConfig.from_env()
    assert cfg.form_pdf == Path("my_form.pdf")
    assert cfg.log_level == "DEBUG"
    assert cfg.extraction.demographics_confidence == 0.99
    assert cfg.extraction.use_llm_fallback is False
    assert cfg.extraction.ocr_dpi == 300
