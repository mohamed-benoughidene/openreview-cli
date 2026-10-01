# Grounding Presence Signals — Implementation Plan (v3)

> **For agentic workers:** Use tasks as checkboxes (`- [ ]`) for tracking.

**Goal:** Record how much of each claim's wording appears in the clause it cites, tell the model when it does not, note that in the memo when the model accepted such a claim, and harden the measurement labels with paraphrases — with no code path ever setting a verdict from the number.

**Architecture:** `presence.py` computes the number and one boolean; the batch path records them on the grounding result and the assessment; the prompt builder appends a per-claim hint; the memo prints a display-only line for the one risky pattern; the harness label builder gains two paraphrase classes.

**Tech stack:** Python 3.12, pytest, `uv`, standard library only.

**Design:** `docs/specs/plans/2026-10-01-grounding-presence-signals-design.md` (v3). Read §1 first — the rejected veto is the constraint every task works under — and §2 for the corrected mechanisms.

## Global Constraints

- **Worktree:** `/home/mohamed/lab/openreview/.worktrees/grounding-presence-signals`, branch `feat/grounding-presence-signals`, based on `feat/slm-measurement` at `5575e8e`. Never commit to `main`.
- **Python 3.12 and `uv` only.** No new dependency.
- **TDD:** failing test first, watched failing, then code.
- **Privacy:** numbers, booleans and counts only — never a claim or clause text in a receipt, log or metric.
- **Do not change `ground_claim`'s signature** (three callers destructure its tuple) and **do not change `GROUNDING_PROMPT_TEMPLATE`** (two tests pin it).
- **Do not change `corruption.py`'s substring guard** — `coverage(...) < 1.0` is not the same test, and swapping them would silently drop more negatives.
- **No verdict may be derived from the coverage number.**
- **`uv run pre-commit run --all-files` must pass** before each commit; messages end with `Co-authored-by: CommandCodeBot <noreply@commandcode.ai>`.
- **Confirm every cited line number before editing**; report any anchor that has moved.

---

### Task 1: The presence primitive

**Files:** create `src/openreview_cli/grounding/presence.py`; create `tests/unit/test_grounding_presence.py`; modify `src/openreview_cli/grounding/corruption.py` (import `normalise` only — its substring guard stays).

**Interfaces:**
- `normalise(text) -> str`; `coverage(claim, clause) -> float`; `measure(claim, clause) -> tuple[float, bool]` returning the number and `wording_absent`. The boolean is `False` when the clause text is empty, the claim has fewer than five tokens, or the claim is only a reference (`^v?\d+(?:\.\d+)*$`). The threshold lives inside the module and is not part of the public surface.

- [ ] **Step 1: Write the tests** — a verbatim quote scores 1.0 and is not absent; a sentence from another clause scores below the threshold and is absent; case and whitespace do not matter; a long clause does not dilute a short quote; an empty clause, a `<5`-token claim and a reference-like claim are never absent; `measure` returns both values consistently.
- [ ] **Step 2: Run them** — `uv run pytest tests/unit/test_grounding_presence.py -q` → `ModuleNotFoundError`.
- [ ] **Step 3: Write the module** (normalise, `[a-z0-9]+` tokens, multiset intersection over claim tokens, `measure` with the three guards).
- [ ] **Step 4: Run them again** → all pass.
- [ ] **Step 5: Let `corruption.py` reuse `normalise`** (and nothing else); its `is_genuine_negative` substring test is untouched.
- [ ] **Step 6: Prove the guard is unchanged** — `uv run pytest tests/unit/test_grounding_corruption.py tests/unit/test_grounding_presence.py -q` → all pass, including the exact-tuple test at `:296`.
- [ ] **Step 7: Commit** — `feat(grounding): add a coverage measure with a wording-absent guard`.

---

### Task 2: Record the number and the boolean on the batch path (item 1)

**Files:** modify `src/openreview_cli/grounding/discriminator.py` (`GroundingResult` is built in the zero-length block `:190-200` (construction `:193-198`), the gateway-error fallback `:280-281` and the batch mapping `:367-368`; confirm them, because Task 2 shifted these lines and the earlier draft cited the empty-report early return by mistake), `src/openreview_cli/grounding/models.py` (`:76`, `:98-100`), `src/openreview_cli/review/models.py` (`:114-117`); tests in `tests/unit/test_grounding_discriminator.py`, `tests/unit/test_grounding_models.py`, `tests/unit/test_review_report.py`.

