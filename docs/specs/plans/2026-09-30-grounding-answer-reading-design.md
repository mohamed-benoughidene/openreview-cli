# Design — read the fact-checker's answers properly, and give the local models a fair test

- **Date:** 2026-09-30
- **Status:** Approved by the owner (design review, 2026-09-30). Scope decision: all three fixes, with the
  JSON-only request gated to local providers.
- **Branch:** `fix/grounding-answer-reading`, based on `feat/slm-measurement` at `4229cfe`.
- **Companion:** `/home/mohamed/lab/openreview/draft/handoff-2026-09-30-slm-fair-test/HANDOFF.md` holds the
  original diagnosis and the raw evidence copies (`evidence/` beside it).

Terms in plain words, used consistently below: the **fact-checker** is the grounding discriminator, the step
that decides whether a claim is really supported by the clause it cites; **reading an answer** means turning
the model's text reply into a structured result; an **unreadable answer** is one the reader could not parse.

---

## 1. Problem

The local model looks like it refuses to decide. It does not — its answers are frequently not being read, and
the code turns that into "uncertain" with confidence 0.0. Half its calls therefore carry no information.

Same task, same 20 clauses, same reader, two models:

| | local `granite4:3b` | cloud `claude-sonnet-4.6` |
|---|---|---|
| answers read successfully | 28 of 60 | 60 of 60 |
| bad claims caught | 27 of 40 (a floor) | 39 of 40 |
| good claims accepted | 1 of 20 | 20 of 20 |
| uncertain | 32, every one confidence 0.0 | 1, confidence 0.45 |
| mean latency per call | 7.72 s | 2.96 s |

Two facts pin the cause. Every one of the 32 local "uncertain" rows carries confidence exactly 0.0, and the
job log holds 31 `Failed to parse grounding response` lines against 0 `Gateway call failed` lines. In
`discriminator.py`, `UNCERTAIN` with confidence 0.0 has only three sources: an empty claim (`:81-83`), a
gateway exception (`:114-115`), and the reader returning nothing (`:117-120`). The log rules out the first
two. The difference between the two models is the reader, not caution.

**Consequence.** The published sentence in `docs/benchmarks/results/slot-measurement.md` — that the local
model "defers rather than decides" — is wrong. The local model's true ability is currently unmeasured.

---

## 2. Root cause

1. **The reader is the only parser in the project that ignores the shared unwrap helper.** `llm_json.py:20`
   `strip_fences` exists for answers wrapped in markdown code fences, and that module's docstring states every
   gateway-response parser must use it. `review/prompts.py:14`, `review/extraction.py:190`,
   `bilateral/comparison.py:138` and `benchmark/baseline.py:114` all do. `grep -c strip_fences
   src/openreview_cli/grounding/prompts.py` returns `0`.
2. **It relies on greedy regexes instead.** `_extract_json_array` (`prompts.py:150`) tries a fenced match at
   `:157`, then a bare greedy match `(\[[\s\S]*\])` at `:162`. The greedy match starts at the *first* `[` in
   the whole reply, so prose containing brackets slices the wrong span.
3. **The failure is invisible.** `parse_grounding_response` returns `[]` (`:101-103`), the caller logs a single
   warning and returns `UNCERTAIN, [], 0.0`, and the receipt records that as "uncertain" — the same value a
   genuine hesitant verdict would produce. Nothing in the measured numbers distinguishes the two.

Answer shapes and how the current reader handles them — nine of the thirteen tested shapes pass and four fail,
with rows merged below wherever the outcome is identical:

