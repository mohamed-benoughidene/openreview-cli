# Grounding Answer Reading — Implementation Plan

> **For agentic workers:** Use tasks as checkboxes (`- [ ]`) for tracking.

**Goal:** Make the grounding reader understand the answers local models actually write, ask local grounding models for JSON only, and make unreadable answers visible in the measurement receipt — so the local model can be measured fairly.

**Architecture:** The reader in `grounding/prompts.py` stops using a greedy regex and instead unwraps a fenced payload through the project's shared helper, then lets the standard library's `json.JSONDecoder().raw_decode` find the first complete value; an object counts as a one-element list. A local-only request parameter (`response_format`) is added to the grounding slot and stripped at both dispatch sites unless the provider runs locally. A counter on the discriminator, surfaced in the harness receipt, separates "unreadable answer" from "model said uncertain".

**Tech Stack:** Python 3.12, pytest, `uv`, litellm, pydantic, `json` (stdlib only — no new dependencies).

**Design document:** `docs/specs/plans/2026-09-30-grounding-answer-reading-design.md` (same directory). Read it before starting; every anchor below was verified against the live code on 2026-09-30.

## Global Constraints

- **Branch:** `fix/grounding-answer-reading`, already created from `feat/slm-measurement` at `4229cfe`. Never commit to `main`.
- **Worktree:** `/home/mohamed/lab/openreview/.worktrees/grounding-answer-reading` — run every command from there.
- **Python 3.12 and `uv` only.** Add no dependency.
- **TDD:** write the failing test first, watch it fail, then implement. A test written after the code does not count.
- **Never log a raw model answer, claim text, or clause text** — structure only (a count, a shape flag). This is a privacy rule.
- **`uv run pre-commit run --all-files` must pass** before each commit.
- **Every commit message ends with the trailer:**
  `Co-authored-by: CommandCodeBot <noreply@commandcode.ai>`