**Interfaces:** `GroundingResult.grounding_presence: float | None = None`, `GroundingResult.wording_absent: bool = False`, and the same two fields on `ClauseAssessment`; the merge copies them. The zero-length-claim result carries `None`/`False` — the measure never ran.

- [ ] **Step 1: Write the failing tests** — a grounded claim carries a number and possibly `wording_absent`; an ungrounded one does too; a zero-length claim carries `None`/`False`; the merge puts both on the assessment; the report JSON carries both and **no claim or clause text**.
- [ ] **Step 2: Run them** → fail on the missing fields.
- [ ] **Step 3: Implement** with `presence.measure` called once per claim where clause text is in hand, so the number and the hint share one computation.
- [ ] **Step 4: Run the three files** → all pass.
- [ ] **Step 5: Commit** — `feat(grounding): record claim coverage and the wording-absent flag`.

---

### Task 3: The per-claim hint (item 2)

**Files:** modify `src/openreview_cli/grounding/prompts.py` (`build_grounding_messages`, `:45-79`), `src/openreview_cli/grounding/discriminator.py` (pass the flag set); tests in `tests/unit/test_grounding_prompts.py`, `tests/unit/test_grounding_discriminator.py`.

**Interfaces:** `build_grounding_messages(source_clauses, claims, wording_absent_indices: set[int] | None = None)`. Default `None` leaves every existing caller unchanged. The hint is one bracketed clause appended to that claim's line in the single user message; `GROUNDING_PROMPT_TEMPLATE` is untouched.

- [ ] **Step 1: Write the failing tests** — a flagged claim's line carries the hint, an unflagged one does not, an empty set adds nothing, and the two template-pinning tests at `tests/unit/test_grounding_prompts.py:135-141` still pass.
- [ ] **Step 2: Run them** → hint absent.
- [ ] **Step 3: Implement** the parameter and the call-site pass-through.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_grounding_prompts.py tests/unit/test_grounding_discriminator.py -q` → all pass.
- [ ] **Step 5: Commit** — `feat(grounding): tell the model when a claim's wording is absent from the clause`.

---

### Task 4: The memo note, on the risky pattern only (item 3)

**Files:** modify `src/openreview_cli/review/memo/models.py` (`MemoClause`, `:48-61`, and its `from_dict`), `src/openreview_cli/review/memo/exporter.py` (`:106-118`), `src/openreview_cli/review/memo/formats.py` (Markdown near `:104-125`, DOCX near `:236-275`); tests: the memo Markdown tests, the memo DOCX tests (**name them explicitly**), plus `tests/unit/test_three_color_models.py` and `tests/unit/test_three_color_report.py`.

**Interfaces:** `MemoClause.grounding_presence: float | None` and `MemoClause.wording_absent: bool`, set in the builder. The note renders as its own line, only when `wording_absent` **and** the assessment's `grounding_verdict` is `GROUNDED`.

- [ ] **Step 1: Write the failing tests** — the note appears for a grounded claim with absent wording; it does **not** appear for a grounded claim with present wording, for an ungrounded claim, or when the fields are `None`/`False`; the DOCX renderer emits the same text; the three-colour output is unchanged with and without the note.
- [ ] **Step 2: Run them** → the note is absent (and the DOCX test fails for the same reason).
- [ ] **Step 3: Implement** both renderers and the builder field.
- [ ] **Step 4: Run** the memo tests plus the three-colour tests → all pass.
- [ ] **Step 5: Commit** — `feat(review): note a claim accepted despite absent wording`.

---

### Task 5: Paraphrased labels (item 4)

**Files:** modify `src/openreview_cli/grounding/corruption.py` (one constant substitution map plus `paraphrase(sentence)`), `scripts/measure_slm_slots.py` (`GROUNDING_VALID_NEGATIVES`, `_build_grounding_labels` at `:357-394`, the caveats at `:82-98` and `:754-764`); tests in `tests/unit/test_grounding_corruption.py`, `tests/unit/test_grounding_harness.py`.

