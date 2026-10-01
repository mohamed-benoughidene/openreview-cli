# Design (v3) — presence signals instead of a veto

- **Date:** 2026-10-01
- **Status:** v3 folds in two independent reviews (28 findings). It supersedes v2; the veto remains **rejected**.
- **Branch:** `feat/grounding-presence-signals`, worktree `/home/mohamed/lab/openreview/.worktrees/grounding-presence-signals`, based on `feat/slm-measurement` at `5575e8e`.

Words used with one meaning throughout: a **claim** is the text the review step grounds (in production
`assessment.citation`); the **clause** is the contract section the claim cites; **coverage** is the share of a
claim's words found in the clause, computed by `presence.coverage`; a **veto** is code that decides a claim without
the model; the **harness** is `scripts/measure_slm_slots.py`.

## 1. Why the veto is rejected — corrected evidence

**The consequence is worse than v2 claimed.** The CLI runs grounding by default: `grounding_mode` defaults to
`"strict"` (`src/openreview_cli/app.py:1379`). In strict mode an ungrounded claim is **deleted** from the report —
`report.assessments = [a for i, a in enumerate(report.assessments) if i in keep_set]`, keeping only grounded
verdicts (`src/openreview_cli/grounding/models.py:117-122`). So a wrong call removes a real finding **by default**,
and nothing remains to show why. (v2 said "opt-in with a silent deletion"; the CLI default makes it
default-on.)

**And the coverage ranges overlap.** All figures below are reproducible with `presence.coverage` — case-folded,
whitespace-collapsed, tokenised by `[a-z0-9]+`, multiset, claim-side:

| source | coverage |
|---|---|
| the harness's 40 planted bad claims (real sentences from other clauses) | **0.000 – 0.689, median 0.260** |
| the repo's live test claim that must come back grounded (`tests/integration/test_grounding_live.py:38`) | 0.750 |
| light paraphrase — `"Each party must keep the other party's confidential information secret."` (11 tokens) | 0.818 |
| medium paraphrase — `"Neither party may reveal confidential details belonging to the other side."` (11 tokens) | 0.455 |
| heavy paraphrase — `"No party is permitted to reveal private data they receive."` (10 tokens) | 0.200 |

The planted claims reach 0.689 and the supported paraphrases start at 0.200, so **any single line either misses
planted claims or rejects real ones**. A line at 0.65 would reject the medium and heavy paraphrases; a line low
enough to catch the planted claims at 0.26 would reject most paraphrases.

**What remains unproven, stated plainly:** these are harness labels, not real citations. No artifact records a claim
beside its clause — the local model's real review output (`slm-result-granite4-3b`) carries only aggregate counts —
so the error rate of any line on *real* extraction output is unknown. What would overturn this rejection: real
citations clustering above ~0.8 while planted claims stay below ~0.3.

## 2. What ships — the four approved items

### Item 1 — record coverage, decide nothing
- `presence.coverage(claim, clause) -> float` and `presence.measure(claim, clause) -> tuple[float, bool]` returning the
  number and `wording_absent`. The threshold is **0.5** — a majority of the claim's wording missing — chosen by the
  implementer because the design named no value, recorded here so the document and the code agree, and deliberately
  kept private: it drives a note and a hint, never a verdict. The boolean also carries the guards: no clause text, a
  claim under five tokens, or a claim that is only a reference such as `4.3`, all return `False`.
- Only the batch path builds a `GroundingResult` (`_process_batch`); `ground_claim` returns a
  `(verdict, provenances, confidence)` tuple whose shape three callers destructure
  (`scripts/measure_slm_slots.py`, `benchmark/hallu_detect.py`, its own tests), so **its signature does not change**.
  `GroundingResult` gains `grounding_presence: float | None` and `wording_absent: bool`; `ClauseAssessment` gains the
  same two beside its other grounding fields (`review/models.py:114-117`), copied by `CGReport.merge_into`
  (`grounding/models.py:98-100`). The zero-length-claim result (`discriminator.py:153-163`) carries `None` and
  `False` — the check never ran.
- Reports are dumped whole through `dataclasses.asdict` (`review/report.py:308`), so the numbers reach the JSON with
  no further work; no test asserts an exact key set.
- Privacy: numbers and one boolean only.

