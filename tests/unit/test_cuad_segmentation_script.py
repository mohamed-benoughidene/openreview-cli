"""Unit tests for ``scripts/benchmark_cuad_segmentation.py``.

The script's public helpers (``load_document_text``, ``segment``,
``containing_clause``, ``evaluate``, ``parse_args``) are exercised against a
tiny synthetic corpus so the real 84-second CUAD run never executes. Doc
segmentation is stubbed out, keeping this a fast, offline unit test.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

import pytest

from openreview_cli.benchmark.metrics import extraction_f1
from openreview_cli.parsing.models import Clause
from tests.helpers.benchmark_scripts import load_benchmark_script

SCRIPT = load_benchmark_script("benchmark_cuad_segmentation")

DOC_A_TEXT = "Alpha beta gamma. Delta epsilon zeta."
_A_SPAN = (0, 17)  # "Alpha beta gamma."
_B_SPAN = (18, len(DOC_A_TEXT))  # "Delta epsilon zeta."

_RESULT_KEYS = frozenset(
    {
        "benchmark",
        "corpus",
        "corpus_sha256",
        "documents_loaded",
        "spans_evaluated",
        "spans_contained",
        "containment_rate",
        "token_f1_mean",
        "tests_with_span",
        "tests_any_span_contained",
        "test_coverage_rate",
        "missing_snippets",
        "unreadable_file_paths",
        "elapsed_seconds",
    }
)


def _clause(span: tuple[int, int], text: str) -> Clause:
    """Build a minimal ``Clause`` carrying ``span`` and ``text``."""
    return Clause(
        id=f"clause-{span[0]}-{span[1]}",
        title=None,
        text=text,
        level=0,
        parent_id=None,
        source_page=None,
        source_paragraph=None,
        source_span=span,
    )


def _fake_segment_for_corpus(text: str) -> list[Clause]:
    """Return a deterministic flat partition without invoking nupunkt."""
    assert text == DOC_A_TEXT, f"unexpected document text: {text!r}"
    return [
        _clause(_A_SPAN, DOC_A_TEXT[_A_SPAN[0] : _A_SPAN[1]]),
        _clause(_B_SPAN, DOC_A_TEXT[_B_SPAN[0] : _B_SPAN[1]]),
    ]


def _write_tiny_corpus(corpus_path: Path, corpus_root: Path) -> None:
    """Write a 2-test corpus referencing doc_a.txt plus one missing file."""
    corpus_root.mkdir(parents=True, exist_ok=True)
    (corpus_root / "doc_a.txt").write_text(DOC_A_TEXT, encoding="utf-8")
    payload = {
        "tests": [
            {"snippets": [{"file_path": "doc_a.txt", "span": [0, 10]}]},
            {
                "snippets": [
                    {"file_path": "doc_a.txt", "span": [10, 24]},
                    {"file_path": "missing.txt", "span": [0, 1]},
                ]
            },
        ]
    }
    corpus_path.write_text(json.dumps(payload), encoding="utf-8")


# ── load_document_text ──────────────────────────────────────────────────────


def test_load_document_text_reads_literal_path(tmp_path: Path) -> None:
    (tmp_path / "doc.txt").write_text("hello world", encoding="utf-8")
    assert SCRIPT.load_document_text(tmp_path, "doc.txt") == "hello world"


def test_load_document_text_resolves_nfd_path_to_nfc_file(tmp_path: Path) -> None:
    nfc_name = unicodedata.normalize("NFC", "Leclanch\u00e9.txt")
    (tmp_path / nfc_name).write_text("accented content", encoding="utf-8")
    nfd_ref = unicodedata.normalize("NFD", nfc_name)
    assert nfd_ref != nfc_name
    assert SCRIPT.load_document_text(tmp_path, nfd_ref) == "accented content"


def test_load_document_text_returns_none_for_missing_path(tmp_path: Path) -> None:
    assert SCRIPT.load_document_text(tmp_path, "does_not_exist.txt") is None


# ── containing_clause ───────────────────────────────────────────────────────


def test_containing_clause_returns_none_when_no_clause_contains_span() -> None:
    clauses = [_clause((0, 100), "outer")]
    assert SCRIPT.containing_clause(clauses, 10, 200) is None


def test_containing_clause_boundary_exact_containment() -> None:
    clause = _clause((10, 20), "exact")
    assert SCRIPT.containing_clause([clause], 10, 20) is clause
    # One past the end is no longer contained.
    assert SCRIPT.containing_clause([clause], 10, 21) is None


def test_containing_clause_ignores_clauses_without_a_span() -> None:
    spanless = Clause(
        id="c",
        title=None,
        text="no span",
        level=0,
        parent_id=None,
        source_page=1,
        source_paragraph=None,
        source_span=None,
    )
    assert SCRIPT.containing_clause([spanless], 0, 1) is None


# ── segment ─────────────────────────────────────────────────────────────────


def test_segment_delegates_to_clause_detector(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel_clauses = [_clause((0, 11), "Hello world")]
    calls: dict[str, Any] = {}

    def fake_boundaries(text: str) -> list[Any]:
        calls["boundaries"] = text
        return ["boundary"]

    def fake_starts(text: str) -> list[tuple[int, dict[str, Any]]]:
        calls["starts"] = text
        return [(0, {})]

    def fake_build(*args: Any) -> list[Clause]:
        calls["build"] = args
        return sentinel_clauses

    monkeypatch.setattr(SCRIPT, "nupunkt_detect_boundaries", fake_boundaries)
    monkeypatch.setattr(SCRIPT, "detect_clause_starts", fake_starts)
    monkeypatch.setattr(SCRIPT, "build_hierarchy", fake_build)

    assert SCRIPT.segment("Hello world.") == sentinel_clauses
    assert calls["boundaries"] == "Hello world."
    assert calls["starts"] == "Hello world."
    assert calls["build"] == (["boundary"], [(0, {})], [], 1, 0, "Hello world.")


# ── evaluate ────────────────────────────────────────────────────────────────


def test_evaluate_scores_a_tiny_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    corpus_root = tmp_path / "corpus"
    corpus_path = tmp_path / "cuad.json"
    _write_tiny_corpus(corpus_path, corpus_root)
    monkeypatch.setattr(SCRIPT, "segment", _fake_segment_for_corpus)

    result = SCRIPT.evaluate(corpus_path, corpus_root, "tiny-subset", "cuad-segmentation")

    assert set(result) == _RESULT_KEYS
    assert result["benchmark"] == "cuad-segmentation"
    assert result["corpus"] == "tiny-subset"
    assert result["documents_loaded"] == 1

    # Two evaluated spans (the missing snippet is excluded); only the first
    # falls fully inside a detected clause.
    assert result["spans_evaluated"] == 2
    assert result["spans_contained"] == 1
    assert result["containment_rate"] == pytest.approx(
        result["spans_contained"] / result["spans_evaluated"]
    )

    expected_f1 = extraction_f1([_A_SPAN], [(0, 10)], DOC_A_TEXT).value
    assert result["token_f1_mean"] == pytest.approx(expected_f1 / result["spans_evaluated"])

    assert result["tests_with_span"] == 2
    assert result["tests_any_span_contained"] == 1
    assert result["test_coverage_rate"] == pytest.approx(1 / 2)
    assert result["missing_snippets"] == 1
    assert result["unreadable_file_paths"] == ["missing.txt"]


# ── parse_args ──────────────────────────────────────────────────────────────


def test_parse_args_defaults() -> None:
    args = SCRIPT.parse_args([])
    assert args.corpus == SCRIPT.DEFAULT_CORPUS
    assert args.corpus_root == SCRIPT.DEFAULT_CORPUS_ROOT
    assert args.output == SCRIPT.DEFAULT_OUTPUT
