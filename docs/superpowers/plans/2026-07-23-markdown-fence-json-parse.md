# Markdown-Fence JSON Parsing Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip markdown code fences before `json.loads` in every LLM-response parser, via one shared helper, killing the silent-fallback bug class from `specs/retro-markdown-fence-bug.md`.

**Architecture:** New top-level module `openreview_cli/llm_json.py` exposes `strip_fences(text) -> str` (stdlib-only, no package imports — safe for benchmark/bilateral/review/TUI). Four call sites adopt it. Extraction's inline stripping (proven semantics, commit `91b2951`) is deduplicated onto the same helper.

**Tech Stack:** Python 3.12, pytest, stdlib `json` only. No new dependencies.

## Global Constraints

- Python 3.12 pinned. No new dependencies. No `pip`/`poetry` — `uv` only.
- TDD: failing test written BEFORE implementation, per `DevelopmentSetup.md`.
- Pipeline peak memory < 110 MB (floor). No full-document loads introduced here.
- `mypy --strict` clean, `ruff check` clean.
- Do NOT run memory tests inside the general suite (spaCy GC hang). Memory tests run solo: `uv run pytest -m memory -q --timeout=300` — not needed here, no memory-sensitive change.
- Conventional Commits: `fix:` prefix.
- Import direction: `bilateral → review` exists and is fine; `benchmark` must NOT gain a dependency on `review` — helper lives top-level to prevent that.

## Bug Sites (verified facts)

| Site | Current code | Fallback behavior |
|---|---|---|
| `src/openreview_cli/review/prompts.py:12` `_parse_json` | `json.loads(raw)` | silent fallback dict (QA + extraction/QA prompt parsers) |
| `src/openreview_cli/bilateral/comparison.py:137` `_parse_comparison_response` | `json.loads(raw)` | silent fallback dict with `"error"` key |
| `src/openreview_cli/benchmark/baseline.py:89` `build_gateway_pipeline.pipeline` | `json.loads(response)` | raises `ValueError` (loud) |
| `src/openreview_cli/review/extraction.py:148-161` `_parse_response` | inline fence-strip (correct) | dedup target only |

`grounding/prompts.py:_extract_json_array` already handles fences via regex — DO NOT TOUCH.

---

### Task 1: Shared `strip_fences` helper

**Files:**
- Create: `src/openreview_cli/llm_json.py`
- Test: `tests/unit/test_llm_json.py`

**Interfaces:**
- Produces: `openreview_cli.llm_json.strip_fences(text: str) -> str` — consumed by Tasks 2, 3, 4, 5.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_llm_json.py`:

```python
"""Unit tests for openreview_cli.llm_json.strip_fences."""

from openreview_cli.llm_json import strip_fences


def test_strips_json_fence() -> None:
    raw = '```json\n{\n  "a": 1\n}\n```'
    assert strip_fences(raw) == '{\n  "a": 1\n}'


def test_strips_bare_fence() -> None:
    raw = '```\n{"a": 1}\n```'
    assert strip_fences(raw) == '{"a": 1}'


def test_plain_json_passthrough() -> None:
    raw = '{"a": 1}'
    assert strip_fences(raw) == '{"a": 1}'


def test_surrounding_whitespace() -> None:
    raw = '  \n```json\n{"a": 1}\n```\n  '
    assert strip_fences(raw) == '{"a": 1}'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_llm_json.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'openreview_cli.llm_json'`

- [ ] **Step 3: Write minimal implementation**

Create `src/openreview_cli/llm_json.py`:

```python
"""Shared helpers for parsing LLM JSON responses.

LLM providers (e.g. Claude via OpenRouter) frequently wrap JSON payloads in
markdown code fences (```json ... ```). ``json.loads`` fails on the leading
backticks, and parsers that swallow ``JSONDecodeError`` then return silent
fallback values. Every gateway-response parser must strip fences via
``strip_fences`` before calling ``json.loads``.

See specs/retro-markdown-fence-bug.md.
"""

from __future__ import annotations


