# Grounding Recall Implementation Plan

> **For agentic workers:** Use tasks as checkboxes (`- [ ]`) for tracking.

**Goal:** Raise the fact-checker's catch rate by giving the test tool the product's question, making its bad sentences genuinely bad, widening the clause window to a sentence-aware ~2000 characters, showing sibling clauses with a fourth "real but wrongly cited" answer, asking a second narrow question and accepting only when both passes agree (off by default until measured), keeping confidence a warning and never a decision, and printing the risky patterns in the memo.

**Architecture:** The hint is computed once from `grounding/presence.py` and reaches both entry points. `grounding/corruption.py` gains one sound negative generator (operand change) and the harness draws its cross-clause negative from a *different document*. `grounding/prompts.py` windows each clause to whole sentences inside ~2000 characters, caps how many clauses it shows, and shares one claim-line formatter and one JSON-only instruction tail between the two passes. `grounding/discriminator.py` can run a second gateway call per batch behind a flag that defaults **off**; when it runs, the two answers combine and the guard records `miscited_to_clause_id` (guarded by the presence primitive, never re-judging the verdict) plus `pass_disagreement`/`not_sure`. The memo prints the risky-pattern lines in both modes.

**Tech stack:** Python 3.12, pytest, `uv`, standard library only. No new dependency.

**Design:** `docs/specs/plans/2026-10-01-grounding-recall-design.md`. §1 items 1–8 are the requirement; §3 is how the change is measured.

## Facts the plan relies on (verified in this worktree)

1. `ground_claim` is `grounding/discriminator.py:69-128`; its message call is `:103-106` (no hint). The batch path computes the hint once: `_process_batch` `:236`, `wording_absent_indices` `:264`, passed at `:268`, `_measure_presence` `:358`, `_get_clauses_for_batch` `:380`. `_BATCH_SIZE = 10` (`:33`). `ground_claim` already has `claim_text`/`clause_text` and builds its own `Clause`, so the hint needs no signature change.
2. `presence.measure(claim, clause) -> tuple[float, bool]` (`grounding/presence.py:70`) is the single primitive: `wording_absent` is `coverage < 0.5`, `False` when the clause has no tokens, the claim is a bare reference (`v?\d+(\.\d+)*`) or the claim has fewer than five tokens (`_MIN_CLAIM_TOKENS = 5`). Measured against the Task-5 fixture claim: the old sibling scored `(0.25, True)` (guard rejects), the reassigned sibling `(1.0, False)`, the unrelated sibling `(0.083, True)`.
3. `prompts.py`: the 500-character cut is `:74` (`text = clause.text[:500]`); claims are cut at 300; `_WORDING_ABSENT_HINT` is `:48`; `build_grounding_messages` is `:54`; `parse_grounding_response` is `:98`. Two tests pin the template tail (`tests/unit/test_grounding_prompts.py` `NEW_TAIL`), so the template text must be preserved.
4. `GroundingVerdict` has exactly three members. `GroundingResult` is `grounding/models.py:36-46`; `CGReport.merge_into` is `:80` and copies verdict/provenances/confidence/presence/wording at `:102-114`; strict mode keeps **only** `GROUNDED`. `ClauseAssessment` grounding fields are `review/models.py:115-120`; `from_dict` rebuilds the enum at `:267-268`; `ReviewReport` is `:176-189`.
5. The harness calls the single-finding entry point (`scripts/measure_slm_slots.py:749`), one row per label (`:757-769`); the confusion matrix is `compute_grounding_matrix` (`:201`). `corruption.py`: the sound grounding negative is `unsupported_claim(clause_a, clause_b)` (a verbatim sentence of another clause; `:175`); `hallucination` returns one of ten **fixed fabrications** and substitutes no operand (`:342`); `first_qualifying_sentence` is `:129`; `GROUNDING_VALID_NEGATIVES` is pinned by `test_grounding_corruption.py::TestDocumentedScope`. Receipts pin the five files this plan edits (`test_benchmark_receipts.py`).
6. The memo clause object is `MemoClause` (`review/memo/models.py:49-66`) — it carries `grounding_presence` and `accepted_despite_absent_wording` but **not the verdict**; the builder sets them at `review/memo/exporter.py:114-123`; one renderer helper `_wording_note` (`review/memo/formats.py:61`) serves Markdown and DOCX. `assign_colors` (`review/colors.py:57`) is not touched.

**Design overrides recorded here (this plan is the authority where they differ):**
- §1 item 2 says operand change is "the pattern `hallucination` already uses". `hallucination` returns ten fixed fabrications and maps **no** operand: operand change is new code (Task 3).
- §1 item 3 says the guard treats a hallucinated re-citation "as `ungrounded`". **Overridden (FIX 1):** the guard changes only `miscited_to_clause_id`; the verdict is never re-judged (Task 5).
- §1 item 4's rule is **gated off by default** so the product changes only once §3's measurement supports it (Task 6).
- §1 item 6's "three cases" is restructured to hold in both grounding modes (Task 8).
- §1 item 2's "adjacent clause": `unsupported_claim` takes whatever `clause_b` it is handed; adjacency is chosen in the harness (Task 3).

## Global Constraints

- **Worktree:** `/home/mohamed/lab/openreview/.worktrees/grounding-recall`, branch `feat/grounding-recall`, based on `feat/slm-measurement` at `147b98b`. Never commit to `main`.
- **`uv` and Python 3.12 only.** No `pip`/`poetry`, no new dependency.
- **TDD:** write the failing test first and *watch it fail* with the named message before writing implementation code.
- **Privacy:** no finding text and no clause text in a receipt, log, audit entry or metric.
- **No verdict is derived from the confidence number** (item 5). `grounding_confidence` is stored and shown; there is no threshold and no confidence warning field anywhere.
- **No chain-of-thought instruction anywhere** (item 8).
- **The 500-character cut becomes a sentence-aware window of about 2000 characters** (item 7): one constant, `_CLAUSE_WINDOW_CHARS = 2000`.
- **The fourth answer is a field, never a new verdict enum member.** `GroundingVerdict` keeps exactly `GROUNDED`/`UNGROUNDED`/`UNCERTAIN`; the guard **never downgrades** a verdict (FIX 1).
- **The agreement rule is off by default** (`require_pass_agreement=False`); the product changes only when the measurement supports it (design §3).
- **Never change the colour logic** (`review/colors.py`, `assign_colors`, the amber reasons) **or the strict/lenient filtering** (strict keeps only `GROUNDED`).
- **`uv run pre-commit run --all-files` must pass** before each commit.
- **Commit trailers:** every commit message ends with `Co-authored-by: CommandCodeBot <noreply@commandcode.ai>`.
- **All tests offline** with a mocked gateway (`--disable-socket` is in `addopts`); no `memory`-marked test.

---

### Task 1: The new grounding fields exist once, with no behaviour change (FIX 6)

**Files:** Modify `src/openreview_cli/grounding/models.py` (`GroundingResult` `:36-46`; `merge_into` `:102-114`), `src/openreview_cli/review/models.py` (`ClauseAssessment` `:120`; `ReviewReport` `:176-189`, `from_dict` `:287-292`). Test: `tests/unit/test_grounding_models.py`.

**Interfaces:** Produces `GroundingResult.miscited_to_clause_id: str | None = None`, `.pass_disagreement: bool = False`, `.not_sure: bool = False`; the same three on `ClauseAssessment`; `ReviewReport.grounding_excluded_unsupported: int = 0`, `.grounding_excluded_unsure: int = 0`, set by `merge_into`. Every later task only *sets* these values.

