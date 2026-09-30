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
| `src/openreview_cli/gateway/router.py` | Builds provider request kwargs; dispatches with fallback | Modify: `_LOCAL_ONLY_PARAMS`, `_strip_local_only_params`, two call sites |
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
Expected: **3 failed, 12 passed.** The failures are `test_bracketed_preamble_before_the_array_parses`, `test_a_single_object_parses_as_one_result`, `test_two_arrays_back_to_back_take_the_first`. If the count differs, stop and re-read the reader before continuing.

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

Delete the whole `_extract_json_array` function (`:150-166`, including its docstring) — its only caller was the code you just replaced. Add in its place:

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
Expected: `test_prompt_permits_a_single_object_and_keeps_the_array_for_batches` FAILS; the other one passes already (the old sentence is present today, so `not in` is currently false → it fails too). Expect **2 failed** before the change.

- [ ] **Step 3: Replace the template's final line**

Replace line `:41`:

```
Respond with a JSON array of these objects, one per claim, in the same order as the input claims.
```

with the exact sentence from Global Constraints (copy it verbatim; it contains no braces).

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
- Modify: `src/openreview_cli/gateway/router.py` (add `_LOCAL_ONLY_PARAMS` and `_strip_local_only_params` near the other module helpers; call it in `_get_litellm_kwargs` after `:373` and in `_call_with_fallback` after `:564`)
- Modify: `src/openreview_cli/config/loader.py` (the `grounding` `ModelSlot` at `:104-106`)
- Test: `tests/unit/test_gateway_router.py` (append a class after `TestExtraParamsPassThrough`)

**Interfaces:**
- Consumes: `ProviderInfo.is_local: bool` (`gateway/models.py:38`); `self._resolve_provider_info(slot)` (`router.py:189`); `load_registry().get(prefix)` (`:560`); the existing test helper `_gateway(tmp_path, monkeypatch, config)` and constant `COMMON_CONFIG`.
- Produces: module-level `_LOCAL_ONLY_PARAMS: frozenset[str]` and `_strip_local_only_params(kwargs: dict[str, Any], info: ProviderInfo | None) -> None`.

- [ ] **Step 1: Read the existing fallback test pattern**

Read `tests/unit/test_gateway_router.py:161-238`. Note two things you will reuse: the config is built with `COMMON_CONFIG.replace(...)`, and a fallback is simulated by `monkeypatch.setattr(router_mod, "completion", failing_then_ok)` where the stub records each call's kwargs and raises on the first call. Also read `COMMON_CONFIG` (around `:81-101`) and copy its exact text for the two lines the helpers below replace — if those lines read differently, adjust the `replace()` arguments to match, keeping the same intent.

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