def strip_fences(text: str) -> str:
    """Strip a markdown code fence wrapping the whole payload.

    Handles `````json\\n{...}\\n````` and `````\\n{...}\\n`````. Returns the
    input whitespace-stripped when no fence is present. Semantics identical
    to the inline stripping validated end-to-end against real providers in
    ``review/extraction.py`` (commit ``91b2951``).
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        first_nl = stripped.find("\n")
        if first_nl >= 0:
            stripped = stripped[first_nl + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[:-3].strip()
    return stripped
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_llm_json.py -q`
Expected: 4 passed

---

### Task 2: `review/prompts.py:_parse_json` strips fences (fixes QA agent + both prompt parsers)

**Files:**
- Modify: `src/openreview_cli/review/prompts.py:9-15`
- Test: `tests/unit/test_prompts.py` (append)

**Interfaces:**
- Consumes: `openreview_cli.llm_json.strip_fences` (Task 1)
- Produces: unchanged signatures — `_parse_json(raw: str, fallback: dict[str, Any]) -> dict[str, Any]`, `parse_qa_response(raw: str) -> dict[str, Any]`, `parse_extraction_response(raw: str) -> dict[str, Any]`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_prompts.py` (match existing import style in that file):

```python
def test_parse_qa_response_strips_markdown_fences() -> None:
    """Regression: real providers wrap JSON in ```json fences (see retro doc)."""
    from openreview_cli.review.prompts import parse_qa_response

    raw = (
        "```json\n{\n"
        '  "verdict": "agree",\n'
        '  "revised_position": null,\n'
        '  "rationale": "checks out",\n'
        '  "citation_valid": true,\n'
        '  "position_valid": true,\n'
        '  "category_valid": true,\n'
        '  "confidence_valid": true\n'
        "}\n```"
    )
    result = parse_qa_response(raw)
    assert result["verdict"] == "agree"
    assert result["citation_valid"] is True
    assert result["rationale"] == "checks out"


def test_parse_extraction_response_strips_markdown_fences() -> None:
    """Regression: real providers wrap JSON in ```json fences (see retro doc)."""
    from openreview_cli.review.prompts import parse_extraction_response

    raw = (
        "```json\n{\n"
        '  "position": "preferred",\n'
        '  "confidence": 0.9,\n'
        '  "citation": "clause 3.2",\n'
        '  "category_match": true\n'
        "}\n```"
    )
    result = parse_extraction_response(raw)
    assert result["position"] == "preferred"
    assert result["confidence"] == 0.9
    assert result["citation"] == "clause 3.2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_prompts.py -q`
Expected: 2 FAIL — both return fallback dicts (`verdict == "uncertain"`, `position == "no-match"`)

- [ ] **Step 3: Minimal implementation**

In `src/openreview_cli/review/prompts.py`, add import after line 6 (`from typing import Any`):

```python
from openreview_cli.llm_json import strip_fences
```

Change `_parse_json` body line 12 from `data = json.loads(raw)` to:

```python
        data = json.loads(strip_fences(raw))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_prompts.py tests/unit/test_qa_agent.py -q`
Expected: all pass (QA agent tests mock at gateway level, unaffected)

---

### Task 3: `bilateral/comparison.py:_parse_comparison_response` strips fences

**Files:**
- Modify: `src/openreview_cli/bilateral/comparison.py:137` (+ import block lines 14-25)
- Test: `tests/unit/test_bilateral_comparison.py` (append)

**Interfaces:**
- Consumes: `openreview_cli.llm_json.strip_fences` (Task 1)
- Produces: unchanged signature — `_parse_comparison_response(raw: str) -> dict[str, Any]`. Fallback dict contains `"error"` key; success dict does not.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_bilateral_comparison.py`:

```python
def test_parse_comparison_response_strips_markdown_fences() -> None:
    """Fenced JSON must parse identically to bare JSON.

    Regression: real providers wrap JSON in ```json fences; the fallback
    silently returned DivergenceVerdict.uncertain (see retro doc).
    """
    from openreview_cli.bilateral.comparison import _parse_comparison_response

    bare = '{"divergence": "no_divergence", "confidence": 0.9, "rationale": "same"}'
    fenced = f"```json\n{bare}\n```"
    fenced_result = _parse_comparison_response(fenced)
    assert "error" not in fenced_result
    assert fenced_result == _parse_comparison_response(bare)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_bilateral_comparison.py::test_parse_comparison_response_strips_markdown_fences -q`
Expected: FAIL — `"error" in fenced_result` (fallback returned)

- [ ] **Step 3: Minimal implementation**

In `src/openreview_cli/bilateral/comparison.py`, add import (module already imports from `openreview_cli.review._gateway`, so `openreview_cli.llm_json` is consistent):

```python
from openreview_cli.llm_json import strip_fences
```

Change line 137 from `data = json.loads(raw)` to:

```python
        data = json.loads(strip_fences(raw))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_bilateral_comparison.py tests/unit/test_pipeline_comparison.py -q`
Expected: all pass

---

### Task 4: `benchmark/baseline.py` strips fences

**Files:**
- Modify: `src/openreview_cli/benchmark/baseline.py:89` (+ import block lines 3-10)
- Test: create `tests/unit/test_benchmark_baseline.py`

**Interfaces:**
- Consumes: `openreview_cli.llm_json.strip_fences` (Task 1). NOTE: import the top-level helper only — do NOT import from `openreview_cli.review` (benchmark must stay decoupled).
- Produces: unchanged — `build_gateway_pipeline(mode: str) -> Any`; inner `pipeline(text, category) -> dict[str, object]`; still raises `ValueError` on genuinely non-JSON responses.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_benchmark_baseline.py`:

