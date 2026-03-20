"""Demographics extractor.

Single Responsibility: extract patient info from a structured demographics.json.
All transformation logic (date/phone parsing, address formatting) lives in utils.py.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from form_filler.config import ExtractionConfig
from form_filler.extractors.base import BaseExtractor, ExtractionResult
from form_filler.extractors.utils import (
    format_address,
    make_entry,
    parse_date,
    parse_phone,
)

logger = logging.getLogger(__name__)

# Maps demographics.json keys → schema field key(s).
# Lists indicate one-to-many mappings (split values).
_FIELD_MAP: dict[str, Any] = {
    "patient_name": "patient_name_last_first_middle_initial",
    "dob": ["date_of_birth_dd", "date_of_birth_mm", "date_of_birth_yyyy"],
    "phone_home": ["home_phone_area_code", "home_phone_first3", "home_phone_last4"],
    "phone_mobile": ["cell_phone_area_code", "cell_phone_first3", "cell_phone_last4"],
    "address": "address_street_city_province_postal_code",
}

_DATE_PARTS = ["day", "month", "year"]
_PHONE_PARTS = ["area_code", "first3", "last4"]


class DemographicsExtractor(BaseExtractor):
    """Extracts structured patient data from demographics.json."""

    def __init__(self, source_path: str, config: ExtractionConfig) -> None:
        self._source_path = source_path
        self._config = config

    @property
    def source_name(self) -> str:
        return "demographics.json"

    def extract(
        self,
        schema: dict[str, Any],
        already_filled: ExtractionResult | None = None,
    ) -> ExtractionResult:
        confidence = self._config.demographics_confidence
        results: ExtractionResult = {}

        with open(self._source_path, encoding="utf-8") as fh:
            demographics: dict[str, Any] = json.load(fh)

        for json_key, json_value in demographics.items():
            if json_key not in _FIELD_MAP:
                continue

            schema_fields = _FIELD_MAP[json_key]

            if isinstance(schema_fields, list):
                self._extract_split(
                    json_key, json_value, schema_fields, schema,
                    confidence, results,
                )
            else:
                self._extract_single(
                    json_key, json_value, schema_fields, schema,
                    confidence, results,
                )

        logger.info("Demographics extraction complete: %d fields", len(results))
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_split(
        self,
        json_key: str,
        json_value: Any,
        schema_fields: list,
        schema: dict[str, Any],
        confidence: float,
        results: ExtractionResult,
    ) -> None:
        if json_key == "dob":
            parts = parse_date(str(json_value))
            part_names = _DATE_PARTS
        else:  # phone_home / phone_mobile
            parts = parse_phone(str(json_value))
            part_names = _PHONE_PARTS

        for field_key, part_name in zip(schema_fields, part_names):
            if field_key not in schema:
                continue
            results[field_key] = make_entry(
                value=parts.get(part_name, ""),
                source=self.source_name,
                reasoning=f"{json_key}_parse.{part_name}",
                confidence=confidence,
            )

    def _extract_single(
        self,
        json_key: str,
        json_value: Any,
        schema_field: str,
        schema: dict[str, Any],
        confidence: float,
        results: ExtractionResult,
    ) -> None:
        if schema_field not in schema:
            return
        if json_key == "address":
            value = format_address(json_value)
            reasoning = "address_format"
        else:
            value = json_value
            reasoning = "direct"

        results[schema_field] = make_entry(
            value=value,
            source=self.source_name,
            reasoning=reasoning,
            confidence=confidence,
        )