- [ ] **Step 1: Write the failing test.** Add to `tests/unit/test_grounding_models.py` (module already imports `CGMetrics, CGReport, GroundingResult, GroundingVerdict`; add `from datetime import datetime` and the `openreview_cli.review.models` names used below):
```python
class TestNewGroundingFields:
    """FIX 6: the three fields and the memo counts land in ONE migration."""

    def _report_and_cg(self, mode, verdict, **result_fields):
        review = ReviewReport(
            document=DocMeta(filename="test.pdf", page_count=1, clause_count=1, pii_stripped=False),
            assessments=[ClauseAssessment(
                clause_id="4.3", clause_text="Test clause", playbook_category="confidentiality",
                position=Position.PREFERRED, confidence=0.9, citation="4.3",
                qa_verdict=QAVerdict.agree, extraction_model="test", qa_model="test")],
            summary=ReviewSummary(), playbook_id="test", generated_at=datetime.now())
        cg = CGReport(
            verdicts=[GroundingResult(claim_index=0, verdict=verdict, provenances=[], **result_fields)],
            mode=mode,
            metrics=CGMetrics(citation_precision=1.0, citation_relevance=1.0, citation_locality=1.0),
            total_claims=1, grounded_count=1 if verdict is GroundingVerdict.GROUNDED else 0,
            ungrounded_count=1 if verdict is GroundingVerdict.UNGROUNDED else 0,
            uncertain_count=1 if verdict is GroundingVerdict.UNCERTAIN else 0)
        return review, cg

    def test_defaults_keep_every_existing_construction_working(self) -> None:
        result = GroundingResult(claim_index=0, verdict=GroundingVerdict.GROUNDED, provenances=[])
        assert (result.miscited_to_clause_id, result.pass_disagreement, result.not_sure) == (
            None, False, False)

    def test_merge_copies_the_three_new_fields(self) -> None:
        review, cg = self._report_and_cg("lenient", GroundingVerdict.GROUNDED,
                                         miscited_to_clause_id="4.7", pass_disagreement=True,
                                         not_sure=True)
        cg.merge_into(review)
        merged = review.assessments[0]
        assert (merged.miscited_to_clause_id, merged.pass_disagreement, merged.not_sure) == (
            "4.7", True, True)

    def test_strict_merge_records_the_exclusion_counts_for_the_memo(self) -> None:
        review, cg = self._report_and_cg("strict", GroundingVerdict.UNGROUNDED)
        cg.merge_into(review)
        assert review.assessments == []
        assert (review.grounding_excluded_unsupported, review.grounding_excluded_unsure) == (1, 0)
```
- [ ] **Step 2: Run it to watch it fail.** Run `uv run pytest tests/unit/test_grounding_models.py::TestNewGroundingFields -q` — Expected: `TypeError: GroundingResult.__init__() got an unexpected keyword argument 'miscited_to_clause_id'`.
- [ ] **Step 3: Implement (the one migration).** In `grounding/models.py`, add to `GroundingResult` after `wording_absent`:
```python
    miscited_to_clause_id: str | None = None  # the fourth answer; never changes ``verdict``
    pass_disagreement: bool = False           # the two passes split GROUNDED/UNGROUNDED
    not_sure: bool = False                    # the final verdict is UNCERTAIN
```
In `merge_into`, beside the existing copies (`:102-106`):
```python
            assessment.miscited_to_clause_id = result.miscited_to_clause_id
            assessment.pass_disagreement = result.pass_disagreement
            assessment.not_sure = result.not_sure
```
In the strict branch of `merge_into`, record what strict removed (Task 8 reads it):
```python
        if self.mode == "strict":
            report.grounding_excluded_unsupported = self.ungrounded_count
            report.grounding_excluded_unsure = self.uncertain_count
```
In `review/models.py`, add the same three to `ClauseAssessment` after `wording_absent` (`:120`), the two counts to `ReviewReport` after `mode` (`:189`), and read them in `from_dict` (`:287-292`):
```python
    miscited_to_clause_id: str | None = None
    pass_disagreement: bool = False
    not_sure: bool = False
    grounding_excluded_unsupported: int = 0
    grounding_excluded_unsure: int = 0
```
```python
            grounding_excluded_unsupported=int(data.get("grounding_excluded_unsupported", 0)),
            grounding_excluded_unsure=int(data.get("grounding_excluded_unsure", 0)),
```
- [ ] **Step 4: Run to verify.** Run `uv run pytest tests/unit/test_grounding_models.py tests/unit/test_grounding_discriminator.py tests/unit/test_three_color_models.py -q` — Expected: all pass.
- [ ] **Step 5: Commit.**
```bash
git add src/openreview_cli/grounding/models.py src/openreview_cli/review/models.py tests/unit/test_grounding_models.py
git commit -m "feat(grounding): add the fourth-answer and two-pass fields in one migration

Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```
**Deliberate wrong implementation to catch:** deriving a fourth `GroundingVerdict` member instead of a field (strict mode would delete it).

---

### Task 2: The single-finding entry point asks the product's question (item 1)

**Files:** Modify `src/openreview_cli/grounding/discriminator.py` (`ground_claim` `:103-106`). Test: `tests/unit/test_grounding_discriminator.py`.

**Interfaces:** Consumes `presence.measure(claim_text, clause_text) -> tuple[float, bool]` (`presence.py:70`) and `build_grounding_messages(source_clauses, claims, wording_absent_indices: set[int] | None = None)` (`prompts.py:54`). Produces nothing new; `ground_claim(claim_text, cited_clause_id, clause_text)` keeps its signature.

- [ ] **Step 1: Write the failing test.** Append to `tests/unit/test_grounding_discriminator.py` (`CitationGroundingDiscriminator`, `GroundingVerdict`, `json` already imported):
```python
class TestGroundClaimAsksTheProductQuestion:
    """Item 1: the single-finding entry point sends the same hint the batch path sends.

    The hint comes from the product's primitive (``presence.measure``), so a high-coverage
    paraphrase — not a substring of the clause, yet substantially present — must NOT be
    flagged. A naive ``claim_text not in clause_text`` test would flag it."""

    _HINT = ("[the claim's wording does not appear in the cited clause; "
             "answer grounded only if the clause still entails it]")
    _CLAUSE = "The receiving party shall not disclose confidential information to any third party"

    def _content(self, gateway: MagicMock) -> str:
        return next(m["content"] for m in gateway.chat.call_args[0][1] if m["role"] == "user")

    def test_an_absent_wording_claim_gets_the_hint(self, mock_gateway: MagicMock) -> None:
        CitationGroundingDiscriminator(mode="lenient", gateway=mock_gateway).ground_claim(
            "Liquidated damages of five million dollars are payable upon breach", "4.3", self._CLAUSE)
        assert self._HINT in self._content(mock_gateway)

    def test_a_high_coverage_paraphrase_gets_no_hint(self, mock_gateway: MagicMock) -> None:
        CitationGroundingDiscriminator(mode="lenient", gateway=mock_gateway).ground_claim(
            "The recipient must not disclose confidential information to any third party",
            "4.3", self._CLAUSE)
        assert self._HINT not in self._content(mock_gateway)
```
- [ ] **Step 2: Run it to watch it fail.** Run `uv run pytest tests/unit/test_grounding_discriminator.py::TestGroundClaimAsksTheProductQuestion -q` — Expected: `test_an_absent_wording_claim_gets_the_hint` FAILS with `AssertionError`; the other two pass.
- [ ] **Step 3: Implement (minimal).** Replace the message construction in `ground_claim` (`:103-106`) with (no new helper, no new parameter):
```python
        # The same hint the batch path sends, from the same primitive. Text only.
        _score, wording_absent = presence.measure(claim_text, clause_text)
        messages = build_grounding_messages(
            source_clauses=[source_clause],
            claims=[(0, claim_text, cited_clause_id)],
            wording_absent_indices={0} if wording_absent else None)
```
(`presence` is already imported at the top of `discriminator.py`.)
- [ ] **Step 4: Run to verify.** Run `uv run pytest tests/unit/test_grounding_discriminator.py tests/unit/test_grounding_prompts.py tests/unit/test_grounding_presence.py -q` — Expected: all pass.
- [ ] **Step 5: Commit.**
```bash
git add src/openreview_cli/grounding/discriminator.py tests/unit/test_grounding_discriminator.py
git commit -m "feat(grounding): ask the product's question from ground_claim

Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```
**Deliberate wrong implementation to catch:** computing the hint with a naive substring test (or `coverage < 1.0`) — `test_a_high_coverage_paraphrase_gets_no_hint` fails.

---

### Task 3: The test tool's bad sentences become genuinely bad (item 2)

**Files:** Modify `src/openreview_cli/grounding/corruption.py` (add `operand_change`; `ClauseUnit` gains `document`), `scripts/measure_slm_slots.py` (`ClauseUnit` `:275`,`:339`; `_label` `:353`; `_build_grounding_labels` `:363-441`; imports `:56-65`; caveat `:98-100`). Test: `tests/unit/test_grounding_corruption.py`, `tests/unit/test_grounding_harness.py`.

**Interfaces:** Produces `operand_change(clause_text: str) -> str | None`; `ClauseUnit(id, text, document: str | None = None)`; each `_label(...)` row gains `"kind": str` and `"source_document": str | None`. Consumes `first_qualifying_sentence`, `is_genuine_negative`, `unsupported_claim`, `paraphrase`. **Note:** operand substitution is **new code**; `hallucination` returns ten fixed fabrications and maps no operand.

