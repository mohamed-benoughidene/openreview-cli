"""Unit tests for the grounding-accuracy mode in ``scripts/measure_slm_slots.py``.

Three groups, all offline (no gateway, no network, no corpus dependency):

1. the confusion-matrix arithmetic on a hand-built verdict list, including the two
   degenerate cases the design pins (guard drained the negative arm; the grounding rejects
   every claim) and the per-call latency aggregation;
2. one end-to-end run over a tiny fixture corpus with the discriminator stubbed, proving the
   counting and the per-generator guard drops are reported;
3. the graceful-skip path when the corpus directory does not exist.

The metrics measured here are a real confusion matrix — bad claims caught, good claims
wrongly rejected, the uncertain columns and per-call latency. ``compute_cg_metrics`` is
deliberately NOT the signal (it is structural, covers only grounded verdicts, and returns
``1.0`` for everything when nothing is grounded — ``grounding/metrics.py:100-105``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from openreview_cli.grounding.models import GroundingVerdict
from tests.helpers.benchmark_scripts import load_benchmark_script

SCRIPT = load_benchmark_script("measure_slm_slots")

# A qualifying paragraph: >= 200 chars, >= 2 sentences, and a first *qualifying* sentence
# (the first sentence is a short heading, below the word/char bar).
PARA_A = (
    "4.1 Confidentiality Obligations. The receiving party shall not disclose any Confidential "
    "Information to any third party without the prior written consent of the disclosing party. "
    "This obligation survives termination of the agreement for a period of five years."
)
PARA_B = (
    "9.3 Payment Terms. The customer shall pay all undisputed invoices within thirty days of "
    "receipt of a valid invoice from the supplier. Late payments accrue interest at one "
    "percent per month until paid in full."
)

FABRICATED = "A wholly fabricated sentence that appears in no clause of this agreement at all."


def _entry(expected: str, verdict: str, seconds: float = 0.1) -> dict[str, Any]:
    """One labelled verdict row, the shape ``compute_grounding_matrix`` consumes."""
    return {"expected": expected, "verdict": verdict, "seconds": seconds}


class TestGroundingConfusionArithmetic:
    """§4.1/§4.2 of the harness design, on a hand-built matrix."""

    def test_counts_and_rates_are_exact(self) -> None:
        labels = [
            _entry("supported", "grounded"),
            _entry("supported", "grounded"),
            _entry("supported", "ungrounded"),
            _entry("supported", "uncertain"),
            _entry("unsupported", "ungrounded"),
            _entry("unsupported", "ungrounded"),
            _entry("unsupported", "grounded"),
        ]
        m = SCRIPT.compute_grounding_matrix(labels)
        assert m["positives"] == 4
        assert m["negatives_kept"] == 3
        assert m["good_accepted"] == 2
        assert m["good_rejected"] == 1
        assert m["good_uncertain"] == 1
        assert m["bad_caught"] == 2
        assert m["bad_missed"] == 1
        assert m["bad_uncertain"] == 0
        assert m["caught_rate"] == pytest.approx(2 / 3, abs=1e-4)
        assert m["false_reject_rate"] == pytest.approx(1 / 4, abs=1e-4)

    def test_guard_drained_negatives_scores_zero_caught_and_none_rate(self) -> None:
        # N == 0: there was nothing to catch, so the rate is None — never 1.0.
        labels = [
            _entry("supported", "grounded"),
            _entry("supported", "grounded"),
            _entry("supported", "ungrounded"),
        ]
        m = SCRIPT.compute_grounding_matrix(labels)
        assert m["negatives_kept"] == 0
        assert m["bad_caught"] == 0
        assert m["caught_rate"] is None
        assert m["caught_rate"] != 1.0
        # The positive arm is still scored, so a drained run is not silently "perfect".
        assert m["false_reject_rate"] == pytest.approx(1 / 3, abs=1e-4)

    def test_reject_everything_catches_all_but_shows_full_wrong_rejection(self) -> None:
        # Mirror control: a grounding that rejects every claim legitimately catches 100% of
        # negatives — false_reject_rate == 1.0 is what exposes it as a failure.
        P, N = 4, 3
        labels = [_entry("supported", "ungrounded") for _ in range(P)]
        labels += [_entry("unsupported", "ungrounded") for _ in range(N)]
        m = SCRIPT.compute_grounding_matrix(labels)
        assert m["bad_caught"] == N
        assert m["caught_rate"] == 1.0
        assert m["good_rejected"] == P
        assert m["false_reject_rate"] == 1.0

    def test_uncertain_is_its_own_column(self) -> None:
        labels = [
            _entry("supported", "uncertain"),
            _entry("unsupported", "uncertain"),
        ]
        m = SCRIPT.compute_grounding_matrix(labels)
        assert m["bad_caught"] == 0
        assert m["good_rejected"] == 0
        assert m["caught_rate"] == 0.0
        assert m["false_reject_rate"] == 0.0
        assert m["good_uncertain"] == 1
        assert m["bad_uncertain"] == 1

    def test_empty_arm_rates_are_none_not_one(self) -> None:
        m = SCRIPT.compute_grounding_matrix([])
        assert m["caught_rate"] is None
        assert m["false_reject_rate"] is None
        assert m["latency"]["calls"] == 0

    def test_latency_aggregation_over_a_known_list(self) -> None:
        labels = [
            _entry("supported", "grounded", 1.0),
            _entry("supported", "grounded", 2.0),
            _entry("supported", "grounded", 3.0),
            _entry("supported", "grounded", 4.0),
            _entry("supported", "grounded", 5.0),
        ]
        latency = SCRIPT.compute_grounding_matrix(labels)["latency"]
        assert latency["calls"] == 5
        assert latency["mean"] == pytest.approx(3.0)
        assert latency["median"] == pytest.approx(3.0)
        assert latency["p95"] == pytest.approx(5.0)
        assert latency["max"] == pytest.approx(5.0)


def _tiny_corpus(tmp_path: Path) -> Path:
    corpus = tmp_path / "cuad"
    corpus.mkdir()
    (corpus / "a.txt").write_text(PARA_A, encoding="utf-8")
    (corpus / "b.txt").write_text(PARA_B, encoding="utf-8")
    return corpus


class _StubDiscriminator:
    """Stands in for ``CitationGroundingDiscriminator``: rejects every claim."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def ground_claim(
        self, claim_text: str, cited_clause_id: str, clause_text: str
    ) -> tuple[GroundingVerdict, list[Any], float]:
        self.calls.append((claim_text, cited_clause_id, clause_text))
        return (GroundingVerdict.UNGROUNDED, [], 0.9)


