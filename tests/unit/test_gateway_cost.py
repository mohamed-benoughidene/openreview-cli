from pathlib import Path
from typing import Any

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


def test_log_call_writes_row_without_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec 035 crit. 2: a cost-log call without a session_id actually writes a
    row to the database, instead of silently swallowing the cost."""
    import sqlite3

    from openreview_cli.storage.database import init_database

    db_path = tmp_path / "cost_test.db"
    init_database(db_path)

    monkeypatch.setattr("openreview_cli.gateway.cost.completion_cost", lambda r: 0.05)
    tracker = CostTracker(db_path)
    response = MockResponse(MockUsage(prompt_tokens=100, completion_tokens=50))
    entry_id = tracker.log_call(
        session_id=None,
        slot="test-slot",
        model="gpt-4",
        provider="openai",
        response=response,
    )
    assert isinstance(entry_id, str), "log_call must return a valid entry_id"

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM cost_logs WHERE id = ?", (entry_id,)).fetchone()
        assert row is not None, "row must exist in cost_logs"
        assert row["session_id"] == ""
        assert row["slot"] == "test-slot"
        assert row["model"] == "gpt-4"
        assert row["provider"] == "openai"
        assert row["prompt_tokens"] == 100
        assert row["completion_tokens"] == 50
        assert row["cost_cents"] == 5  # 0.05 USD → 5 cents
    finally:
        conn.close()


# ── Phase-6 B3: cost-limit enforcement fix (FR-6 / US4 / US5) ──


def _make_gateway(config: dict[str, Any], data_path: Path) -> Any:
    """Build a Gateway with the real _check_cost_limits bound.

    Uses Gateway.__new__(Gateway) to skip __init__ (which would
    resolve real config paths) and binds _config and _data_path
    directly. This matches the existing pattern in
    test_gateway_router.py:808-812.
    """
    from openreview_cli.gateway.router import Gateway

    gw = Gateway.__new__(Gateway)
    gw._config = config
    gw._data_path = data_path
    return gw


def test_b3_over_limit_daily_calls_cost_limit_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """US4/AC3 + FR-017: over daily limit must exit 6 with the
    spec-mandated message. The test patches cost_limit_error to
    raise SystemExit(6) so the assertion proves the production
    code calls the helper with the right message.
    """
    called: dict[str, str] = {}

    def fake_cost_limit_error(message: str) -> None:
        called["message"] = message
        raise SystemExit(6)

    monkeypatch.setattr("openreview_cli.gateway.router.cost_limit_error", fake_cost_limit_error)

    def daily_over(db: Path, cents: int) -> bool:
        return False  # over limit

    monkeypatch.setattr(
        "openreview_cli.gateway.router.check_daily_limit",
        daily_over,
    )
    # Prevent the real session-limit check from being reached,
    # so the test isolates the daily-limit path.

    def session_under(db: Path, sid: str, cents: int) -> bool:
        return True

    monkeypatch.setattr(
        "openreview_cli.gateway.router.check_session_limit",
        session_under,
    )

    # Cents values are integer cents: 1000 cents == $10.00,
    # 100 cents == $1.00.
    gw = _make_gateway(
        {"gateway": {"cost_limits": {"daily_cents": 1000, "per_review_cents": 100}}},
        tmp_path / "db.sqlite",
    )
    with pytest.raises(SystemExit) as exc_info:
        gw._check_cost_limits("session-1")
    assert exc_info.value.code == 6
    assert "Daily cost limit reached" in called["message"]
    assert "$10.00" in called["message"]


def test_b3_over_limit_session_calls_cost_limit_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """US4/AC4 + FR-016: over per-review limit must exit 6 with
    the spec-mandated message.
    """
    called: dict[str, str] = {}

    def fake_cost_limit_error(message: str) -> None:
        called["message"] = message
        raise SystemExit(6)

    monkeypatch.setattr("openreview_cli.gateway.router.cost_limit_error", fake_cost_limit_error)

    def daily_under(db: Path, cents: int) -> bool:
        return True  # daily ok

    def session_over(db: Path, sid: str, cents: int) -> bool:
        return False  # session over limit

    monkeypatch.setattr(
        "openreview_cli.gateway.router.check_daily_limit",
        daily_under,
    )
    monkeypatch.setattr(
        "openreview_cli.gateway.router.check_session_limit",
        session_over,
    )

    gw = _make_gateway(
        {"gateway": {"cost_limits": {"daily_cents": 1000, "per_review_cents": 100}}},
        tmp_path / "db.sqlite",
    )
    with pytest.raises(SystemExit) as exc_info:
        gw._check_cost_limits("session-1")
    assert exc_info.value.code == 6
    assert "Per-review cost limit reached" in called["message"]
    assert "$1.00" in called["message"]


def test_b3_under_limit_does_not_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US5/AC2: under both limits must not raise or exit."""

    def fake_cost_limit_error(message: str) -> None:
        raise SystemExit(6)

    monkeypatch.setattr("openreview_cli.gateway.router.cost_limit_error", fake_cost_limit_error)

    def daily_under2(db: Path, cents: int) -> bool:
        return True

    def session_under2(db: Path, sid: str, cents: int) -> bool:
        return True

    monkeypatch.setattr(
        "openreview_cli.gateway.router.check_daily_limit",
        daily_under2,
    )
    monkeypatch.setattr(
        "openreview_cli.gateway.router.check_session_limit",
        session_under2,
    )

    gw = _make_gateway(
        {"gateway": {"cost_limits": {"daily_cents": 1000, "per_review_cents": 100}}},
        tmp_path / "db.sqlite",
    )
    # Must not raise.
    gw._check_cost_limits("session-1")


