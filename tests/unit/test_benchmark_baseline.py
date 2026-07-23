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
        lambda: _FakeGateway('```json\n{"label": "entailment"}\n```'),
    )
    pipeline = build_gateway_pipeline("precheck")
    result = pipeline("clause text", "category")
    assert result == {
        "start": 0,
        "end": 0,
        "category": "category",
        "label": "entailment",
        "match": True,
    }


def test_real_baseline_raises_on_non_json(monkeypatch: pytest.MonkeyPatch) -> None:
    from openreview_cli.gateway import router as gateway_router

    monkeypatch.setattr(gateway_router, "Gateway", lambda: _FakeGateway("not json"))
    pipeline = build_gateway_pipeline("precheck")
    with pytest.raises(ValueError, match="structured JSON"):
        pipeline("clause text", "category")
