"""
PDF population utilities for fillable (AcroForm) PDFs.

Text-fields only (per take-home scope):
- Use schema.json to map normalized field keys -> PDF form field names (pdf_name)
- Use answers.json to provide values for those normalized field keys
- Write populated.pdf without hardcoding field names
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from pypdf import PdfReader, PdfWriter


@dataclass
class PopulationReport:
    filled: Dict[str, str]                 # normalized_key -> value
    skipped: Dict[str, str]                # normalized_key -> reason
    missing_pdf_fields: Dict[str, str]     # normalized_key -> pdf_name


def _as_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        # Keep simple numeric formatting (avoid 0.400000)
        s = str(v)
        return s
    return str(v)


def populate_fillable_pdf(
    form_pdf_path: str,
    schema_path: str,
    answers_path: str,
    output_path: str = "populated.pdf",
) -> Tuple[str, PopulationReport]:
    """
    Populate a fillable PDF using extracted answers.

    Args:
        form_pdf_path: path to the fillable PDF (e.g., form_fillable.pdf)
        schema_path: path to schema.json
        answers_path: path to answers.json
        output_path: where to write the populated PDF

    Returns:
        (output_path, report)
    """
    with open(schema_path, "r", encoding="utf-8") as f:
        schema: Dict[str, Any] = json.load(f)

    with open(answers_path, "r", encoding="utf-8") as f:
        answers: Dict[str, Any] = json.load(f)

    # Build normalized_key -> pdf_name mapping for text fields
    text_targets: Dict[str, str] = {}
    for norm_key, meta in schema.items():
        if (meta.get("type") or "").lower() != "text":
            continue
        pdf_name = meta.get("pdf_name")
        if not pdf_name:
            continue
        text_targets[norm_key] = str(pdf_name)

    reader = PdfReader(form_pdf_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    # pypdf: make appearances show up in many viewers
    try:
        writer.set_need_appearances_writer()
    except Exception:
        # Some pypdf versions don't expose this; safe to ignore.
        pass

    pdf_fields = reader.get_fields() or {}
    pdf_field_names = set(pdf_fields.keys())

    to_fill: Dict[str, str] = {}  # pdf_name -> value
    report = PopulationReport(filled={}, skipped={}, missing_pdf_fields={})

    for norm_key, ans_obj in answers.items():
        if norm_key not in text_targets:
            # Not a text field per schema (or unknown key)
            report.skipped[norm_key] = "not a text field in schema or not present in schema"
            continue

        pdf_name = text_targets[norm_key]
        value = _as_str(ans_obj.get("value") if isinstance(ans_obj, dict) else ans_obj)

        if not value.strip():
            report.skipped[norm_key] = "empty value"
            continue

        if pdf_name not in pdf_field_names:
            report.missing_pdf_fields[norm_key] = pdf_name
            report.skipped[norm_key] = "pdf field not found in form"
            continue

        to_fill[pdf_name] = value
        report.filled[norm_key] = value

    # Apply values across all pages (pypdf internally handles only fields on each page)
    for page in writer.pages:
        try:
            writer.update_page_form_field_values(page, to_fill)
        except Exception:
            # If a PDF is malformed, don't crash the whole pipeline; keep best-effort.
            pass

    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path, report

