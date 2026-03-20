"""PDF population.

Single Responsibility: write answer values into a fillable (AcroForm) PDF.
Receives data dicts directly (not file paths) — keeps it testable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pypdf import PdfReader, PdfWriter

from form_filler.extractors.base import ExtractionResult

logger = logging.getLogger(__name__)


@dataclass
class PopulationReport:
    """Summary of what was filled, skipped, or missing."""

    filled: dict[str, str] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)
    missing_pdf_fields: dict[str, str] = field(default_factory=dict)


class PDFPopulator:
    """Populates text fields in a fillable PDF from schema + answer dicts."""

    def populate(
        self,
        form_pdf_path: str,
        schema: dict[str, Any],
        answers: ExtractionResult,
        output_path: str = "populated.pdf",
    ) -> tuple[str, PopulationReport]:
        """Write answers into the PDF form.

        Args:
            form_pdf_path: Path to the original fillable PDF.
            schema:        Normalised schema dict (from SchemaExtractor).
            answers:       Reconciled extraction results.
            output_path:   Where to write the populated PDF.

        Returns:
            (output_path, report)
        """
        # Build normalised_key → pdf_name for text fields only
        text_targets: dict[str, str] = {
            norm_key: str(meta["pdf_name"])
            for norm_key, meta in schema.items()
            if (meta.get("type") or "").lower() == "text" and meta.get("pdf_name")
        }

        reader = PdfReader(form_pdf_path)
        # Clone preserves AcroForm structure; plain PdfWriter() drops it.
        writer = PdfWriter(clone_from=reader)

        try:
            writer.set_need_appearances_writer()
        except Exception:
            pass  # Some pypdf versions don't have this method

        pdf_field_names = set((reader.get_fields() or {}).keys())
        report = PopulationReport()
        to_fill: dict[str, str] = {}

        for norm_key, ans_obj in answers.items():
            if norm_key not in text_targets:
                report.skipped[norm_key] = "not a text field in schema"
                continue

            pdf_name = text_targets[norm_key]
            value = _to_str(ans_obj.get("value") if isinstance(ans_obj, dict) else ans_obj)

            if not value.strip():
                report.skipped[norm_key] = "empty value"
                continue

            if pdf_name not in pdf_field_names:
                report.missing_pdf_fields[norm_key] = pdf_name
                report.skipped[norm_key] = "pdf field not found"
                continue

            to_fill[pdf_name] = value
            report.filled[norm_key] = value

        for page in writer.pages:
            try:
                writer.update_page_form_field_values(page, to_fill)
            except Exception:
                pass  # Best-effort on malformed PDFs

        with open(output_path, "wb") as fh:
            writer.write(fh)

        logger.info(
            "PDF populated: %d filled, %d skipped, %d missing pdf fields → %s",
            len(report.filled),
            len(report.skipped),
            len(report.missing_pdf_fields),
            output_path,
        )
        return output_path, report


def _to_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v)
