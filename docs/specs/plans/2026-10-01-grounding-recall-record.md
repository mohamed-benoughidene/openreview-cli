# Grounding recall — record of the kept fixes and the dropped work

**Date:** 2026-10-01 · **Branch:** `chore/keep-defect-fixes`

A body of grounding-recall work was reverted. Four defect fixes were kept; every behaviour
change was dropped. This records what ships, what was measured, and why the rest went. The
runs behind the shipped numbers are the two receipts
`docs/benchmarks/results/grounding-accuracy-local.json` and
`docs/benchmarks/results/grounding-accuracy-cloud.json`.

## What ships

The four kept defect fixes, one line each:

- **Honest measurement labels.** The harness's `unsupported_claim` negatives now come from a
  different document, or from the cited clause's own sentence with one operand changed, so a
  scored negative is genuinely unsupported rather than an unchanged repeat
  (`src/openreview_cli/grounding/corruption.py`).
- **The single-finding path asks the product's question.** `ground_claim` builds its messages
  through the same `build_grounding_messages` primitive as the batch path, so the measurement
  question and the product question cannot drift (`src/openreview_cli/grounding/discriminator.py`).
- **The grounding model's configured context.** The grounding slot reserves the configured
  context window and stays Ollama-only (`src/openreview_cli/config/loader.py`).
- **The receipt hashes text instead of publishing it.** A finding's own text and any raw
  provider error are stored as a sha256, never in the clear (`scripts/measure_slm_slots.py`).

## Measured on this state

Both receipts were regenerated from runs made on this state; the numbers live in them.

- **Local** (`ollama/granite4:3b`, CI run 36905917351): 32 of 44 planted bad claims caught,
  12 called grounded, 25 of 25 known-good accepted, 0 uncertain, mean latency 17.92 s. Receipt:
  `docs/benchmarks/results/grounding-accuracy-local.json`.
- **Cloud** (`openrouter/anthropic/claude-sonnet-4.6`, run locally over the same assembled
  corpus): 38 of 44 caught, 0 called grounded, 24 of 25 accepted, 1 uncertain, mean latency
  3.33 s. Receipt: `docs/benchmarks/results/grounding-accuracy-cloud.json`.

The positives are the clause's own sentences plus a narrow rewrite, so they are supported by
construction and only the negative arm discriminates; both arms run the same assembled corpus.

## What was dropped, and what it was worth

- **The wider clause window, sibling clauses in the prompt, the memo lines, the wrongly-cited
  flag.** Local: identical accuracy with and without them (32 of 44 both ways) but slower with
  them (mean 21.5 s against 17.9 s). Cloud: 41 of 44 with them against 38 of 44 without.
- **The second narrow question.** A net loss on both models — local 29 of 44 with 5 of 25
  known-good claims wrongly rejected and 4 second-pass fallbacks; cloud 26 of 44 with 6 of 25
  wrongly rejected. Not shipped.
- **Three alternative wordings of that second question** lost too (5 of 44 and 31 of 44 caught),
  so the question was dropped on evidence, not on taste.

## Open items

- **Issue #180, a pre-existing red guard.** `tests/unit/test_benchmark_receipts.py::test_results_dir_contains_exactly_the_expected_receipts` still fails: the superseded `slot-measurement.json` is not a registered receipt. Untouched here.
- **The finding text shown to the checker is still cut at 300 characters** (`grounding/prompts.py`), pre-existing and unchanged.
- **The rerank evidence gap is closed** by `docs/benchmarks/results/cuad-rerank-offline.json` on a smaller query set (352 queries), where the lexical-rerank arm came out statistically indistinguishable from plain BM25 rather than worse.
