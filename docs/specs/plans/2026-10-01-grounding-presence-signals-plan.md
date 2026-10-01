# Grounding Presence Signals — Implementation Plan

> **For agentic workers:** Use tasks as checkboxes (`- [ ]`) for tracking.

**Goal:** Record how much of each claim's wording appears in the clause it cites, ask the model a sharper question when little of it does, surface that in the memo as a note, and harden the measurement labels with paraphrases — without any code path ever setting a verdict from that number.

**Architecture:** A product-owned scoring module computes coverage; the discriminator attaches it to each grounding result and passes a per-claim hint to the prompt builder; the memo renders a display-only line when coverage is low; the harness gains paraphrased label classes so its numbers mean more.

**Tech Stack:** Python 3.12, pytest, `uv`. Standard library only.

**Design:** `docs/specs/plans/2026-10-01-grounding-presence-signals-design.md` in this worktree. Read §1 first: it records why a code veto was rejected, and that rejection is a constraint on every task below.

## Global Constraints

- **Branch:** `feat/grounding-presence-signals` in `/home/mohamed/lab/openreview/.worktrees/grounding-citation-veto`, based on `feat/slm-measurement` at `5575e8e`. Never commit to `main`.
- **Python 3.12 and `uv` only.** No new dependency.
- **TDD:** failing test first, watched failing, then code.
- **Privacy:** numbers, band names and counts only. Never place a claim or clause text into a receipt, a log, or a metric.
- **The test-pinned prompt template must not change** (`tests/unit/test_grounding_prompts.py:135-141`). Item 2 edits the per-claim user line only.
- **No verdict may be derived from the coverage number.** If a task tempts you to skip or force a model call, stop.
- **The product must not import `grounding/corruption.py`** (harness-owned by its docstring).
- **`uv run pre-commit run --all-files` must pass** before each commit; messages end with `Co-authored-by: CommandCodeBot <noreply@commandcode.ai>`.
- **Confirm every cited line number before editing** and report any anchor that has moved.

---

### Task 1: The coverage primitive

**Files:** create `src/openreview_cli/grounding/presence.py`; create `tests/unit/test_grounding_presence.py`; modify `src/openreview_cli/grounding/corruption.py` (delegate, keeping meaning).