| shape | now |
|---|---|
| bare array of one object | pass |
| fenced array (```json and untagged) | pass |
| prose before / after the array | pass |
| fenced array with trailing prose | pass |
| quoted reason containing `[`, `]` or `}` | pass |
| **prose containing brackets before the array** | **fail** |
| **a single object instead of an array** | **fail** |
| **two arrays back to back** | **fail** |
| **truncated / unbalanced JSON** | **fail** |

---

## 3. Goals and non-goals

**Goals**

1. The reader handles the shapes local models actually emit, without weakening the batched path.
2. Local grounding models are asked for JSON only; the cloud path cannot receive that request.
3. The prompt matches what the code actually sends.
4. Unreadable answers become visible in the measurement receipt, so this class of defect cannot hide again.
5. Re-measure honestly and correct the published sentence.

**Non-goals**

- No change of model, slot count, privacy tiers, or defaults.
- No weakening of the receipt guard or of the CI job's fail-loud gate.
- No changes to the extraction, QA, bilateral or benchmark parsers.
- No logging of raw model answers or contract text (privacy rule — the reason this diagnosis is an inference
  rather than an observation).

---

## 4. Design

### 4.1 Reader (Fix 1) — `src/openreview_cli/grounding/prompts.py`

- `parse_grounding_response` (`:81`) first unwraps through `llm_json.strip_fences` (the project's rule).
- Then it scans candidate start offsets — each position of `[` or `{` — calling the standard library's
  `json.JSONDecoder().raw_decode` until one decodes, and keeps the first value that does.
- A decoded object becomes a one-element list; a decoded list is used as is.
- Per-item validation is unchanged: skip non-dict items, skip items without an integer `claim_index`, skip
  unknown verdict strings.
- `_extract_json_array` (`:150-166`) is **deleted** — verified to have exactly one caller (`:100`).

Why `raw_decode`: it understands quoted strings and escapes natively, so a `[`, `]` or `}` inside a quoted
reason cannot unbalance the scan, and it stops at the end of the first valid value, so trailing prose is
ignored. Writing a bracket-aware scanner by hand would reimplement the standard library. `strip_fences` is
kept despite `raw_decode` making it largely redundant, because the repo states it as a rule for every parser
and consistency is what the reviewers check; note it as a deliberate, documented choice.

Resulting behaviour on the table in section 2: the brackets-in-preamble case is fixed (the scan steps past the
bad candidate), the single-object case is fixed (object → list), two arrays now take the first value, and
truncated JSON still fails — but visibly, per 4.4.

### 4.2 Local-only JSON request (Fix 2) — `gateway/router.py` + `config/loader.py`

- Add a module-level `_LOCAL_ONLY_PARAMS = frozenset({"response_format"})` in `gateway/router.py`.
- In `_get_litellm_kwargs` (`:352`), resolve provider info *before* merging `extra_params`. Today
  `info = self._resolve_provider_info(slot)` sits at `:373`, after the merge at `:361-371`; the resolution
  moves one block up.
- When merging `extra_params`, drop any key in `_LOCAL_ONLY_PARAMS` if the provider is not local — that is,
  when `info is None` (unknown provider: fail safe) or `info.is_local` is false (`gateway/models.py:38`).
  Log at debug level, not warning: the drop is expected, not an error.
- Config default: the `grounding` slot gains
  `extra_params={"response_format": {"type": "json_object"}}` in `config/loader.py:104-106`.
- The installed litellm honours this for Ollama: `response_format={"type":"json_object"}` becomes
  `optional_params["format"] = "json"` (`litellm/.../transformation.py:176-180`, emitted at `:319-320`).
- The cloud path is provably untouched: a non-local provider never receives the key. This matters because
  unsupported parameters raise (`litellm/utils.py:3170`) rather than being dropped, so an unconditional flag
  would turn a degraded parse into a hard failure for cloud grounding users.

### 4.3 Prompt (Fix 3) — `src/openreview_cli/grounding/prompts.py:41`

The prompt is shared by two callers: `ground_claim` sends exactly one claim (`discriminator.py:99-102`), while
`ground_report` batches up to `_BATCH_SIZE = 10` (`:32`, flush at `:199-201`, remainder at `:204-205`). The
current final line demands an array unconditionally, which is what invites the single-object reply that the
old reader then rejected.

Replacement for the final instruction line:

> For each claim, respond with one JSON object. If there is a single claim, you may return that object on its
> own; if there are several, return a JSON array of the objects, one per claim, in the same order as the input
> claims. Return the JSON only — no text before or after it.

This stays correct for both callers: the batch case keeps the array contract, and the single-claim case now
permits the natural shape that the new reader also accepts.

### 4.4 Unreadable-answer counter — `grounding/discriminator.py` + `scripts/measure_slm_slots.py`

- `GroundingDiscriminator` gains a counter, incremented exactly where the reader returns nothing
  (`discriminator.py:117-120`). It is not incremented on the gateway-exception path (`:114-115`) — that is a
  different fault and stays in the log.
- The counter must remain correct across batching, including `_process_batch` (`:275`).
- The harness adds `unreadable_answers` to the receipt near `scripts/measure_slm_slots.py:518-526` and prints
  it beside the uncertain counts near `:547`.
- Purpose: turn "the fix appears to work" into "the receipt shows zero". Without it, a regression hides
  inside "uncertain" exactly as this one did.

---

## 5. Data flow

Before: answer text → greedy regex → `json.loads` → on failure `[]` → `UNCERTAIN, confidence 0.0` → receipt
says "uncertain" (indistinguishable from a real hesitation).

After: answer text → `strip_fences` → first value that `raw_decode` accepts (object wrapped as a list) → on
failure `[]` **and counter incremented** → `UNCERTAIN, confidence 0.0` → receipt shows both "uncertain" and
"unreadable answers", so the two causes are separable.

Request side: grounding slot config → `extra_params` → router merges, dropping `response_format` unless
`info.is_local` → litellm → Ollama receives `format: "json"`; a cloud provider receives nothing extra.

---

## 6. Error handling and privacy

- An unreadable answer keeps today's safe fallback (`UNCERTAIN`, confidence 0.0) — the pipeline stays
  fail-safe, it just stops being silent.
- The only new visibility is a count. No raw answer, claim text, or clause text is logged, in debug or
  otherwise. If shape-level diagnostics are ever wanted, they record structure only (for example whether a
  fence was present), never content.
- A dropped local-only parameter is a debug line; stripping a protected key keeps its existing warning
  (`router.py:365-368`).

---

## 7. Testing plan (TDD — every test fails before the change)

| Where | What it pins |
|---|---|
| **new** `tests/unit/test_grounding_prompts.py` | The shape table from section 2, executed rather than traced: all four currently failing shapes now parse, the passing ones still parse, a quoted reason containing `[`/`]`/`}` still parses, truncated JSON still returns empty, empty string returns empty, a single object yields one result, and an array of three yields three |
| `tests/unit/test_grounding_discriminator.py` | Existing tests unaffected (the suite's only parse input is a bare array at `:22`); batched shape links `claim_index` correctly; the counter increments on an unreadable answer and stays put on a readable one; the gateway-failure path does not touch the counter |
| `tests/unit/test_gateway_router.py` | `response_format` is forwarded when the provider is local; dropped when it is not; dropped when the provider is unknown; other `extra_params` still forwarded (no regression to existing `extra_params` tests) |
| `tests/unit/test_grounding_harness.py` | The receipt carries `unreadable_answers`, and it is zero when every answer parses |
| fallback path | A fallback to a cloud model must not inherit `response_format` — *to confirm during the plan stage how the fallback path builds its kwargs; if it does not route through the same gate, the fix there is part of this task* |

Commands:

```bash
uv run pytest tests/unit/test_grounding_prompts.py tests/unit/test_grounding_discriminator.py \
    tests/unit/test_gateway_router.py tests/unit/test_grounding_harness.py -q
