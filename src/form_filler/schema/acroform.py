"""AcroForm schema extractor.

Single Responsibility: extract and normalise form field metadata from a fillable PDF.
Combines pypdf (labels, types) with PyMuPDF (bounding boxes, page numbers).
"""

from __future__ import annotations

import logging
import re
from typing import Any

import fitz  # PyMuPDF
from pypdf import PdfReader

logger = logging.getLogger(__name__)


class SchemaExtractor:
    """Extracts a normalised field schema from a fillable (AcroForm) PDF."""

    def __init__(self) -> None:
        self._used_keys: set = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_schema(
        self, pdf_path: str, filter_clear_button: bool = True
    ) -> dict[str, Any]:
        """Extract and return the normalised schema dict.

        Args:
            pdf_path:            Path to the fillable PDF.
            filter_clear_button: Drop 'Clear Form' button fields.

        Returns:
            Dict mapping normalised_key → field metadata.
        """
        self._used_keys = set()

        # pypdf: labels + field types
        reader = PdfReader(pdf_path)
        pfields = reader.get_fields() or {}
        meta: dict[str, dict] = {
            name: {
                "label": (d.get("/TU") or "").strip(),
                "ft": (d.get("/FT") or "").strip(),
            }
            for name, d in pfields.items()
        }

        # PyMuPDF: bounding boxes + page numbers
        doc = fitz.open(pdf_path)
        widgets: dict[str, dict] = {}
        for pno in range(doc.page_count):
            for w in doc[pno].widgets() or []:
                fname = (w.field_name or "").strip()
                if fname:
                    r = w.rect
                    widgets.setdefault(
                        fname,
                        {"page": pno, "bbox": [float(r.x0), float(r.y0), float(r.x1), float(r.y1)]},
                    )

        out: dict[str, Any] = {}
        for pdf_name in sorted(set(meta) | set(widgets)):
            label = meta.get(pdf_name, {}).get("label", "")
            ft = meta.get(pdf_name, {}).get("ft", "")
            bbox = widgets.get(pdf_name, {}).get("bbox")
            page = widgets.get(pdf_name, {}).get("page")

            if filter_clear_button and "Button" in pdf_name and "Clear" in label:
                continue
            if _is_parent_field(pdf_name, label, ft, bbox):
                continue

            base = label if label else pdf_name.split(".")[-1]
            base_norm = slugify(base)
            group: str | None = None
            part: str | None = None

            phone = _detect_phone_part(label, pdf_name)
            if phone:
                group, part = phone
                base_norm = f"{group}_{part}"

            date = _detect_date_part(pdf_name)
            if date:
                group, part = date
                base_norm = f"{group}_{part}"

            med = _detect_medication(pdf_name)
            if med:
                group, part = med
                base_norm = f"{group}_{part}"

            key = self._unique_key(base_norm)
            out[key] = {
                "label": label or pdf_name,
                "type": _pdf_type(ft),
                "bbox": bbox,
                "normalized_name": key,
                "pdf_name": pdf_name,
                "page": page,
                "group": group,
                "part": part,
            }

        logger.info("Schema extraction complete: %d fields from %s", len(out), pdf_path)
        return out

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _unique_key(self, base: str) -> str:
        if base not in self._used_keys:
            self._used_keys.add(base)
            return base
        i = 2
        while f"{base}_{i}" in self._used_keys:
            i += 1
        key = f"{base}_{i}"
        self._used_keys.add(key)
        return key


# ------------------------------------------------------------------
# Module-level helpers (pure functions — easy to test in isolation)
# ------------------------------------------------------------------

def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[''']", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "field"


def _pdf_type(ft: str) -> str:
    return {"/Tx": "text", "/Btn": "button", "/Ch": "choice", "/Sig": "signature"}.get(
        (ft or "").strip(), "unknown"
    )


def _is_parent_field(
    pdf_name: str, label: str, ft: str, bbox: list | None
) -> bool:
    if bbox is not None:
        return False
    if (label or "").strip():
        return False
    if (ft or "").strip():
        return False
    return "." not in pdf_name


def _detect_date_part(pdf_name: str) -> tuple[str, str] | None:
    m = re.search(r"(date[\w]*)[_. ]([dmy])\b", pdf_name, re.IGNORECASE)
    if not m:
        return None
    group = slugify(m.group(1))
    part = {"d": "day", "m": "month", "y": "year"}[m.group(2).lower()]
    return group, part


def _detect_phone_part(label: str, pdf_name: str) -> tuple[str, str] | None:
    t = (label or pdf_name).lower()
    if "home phone" in t:
        group = "home_phone"
    elif "cell phone" in t or "mobile phone" in t:
        group = "cell_phone"
    elif "work phone" in t:
        group = "work_phone"
    else:
        return None

    if "area code" in t:
        part = "area_code"
    elif "first three" in t or "first 3" in t:
        part = "first3"
    elif "last four" in t or "last 4" in t:
        part = "last4"
    else:
        part = "full"

    return group, part


def _detect_medication(pdf_name: str) -> tuple[str, str] | None:
    m = re.search(r"\b(medication|dose|often)\s*([0-9]+)\b", pdf_name, re.IGNORECASE)
    if not m:
        return None
    raw_part = slugify(m.group(1))
    part = "name" if raw_part == "medication" else raw_part
    group = f"medication_{m.group(2)}"
    return group, part