class TestGroundingAccuracyEndToEnd:
    """End to end over a tiny fixture corpus, discriminator stubbed (offline)."""

    def test_counts_and_per_generator_drops_are_reported(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        corpus = _tiny_corpus(tmp_path)
        out = tmp_path / "ga.json"
        stub = _StubDiscriminator()

        monkeypatch.setattr(
            SCRIPT,
            "_configured_slots",
            lambda: {
                "extraction": "stub/reader",
                "reasoning": "stub/checker",
                "grounding": "stub/grounding",
            },
        )
        monkeypatch.setattr(SCRIPT, "_make_discriminator", lambda: stub)
        # Force every cross-clause negative to be the cited clause itself, so the guard
        # drops it; the hallucination override is genuinely unsupported and survives.
        monkeypatch.setattr(SCRIPT, "unsupported_claim", lambda a, b: a.text)
        monkeypatch.setattr(SCRIPT, "hallucination", lambda claim: FABRICATED)

        receipt = SCRIPT.run_grounding_accuracy(
            corpus_dir=corpus, limit=2, arm="configured", out=out, no_pii=True
        )

        assert receipt["skipped"] is False
        assert receipt["units"] == 2
        # --no-pii is recorded, not silently ignored: the receipt says raw text was sent.
        assert receipt["pii_stripped"] is False
        assert receipt["pii"]["no_pii"] is True
        assert receipt["pii"]["stripped"] is False
        assert receipt["positives"] == 2
        assert receipt["negatives_kept"] == 2  # hallucination only; cross-clause dropped
        assert receipt["negatives_dropped_guard"] == 2
        assert receipt["negatives_dropped_guard_by_generator"] == {
            "unsupported_claim": 2,
            "hallucination": 0,
        }
        # Reject-everything: all negatives caught and all positives wrongly rejected.
        assert receipt["bad_caught"] == 2
        assert receipt["caught_rate"] == 1.0
        assert receipt["good_rejected"] == 2
        assert receipt["false_reject_rate"] == 1.0
        assert receipt["model_ids"]["grounding"] == "stub/grounding"
        assert len(receipt["per_label"]) == 4
        assert len(stub.calls) == 4
        # Every negative row carries its generator; the zero-drop generator is recorded too.
        generators = {row["generator"] for row in receipt["per_label"]}
        assert generators == {"positive", "hallucination"}
        assert any("verbatim" in c for c in receipt["caveats"])

        # The same receipt is on disk, in one output format.
        assert json.loads(out.read_text())["negatives_dropped_guard"] == 2

    def test_cloud_arm_without_a_cloud_model_skips_cleanly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        corpus = _tiny_corpus(tmp_path)
        out = tmp_path / "ga.json"
        monkeypatch.setattr(
            SCRIPT,
            "_configured_slots",
            lambda: {"extraction": "ollama/x", "reasoning": "ollama/x", "grounding": "ollama/x"},
        )
        monkeypatch.setattr(SCRIPT, "_make_discriminator", _StubDiscriminator)

        receipt = SCRIPT.run_grounding_accuracy(corpus_dir=corpus, limit=2, arm="cloud", out=out)

        assert receipt["skipped"] is True
        assert "cloud" in receipt["skip_reason"]
        assert json.loads(out.read_text())["skipped"] is True
        assert "skipping" in capsys.readouterr().out


class TestGroundingAccuracyPiiStrip:
    """The grounding arm strips before any model call, using the review path's machinery.

    The strip and the tier flag are stubbed here so the test stays offline; what it proves
    is the wiring: clause text is stripped *before* it reaches ``ground_claim``, the gate is
    marked available, and the receipt records the strip (or the explicit opt-out).
    """

    def test_clause_text_reaching_the_model_is_stripped_and_gate_is_marked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import dataclasses

        import openreview_cli.pii as pii_pkg
        from openreview_cli.pii.models import PiiEntity, PiiResult

        corpus = _tiny_corpus(tmp_path)
        out = tmp_path / "ga.json"
        stub = _StubDiscriminator()
        marked = {"called": False}

        def fake_strip(clauses: list[Any], document: Any, **kwargs: Any) -> Any:
            stripped = [dataclasses.replace(c, text=c.text + " [PARTY_A]") for c in clauses]
            result = PiiResult(
                stripped_text=" ".join(c.text for c in stripped),
                mapping={"PARTY_A": "Acme Corp"},
                entities=[
                    PiiEntity(
                        entity_type="PERSON",
                        original_value="Jane Doe",
                        start=0,
                        end=8,
                        score=0.9,
                        placeholder="[PERSON_A]",
                        source="nlp",
                    ),
                    PiiEntity(
                        entity_type="ORG",
                        original_value="Acme Corp",
                        start=9,
                        end=18,
                        score=0.9,
                        placeholder="[ORG_A]",
                        source="nlp",
                    ),
                ],
                page_count=len(clauses) or 1,
                duration_seconds=0.0,
                warnings=[],
            )
            return stripped, result

        def fake_mark() -> None:
            marked["called"] = True

        monkeypatch.setattr(
            SCRIPT,
            "_configured_slots",
            lambda: {"extraction": "x", "reasoning": "x", "grounding": "stub/grounding"},
        )
        monkeypatch.setattr(SCRIPT, "_make_discriminator", lambda: stub)
        monkeypatch.setattr(SCRIPT, "hallucination", lambda claim: FABRICATED)
        monkeypatch.setattr(pii_pkg, "strip_pii_clauses", fake_strip)
        monkeypatch.setattr("openreview_cli.gateway.router.mark_pii_available", fake_mark)

        receipt = SCRIPT.run_grounding_accuracy(
            corpus_dir=corpus, limit=2, arm="configured", out=out
        )

        assert marked["called"] is True
        assert receipt["pii"]["stripped"] is True
        assert receipt["pii"]["no_pii"] is False
        assert receipt["pii"]["entities"] == 2
        assert receipt["pii_stripped"] is True
        # Every clause the model saw is the stripped text, not the raw corpus paragraph.
        assert stub.calls
        assert all(clause_text.endswith("[PARTY_A]") for _c, _i, clause_text in stub.calls)
        assert any(
            row["generator"] == "positive" and row["claim_text"] for row in receipt["per_label"]
        )


class TestGroundingAccuracyGracefulSkip:
    """The corpus is gitignored, so CI runs this path; it must never fail the build."""

    def test_missing_corpus_writes_a_skip_receipt_and_prints_one_line(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = tmp_path / "ga.json"
        missing = tmp_path / "does-not-exist"

        result = SCRIPT.main(
            [
                "--grounding-accuracy",
                "--corpus-dir",
                str(missing),
                "--limit",
                "3",
                "--arm",
                "configured",
                "--out",
                str(out),
            ]
        )

        assert result is None  # normal return == exit 0; no SystemExit
        captured = capsys.readouterr().out
        assert captured.count("[grounding-accuracy]") == 1
        assert "corpus absent" in captured
        assert "skipping" in captured

        receipt = json.loads(out.read_text())
        assert receipt["skipped"] is True
        assert receipt["corpus_dir"] == str(missing)
        assert receipt["arm"] == "configured"
        assert receipt["limit"] == 3

    def test_empty_corpus_dir_also_skips(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        empty = tmp_path / "empty-corpus"
        empty.mkdir()
        out = tmp_path / "ga.json"

        SCRIPT.main(["--grounding-accuracy", "--corpus-dir", str(empty), "--out", str(out)])

        assert json.loads(out.read_text())["skipped"] is True
        assert "corpus absent" in capsys.readouterr().out