- **Do not touch:** `tests/unit/test_benchmark_receipts.py` (it holds one known failure, issue #180), the CI job's fail-loud gate in `.github/workflows/slm-measurement.yml:445-534`, `_BATCH_SIZE = 10` (`discriminator.py:32`), and both batch flush sites (`:199-205`).
- **Memory-marked tests run solo:** `uv run pytest -m memory -q`, never in a pool.
- **Audience rule:** no product-audience terms in committed text.
- **The exact new prompt sentence** (used verbatim in Task 2): `For each claim, respond with one JSON object. If there is a single claim, you may return that object on its own; if there are several, return a JSON array of the objects, one per claim, in the same order as the input claims. Return the JSON only — no text before or after it.`

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `src/openreview_cli/grounding/prompts.py` | The grounding prompt and the answer reader | Modify: reader rewritten, `_extract_json_array` deleted, prompt tail replaced |
| `src/openreview_cli/gateway/router.py` | Builds provider request kwargs; dispatches with fallback | Modify: `_enforce_local_only_params`, enforced once per dispatch in both legs of `_call_with_fallback` |
| `src/openreview_cli/config/loader.py` | Shipped gateway defaults | Modify: grounding slot gains `extra_params` |
| `src/openreview_cli/grounding/discriminator.py` | Decides per-claim verdicts | Modify: `unreadable_answers` counter |
| `scripts/measure_slm_slots.py` | The measurement harness and its receipt | Modify: receipt field, summary line |
| `tests/unit/test_grounding_prompts.py` | The reader's shape table | **Create** |
| `tests/unit/test_grounding_discriminator.py` | Counter behaviour | Modify |
| `tests/unit/test_gateway_router.py` | Local-only parameter gate, including the fallback | Modify |
| `tests/unit/test_grounding_harness.py` | Receipt carries the counter | Modify |
| `docs/benchmarks/results/slot-measurement.md` | The published slot report | Modify in Task 5 only |

---

### Task 1: Read the answers local models actually write

**Files:**
- Modify: `src/openreview_cli/grounding/prompts.py` (reader at `:81`, delete `:99-109` regex use, delete `_extract_json_array` at `:150-166`)
- Test: `tests/unit/test_grounding_prompts.py` (create)

**Interfaces:**
- Consumes: `openreview_cli.llm_json.strip_fences(text: str) -> str`; `openreview_cli.grounding.models.{GroundingVerdict, CitationProvenance}`
- Produces: `parse_grounding_response(response: str) -> list[tuple[int, GroundingVerdict, list[CitationProvenance], float]]` — unchanged signature, widened acceptance; private helper `_first_json_value(text: str) -> Any | None`

- [ ] **Step 1: Write the failing test file**

Create `tests/unit/test_grounding_prompts.py`:

```python
"""Unit tests for the grounding answer reader."""

from __future__ import annotations

import json

from openreview_cli.grounding.models import GroundingVerdict
from openreview_cli.grounding.prompts import parse_grounding_response

GROUNDED = {
    "claim_index": 0,
    "verdict": "grounded",
    "provenances": [{"clause_id": "4.3", "paragraph_index": 2, "confidence": 0.95}],
    "confidence": 0.95,
    "reason": None,
}


def _obj(index: int, verdict: str = "grounded") -> dict:
    return {**GROUNDED, "claim_index": index, "verdict": verdict}


def _verdicts(response: str) -> list[GroundingVerdict]:
    return [row[1] for row in parse_grounding_response(response)]


def _indices(response: str) -> list[int]:
    return [row[0] for row in parse_grounding_response(response)]


# ── shapes that already worked: regression guards ─────────────────────────────


def test_bare_array_parses() -> None:
    assert _verdicts(json.dumps([GROUNDED])) == [GroundingVerdict.GROUNDED]


def test_fenced_array_parses() -> None:
    assert _verdicts(f"```json\n{json.dumps([GROUNDED])}\n```") == [GroundingVerdict.GROUNDED]


def test_fenced_array_without_language_tag_parses() -> None:
    assert _verdicts(f"```\n{json.dumps([GROUNDED])}\n```") == [GroundingVerdict.GROUNDED]


def test_prose_before_the_array_parses() -> None:
    assert _verdicts(f"Here is the result:\n{json.dumps([GROUNDED])}") == [GroundingVerdict.GROUNDED]


def test_prose_after_the_array_parses() -> None:
    assert _verdicts(f"{json.dumps([GROUNDED])}\nLet me know if you need more.") == [
        GroundingVerdict.GROUNDED
    ]


def test_fenced_array_with_trailing_prose_parses() -> None:
    assert _verdicts(f"```json\n{json.dumps([GROUNDED])}\n```\nThat is my answer.") == [
        GroundingVerdict.GROUNDED
    ]


def test_quoted_reason_containing_brackets_parses() -> None:
    grounded = {**GROUNDED, "reason": "see [section 3] and a stray ] here"}
    assert _verdicts(json.dumps([grounded])) == [GroundingVerdict.GROUNDED]


def test_quoted_reason_containing_a_brace_parses() -> None:
    grounded = {**GROUNDED, "reason": "a closing } brace inside a string"}
    assert _verdicts(json.dumps([grounded])) == [GroundingVerdict.GROUNDED]


def test_batch_of_three_parses_with_indices_in_order() -> None:
    response = json.dumps([_obj(0), _obj(1, "ungrounded"), _obj(2)])
    assert _indices(response) == [0, 1, 2]


def test_truncated_json_returns_empty() -> None:
    assert parse_grounding_response('[{"claim_index": 0, "verdict": "gro') == []


def test_empty_string_returns_empty() -> None:
    assert parse_grounding_response("") == []


def test_text_without_json_returns_empty() -> None:
    assert parse_grounding_response("I cannot help with that.") == []


# ── shapes that failed: the reason this task exists ───────────────────────────


def test_bracketed_preamble_before_the_array_parses() -> None:
    response = f"First, consider [the claim]. Then:\n{json.dumps([GROUNDED])}"
    assert _verdicts(response) == [GroundingVerdict.GROUNDED]


def test_a_single_object_parses_as_one_result() -> None:
    assert _verdicts(json.dumps(GROUNDED)) == [GroundingVerdict.GROUNDED]


def test_two_arrays_back_to_back_take_the_first() -> None:
    response = json.dumps([_obj(0)]) + json.dumps([_obj(1)])
    assert _indices(response) == [0]
```

- [ ] **Step 2: Run it and confirm three failures**

Run: `uv run pytest tests/unit/test_grounding_prompts.py -q`
Expected: **3 failed, 12 passed.** The failures are `test_bracketed_preamble_before_the_array_parses`, `test_a_single_object_parses_as_one_result` and `test_two_arrays_back_to_back_take_the_first`. This baseline was **executed** against the unmodified reader on 2026-09-30, not traced. The three tests that assert emptiness (`truncated`, `empty string`, `text without json`) also pass before the change — they are regression guards, not evidence. If your failure set differs, stop and re-read the reader before continuing.

- [ ] **Step 3: Implement the reader**

In `src/openreview_cli/grounding/prompts.py` add to the imports (the module already imports `json`, `logging`, `re` and `Any`):

```python
from openreview_cli.llm_json import strip_fences
```

Replace the block at `:99-109` — from `# Try to extract JSON array from response` through the `except json.JSONDecodeError` block — with:

```python
    data = _first_json_value(response)
    if data is None:
        return results
    items: list[Any] = data if isinstance(data, list) else [data]
```

Then change the loop header `for item in data:` to `for item in items:`. Leave everything inside the loop (the `claim_index` check, verdict parsing, provenance parsing) exactly as it is.

Delete the whole `_extract_json_array` function (`:150-166`, including its docstring) — its only caller was the code you just replaced. **Also delete `import re` (`:12`)**: its only two uses are the regexes inside the function you removed, and leaving it trips ruff `F401`, which fails the pre-commit gate you must pass in Task 5. Confirm with `uv run ruff check src/openreview_cli/grounding/prompts.py` (expected: no output). Add in its place:

```python
def _first_json_value(text: str) -> Any | None:
    """Return the first JSON value in ``text``, or None when there is none.

    The payload is unwrapped through the project-wide fence helper first, then
    candidate start positions are offered to the standard library decoder. That
    decoder understands quoted strings and escapes, so a bracket or brace inside
    a reason string cannot unbalance the scan, and it stops at the end of the
    first valid value, so trailing prose is ignored.
    """
    candidate_text = strip_fences(text)
    decoder = json.JSONDecoder()
    for index, char in enumerate(candidate_text):
        if char not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(candidate_text, index)
        except json.JSONDecodeError:
            continue
        return value
    return None
```

- [ ] **Step 4: Run the tests again**

Run: `uv run pytest tests/unit/test_grounding_prompts.py -q`
Expected: **15 passed.**

- [ ] **Step 5: Confirm nothing else depended on the deleted helper**

Run: `uv run pytest tests/unit/test_grounding_discriminator.py tests/unit/test_grounding_harness.py -q`
Expected: all pass — the harness's stub is unaffected because it replaces `ground_claim`, not the reader.

- [ ] **Step 6: Commit**

```bash
git add src/openreview_cli/grounding/prompts.py tests/unit/test_grounding_prompts.py
git commit -m "fix(grounding): read single objects, fenced payloads and bracketed preambles"
```

---

### Task 2: Ask for one object, and keep the array contract for batches

**Files:**
- Modify: `src/openreview_cli/grounding/prompts.py` (final line of `GROUNDING_PROMPT_TEMPLATE`, `:41`)
- Test: `tests/unit/test_grounding_prompts.py` (append)

**Interfaces:**
- Consumes: `GROUNDING_PROMPT_TEMPLATE` (module constant) and `build_grounding_messages(source_clauses, claims)`, both unchanged in signature. The template is consumed by both `ground_claim` (1 claim) and `ground_report` (up to `_BATCH_SIZE = 10`).
- Produces: no callable change — the template text only. Do not add or remove any `{...}` placeholder: the template is formatted and already contains doubled braces for literal JSON.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_grounding_prompts.py`:

```python
from openreview_cli.grounding.prompts import GROUNDING_PROMPT_TEMPLATE

NEW_TAIL = (
    "For each claim, respond with one JSON object. If there is a single claim, you may return that "
    "object on its own; if there are several, return a JSON array of the objects, one per claim, in the "
    "same order as the input claims. Return the JSON only"
)


def test_prompt_permits_a_single_object_and_keeps_the_array_for_batches() -> None:
    normalised = " ".join(GROUNDING_PROMPT_TEMPLATE.split())
    assert NEW_TAIL in normalised


def test_prompt_no_longer_demands_an_array_unconditionally() -> None:
    assert "Respond with a JSON array of these objects" not in GROUNDING_PROMPT_TEMPLATE
```

- [ ] **Step 2: Run it and confirm one failure**

Run: `uv run pytest tests/unit/test_grounding_prompts.py -q -k prompt`
Expected: **2 failed.** Both assertions read the unmodified template — the new sentence is absent and the old sentence is still present, so each is false before the change.

- [ ] **Step 3: Replace the template's final line**

Replace the sentence on line `:41`. That line also carries the template's closing triple quote, so replace only the sentence text and keep the `"""` — deleting the whole line leaves an unterminated string and a `SyntaxError`:

```
Respond with a JSON array of these objects, one per claim, in the same order as the input claims.
```

Use the exact sentence from Global Constraints, copied verbatim; it contains no braces.

- [ ] **Step 4: Run the tests again**

Run: `uv run pytest tests/unit/test_grounding_prompts.py -q`
Expected: **17 passed.**

- [ ] **Step 5: Commit**

```bash
git add src/openreview_cli/grounding/prompts.py tests/unit/test_grounding_prompts.py
git commit -m "fix(grounding): permit a single object for a single claim in the prompt"
```

---

### Task 3: Ask only local models for JSON — including on the fallback path

**Files:**
- Modify: `src/openreview_cli/gateway/router.py` (add `_enforce_local_only_params` near the other module helpers; call it in `_call_with_fallback` before the first attempt — never in `_get_litellm_kwargs`, which is build time)
- Modify: `src/openreview_cli/config/loader.py` (the `grounding` entry in `DEFAULT_CONFIG` at `:31-35`)
- Test: `tests/unit/test_gateway_router.py` (append a class after `TestExtraParamsPassThrough`)
- Test: `tests/unit/test_gateway_models.py` (append one test pinning the shipped default)

**Interfaces:**
- Consumes: `classify_provider(info) -> str` (`gateway/models.py:46`), the codebase's single notion of local; `load_registry().get(prefix)` (`router.py:604`); the slot's `extra_params`; the existing test helper `_gateway(tmp_path, monkeypatch, config)`, constant `COMMON_CONFIG` and response double `_MockCompletionResponse`.
- Produces: `_enforce_local_only_params(kwargs: dict[str, Any], extra_params: dict[str, Any] | None, provider_prefix: str) -> None` — one gate per dispatch, against the provider actually dispatched.

- [ ] **Step 1: Read the existing fallback test pattern**

Read `tests/unit/test_gateway_router.py:161-238`. Note two things you will reuse: the config is built with `COMMON_CONFIG.replace(...)`, and a fallback is simulated by `monkeypatch.setattr(router_mod, "completion", ...)` where the stub records each dispatch's kwargs and raises until the fallback is dispatched. The gate runs at **dispatch** time, so the kwargs must be read at that same `completion` seam — a build-time dict from `_get_litellm_kwargs` is never dispatched as-is and can still be rewritten by a `model=` override. Also read `COMMON_CONFIG` (around `:80-101`) and copy its exact text for the two lines the helpers below replace — if those lines read differently, adjust the `replace()` arguments to match, keeping the same intent.

- [ ] **Step 2: Write the failing tests (the five mandatory cases)**

Append to `tests/unit/test_gateway_router.py`:

```python
def _config_with(primary: str, *, fallback: str = "anthropic/claude-3") -> str:
    """COMMON_CONFIG with a chosen reasoning primary and fallback plus a local-only param."""
    cfg = COMMON_CONFIG.replace("      primary: openai/gpt-4\n", f"      primary: {primary}\n")
    cfg = cfg.replace("      fallback: anthropic/claude-3\n", f"      fallback: {fallback}\n")
    return cfg.replace(
        "      extra_params:\n        top_p: 0.9\n",
        "      extra_params:\n        response_format:\n          type: json_object\n",
    )


def _capture_dispatches(
    monkeypatch: pytest.MonkeyPatch, *, failures_before_success: int = 0
) -> list[dict]:
    """Patch ``router.completion`` to record the kwargs each dispatch received.

    The gate runs at DISPATCH time, so a test must observe the kwargs at the
    litellm seam — a dict that is never dispatched hides an override leak.
    """
    import openreview_cli.gateway.router as router_mod

    seen: list[dict] = []

    def stub(**kwargs) -> _MockCompletionResponse:
        seen.append(dict(kwargs))
        # `gateway.fallback.retries` is 2 in COMMON_CONFIG, so the primary is
        # attempted three times before the fallback is dispatched. A stub that
        # raises once would only trigger a primary retry and never reach the
        # fallback at all — the test would then fail after implementation.
        if len(seen) <= failures_before_success:
            raise RuntimeError("primary unavailable")
        return _MockCompletionResponse("from fallback" if failures_before_success else "ok")

    monkeypatch.setattr(router_mod, "completion", stub)
    return seen


class TestLocalOnlyExtraParams:
    """`response_format` is a local-only hint; a cloud provider must never see it.

    An unsupported parameter raises in litellm rather than being dropped, so a
    leak here turns a degraded parse into a hard failure. The gate is enforced
    for the provider ACTUALLY dispatched, so these tests assert on the kwargs
    captured at the ``completion`` seam, never on ``_get_litellm_kwargs`` — a
    build-time dict a dispatch-time ``model=`` override can still rewrite.
    """

    def test_forwarded_to_a_local_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen = _capture_dispatches(monkeypatch)
        gw = _gateway(tmp_path, monkeypatch, _config_with("ollama/granite4:3b"))
        assert gw.chat("reasoning", [{"role": "user", "content": "Hi"}]) == "ok"
        assert seen[0]["response_format"] == {"type": "json_object"}

    def test_dropped_for_a_cloud_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen = _capture_dispatches(monkeypatch)
        gw = _gateway(tmp_path, monkeypatch, _config_with("openai/gpt-4"))
        gw.chat("reasoning", [{"role": "user", "content": "Hi"}])
        assert "response_format" not in seen[0]

    def test_dropped_for_an_unknown_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen = _capture_dispatches(monkeypatch)
        gw = _gateway(tmp_path, monkeypatch, _config_with("nosuchprovider/model-x"))
        gw.chat("reasoning", [{"role": "user", "content": "Hi"}])
        assert "response_format" not in seen[0]

    def test_a_cloud_fallback_does_not_receive_the_param(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen = _capture_dispatches(monkeypatch, failures_before_success=3)
        gw = _gateway(tmp_path, monkeypatch, _config_with("ollama/granite4:3b"))
        assert gw.chat("reasoning", [{"role": "user", "content": "Hi"}]) == "from fallback"
        assert seen[0]["response_format"] == {"type": "json_object"}
        assert "response_format" not in seen[-1]

    def test_a_local_fallback_still_receives_the_param(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A guard, not a fail-first test: the gate must not over-reach."""
        seen = _capture_dispatches(monkeypatch, failures_before_success=3)
        cfg = _config_with("ollama/granite4:3b", fallback="ollama/granite4:3b")
        gw = _gateway(tmp_path, monkeypatch, cfg)
        assert gw.chat("reasoning", [{"role": "user", "content": "Hi"}]) == "from fallback"
        assert seen[-1]["response_format"] == {"type": "json_object"}
```

- [ ] **Step 3: Run it and confirm the failures**

Run: `uv run pytest tests/unit/test_gateway_router.py -q -k LocalOnlyExtraParams`
Expected: **3 failed, 2 passed.** `_get_litellm_kwargs` merges `extra_params` unconditionally today (`:401-411`) and nothing removes the key at dispatch, so it reaches every provider: the failing three are `test_dropped_for_a_cloud_provider`, `test_dropped_for_an_unknown_provider` and `test_a_cloud_fallback_does_not_receive_the_param`. Already passing are `test_forwarded_to_a_local_provider` and the local-fallback guard. The "other extra_params" behaviour is deliberately **not** re-tested here — `TestExtraParamsPassThrough.test_keys_appear_in_kwargs` (`tests/unit/test_gateway_router.py:481`) already pins it with the same config and slot. If the failing set differs, stop: the gate is not where you think it is.

- [ ] **Step 4: Implement the gate**

In `src/openreview_cli/gateway/router.py`, add near the other module-level helpers:

```python
def _enforce_local_only_params(
    kwargs: dict[str, Any],
    extra_params: dict[str, Any] | None,
    provider_prefix: str,
) -> None:
    """Enforce local-only request parameters for the provider ACTUALLY dispatched.

    ``response_format`` becomes Ollama's ``format: json``. A provider that does
    not accept it raises in litellm rather than ignoring it, so the key must be
    present for a local provider and absent for every other one.

    This runs at dispatch time, against ``provider_prefix`` — not at build time
    against the slot's configured primary — because a dispatch-time ``model=``
    override or a caller-supplied kwarg can point the call at a provider the
    built kwargs never saw. It also RESTORES the declared value for a local
    target, since an earlier non-local dispatch may have stripped it: the gate
    is per-dispatch, not a permanent mutation.

    Locality reuses ``classify_provider``, the codebase's one notion of local, so
    a localhost custom provider counts as local exactly as it does for tier
    enforcement. An unknown or unclassifiable prefix is remote.
    """
    info = load_registry().get(provider_prefix)
    is_local = False
    if info is not None:
        try:
            is_local = classify_provider(info) == "local"
        except ValueError:
            # No base_url and not flagged local: unclassifiable, so remote.
            is_local = False
    if not is_local:
        # ponytail: one key today — a set-and-loop earns its keep when a second arrives.
        if "response_format" in kwargs:
            kwargs.pop("response_format")
            logger.debug("Dropped local-only response_format for non-local %r", provider_prefix)
        return
    if "response_format" not in kwargs and extra_params and "response_format" in extra_params:
        kwargs["response_format"] = extra_params["response_format"]
```

Call it once per dispatch, inside `_call_with_fallback` — before the first attempt (`:551`), for the provider named by `provider_prefix`:

```python
        extra_params = cfg.get("extra_params")
        _enforce_local_only_params(call_kwargs, extra_params, provider)
```

and again for the fallback leg (`:610`), after the fallback's credentials are applied and before the model is swapped, keyed to `fallback_prefix`:

```python
        _enforce_local_only_params(call_kwargs, extra_params, fallback_prefix)
```

There is deliberately **no** call in `_get_litellm_kwargs`: that dict is built for the slot's configured primary, and a dispatch-time `model=` override or a caller-supplied kwarg can retarget the call after it is built. The second call site is what protects a cloud fallback reached from a local primary — and its restore half is what un-starves a local fallback reached from a cloud primary; without it, the primary's dispatch has already rewritten the kwargs that ride along to the fallback host.

- [ ] **Step 5: Add the shipped default — in `DEFAULT_CONFIG`, not the model class**

`_validate_and_merge` deep-merges `DEFAULT_CONFIG` over the pydantic class defaults (`src/openreview_cli/config/loader.py:209-210`), and the no-config path returns `dict(DEFAULT_CONFIG)` verbatim (`:330`). Changing the `ModelSlot` class default at `:105-107` therefore has **no effect on a real run** — the parameter would be inert and this whole task would measure nothing.

Add it to the `grounding` entry in `DEFAULT_CONFIG` (`:31-35`):

```python
            "grounding": {
                "primary": "ollama/granite4:3b",
                "fallback": None,
                "params": {"temperature": 0.0, "max_tokens": 4000},
                "extra_params": {"response_format": {"type": "json_object"}},
            },
```

Then add the test that pins it, to `tests/unit/test_gateway_models.py`:

```python
def test_the_shipped_default_asks_the_local_grounding_slot_for_json() -> None:
    from openreview_cli.config.loader import DEFAULT_CONFIG

    grounding = DEFAULT_CONFIG["gateway"]["models"]["grounding"]
    assert grounding["extra_params"] == {"response_format": {"type": "json_object"}}
```

- [ ] **Step 6: Prove the default is not inert**

A merge or a pydantic model can silently drop a key, so check the value a run actually sees — not the constant:

```bash
uv run python -c "
from openreview_cli.config.loader import load_config
print(load_config()['gateway']['models']['grounding']['extra_params'])"
```

Expected: `{'response_format': {'type': 'json_object'}}`. If it prints `None`, the parameter never reaches a request — stop and fix that before continuing. (If `load_config` requires an explicit config path, pass the repository default; the printed value is what matters.)

- [ ] **Step 7: Run the tests again**

Run: `uv run pytest tests/unit/test_gateway_router.py -q`
Expected: all pass, including the pre-existing `TestExtraParamsPassThrough` cases and the fallback tests at `:161-238`.

- [ ] **Step 8: Commit the gate on its own**

```bash
git add src/openreview_cli/gateway/router.py tests/unit/test_gateway_router.py
git commit -m "feat(gateway): send response_format to local providers only, fallback included"
```

- [ ] **Step 9: Commit the shipped default separately**

It is the user-visible behaviour change and must be revert-able without the gate.

```bash
git add src/openreview_cli/config/loader.py tests/unit/test_gateway_models.py
git commit -m "feat(config): ask the local grounding slot for JSON by default"
```

---

### Task 4: Count the unreadable answers in the receipt

**Files:**
- Modify: `src/openreview_cli/grounding/discriminator.py` (counter in `__init__`, increments at `:119-120` and at the batch site `:275-300`)
- Modify: `scripts/measure_slm_slots.py` (receipt field near `:519-526`, main receipt near `:719-726`, summary print near `:547`)
- Test: `tests/unit/test_grounding_discriminator.py` (append), `tests/unit/test_grounding_harness.py` (modify the stub)

**Interfaces:**
- Consumes: `CitationGroundingDiscriminator(mode=..., gateway=..., output_dir=...)` and its `ground_claim(...)`
- Produces: `CitationGroundingDiscriminator.unreadable_answers: int` (plain public attribute, zero-initialised); receipt key `unreadable_answers: int`

- [ ] **Step 1: Write the failing discriminator tests**

Append to `tests/unit/test_grounding_discriminator.py`, reusing the existing `mock_gateway` fixture and copying the `ground_claim(...)` call shape from an existing test in that file:

```python
def test_an_unreadable_answer_increments_the_counter(mock_gateway: MagicMock) -> None:
    mock_gateway.chat.return_value = "I cannot help with that."
    d = CitationGroundingDiscriminator(mode="strict", gateway=mock_gateway)

    verdict, _provenances, confidence = d.ground_claim("claim text", "4.3", "clause text")

    assert verdict is GroundingVerdict.UNCERTAIN
    assert confidence == 0.0
    assert d.unreadable_answers == 1


def test_a_readable_answer_leaves_the_counter_at_zero(mock_gateway: MagicMock) -> None:
    d = CitationGroundingDiscriminator(mode="strict", gateway=mock_gateway)

    d.ground_claim("claim text", "4.3", "clause text")

    assert d.unreadable_answers == 0


def test_a_gateway_failure_is_not_counted_as_unreadable(mock_gateway: MagicMock) -> None:
    mock_gateway.chat.side_effect = RuntimeError("connection refused")
    d = CitationGroundingDiscriminator(mode="strict", gateway=mock_gateway)

    verdict, _provenances, confidence = d.ground_claim("claim text", "4.3", "clause text")

    assert verdict is GroundingVerdict.UNCERTAIN
    assert confidence == 0.0
    assert d.unreadable_answers == 0


def test_an_unreadable_batch_counts_every_claim_in_it(
    mock_gateway: MagicMock, sample_report: MagicMock, sample_document: MagicMock
) -> None:
    """The batch path has no early return: it maps missing indices to UNCERTAIN.

    Copy the `ground_report(...)` call shape from an existing test in this file
    (see `test_ground_report_with_clause_text`) so the fixtures are wired the
    same way.
    """
    mock_gateway.chat.return_value = "I cannot help with that."
    d = CitationGroundingDiscriminator(mode="strict", gateway=mock_gateway)

    d.ground_report(sample_report, sample_document)

    # One unreadable answer per claim in the batch the reader could not parse.
    # For this fixture that is every assessment; if the pipeline filters any, use
    # the count the ground_report test you copied already asserts on.
    assert d.unreadable_answers == len(sample_report.assessments)
```

- [ ] **Step 2: Run them and confirm the failures**

Run: `uv run pytest tests/unit/test_grounding_discriminator.py -q -k "counter or unreadable"`
Expected: the increment test FAILS with `AttributeError: 'CitationGroundingDiscriminator' object has no attribute 'unreadable_answers'`; the zero test fails the same way. The gateway-failure test fails identically (the attribute does not exist yet).

- [ ] **Step 3: Implement the counter**

In `src/openreview_cli/grounding/discriminator.py`, declare the counter in `__init__` as a plain public attribute — the class uses plain attributes elsewhere, so a property would be ceremony:

```python
        self.unreadable_answers = 0
```

Increment it in **both** places the reader can return nothing.

Single-claim site (`:119-120`):

```python
        if not results:
            logger.warning("Failed to parse grounding response for claim")
            self.unreadable_answers += 1
            return (GroundingVerdict.UNCERTAIN, [], 0.0)
```

Batch site: `_process_batch` has **no** early return — it maps each missing index onto an UNCERTAIN verdict (`:295-300`). Read `:255-300` first so your variable names match, then count the batch the reader failed to parse, next to its parse call at `:275`:

```python
        parsed = parse_grounding_response(response)
        if not parsed:
            self.unreadable_answers += len(batch)
```

Do **not** increment on the gateway-exception path (`:113-115`): a failed call and an unreadable answer are different faults, and conflating them is exactly what hid this defect inside the "uncertain" column.

- [ ] **Step 4: Run the tests again**

Run: `uv run pytest tests/unit/test_grounding_discriminator.py -q`
Expected: all pass.

- [ ] **Step 5: Write the failing harness test**

Every receipt in `tests/unit/test_grounding_harness.py` is assembled from a stub discriminator, and there are **two** of them — both need the attribute or the new receipt line raises `AttributeError`:

- `_StubDiscriminator` (around `:161`): add `self.unreadable_answers = 0` in its `__init__`.
- `_AlwaysUncertainDiscriminator` (around `:390-405`): add `self.unreadable_answers = 0` in its `__init__` — the all-uncertain test also assembles a receipt.

Then extend the existing end-to-end test that already inspects receipt fields (the one asserting counts and per-generator drops) with one line:

```python
    assert receipt["unreadable_answers"] == 0
```

Do not add a separate placeholder test, and do not touch a variable named `skip_receipt` — it does not exist in that file. If the file has a corpus-absent skip test, add the same one-line assertion there, because the skip receipt builder emits the key at `:519-526` and an untested field can quietly disappear.

- [ ] **Step 6: Run it and confirm it fails**

Run: `uv run pytest tests/unit/test_grounding_harness.py -q`
Expected: FAIL with `KeyError: 'unreadable_answers'`.

- [ ] **Step 7: Surface it in the receipt**

In `scripts/measure_slm_slots.py`:

- In the skip receipt dict (`:519-526`, beside `all_uncertain`): `"unreadable_answers": 0,`
- In the main receipt dict (the block at `:730-764`, which already carries `all_uncertain`; the `all_uncertain` *computation* sits just above at `:719-726`), add:

```python
        "unreadable_answers": discriminator.unreadable_answers,
```

The discriminator is already a single local created at `:675` and used by the run loop at `:693`, so both the loop and the receipt see the same instance — no hoisting is needed.

- In `_print_grounding_summary` (`:533`, in the `uncertain good/bad` line at `:547`), extend the line so the two causes are listed side by side:

```python
        f"uncertain good/bad={receipt['good_uncertain']}/{receipt['bad_uncertain']} "
        f"unreadable={receipt['unreadable_answers']}"
```

- [ ] **Step 8: Run the tests again**

Run: `uv run pytest tests/unit/test_grounding_harness.py tests/unit/test_grounding_discriminator.py -q`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add src/openreview_cli/grounding/discriminator.py scripts/measure_slm_slots.py tests/unit/test_grounding_discriminator.py tests/unit/test_grounding_harness.py
git commit -m "feat(benchmark): count unreadable grounding answers in the receipt"
```

---

### Task 5: Re-measure and correct the published report

**Files:**
- Modify: `docs/benchmarks/results/slot-measurement.md`

**Interfaces:**
- Consumes: the CI job `grounding-accuracy` in `.github/workflows/slm-measurement.yml` (unchanged) and its uploaded artifact `grounding-accuracy-local`
- Produces: a corrected slot report quoting the re-measured numbers

- [ ] **Step 1: Run the whole offline suite**

Run: `uv run pytest -m "fast" -q`
Expected: same pass count as before this branch, plus the new tests. No new failures.

- [ ] **Step 2: Run the pre-commit gate**

Run: `uv run pre-commit run --all-files`
Expected: all hooks pass. (`tests/unit/test_benchmark_receipts.py`'s known issue #180 is not a hook.)

- [ ] **Step 3: Push the branch and dispatch the measurement**

```bash
git push -u origin fix/grounding-answer-reading
gh workflow run slm-measurement.yml --ref fix/grounding-answer-reading
gh run list --workflow=slm-measurement.yml --branch fix/grounding-answer-reading --limit 3
```

The `grounding-accuracy` job takes roughly 15 minutes. A green run that measured nothing is a failure by design — the job exits non-zero on `all_uncertain`, zero positives, zero negatives kept, or fewer units than requested. Do not weaken those conditions to get past them.

- [ ] **Step 4: Compare against the recorded baseline**

Baseline (local arm, `granite4:3b`, limit 20): units 20, positives 20, negatives kept 40, guard drops 0,
`bad_caught 27/40`, `good_accepted 1/20`, uncertain 32 with confidence exactly 0.0, mean latency 7.72 s.

Download the new receipt (`gh run download <run-id> -n grounding-accuracy-local`) and compare field by field,
including the new `unreadable_answers`. Report whatever the run returns. Assume neither that the numbers
improve nor that they reach the cloud arm's (39 of 40 caught, 20 of 20 accepted).

- [ ] **Step 5: Correct the report**

In `docs/benchmarks/results/slot-measurement.md`:

- Replace the sentence claiming the local model "defers rather than decides" and the "19 of 20 good claims"
  figure with the re-measured numbers and the `unreadable_answers` count.
- Add one line to the method section: the grounding reader now unwraps fenced payloads through the shared
  helper and accepts a single object, and the local grounding request asks for JSON only.
- If the local numbers still trail the cloud's after the fix, say so plainly — that is a finding, not a
  failure of the task.

- [ ] **Step 6: Commit and push**

```bash
git add docs/benchmarks/results/slot-measurement.md
git commit -m "docs(benchmark): correct the local grounding figures after the reader fix"
git push
```

---

## Plan Self-Review

**Spec coverage** — every design requirement maps to a task: reader (Task 1), prompt (Task 2), local-only request with both call sites (Task 3), unreadable-answer counter (Task 4), re-measurement and the report correction (Task 5). The design's five mandatory structural tests all live in Task 3 Step 2 and Task 4 Step 1: local provider, cloud provider, unknown provider, cloud fallback, local fallback — plus the batch-of-three shape in Task 1.

**Placeholder scan** — two instructions are deliberately conditional rather than placeholders: Task 3 Step 1 tells the implementer to confirm `COMMON_CONFIG`'s exact text before the `replace()` calls, and Task 3 Step 6 to pass a config path if `load_config` needs one. Inventing either value here would produce a check that fails for the wrong reason. Every other step carries its exact code, command and expected result.

**Type consistency** — `parse_grounding_response` keeps its signature; `unreadable_answers` is a zero-initialised `int` attribute on the discriminator and an `int` receipt field; `_enforce_local_only_params(kwargs, extra_params, provider_prefix)` takes the dict `_call_with_fallback` already holds, the slot's `extra_params`, and the `str` prefix of the provider being dispatched — the same value `_get_litellm_kwargs` resolves the primary from (`:413`) and `load_registry().get` (`:604`) resolves the fallback from.

**Review record** — two independent sub-agents reviewed this plan on 2026-09-30 (one verified anchors and test behaviour against the code, one ran an over-engineering pass). Their blocking findings are folded in: the shipped default had to move to `DEFAULT_CONFIG` because a pydantic class default is dead code; the fallback tests had to survive three primary attempts (`gateway.fallback.retries` is 2), or they would never reach the fallback; `import re` had to be deleted alongside `_extract_json_array`; both harness stubs needed the counter; and the batch-site increment needed its own code and its own test. The 15-shape baseline is now executed rather than traced.

**Known open point carried from the design** — nobody has observed which malformation the local model emits; the new counter is the instrument that answers it. If unreadable answers remain after Task 5, the next lever is the model and its parameters, not the reader.
