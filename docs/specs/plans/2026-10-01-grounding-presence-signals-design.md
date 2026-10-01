# Design (v2) — presence signals instead of a veto

- **Date:** 2026-10-01
- **Status:** supersedes `2026-10-01-grounding-citation-presence-design.md`, whose veto is **rejected** (§1). Awaiting owner approval of the four items in §2.
- **Branch:** `feat/grounding-presence-signals` (renamed from `fix/grounding-citation-veto`; nothing was ever committed), based on `feat/slm-measurement` at `5575e8e`.

Plain words, used with one meaning throughout: a **claim** is the text the review step grounds (in production,
`assessment.citation` — the extraction step is asked for an "exact quoted text from the clause"); the **clause** is
the numbered contract section the claim cites; **coverage** is the share of a claim's words found in that clause;
a **veto** is code that decides a claim without asking the model; the **harness** is
`scripts/measure_slm_slots.py`, which builds known-good and known-bad labels and scores the fact-checker.

## 1. Why the veto is rejected (measured 2026-10-01)

| claim | coverage | what the veto would do |
|---|---|---|
| the repo's live test claim that **must** come back grounded (`tests/integration/test_grounding_live.py:38`) | 0.750 | model decides (safe) |
| a light paraphrase (2 words changed) | 0.818 | model decides (safe) |
| a medium paraphrase (half reworded) | 0.455 | **vetoed → ungrounded** |
| a heavy paraphrase | 0.200 | **vetoed → ungrounded** |
| a genuine sentence from another clause | 0.154 | vetoed (correct) |

A supported claim and a planted bad claim occupy the same coverage range once the wording changes, so any line that
catches the second rejects some of the first. The consequence is silent: in the `strict` grounding mode the CLI
describes as "ungrounded excluded" (`src/openreview_cli/app.py:1378-1383`), a vetoed claim leaves the memo with
nothing to distinguish it from a claim the model rejected. Grounding is opt-in (`review/runner.py:169` runs it only
when a mode is supplied), which bounds the blast radius but does not remove the risk.

Decisive point: **the false-reject rate cannot be measured today.** No artifact records a claim next to the clause:
the local model's real review output (`slm-result-granite4-3b`) carries only aggregate counts, and the cloud
review output has the same shape. The harness cannot bound it either — its known-good labels are verbatim by
construction. Shipping a rule that can delete a real finding, whose error rate is unmeasured, is not defensible for
this product.

## 2. What ships instead — the four approved items

### Item 1 — record coverage as a number, decide nothing
- New scalar field `grounding_presence: float | None = None` beside the grounding fields in
  `ClauseAssessment` (`review/models.py:114-117`).
- Set in the merge that assigns the other grounding fields (`grounding/models.py:98-100`); the value rides on
  `GroundingResult`, which gains the same field, computed in `discriminator.py` at both call sites
  (`ground_claim` and `_process_batch`) where claim and clause text are both in hand.
- The number reaches the JSON output for free: reports are dumped whole through `dataclasses.asdict`
  (`review/report.py:308`), and no test asserts an exact assessment key set.
- Privacy: a number is recorded; no claim text and no clause text is added anywhere.

### Item 2 — sharpen the question, keep the model as the decider
- `build_grounding_messages` (`grounding/prompts.py:45-79`) gains an optional set of claim indices whose wording was
  not found in the cited clause, and appends one clause to **that claim's line**, for example
  `[the claim's wording is not in the clause; answer grounded only if the clause still entails it]`.
- The system template is untouched, so the two tests that pin its text (`tests/unit/test_grounding_prompts.py:135-141`)
  stay green. The verdict remains the model's; nothing is decided by code.

### Item 3 — a report-only line in the memo
- When `grounding_presence` is below the line, the memo prints a display-only note beside the clause's severity
  (`review/memo/formats.py:111-112` for Markdown, `:268-271` for DOCX), naming the coverage value.
- The colour logic reads only `error`, `confidence`, `qa_verdict` and `grounding_verdict`
  (`review/colors.py:41-53`), so a note cannot change amber or the three-colour output, and its tests are untouched.

### Item 4 — harden the label set
- No paraphrase machinery exists anywhere in the repo (searched `src/`, `scripts/`, `tests/`, fixtures), so a small
  deterministic one is written in `grounding/corruption.py`, in the style of the existing hash-seeded helpers.
- Two new label classes: a **paraphrased positive** (a meaning-preserving rewrite of a clause sentence, verified to
  be *different* from the clause so it is a real paraphrase) and a **paraphrased negative** (a paraphrase of a
  sentence from a different clause, so it stays unsupported).
- The substitution table is small, curated, and each entry is meaning-preserving; a test asserts the rewrite is not a
  substring of the clause and that it differs only by the table's entries. `GROUNDING_VALID_NEGATIVES`
  (`corruption.py:48`) gains the new negative class; every place that enumerates generator names must learn about it
  (`scripts/measure_slm_slots.py:382,386,389,393,519,521,751,753,759`), and the harness's own claims about verbatim
  positives (`:82-98`, `:754-764`) must be corrected.

### Item 5 — measure, then publish
- The harness records coverage per label so the distribution is visible in a receipt, and one real local review runs
  with grounding enabled so the numbers come from real extraction output rather than from harness labels.
- Publish: the coverage distribution, the new hardened-set numbers, and — plainly — that the local arm's remaining
  gap is a model property, not something code can close without the veto that was rejected.

## 3. Non-goals

- **No veto, and no verdict ever set from the coverage number.** The number may inform the question (item 2) and the
  memo (item 3); it never decides.
- No new slot, privacy tier or model default; no cloud run (the cloud row is labelled as measured before this change).
- No enforcement of verbatim quotations at the extraction step — a candidate long shot, recorded in §6, not built here.

## 4. Risks

| risk | mitigation, and what would prove it wrong |
|---|---|
| The paraphrase table under-represents real paraphrases, so the hardened set still flatters the model | keep the table curated and small; state the limit in the receipt and the page. It would be wrong to claim the set equals real extraction output |
| Item 2's hint biases the model rather than helping it | measure with and without; if the local arm's caught count does not move, the hint is not worth keeping |
| Item 3's line adds noise if the line misfires on legitimate paraphrases | it is display-only, so the cost is a wrong note, never a lost finding |
| The coverage number is misread as a verdict by a later reader | name it in the schema and the docs as a signal; the memo wording says "wording not found", not "unsupported" |

## 5. Definition of done

- Items 1–4 implemented with the interfaces above; a test per item, written first and watched to fail.
- The harness records coverage; one real local review with grounding enabled produces a coverage distribution.
- The published pages carry the distribution, the hardened-set numbers, and the explicit statement that the gain is
  not a model improvement; the cloud row is labelled as pre-change.
- The rejected veto is recorded as rejected, with the measurement that rejected it, so it is not re-proposed.

## 6. Alternatives considered

| alternative | why not |
|---|---|
| The hard veto | §1: silent deletion of real findings, with an unmeasurable error rate |
| Enforce verbatim citations at the extraction step, then veto safely | plausible long shot; a small model may loop on re-asks, and it is a larger change than this branch. Recorded, not built |
| Prompt-only improvement, no measurement | cannot be told apart from noise; item 1 exists precisely to make it measurable |

## 7. Open uncertainties

- Whether real citations sit above the line — the whole point of item 1, unanswered until a real review runs.
- Whether a curated substitution table is a fair proxy for real paraphrases (Assumption; it would be wrong in the
  direction of flattering the model).
