"""W7c chaos suite: cost accounting and recovery honesty.

Two invariants from the plan's Track D (section 5), asserted rather than assumed:

1. **Accounting.** A call that did not produce a usable reply must not leave a
   ``cost_logs`` row and must not increment a counter it did not earn; a call that
   did produce one must leave exactly one row per logical call, and the row count
   must cross-check against the egress counter. (RT-028 already covers the
   dispatch-vs-logical-call *counter* asymmetry — the retry-path case below is
   cross-referenced to it, not re-opened.)
2. **Retry shape.** Sharp edge 9 fixed: ``_call_with_fallback`` retries a
   transient ``Exception`` three times with a fixed delay, but a permanent auth
   or not-found class is dispatched once and re-raised (#154).

Plus the recovery layer: ``RecoveryCoordinator.handle_gateway_failure`` routing,
the ``provider_fallback`` privacy-tier guard and the ``user_guided_recovery``
suggestion contract.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from openreview_cli.gateway.errors import (
    AuthError,
    GatewayError,
    ModelNotFoundError,
    UnclassifiedProviderError,
)
from openreview_cli.gateway.models import get_total_cloud_calls
from openreview_cli.recovery.coordinator import RecoveryCoordinator
from openreview_cli.recovery.models import (
    PRIVACY_TIER_STANDARD,
    PRIVACY_TIER_STRICT,
    ErrorCategory,
    RecoveryContext,
    RecoveryOutcome,
    classify_error,
)
from openreview_cli.recovery.strategies.user_guided_recovery import user_guided_recovery
from tests.chaos import _w7_probe as _w7
from tests.chaos.conftest import FlakyGatewayFactory

pytestmark = pytest.mark.chaos

CLOUD_PRIMARY = "openai/gpt-4o"
# The faults whose honest outcome is "failure, so no cost and no counter".
NO_COST_FAULTS: tuple[str, ...] = (
    "timeout",
    "rate_limit",
    "five_hundred",
    "five_hundred_three",
    "auth",
    "not_found",
)
# Permanent classes: a retry cannot fix either one (sharp edge 9 / RT-043).
PERMANENT_FAULTS: dict[str, type[Exception]] = {"auth": AuthError, "not_found": ModelNotFoundError}
EXPECTED_RETRY_ATTEMPTS = 3  # config retries: 2 -> 3 dispatches


def assert_no_earned_cost(
    rows: list[tuple[str, str, int]], gw: Any, process_calls: int, attempts: int
) -> None:
    """The accounting oracle: no cost row, and only the dispatch attempts counted."""
    assert rows == [], f"a faulted call logged a cost: {rows}"
    assert gw._cloud_calls_made == attempts, "the counter must count every dispatch attempt"
    assert process_calls == attempts, "the process counter must count every dispatch attempt"


# ── Cost-accounting integrity ───────────────────────────────────────────────


@pytest.mark.parametrize("fault_name", NO_COST_FAULTS)
def test_faulted_call_logs_no_cost_and_earns_only_the_attempts_it_made(
    flaky_gateway: FlakyGatewayFactory, fault_name: str
) -> None:
    """A failed dispatch must leave no cost row, while the counter counts each attempt."""
    flaky = flaky_gateway(fault_name)

    with pytest.raises(GatewayError):
        flaky.chat()

    expected_attempts = 1 if fault_name in PERMANENT_FAULTS else EXPECTED_RETRY_ATTEMPTS
    assert flaky.seam.attempts == expected_attempts, "unexpected number of dispatch attempts"
    assert_no_earned_cost(
        _w7.cost_rows(flaky.state.db_path), flaky.gw, get_total_cloud_calls(), flaky.seam.attempts
    )


def test_successful_call_logs_exactly_one_row_and_counts_one(
    flaky_gateway: FlakyGatewayFactory,
) -> None:
    """The clean path: one logical call -> one cost row and one counter increment."""
    flaky = flaky_gateway("timeout")
    flaky.install_seam(
        _w7.FlakyDispatch(
            failures=0, response=_w7.CompletionResponse("ok", usage=_w7.Usage(10, 20))
        )
    )

    result = flaky.chat()

    assert result == "ok"
    rows = _w7.cost_rows(flaky.state.db_path)
    assert rows == [(CLOUD_PRIMARY, "openai", 5)], rows
    assert flaky.gw._cloud_calls_made == 1
    assert get_total_cloud_calls() == 1
    # Cross-check: rows observed == counter increments earned.
    assert len(rows) == flaky.gw._cloud_calls_made == get_total_cloud_calls()


def test_retry_then_success_logs_one_row_for_three_dispatches(
    flaky_gateway: FlakyGatewayFactory,
) -> None:
    """Two failures then a success: 3 dispatch attempts, 3 counter increments, 1 row.

    The ledger still agrees with the *logical* call (one row), while the egress
    counter now counts dispatches (#143): the counter no longer equals the row
    count, because one logical call made three network attempts.
    """
    flaky = flaky_gateway("timeout")
    flaky.install_seam(
        _w7.FlakyDispatch(
            failures=2, response=_w7.CompletionResponse("ok", usage=_w7.Usage(10, 20))
        )
    )

    assert flaky.chat() == "ok"

    assert flaky.seam.attempts == 3, "expected two failures then a success"
    rows = _w7.cost_rows(flaky.state.db_path)
    assert rows == [(CLOUD_PRIMARY, "openai", 5)], rows
    assert flaky.gw._cloud_calls_made == 3, "every dispatch attempt earned one increment"
    assert get_total_cloud_calls() == 3


def test_no_choice_reply_leaves_no_cost_row_and_counts_the_dispatch(
    flaky_gateway: FlakyGatewayFactory,
) -> None:
    """RT-039 fixed, the accounting half of W7a's RT-038 node.

    The W0 ``delay`` record delivers no response object; the reply is validated
    before the cost row, so the call raises a typed ``UnclassifiedProviderError``
    naming the provider and leaves no ``cost_logs`` row. The dispatch is still
    counted (#147/C2). ``draft/evidence/RT-039.txt`` is superseded.
    """
    flaky = flaky_gateway("delay")

    with pytest.raises(UnclassifiedProviderError):
        flaky.chat()

    assert _w7.cost_rows(flaky.state.db_path) == []
    assert flaky.gw._cloud_calls_made == 1


# ── Retry shape (sharp edge 9 / RT-043) ─────────────────────────────────────


def test_retry_shape_is_three_attempts_for_every_fault_class(
    flaky_gateway: FlakyGatewayFactory,
) -> None:
    """Sharp edge 9 fixed: a transient class retries three times; a permanent one once."""
    recorded: dict[str, int] = {}
    for fault_name in NO_COST_FAULTS:
        flaky = flaky_gateway(fault_name)
        with pytest.raises(GatewayError):
            flaky.chat()
        recorded[fault_name] = flaky.seam.attempts

    expected = {
        fault_name: 1 if fault_name in PERMANENT_FAULTS else EXPECTED_RETRY_ATTEMPTS
        for fault_name in NO_COST_FAULTS
    }
    assert recorded == expected, recorded


@pytest.mark.parametrize("fault_name", sorted(PERMANENT_FAULTS))
def test_permanent_errors_are_dispatched_once(
    flaky_gateway: FlakyGatewayFactory, fault_name: str
) -> None:
    """Inverted RT-043 pin (#154): the permanent class is classified and short-circuited."""
    flaky = flaky_gateway(fault_name)

    with pytest.raises(PERMANENT_FAULTS[fault_name]) as exc_info:
        flaky.chat()

    assert isinstance(exc_info.value, GatewayError), "the class IS detected"
    assert flaky.seam.attempts == 1, flaky.seam.attempts


def test_retry_delay_is_fixed_with_no_jitter_or_cap(
    flaky_gateway: FlakyGatewayFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sharp edge 9: the delay is the configured constant, identical on every retry."""
    sleeps: list[float] = []
    monkeypatch.setattr("openreview_cli.gateway.router.time.sleep", sleeps.append)
    flaky = flaky_gateway("timeout", retry_delay=0.25)

    with pytest.raises(UnclassifiedProviderError):
        flaky.chat()

    # Two sleeps for three attempts, each exactly the configured delay: no jitter,
    # no exponential growth, no trailing sleep. There is no elapsed-time deadline
    # in _call_with_fallback (router.py:507-513), so retries*r is the worst case.
    assert sleeps == [0.25, 0.25], sleeps
    assert flaky.seam.attempts == EXPECTED_RETRY_ATTEMPTS


def test_retries_configured_as_zero_means_one_attempt(flaky_gateway: FlakyGatewayFactory) -> None:
    """The retry count is read from config, not hard-coded."""
    flaky = flaky_gateway("timeout", retries=0)

    with pytest.raises(UnclassifiedProviderError):
        flaky.chat()

    assert flaky.seam.attempts == 1


# ── RecoveryCoordinator: classification, fallback and the privacy guard ──────


def test_classify_error_transient_versus_permanent() -> None:
    """The classification table the coordinator's routing depends on."""
    assert classify_error(http_status=429) is ErrorCategory.transient
    assert classify_error(http_status=500) is ErrorCategory.transient
    assert classify_error(http_status=503) is ErrorCategory.transient
    assert classify_error(http_status=401) is ErrorCategory.permanent
    assert classify_error(http_status=403) is ErrorCategory.permanent
    assert classify_error(http_status=404) is ErrorCategory.permanent
    assert classify_error(http_status=400) is ErrorCategory.permanent
    assert classify_error() is ErrorCategory.unknown


async def _drive(
    status: int | None,
    *,
    tier: str,
    providers: list[str] | None = None,
    attempt: Callable[[str], Awaitable[bool]] | None = None,
) -> tuple[Any, RecoveryContext]:
    """Drive ``handle_gateway_failure`` once and return (result, context)."""
    coordinator = RecoveryCoordinator(user_privacy_tier=tier)
    ctx = coordinator.create_context(provider_list=providers or [])
    result = await coordinator.handle_gateway_failure(
        provider_name="extraction",
        error_metadata={"http_status": status, "last_error": "provider call failed"},
        ctx=ctx,
        stage_name="review",
        attempt_fn=attempt,
    )
    return result, ctx


def _attempt_recorder(result: bool) -> tuple[Callable[[str], Awaitable[bool]], list[str]]:
    """An ``attempt_fn`` that records every provider it is asked to try."""
    calls: list[str] = []

    async def _attempt(provider: str) -> bool:
        calls.append(provider)
        return result

    return _attempt, calls


async def test_transient_failure_falls_back_to_a_working_provider() -> None:
    """503 (transient) -> provider_fallback -> resolved on the alternate provider."""
    attempt, calls = _attempt_recorder(True)

    result, ctx = await _drive(
        503, tier="balanced", providers=["ollama/qwen3:8b", CLOUD_PRIMARY], attempt=attempt
    )

    assert result is not None, "a working fallback should resolve the failure"
    assert result.outcome is RecoveryOutcome.RESOLVED
    assert result.provider_name == CLOUD_PRIMARY
    assert calls == [CLOUD_PRIMARY], "provider_fallback was never entered"
    assert "provider_fallback" in ctx.attempted_strategies


async def test_permanent_failure_also_routes_through_provider_fallback() -> None:
    """401 (permanent) reaches provider_fallback too, not user_guided directly."""
    attempt, calls = _attempt_recorder(True)

    result, ctx = await _drive(
        401, tier="balanced", providers=["ollama/qwen3:8b", CLOUD_PRIMARY], attempt=attempt
    )

    assert result is not None and result.outcome is RecoveryOutcome.RESOLVED
    assert calls == [CLOUD_PRIMARY]
    assert "provider_fallback" in ctx.attempted_strategies


async def test_unknown_failure_is_user_guided_with_at_least_two_suggestions() -> None:
    """An unclassifiable failure is terminal, and must offer real actions."""
    result, ctx = await _drive(None, tier="balanced", providers=[CLOUD_PRIMARY])

    assert result is None, "an unknown failure must not claim recovery"
    last = ctx.events[-1]
    assert last.outcome is RecoveryOutcome.UNRECOVERABLE
    assert last.strategy_name == "user_guided_recovery"
    assert "user_guided_recovery" in ctx.attempted_strategies
    numbered = [
        line
        for line in last.message.splitlines()
        if line.strip()[:2] in {"1.", "2.", "3.", "4.", "5."}
    ]
    assert len(numbered) >= 2, f"only {len(numbered)} suggestions: {last.message!r}"


async def test_provider_fallback_privacy_guard_blocks_a_cloud_fallback() -> None:
    """A strict privacy tier must not fall back to a cloud provider (SC-04)."""
    attempt, calls = _attempt_recorder(True)

    result, ctx = await _drive(
        503, tier="maximum", providers=["ollama/qwen3:8b", CLOUD_PRIMARY], attempt=attempt
    )

    assert result is None, "the cloud fallback should have been blocked"
    assert calls == [], f"the cloud provider was attempted despite the strict tier: {calls}"
    last = ctx.events[-1]
    assert last.outcome is RecoveryOutcome.UNRECOVERABLE
    assert PRIVACY_TIER_STRICT in (ctx.user_privacy_tier,)


async def test_the_privacy_guard_control_is_reachable_on_a_permissive_tier() -> None:
    """Anti-vacuity: the SAME setup resolves once the tier permits cloud fallback."""
    attempt, calls = _attempt_recorder(True)

    result, ctx = await _drive(
        503, tier="balanced", providers=["ollama/qwen3:8b", CLOUD_PRIMARY], attempt=attempt
    )

    assert ctx.user_privacy_tier == PRIVACY_TIER_STANDARD
    assert result is not None and result.outcome is RecoveryOutcome.RESOLVED
    assert calls == [CLOUD_PRIMARY], "the guard wiring is dead — nothing was attempted"


async def test_user_guided_recovery_offers_at_least_two_suggestions() -> None:
    """The strategy's own contract (SC-07), driven directly."""
    ctx = RecoveryContext(user_privacy_tier=PRIVACY_TIER_STRICT)

    event = await user_guided_recovery(
        ctx,
        "review",
        {"error_category": "transient", "last_error": "boom", "provider_name": CLOUD_PRIMARY},
    )

    assert event.outcome is RecoveryOutcome.UNRECOVERABLE
    numbered = [
        line
        for line in event.message.splitlines()
        if line.strip()[:2] in {"1.", "2.", "3.", "4.", "5."}
    ]
    assert len(numbered) >= 2, event.message
    assert "strict" in event.message, "the privacy-tier warning is missing"


# ── Sharp edge 10 and 11: the two dispatch sites without a retry loop ───────


def test_chat_stream_retries_then_tries_the_fallback(
    flaky_gateway: FlakyGatewayFactory,
) -> None:
    """Sharp edge 10 fixed: ``chat_stream`` dispatches through the retry/fallback seam.

    The stream dispatch is routed through ``_call_with_fallback``, so a configured
    slot fallback IS tried after the primary's retries: three primary dispatches, then
    one fallback dispatch, and the failure is classified. Both prefixes in that
    registry are cloud — the absent ``anthropic`` entry takes the fail-closed
    unknown-prefix count — so every dispatch earned one counter increment, while a
    stream that never produced a usable reply leaves no ``cost_logs`` row.

    Only the DISPATCH is retried; nothing has been yielded yet (FR-6/#151).
    """
    flaky = flaky_gateway("provider_down", slot_fallback="anthropic/claude-3-5-haiku")

    outcome = _w7.collect_stream(flaky.gw)

    assert outcome.caught is not None, "the fault did not surface"
    assert isinstance(outcome.caught, GatewayError), outcome.caught
    assert flaky.seam.attempts == 4, (
        f"expected 3 primary retries + 1 fallback, saw {flaky.seam.attempts}"
    )
    assert flaky.seam.models == [CLOUD_PRIMARY] * 3 + ["anthropic/claude-3-5-haiku"], (
        flaky.seam.models
    )
    assert _w7.cost_rows(flaky.state.db_path) == [], "a failed stream logged a cost"
    assert flaky.gw._cloud_calls_made == 4


# ── Negative control (anti-vacuity, plan section 9.3) ───────────────────────


def test_negative_control_accounting_oracle_rejects_a_real_cost_row(
    flaky_gateway: FlakyGatewayFactory,
) -> None:
    """The accounting oracle must fail on a row that WAS written, or it proves nothing."""
    flaky = flaky_gateway("timeout")
    flaky.install_seam(_w7.FlakyDispatch(failures=0))
    assert flaky.chat() == "ok"

    with pytest.raises(AssertionError, match="logged a cost"):
        assert_no_earned_cost(
            _w7.cost_rows(flaky.state.db_path),
            flaky.gw,
            get_total_cloud_calls(),
            flaky.seam.attempts,
        )