```python
"""Regression tests: real-baseline pipeline tolerates markdown-fenced JSON."""

from typing import Any

import pytest

from openreview_cli.benchmark.baseline import build_gateway_pipeline


class _FakeGateway:
    """Stand-in for openreview_cli.gateway.router.Gateway."""

    def __init__(self, response: str) -> None:
        self._response = response

    def chat(self, slot: str, messages: list[dict[str, str]], **kwargs: Any) -> str:
        return self._response


def test_real_baseline_strips_markdown_fences(monkeypatch: pytest.MonkeyPatch) -> None:
    from openreview_cli.gateway import router as gateway_router

    monkeypatch.setattr(
        gateway_router,
        "Gateway",
        lambda: _FakeGateway('```json\n{"position": "preferred"}\n```'),
    )
    pipeline = build_gateway_pipeline("precheck")
    result = pipeline("clause text", "category")
    assert result == {"position": "preferred"}


def test_real_baseline_raises_on_non_json(monkeypatch: pytest.MonkeyPatch) -> None:
    from openreview_cli.gateway import router as gateway_router

    monkeypatch.setattr(gateway_router, "Gateway", lambda: _FakeGateway("not json"))
    pipeline = build_gateway_pipeline("precheck")
    with pytest.raises(ValueError, match="structured JSON"):
        pipeline("clause text", "category")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_benchmark_baseline.py -q`
Expected: 1 FAIL (`test_real_baseline_strips_markdown_fences` raises `ValueError`), 1 PASS

- [ ] **Step 3: Minimal implementation**

In `src/openreview_cli/benchmark/baseline.py`, add import:

```python
from openreview_cli.llm_json import strip_fences
```

Change line 89 from `result = json.loads(response)` to:

```python
            result = json.loads(strip_fences(response))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_benchmark_baseline.py -q`
Expected: 2 passed

---

### Task 5: Dedup `extraction.py` onto shared helper + full verification sweep

**Files:**
- Modify: `src/openreview_cli/review/extraction.py:148-161` (+ import block)

**Interfaces:**
- Consumes: `openreview_cli.llm_json.strip_fences` (Task 1)
- Produces: unchanged — `_parse_response(raw: str) -> dict[str, Any]`. Guarded by existing tests `tests/unit/test_extraction_agent.py:125-165`.

- [ ] **Step 1: Existing tests already cover this refactor** — no new test needed (the three fence tests at `test_extraction_agent.py:125-165` pin the behavior).

- [ ] **Step 2: Refactor**

In `src/openreview_cli/review/extraction.py`, add import:

```python
from openreview_cli.llm_json import strip_fences
```

Replace the inline block (lines 149-161: `stripped = raw.strip()` plus the whole `if stripped.startswith("```"):` block) with:

```python
    stripped = strip_fences(raw)
```

Leave the `try: data = json.loads(stripped)` and everything after untouched.

- [ ] **Step 3: Run extraction tests**

Run: `uv run pytest tests/unit/test_extraction_agent.py -q`
Expected: all pass

- [ ] **Step 4: Full verification sweep**

Run (in order):
1. `uv run pytest tests/unit/ -q` — Expected: all pass
2. `uv run pytest tests/integration/ -q -m "not slow"` — Expected: all pass
3. `uv run ruff check .` — Expected: no findings
4. `uv run ruff format --check .` — Expected: no diffs
5. `uv run mypy src/ tests/` — Expected: no errors

Do NOT run `-m memory` tests (spaCy GC hang under cumulative load; no memory-sensitive change in this plan).

---

## Self-Review Notes

- Spec coverage: all 3 unprotected sites + dedup covered; grounding verified already-safe and excluded.
- No placeholders: every code step contains complete code.
- Type consistency: `strip_fences(text: str) -> str` used identically in Tasks 2-5.
- Deliberately skipped: prose-around-JSON extraction (grounding-style regex) — no current parser needs it, fallback path is acceptable (YAGNI). Add when a provider is observed emitting prose + fenced JSON to these endpoints.