uv run pytest -m "fast" -q          # the default pool
uv run pre-commit run --all-files   # the required pre-commit gate
```

---

## 8. Verification and acceptance

1. Unit tests above, written first and passing.
2. Re-run the local arm in CI — the only place a local model can run:
   ```bash
   gh workflow run slm-measurement.yml --ref fix/grounding-answer-reading
   gh run list --workflow=slm-measurement.yml --branch fix/grounding-answer-reading --limit 3
   ```
   The `grounding-accuracy` job takes roughly 15 minutes. Its fail-loud gate
   (`.github/workflows/slm-measurement.yml:445-534`; `REQUIRED_UNITS = 20`) must stay exactly as it is.
3. Compare against the recorded baseline — units 20, positives 20, negatives kept 40, guard drops 0;
   before: `bad_caught 27/40`, `good_accepted 1/20`, uncertain 32 with confidence 0.0. Report whatever the run
   returns; assume neither that it improves nor that it reaches the cloud's figures.
4. Correct `docs/benchmarks/results/slot-measurement.md`: replace the "defers rather than decides" sentence and
   the "19 of 20 good claims" figure with the re-measured numbers, and add one line to the method section
   stating the reader was fixed and the local grounding request now asks for JSON.

**What the two runs do and do not cover.** Read this before treating a green run as proof of safety.

| Risk | Local run | Cloud run | Unit tests |
|---|---|---|---|
| The JSON request leaks to a cloud provider | not applicable | Only if that provider *rejects* the parameter — then the pre-flight (`scripts/measure_slm_slots.py:418-448`) aborts the run loudly. If the provider accepts it, the run stays green and the leak is invisible | yes, explicit |
| Several claims in one call breaks | **no** — the harness calls `ground_claim` one claim at a time (`:693`) | **no** | yes, required |
| A fallback model inherits the request | **no** — the grounding slot ships with `fallback: None` (`config/loader.py:31-35`), and nothing forces a fallback | **no** | yes, required |
| An unknown provider receives the request | no | no | yes |
| Answers cut off partway | visible only through the new counter | same | yes |

Consequence, stated plainly: the two runs confirm the main path of each arm and nothing more. The three
structural risks (multi-claim batches, fallback, unknown provider) are covered by unit tests alone — which is
exactly why those tests are mandatory rather than nice-to-have. The cloud arm is manual by design: it needs a
key that can spend, so it is not part of CI.

---

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| A cloud grounding user is affected by the new request | Local-only gate; `response_format` never reaches a non-local provider; tested for the local, cloud and unknown-provider cases |
| The batched caller breaks | Prompt keeps the array contract for several claims; a three-object batch test; `_BATCH_SIZE` and both flush sites unchanged |
| The fallback model inherits the flag | Explicit test; the fallback path is inspected during planning and fixed here if it does not route through the gate |
| A parameter drop is mistaken for a bug | Debug-level log explains it; the existing protected-key warning is untouched |
| Truncated answers remain unreadable | Not solved by this change, but now counted and visible; the local JSON request reduces the chance |
| The receipt guard or the CI gate erodes | Neither is edited; the existing known failure (`tests/unit/test_benchmark_receipts.py`, issue #180) is left alone |
| Two arrays back to back silently yield only the first | Accepted: one response corresponds to one call, and the second value would be meaningless |

---

## 10. Alternatives considered

| Alternative | Why rejected |
|---|---|
| Do nothing | The published numbers stay wrong and the local model keeps being misjudged |
| Fix the reader only, defer the JSON request | Was offered as the smallest option; the owner chose all three, and the local-gate removes the cloud risk that motivated deferring |
| Apply `response_format` unconditionally | Unsupported parameters raise (`litellm/utils.py:3170`), so cloud grounding would fail hard instead of degrading |
| Gate at the call site via a public `is_local` query | Puts a routing concern in the caller, duplicates the decision, and touches both call sites |
| Hand-written bracket scanner | Stdlib `raw_decode` already handles strings and escapes correctly |
| Retry a failed parse, or ask the model to repair its own JSON | Doubles calls, adds latency, and hides the defect instead of fixing it |
| Switch to a larger local model | Does not address a reader defect; the model is not the cause here |
| Delete `strip_fences` as redundant given `raw_decode` | Kept deliberately: the repo states it as a rule for every parser, and consistency is cheaper than explaining the exception |

---

## 11. Definition of done

- The reader unwraps through the shared helper, takes the first value `raw_decode` accepts, accepts a single
  object as a one-element list, and still parses the batched shape — each covered by a test that fails before
  the change.
- The local grounding request asks for JSON only, with tests proving the cloud and unknown-provider paths are
  unchanged, and the fallback path verified.
- The prompt matches what both callers send.
- The receipt shows unreadable answers separately from uncertain ones.
- The local grounding job has been re-run in CI, its numbers recorded against the baseline, and the wrong
  sentence in the slot report corrected.
- Nothing else changed: no slots, tiers, defaults, receipt-guard edits, or `main` commits.

---

## 12. Open uncertainties

- **Still unknown: which malformation the local model actually emits.** Nobody has captured an answer's shape
  (privacy forbids logging it), so the fixes target the four known failure modes plus the JSON request. The
  new counter is what will tell us whether they were the right four. If unreadable answers persist after this
  change, the next lever is the local model and its parameters, not the reader.
- **Whether the fallback path routes through the same kwargs builder** is unverified; the plan stage must check
  it, and section 7 makes it a required test.
- **Whether two back-to-back arrays ever occur in practice** is unverified; the chosen behaviour (first value
  wins) is safe either way.
- **Correction carried from the diagnosis:** the handoff wrote bare `config/loader.py` for a path that is
  `src/openreview_cli/config/loader.py`, and listed `_SLOT_METHOD_MAP` as a live concern when it no longer
  exists (a test asserts its absence). Both fixed in the handoff on 2026-09-30.
