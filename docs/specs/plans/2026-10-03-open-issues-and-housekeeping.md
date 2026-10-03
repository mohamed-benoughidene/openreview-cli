# Open issues and housekeeping — record of the fixes on this branch

**Date:** 2026-10-03 · **Landed on:** `fix/open-issues-and-docs`, branched off `main` at
`8be30ca`

This branch closes issues #181, #182 and #183 in code and records the #179 decision as
by-design. Repo-level housekeeping was done alongside the branch, not as part of its diff: an
archive tag, a dependabot update and branch pruning. Each of the three code fixes is listed with
its pinning test; the #179 decision and the docs housekeeping have none. The one known open item
is recorded plainly.

## What ships

- **#181, the override rewrites the provider it actually dispatches to** (`fa11da0`, follow-up
  `9d9bd03`, `src/openreview_cli/gateway/router.py`). The extracted
  `Gateway._retarget_provider(call_kwargs, from_prefix, to_prefix)` re-points `api_base` and
  credentials to the provider actually dispatched when a `model=` override — or the fallback leg —
  names a different prefix. It scrubs
  `from_prefix`'s declared credential fields plus `api_base`/`api_key`, then applies `to_prefix`'s
  `base_url`, credentials and, through the extracted `_apply_custom_provider_routing` (shared with
  `_get_litellm_kwargs`), custom-provider `openai/<id>` routing. `_call_with_fallback` calls it on
  the override leg (`primary_prefix`→`provider`) and the fallback leg (`provider`→`fallback_prefix`).
  Tests: `tests/unit/test_gateway_router.py::TestModelOverrideRetargetsProvider` and
  `::TestFallbackDropsThePreviouslyAppliedProvider`. Redteam RT-031/RT-032
  (`tests/redteam/test_redteam_egress_guard.py`) were updated — they had pinned the buggy
  destination, and the strict `xfail` on
  `test_a_tier_approved_local_override_is_not_sent_to_a_cloud_host` was removed because the fix
  makes it pass.
- **#182, the dispatch-time local-only gate** (`fa11da0`). `_enforce_local_only_params` now takes
  `restore=`; `_call_with_fallback` snapshots the local-only values present before the first strip
  and restores from that snapshot on a local leg, falling back to the slot's declared
  `extra_params`. Test: `test_a_caller_supplied_param_reaches_a_local_fallback_when_the_slot_declares_none`.
- **#183, the bracket-run scan no longer abandons the payload** (`c145cca`,
  `src/openreview_cli/grounding/prompts.py::_first_json_value`). On a decoder `RecursionError` it
  resumes at the tail of the offending bracket run (`_DEEP_RUN_TAIL = 64`) instead of abandoning the
  scan; it still stops when the run is not longer than the tail, which keeps the scan bounded.
  Tests: `tests/unit/test_grounding_prompts.py::test_a_bracket_heavy_preamble_still_parses_the_answer`
  and `::test_a_bracket_only_payload_is_unreadable_and_still_bounded`.
- **Docs debt** (`1a06563`). `AGENTS.md` lost the stale "(and embedding/reranking, if enabled)"
  note — those sockets were removed in spec 035 — and gained the never-rebase-merge rule under
  Conventions.
- **#179, closed as not planned / by design.** There is no privacy-safe local reranking route:
  Ollama's API documents no rerank endpoint, and the pinned litellm ships no ollama rerank handler
  (handlers exist only for bedrock, deepinfra, hosted_vllm and vertex_ai).

## Known open item

- **#183 is not yet mergeable.** Six committed grounding receipts under `docs/benchmarks/results/`
  pin `src/openreview_cli/grounding/prompts.py` by sha256, so
  `tests/unit/test_benchmark_receipts.py::test_every_receipt_pins_its_producing_content` is red on
  this branch. Regenerating the receipts needs real model runs (Ollama + OpenRouter)
  (environment note: no Ollama/OpenRouter access at write time), so the regeneration is deferred
  to a run-backed follow-up. The 235B MoE row's
  `unreadable_answers` (2) is expected to change.

## Pre-existing, not fixed

- A same-prefix `model=` override on a `source == "custom"` primary stays unroutable: on the
  OVERRIDE leg `_retarget_provider` is skipped when the prefix is unchanged (`router.py:603`), so
  the `openai/<id>` rewrite does not re-run; on the fallback leg it is called unconditionally. Not
  introduced by this work.

## Verification

As of writing:

- `uv run pytest tests/unit/test_gateway_router.py tests/unit/test_grounding_prompts.py tests/redteam/test_redteam_egress_guard.py tests/unit/test_gateway_tier_enforcement.py` → 183 passed.
- `uv run ruff check .` clean; `uv run mypy src/ tests/` clean.