**Interfaces:** `paraphrase(sentence) -> str` (never `None`; a narrow, reviewed map — `shall`→`must`, `shall not`→`must not`, `in no event`→`under no circumstances`, `prior to`→`before`, `receiving party`→`recipient`); `paraphrased_supported(unit)` uses the clause's own qualifying sentence; `paraphrased_unsupported(a, b)` paraphrases a sentence from another clause. The new negative name joins `GROUNDING_VALID_NEGATIVES`; the positive does not. Only labels whose rewrite actually differs are kept, and the ones dropped are counted.

- [ ] **Step 1: Write the failing tests** — the rewrite differs from the clause sentence and is not a substring of it; `is_genuine_negative` passes for the unsupported variant and fails for the supported one; an unchanged rewrite yields no label and increments a drop counter; the harness builds and counts both classes. **This task must also update the tests that pin today's exact numbers**: `tests/unit/test_grounding_harness.py` asserts `positives == 2`, `negatives_kept == 2`, `negatives_dropped_guard == 2`, the generator dict, `len(per_label) == 4`, the generator set, the stub call count, and at `:233` that a caveat contains "verbatim" — all of these change, so recompute each expected value from the new label set and report the new numbers; and `tests/unit/test_grounding_corruption.py:296` pins the negative tuple exactly.
- [ ] **Step 2: Run them** → new classes missing, and the pinned counts fail.
- [ ] **Step 3: Implement** the map, the writers, the label wiring, the caveat correction, and the test updates.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_grounding_corruption.py tests/unit/test_grounding_harness.py -q` → all pass.
- [ ] **Step 5: Commit** — `test(grounding): add paraphrased labels so wording, not quoting, is measured`.

**Note for the implementer:** per-generator *positive* counts do not exist today (the counter dicts key off the negative tuple). Do not invent them; if the receipt needs them, say so in the report instead of widening the change.

---

### Task 6: Measure, then publish — two tasks in practice

**Files:** `scripts/measure_slm_slots.py` (a `coverage` field per `per_label` row), `docs/benchmarks/results/grounding-accuracy-local.json`, `docs/BENCHMARKS.md`, `docs/benchmarks/results/slot-measurement.md`.

- [ ] **Step 1: Offline suite and gate** — `uv run pytest -m "fast" -q`, `uv run pre-commit run --all-files`. Expected: only the known issue #180 receipt failure.
- [ ] **Step 2: Record coverage in the harness output** — add the number to each `per_label` row (the harness computes it with `presence.measure`; the harness may import the product). Run the local arm and report the coverage distribution by label class.
- [ ] **Step 3: The pilot** — one real local review with grounding left at its CLI default, recording the coverage distribution (a sample, not a benchmark). This is the only thing that can answer design §7.
- [ ] **Step 4: Regenerate the registered receipt** — rebuild `grounding-accuracy-local.json` with the new class counts, the corrected `git_commit`, re-pinned sha256 provenance, and no duplicate `bad_called_grounded` field (it contradicts `bad_missed`). Then `uv run pytest tests/unit/test_benchmark_receipts.py -q` → only the known #180 failure.
- [ ] **Step 5: Publish** — the local arm's "bad claims called grounded" row is **12**, not 0; replace the local numbers; label the cloud row as measured before this change; print the coverage distribution and the pilot's numbers; state that nothing here is a model improvement.
- [ ] **Step 6: Commit and push.**

---

## Plan Self-Review

**Design coverage** — items 1–4 map to Tasks 1–5, and "measure before deciding" to Task 6 (Steps 2–3 measure, 4–5 publish, kept separate so a measurement is not mixed with edits). The rejected veto appears in no task.

**Placeholder scan** — Task 5 names the tests whose pinned numbers change and requires the implementer to recompute and report them, because those values follow from the new label set and cannot be quoted in advance. Everything else carries its anchor, command and expected result.

**Type consistency** — `measure` returns `(float, bool)`; the fields are `float | None` and `bool` on both the grounding result and the assessment; the hint parameter is an optional set of indices; every default preserves today's behaviour.

**Review record** — v3 folds in 28 findings from two independent reviews: the memo path was missing two files, `ground_claim` builds no `GroundingResult`, the guard swap would have changed label meaning, the harness tests pin exact counts, the design's §1 evidence was unreproducible, and the CLI default made the original risk larger than v2 stated.