class TestLocalOnlyExtraParams:
    """`response_format` is a local-only hint; a cloud provider must never see it.

    An unsupported parameter raises in litellm rather than being dropped, so a
    leak here turns a degraded parse into a hard failure.
    """

    def test_forwarded_for_a_local_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gw = _gateway(tmp_path, monkeypatch, _config_with("ollama/granite4:3b"))
        kwargs = gw._get_litellm_kwargs("reasoning")
        assert kwargs.get("response_format") == {"type": "json_object"}

    def test_dropped_for_a_cloud_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gw = _gateway(tmp_path, monkeypatch, _config_with("openai/gpt-4"))
        kwargs = gw._get_litellm_kwargs("reasoning")
        assert "response_format" not in kwargs

    def test_dropped_for_an_unknown_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gw = _gateway(tmp_path, monkeypatch, _config_with("nosuchprovider/model-x"))
        kwargs = gw._get_litellm_kwargs("reasoning")
        assert "response_format" not in kwargs

    def test_other_extra_params_are_still_forwarded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        kwargs = gw._get_litellm_kwargs("reasoning")
        assert kwargs.get("top_p") == 0.9

    def test_a_cloud_fallback_does_not_receive_the_param(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import openreview_cli.gateway.router as router_mod

        seen: list[dict] = []

        def failing_then_ok(**kwargs) -> str:
            seen.append(dict(kwargs))
            if len(seen) == 1:
                raise RuntimeError("primary unavailable")
            return "from fallback"

        monkeypatch.setattr(router_mod, "completion", failing_then_ok)
        gw = _gateway(tmp_path, monkeypatch, _config_with("ollama/granite4:3b"))
        assert gw.chat("reasoning", [{"role": "user", "content": "Hi"}]) == "from fallback"
        assert seen[0].get("response_format") == {"type": "json_object"}
        assert "response_format" not in seen[-1]

    def test_a_local_fallback_still_receives_the_param(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import openreview_cli.gateway.router as router_mod

        seen: list[dict] = []

        def failing_then_ok(**kwargs) -> str:
            seen.append(dict(kwargs))
            if len(seen) == 1:
                raise RuntimeError("primary unavailable")
            return "from fallback"

        monkeypatch.setattr(router_mod, "completion", failing_then_ok)
        cfg = _config_with("ollama/granite4:3b", fallback="ollama/granite4:3b")
        gw = _gateway(tmp_path, monkeypatch, cfg)
        assert gw.chat("reasoning", [{"role": "user", "content": "Hi"}]) == "from fallback"
        assert seen[-1].get("response_format") == {"type": "json_object"}
```

- [ ] **Step 3: Run it and confirm the failures**

Run: `uv run pytest tests/unit/test_gateway_router.py -q -k LocalOnlyExtraParams`
Expected: the two local cases FAIL (the key is absent for a local provider today) and the fallback-to-cloud case FAILS (the key reaches the cloud fallback today). The two "dropped" cases may already pass — that is the correct baseline, not a problem.

- [ ] **Step 4: Implement the strip**

In `src/openreview_cli/gateway/router.py`, add near the other module-level constants:

```python
_LOCAL_ONLY_PARAMS = frozenset({"response_format"})


def _strip_local_only_params(kwargs: dict[str, Any], info: ProviderInfo | None) -> None:
    """Drop request parameters that only a locally-hosted provider may receive.

    ``response_format`` becomes Ollama's ``format: json``. A provider that does
    not accept it raises rather than ignoring it, so the key is forwarded only
    when the provider actually runs locally; an unknown provider counts as remote.
    """
    if info is not None and info.is_local:
        return
    for key in _LOCAL_ONLY_PARAMS:
        if key in kwargs:
            kwargs.pop(key)
            logger.debug("Dropped local-only param %s for a non-local provider", key)
```

Call it in `_get_litellm_kwargs` immediately after `info = self._resolve_provider_info(slot)` (`:373`):

```python
        info = self._resolve_provider_info(slot)
        _strip_local_only_params(kwargs, info)
```

Call it in `_call_with_fallback` after the fallback's credentials are applied and before the model is swapped (`:564`, above `call_kwargs["model"] = fallback`):

```python
        _strip_local_only_params(call_kwargs, info)
```

The second call site is what protects a cloud fallback reached from a local primary; without it the primary's merged `extra_params` ride along to the fallback host.

- [ ] **Step 5: Add the shipped default**

In `src/openreview_cli/config/loader.py`, the `grounding` slot at `:104-106` becomes:

```python
        grounding: ModelSlot = ModelSlot(
            primary="ollama/granite4:3b",
            params=ModelParams(temperature=0.0, max_tokens=4000),
            extra_params={"response_format": {"type": "json_object"}},
        )
```

- [ ] **Step 6: Run the tests again**

Run: `uv run pytest tests/unit/test_gateway_router.py -q`
Expected: all pass, including the pre-existing `TestExtraParamsPassThrough` cases and the fallback tests at `:161-238`.

- [ ] **Step 7: Commit**

```bash
git add src/openreview_cli/gateway/router.py src/openreview_cli/config/loader.py tests/unit/test_gateway_router.py
git commit -m "feat(gateway): send response_format to local providers only, fallback included"
```

---

### Task 4: Count the unreadable answers in the receipt

**Files:**
- Modify: `src/openreview_cli/grounding/discriminator.py` (counter in `__init__`, increments at `:119-120` and at the batch site `:275-300`)
- Modify: `scripts/measure_slm_slots.py` (receipt field near `:519-526`, main receipt near `:719-726`, summary print near `:547`)
- Test: `tests/unit/test_grounding_discriminator.py` (append), `tests/unit/test_grounding_harness.py` (modify the stub)

**Interfaces:**
- Consumes: `CitationGroundingDiscriminator(mode=..., gateway=..., output_dir=...)` and its `ground_claim(...)`
- Produces: `CitationGroundingDiscriminator.unreadable_answers: int` (read-only property over a private counter); receipt key `unreadable_answers: int`

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
```

- [ ] **Step 2: Run them and confirm the failures**

Run: `uv run pytest tests/unit/test_grounding_discriminator.py -q -k counter or unreadable`
Expected: the increment test FAILS with `AttributeError: 'CitationGroundingDiscriminator' object has no attribute 'unreadable_answers'`; the zero test fails the same way. The gateway-failure test fails identically (the attribute does not exist yet).

- [ ] **Step 3: Implement the counter**

In `src/openreview_cli/grounding/discriminator.py`:

In `__init__`, alongside the other instance state:

```python
        self._unreadable_answers = 0
```

Add the read-only accessor next to the other properties:

```python
    @property
    def unreadable_answers(self) -> int:
        """Answers the reader could not parse.

        Counted separately from a gateway failure: both end in an UNCERTAIN
        verdict, and conflating them is what hid this defect inside the
        "uncertain" column of the measurement receipt.
        """
        return self._unreadable_answers
```

Increment exactly where the reader returns nothing — the single-claim site (`:119-120`) and the batch site (`:275` onward, where `_process_batch` handles the same empty result):

```python
        if not results:
            logger.warning("Failed to parse grounding response for claim")
            self._unreadable_answers += 1
            return (GroundingVerdict.UNCERTAIN, [], 0.0)
```

Do **not** increment on the gateway-exception path (`:113-115`).

- [ ] **Step 4: Run the tests again**

Run: `uv run pytest tests/unit/test_grounding_discriminator.py -q`
Expected: all pass.

- [ ] **Step 5: Write the failing harness test**

In `tests/unit/test_grounding_harness.py`, the end-to-end test's stub discriminator must expose the attribute (a `MagicMock` would otherwise hand the receipt a mock). Set `stub.unreadable_answers = 0` where the stub is created, and add to the receipt assertions:

```python
def test_receipt_reports_unreadable_answers(...) -> None:
    # same setup as the existing end-to-end grounding test in this file
    assert receipt["unreadable_answers"] == 0
```

Also copy the assertion into the existing end-to-end test if that is where the fixture is cheapest to reuse, and add one line asserting the skip receipt carries the key:

```python
    assert "unreadable_answers" in skip_receipt
```

- [ ] **Step 6: Run it and confirm it fails**

Run: `uv run pytest tests/unit/test_grounding_harness.py -q`
Expected: FAIL with `KeyError: 'unreadable_answers'`.

- [ ] **Step 7: Surface it in the receipt**

In `scripts/measure_slm_slots.py`:

- In the skip receipt dict (`:519-526`, beside `all_uncertain`): `"unreadable_answers": 0,`
- In the main receipt, where the confused-matrix fields are assembled (`:719-726`, beside `all_uncertain`):

```python
    receipt["unreadable_answers"] = discriminator.unreadable_answers
```

using the same discriminator instance the run loop calls `ground_claim` on (`:693`); if that instance is constructed inside a helper, hoist it so the loop and the receipt share one object.

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

**Placeholder scan** — one instruction is deliberately conditional rather than a placeholder: Task 3 Step 1 tells the implementer to confirm `COMMON_CONFIG`'s exact text before the `replace()` calls, because inventing that text here would produce a test that fails for the wrong reason. Every other step carries its exact code, command and expected result.

**Type consistency** — `parse_grounding_response` keeps its signature; `unreadable_answers` is an `int` property on the discriminator and an `int` receipt field; `_strip_local_only_params(kwargs, info)` takes the dict that `_get_litellm_kwargs` and `_call_with_fallback` both already hold, and `ProviderInfo | None` matches what `_resolve_provider_info` (`:373`) and `load_registry().get` (`:560`) return.

**Known open point carried from the design** — nobody has observed which malformation the local model emits; the new counter is the instrument that answers it. If unreadable answers remain after Task 5, the next lever is the model and its parameters, not the reader.
