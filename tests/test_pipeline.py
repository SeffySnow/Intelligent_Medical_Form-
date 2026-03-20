"""Integration tests for Pipeline — all dependencies mocked."""

import pytest
from unittest.mock import MagicMock
from pathlib import Path

from form_filler.config import PipelineConfig, ExtractionConfig
from form_filler.pipeline import Pipeline, PipelineResult
from form_filler.pdf_populator import PopulationReport


@pytest.fixture
def pipeline_config(tmp_path):
    cfg = PipelineConfig(
        form_pdf=tmp_path / "form.pdf",
        schema_json=tmp_path / "schema.json",
        answers_json=tmp_path / "answers.json",
        output_pdf=tmp_path / "out.pdf",
        extraction=ExtractionConfig(use_llm_fallback=False, use_ocr_fallback=False),
    )
    # Create placeholder files so Pipeline doesn't crash on path checks
    (tmp_path / "form.pdf").write_bytes(b"fake")
    return cfg


def _make_pipeline(config, extractors=None, schema=None, answers=None):
    schema_extractor = MagicMock()
    schema_extractor.extract_schema.return_value = schema or {"field_a": {"type": "text", "pdf_name": "F.A"}}

    reconciler = MagicMock()
    reconciler.merge.side_effect = lambda *args: {k: v for d in args for k, v in d.items()}

    populator = MagicMock()
    populator.populate.return_value = ("out.pdf", PopulationReport(filled={"field_a": "val"}))

    if extractors is None:
        mock_ext = MagicMock()
        mock_ext.source_name = "mock_source"
        mock_ext.extract.return_value = answers or {"field_a": {"value": "val", "confidence": 0.9}}
        extractors = [mock_ext]

    return Pipeline(
        config=config,
        schema_extractor=schema_extractor,
        extractors=extractors,
        reconciler=reconciler,
        populator=populator,
    )


class TestPipeline:
    def test_run_returns_result(self, pipeline_config):
        pipeline = _make_pipeline(pipeline_config)
        result = pipeline.run()
        assert isinstance(result, PipelineResult)
        assert result.schema is not None
        assert result.answers is not None
        assert result.output_pdf == "out.pdf"

    def test_schema_extractor_called_with_form_pdf(self, pipeline_config):
        pipeline = _make_pipeline(pipeline_config)
        pipeline.run()
        pipeline._schema_extractor.extract_schema.assert_called_once_with(
            str(pipeline_config.form_pdf)
        )

    def test_extractors_called_with_schema(self, pipeline_config):
        mock_ext = MagicMock()
        mock_ext.source_name = "mock"
        mock_ext.extract.return_value = {}
        pipeline = _make_pipeline(pipeline_config, extractors=[mock_ext])
        pipeline.run()
        mock_ext.extract.assert_called_once()
        call_kwargs = mock_ext.extract.call_args.kwargs
        assert "schema" in call_kwargs

    def test_extractors_receive_accumulated_already_filled(self, pipeline_config):
        """Each extractor receives the merged results of all previous extractors."""
        ext1 = MagicMock()
        ext1.source_name = "source1"
        ext1.extract.return_value = {"f1": {"value": "v1", "confidence": 0.9}}

        ext2 = MagicMock()
        ext2.source_name = "source2"
        ext2.extract.return_value = {}

        pipeline = _make_pipeline(pipeline_config, extractors=[ext1, ext2])
        pipeline.run()

        # ext2's already_filled should contain ext1's result
        ext2_call = ext2.extract.call_args
        already = ext2_call.kwargs.get("already_filled", {})
        assert "f1" in already

    def test_populator_called(self, pipeline_config):
        pipeline = _make_pipeline(pipeline_config)
        pipeline.run()
        pipeline._populator.populate.assert_called_once()

    def test_schema_saved_to_json(self, pipeline_config):
        pipeline = _make_pipeline(pipeline_config)
        pipeline.run()
        assert pipeline_config.schema_json.exists()

    def test_answers_saved_to_json(self, pipeline_config):
        pipeline = _make_pipeline(pipeline_config)
        pipeline.run()
        assert pipeline_config.answers_json.exists()
