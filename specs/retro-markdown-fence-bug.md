# Retro: Markdown-Fence JSON Parsing Bug

## What happened

LLM (Claude via OpenRouter) wraps JSON responses in ````` ```json\n{...}\n``` ````` code fences.
`extraction.py:_parse_response` called `json.loads(raw)` directly without stripping fences.
First backtick caused `json.JSONDecodeError`, and the fallback returned `citation=""`,
`position="uncertain"`, `confidence=0.0` for every clause.

## Impact

Every review run before this fix had silently empty extraction results. Rule-based
category matching still worked (heading match is before the LLM call), but all
LLM-driven assessment fields — position, confidence, citation — were silently zeroed
across every document. Grounding then received `citation=""`, fell back to full
clause text, and trivially verified the tautology.

## Why unit tests didn't catch it

Unit tests mock the gateway and return raw unwrapped JSON
(`'{"position": "preferred", ...}'`). Real providers return markdown-wrapped JSON.
The difference between mock and reality is a ````` ```json ````` prefix and ````` ``` ````` suffix.

## How it was caught

Real end-to-end test with OpenRouter + Claude, run during grounding fix validation
(2026-07-22). Diagnostic printing of the LLM's raw response revealed the markdown
wrapping.

## Fix

`_parse_response` in `src/openreview_cli/review/extraction.py` (line 146) now strips
````` ```json ````` / ````` ``` ````` fences before `json.loads()`. Commit `91b2951`.

## Lesson

Mock-based unit tests cannot catch integration-format issues. E2E tests with real
providers are the only reliable way to validate LLM response parsing. When a test
uses `MagicMock.return_value`, the contract being tested is the mock format, not
the real provider format.
