"""Pipeline orchestrator.

Depends on abstractions (List[BaseExtractor], Reconciler, PDFPopulator, SchemaExtractor)
— never on concrete implementations. This is the Dependency Inversion principle in action.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from form_filler.config import PipelineConfig
from form_filler.extractors.base import BaseExtractor, ExtractionResult
from form_filler.pdf_populator import PDFPopulator, PopulationReport
from form_filler.reconciler import Reconciler
from form_filler.schema.acroform import SchemaExtractor

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    schema: dict[str, Any]
    answers: ExtractionResult
    output_pdf: str | None
    report: PopulationReport | None


class Pipeline:
    """Orchestrates schema extraction → information extraction → reconciliation → PDF population.

    Constructor receives all dependencies as abstractions — concrete classes are
    wired together in cli.py (the composition root).
    """

    def __init__(
        self,
        config: PipelineConfig,
        schema_extractor: SchemaExtractor,
        extractors: list[BaseExtractor],
        reconciler: Reconciler,
        populator: PDFPopulator,
    ) -> None:
        self._config = config
        self._schema_extractor = schema_extractor
        self._extractors = extractors
        self._reconciler = reconciler
        self._populator = populator

    def run(self) -> PipelineResult:
        """Execute the full pipeline end-to-end."""
        logger.info("=== Form-Filler pipeline starting ===")

        # Ensure output directory exists before writing any files
        self._config.schema_json.parent.mkdir(parents=True, exist_ok=True)
        self._config.output_pdf.parent.mkdir(parents=True, exist_ok=True)

        # Step 1: Extract schema
        logger.info("Step 1/3 — Extracting form schema from %s", self._config.form_pdf)
        schema = self._schema_extractor.extract_schema(str(self._config.form_pdf))
        self._save_json(schema, self._config.schema_json)

        # Step 2: Run extractors sequentially.
        # Each extractor receives the accumulated results as `already_filled`
        # so it can skip fields already known (completion-only targeting).
        logger.info("Step 2/3 — Running %d extractor(s)", len(self._extractors))
        accumulated: ExtractionResult = {}
        for extractor in self._extractors:
            logger.info("  Extractor: %s", extractor.source_name)
            result = extractor.extract(schema=schema, already_filled=accumulated)
            accumulated = self._reconciler.merge(accumulated, result)

        self._save_json(accumulated, self._config.answers_json)

        # Step 3: Populate PDF
        logger.info("Step 3/3 — Populating PDF → %s", self._config.output_pdf)
        output_pdf, report = self._populator.populate(
            form_pdf_path=str(self._config.form_pdf),
            schema=schema,
            answers=accumulated,
            output_path=str(self._config.output_pdf),
        )

        logger.info("=== Pipeline complete ===")
        return PipelineResult(
            schema=schema,
            answers=accumulated,
            output_pdf=output_pdf,
            report=report,
        )

    @staticmethod
    def _save_json(data: Any, path: Any) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        logger.debug("Saved %s", path)