### Item 2 — tell the model when the wording is absent, then let it decide
- `build_grounding_messages` gains an optional `wording_absent_indices: set[int] | None = None` and appends one
  clause to **that claim's line** in the single user message: `[the claim's wording does not appear in the cited
  clause; answer grounded only if the clause still entails it]`.
- There is **no system message** (`prompts.py:79` returns one `{"role": "user"}` message), so v2's phrase "the system
  template is untouched" is corrected to "`GROUNDING_PROMPT_TEMPLATE` is untouched". The two tests that pin it
  (`tests/unit/test_grounding_prompts.py:135-141`) stay green because the hint is per-claim.
- Why per-claim rather than one global sentence: a global sentence would assert something false about claims whose
  wording *is* present, which is most of them. The hint is true only where it is printed.

### Item 3 — a report-only line in the memo, on the risky pattern only
- The note prints **only when the model accepted the claim and the wording is absent** — the one combination worth a
  human's attention. It renders as its own line, not beside "Severity" (which is never populated on export, so v2's
  instruction would have been dead code), in Markdown (`review/memo/formats.py:104-125`) and DOCX (`:236-275`). It
  reads as a fact, never a verdict: `Citation wording not present in the cited clause (coverage 0.46)`.
- This needs `grounding_presence` and `wording_absent` on `MemoClause` and its builder
  (`review/memo/models.py:48-61`, `review/memo/exporter.py:106-118`) — v2 missed both files.
- The colour logic reads `error`, `confidence`, `qa_verdict`, `grounding_verdict`, `position` and
  `grounding_confidence` (`review/colors.py:41-68`); none of the new fields is among them, so amber cannot move.

### Item 4 — harden the labels with paraphrases
- One constant substitution map in `grounding/corruption.py` applied to any sentence: safe, narrow rewrites only
  (`shall` → `must`, `shall not` → `must not`, `in no event` → `under no circumstances`, `prior to` → `before`,
  `receiving party` → `recipient`, and similar). No per-clause curation, no `None` branch: `paraphrase(sentence)`
  always returns a sentence, and the caller drops it when the rewrite changed nothing (counted, never silent).
- Two classes: a **paraphrased positive** (the clause's own sentence rewritten) and a **paraphrased negative** (a
  sentence from another clause rewritten, so it stays unsupported). The negative joins
  `GROUNDING_VALID_NEGATIVES` (`corruption.py:48`); the positive is a positive and must not.
- Narrow map = honest limit: it under-represents real paraphrases, and the page must say so.
- Reuse considered and rejected in writing: `benchmark/hallu_detect.py` already computes a per-claim overlap
  (`:65-77`) but it imports the discriminator, so grounding importing it would close a cycle; a local primitive
  avoids that. Recorded in §6.

## 3. Non-goals
No veto and no verdict derived from coverage. No new slot, tier or model default. No cloud run (the cloud row is
labelled pre-change). No verbatim enforcement at the extraction step (recorded in §6, not built).

## 4. Risks

| risk | mitigation, and what would prove it wrong |
|---|---|
| The narrow substitution map flatters the model | state the limit in the receipt and the page; it would be wrong to claim the set equals real extraction output |
| Item 2's hint biases instead of helping | measure with and without; if the caught count does not move, drop it |
| Item 3's note fires on a real finding the model accepted | it is display-only, so the cost is a wrong note, never a lost finding — and the note states the coverage number so a human can judge |
| The number is misread as a verdict by a later reader | the field is named and documented as a signal, and the memo wording says "not present", not "unsupported" |

## 5. Definition of done
Items 1–4 implemented with a failing test first per item; the harness records coverage per label and the labels
include both paraphrase classes; one real local review with grounding enabled produces a coverage distribution
(called a pilot, not a benchmark); the published pages carry that distribution, the new numbers, the correction that
the local arm's "bad claims called grounded" row is 12 not 0, and the explicit statement that nothing here is a model
improvement; the rejected veto is recorded with the measurement that rejected it.

## 6. Alternatives considered

| alternative | why not |
|---|---|
| The hard veto | §1: overlapping ranges, and a default-on deletion with an unmeasured error rate |
| One global sentence in the prompt instead of a per-claim hint | it would assert something false about claims whose wording is present |
| Reusing `benchmark/hallu_detect.py`'s overlap metric | circular import (that module imports the discriminator) |
| Enforce verbatim citations at extraction, then veto safely | plausible long shot; a small model may loop on re-asks; larger than this branch |
| Drop the memo note, keep the JSON number only | the risky pattern (accepted despite absent wording) would stay invisible to the reviewer who acts on the memo |

## 7. Open uncertainties
- Whether real citations sit above the line: the point of item 1, unanswered until a real review runs.
- Whether a narrow map is a fair proxy for real paraphrases: labelled an Assumption; it errs toward flattering.
