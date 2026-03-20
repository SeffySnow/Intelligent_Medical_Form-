"""Configuration management for the form-filler pipeline.

Uses plain dataclasses + environment variables (via python-dotenv).
No external config library required — standard library os.getenv is enough.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExtractionConfig:
    """Settings that govern extraction behaviour."""

    demographics_confidence: float = 0.95
    soap_confidence: float = 0.75
    lab_confidence: float = 0.70

    use_llm_fallback: bool = True
    model_name: str = "Qwen/Qwen2.5-3B-Instruct"
    model_cache_dir: str = "./models/Qwen2.5-3B-Instruct"
    max_input_tokens: int = 2048
    max_new_tokens: int = 450

    use_ocr_fallback: bool = True
    ocr_dpi: int = 200


@dataclass
class PipelineConfig:
    """Top-level pipeline configuration."""

    form_pdf: Path = field(default_factory=lambda: Path("inputs/form_fillable.pdf"))
    schema_json: Path = field(default_factory=lambda: Path("outputs/schema.json"))
    answers_json: Path = field(default_factory=lambda: Path("outputs/answers.json"))
    demographics_json: Path = field(default_factory=lambda: Path("inputs/demographics.json"))
    soap_notes_txt: Path = field(default_factory=lambda: Path("inputs/soap_notes.txt"))
    lab_result_pdf: Path = field(default_factory=lambda: Path("inputs/lab_result.pdf"))
    output_pdf: Path = field(default_factory=lambda: Path("outputs/populated.pdf"))

    log_level: str = "INFO"
    log_format: str = "console"  # "console" | "json"

    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)

    @classmethod
    def from_env(cls) -> PipelineConfig:
        """Build config from environment variables with sensible defaults."""
        ext = ExtractionConfig(
            demographics_confidence=float(os.getenv("DEMOGRAPHICS_CONFIDENCE", "0.95")),
            soap_confidence=float(os.getenv("SOAP_CONFIDENCE", "0.75")),
            lab_confidence=float(os.getenv("LAB_CONFIDENCE", "0.70")),
            use_llm_fallback=os.getenv("USE_LLM_FALLBACK", "true").lower() != "false",
            model_name=os.getenv("MODEL_NAME", "Qwen/Qwen2.5-3B-Instruct"),
            model_cache_dir=os.getenv("MODEL_CACHE_DIR", "./models/Qwen2.5-3B-Instruct"),
            max_input_tokens=int(os.getenv("MAX_INPUT_TOKENS", "2048")),
            max_new_tokens=int(os.getenv("MAX_NEW_TOKENS", "450")),
            use_ocr_fallback=os.getenv("USE_OCR_FALLBACK", "true").lower() != "false",
            ocr_dpi=int(os.getenv("OCR_DPI", "200")),
        )
        return cls(
            form_pdf=Path(os.getenv("FORM_PDF", "inputs/form_fillable.pdf")),
            schema_json=Path(os.getenv("SCHEMA_JSON", "outputs/schema.json")),
            answers_json=Path(os.getenv("ANSWERS_JSON", "outputs/answers.json")),
            demographics_json=Path(os.getenv("DEMOGRAPHICS_JSON", "inputs/demographics.json")),
            soap_notes_txt=Path(os.getenv("SOAP_NOTES_TXT", "inputs/soap_notes.txt")),
            lab_result_pdf=Path(os.getenv("LAB_RESULT_PDF", "inputs/lab_result.pdf")),
            output_pdf=Path(os.getenv("OUTPUT_PDF", "outputs/populated.pdf")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_format=os.getenv("LOG_FORMAT", "console"),
            extraction=ext,
        )