**Interfaces:**
- Produces `normalise(text) -> str`; `coverage(claim_text, clause_text) -> float` (share of the *claim's* tokens found in the clause, multiset); `LOW_COVERAGE = 0.65`; `is_low(claim_text, clause_text) -> bool` which is `False` when the clause is empty, the claim has fewer than five tokens, or the claim looks like a reference such as `4.3`.
- Consumes in `corruption.py`: `normalise` for `_normalize_for_guard`, and `coverage(...) < 1.0` in place of its substring test, so the guard's meaning is unchanged and `tests/unit/test_grounding_corruption.py` stays green.

- [ ] **Step 1: Write the tests** — `tests/unit/test_grounding_presence.py`: a verbatim quote scores 1.0; a sentence from another clause scores below `LOW_COVERAGE`; case and whitespace do not matter; a long clause does not dilute a short quote; an empty clause and a reference-like claim are never "low"; the constant is pinned at `0.65`.
- [ ] **Step 2: Run them** — `uv run pytest tests/unit/test_grounding_presence.py -q` → `ModuleNotFoundError` for the new module.
- [ ] **Step 3: Write the module** with the code in the design §2 item 1: normalise, tokenise with `[a-z0-9]+`, multiset intersection over claim tokens, and `is_low` carrying the three guards.
- [ ] **Step 4: Run them again** → all pass.
- [ ] **Step 5: Make `corruption.py` delegate** to `normalise` and `coverage`; update its module docstring to say the primitive now lives in `presence.py`.
- [ ] **Step 6: Prove no meaning changed** — `uv run pytest tests/unit/test_grounding_corruption.py tests/unit/test_grounding_presence.py -q` → all pass.
- [ ] **Step 7: Commit** — `feat(grounding): add a coverage primitive with a low-coverage guard`.

---

### Task 2: Record coverage on every grounding result (item 1)

**Files:** modify `src/openreview_cli/grounding/discriminator.py` (`GroundingResult`, `ground_claim`, `_process_batch`), `src/openreview_cli/grounding/models.py` (the merge at `:98-100`), `src/openreview_cli/review/models.py` (the field at `:114-117`); tests in `tests/unit/test_grounding_discriminator.py`, `tests/unit/test_grounding_models.py`, `tests/unit/test_review_report.py`.

**Interfaces:**
- Produces `GroundingResult.grounding_presence: float | None = None` and `ClauseAssessment.grounding_presence: float | None = None`; the merge copies one to the other.
- The number is recorded for **every** grounded and ungrounded claim, whatever the model decided; it is `None` only when there is no clause text to measure against.

- [ ] **Step 1: Write the failing tests** — a grounded claim carries the computed coverage; an ungrounded one does too; a claim with no clause text carries `None`; the assessment produced by the merge carries it; the report JSON (`tests/unit/test_review_report.py`) contains the field and **no claim or clause text**.
- [ ] **Step 2: Run them** → fail on the missing field.
- [ ] **Step 3: Implement** — compute coverage in both call sites, carry it on `GroundingResult`, copy it in `CGReport.merge_into` (`grounding/models.py:76,98-100`), add the field to `ClauseAssessment`.
- [ ] **Step 4: Run the three test files** → all pass. Confirm the JSON dump needs no change (reports are dumped whole via `dataclasses.asdict`, `review/report.py:308`).
- [ ] **Step 5: Commit** — `feat(grounding): record claim coverage on every grounding result`.

---

### Task 3: Ask a sharper question when little of the claim is in the clause (item 2)

**Files:** modify `src/openreview_cli/grounding/prompts.py` (`build_grounding_messages`), `src/openreview_cli/grounding/discriminator.py` (pass the flags); tests in `tests/unit/test_grounding_prompts.py`, `tests/unit/test_grounding_discriminator.py`.

**Interfaces:**
- `build_grounding_messages(source_clauses, claims, low_coverage_indices: set[int] | None = None)`. Default `None` keeps every existing caller and test behaving exactly as today.
- The hint is appended to that claim's own line; the system template is untouched.

- [ ] **Step 1: Write the failing tests** — a flagged claim's line carries the hint and an unflagged one does not; the hint names neither claim nor clause text beyond what the caller already sends; the two template-pinning tests still pass unchanged; the discriminator passes the flags for exactly the claims whose wording is missing.
- [ ] **Step 2: Run them** → the hint is absent.
- [ ] **Step 3: Implement** the optional parameter and the call-site flags.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_grounding_prompts.py tests/unit/test_grounding_discriminator.py -q` → all pass.
- [ ] **Step 5: Commit** — `feat(grounding): tell the model when a claim's wording is absent from the clause`.

---

### Task 4: Surface it in the memo, without touching a verdict (item 3)

**Files:** modify `src/openreview_cli/review/memo/formats.py` (Markdown `:111-112`, DOCX `:268-271`); tests in `tests/unit/test_grounding_report.py` or the memo tests beside them, plus a check that the colour tests are untouched.

**Interfaces:**
- A display-only note, rendered only when `grounding_presence` is not `None` and below `presence.LOW_COVERAGE`. Wording states the fact, not a verdict: for example `Citation wording not found in the cited clause (coverage 0.31)`.

- [ ] **Step 1: Write the failing tests** — the note appears for a low-coverage assessment, is absent for a high-coverage one and for `None`, and the three-colour output is byte-identical with and without it.
- [ ] **Step 2: Run them** → the note is absent.
- [ ] **Step 3: Implement** the note in both memo formats.
- [ ] **Step 4: Run** the memo tests plus `tests/unit/test_three_color_models.py tests/unit/test_three_color_report.py` → all pass.
- [ ] **Step 5: Commit** — `feat(review): note when a claim's wording is absent from its clause`.

---

### Task 5: Harden the label set with paraphrases (item 4)

**Files:** modify `src/openreview_cli/grounding/corruption.py` (a curated substitution table plus two builders), `scripts/measure_slm_slots.py` (`_build_grounding_labels` at `:357-394`, the counters and the receipt fields at `:382,386,389,393,519,521,751,753,759`, the claims about verbatim positives at `:82-98,754-764`); tests in `tests/unit/test_grounding_corruption.py`, `tests/unit/test_grounding_harness.py`.

**Interfaces:**
- `paraphrase_supported(clause_unit) -> str | None`: a meaning-preserving rewrite of the clause's first qualifying sentence, or `None` when no table entry applies.
- `paraphrase_unsupported(clause_a, clause_b) -> str | None`: the same rewrite applied to a sentence taken from `clause_b`, so the result is still unsupported by `clause_a`.
- `GROUNDING_VALID_NEGATIVES` gains `paraphrase_unsupported`; a new positive class `paraphrase_supported` is added to the label set (it is a positive, so it must **not** go into that tuple).

- [ ] **Step 1: Write the failing tests** — the rewrite differs from the clause and is not a substring of it (so it is a real paraphrase); it is still meaning-preserving, asserted entry by entry against the curated table; the unsupported variant passes `is_genuine_negative`; the harness builds both new classes and counts them per generator; the receipt enumerates the new names; the caveat text no longer claims all positives are verbatim.
- [ ] **Step 2: Run them** → new classes missing.
- [ ] **Step 3: Implement** the table and the two builders, wire them into `_build_grounding_labels`, extend the counters and the receipt field lists, and correct the caveats.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_grounding_corruption.py tests/unit/test_grounding_harness.py -q` → all pass.
- [ ] **Step 5: Commit** — `test(grounding): add paraphrased labels so the harness measures wording, not quotes`.

---

### Task 6: Measure with grounding on, then publish

**Files:** modify `docs/benchmarks/results/grounding-accuracy-local.json` (regenerate + re-pin), `docs/BENCHMARKS.md`, `docs/benchmarks/results/slot-measurement.md`.

- [ ] **Step 1: Offline suite and gate** — `uv run pytest -m "fast" -q`, then `uv run pre-commit run --all-files`. Expected: the known issue #180 failure only.
- [ ] **Step 2: Measure both things** — the harness arm (labels, now including paraphrases) and **one real local review with grounding enabled**, which is the only way to learn whether real citations sit above the line. Record the coverage distribution for both.
- [ ] **Step 3: Regenerate the registered receipt** — rebuild `grounding-accuracy-local.json` from the run: new counts per class, `git_commit`, re-pinned sha256 provenance, and keep the duplicate `bad_called_grounded` field out (it contradicts `bad_missed`). Then `uv run pytest tests/unit/test_benchmark_receipts.py -q` → only the known #180 failure.
- [ ] **Step 4: Correct the pages** — the local arm's "bad claims called grounded" row is **12**, not 0; replace the local numbers with the new ones; label the cloud row as measured before this change; publish the coverage distribution; and state plainly that any gain is a wording check plus a sharper question, never a code verdict.
- [ ] **Step 5: Commit and push.**

---

## Plan Self-Review

**Design coverage** — items 1–4 map to Tasks 1–5, and the "measure, then decide" instruction maps to Task 6. The rejected veto appears in no task, and Task 2's interface note forbids deriving a verdict from the number.

**Placeholder scan** — the paraphrase table's entries are described rather than quoted because each entry must be chosen and justified individually against the real clause text; the task says so and requires a per-entry test. Everything else carries its file, anchor, command and expected result.

**Type consistency** — `coverage` returns `float`, `is_low` a `bool`, the field is `float | None` on both `GroundingResult` and `ClauseAssessment`, the hint parameter is an optional set of indices, and every default preserves today's behaviour for existing callers.

**Known limit carried from the design** — a curated table cannot represent the space of real paraphrases, so the hardened labels are harder than verbatim ones but still easier than production. The receipt and the published page must say so.
