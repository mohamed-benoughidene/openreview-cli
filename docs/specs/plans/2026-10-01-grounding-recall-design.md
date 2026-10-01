# Design — raising the fact-checker's catch rate (grounding recall)

- **Date:** 2026-10-01
- **Branch/worktree:** `feat/grounding-recall` in `.worktrees/grounding-recall`, based on `feat/slm-measurement` at `147b98b`.
- **Owner decisions this design implements (all four as recommended):** accept only when both passes agree; flag a "real but wrongly cited" finding and name the right section (never edit the document); a sentence-aware window of about 2000 characters; memo shows only the risky patterns.

Words with one meaning throughout: **finding** = a sentence the review extracted; **clause** = the numbered section of the contract; **the checker** = the local model that decides whether the clause supports the finding; **pass** = one question asked of the checker; **catch** = the checker correctly says "not supported"; **miss** = it wrongly says "supported"; **test tool** = `scripts/measure_slm_slots.py`.

## 0. What this fixes, and what the evidence is

The recorded runs and the audit behind every number are in the (gitignored) `draft/fact-checker-recall-solution-2026-10-01.md`. In short: the reported miss rate (12 of 45 bad items) is really **5 of 45**, because 6 of the 12 "misses" were the test tool's fault (its bad sentence was genuinely supported by the cited clause) and 1 was undecidable. The 5 real ones are two wrongly-cited findings, two that claim more than the clause allows, and one different proposition. Three measurement or presentation defects sit on top: the test tool asks a **different question** from the product (it omits the wording-absent hint), the test tool's bad sentences are **not reliably bad**, and in the default setting an "not supported" or "not sure" finding is **deleted quietly** while a merely asserted one prints green.

## 1. The eight items

### Item 1 — the test tool asks the product's question
`CitationGroundingDiscriminator.ground_claim` (the single-finding entry point the test tool calls) builds its messages with no hint, while the batch path passes one. It already has the finding text and the clause text, so it computes the absence itself with `grounding/presence.py`'s `measure` — **no signature change**, and both paths derive the hint from one primitive.
- Must not: change the verdict logic; the hint is text only.
- Note: this also gives the other calling benchmark (`benchmark/hallu_detect.py`) the same question as the product, which is the point.

### Item 2 — the test tool's bad sentences become genuinely bad
`grounding/corruption.py` builds `unsupported_claim` from the **adjacent** clause, which in near-identical contracts is often supported by the cited clause. Replace the construction with two sound kinds:
1. **operand change** — a sentence of the *cited* clause with a number, date or party changed (the pattern `hallucination` already uses). A changed operand cannot be supported by that clause.
2. **cross-document** — a sentence drawn from a clause of an **unrelated** contract (different topic), with the source document recorded.
Keep the generator's name and the label counts; record which kind produced each row. `paraphrased_unsupported` draws from the same two sound sources.
- Must not: claim soundness it cannot prove. A guard can prove the operand changed and the source document differs; it cannot prove non-entailment, and the receipt's caveat must keep saying so.
- The honest consequence: the numbers will get **worse** (fewer false misses), and that is the point.

### Item 3 — sibling sections, and "real but wrongly cited"
The prompt today shows only the cited clauses' first 500 characters, so a finding that is true but cited to the wrong section is unanswerable. Change: show the document's other clauses too (the full list already arrives at the batch path — `review/runner.py:177`; bound how many and window each one, item 7), and add a fourth answer: **`miscited`**, carrying the clause id the checker believes does support the finding.
- Behaviour: the finding is **kept** (it is real), and a display-only note names the supporting section. The document is never edited automatically.
- **Representation, and why it is not a verdict**: the fourth answer is a separate field on the result (`miscited_to_clause_id`), while the verdict stays "supported". If it were a new verdict it would be deleted by the default filtering rule, which keeps only supported findings (`grounding/models.py`), and every other consumer — colours, the report, the TUI — would silently have to learn it. A field cannot be deleted by accident.
- Sibling clauses are shown with a hard cap on how many and on the length of each, with a test asserting the prompt cannot grow past the cap, so one long contract cannot blow the small model's context.
- Sanity guard against a hallucinated re-citation: accept `miscited` only when the finding's wording is substantially present in the clause the checker names (measured with the same primitive as item 1). Otherwise treat the answer as `ungrounded`.
- Must not: change the colour logic, or repair any pointer.

