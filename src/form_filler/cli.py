"""CLI entry point and composition root.

This is the ONLY place where concrete classes are wired together.
Everything else depends on abstractions.

Usage:
  form-filler                        # runs with env vars / defaults
  form-filler --form myform.pdf      # override form path
  form-filler --no-llm               # disable LLM fallback
  form-filler --log-format json      # structured logging
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="form-filler",
        description="Automated medical form population pipeline",
    )
    p.add_argument("--form", metavar="PDF", help="Fillable PDF (overrides FORM_PDF env var)")
    p.add_argument("--output", metavar="PDF", help="Output PDF (overrides OUTPUT_PDF env var)")
    p.add_argument("--no-llm", action="store_true", help="Disable LLM fallback for SOAP extraction")
    p.add_argument("--no-ocr", action="store_true", help="Disable OCR fallback for lab PDF")
    p.add_argument("--log-level", default=None, choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument("--log-format", default=None, choices=["console", "json"])
    return p


def main() -> None:  # noqa: C901
    load_dotenv()  # Load .env if present (no-op in production)

    args = _build_parser().parse_args()

    # Import after dotenv so env vars are available
    from form_filler.config import PipelineConfig
    from form_filler.logging_config import setup_logging

    config = PipelineConfig.from_env()

    # Apply CLI overrides
    if args.form:
        from pathlib import Path
        config.form_pdf = Path(args.form)
    if args.output:
        from pathlib import Path
        config.output_pdf = Path(args.output)
    if args.no_llm:
        config.extraction.use_llm_fallback = False
    if args.no_ocr:
        config.extraction.use_ocr_fallback = False
    if args.log_level:
        config.log_level = args.log_level
    if args.log_format:
        config.log_format = args.log_format

    setup_logging(config.log_level, config.log_format)

    # Validate required input files
    required = (
        config.form_pdf, config.demographics_json,
        config.soap_notes_txt, config.lab_result_pdf,
    )
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print(f"[form-filler] Missing required files: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    # ----- Composition root: wire concrete implementations -----
    from form_filler.extractors.demographics import DemographicsExtractor
    from form_filler.extractors.lab import LabExtractor
    from form_filler.extractors.soap import SOAPExtractor
    from form_filler.pdf_populator import PDFPopulator
    from form_filler.pipeline import Pipeline
    from form_filler.reconciler import Reconciler
    from form_filler.schema.acroform import SchemaExtractor

    pipeline = Pipeline(
        config=config,
        schema_extractor=SchemaExtractor(),
        extractors=[
            DemographicsExtractor(str(config.demographics_json), config.extraction),
            SOAPExtractor(str(config.soap_notes_txt), config.extraction),
            LabExtractor(str(config.lab_result_pdf), config.extraction),
        ],
        reconciler=Reconciler(),
        populator=PDFPopulator(),
    )

    result = pipeline.run()

    print(f"\nDone. Populated PDF → {result.output_pdf}")
    if result.report:
        print(f"  Filled:  {len(result.report.filled)} fields")
        print(f"  Skipped: {len(result.report.skipped)} fields")
        if result.report.missing_pdf_fields:
            print(f"  Missing in PDF: {list(result.report.missing_pdf_fields.keys())}")


if __name__ == "__main__":
    main()
