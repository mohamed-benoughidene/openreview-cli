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

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

from openreview_cli.grounding.corruption import ClauseUnit
from openreview_cli.grounding.models import GroundingVerdict
from tests.helpers.benchmark_scripts import load_benchmark_script

SCRIPT = load_benchmark_script("measure_slm_slots")


@pytest.fixture(autouse=True)
def _isolate_default_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the gateway's default database out of the developer's real data tree.

    ``run_grounding_accuracy`` creates the app database (``get_data_dir()/openreview.db``)
    before the pre-flight gateway call, so every test here must redirect platformdirs at a
    throwaway tree rather than writing into ``~/.local/share/openreview``.
    """
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))


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
PARA_C = (
    "12.2 Assignment. Neither party may assign this agreement, in whole or in part, without "
    "the prior written consent of the other party. Any purported assignment in violation of "
    "this section is void and of no effect, and the non-assigning party may terminate."
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


def _two_unit_document_corpus(tmp_path: Path) -> Path:
    """A corpus where ONE document holds TWO qualifying units.

    Every other fixture holds a single unit per document, so "pick another unit" and "pick
    another document" land on the same unit by accident: a picker that preferred the cited
    unit's own document had nothing to prefer and was never exercised. Here ``a.txt`` holds
    two units (c000, c001) and ``b.txt`` one (c002), so the two-unit document's units have a
    same-document sibling that a correct cross-document picker must skip.
    """
    corpus = tmp_path / "cuad"
    corpus.mkdir()
    (corpus / "a.txt").write_text(PARA_A + "\n\n" + PARA_B, encoding="utf-8")
    (corpus / "b.txt").write_text(PARA_C, encoding="utf-8")
    return corpus


class _StubDiscriminator:
    """Stands in for ``CitationGroundingDiscriminator``: rejects every claim."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.unreadable_answers = 0

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
        # The arm reachability pre-flight is a real gateway call; stub it as reachable so this
        # offline test exercises the measurement, not the network.
        monkeypatch.setattr(SCRIPT, "_preflight_arm_reachability", lambda: (True, None))
        # Force the *verbatim* cross-clause negative to be the cited clause itself, so the
        # guard drops it. The paraphrased cross-clause negative is a real rewrite of a
        # sentence from the other unit; it is genuinely unsupported and survives the guard.
        # The hallucination override is fabricated and survives too. ``operand_change`` is
        # disabled so the negative is drawn from the other unit (the cross-document branch).
        monkeypatch.setattr(SCRIPT, "operand_change", lambda _text: None)
        monkeypatch.setattr(SCRIPT, "unsupported_claim", lambda a, b: a.text)
        monkeypatch.setattr(SCRIPT, "hallucination", lambda claim: FABRICATED)

        receipt = SCRIPT.run_grounding_accuracy(
            corpus_dir=corpus, limit=2, arm="configured", out=out, no_pii=True
        )

        assert receipt["skipped"] is False
        assert receipt["all_uncertain"] is False
        assert receipt["unreadable_answers"] == 0
        assert receipt["units"] == 2
        # --no-pii is recorded, not silently ignored: the receipt says raw text was sent.
        assert receipt["pii_stripped"] is False
        assert receipt["pii"]["no_pii"] is True
        assert receipt["pii"]["stripped"] is False
        # Positives: the clause sentence and its rewrite, per unit -> 4.
        assert receipt["positives"] == 4
        # Negatives kept: the paraphrased cross-clause sentence and the fabrication, per unit.
        assert receipt["negatives_kept"] == 4
        # Only the verbatim cross-clause negative hits the guard (its claim is the clause).
        assert receipt["negatives_dropped_guard"] == 2
        assert receipt["negatives_dropped_guard_by_generator"] == {
            "unsupported_claim": 2,
            "hallucination": 0,
            "paraphrased_unsupported": 0,
        }
        assert receipt["paraphrases_skipped"] == 0
        # Reject-everything: all negatives caught and all positives wrongly rejected.
        assert receipt["bad_caught"] == 4
        assert receipt["caught_rate"] == 1.0
        assert receipt["good_rejected"] == 4
        assert receipt["false_reject_rate"] == 1.0
        assert receipt["model_ids"]["grounding"] == "stub/grounding"
        assert len(receipt["per_label"]) == 8
        assert len(stub.calls) == 8
        # Every negative row carries its generator; the zero-drop generator is recorded too.
        generators = {row["generator"] for row in receipt["per_label"]}
        assert generators == {
            "positive",
            "paraphrased_supported",
            "paraphrased_unsupported",
            "hallucination",
        }
        # The caveat no longer promises that every positive is a verbatim clause sentence.
        assert not any("Positives are verbatim" in c for c in receipt["caveats"])
        assert any("two classes" in c for c in receipt["caveats"])
        # ... and it names the map's under-representation of real paraphrases.
        assert any("under-represent" in c for c in receipt["caveats"])

        # The same receipt is on disk, in one output format.
        assert json.loads(out.read_text())["negatives_dropped_guard"] == 2

    def test_per_label_rows_carry_a_coverage_number(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each row records how much of its claim's wording is in the clause it cites.

        The harness computes the number with the product's own ``presence.measure`` (the
        harness may import the product, never the reverse). A verbatim clause sentence is
        fully covered (1.0); a claim planted from nowhere is far below it. This only records
        the number — no verdict, count or label changes.
        """
        corpus = _tiny_corpus(tmp_path)
        out = tmp_path / "ga.json"
        stub = _StubDiscriminator()

        monkeypatch.setattr(
            SCRIPT,
            "_configured_slots",
            lambda: {"extraction": "s", "reasoning": "s", "grounding": "stub/grounding"},
        )
        monkeypatch.setattr(SCRIPT, "_make_discriminator", lambda: stub)
        monkeypatch.setattr(SCRIPT, "_preflight_arm_reachability", lambda: (True, None))
        monkeypatch.setattr(SCRIPT, "unsupported_claim", lambda a, b: a.text)
        monkeypatch.setattr(SCRIPT, "hallucination", lambda claim: FABRICATED)

        receipt = SCRIPT.run_grounding_accuracy(
            corpus_dir=corpus, limit=2, arm="configured", out=out, no_pii=True
        )

        rows = receipt["per_label"]
        assert rows
        for row in rows:
            assert "coverage" in row
            assert isinstance(row["coverage"], float)
            assert 0.0 <= row["coverage"] <= 1.0

        # A verbatim positive is the clause's own sentence: every word is present.
        verbatim = [row for row in rows if row["generator"] == "positive"]
        assert verbatim
        assert all(row["coverage"] == pytest.approx(1.0) for row in verbatim)

        # A claim planted from nowhere (the fabrication) appears in no clause: well below 1.0.
        planted = [row for row in rows if row["generator"] == "hallucination"]
        assert planted
        assert all(row["coverage"] < 0.5 for row in planted)

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


class TestGroundingParaphraseLabels:
    """The label builder adds two paraphrase classes (plan T5 / design §2.4).

    Before this, a positive was a verbatim clause sentence and the cross-clause negative was a
    verbatim sentence from another clause, so the labels measured quoting. A meaning-preserving
    rewrite of each keeps the support relation intact while making the label about wording.
    """

    UNITS = [ClauseUnit(id="c000", text=PARA_A), ClauseUnit(id="c001", text=PARA_B)]

    def test_builds_both_paraphrase_classes(self) -> None:
        labels, drops, generated, skips = SCRIPT._build_grounding_labels(self.UNITS)

        supported = [row for row in labels if row["expected"] == "supported"]
        assert {row["generator"] for row in supported} == {"positive", "paraphrased_supported"}
        assert len(supported) == 4  # one of each positive class per unit
        assert any(
            row["generator"] == "paraphrased_unsupported" and row["expected"] == "unsupported"
            for row in labels
        )
        # The paraphrased negative joins the negative counters; no positive counter exists.
        # These assert the actual per-class counts, not just the key set: both dicts are
        # seeded with ``dict.fromkeys(GROUNDING_VALID_NEGATIVES)``, so comparing key sets (or
        # against that same tuple) is a tautology that passes even if a generator never runs.
        assert generated == {
            "unsupported_claim": 2,
            "hallucination": 2,
            "paraphrased_unsupported": 2,
        }
        assert drops == {
            "unsupported_claim": 0,
            "hallucination": 0,
            "paraphrased_unsupported": 0,
        }
        assert skips == 0

    def test_unchanged_rewrites_are_skipped_and_counted_not_labelled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Force every rewrite to a no-op: a label whose wording equals a label already present
        # is a duplicate, so it is skipped and counted rather than kept silently.
        monkeypatch.setattr(
            SCRIPT,
            "paraphrased_supported",
            lambda unit: SCRIPT.first_qualifying_sentence(unit.text),
        )
        # An identity paraphrase map makes every rewrite equal its source, so the rewritten
        # positive and the rewritten negative both duplicate a label already present.
        monkeypatch.setattr(SCRIPT, "paraphrase", lambda sentence: sentence)
        # Drive the cross-document branch: the operand-change construction is preferred, and
        # its sentences would otherwise rewrite under the identity map alone.
        monkeypatch.setattr(SCRIPT, "operand_change", lambda _text: None)

        labels, _drops, generated, skips = SCRIPT._build_grounding_labels(self.UNITS)

        assert skips == 4  # 2 units x (positive + negative) no-op rewrites
        assert not any(
            row["generator"] in {"paraphrased_supported", "paraphrased_unsupported"}
            for row in labels
        )
        assert generated["paraphrased_unsupported"] == 0

    def test_negation_guarded_no_op_is_counted_as_a_skip_not_a_label(self) -> None:
        # The meaning-safe map declines to rewrite a bare modal under a negated/quantified
        # subject, so the paraphrase writer returns the sentence unchanged. When that sentence
        # is the only candidate rewrite for its label, the harness counts a skip and keeps no
        # paraphrase label — it is not silently labelled as a harder duplicate.
        negated = ClauseUnit(
            id="c000",
            text=(
                "4.7 Non-disclosure. Neither party shall disclose Confidential Information to "
                "any third party. This obligation survives termination for five years."
            ),
        )
        other = ClauseUnit(
            id="c001",
            text=(
                "9.3 Payment Terms. The customer shall pay all undisputed invoices within thirty "
                "days of receipt. Late payments accrue interest until paid in full."
            ),
        )

        labels, _drops, _generated, skips = SCRIPT._build_grounding_labels([negated, other])

        # The negated unit's own sentence is a no-op rewrite -> skipped, never labelled ...
        assert not any(
            row["generator"] == "paraphrased_supported" and row["unit_id"] == "c000"
            for row in labels
        )
        # ... but the other unit's cross-clause negative is operanded (thirty -> ninety) and
        # its rewrite changes the wording, so the paraphrase label survives.
        assert any(
            row["generator"] == "paraphrased_unsupported" and row["unit_id"] == "c001"
            for row in labels
        )
        assert skips == 1


class TestGroundingNegativeKinds:
    """The cross-clause negative comes from a different document, and the operand change is
    preferred when the cited clause has an operand. Each row records its own kind."""

    def test_units_carry_their_source_document(self, tmp_path: Path) -> None:
        units, _ = SCRIPT._load_corpus_units(_tiny_corpus(tmp_path), limit=2)
        assert [u.document for u in units] == ["a.txt", "b.txt"]

    def test_cross_document_kind_names_a_different_document(self, tmp_path: Path) -> None:
        # Both fixture units are operanded, so drive the cross-document branch explicitly.
        units, _ = SCRIPT._load_corpus_units(_tiny_corpus(tmp_path), limit=2)
        with pytest.MonkeyPatch.context() as monkey:
            monkey.setattr(SCRIPT, "operand_change", lambda _text: None)
            labels, _drops, _generated, _skips = SCRIPT._build_grounding_labels(units)
        negatives = [row for row in labels if row["generator"] == "unsupported_claim"]
        cited_document = {"c000": "a.txt", "c001": "b.txt"}
        assert negatives
        assert all(row["kind"] == "cross_document" for row in negatives)
        assert all(row["source_document"] != cited_document[row["unit_id"]] for row in negatives)

    def test_a_two_unit_document_never_supplies_its_own_cross_document_negative(
        self, tmp_path: Path
    ) -> None:
        # The fixture (not the assertion style) is the point: with one unit per document,
        # "pick another unit" and "pick another document" coincide, so a picker preferring the
        # cited unit's own document would still pass. Here a.txt holds c000 AND c001, so the
        # picker must skip its same-document sibling and reach b.txt.
        units, _ = SCRIPT._load_corpus_units(_two_unit_document_corpus(tmp_path), limit=3)
        assert [(unit.id, unit.document) for unit in units] == [
            ("c000", "a.txt"),
            ("c001", "a.txt"),
            ("c002", "b.txt"),
        ]
        # Both a.txt units are operanded, so drive the cross-document branch explicitly.
        with pytest.MonkeyPatch.context() as monkey:
            monkey.setattr(SCRIPT, "operand_change", lambda _text: None)
            labels, _drops, _generated, _skips = SCRIPT._build_grounding_labels(units)

        negatives = [row for row in labels if row["generator"] == "unsupported_claim"]
        cited_document = {unit.id: unit.document for unit in units}
        # Every unit is scored, so a dropped negative cannot hide a same-document pick.
        assert {row["unit_id"] for row in negatives} == set(cited_document)
        assert all(row["kind"] == "cross_document" for row in negatives)
        assert all(row["source_document"] != cited_document[row["unit_id"]] for row in negatives)
        # The two-unit document's units draw from the *other* document, never from each other.
        assert [row["source_document"] for row in negatives] == ["b.txt", "b.txt", "a.txt"]

    def test_operand_change_is_preferred_and_recorded(self, tmp_path: Path) -> None:
        units, _ = SCRIPT._load_corpus_units(_tiny_corpus(tmp_path), limit=2)
        labels, _drops, _generated, _skips = SCRIPT._build_grounding_labels(units)
        # Both fixture units carry a mapped operand, so every cross-family negative row (the
        # ``unsupported_claim`` and its ``paraphrased_unsupported`` rewrite) records the
        # operand_change construction; no row falls back to cross_document. The
        # ``hallucination`` rows are a separate kind and are excluded by the generator filter.
        kinds = {
            row["kind"]
            for row in labels
            if row["generator"] in {"unsupported_claim", "paraphrased_unsupported"}
        }
        assert kinds == {"operand_change"}

    def test_a_clause_without_an_operand_still_gets_a_sound_negative(self) -> None:
        no_operand = ClauseUnit(
            id="c000",
            document="a.txt",
            text=(
                "4.9 Governing Law. The parties agree that this agreement is governed by the "
                "laws of the state named above. Nothing in this section survives termination."
            ),
        )
        other = ClauseUnit(
            id="c001",
            document="b.txt",
            text=(
                "9.3 Payment Terms. The customer shall pay all undisputed invoices within "
                "thirty days of receipt. Late payments accrue interest until paid in full."
            ),
        )
        labels, _drops, _generated, _skips = SCRIPT._build_grounding_labels([no_operand, other])
        neg = [row for row in labels if row["generator"] == "unsupported_claim"]
        assert neg and neg[0]["kind"] == "cross_document"
        assert neg[0]["source_document"] == "b.txt"


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
        monkeypatch.setattr(SCRIPT, "_preflight_arm_reachability", lambda: (True, None))
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
            row["generator"] == "positive" and row["claim_sha256"] for row in receipt["per_label"]
        )


class _RaisingDiscriminator:
    """Stands in for a per-call gateway failure: every ``ground_claim`` raises."""

    def __init__(self) -> None:
        self.unreadable_answers = 0

    def ground_claim(
        self, claim_text: str, cited_clause_id: str, clause_text: str
    ) -> tuple[GroundingVerdict, list[Any], float]:
        raise RuntimeError("kaboom")


class TestGroundingReceiptCarriesNoFindingText:
    """A per-finding row must not publish the finding's own text.

    The receipts are regenerated and committed, so the exposure is closed at the source: a
    row carries the sha256 of its claim (``claim_sha256``), and of a per-call error
    (``error_sha256``), instead of the raw claim or error text. The receipt stays able to
    identify a row, but it can no longer leak a clause sentence or a provider message.
    """

    def _receipt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stub: Any
    ) -> tuple[dict[str, Any], Path]:
        corpus = _tiny_corpus(tmp_path)
        out = tmp_path / "ga.json"
        monkeypatch.setattr(
            SCRIPT,
            "_configured_slots",
            lambda: {"extraction": "s", "reasoning": "s", "grounding": "stub/grounding"},
        )
        monkeypatch.setattr(SCRIPT, "_make_discriminator", lambda: stub)
        monkeypatch.setattr(SCRIPT, "_preflight_arm_reachability", lambda: (True, None))
        monkeypatch.setattr(SCRIPT, "operand_change", lambda _text: None)
        monkeypatch.setattr(SCRIPT, "unsupported_claim", lambda a, b: a.text)
        monkeypatch.setattr(SCRIPT, "hallucination", lambda claim: FABRICATED)
        receipt = SCRIPT.run_grounding_accuracy(
            corpus_dir=corpus, limit=2, arm="configured", out=out, no_pii=True
        )
        return receipt, out

    def test_rows_hash_the_claim_instead_of_writing_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        receipt, out = self._receipt(tmp_path, monkeypatch, _StubDiscriminator())

        rows = receipt["per_label"]
        assert rows
        # The raw finding-text key is gone everywhere.
        assert all("claim_text" not in row for row in rows)
        # A sha256 identifies each row instead of its text.
        assert all(re.fullmatch(r"[0-9a-f]{64}", row["claim_sha256"]) for row in rows)
        positive = next(
            row for row in rows if row["generator"] == "positive" and row["unit_id"] == "c000"
        )
        raw_positive = SCRIPT.first_qualifying_sentence(PARA_A)
        assert raw_positive
        assert positive["claim_sha256"] == hashlib.sha256(raw_positive.encode("utf-8")).hexdigest()
        # ... and the finding's own text never reaches the serialized receipt.
        assert raw_positive not in out.read_text()

    def test_a_per_call_error_is_hashed_not_written_raw(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        receipt, out = self._receipt(tmp_path, monkeypatch, _RaisingDiscriminator())

        rows = receipt["per_label"]
        assert rows
        assert all("error" not in row for row in rows)
        expected = hashlib.sha256(b"RuntimeError: kaboom").hexdigest()
        assert all(row["error_sha256"] == expected for row in rows)
        # The provider message is not in the receipt either.
        assert "kaboom" not in out.read_text()


class TestGroundingAccuracyGracefulSkip:
    """The CUAD corpus is gitignored, so when no corpus is present the mode must skip
    cleanly and never fail the build (CI now runs the mode for real on a deterministic
    corpus assembled from the repository's tracked fixtures, not this skip path)."""

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
        assert receipt["skip_kind"] == "corpus_absent"
        assert receipt["corpus_dir"] == str(missing)
        assert receipt["arm"] == "configured"
        assert receipt["limit"] == 3
        assert receipt["unreadable_answers"] == 0

    def test_empty_corpus_dir_also_skips(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        empty = tmp_path / "empty-corpus"
        empty.mkdir()
        out = tmp_path / "ga.json"

        SCRIPT.main(["--grounding-accuracy", "--corpus-dir", str(empty), "--out", str(out)])

        assert json.loads(out.read_text())["skipped"] is True
        assert "corpus absent" in capsys.readouterr().out


class _AlwaysUncertainDiscriminator:
    """Stands in for a broken arm: the gateway call fails and the verdict comes back uncertain.

    This mirrors what ``CitationGroundingDiscriminator.ground_claim`` actually does when the
    gateway raises (``grounding/discriminator.py``): it swallows the error and returns
    ``UNCERTAIN``. The harness must not read that as model caution.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.unreadable_answers = 0

    def ground_claim(
        self, claim_text: str, cited_clause_id: str, clause_text: str
    ) -> tuple[GroundingVerdict, list[Any], float]:
        self.calls.append((claim_text, cited_clause_id, clause_text))
        return (GroundingVerdict.UNCERTAIN, [], 0.0)


def _stub_reachable_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    """The offline scaffolding shared by the pre-flight tests: slots + a passing check."""
    monkeypatch.setattr(
        SCRIPT,
        "_configured_slots",
        lambda: {"extraction": "x", "reasoning": "x", "grounding": "stub/grounding"},
    )
    # Disable the preferred operand-change construction so the cross-document branch (the
    # patched verbatim negative below) is the one exercised, keeping the label counts stable.
    monkeypatch.setattr(SCRIPT, "operand_change", lambda _text: None)
    monkeypatch.setattr(SCRIPT, "unsupported_claim", lambda a, b: a.text)
    monkeypatch.setattr(SCRIPT, "hallucination", lambda claim: FABRICATED)


class TestGroundingArmPreflight:
    """Guard 1: an arm that cannot be reached aborts before the matrix, with a distinct receipt.

    The failure is *observable live*: no local server gives ``Connection refused``, a cloud
    key at its spend limit gives ``403 Key limit exceeded``. Either way the discriminator
    would have returned ``uncertain`` for every claim, so the harness must refuse to measure.
    """

    def test_unreachable_arm_aborts_with_error_receipt_and_no_matrix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        corpus = _tiny_corpus(tmp_path)
        out = tmp_path / "ga.json"
        _stub_reachable_slots(monkeypatch)
        built = {"discriminator": False}

        monkeypatch.setattr(
            SCRIPT,
            "_preflight_arm_reachability",
            lambda: (False, "ConnectionError: Connection refused"),
        )

        def _record_build() -> _StubDiscriminator:
            built["discriminator"] = True
            return _StubDiscriminator()

        monkeypatch.setattr(SCRIPT, "_make_discriminator", _record_build)

        with pytest.raises(SystemExit) as excinfo:
            SCRIPT.main(
                [
                    "--grounding-accuracy",
                    "--corpus-dir",
                    str(corpus),
                    "--limit",
                    "2",
                    "--arm",
                    "configured",
                    "--no-pii",
                    "--out",
                    str(out),
                ]
            )

        # A measurement that could not run is not a measurement: non-zero exit, no matrix.
        assert excinfo.value.code == 1
        assert built["discriminator"] is False  # never even built; no call was attempted

        receipt = json.loads(out.read_text())
        assert receipt["skipped"] is True
        assert receipt["skip_kind"] == "arm_unreachable"
        assert "arm 'configured' unreachable" in receipt["skip_reason"]
        assert "Connection refused" in receipt["skip_reason"]
        assert receipt["preflight"]["ok"] is False
        assert receipt["preflight"]["arm"] == "configured"
        assert receipt["preflight"]["error"] == "ConnectionError: Connection refused"
        assert receipt["per_label"] == []
        assert receipt["positives"] == 0

        captured = capsys.readouterr().out
        assert "arm 'configured' unreachable" in captured
        assert "Connection refused" in captured

    def test_reachable_arm_proceeds_and_says_so(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        corpus = _tiny_corpus(tmp_path)
        out = tmp_path / "ga.json"
        stub = _StubDiscriminator()
        _stub_reachable_slots(monkeypatch)
        monkeypatch.setattr(SCRIPT, "_preflight_arm_reachability", lambda: (True, None))
        monkeypatch.setattr(SCRIPT, "_make_discriminator", lambda: stub)

        receipt = SCRIPT.run_grounding_accuracy(
            corpus_dir=corpus, limit=2, arm="configured", out=out, no_pii=True
        )

        assert receipt["skipped"] is False
        assert receipt["all_uncertain"] is False
        assert len(receipt["per_label"]) == 8
        assert len(stub.calls) == 8
        assert json.loads(out.read_text())["skipped"] is False
        assert "pre-flight OK" in capsys.readouterr().out

    def test_all_uncertain_run_is_flagged_in_print_and_receipt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        corpus = _tiny_corpus(tmp_path)
        out = tmp_path / "ga.json"
        stub = _AlwaysUncertainDiscriminator()
        _stub_reachable_slots(monkeypatch)
        monkeypatch.setattr(SCRIPT, "_preflight_arm_reachability", lambda: (True, None))
        monkeypatch.setattr(SCRIPT, "_make_discriminator", lambda: stub)

        receipt = SCRIPT.run_grounding_accuracy(
            corpus_dir=corpus, limit=2, arm="configured", out=out, no_pii=True
        )

        # An all-uncertain run is a broken-arm smell, not a cautious model.
        assert receipt["skipped"] is False
        assert receipt["all_uncertain"] is True
        assert receipt["caught_rate"] == 0.0
        assert receipt["good_uncertain"] == receipt["positives"]
        assert "arm" in receipt["all_uncertain_note"].lower()
        assert json.loads(out.read_text())["all_uncertain"] is True

        captured = capsys.readouterr().out
        assert "WARNING" in captured
        assert "uncertain" in captured.lower()


class TestGroundingInitialisesCostLedgerBeforePreflight:
    """The gateway reads its cost ledger (``cost_logs``) *before* it dispatches a call, so
    the grounding path must have created the app database before the pre-flight gateway
    call. A fresh CI checkout has no database file, and the pre-flight used to die with
    ``sqlite3.OperationalError: no such table: cost_logs`` before any model was reached
    (the ``grounding-accuracy`` CI job failure). All offline: no model, no network.
    """

    def test_database_is_initialised_before_the_preflight_call(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        corpus = _tiny_corpus(tmp_path)
        out = tmp_path / "ga.json"
        order: list[str] = []
        _stub_reachable_slots(monkeypatch)

        monkeypatch.setattr(SCRIPT, "_ensure_cost_ledger_database", lambda: order.append("ledger"))

        def _preflight() -> tuple[bool, str | None]:
            order.append("preflight")
            return False, "ConnectionError: Connection refused"

        monkeypatch.setattr(SCRIPT, "_preflight_arm_reachability", _preflight)

        with pytest.raises(SystemExit):
            SCRIPT.run_grounding_accuracy(
                corpus_dir=corpus, limit=2, arm="configured", out=out, no_pii=True
            )

        # The ledger is created before the pre-flight gateway call — not after it (which was
        # the bug: the only init happened inside the discriminator build, past the pre-flight).
        assert order[:2] == ["ledger", "preflight"]

    def test_initialiser_creates_the_cost_ledger_table_at_the_gateway_default_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A fresh checkout: the default data dir holds no database at all.
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "fresh-data"))

        from openreview_cli.config.paths import get_data_dir
        from openreview_cli.storage.costs import check_daily_limit

        # This is the path the Gateway resolves for its cost ledger by default
        # (``gateway/router.py``: ``get_data_dir() / "openreview.db"``).
        db_path = get_data_dir() / "openreview.db"
        assert not db_path.exists()

        SCRIPT._ensure_cost_ledger_database()

        assert db_path.exists()
        # The gateway's own pre-dispatch check now succeeds instead of raising
        # ``no such table: cost_logs`` (empty ledger is within every limit).
        assert check_daily_limit(db_path, max_cents=10_000) is True
