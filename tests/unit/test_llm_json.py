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
