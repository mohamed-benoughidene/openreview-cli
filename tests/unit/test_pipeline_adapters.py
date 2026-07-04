"""Unit tests for pipeline stage adapters.

Tests validate each adapter's contract: reads expected context keys,
writes expected output keys, and handles errors gracefully.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import Mock, patch

import pytest

from openreview_cli.pipeline.adapters import (
    ChunkStage,
    GenerateStage,
    ParseStage,
    RetrieveStage,
    StripStage,
)
from openreview_cli.pipeline.base import Stage
from openreview_cli.pipeline.errors import StageError

# ── Helpers ──────────────────────────────────────────────────────────────


def _make_mock_clause(id: str = "1", text: str = "test clause") -> Mock:
    clause = Mock(spec=["id", "text", "title", "level"])
    clause.id = id
    clause.text = text
    clause.title = "Test"
    clause.level = 1
    return clause


def _make_mock_document() -> Mock:
    doc = Mock(spec=["source_path", "format", "page_count", "clause_count"])
    doc.source_path = "/path/to/doc.pdf"
    doc.format = "pdf"
    doc.page_count = 1
    doc.clause_count = 1
    return doc


def _make_mock_chunk(id: str = "chunk-1") -> Mock:
    c = Mock(spec=["id", "text", "source_clause_id", "source_clause_title"])
    c.id = id
    c.text = "test chunk text"
    c.source_clause_id = "1"
    c.source_clause_title = "Test"
    return c


def _make_mock_retrieval_result(id: str = "chunk-1") -> Mock:
    r = Mock(spec=["chunk_id", "text", "score"])
    r.chunk_id = id
    r.text = "retrieved text"
    r.score = 0.95
    return r


# ── ParseStage ──────────────────────────────────────────────────────────


class TestParseStage:
    def test_contract(self) -> None:
        """ParseStage reads document_path, writes document and clauses."""
        mock_doc = _make_mock_document()
        mock_clauses = [_make_mock_clause("1"), _make_mock_clause("2")]

        with patch(
            "openreview_cli.parsing.stream.parse_document",
            return_value=(mock_doc, mock_clauses),
        ):
            stage = ParseStage()
            ctx = {"document_path": "/fake/doc.pdf"}
            result = asyncio.run(stage.run(ctx))

        assert "document" in result
        assert "clauses" in result
        assert result["document"] is mock_doc
        assert result["clauses"] == mock_clauses

    def test_preserves_name_and_critical(self) -> None:
        stage = ParseStage()
        assert stage.name == "parse"
        assert stage.critical is True

    def test_missing_document_path_raises(self) -> None:
        stage = ParseStage()
        with pytest.raises(KeyError, match="document_path"):
            asyncio.run(stage.run({}))

    def test_parse_error_wrapped(self) -> None:
        with patch(
            "openreview_cli.parsing.stream.parse_document",
            side_effect=ValueError("corrupt file"),
        ):
            stage = ParseStage()
            ctx = {"document_path": "/fake/bad.pdf"}
            with pytest.raises(StageError, match="ParseStage failed"):
                asyncio.run(stage.run(ctx))


# ── StripStage ──────────────────────────────────────────────────────────


class TestStripStage:
    def test_contract(self) -> None:
        """StripStage reads clauses, writes stripped_clauses."""
        clauses = [_make_mock_clause("1")]
        document = _make_mock_document()

        with patch(
            "openreview_cli.pii.strip_pii_clauses",
            return_value=(clauses, Mock()),
        ):
            stage = StripStage()
            ctx = {"clauses": clauses, "document": document}
            result = asyncio.run(stage.run(ctx))

        assert "stripped_clauses" in result
        assert result["stripped_clauses"] == clauses

    def test_no_pii_passthrough(self) -> None:
        """When no_pii=True, clauses are passed through without calling the engine."""
        clauses = [_make_mock_clause("1")]

        with patch(
            "openreview_cli.pii.strip_pii_clauses",
        ) as mock_strip:
            stage = StripStage(no_pii=True)
            ctx = {"clauses": clauses}
            result = asyncio.run(stage.run(ctx))

        assert "stripped_clauses" in result
        assert len(result["stripped_clauses"]) == 1
        mock_strip.assert_not_called()

    def test_preserves_name(self) -> None:
        stage = StripStage()
        assert stage.name == "strip"
        assert stage.critical is False

    def test_missing_clauses_raises(self) -> None:
        stage = StripStage()
        with pytest.raises(KeyError, match="clauses"):
            asyncio.run(stage.run({}))

    def test_strip_error_wrapped(self) -> None:
        with patch(
            "openreview_cli.pii.strip_pii_clauses",
            side_effect=ValueError("engine error"),
        ):
            stage = StripStage()
            ctx = {"clauses": [_make_mock_clause("1")], "document": _make_mock_document()}
            with pytest.raises(StageError, match="StripStage failed"):
                asyncio.run(stage.run(ctx))


# ── ChunkStage ──────────────────────────────────────────────────────────


class TestChunkStage:
    def test_contract_with_stripped(self) -> None:
        """ChunkStage reads stripped_clauses and writes chunks."""
        clauses = [_make_mock_clause("1")]
        chunks = [_make_mock_chunk("c1")]

        with patch(
            "openreview_cli.chunking.stream_chunks",
            return_value=iter(chunks),
        ):
            stage = ChunkStage()
            ctx = {"stripped_clauses": clauses}
            result = asyncio.run(stage.run(ctx))

        assert "chunks" in result
        assert result["chunks"] == chunks

    def test_fallback_to_clauses(self) -> None:
        """Falls back to ctx['clauses'] when stripped_clauses is absent."""
        clauses = [_make_mock_clause("1")]
        chunks = [_make_mock_chunk("c1")]

        with patch(
            "openreview_cli.chunking.stream_chunks",
            return_value=iter(chunks),
        ):
            stage = ChunkStage()
            ctx = {"clauses": clauses}
            result = asyncio.run(stage.run(ctx))

        assert "chunks" in result
        assert result["chunks"] == chunks

    def test_preserves_name(self) -> None:
        stage = ChunkStage()
        assert stage.name == "chunk"
        assert stage.critical is False

    def test_no_input_raises(self) -> None:
        """Neither stripped_clauses nor clauses present."""
        stage = ChunkStage()
        with pytest.raises(KeyError, match="clauses"):
            asyncio.run(stage.run({}))

    def test_config_passed_through(self) -> None:
        from openreview_cli.chunking.models import ChunkConfig

        config = ChunkConfig(chunk_size=256, chunk_overlap=25)
        clauses = [_make_mock_clause("1")]
        chunks = [_make_mock_chunk("c1")]

        with patch(
            "openreview_cli.chunking.stream_chunks",
            return_value=iter(chunks),
        ) as mock_stream:
            stage = ChunkStage(config=config)
            ctx = {"clauses": clauses}
            asyncio.run(stage.run(ctx))

            mock_stream.assert_called_once()
            args, _kwargs = mock_stream.call_args
            assert args[1] is config


# ── RetrieveStage ───────────────────────────────────────────────────────


class TestRetrieveStage:
    def test_contract_with_custom_query(self) -> None:
        """RetrieveStage reads chunks, writes retrieved with custom query."""
        chunks = [_make_mock_chunk("c1")]
        results = [_make_mock_retrieval_result("c1")]

        mock_engine = Mock()
        mock_engine.retrieve.return_value = results

        stage = RetrieveStage(
            engine=mock_engine,
        )
        ctx = {"chunks": chunks, "retrieval_query": "test query"}
        result = asyncio.run(stage.run(ctx))

        assert "retrieved" in result
        assert result["retrieved"] == results
        mock_engine.retrieve.assert_called_once()

    def test_contract_without_custom_query(self) -> None:
        """Uses chunk text as query when retrieval_query is absent."""
        chunks = [_make_mock_chunk("c1")]
        results = [_make_mock_retrieval_result("c1")]

        mock_engine = Mock()
        mock_engine.retrieve.return_value = results

        stage = RetrieveStage(engine=mock_engine)
        ctx = {"chunks": chunks}
        result = asyncio.run(stage.run(ctx))

        assert "retrieved" in result
        assert result["retrieved"] == results

    def test_preserves_name(self) -> None:
        stage = RetrieveStage(engine=Mock())
        assert stage.name == "retrieve"
        assert stage.critical is False

    def test_missing_chunks_raises(self) -> None:
        stage = RetrieveStage(engine=Mock())
        with pytest.raises(KeyError, match="chunks"):
            asyncio.run(stage.run({}))

    def test_no_engine_config_raises(self) -> None:
        """Without engine or db_path, stage raises a clear error."""
        stage = RetrieveStage()
        ctx = {"chunks": [_make_mock_chunk("c1")]}
        with pytest.raises(StageError, match="engine instance or a db_path"):
            asyncio.run(stage.run(ctx))


# ── GenerateStage ───────────────────────────────────────────────────────


class TestGenerateStage:
    def test_contract(self) -> None:
        """GenerateStage reads retrieved and writes generated."""
        retrieved = [_make_mock_retrieval_result("c1")]

        mock_gateway = Mock()
        mock_gateway.chat.return_value = "Generated review output"

        stage = GenerateStage(gateway=mock_gateway)
        ctx = {"retrieved": retrieved}
        result = asyncio.run(stage.run(ctx))

        assert "generated" in result
        assert result["generated"] == "Generated review output"
        mock_gateway.chat.assert_called_once()

    def test_with_playbook(self) -> None:
        """Playbook metadata is included in the prompt."""
        retrieved = [_make_mock_retrieval_result("c1")]
        playbook = Mock()
        playbook.id = "nda-v1"
        playbook.mode = "precheck"

        mock_gateway = Mock()
        mock_gateway.chat.return_value = "Output with playbook"

        stage = GenerateStage(gateway=mock_gateway)
        ctx = {"retrieved": retrieved, "playbook": playbook}
        result = asyncio.run(stage.run(ctx))

        assert result["generated"] == "Output with playbook"

    def test_preserves_name(self) -> None:
        stage = GenerateStage(gateway=Mock())
        assert stage.name == "generate"
        assert stage.critical is False

    def test_missing_retrieved_raises(self) -> None:
        stage = GenerateStage(gateway=Mock())
        with pytest.raises(KeyError, match="retrieved"):
            asyncio.run(stage.run({}))

    def test_generate_error_wrapped(self) -> None:
        retrieved = [_make_mock_retrieval_result("c1")]
        mock_gateway = Mock()
        mock_gateway.chat.side_effect = RuntimeError("API error")

        stage = GenerateStage(gateway=mock_gateway)
        ctx = {"retrieved": retrieved}
        with pytest.raises(StageError, match="GenerateStage failed"):
            asyncio.run(stage.run(ctx))


# ── Stage as Pipeline component ─────────────────────────────────────────


class TestAdaptersInPipeline:
    """Verify adapters compose correctly when plugged into the Pipeline runner."""

    def test_two_stage_subset_pipeline(self) -> None:
        """Pipeline with ParseStage + ChunkStage produces expected keys."""
        from openreview_cli.pipeline.runner import Pipeline

        mock_doc = _make_mock_document()
        mock_clauses = [_make_mock_clause("1"), _make_mock_clause("2")]
        mock_chunks = [_make_mock_chunk("c1"), _make_mock_chunk("c2")]

        with (
            patch(
                "openreview_cli.parsing.stream.parse_document",
                return_value=(mock_doc, mock_clauses),
            ),
            patch(
                "openreview_cli.chunking.stream_chunks",
                return_value=iter(mock_chunks),
            ),
        ):
            pipeline = Pipeline(stages=[ParseStage(), ChunkStage()])
            ctx = {"document_path": "/fake/doc.pdf"}
            report = asyncio.run(pipeline.run(ctx))

        assert len(report.stage_results) == 2
        # Context should contain keys from both stages
        assert "document" in report.stage_results[0].output_keys
        assert "chunks" in report.stage_results[1].output_keys

    def test_stage_independent_instantiation(self) -> None:
        """Each adapter can be instantiated and run in isolation."""
        p_stage = ParseStage()
        assert p_stage.name == "parse"
        assert isinstance(p_stage, ParseStage)

        c_stage = ChunkStage()
        assert c_stage.name == "chunk"
        assert isinstance(c_stage, ChunkStage)


# ---------------------------------------------------------------------------
# CV-T-013: skip stage test
# ---------------------------------------------------------------------------


class TestSkipStage:
    """skip() wiring with should_skip()."""

    def test_skip_stage_not_called(self) -> None:
        """Stage with should_skip() returning True is not executed."""
        from openreview_cli.pipeline.runner import Pipeline

        class SkippableStage(Stage):
            name = "skippable"
            ran = False

            async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
                self.ran = True
                return {"result": "should_not_appear"}

            def should_skip(self, ctx: dict[str, Any]) -> bool:
                return bool(ctx.get("skip_it", False))

        stage = SkippableStage()
        pipeline = Pipeline(stages=[stage])
        report = asyncio.run(pipeline.run({"skip_it": True}))

        assert stage.ran is False, "Stage ran despite should_skip()=True"
        assert len(report.stage_results) == 1
        assert report.stage_results[0].skipped is True

    def test_skip_absent_key_not_skipped(self) -> None:
        """When should_skip returns False (default), stage runs normally."""
        from openreview_cli.pipeline.runner import Pipeline

        class DefaultStage(Stage):
            name = "default"

            async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
                return {"result": "ok"}

        stage = DefaultStage()
        pipeline = Pipeline(stages=[stage])
        report = asyncio.run(pipeline.run({}))

        assert len(report.stage_results) == 1
        assert report.stage_results[0].skipped is False
        assert report.stage_results[0].error is None
