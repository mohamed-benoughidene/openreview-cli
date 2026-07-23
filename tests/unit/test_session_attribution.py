"""Tests for session attribution across the review pipeline."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ── cost test helpers ──────────────────────────────────────────────────────


class _MockUsage:
    prompt_tokens = 100
    completion_tokens = 50


class _MockResponse:
    model = "gpt-4"
    usage = _MockUsage()


# ═══════════════════════════════════════════════════════════════════════════════
# Layer-level session attribution tests (1-4): direct function calls
# ═══════════════════════════════════════════════════════════════════════════════


class TestCallGatewayChatSessionForwarding:
    """Test 1: call_gateway_chat forwards session_id to Gateway.chat."""

    def test_call_gateway_chat_forwards_session_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, object] = {}

        def fake_chat(
            self_obj: object,
            slot: str,
            messages: list[dict[str, str]],
            **kwargs: object,
        ) -> str:
            captured.update(kwargs)
            return ""

        monkeypatch.setattr(
            "openreview_cli.gateway.router.Gateway.chat",
            fake_chat,
        )
        from openreview_cli.review._gateway import call_gateway_chat

        sid = f"review:{uuid.uuid4()}"
        call_gateway_chat("slot", [{"role": "user", "content": "hi"}], session_id=sid)
        assert captured.get("session_id") == sid


class TestExtractionSessionForwarding:
    """Test 2: extract_clause passes session_id to call_gateway_chat."""

    def test_extract_clause_passes_session_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured_sessions: list[str | None] = []

        def fake_call(slot: str, messages: list[dict[str, str]], **kwargs: object) -> str:
            captured_sessions.append(kwargs.get("session_id"))  # type: ignore[arg-type]
            return (
                '{"position": "preferred", "confidence": 0.9, '
                '"citation": "test", "category_match": true}'
            )

        monkeypatch.setattr(
            "openreview_cli.review.extraction.call_gateway_chat",
            fake_call,
        )
        from openreview_cli.review.extraction import extract_clause
        from openreview_cli.review.models import Position

        category = MagicMock()
        category.id = "confidentiality"
        category.name = "Confidentiality"
        category.description = ""
        category.default_position = Position.UNCERTAIN
        for name in ("preferred", "acceptable", "walkaway"):
            p = MagicMock()
            p.description = f"{name} desc"
            p.exemplars = []
            setattr(category, name, p)

        sid = f"review:{uuid.uuid4()}"
        extract_clause(
            clause_text="confidential clause text",
            clause_id="cl-1",
            category=category,
            extraction_model="extraction",
            session_id=sid,
        )
        assert captured_sessions == [sid]


class TestQASessionForwarding:
    """Test 3: verify_assessment passes session_id to call_gateway_chat."""

    def test_verify_assessment_passes_session_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured_sessions: list[str | None] = []

        def fake_call(slot: str, messages: list[dict[str, str]], **kwargs: object) -> str:
            captured_sessions.append(kwargs.get("session_id"))  # type: ignore[arg-type]
            return (
                '{"verdict": "agree", "confidence": 0.9, '
                '"citation_valid": true, "position_valid": true}'
            )

        monkeypatch.setattr(
            "openreview_cli.review.qa.call_gateway_chat",
            fake_call,
        )
        from openreview_cli.review.models import ClauseAssessment, Position, QAVerdict
        from openreview_cli.review.qa import verify_assessment

        assessment = ClauseAssessment(
            clause_id="cl-1",
            clause_text="test",
            playbook_category="confidentiality",
            position=Position.PREFERRED,
            confidence=0.9,
            citation="test",
            qa_verdict=QAVerdict.agree,
            extraction_model="extraction",
            qa_model="extraction",
        )
        category = MagicMock()
        category.id = "confidentiality"
        category.name = "Confidentiality"
        for name in ("preferred", "acceptable", "walkaway"):
            p = MagicMock()
            p.description = f"{name} desc"
            p.exemplars = []
            setattr(category, name, p)

        sid = f"review:{uuid.uuid4()}"
        verify_assessment(assessment, category, qa_model="extraction", session_id=sid)
        assert captured_sessions == [sid]


class TestGroundingSessionForwarding:
    """Test 4: run_grounding forwards session_id to discriminator's gateway.chat."""

    def test_run_grounding_forwards_session_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured_sessions: list[str | None] = []

        def _fake_chat(*a: object, **kw: object) -> str:
            captured_sessions.append(kw.get("session_id"))  # type: ignore[arg-type]
            return (
                '{"verdict": "grounded", "provenance": [{"clause_id": "cl-1", '
                '"text": "test", "score": 0.95}], "score": 0.95}'
            )

        fake_gateway = MagicMock()
        fake_gateway.chat = MagicMock(side_effect=_fake_chat)

        from openreview_cli.grounding import run_grounding
        from openreview_cli.parsing.models import Clause
        from openreview_cli.review.models import ClauseAssessment, Position, QAVerdict

        assessment = ClauseAssessment(
            clause_id="cl-1",
            clause_text="test clause text",
            playbook_category="confidentiality",
            position=Position.PREFERRED,
            confidence=0.9,
            citation="Section 3.1",
            qa_verdict=QAVerdict.agree,
            extraction_model="extraction",
            qa_model="extraction",
        )
        report = MagicMock()
        report.assessments = [assessment]
        report.document = MagicMock()

        source_document = MagicMock()
        source_document.pages = []

        source_clauses = [
            Clause(
                id="cl-1",
                title="Confidentiality",
                text="test clause text",
                level=1,
                parent_id=None,
                source_page=None,
                source_paragraph=None,
                source_span=None,
            ),
        ]

        sid = f"review:{uuid.uuid4()}"
        result = run_grounding(
            report=report,
            source_document=source_document,
            mode="strict",
            gateway=fake_gateway,
            session_id=sid,
            source_clauses=source_clauses,
        )

        assert len(captured_sessions) >= 1, "No gateway.chat calls made"
        assert all(s == sid for s in captured_sessions)


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline-level forwarding tests (5-9): real run_review with stubbed internals
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunReviewSessionForwarding:
    """run_review session ID minting and forwarding through the pipeline."""

    # ── helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _stub_pipeline_parse(monkeypatch: pytest.MonkeyPatch) -> None:
        """Replace ParseStage.run with a no-op that populates pipeline context."""
        from openreview_cli.parsing.models import Clause

        async def fake_parse_run(self_obj: object, ctx: dict[str, object]) -> dict[str, object]:
            clauses = [
                Clause(
                    id="cl-1",
                    title="Confidentiality",
                    text="The receiving party shall not disclose confidential information.",
                    level=1,
                    parent_id=None,
                    source_page=None,
                    source_paragraph=None,
                    source_span=None,
                ),
            ]
            ctx["clauses"] = clauses
            ctx["document"] = MagicMock()
            return {"clauses": clauses, "document": ctx["document"]}

        monkeypatch.setattr(
            "openreview_cli.pipeline.adapters.parse.ParseStage.run",
            fake_parse_run,
        )

    @staticmethod
    def _stub_call_gateway_chat(
        monkeypatch: pytest.MonkeyPatch,
        captured_sessions: list[str | None],
    ) -> None:
        """Monkeypatch call_gateway_chat at extraction + QA to capture session IDs."""

        def fake_call(slot: str, messages: list[dict[str, str]], **kwargs: object) -> str:
            captured_sessions.append(kwargs.get("session_id"))  # type: ignore[arg-type]
            return (
                '{"position": "preferred", "confidence": 0.9, '
                '"citation": "test", "category_match": true}'
            )

        monkeypatch.setattr(
            "openreview_cli.review.extraction.call_gateway_chat",
            fake_call,
        )
        monkeypatch.setattr(
            "openreview_cli.review.qa.call_gateway_chat",
            fake_call,
        )

    @staticmethod
    def _stub_gateway_chat(
        monkeypatch: pytest.MonkeyPatch,
        captured_sessions: list[str | None],
    ) -> None:
        """Monkeypatch Gateway.chat to capture grounding session IDs."""

        def fake_chat(
            self_obj: object,
            slot: str,
            messages: list[dict[str, str]],
            **kwargs: object,
        ) -> str:
            captured_sessions.append(kwargs.get("session_id"))  # type: ignore[arg-type]
            return (
                '{"verdict": "grounded", "provenance": [{"clause_id": "cl-1", '
                '"text": "test", "score": 0.95}], "score": 0.95}'
            )

        monkeypatch.setattr(
            "openreview_cli.gateway.router.Gateway.chat",
            fake_chat,
        )

    # ── tests ──────────────────────────────────────────────────────────

    def test_single_doc_uses_caller_session_id(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test 5: single doc — caller-provided session_id reaches call_gateway_chat."""
        self._stub_pipeline_parse(monkeypatch)
        captured_sessions: list[str | None] = []
        self._stub_call_gateway_chat(monkeypatch, captured_sessions)

        doc = tmp_path / "test.pdf"
        doc.write_text("dummy")

        from openreview_cli.review import run_review

        sid = f"review:{uuid.uuid4()}"
        run_review(
            paths=[str(doc)],
            session_id=sid,
            no_pii=True,
            verbose=False,
        )

        assert len(captured_sessions) >= 1, "No call_gateway_chat calls made"
        assert all(s == sid for s in captured_sessions)

    def test_two_docs_have_distinct_session_ids(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test 6: two docs — each gets a distinct minted review:uuid ID."""
        self._stub_pipeline_parse(monkeypatch)
        captured_sessions: list[str | None] = []
        self._stub_call_gateway_chat(monkeypatch, captured_sessions)

        doc1 = tmp_path / "doc1.pdf"
        doc2 = tmp_path / "doc2.pdf"
        doc1.write_text("dummy 1")
        doc2.write_text("dummy 2")

        from openreview_cli.review import run_review

        run_review(
            paths=[str(doc1), str(doc2)],
            session_id=None,
            no_pii=True,
            verbose=False,
        )

        unique_sessions = {s for s in captured_sessions if s is not None}
        assert len(unique_sessions) >= 2, f"Expected 2+ distinct session IDs, got {unique_sessions}"
        for found in unique_sessions:
            assert found.startswith("review:"), f"Session ID {found} lacks review: prefix"
            uuid.UUID(found[len("review:") :])  # raises ValueError if invalid

    def test_grounding_uses_same_session_as_extraction(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test 7: grounding within run_review uses same session_id as extraction."""
        self._stub_pipeline_parse(monkeypatch)
        captured_sessions: list[str | None] = []
        self._stub_call_gateway_chat(monkeypatch, captured_sessions)
        self._stub_gateway_chat(monkeypatch, captured_sessions)

        doc = tmp_path / "test.pdf"
        doc.write_text("dummy")

        from openreview_cli.review import run_review

        sid = f"review:{uuid.uuid4()}"
        run_review(
            paths=[str(doc)],
            session_id=sid,
            no_pii=True,
            verbose=False,
            grounding_mode="strict",
        )

        assert len(captured_sessions) >= 2, "Expected extraction + grounding calls"
        assert all(s == sid for s in captured_sessions)

    def test_minted_id_format(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test 8: without caller session_id, a new review:uuid ID is minted."""
        self._stub_pipeline_parse(monkeypatch)
        captured_sessions: list[str | None] = []
        self._stub_call_gateway_chat(monkeypatch, captured_sessions)

        doc = tmp_path / "test.pdf"
        doc.write_text("dummy")

        from openreview_cli.review import run_review

        run_review(
            paths=[str(doc)],
            session_id=None,
            no_pii=True,
            verbose=False,
        )

        assert len(captured_sessions) >= 1
        sid = captured_sessions[0]
        assert sid is not None
        assert sid.startswith("review:")
        uuid.UUID(sid[len("review:") :])  # raises ValueError if invalid

    def test_two_docs_with_caller_session_id_ignored(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test 9: two docs with caller session_id — each gets minted ID."""
        self._stub_pipeline_parse(monkeypatch)
        captured_sessions: list[str | None] = []
        self._stub_call_gateway_chat(monkeypatch, captured_sessions)

        doc1 = tmp_path / "doc1.pdf"
        doc2 = tmp_path / "doc2.pdf"
        doc1.write_text("dummy 1")
        doc2.write_text("dummy 2")

        from openreview_cli.review import run_review

        caller_sid = f"review:{uuid.uuid4()}"
        run_review(
            paths=[str(doc1), str(doc2)],
            session_id=caller_sid,
            no_pii=True,
            verbose=False,
        )

        assert caller_sid not in captured_sessions, (
            f"Caller session_id {caller_sid} should not be used for multi-doc"
        )
        unique_sessions = {s for s in captured_sessions if s is not None}
        assert len(unique_sessions) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# Cost-attribution tests (10-12): real SQLite db, stubbed pricing
# ═══════════════════════════════════════════════════════════════════════════════


class TestSessionCostAttribution:
    """Cost attribution for session IDs via real SQLite db."""

    @staticmethod
    def _stub_completion_cost(monkeypatch: pytest.MonkeyPatch) -> None:
        """Return fixed cost so we don't depend on litellm pricing tables."""
        monkeypatch.setattr(
            "openreview_cli.gateway.cost.completion_cost",
            lambda *a, **kw: 0.05,
        )

    def test_log_call_and_get_session_cost(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test 10: CostTracker.log_call writes rows queryable via get_session_cost."""
        self._stub_completion_cost(monkeypatch)
        from openreview_cli.gateway.cost import CostTracker
        from openreview_cli.storage.database import get_session_cost, init_database

        db_path = tmp_path / "costs.db"
        init_database(db_path)
        tracker = CostTracker(db_path)

        sid = f"review:{uuid.uuid4()}"
        tracker.log_call(sid, "extraction", "gpt-4", "openai", _MockResponse())

        cost_data = get_session_cost(db_path, sid)
        assert isinstance(cost_data, dict)
        # 0.05 USD = 5 cents → max(1, round(5)) = 5
        assert cost_data["cost_cents"] > 0, f"Expected nonzero cost for {sid}, got {cost_data}"

    def test_empty_session_returns_zero(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test 11: get_session_cost for unused session returns zero."""
        self._stub_completion_cost(monkeypatch)
        from openreview_cli.storage.database import get_session_cost, init_database

        db_path = tmp_path / "costs.db"
        init_database(db_path)

        cost_data = get_session_cost(db_path, "nonexistent-session")
        assert cost_data["cost_cents"] == 0

    def test_check_session_limit(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test 12: check_session_limit reflects logged rows under session ID."""
        self._stub_completion_cost(monkeypatch)
        from openreview_cli.gateway.cost import CostTracker
        from openreview_cli.storage.database import (
            check_session_limit,
            get_session_cost,
            init_database,
        )

        db_path = tmp_path / "costs.db"
        init_database(db_path)
        tracker = CostTracker(db_path)

        sid = f"review:{uuid.uuid4()}"

        # Before any calls, limit of 0 is exceeded (sum=0, 0 < 0 = False)
        assert not check_session_limit(db_path, sid, 0)

        # Log a call
        tracker.log_call(sid, "extraction", "gpt-4", "openai", _MockResponse())
        logged_cost = get_session_cost(db_path, sid)["cost_cents"]
        assert logged_cost > 0, "Logged call should have nonzero cost"

        # Very high limit: within limit
        assert check_session_limit(db_path, sid, 999999)

        # Limit of 0: not within limit
        assert not check_session_limit(db_path, sid, 0)

        # Limit exactly equal to cost: not within (strict <)
        assert not check_session_limit(db_path, sid, logged_cost)

        # Limit just above: within
        assert check_session_limit(db_path, sid, logged_cost + 1)