- [ ] **Step 1: Write the failing tests.** Add to `tests/unit/test_grounding_corruption.py` (module already imports `ClauseUnit`, `first_qualifying_sentence`, `is_genuine_negative`; add `operand_change`):
```python
class TestOperandChange:
    """A sound negative: the cited clause's own sentence with one operand changed."""

    def test_changes_an_operand_and_is_not_the_clause_sentence(self) -> None:
        unit = ClauseUnit(id="c000", text=(
            "4.4 Term. The receiving party shall keep the Confidential Information "
            "confidential for five years from the effective date."))
        changed = operand_change(unit.text)
        assert changed is not None
        assert changed != first_qualifying_sentence(unit.text)
        assert is_genuine_negative(changed, unit.text) is True

    def test_returns_none_when_no_operand_occurs(self) -> None:
        # The caller must fall back to the cross-document negative rather than keep an
        # unchanged sentence labelled unsupported.
        assert operand_change(
            "4.9 Governing Law. The parties agree that this agreement is governed by the "
            "laws of the state named above.") is None
```
Add to `tests/unit/test_grounding_harness.py` (`PARA_A`, `PARA_B`, `_tiny_corpus`, `SCRIPT` are module-level):
```python
class TestGroundingNegativeKinds:
    """Item 2: the cross-clause negative comes from a different document, and the operand
    change is preferred when the cited clause has an operand. Each row records its own kind."""

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

    def test_operand_change_is_preferred_and_recorded(self, tmp_path: Path) -> None:
        units, _ = SCRIPT._load_corpus_units(_tiny_corpus(tmp_path), limit=2)
        labels, _drops, _generated, _skips = SCRIPT._build_grounding_labels(units)
        assert {row["kind"] for row in labels if row["expected"] == "unsupported"} == {
            "operand_change"}

    def test_a_clause_without_an_operand_still_gets_a_sound_negative(self) -> None:
        no_operand = ClauseUnit(id="c000", document="a.txt", text=(
            "4.9 Governing Law. The parties agree that this agreement is governed by the "
            "laws of the state named above. Nothing in this section survives termination."))
        other = ClauseUnit(id="c001", document="b.txt", text=(
            "9.3 Payment Terms. The customer shall pay all undisputed invoices within "
            "thirty days of receipt. Late payments accrue interest until paid in full."))
        labels, _drops, _generated, _skips = SCRIPT._build_grounding_labels([no_operand, other])
        neg = [row for row in labels if row["generator"] == "unsupported_claim"]
        assert neg and neg[0]["kind"] == "cross_document"
        assert neg[0]["source_document"] == "b.txt"
```
- [ ] **Step 2: Run them to watch them fail.** Run `uv run pytest tests/unit/test_grounding_corruption.py::TestOperandChange tests/unit/test_grounding_harness.py::TestGroundingNegativeKinds -q` — Expected: `AttributeError: module ... has no attribute 'operand_change'` and `TypeError: ClauseUnit.__new__() got an unexpected keyword argument 'document'`.
- [ ] **Step 3: Implement.** In `corruption.py`, add below `paraphrased_unsupported`:
```python
# FIX 9 — the reviewed operand map, limited to the operands this corpus carries: a
# prior-written-consent phrase, the two party labels, a survival period and a payment period.
# Anything else is dead weight the corpus never reaches. The first matching pair wins.
_OPERAND_MAP: tuple[tuple[str, str], ...] = (
    ("prior written consent", "prior oral consent"),
    ("receiving party", "disclosing party"),
    ("five years", "nine years"),
    ("thirty", "ninety"),
)
_OPERAND_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(rf"\b{re.escape(source)}\b", re.IGNORECASE), replacement)
    for source, replacement in _OPERAND_MAP)


def operand_change(clause_text: str) -> str | None:
    """The clause's own qualifying sentence with one operand changed, or ``None`` when it has
    no qualifying sentence or no mapped operand — the caller then uses the cross-document
    negative rather than keep an unchanged sentence."""
    sentence = first_qualifying_sentence(clause_text)
    if sentence is None:
        return None
    for pattern, replacement in _OPERAND_PATTERNS:
        changed = pattern.sub(replacement, sentence)
        if changed != sentence:
            return changed
    return None
```
In `corruption.py`, extend `ClauseUnit` with `document: str | None = None` (the contract this paragraph came from, so the harness can draw its cross-clause negative from a *different* document). In `scripts/measure_slm_slots.py`: imports (`:56-65`) add `operand_change` and `paraphrase`, drop `paraphrased_unsupported` (unused → `ruff` fails); `_load_corpus_units` (`:275`) builds `ClauseUnit(id=f"c{len(units):03d}", text=paragraph, document=path.name)`; `_strip_grounding_units` (`:339`) keeps the document via `document_by_id = {u.id: u.document for u in units}`; `_label` (`:353`) adds keyword-only defaults so positive call sites are unchanged:
```python
def _label(claim_text: str, unit: ClauseUnit, expected: str, generator: str, *,
           kind: str = "positive", source_document: str | None = None) -> dict[str, Any]:
    return {"claim_text": claim_text, "unit_id": unit.id, "clause_text": unit.text,
            "expected": expected, "generator": generator, "kind": kind,
            "source_document": source_document}
```
Add `_negative_source(unit, units, index) -> ClauseUnit | None`: a different-document unit if one exists, else any other unit, deterministic (`pool[index % len(pool)]`). Then replace the `other = units[(index + 1) % count]` block (`:405-432`) with:
```python
        if count > 1:
            other = _negative_source(unit, units, index)
            if other is not None:
                changed = operand_change(unit.text)
                if changed is not None:
                    cross, kind, source_document = changed, "operand_change", unit.document
                else:
                    cross = unsupported_claim(unit, other)
                    kind, source_document = "cross_document", other.document
                if cross is not None:  # None = degenerate pair, nothing to score
                    generated["unsupported_claim"] += 1
                    if is_genuine_negative(cross, unit.text):
                        labels.append(_label(cross, unit, "unsupported", "unsupported_claim",
                                             kind=kind, source_document=source_document))
                    else:
                        drops["unsupported_claim"] += 1
                    rewritten = paraphrase(cross)
                    if rewritten == cross:
                        paraphrase_skips += 1
                    else:
                        generated["paraphrased_unsupported"] += 1
                        if is_genuine_negative(rewritten, unit.text):
                            labels.append(_label(rewritten, unit, "unsupported",
                                                 "paraphrased_unsupported", kind=kind,
                                                 source_document=source_document))
                        else:
                            drops["paraphrased_unsupported"] += 1
```
The hallucination call (`:434-439`) must record its own kind (FIX 8):
```python
        fabricated = hallucination(positive)
        generated["hallucination"] += 1
        if is_genuine_negative(fabricated, unit.text):
            labels.append(_label(fabricated, unit, "unsupported", "hallucination",
                                 kind="hallucination"))
        else:
            drops["hallucination"] += 1
```
The caveat (`:98-100`) gains one sentence naming the two kinds (`operand_change`, `cross_document`) and that the guard still cannot prove non-entailment. Do not weaken the existing caveats.
- [ ] **Step 4: Update the tests that pin today's exact numbers, then run.** Numbers were **computed by running the new label builder** over the fixtures (operand map above):
  - `test_builds_both_paraphrase_classes` — unchanged: `len(supported) == 4`, `generated == {"unsupported_claim": 2, "hallucination": 2, "paraphrased_unsupported": 2}`, `drops == {all 0}`, `skips == 0`.
  - `test_unchanged_rewrites_are_skipped_and_counted_not_labelled` — monkeypatch `SCRIPT.paraphrased_supported` to `lambda unit: SCRIPT.first_qualifying_sentence(unit.text)`, `SCRIPT.paraphrase` to identity, `SCRIPT.operand_change` to `lambda _t: None`; `skips == 4`, no `paraphrased_*` rows.
  - `test_negation_guarded_no_op_is_counted_as_a_skip_not_a_label` — now `skips == 1`; replace the old "no `paraphrased_unsupported` for c001" assertion with `assert any(row["generator"] == "paraphrased_unsupported" and row["unit_id"] == "c001" for row in labels)`.
  - `TestGroundingAccuracyEndToEnd::test_counts_and_per_generator_drops_are_reported` — add `monkeypatch.setattr(SCRIPT, "operand_change", lambda _text: None)` before the `unsupported_claim` patch; counts unchanged: `positives == 4`, `negatives_kept == 4`, `negatives_dropped_guard == 2`, `negatives_dropped_guard_by_generator == {"unsupported_claim": 2, "hallucination": 0, "paraphrased_unsupported": 0}`, `bad_caught == 4`, `len(per_label) == 8`, `len(stub.calls) == 8`.
  - `TestGroundingArmPreflight::test_reachable_arm_proceeds_and_says_so` — `len(per_label) == 8`, `len(stub.calls) == 8`.
  Run `uv run pytest tests/unit/test_grounding_corruption.py tests/unit/test_grounding_harness.py -q` — Expected: all pass.
- [ ] **Step 5: Commit.**
```bash
git add src/openreview_cli/grounding/corruption.py scripts/measure_slm_slots.py \
        tests/unit/test_grounding_corruption.py tests/unit/test_grounding_harness.py
git commit -m "test(grounding): make the harness negatives genuinely unsupported

Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```
**Deliberate wrong implementation to catch:** keeping the source in the same document (the old `units[(index + 1) % count]`) — `test_cross_document_kind_names_a_different_document` fails.

---

### Task 4: The sentence-aware clause window (item 7)

**Files:** Modify `src/openreview_cli/grounding/prompts.py` (`:74`; add two constants and one helper). Test: `tests/unit/test_grounding_prompts.py`.

**Interfaces:** Produces `_CLAUSE_WINDOW_CHARS = 2000`, `_TRUNCATION_MARKER = " …[clause text truncated]"`, `_clause_window(text: str, limit: int = _CLAUSE_WINDOW_CHARS) -> str`. Consumes `nupunkt_detect_boundaries(text) -> list[tuple[int, int]]` (`parsing/clause_detector.py:28`).

