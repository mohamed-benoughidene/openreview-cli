"""Spec 035 T1.3 — ``gateway test`` only offers the three surviving sockets.

The per-slot smoke test used to branch on the removed sockets (``embedding``,
``reranking``, ``graph``) and a removed socket fell through silently. These tests
pin the reduced surface, and that a socket the command cannot smoke-test fails
with one clean line instead of a stack trace.
"""

from __future__ import annotations

from typing import Any

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

SURVIVING_SLOTS = ("extraction", "reasoning", "grounding")
REMOVED_SLOTS = ("embedding", "reranking", "graph")


def _fake_gateway_class(calls: list[str]) -> Any:
    """A Gateway stand-in that records which transport the command reached for."""

    class _FakeGateway:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def chat(self, slot: str, *_args: Any, **_kwargs: Any) -> str:
            calls.append(f"chat:{slot}")
            return "OK"

        def embed(self, slot: str, *_args: Any, **_kwargs: Any) -> list[list[float]]:
            calls.append(f"embed:{slot}")
            return [[0.0]]

        def rerank(self, slot: str, *_args: Any, **_kwargs: Any) -> list[Any]:
            calls.append(f"rerank:{slot}")
            return []

    return _FakeGateway


@pytest.mark.parametrize("slot", SURVIVING_SLOTS)
def test_surviving_slot_is_accepted(monkeypatch: pytest.MonkeyPatch, slot: str) -> None:
    calls: list[str] = []
    monkeypatch.setattr("openreview_cli.gateway.router.Gateway", _fake_gateway_class(calls))

    result = runner.invoke(app, ["gateway", "test", slot])

    assert result.exit_code == 0, result.output
    assert "OK" in result.output
    assert calls == [f"chat:{slot}"]


@pytest.mark.parametrize("slot", REMOVED_SLOTS)
def test_removed_slot_errors_cleanly(monkeypatch: pytest.MonkeyPatch, slot: str) -> None:
    calls: list[str] = []
    monkeypatch.setattr("openreview_cli.gateway.router.Gateway", _fake_gateway_class(calls))

    result = runner.invoke(app, ["gateway", "test", slot])

    assert result.exit_code == 1
    # No transport is exercised for a socket the command cannot test.
    assert calls == []
    output_lines = [line for line in result.output.splitlines() if line.strip()]
    assert len(output_lines) == 1, result.output
    assert slot in output_lines[0]
    assert "Traceback" not in result.output
