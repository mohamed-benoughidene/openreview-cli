from pathlib import Path

import pytest

from openreview_cli.gateway.cost import CostTracker

FAKE_ENTRY_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


class MockUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class MockResponse:
    def __init__(self, usage: object = None) -> None:
        self.usage = usage


def test_log_call_stores_token_counts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, int] = {}

    def fake_log_cost(
        db_path: object,
        session_id: str,
        model: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_cents: int,
        slot: str | None = None,
    ) -> str:
        captured["prompt_tokens"] = prompt_tokens
        captured["completion_tokens"] = completion_tokens
        captured["cost_cents"] = cost_cents
        return FAKE_ENTRY_ID

    monkeypatch.setattr("openreview_cli.gateway.cost.db_log_cost", fake_log_cost)
    monkeypatch.setattr("openreview_cli.gateway.cost.completion_cost", lambda r: 0.05)
    tracker = CostTracker(tmp_path)
    response = MockResponse(MockUsage(150, 50))
    tracker.log_call("session-1", "slot-1", "gpt-4", "openai", response)
    assert captured["prompt_tokens"] == 150
    assert captured["completion_tokens"] == 50


def test_log_call_calculates_cost_cents(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, int] = {}

    def fake_log_cost(
        db_path: object,
        session_id: str,
        model: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_cents: int,
        slot: str | None = None,
    ) -> str:
        captured["cost_cents"] = cost_cents
        return FAKE_ENTRY_ID

    monkeypatch.setattr("openreview_cli.gateway.cost.db_log_cost", fake_log_cost)
    monkeypatch.setattr("openreview_cli.gateway.cost.completion_cost", lambda r: 0.05)
    tracker = CostTracker(tmp_path)
    response = MockResponse(MockUsage(100, 50))
    tracker.log_call("session-2", None, "gpt-4", "openai", response)
    assert captured["cost_cents"] == 5


def test_log_call_returns_entry_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("openreview_cli.gateway.cost.db_log_cost", lambda *a, **kw: FAKE_ENTRY_ID)
    monkeypatch.setattr("openreview_cli.gateway.cost.completion_cost", lambda r: 0.05)
    tracker = CostTracker(tmp_path)
    response = MockResponse(MockUsage(10, 5))
    entry_id = tracker.log_call("session-3", "slot-3", "gpt-4", "openai", response)
    assert isinstance(entry_id, str)
    assert len(entry_id) > 0


def test_get_session_cost_returns_expected_dict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    expected = {"prompt_tokens": 150, "completion_tokens": 50, "cost_cents": 5}
    monkeypatch.setattr("openreview_cli.gateway.cost.db_get_session_cost", lambda p, s: expected)
    tracker = CostTracker(tmp_path)
    result = tracker.get_session_cost("session-1")
    assert result == expected


def test_log_call_empty_usage_defaults_to_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, int] = {}

    def fake_log_cost(
        db_path: object,
        session_id: str,
        model: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_cents: int,
        slot: str | None = None,
    ) -> str:
        captured["prompt_tokens"] = prompt_tokens
        captured["completion_tokens"] = completion_tokens
        captured["cost_cents"] = cost_cents
        return FAKE_ENTRY_ID

    monkeypatch.setattr("openreview_cli.gateway.cost.db_log_cost", fake_log_cost)
    tracker = CostTracker(tmp_path)
    response = MockResponse()
    tracker.log_call("session-4", None, "gpt-4", "openai", response)
    assert captured["prompt_tokens"] == 0
    assert captured["completion_tokens"] == 0
    assert captured["cost_cents"] == 0