- [ ] **Step 1: Write the failing test.**
```python
class TestClauseWindow:
    """Item 7: ~2000 characters, whole sentences while they fit, a marker when text was left out."""

    def test_a_long_clause_is_cut_on_a_sentence_boundary_and_marked(self) -> None:
        text = "The receiving party shall not disclose Confidential Information to anyone. " * 80
        window = _clause_window(text)
        assert len(window) <= _CLAUSE_WINDOW_CHARS + len(_TRUNCATION_MARKER)
        assert window.endswith(_TRUNCATION_MARKER)
        body = window[: -len(_TRUNCATION_MARKER)]
        assert text.startswith(body) and body.rstrip().endswith(".")

    def test_a_single_oversized_first_sentence_is_hard_clipped(self) -> None:
        # The bound in the sentence-boundary test must hold for every input, so a first
        # sentence longer than the window is clamped at the window, not kept whole.
        text = "x" * (_CLAUSE_WINDOW_CHARS + 500)
        assert _clause_window(text) == text[:_CLAUSE_WINDOW_CHARS] + _TRUNCATION_MARKER
```
Add `_CLAUSE_WINDOW_CHARS`, `_TRUNCATION_MARKER`, `_clause_window` to the file's imports from `openreview_cli.grounding.prompts`.
- [ ] **Step 2: Run it to watch it fail.** Run `uv run pytest tests/unit/test_grounding_prompts.py::TestClauseWindow -q` — Expected: `ImportError: cannot import name '_clause_window'`.
- [ ] **Step 3: Implement.** In `prompts.py`, add near `_WORDING_ABSENT_HINT`:
```python
# Item 7: 59% of CUAD clauses exceed 500 characters and 99.6% of those were cut mid-word; a
# sentence-aware window of about 2000 characters covers 9 in 10. Whole sentences while they
# fit; a single sentence longer than the window is hard-clipped.
_CLAUSE_WINDOW_CHARS = 2000
_TRUNCATION_MARKER = " …[clause text truncated]"


def _clause_window(text: str, limit: int = _CLAUSE_WINDOW_CHARS) -> str:
    """At most ``limit`` characters of ``text``, cut on a sentence boundary when one fits.
    A single first sentence longer than ``limit`` is hard-clipped at ``limit``."""
    if len(text) <= limit:
        return text
    from openreview_cli.parsing.clause_detector import nupunkt_detect_boundaries

    end = 0
    for _start, stop in nupunkt_detect_boundaries(text):
        if stop <= limit and text[end:stop].strip():
            end = stop
    if end == 0:  # the first sentence alone exceeds the window: hard-clip it
        end = limit
    return text[:end].rstrip() + _TRUNCATION_MARKER
```
Change `:74` from `text = clause.text[:500]` to `text = _clause_window(clause.text)`.
- [ ] **Step 4: Run to verify.** Run `uv run pytest tests/unit/test_grounding_prompts.py -q` — Expected: all pass, including `test_none_is_byte_identical_to_omitting_the_argument` and the two `NEW_TAIL` pins.
- [ ] **Step 5: Commit.**
```bash
git add src/openreview_cli/grounding/prompts.py tests/unit/test_grounding_prompts.py
git commit -m "feat(grounding): show a sentence-aware ~2000-character clause window

Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```
**Deliberate wrong implementation to catch:** `text = clause.text[:2000]` (the same bug at a bigger number) — `test_a_long_clause_is_cut_on_a_sentence_boundary_and_marked` fails.

---

### Task 5: Sibling clauses, the fourth answer, and its non-downgrading guard (item 3)

**Files:** Modify `src/openreview_cli/grounding/prompts.py` (add `_MAX_PROMPT_CLAUSES`, `_format_clauses`, `parse_miscited_ids`, one template bullet), `src/openreview_cli/grounding/discriminator.py` (`_process_batch` `:236-355`). Test: `tests/unit/test_grounding_prompts.py`, `tests/unit/test_grounding_discriminator.py`.

**Interfaces:** Produces `_MAX_PROMPT_CLAUSES = 20`; `build_grounding_messages` shows at most that many clauses via `_clause_window`; `parse_miscited_ids(response: str) -> dict[int, str]`. `miscited_to_clause_id` already exists (Task 1). Consumes `presence.measure`, `_clause_window` (Task 4).

- [ ] **Step 1: Write the failing tests.** In `tests/unit/test_grounding_prompts.py`:
```python
def test_the_prompt_shows_at_most_the_cap_of_clauses() -> None:
    clauses = [Clause(id=f"c{i}", title=None, text="Sentence one is here. " * 20, level=1,
                      parent_id=None, source_page=1, source_paragraph=None, source_span=None)
               for i in range(_MAX_PROMPT_CLAUSES + 5)]
    content = _user_content(build_grounding_messages(clauses, [(0, "a claim", "c0")]))
    clause_lines = [line for line in content.splitlines() if line.startswith("[")]
    assert len(clause_lines) == _MAX_PROMPT_CLAUSES
    assert all(len(line) <= _CLAUSE_WINDOW_CHARS + len(_TRUNCATION_MARKER) + 8
               for line in clause_lines)


def test_the_prompt_offers_the_fourth_answer_as_a_field() -> None:
    assert "miscited_to_clause_id" in GROUNDING_PROMPT_TEMPLATE
    # The three verdicts are unchanged: the fourth answer is a field, never a verdict.
    assert '"grounded" | "ungrounded" | "uncertain"' in GROUNDING_PROMPT_TEMPLATE


def test_the_verdict_enum_has_no_fourth_member() -> None:
    assert set(GroundingVerdict.__members__) == {"GROUNDED", "UNGROUNDED", "UNCERTAIN"}
```
In `tests/unit/test_grounding_discriminator.py`:
```python
class TestMiscitedIsAFieldWithAGuard:
    """Item 3, FIX 1: a real-but-miscited finding is kept with a field, and the field is
    believed only when the finding's wording is substantially present in the named clause.
    A failed guard changes only the pointer — the verdict is never re-judged."""

    _CLAIM = "The receiving party shall keep the Confidential Information confidential for five years"
    _CITED = "4.4 The term of the confidentiality obligation is three years from the date of disclosure."
    # FIX 8: real text whose wording IS substantially present in the claim. Measured:
    # presence.measure(_CLAIM, _SIBLING_SUPPORTS) == (1.0, False), so the guard accepts it.
    _SIBLING_SUPPORTS = ("4.7 The receiving party shall keep the Confidential Information "
                         "confidential for five years after disclosure.")
    # Measured (0.083, True): the claim's wording is absent, so the guard drops the pointer.
    _SIBLING_UNRELATED = "9.2 Neither party may assign this agreement without prior written consent."

    def _clauses(self) -> list[Clause]:
        from openreview_cli.parsing.models import Clause
        return [Clause(id=cid, title=None, text=text, level=1, parent_id=None, source_page=1,
                       source_paragraph=None, source_span=None)
                for cid, text in (("4.4", self._CITED), ("4.7", self._SIBLING_SUPPORTS),
                                  ("9.2", self._SIBLING_UNRELATED))]

    def _report(self) -> ReviewReport:
        from datetime import datetime
        from openreview_cli.review.models import (ClauseAssessment, DocMeta, Position,
                                                  QAVerdict, ReviewReport, ReviewSummary)
        return ReviewReport(
            document=DocMeta(filename="t.pdf", page_count=1, clause_count=3, pii_stripped=False),
            assessments=[ClauseAssessment(
                clause_id="4.4", clause_text=self._CITED, playbook_category="confidentiality-term",
                position=Position.PREFERRED, confidence=0.9, citation=self._CLAIM,
                qa_verdict=QAVerdict.agree, extraction_model="test", qa_model="test")],
            summary=ReviewSummary(), playbook_id="test", generated_at=datetime.now())

    def _answer(self, miscited: str) -> str:
        return json.dumps([{"claim_index": 0, "verdict": "grounded", "provenances": [],
                            "confidence": 0.9, "reason": None,
                            "miscited_to_clause_id": miscited}])

    def _ground(self, miscited: str, mock_gateway, sample_document):
        mock_gateway.chat.return_value = self._answer(miscited)
        return CitationGroundingDiscriminator(mode="lenient", gateway=mock_gateway).ground_report(
            self._report(), sample_document, self._clauses()).verdicts[0]

    def test_a_supported_recitation_is_kept_and_named(self, mock_gateway, sample_document) -> None:
        result = self._ground("4.7", mock_gateway, sample_document)
        assert result.verdict is GroundingVerdict.GROUNDED
        assert result.miscited_to_clause_id == "4.7"

    def test_a_hallucinated_recitation_keeps_the_verdict_and_drops_the_pointer(
            self, mock_gateway, sample_document) -> None:
        result = self._ground("9.2", mock_gateway, sample_document)
        assert result.verdict is GroundingVerdict.GROUNDED
        assert result.miscited_to_clause_id is None

    def test_an_unknown_named_clause_keeps_the_verdict_and_drops_the_pointer(
            self, mock_gateway, sample_document) -> None:
        result = self._ground("77.7", mock_gateway, sample_document)
        assert result.verdict is GroundingVerdict.GROUNDED
        assert result.miscited_to_clause_id is None
```
- [ ] **Step 2: Run them to watch them fail.** Run `uv run pytest tests/unit/test_grounding_prompts.py::test_the_prompt_shows_at_most_the_cap_of_clauses tests/unit/test_grounding_discriminator.py::TestMiscitedIsAFieldWithAGuard -q` — Expected: `ImportError: cannot import name '_MAX_PROMPT_CLAUSES'`, then `assert result.miscited_to_clause_id == "4.7"` fails (never set yet).
- [ ] **Step 3: Implement.** In `prompts.py`: add `_MAX_PROMPT_CLAUSES = 20`; add `_format_clauses(source_clauses)` returning `"\n\n".join(f"[{c.id}]: {_clause_window(c.text)}" for c in source_clauses[:_MAX_PROMPT_CLAUSES])` (or `"(no clauses provided)"`) and use it in place of the loop at `:72-79`; add to `GROUNDING_PROMPT_TEMPLATE`, after the `reason` bullet and before the final paragraph (so the pinned `NEW_TAIL` still matches): `- miscited_to_clause_id: str | None — set this only when the claim is genuinely true but the clause it cites does not support it while a different clause in the list does; name that clause's id. Leave it null in every other case. Keep verdict "grounded" when you set it.`; add the sibling reader (reusing `_answer_items`/`_first_json_value`/`_claim_index`):
```python
def parse_miscited_ids(response: str) -> dict[int, str]:
    """The fourth answer, per claim: the clause id the checker named, if any."""
    ids: dict[int, str] = {}
    for position, item in enumerate(_answer_items(_first_json_value(response))):
        if isinstance(item, dict):
            named = item.get("miscited_to_clause_id")
            if isinstance(named, str) and named.strip():
                ids[_claim_index(item.get("claim_index"), position)] = named.strip()
    return ids
```
In `discriminator.py` — in `_process_batch`, pass a wider, cited-first clause list to the prompt (keep `_measure_presence` on `matched_clauses` alone):
```python
        cited_ids = {clause.id for clause in matched_clauses}
        prompt_clauses = matched_clauses + [
            clause for clause in (source_clauses or []) if clause.id not in cited_ids]
        messages = build_grounding_messages(prompt_clauses, batch, wording_absent_indices)
```
After the first parse (`miscited_ids = parse_miscited_ids(response)`; `all_clause_text_by_id = {c.id: c.text for c in (source_clauses or [])}`) apply the per-claim guard. **FIX 1 — one line changes only the pointer; the verdict is never re-judged:**
```python
            named = miscited_ids.get(idx)
            named_text = all_clause_text_by_id.get(named) if named is not None else None
            miscited_to_clause_id = (
                named if (named_text and not presence.measure(claim_text, named_text)[1]) else None)
```
Pass `miscited_to_clause_id=miscited_to_clause_id` to the `GroundingResult`.
- [ ] **Step 4: Run to verify.** Run `uv run pytest tests/unit/test_grounding_prompts.py tests/unit/test_grounding_discriminator.py tests/unit/test_grounding_models.py tests/unit/test_grounding_harness.py -q` — Expected: all pass (the harness stubs `ground_claim`, so its counts are unchanged).
- [ ] **Step 5: Commit.**
```bash
git add src/openreview_cli/grounding/prompts.py src/openreview_cli/grounding/discriminator.py \
        tests/unit/test_grounding_prompts.py tests/unit/test_grounding_discriminator.py
git commit -m "feat(grounding): show sibling clauses and keep a real-but-miscited finding

Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```
**Deliberate wrong implementation to catch:** trusting the fourth answer without the presence guard — `test_a_hallucinated_recitation_keeps_the_verdict_and_drops_the_pointer` fails if the pointer is believed.

