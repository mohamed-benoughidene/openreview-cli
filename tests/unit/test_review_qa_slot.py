"""Spec 035 T1.6 — the checker (QA) has its own socket (plan T1.6).

Before this change the QA step silently borrowed the reader's slot
(``qa_model or extraction_model``). It now defaults to the ``reasoning`` slot,
so the checker is independently configurable.

What this pins, and what it deliberately does *not*: the shipped defaults point
all three sockets at the same model, so out-of-the-box behaviour is unchanged.
The tests below only assert the wiring — the QA call goes to ``reasoning`` and
the reader call goes to ``extraction``, and the two slots resolve their primary
models independently.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from openreview_cli.parsing.models import Clause
from openreview_cli.review.pipeline import ReviewStage

EXTRACTION_RESPONSE = json.dumps(
    {"position": "acceptable", "confidence": 0.8, "citation": "Clause 1"}
)
QA_RESPONSE = json.dumps(
    {
        "verdict": "agree",
        "revised_position": None,
        "rationale": "position matches the clause",
        "citation_valid": True,
        "position_valid": True,
        "category_valid": True,
        "confidence_valid": True,
    }
)


def _make_playbook() -> Any:
    from openreview_cli.review.models import (
        Category,
        Playbook,
        PlaybookMetadata,
        Position,
        PositionDef,
    )

    category = Category(
        id="test-cat",
        name="Test Category",
        description="test",
        preferred=PositionDef(description="best", exemplars=["ex a"]),
        acceptable=PositionDef(description="ok", exemplars=["ex b"]),
        walkaway=PositionDef(description="bad", exemplars=["ex c"]),
        default_position=Position.ACCEPTABLE,
    )
    return Playbook(
        id="qa-slot",
        mode="precheck",
        categories=[category],
        metadata=PlaybookMetadata(version="1.0.0", description="test", author="test"),
    )


def _recording_chat(recorded: list[str], response: str) -> Any:
    """Build a ``call_gateway_chat`` stand-in that records the slot it was given."""

    def _call(slot: str, *_args: Any, **_kwargs: Any) -> str:
        recorded.append(slot)
        return response

    return _call


def _run_one_clause(monkeypatch: pytest.MonkeyPatch, recorded: list[str]) -> None:
    playbook = _make_playbook()

    monkeypatch.setattr(
        "openreview_cli.review.extraction.match_category",
        lambda _text, _playbook, _pb=playbook: _pb.categories[0],
    )
    monkeypatch.setattr(
        "openreview_cli.review.extraction.call_gateway_chat",
        _recording_chat(recorded, EXTRACTION_RESPONSE),
    )
    monkeypatch.setattr(
        "openreview_cli.review.qa.call_gateway_chat",
        _recording_chat(recorded, QA_RESPONSE),
    )

    stage = ReviewStage(playbook=playbook)
    asyncio.run(
        stage.run(
            {
                "document": None,
                "clauses": [
                    Clause(
                        id="c1",
                        title=None,
                        text="The parties shall keep information confidential.",
                        level=1,
                        parent_id=None,
                        source_page=None,
                        source_paragraph=None,
                        source_span=None,
                    )
                ],
            }
        )
    )


def test_checker_calls_the_reasoning_slot_and_reader_calls_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reader verifies against a different socket than the one it extracts with."""
    recorded: list[str] = []
    _run_one_clause(monkeypatch, recorded)

    assert recorded == ["extraction", "reasoning"]


def test_reasoning_slot_resolves_independently_of_the_reader(tmp_path: Path) -> None:
    """Pointing ``reasoning`` at another model moves only the checker's model."""
    from openreview_cli.gateway.router import Gateway

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "gateway:\n"
        "  models:\n"
        "    extraction:\n"
        "      primary: ollama/reader:3b\n"
        "    reasoning:\n"
        "      primary: ollama/checker:1b\n"
    )

    gateway = Gateway(config_path=config_path, auth_path=tmp_path / "auth.json")

    # The checker's socket and the reader's socket resolve different models, and
    # the QA call above is routed through the former only.
    assert gateway.slot_primary_model("reasoning") == "ollama/checker:1b"
    assert gateway.slot_primary_model("extraction") == "ollama/reader:3b"


def test_run_review_defaults_qa_to_reasoning_and_reader_to_extraction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The ``review`` entry point resolves the same pair of slots."""
    from openreview_cli.review.runner import run_review

    document = tmp_path / "nda.docx"
    document.write_text("placeholder")

    captured: dict[str, str] = {}

    def _fake_doc_pipeline(**_kwargs: Any) -> tuple[Any, list[Any]]:
        captured.update(_kwargs)
        return object(), []

    monkeypatch.setattr("openreview_cli.review.runner.load_bundled", _make_playbook)
    monkeypatch.setattr("openreview_cli.review.runner._run_review_doc_pipeline", _fake_doc_pipeline)

    run_review(paths=[str(document)])

    assert captured["extraction_model"] == "extraction"
    assert captured["qa_model"] == "reasoning"


def test_run_comparison_defaults_qa_to_reasoning_and_reader_to_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ``compare`` entry point resolves the same pair of slots."""
    from openreview_cli.bilateral import run_comparison

    captured: list[str] = []

    def _fake_process(
        _path: str, _playbook: Any, _extraction_model: str, qa_model: str, **_kwargs: Any
    ) -> Any:
        captured.append(qa_model)
        raise RuntimeError("stop after the default has been resolved")

    monkeypatch.setattr("openreview_cli.bilateral._check_first_run", lambda: None)
    monkeypatch.setattr("openreview_cli.bilateral._process_document", _fake_process)

    with pytest.raises(RuntimeError):
        run_comparison(doc_a_path="a.docx", doc_b_path="b.docx", playbook=_make_playbook())

    assert captured == ["reasoning"]
