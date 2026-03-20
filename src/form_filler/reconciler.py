"""Reconciler: confidence-based merge of multiple extraction results.

Single Responsibility: combine extraction dicts, keeping the highest-confidence
value for each field.
Open/Closed: swap merge strategy by subclassing without touching the pipeline.
"""

from __future__ import annotations

import logging

from form_filler.extractors.base import ExtractionResult

logger = logging.getLogger(__name__)


class Reconciler:
    """Merges extraction results, preferring higher-confidence values."""

    def merge(self, *results: ExtractionResult) -> ExtractionResult:
        """Merge any number of extraction dicts.

        For each field, the entry with the highest ``confidence`` wins.

        Args:
            *results: Extraction dicts from one or more extractors.

        Returns:
            A single merged ExtractionResult.
        """
        combined: ExtractionResult = {}
        for extraction in results:
            for field, data in extraction.items():
                if field not in combined:
                    combined[field] = data
                elif data.get("confidence", 0.0) > combined[field].get("confidence", 0.0):
                    logger.debug(
                        "Field '%s': replacing (conf=%.2f) with (conf=%.2f) from '%s'",
                        field,
                        combined[field].get("confidence", 0.0),
                        data.get("confidence", 0.0),
                        data.get("source", "?"),
                    )
                    combined[field] = data
        return combined