### Item 4 — the second narrow question, and the agreement rule
A second pass per batch asks only: *"does the clause impose a condition, a limit, a number or a party that the finding leaves out?"* It answers supported / unsupported / uncertain per finding, nothing else. Then the two passes combine:
- both **supported** → supported (accepted);
- either **unsupported** → unsupported;
- anything else (including any abstention) → **not sure**.
Cost: one extra call per batch (batches are ≤10 findings), not per finding.
- Must not: ask the checker to reason in prose, and must not accept on a single pass.
- The rule's cost is real and must be measured: good findings can become "not sure", and in the default setting that means dropped.

### Item 5 — confidence is a warning, never the decision
The checker's self-reported confidence is recorded as today and shown as a warning when it is low; **no verdict may be derived from it**. The recorded evidence is why: the five real mistakes came with the checker 0.9–0.95 sure, and the correct answers with 1.0, so it does not separate wrong from right.
- Must not: introduce a threshold that changes a verdict.

### Item 6 — the memo shows the risky patterns
The memo's clause object gains the verdict and the flags it needs, and prints a line for exactly three cases: **accepted although the wording is absent** (already exists), **not sure**, and **the two passes disagreed**. Ordinary findings render exactly as today.
- Must not: touch `assign_colors` or the amber reasons; the notes are display-only.

### Item 7 — the clause window
Replace the 500-character cut with a sentence-aware window of about **2000 characters**: include the clause's opening, cut on a sentence boundary, and mark when text was left out. Measured reason: 59% of the CUAD corpus clauses exceed 500 characters and 99.6% of those are cut mid-word; a 2000-character window covers 9 in 10.

### Item 8 — no chain-of-thought
No instruction anywhere asks the checker to reason step by step. The paper's finding is that this *lowers* the catch rate at a strict false-positive budget. This item produces no code; the whole-branch review verifies its absence, and the measurement would show it if we were wrong.

## 2. Non-goals

No automatic repair of citations (the owner chose flag-only). No token-logit scoring — verified unavailable for the local model. No fine-tuning. No cloud model in the product path. No change to model slots, privacy tiers or defaults. No chain-of-thought.

## 3. How the change is measured, and what would falsify it

Before/after on the same sound label set, with the audited five tracked individually:

| item | measured by | falsified if |
|---|---|---|
| 1 | the arm run before and after the hint reaches `ground_claim` | the caught count does not move |
| 2 | the audited five re-read against the new negatives; the labelled-as-bad rate | the new negatives still turn out supported on inspection |
| 3 | how many of the two wrongly-cited findings become `miscited`, and how many `miscited` answers name the wrong section | `miscited` fires on findings that are simply unsupported |
| 4 | caught count and good-findings-not-accepted, both passes vs one | caught count does not rise, or good findings are lost faster than bad ones are caught |
| 5/6 | the memo and JSON output, byte-compared with and without | a verdict or colour moves |
| 7 | the window's coverage of the real clause texts | long clauses still lose their deciding text |

The run is the Cloud-free local arm in CI. Receipts are re-pinned and the pages republished with the honest before/after; if the two-pass rule costs more good findings than it catches bad ones, that is published as the result and the rule is not enabled by default.

## 4. Definition of done

Items 1–7 implemented with a failing test first per item; item 8 verified absent by review; the arm run publishes sound-label numbers and a before/after on the hint and on the two-pass rule; the memo shows the three risky patterns and nothing else; no verdict anywhere is derived from confidence; the clause window never cuts mid-sentence; receipts re-pinned, guard green apart from the known issue #180; both documents' claims match the shipped code.
