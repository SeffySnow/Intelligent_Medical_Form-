"""Lab result extractor.

Single Responsibility: extract medications (and optionally phone numbers)
from a lab result PDF using embedded text, with optional OCR fallback.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from form_filler.config import ExtractionConfig
from form_filler.extractors.base import BaseExtractor, ExtractionResult
from form_filler.extractors.utils import is_filled, make_entry

logger = logging.getLogger(__name__)

_FREQ_PATTERNS = [
    r"once\s+a\s+day", r"twice\s+a\s+day", r"three\s+times\s+a\s+day",
    r"twice\s+daily", r"once\s+daily", r"daily", r"every\s+day",
    r"\bBID\b", r"\bTID\b", r"\bQID\b", r"\bPRN\b", r"as\s+needed",
]
_FREQ_RE = re.compile("|".join(_FREQ_PATTERNS), re.IGNORECASE)


class LabExtractor(BaseExtractor):
    """Extracts medications and contact info from a lab result PDF."""

    def __init__(self, source_path: str, config: ExtractionConfig) -> None:
        self._source_path = source_path
        self._config = config

    @property
    def source_name(self) -> str:
        return "lab_result.pdf"

    def extract(
        self,
        schema: dict[str, Any],
        already_filled: ExtractionResult | None = None,
    ) -> ExtractionResult:
        already_filled = already_filled or {}
        text, used_ocr = self._load_text()
        if not text:
            logger.warning("No text extracted from %s; skipping", self.source_name)
            return {}

        base_conf = 0.65 if used_ocr else self._config.lab_confidence
        results: ExtractionResult = {}

        meds = _parse_medication_lines(text)
        self._fill_medication_slots(meds, schema, already_filled, results, base_conf)
        self._fill_phone(text, schema, already_filled, results, base_conf)

        filled = sum(1 for v in results.values() if v.get("value") is not None)
        logger.info("Lab extraction complete: %d fields", filled)
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_text(self) -> tuple[str, bool]:
        """Return (text, used_ocr). Tries embedded text first, OCR fallback second."""
        text = ""
        try:
            import fitz
            doc = fitz.open(self._source_path)
            text = "\n".join(doc[i].get_text("text") or "" for i in range(doc.page_count)).strip()
        except Exception:
            pass

        if self._config.use_ocr_fallback and len(text) < 50:
            try:
                import io

                import fitz
                import pytesseract
                from PIL import Image

                doc = fitz.open(self._source_path)
                parts = []
                for i in range(doc.page_count):
                    pix = doc[i].get_pixmap(dpi=self._config.ocr_dpi)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    parts.append(pytesseract.image_to_string(img) or "")
                return "\n".join(parts).strip(), True
            except Exception:
                logger.warning("OCR fallback failed; no text from %s", self.source_name)

        return text, False

    def _fill_medication_slots(
        self,
        meds: list[tuple[str, str, str, str]],
        schema: dict[str, Any],
        already_filled: ExtractionResult,
        results: ExtractionResult,
        conf: float,
    ) -> None:
        for name, dose, freq, evidence in meds:
            norm = _norm_name(name)
            slot = _find_existing_slot(norm, already_filled, results) or _find_next_slot(
                already_filled, results
            )
            if slot is None:
                break

            name_k, dose_k, often_k = (
                f"medication_{slot}_name",
                f"medication_{slot}_dose",
                f"medication_{slot}_often",
            )
            if name_k in schema and not is_filled(name_k, already_filled):
                results[name_k] = make_entry(name, self.source_name,
                    "extracted from lab_result medication section", conf, evidence)
            if dose_k in schema and not is_filled(dose_k, already_filled):
                results[dose_k] = make_entry(dose, self.source_name,
                    "extracted numeric mg dose from lab_result", conf, evidence)
            if freq and often_k in schema and not is_filled(often_k, already_filled):
                results[often_k] = make_entry(freq.lower(), self.source_name,
                    "extracted frequency from lab_result", conf, evidence)

    def _fill_phone(
        self,
        text: str,
        schema: dict[str, Any],
        already_filled: ExtractionResult,
        results: ExtractionResult,
        conf: float,
    ) -> None:
        phones = re.findall(r"\b(\d{3})[-.\s]?(\d{3})[-.\s]?(\d{4})\b", text)
        if len(phones) != 1:
            return

        area, first3, last4 = phones[0]
        evidence = f"{area}-{first3}-{last4}"

        for prefix in ("cell_phone", "home_phone"):
            fields = [f"{prefix}_area_code", f"{prefix}_first3", f"{prefix}_last4"]
            if all(f in schema and not is_filled(f, already_filled) for f in fields):
                rsn = "parsed phone"
                results[fields[0]] = make_entry(area, self.source_name, rsn, conf, evidence)
                results[fields[1]] = make_entry(first3, self.source_name, rsn, conf, evidence)
                results[fields[2]] = make_entry(last4, self.source_name, rsn, conf, evidence)
                break


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _parse_medication_lines(text: str) -> list[tuple[str, str, str, str]]:
    """Extract (name, dose_mg, frequency, raw_line) from a Medication: section."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    med_lines: list[str] = []
    in_meds = False
    current = ""

    for ln in lines:
        if re.match(r"^Medication\s*:\s*$", ln, re.IGNORECASE):
            in_meds = True
            current = ""
            continue
        if in_meds and re.match(r"^[A-Za-z][A-Za-z /-]*:\s*$", ln):
            break
        if in_meds:
            if ln.startswith(("•", "-", "*")):
                if current:
                    med_lines.append(current.strip())
                current = ln.lstrip("•-* ").strip()
            else:
                current = (current + " " + ln).strip() if current else ln

    if in_meds and current:
        med_lines.append(current.strip())

    results = []
    for ln in med_lines:
        m = re.search(
            r"\b([A-Z][A-Za-z0-9/-]{2,}(?:\s+[A-Z][A-Za-z0-9/-]{2,})*)\b\s+(\d+(?:\.\d+)?)\s*mg\b",
            ln,
        )
        if not m:
            continue
        name, dose = m.group(1).strip(), m.group(2).strip()
        freq_m = _FREQ_RE.search(ln)
        freq = freq_m.group(0).strip() if freq_m else ""
        results.append((name, dose, freq, ln))

    return results


def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _find_existing_slot(
    norm_name: str,
    already_filled: ExtractionResult,
    results: ExtractionResult,
) -> int | None:
    for i in range(1, 6):
        k = f"medication_{i}_name"
        existing = None
        if k in results and isinstance(results[k], dict):
            existing = results[k].get("value")
        if existing is None and k in already_filled and isinstance(already_filled[k], dict):
            existing = already_filled[k].get("value")
        if existing and _norm_name(str(existing)) == norm_name:
            return i
    return None


def _find_next_slot(
    already_filled: ExtractionResult,
    results: ExtractionResult,
) -> int | None:
    for i in range(1, 6):
        k = f"medication_{i}_name"
        if not is_filled(k, already_filled) and k not in results:
            return i
    return None