---

### Task 6: The second narrow question; both must agree; off by default (item 4, FIX 5, FIX 7)

**Files:** Modify `src/openreview_cli/grounding/prompts.py` (share `_JSON_ONLY_TAIL` and the claim-line formatter; add `SECOND_PASS_PROMPT_TEMPLATE`, `build_second_pass_messages`), `src/openreview_cli/grounding/discriminator.py` (`__init__`, `ground_claim`, `_process_batch`; add `combine_grounding_passes`, `_second_pass`). Test: `tests/unit/test_grounding_prompts.py`, `tests/unit/test_grounding_discriminator.py`.

**Interfaces:** Produces `build_second_pass_messages(source_clauses, claims) -> list[dict[str, str]]`; `combine_grounding_passes(first, second, *, second_available=True) -> GroundingVerdict`; `CitationGroundingDiscriminator(..., require_pass_agreement: bool = False)`; `self.second_pass_fallbacks: int`. Consumes `parse_grounding_response`, `_format_clauses`; sets `pass_disagreement`/`not_sure` (Task 1).

**Cost note:** with the flag on, the product path makes one extra call per batch (≤10 findings) and `ground_claim` one extra call *per finding* (it is not batched) — deliberate, because `scripts/measure_slm_slots.py:749` measures through `ground_claim`.