def test_b3_unset_limits_no_op(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset (None) limits must be a no-op. No warning, no exit,
    no check call. Also covers the session_id=None case: the
    session check is skipped when there is no session.
    """
    daily_called: list[int] = []
    session_called: list[tuple[str, int]] = []

    def fake_cost_limit_error(message: str) -> None:
        raise SystemExit(6)

    def fake_check_daily(db: Path, cents: int) -> bool:
        daily_called.append(cents)
        return True

    def fake_check_session(db: Path, sid: str, cents: int) -> bool:
        session_called.append((sid, cents))
        return True

    monkeypatch.setattr("openreview_cli.gateway.router.cost_limit_error", fake_cost_limit_error)
    monkeypatch.setattr("openreview_cli.gateway.router.check_daily_limit", fake_check_daily)
    monkeypatch.setattr("openreview_cli.gateway.router.check_session_limit", fake_check_session)

    # No gateway.cost_limits section at all.
    gw = _make_gateway({"gateway": {}}, tmp_path / "db.sqlite")
    # session_id=None exercises the production branch that
    # skips the per-review check when there is no session.
    gw._check_cost_limits(None)
    assert daily_called == [], "daily check must be skipped when daily_cents is None"
    assert session_called == [], (
        "session check must be skipped when per_review_cents is None or session_id is None"
    )


def test_b3_check_exception_reraises_with_visible_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """FR-6 + R8: check exception must be logged at WARNING and
    re-raised. The WARNING is not swallowed. Pin both the
    message and the level in one assertion to avoid relying on
    unrelated WARNINGs.
    """
    import logging

    def fake_cost_limit_error(message: str) -> None:
        raise SystemExit(6)

    def fake_check_daily(db: Path, cents: int) -> bool:
        raise RuntimeError("simulated db error")

    monkeypatch.setattr("openreview_cli.gateway.router.cost_limit_error", fake_cost_limit_error)
    monkeypatch.setattr("openreview_cli.gateway.router.check_daily_limit", fake_check_daily)

    gw = _make_gateway(
        {"gateway": {"cost_limits": {"daily_cents": 1000, "per_review_cents": 100}}},
        tmp_path / "db.sqlite",
    )

    with (
        caplog.at_level(logging.WARNING, logger="openreview_cli.gateway.router"),
        pytest.raises(RuntimeError, match="simulated db error"),
    ):
        gw._check_cost_limits("session-1")
    assert any(
        "Failed to check daily cost limit" in r.message and r.levelname == "WARNING"
        for r in caplog.records
    ), "expected a WARNING-level log with the daily-check failure message"


def test_b3_session_check_exception_reraises_with_visible_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """FR-6 + R8: per-review check exception must be logged at
    WARNING and re-raised. The WARNING is not swallowed.
    """
    import logging

    def fake_check_daily(db: Path, cents: int) -> bool:
        return True  # daily ok, so the session check runs

    def fake_check_session(db: Path, sid: str, cents: int) -> bool:
        raise RuntimeError("simulated session db error")

    monkeypatch.setattr("openreview_cli.gateway.router.check_daily_limit", fake_check_daily)
    monkeypatch.setattr("openreview_cli.gateway.router.check_session_limit", fake_check_session)

    gw = _make_gateway(
        {"gateway": {"cost_limits": {"daily_cents": 1000, "per_review_cents": 100}}},
        tmp_path / "db.sqlite",
    )

    with (
        caplog.at_level(logging.WARNING, logger="openreview_cli.gateway.router"),
        pytest.raises(RuntimeError, match="simulated session db error"),
    ):
        gw._check_cost_limits("session-1")
    assert any(
        "Failed to check session cost limit" in r.message and r.levelname == "WARNING"
        for r in caplog.records
    ), "expected a WARNING-level log with the session-check failure message"


def test_b3_session_id_none_skips_session_check_even_when_per_review_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Follow-up to review comment 3: the session_id=None skip
    must be exercised independently of the per_review_cents unset
    case. With per_review_cents=100 configured but session_id=None,
    the per-review check is skipped. A regression to "skip only
    when per_review_cents is None" would be caught here.
    """
    session_called: list[tuple[str, int]] = []

    def fake_check_session(db: Path, sid: str, cents: int) -> bool:
        session_called.append((sid, cents))
        return True

    monkeypatch.setattr(
        "openreview_cli.gateway.router.check_daily_limit",
        lambda db, cents: True,
    )
    monkeypatch.setattr("openreview_cli.gateway.router.check_session_limit", fake_check_session)

    # per_review_cents is configured but session_id is None.
    gw = _make_gateway(
        {"gateway": {"cost_limits": {"daily_cents": 1000, "per_review_cents": 100}}},
        tmp_path / "db.sqlite",
    )
    gw._check_cost_limits(None)
    assert session_called == [], (
        "session check must be skipped when session_id is None, "
        "even if per_review_cents is configured"
    )