- [ ] **Step 1: Write the failing tests.** In `tests/unit/test_grounding_prompts.py` (`_CLAUSES`, `_CLAIMS`, `_user_content` already exist):
```python
def test_the_second_pass_question_is_closed_and_never_asks_for_reasoning() -> None:
    content = _user_content(build_second_pass_messages(_CLAUSES, _CLAIMS))
    assert "leaves out" in content
    for banned in ("step by step", "chain of thought", "think through", "explain your reasoning"):
        assert banned not in content.lower()


def test_the_second_pass_uses_the_same_clause_window() -> None:
    # FIX 8: 100 sentences (~2200 chars) actually exceeds the 2000-char window, so it truncates.
    long_clause = Clause(id="4.3", title=None, text="Sentence one is here. " * 100, level=1,
                         parent_id=None, source_page=1, source_paragraph=None, source_span=None)
    assert _TRUNCATION_MARKER in _user_content(
        build_second_pass_messages([long_clause], [(0, "a claim", "4.3")]))
```
In `tests/unit/test_grounding_discriminator.py`:
```python
class TestBothPassesMustAgree:
    """Item 4: one extra call per batch when the flag is on; either unsupported rejects; both
    must accept; a failed second pass keeps the first pass's verdict."""

    _fixtures = TestGroundingPresenceRecorded()

    def _answer(self, verdict: str) -> str:
        return json.dumps([{"claim_index": 0, "verdict": verdict, "provenances": [],
                            "confidence": 0.9, "reason": None}])

    def test_the_combine_rule(self) -> None:
        G, U, C = GroundingVerdict, GroundingVerdict.UNGROUNDED, GroundingVerdict.UNCERTAIN
        assert combine_grounding_passes(G.GROUNDED, G.GROUNDED) is G.GROUNDED
        assert combine_grounding_passes(G.GROUNDED, U) is U
        assert combine_grounding_passes(U, G.GROUNDED) is U
        assert combine_grounding_passes(G.GROUNDED, C) is C
        assert combine_grounding_passes(C, U) is C
        # An unavailable second pass keeps the first verdict — never a downgrade.
        assert combine_grounding_passes(G.GROUNDED, None, second_available=False) is G.GROUNDED

    def test_the_rule_is_off_by_default(self, mock_gateway) -> None:
        CitationGroundingDiscriminator(mode="lenient", gateway=mock_gateway).ground_claim(
            "a claim", "4.3", "the clause text")
        assert mock_gateway.chat.call_count == 1

    def test_ground_claim_calls_the_gateway_twice_and_applies_the_rule(self, mock_gateway) -> None:
        mock_gateway.chat.side_effect = [self._answer("grounded"), self._answer("ungrounded")]
        d = CitationGroundingDiscriminator(
            mode="lenient", gateway=mock_gateway, require_pass_agreement=True)
        verdict, _p, _c = d.ground_claim("a claim", "4.3", "the clause text")
        assert mock_gateway.chat.call_count == 2
        assert verdict is GroundingVerdict.UNGROUNDED

    def test_a_failed_second_call_keeps_the_first_verdict_and_counts_it(self, mock_gateway) -> None:
        mock_gateway.chat.side_effect = [self._answer("grounded"), RuntimeError("boom")]
        d = CitationGroundingDiscriminator(
            mode="lenient", gateway=mock_gateway, require_pass_agreement=True)
        verdict, _p, _c = d.ground_claim("a claim", "4.3", "the clause text")
        assert verdict is GroundingVerdict.GROUNDED
        assert d.second_pass_fallbacks == 1

    def test_ground_report_makes_one_second_call_per_batch(
            self, mock_gateway, sample_report, sample_document) -> None:
        sample_report.assessments = sample_report.assessments[:3]
        mock_gateway.chat.return_value = json.dumps(
            [{"claim_index": i, "verdict": "grounded", "provenances": [], "confidence": 0.9,
              "reason": None} for i in range(3)])
        d = CitationGroundingDiscriminator(
            mode="lenient", gateway=mock_gateway, require_pass_agreement=True)
        d.ground_report(sample_report, sample_document)
        assert mock_gateway.chat.call_count == 2  # one first pass + one narrow question

    def test_a_disagreement_is_recorded_on_the_result(self, mock_gateway, sample_document) -> None:
        mock_gateway.chat.side_effect = [self._answer("grounded"), self._answer("ungrounded")]
        d = CitationGroundingDiscriminator(
            mode="lenient", gateway=mock_gateway, require_pass_agreement=True)
        cg = d.ground_report(self._fixtures._report(self._fixtures._CLAIM), sample_document,
                             self._fixtures._source_clauses())
        assert cg.verdicts[0].verdict is GroundingVerdict.UNGROUNDED
        assert cg.verdicts[0].pass_disagreement is True
        assert cg.verdicts[0].not_sure is False
```
- [ ] **Step 2: Run them to watch them fail.** Run `uv run pytest tests/unit/test_grounding_discriminator.py::TestBothPassesMustAgree -q` — Expected: `ImportError: cannot import name 'combine_grounding_passes'`; with it present but unwired, `test_ground_claim_calls_the_gateway_twice_and_applies_the_rule` fails with `call_count == 1`.
- [ ] **Step 3: Implement.** In `prompts.py` — share the machinery (FIX 5): define the JSON-only tail once and append it to both templates by concatenation, so the raw `GROUNDING_PROMPT_TEMPLATE` still contains the pinned `NEW_TAIL`:
```python
_JSON_ONLY_TAIL = (
    "For each claim, respond with one JSON object. If there is a single claim, you may return that "
    "object on its own; if there are several, return a JSON array of the objects, one per claim, in the "
    "same order as the input claims. Return the JSON only — no text before or after it."
)
GROUNDING_PROMPT_TEMPLATE = _GROUNDING_PROMPT_HEAD + _JSON_ONLY_TAIL
SECOND_PASS_PROMPT_TEMPLATE = (
    "You are checking one narrow question about a contract finding and the clause it cites.\n\n"
    "Question: does the cited clause impose a condition, a limit, a number or a party that the "
    "finding leaves out?\n\nAnswer about the clause's content only. Do not restate the finding and "
    "do not explain your answer.\n\nSource clauses:\n{clauses_text}\n\nFindings to check:"
    "\n{claims_text}\n\n") + _JSON_ONLY_TAIL


def _format_claim(claim: tuple[int, str, str]) -> str:
    """One claim line, shared by both passes so the finding's wording is sent identically."""
    idx, claim_text, cited_clause_id = claim
    truncated = claim_text[:300] if len(claim_text) > 300 else claim_text
    return f'{idx}. "{truncated}" (cites clause {cited_clause_id})'


def build_second_pass_messages(source_clauses: list[Clause],
                               claims: list[tuple[int, str, str]]) -> list[dict[str, str]]:
    """Messages for the one narrow second question. No hint: the question is different."""
    return [{"role": "user", "content": SECOND_PASS_PROMPT_TEMPLATE.format(
        clauses_text=_format_clauses(source_clauses),
        claims_text="\n".join(_format_claim(c) for c in claims))}]
```
`build_grounding_messages` uses the same `_format_claim` (then appends `_WORDING_ABSENT_HINT` on flagged lines), so the two passes cannot drift. In `discriminator.py` (module level):
```python
def combine_grounding_passes(first: GroundingVerdict, second: GroundingVerdict | None, *,
                             second_available: bool = True) -> GroundingVerdict:
    """Both supported accepts; either unsupported rejects; an available abstention is 'not
    sure'. An unavailable second pass keeps the first verdict — never a downgrade."""
    if not second_available or second is None:
        return first
    if first is GroundingVerdict.GROUNDED and second is GroundingVerdict.GROUNDED:
        return GroundingVerdict.GROUNDED
    if GroundingVerdict.UNGROUNDED in (first, second):
        return GroundingVerdict.UNGROUNDED
    return GroundingVerdict.UNCERTAIN
```
`__init__`: add `require_pass_agreement: bool = False`, store it, and add `self.second_pass_fallbacks = 0`. Add one private method used by both entry points:
```python
    def _second_pass(self, prompt_clauses: list[Clause],
                     batch: list[tuple[int, str, str]]) -> dict[int, GroundingVerdict] | None:
        """The narrow question, one call per batch, forwarding the same model override and
        session id as the first pass. ``None`` when the call failed or nothing parsed: the
        caller then keeps the first pass's verdict, so a broken second pass can never turn an
        accepted finding into 'not sure' (which strict mode deletes)."""
        messages = build_second_pass_messages(prompt_clauses, batch)
        chat_kwargs: dict[str, Any] = {"requirement": CapabilityRequirement(capability="reasoning")}
        if self._model:
            chat_kwargs["model"] = self._model
        if self._session_id is not None:
            chat_kwargs["session_id"] = self._session_id
        try:
            response = self._gateway.chat("grounding", messages, **chat_kwargs)
        except Exception as e:
            logger.warning("Second grounding pass failed: %s", e)
            return None
        parsed = parse_grounding_response(response)
        return {index: verdict for index, verdict, _p, _c in parsed} if parsed else None
```
- `ground_claim`: when `self.require_pass_agreement`, after the first parse succeeds call `second = self._second_pass([source_clause], [(0, claim_text, cited_clause_id)])`; if `second` is `None` or lacks index 0, increment `second_pass_fallbacks` and keep `verdict`; else `verdict = combine_grounding_passes(verdict, second[0])`. When the first answer is unreadable or the gateway raises, return early exactly as today.
- `_process_batch`: when the flag is on, call `second = self._second_pass(prompt_clauses, batch)` once after the first-pass mapping; per claim set `verdict = first_verdict` if `second is None` or the index is missing (and increment `second_pass_fallbacks`), else `combine_grounding_passes(first_verdict, second[idx])`; set `pass_disagreement = {first_verdict, second[idx]} == {GROUNDED, UNGROUNDED}` only when a second verdict exists and `not_sure = verdict is GroundingVerdict.UNCERTAIN`, before the audit entry (one audit entry per claim). The gateway-error fallback path is unchanged.
- [ ] **Step 4: Run to verify, including the two existing tests this work moves (FIX 8).** Update `test_model_override_passed_to_gateway` to construct with `require_pass_agreement=True` and assert the override on **every** call (the second call must carry it too): `assert all(call.kwargs.get("model") == "openrouter/deepseek/deepseek-r1" for call in mock_gateway.chat.call_args_list)`. Update `TestWordingAbsentHintReachesTheModel::test_only_the_absent_claims_line_carries_the_hint` (and its class's other call-args reads) to read the **first** call: `messages = mock_gateway.chat.call_args_list[0][0][1]` (with a second pass the last call is the second pass, which carries no hint).

  Run `uv run pytest tests/unit/test_grounding_discriminator.py tests/unit/test_grounding_models.py tests/unit/test_grounding_prompts.py -q` — Expected: all pass — in particular `test_only_the_claims_missing_from_a_partial_batch_are_counted` (`unreadable_answers == 2`), `test_an_unreadable_batch_counts_every_claim_in_it` (`== 10`), `test_an_unreadable_answer_increments_the_counter` (`== 1`), `test_a_gateway_failure_is_not_counted_as_unreadable` (`== 0`), and `test_model_override_passed_to_gateway`.
- [ ] **Step 5: Commit.**
```bash
git add src/openreview_cli/grounding/prompts.py src/openreview_cli/grounding/discriminator.py \
        tests/unit/test_grounding_prompts.py tests/unit/test_grounding_discriminator.py
git commit -m "feat(grounding): add the second narrow question, gated off by default

Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```
**Deliberate wrong implementation to catch:** accepting on a single pass — `test_ground_claim_calls_the_gateway_twice_and_applies_the_rule` fails; a failed second pass that turns a GROUNDED finding into UNCERTAIN fails `test_a_failed_second_call_keeps_the_first_verdict_and_counts_it`.

---

### Task 7: Confidence is a warning, never the decision — test only (item 5, FIX 3)

**Files:** Test `tests/unit/test_grounding_discriminator.py`. No production change: `confidence_warning`, `grounding_confidence_warning` and `LOW_CONFIDENCE_THRESHOLD` are dropped entirely; `grounding_confidence` is already stored (`merge_into`) and shown.

**Interfaces:** Consumes `TestGroundingPresenceRecorded._report(citation, clause_id)` and `._source_clauses()` already in the file (reused directly, no new helper).

- [ ] **Step 1: Write the guard test.** Append to `tests/unit/test_grounding_discriminator.py`:
```python
class TestConfidenceIsNeverTheVerdict:
    """Item 5 (FIX 3): the checker's confidence is recorded and shown; no verdict path reads
    it. The five real misses came with the checker 0.9-0.95 sure and the correct answers with
    1.0, so the number does not separate wrong from right. No threshold, no warning field."""

    _fixtures = TestGroundingPresenceRecorded()

    def _grounded_at(self, confidence: float, gateway: MagicMock, document: MagicMock):
        gateway.chat.return_value = json.dumps([{"claim_index": 0, "verdict": "grounded",
                                                 "provenances": [], "confidence": confidence,
                                                 "reason": None}])
        d = CitationGroundingDiscriminator(mode="lenient", gateway=gateway)
        cg = d.ground_report(self._fixtures._report(self._fixtures._CLAIM), document,
                             self._fixtures._source_clauses())
        return cg.verdicts[0].verdict

    def test_the_verdict_is_identical_at_both_confidence_extremes(
            self, mock_gateway: MagicMock, sample_document: MagicMock) -> None:
        # One assertion covers the whole requirement: if no verdict path read the number, the
        # verdict is the same at 0.0 and 1.0 (and is what the pass answered).
        assert (self._grounded_at(0.0, mock_gateway, sample_document)
                is self._grounded_at(1.0, mock_gateway, sample_document)
                is GroundingVerdict.GROUNDED)
```
- [ ] **Step 2: Run it.** Run `uv run pytest tests/unit/test_grounding_discriminator.py::TestConfidenceIsNeverTheVerdict -q` — Expected: PASS immediately. This task adds no production code (FIX 3 deleted the warning fields), so it is a regression guard — the deliberate exception to TDD for item 5, whose whole requirement is the *absence* of a behaviour.
- [ ] **Step 3: Confirm nothing reads confidence.** Run `grep -n "confidence" src/openreview_cli/grounding/discriminator.py` — Expected: every hit records/forwards it (the audit entry, `grounding_confidence`, the second-pass parse) — no comparison that picks a verdict.
- [ ] **Step 4: Commit.**
```bash
git add tests/unit/test_grounding_discriminator.py
git commit -m "test(grounding): pin that no verdict path reads the confidence number

Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```
**Deliberate wrong implementation to catch:** deriving the verdict from the confidence (e.g. `if confidence < threshold: verdict = UNCERTAIN`) — `test_the_verdict_is_identical_at_both_confidence_extremes` fails.

---

### Task 8: The memo's risky-pattern lines hold in both modes (item 6, FIX 4)

**Files:** Modify `src/openreview_cli/review/memo/models.py` (`MemoClause` `:49-66`, `MemoSummary`, `MemoReport.from_dict` `:123-129`), `src/openreview_cli/review/memo/exporter.py` (`:114-123`), `src/openreview_cli/review/memo/formats.py` (`_wording_note` `:61-74` → `_risky_note`; add `_exclusions_note`; Markdown/DOCX call sites). Test: `tests/unit/review/test_memo_formats.py`, `tests/unit/review/test_memo_exporter.py`.

**Interfaces:** Produces `MemoClause.not_sure: bool = False`, `MemoClause.pass_disagreement: bool = False`; `MemoSummary.grounding_excluded_unsupported: int = 0`, `.grounding_excluded_unsure: int = 0` (from the `ReviewReport` counts Task 1 recorded); `_risky_note(clause) -> str | None`; `_exclusions_note(memo) -> str | None`. Consumes `ClauseAssessment.not_sure`/`pass_disagreement`, `ReviewReport.grounding_excluded_*`. Does not consume `assign_colors`.

**Why the restructure (FIX 4):** in the default strict mode, UNGROUNDED and UNCERTAIN findings are removed before the memo is built, so only the accepted-although-wording-absent line (a) is reachable there. Strict mode reports the two counts instead (b); the per-finding "not sure" and "the two passes disagreed" lines (c) are tested end-to-end in lenient mode only.

- [ ] **Step 1: Write the failing tests.** In `tests/unit/review/test_memo_formats.py`, extend `_make_wording_note_memo` with `not_sure: bool = False, pass_disagreement: bool = False` (passed to `MemoClause`) and add:
```python
NOT_SURE_TEXT = "Grounding: not sure (the checker did not accept this citation)"
DISAGREED_TEXT = "Grounding: the two passes disagreed"
EXCLUSIONS_TEXT = "Excluded by grounding (strict): 2 unsupported, 1 not sure"


class TestMarkdownRiskyPatterns:
    def test_an_ordinary_clause_renders_exactly_as_today(self) -> None:
        ordinary = _make_wording_note_memo(accepted_despite_absent_wording=False, grounding_presence=1.0)
        baseline = _make_wording_note_memo(accepted_despite_absent_wording=False, grounding_presence=None)
        assert render_markdown(ordinary) == render_markdown(baseline)

    def test_each_risky_case_gets_its_own_line(self) -> None:
        absent = _make_wording_note_memo(accepted_despite_absent_wording=True, grounding_presence=0.46)
        not_sure = _make_wording_note_memo(accepted_despite_absent_wording=False,
                                           grounding_presence=1.0, not_sure=True)
        disagreed = _make_wording_note_memo(accepted_despite_absent_wording=False,
                                            grounding_presence=1.0, pass_disagreement=True)
        assert WORDING_NOTE_TEXT in render_markdown(absent)
        assert NOT_SURE_TEXT in render_markdown(not_sure)
        assert DISAGREED_TEXT in render_markdown(disagreed)

    def test_the_strict_exclusion_summary_line(self) -> None:
        memo = _make_wording_note_memo(accepted_despite_absent_wording=False, grounding_presence=None)
        memo.overall.grounding_excluded_unsupported = 2
        memo.overall.grounding_excluded_unsure = 1
        assert EXCLUSIONS_TEXT in render_markdown(memo)
```
plus the same three assertions for `render_docx(...)` paragraph texts (via `[p.text for p in render_docx(memo).paragraphs]`). Update every existing caller of `_wording_note` to the new `_risky_note` name (the existing `WORDING_NOTE_TEXT` assertions keep passing). Add to `tests/unit/review/test_memo_exporter.py` (add the imports shown to that module):
```python
class TestRiskyLinesAreReachableInLenientMode:
    """(c) The per-finding 'not sure' and 'disagreed' lines exist only in lenient mode.

    The default grounding mode is strict, and strict removes UNGROUNDED and UNCERTAIN
    findings before the memo is built, so these two lines are unreachable there. This drives
    the real grounding path in lenient mode with the agreement rule on, then renders the memo."""

    def test_both_lines_render_end_to_end(self) -> None:
        def assessment() -> ClauseAssessment:
            return ClauseAssessment(
                clause_id="4.3", clause_text="The receiving party shall not disclose.",
                playbook_category="confidentiality", position=Position.PREFERRED, confidence=0.9,
                citation="The receiving party shall not disclose confidential information",
                qa_verdict=QAVerdict.agree, extraction_model="test", qa_model="test")

        report = ReviewReport(
            document=DocMeta(filename="t.pdf", page_count=1, clause_count=1, pii_stripped=False),
            assessments=[assessment(), assessment()], summary=ReviewSummary(),
            playbook_id="test", generated_at=datetime.now())
        clauses = [Clause(id="4.3", title=None, level=1, parent_id=None, source_page=1,
                          source_paragraph=None, source_span=None,
                          text="The receiving party shall not disclose confidential information "
                               "to any third party.")]
        gateway = MagicMock()
        gateway.chat.side_effect = [
            json.dumps([{"claim_index": i, "verdict": v, "provenances": [], "confidence": 0.9,
                         "reason": None} for i, v in ((0, "uncertain"), (1, "grounded"))]),
            json.dumps([{"claim_index": i, "verdict": v, "provenances": [], "confidence": 0.9,
                         "reason": None} for i, v in ((0, "uncertain"), (1, "ungrounded"))])]
        discriminator = CitationGroundingDiscriminator(
            mode="lenient", gateway=gateway, require_pass_agreement=True)
        discriminator.ground_report(report, MagicMock(), clauses).merge_into(report)

        markdown = render_markdown(MemoExporter(report=report, mode="precheck")._build_memo_report())
        assert NOT_SURE_TEXT in markdown
        assert DISAGREED_TEXT in markdown
```
(with `from datetime import datetime`, `from unittest.mock import MagicMock`, `json`; `CitationGroundingDiscriminator`; `Clause`; `MemoExporter`, `render_markdown`; `NOT_SURE_TEXT`/`DISAGREED_TEXT` from `test_memo_formats`; and the `openreview_cli.review.models` names.)
- [ ] **Step 2: Run them to watch them fail.** Run `uv run pytest tests/unit/review/test_memo_formats.py tests/unit/review/test_memo_exporter.py -q` — Expected: `TypeError` on the new keyword arguments, then `assert NOT_SURE_TEXT in ...` fails.
- [ ] **Step 3: Implement.** `models.py`: add `not_sure: bool = False` and `pass_disagreement: bool = False` to `MemoClause`; add `grounding_excluded_unsupported: int = 0` and `grounding_excluded_unsure: int = 0` to `MemoSummary`; read them in `MemoReport.from_dict` (`not_sure=bool(c.get("not_sure", False))`, `pass_disagreement=bool(c.get("pass_disagreement", False))` for the clause, `grounding_excluded_unsupported=int(overall_raw.get("grounding_excluded_unsupported", 0))`, `grounding_excluded_unsure=int(overall_raw.get("grounding_excluded_unsure", 0))` for the summary). `exporter.py` (`:114-123`): set `not_sure=bool(ca.not_sure)`, `pass_disagreement=bool(ca.pass_disagreement)` on each `MemoClause`, and the two `MemoSummary` counts from `self.report.grounding_excluded_*`. `formats.py`: rename `_wording_note` to `_risky_note` (cases (a) then (c)) and add `_exclusions_note` (case (b)):
```python
def _risky_note(clause: MemoClause) -> str | None:
    """The one risky-pattern line this clause earns, or ``None`` for an ordinary clause.
    (a) accepted although the wording is absent (reachable in strict); (c) "not sure" or the
    two passes disagreed (reachable in lenient only). Display only."""
    if clause.accepted_despite_absent_wording:
        if clause.grounding_presence is None:
            return "Citation wording not present in the cited clause"
        return (f"Citation wording not present in the cited clause "
                f"(coverage {clause.grounding_presence:.2f})")
    if clause.not_sure:
        return "Grounding: not sure (the checker did not accept this citation)"
    if clause.pass_disagreement:
        return "Grounding: the two passes disagreed"
    return None


def _exclusions_note(memo: MemoReport) -> str | None:
    """(b) Strict mode's one summary line, or ``None`` when nothing was excluded. Strict
    removes UNGROUNDED/UNCERTAIN findings before the memo is built, so the report's counts
    stand in for the per-finding lines ``_risky_note`` can no longer print."""
    unsupported = memo.overall.grounding_excluded_unsupported
    unsure = memo.overall.grounding_excluded_unsure
    if not unsupported and not unsure:
        return None
    return f"Excluded by grounding (strict): {unsupported} unsupported, {unsure} not sure"
```
Call `_risky_note` where `_wording_note` was called (Markdown and DOCX); render `_exclusions_note(memo)` as `lines.append(f"- {note}")` in Markdown and `doc.add_paragraph(note)` in DOCX, both after the summary table.
- [ ] **Step 4: Run to verify.** Run `uv run pytest tests/unit/review/ -q` — Expected: all pass, including `test_export_markdown_notes_only_the_grounded_absent_case` and `test_wording_fields_roundtrip`.
- [ ] **Step 5: Commit.**
```bash
git add src/openreview_cli/review/memo/ tests/unit/review/
git commit -m "feat(review): print the risky grounding patterns in both grounding modes

Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```
**Deliberate wrong implementation to catch:** printing a note for every clause — `test_an_ordinary_clause_renders_exactly_as_today` fails on a byte difference.

---

## Item 8: no chain-of-thought, and the measurement

**No chain-of-thought (review-only).** Verify no instruction asks the checker to reason step by step and that the two prompt surfaces ask closed questions with JSON answers only:
```bash
grep -rniE "step[- ]by[- ]step|chain of thought|think (this )?through|explain your reasoning|reason about" \
  src/openreview_cli/grounding src/openreview_cli/review/memo scripts/measure_slm_slots.py
```
Expected: no matches. Also confirm `GROUNDING_PROMPT_TEMPLATE`, `SECOND_PASS_PROMPT_TEMPLATE` and the miscited bullet carry no such phrasing, and state the paper's finding (chain-of-thought lowers the catch rate at a strict false-positive budget) as the reason. Separately, `grep -n "confidence" src/openreview_cli/grounding/discriminator.py` shows it only recorded/forwarded; the only colour use stays `review/colors.py`.

**The measurement task (one task).**
- Gate the rule for the arm: add `--require-pass-agreement` to `scripts/measure_slm_slots.py` (default off), a module-level `_REQUIRE_PASS_AGREEMENT`, and forward it from `_make_discriminator` (`CitationGroundingDiscriminator(mode="strict", output_dir=..., require_pass_agreement=_REQUIRE_PASS_AGREEMENT)`).
- Run the CI arm: push the branch and watch the `grounding-accuracy` job in `.github/workflows/slm-measurement.yml` (`:179`), which runs `--arm local --limit 20 --no-pii --corpus-dir corpus`; run it twice — as shipped (rule off) and with `--require-pass-agreement` — for the both-passes-vs-one comparison. Its fail-loud gate (`:448-551`) must pass on the new label set. `gh run download <run-id> -n grounding-accuracy-local` for the receipt.
- Re-pin both receipts: regenerate `docs/benchmarks/results/grounding-accuracy-local.json` (from the CI artifact) and `grounding-accuracy-cloud.json` (locally, `--arm cloud`), updating `git_commit`, `models`, the `provenance` sha256 for the five edited files (`scripts/measure_slm_slots.py`, `grounding/{corruption,presence,prompts,discriminator}.py`), the `sample`/`metrics` block, and the `notes`. Then `uv run pytest tests/unit/test_benchmark_receipts.py -q` → green apart from the known issue #180; `test_every_receipt_pins_its_producing_content` must pass.
- Update `docs/BENCHMARKS.md` §`## Grounding accuracy (local vs cloud)` (numbers and its `Last verified:` line) and `docs/benchmarks/results/slot-measurement.md:39`. Publish the honest before/after on the hint (item 1), on the two-pass rule (item 4), and the count of `miscited` answers naming a section that does not support the finding (item 3). **If the two-pass rule costs more good findings than it catches bad ones, publish that and leave it disabled by default** (design §3).
- The harness caveats (`GROUNDING_ACCURACY_CAVEATS`, `:85-104`) must still say the guard cannot prove non-entailment, and the receipt's `harness_notes` must name the two new negative kinds.

---

## Plan Self-Review

**Design coverage:**

| Design item | Task |
|---|---|
| (FIX 6) one field migration | Task 1 |
| 1 — the test tool asks the product's question | Task 2 |
| 2 — the bad sentences become genuinely bad (two sound kinds) | Task 3 |
| 7 — the sentence-aware ~2000-character window | Task 4 |
| 3 — sibling clauses + `miscited_to_clause_id` + non-downgrading guard | Task 5 |
| 4 — the second narrow question and the both-must-agree rule (off by default) | Task 6 |
| 5 — confidence a warning only | Task 7 |
| 6 — the memo's risky-pattern lines in both modes | Task 8 |
| 8 — no chain-of-thought; the measurement | the final section |

Every item maps to exactly one task; no task implements two items.

**FIX 8 status of the named tests:**
1. `test_model_override_passed_to_gateway` — updated to assert the override on every call, so the second pass must forward it.
2. `TestWordingAbsentHintReachesTheModel::test_only_the_absent_claims_line_carries_the_hint` — updated to read the **first** gateway call (`chat.call_args_list[0]`).
3. the hallucination label call — now passes `kind="hallucination"` (Task 3).
4. the tautological `or True` assertion — removed from `test_cross_document_kind_names_a_different_document` (Task 3).
5. the miscited sibling fixture — rewritten to `4.7 The receiving party shall keep … for five years after disclosure.` (measured `(1.0, False)`) so the guard accepts it (Task 5).
6. the second-pass window fixture — `"Sentence one is here. " * 100` (2200 chars) so it truncates (Task 6).
7. the oversized-first-sentence window contradiction — resolved: `_clause_window` hard-clips a first sentence longer than the window, and `test_a_single_oversized_first_sentence_is_hard_clipped` pins the bound (Task 4).

**FIX 10 anchors/counts:** `ground_claim` is `:69-128` (corrected from `:69-125`); the pinned label counts were computed by running the new builder over the fixtures and are quoted in Task 3, Step 4, not delegated to the implementer.

**FIX 2 (no placeholders) and the placeholder scan:** every test body is literal, runnable code that reuses the helper methods already present in each file (`TestGroundingPresenceRecorded._report`/`._source_clauses`, `_make_wording_note_memo`); none invents a helper that does not exist, and the previous draft's `...` bodies are gone. No "TBD"/"TODO"/"add error handling" anywhere.

**FIX 9 (size of the operand map):** the map carries only the operands the corpus reaches (Task 3), and operand substitution is stated plainly as new code.

**FIX 11 (size):** this plan replaces the 1258-line draft; the facts preamble is six anchors, reproduced helper docstrings are removed, and each task's "deliberate wrong implementation" is one line.

**Type consistency:** `presence.measure(...) -> tuple[float, bool]` (Tasks 2, 5, harness); `miscited_to_clause_id`/`pass_disagreement`/`not_sure` (Task 1 produces, 5/6 set, 8 consumes); `_clause_window(text, limit)` (Task 4 → Tasks 5/6); `_format_claim`/`_JSON_ONLY_TAIL` (Task 6, shared); `combine_grounding_passes(first, second, *, second_available=True)`, `require_pass_agreement=False`, `second_pass_fallbacks` (Task 6); `operand_change`/`ClauseUnit.document` (Task 3). `GroundingVerdict` keeps exactly three members; no task touches `review/colors.py`, `assign_colors`, the amber reasons, or the strict/lenient filtering.
