"""W5 red-team suite: the egress gate.

Attacks the three guarantees the gateway claims to enforce before any network
call (plan section 5, Track B):

* guarantee 1/3 — a privacy tier that forbids cloud egress must block dispatch,
  and an ambiguous provider state must fail **closed**;
* the cloud-call counter must increment once per dispatch that actually
  happened, so the privacy footer tells the truth.

Technique (plan section 10, W5): the dispatch seam is patched so that it records
the call and then raises ``AssertionError("dispatched <model>")``. A passing
test therefore proves the network was *never reached*, not that a boolean came
back correct — and the record survives ``_call_with_fallback``'s
``except Exception``, which would otherwise swallow the assertion into
``UnclassifiedProviderError``. The *record* is what makes the dispatch
observable; the cloud-call counter now also counts every dispatch attempt, so
the two agree.

Real command paths driven end to end: ``precheck --document``,
``precheck review``, ``privacycheck`` and ``gateway test``.

No sockets, no network, no paid providers: every seam is in-process.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from openreview_cli.gateway.errors import NoMatchingProviderError, UnclassifiedProviderError
from openreview_cli.gateway.models import get_total_cloud_calls, reset_total_cloud_calls
from openreview_cli.gateway.router import classify_provider, mark_pii_available, reset_pii_available
from tests.redteam import _w5_probe as _w5

pytestmark = pytest.mark.redteam

TIER_ERROR_TOKEN = "requires a local provider"


@pytest.fixture(autouse=True)
def _reset_process_globals() -> Any:
    """Isolate the two process-wide router globals per test."""
    reset_total_cloud_calls()
    reset_pii_available()
    yield
    reset_total_cloud_calls()
    reset_pii_available()


@dataclass(frozen=True)
class SiteRow:
    """One row of the counter-equality table."""

    case: str
    dispatches: int
    increments: int


class FlakyDispatch(_w5.DispatchRecorder):
    """Record every dispatch, but fail the first ``failures`` of them."""

    def __init__(self, failures: int) -> None:
        super().__init__(fail=False)
        self.failures = failures

    def _maybe_fail(self, site: str, kwargs: dict[str, Any]) -> None:
        if len(self.records) <= self.failures:
            raise ConnectionError(f"transient failure on dispatch {len(self.records)}")


# ── Named real command paths on the strict tier ─────────────────────────────


def test_gateway_test_blocks_cloud_dispatch_on_the_strict_tier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``openreview gateway test extraction`` must not reach the network."""
    state = _w5.prepare_state(monkeypatch, tmp_path)
    gw = _w5.make_gateway(state, primary=_w5.CLOUD_PRIMARY, tier="maximum")
    constructed = _w5.patch_gateway_factory(monkeypatch, _w5.gateway_returning(gw))
    recorder = _w5.DispatchRecorder()
    recorder.install(monkeypatch)

    result = _w5.run_cli(["gateway", "test", "extraction"])

    assert constructed == [1], "gateway test must go through the real Gateway constructor"
    assert result.exit_code == 1, f"exit={result.exit_code} output={result.output!r}"
    assert isinstance(result.exception, SystemExit), "a clean exit, not a raw traceback"
    assert TIER_ERROR_TOKEN in result.output, result.output
    _w5.assert_no_dispatch(recorder, "gateway test extraction on the maximum tier")
    assert gw._cloud_calls_made == 0
    assert get_total_cloud_calls() == 0


def test_precheck_document_path_never_constructs_a_gateway(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``precheck --document`` is PII-only: it must not even build a Gateway."""
    state = _w5.prepare_state(monkeypatch, tmp_path)
    constructed = _w5.patch_gateway_factory(monkeypatch, _w5.gateway_forbidden())
    recorder = _w5.DispatchRecorder()
    recorder.install(monkeypatch)
    monkeypatch.chdir(tmp_path)

    result = _w5.run_cli(
        ["precheck", "-d", str(_w5.NDA_PDF), "--no-pii", "--output", str(state.output_dir)]
    )

    assert result.exit_code == 0, f"exit={result.exit_code} output={result.output!r}"
    assert constructed == [], "precheck --document constructed a Gateway"
    _w5.assert_no_dispatch(recorder, "precheck --document on the maximum tier")


def test_the_forbidden_gateway_factory_is_reachable_from_the_review_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Negative control for the case above: the guard fires where a Gateway IS built.

    Without this, ``constructed == []`` in the previous test would certify
    nothing — a guard wired to nothing is always satisfied (plan section 9.3).
    """
    state = _w5.prepare_state(monkeypatch, tmp_path)
    _w5.patch_gateway_factory(monkeypatch, _w5.gateway_forbidden())
    monkeypatch.chdir(tmp_path)

    result = _w5.run_cli(
        ["precheck", "review", str(_w5.NDA_PDF), "--no-pii", "--output-dir", str(state.output_dir)]
    )

    assert "gateway constructed" in result.output, (
        "precheck review never reached the Gateway seam, so the guard above proves nothing: "
        f"exit={result.exit_code} output={result.output!r}"
    )


def test_precheck_review_blocks_cloud_dispatch_on_the_strict_tier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``precheck review`` drives the review pipeline: blocked before the network."""
    state = _w5.prepare_state(monkeypatch, tmp_path)
    gw = _w5.make_gateway(state, primary=_w5.CLOUD_PRIMARY, tier="maximum")
    constructed = _w5.patch_gateway_factory(monkeypatch, _w5.gateway_returning(gw))
    recorder = _w5.DispatchRecorder()
    recorder.install(monkeypatch)
    monkeypatch.chdir(tmp_path)

    result = _w5.run_cli(
        ["precheck", "review", str(_w5.NDA_PDF), "--no-pii", "--output-dir", str(state.output_dir)]
    )

    assert len(constructed) >= 1, "the review path never reached the gateway seam"
    assert TIER_ERROR_TOKEN in result.output, result.output
    _w5.assert_no_dispatch(recorder, "precheck review on the maximum tier")
    assert gw._cloud_calls_made == 0
    assert get_total_cloud_calls() == 0


def test_privacycheck_blocks_cloud_dispatch_on_the_strict_tier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``privacycheck`` drives the review pipeline: blocked before the network."""
    state = _w5.prepare_state(monkeypatch, tmp_path)
    gw = _w5.make_gateway(state, primary=_w5.CLOUD_PRIMARY, tier="maximum")
    constructed = _w5.patch_gateway_factory(monkeypatch, _w5.gateway_returning(gw))
    recorder = _w5.DispatchRecorder()
    recorder.install(monkeypatch)
    monkeypatch.chdir(tmp_path)

    result = _w5.run_cli(
        [
            "privacycheck",
            str(_w5.NDA_PDF),
            "--no-pii",
            "--playbook",
            str(_w5.NDA_PLAYBOOK),
            "--output-dir",
            str(state.output_dir),
        ]
    )

    assert len(constructed) >= 1, "privacycheck never reached the gateway seam"
    assert TIER_ERROR_TOKEN in result.output, result.output
    _w5.assert_no_dispatch(recorder, "privacycheck on the maximum tier")
    assert gw._cloud_calls_made == 0
    assert get_total_cloud_calls() == 0


# ── Ambiguous provider states at the real gate ──────────────────────────────


def test_unknown_override_provider_prefix_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A recovery-style ``model=`` override outside the registry is blocked.

    ``router.py:252-272``: the override path fails closed. Its sibling — the
    same unknown prefix as a *slot primary* — does not (RT-026).
    """
    state = _w5.prepare_state(monkeypatch, tmp_path)
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", dict)
    gw = _w5.make_gateway(state, primary=_w5.CLOUD_PRIMARY, tier="maximum")
    recorder = _w5.DispatchRecorder()
    recorder.install(monkeypatch)

    with pytest.raises(NoMatchingProviderError) as exc:
        gw.chat("extraction", [{"role": "user", "content": "hi"}], model="mystery/model")

    assert "Unknown provider 'mystery'" in str(exc.value)
    _w5.assert_no_dispatch(recorder, "unknown override prefix on the maximum tier")
    assert gw._cloud_calls_made == 0


def test_unknown_slot_primary_prefix_is_dispatched_on_the_strict_tier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """RT-026 pinning node, inverted by R-01 (was: dispatched on the strict tier).

    Before the fix the guard returned at ``router.py:293-294`` and dispatched
    ``mystery/model`` three times. The slot-primary branch now fails closed like
    the override branch (``router.py:252-272``): a typed error is raised before
    the dispatch seam is reached.
    """
    state = _w5.prepare_state(monkeypatch, tmp_path)
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", dict)
    gw = _w5.make_gateway(state, primary="mystery/model", tier="maximum")
    recorder = _w5.DispatchRecorder()
    recorder.install(monkeypatch)

    with pytest.raises(NoMatchingProviderError) as exc:
        gw.chat("extraction", [{"role": "user", "content": "hi"}])

    assert "Unknown provider 'mystery'" in str(exc.value)
    _w5.assert_no_dispatch(recorder, "unknown slot primary on the maximum tier")
    assert gw._cloud_calls_made == 0
    assert get_total_cloud_calls() == 0


def test_unknown_slot_primary_prefix_never_reaches_dispatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Expected: an unregistered slot primary fails closed like an override does."""
    state = _w5.prepare_state(monkeypatch, tmp_path)
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", dict)
    gw = _w5.make_gateway(state, primary="mystery/model", tier="maximum")
    recorder = _w5.DispatchRecorder()
    recorder.install(monkeypatch)

    with contextlib.suppress(Exception):
        gw.chat("extraction", [{"role": "user", "content": "hi"}])

    _w5.assert_no_dispatch(recorder, "unknown slot primary on the maximum tier")


def test_bundled_registry_holds_unclassifiable_cloud_providers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Grounds RT-027 in the shipped registry, not in a synthetic double."""
    _w5.prepare_state(monkeypatch, tmp_path)
    from openreview_cli.gateway.registry import load_registry

    registry = load_registry()
    for name in ("bedrock", "vertex"):
        info = registry[name]
        assert info.is_local is False, name
        assert info.base_url is None, name
        with pytest.raises(ValueError, match="no base_url and not local"):
            classify_provider(info)


def test_unclassifiable_provider_is_blocked_on_the_strict_tier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The ValueError from ``classify_provider`` is caught and fails CLOSED (router.py:297-301)."""
    state = _w5.prepare_state(monkeypatch, tmp_path)
    registry = _w5.unclassifiable_registry()
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)
    gw = _w5.make_gateway(state, primary="bedrock/anthropic.claude-3-5-sonnet", tier="maximum")
    recorder = _w5.DispatchRecorder()
    recorder.install(monkeypatch)

    with pytest.raises(NoMatchingProviderError):
        gw.chat("extraction", [{"role": "user", "content": "hi"}])

    _w5.assert_no_dispatch(recorder, "unclassifiable provider on the maximum tier")
    assert gw._cloud_calls_made == 0


def test_unclassifiable_provider_dispatch_is_counted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """RT-027 pinning node, inverted by #143: one state, one resolution.

    ``_enforce_tier`` calls the unclassifiable provider cloud and lets it
    through on a permissive tier; ``_record_cloud_call`` now reaches the same
    verdict and counts every dispatch attempt as cloud.
    """
    state = _w5.prepare_state(monkeypatch, tmp_path)
    registry = _w5.unclassifiable_registry()
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)
    gw = _w5.make_gateway(state, primary="bedrock/anthropic.claude-3-5-sonnet", tier="performance")
    mark_pii_available()
    recorder = _w5.DispatchRecorder()
    recorder.install(monkeypatch)

    with pytest.raises(UnclassifiedProviderError):
        gw.chat("extraction", [{"role": "user", "content": "hi"}])

    assert recorder.models() == ["bedrock/anthropic.claude-3-5-sonnet"] * 3
    assert gw._cloud_calls_made == 3
    assert get_total_cloud_calls() == 3


def test_unclassifiable_provider_dispatch_increments_the_cloud_counter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Expected: every cloud dispatch is counted, whatever the counter can classify."""
    state = _w5.prepare_state(monkeypatch, tmp_path)
    registry = _w5.unclassifiable_registry()
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)
    gw = _w5.make_gateway(state, primary="bedrock/anthropic.claude-3-5-sonnet", tier="performance")
    mark_pii_available()
    recorder = _w5.DispatchRecorder()
    recorder.install(monkeypatch)

    with contextlib.suppress(UnclassifiedProviderError):
        gw.chat("extraction", [{"role": "user", "content": "hi"}])

    assert len(recorder.records) == 3
    assert gw._cloud_calls_made == len(recorder.records) > 0


# ── Counter integrity ───────────────────────────────────────────────────────


def test_counter_equality_per_dispatch_site(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """One successful dispatch on each remaining real dispatch site: 1 == 1."""
    state = _w5.prepare_state(monkeypatch, tmp_path)
    registry = _w5.cloud_registry()
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)
    mark_pii_available()
    recorder = _w5.DispatchRecorder(fail=False)
    recorder.install(monkeypatch)

    rows: list[SiteRow] = []

    gw = _w5.make_gateway(state, primary=_w5.CLOUD_PRIMARY, tier="performance")
    assert gw.chat("extraction", [{"role": "user", "content": "hi"}]) == "ok"
    rows.append(SiteRow("chat", len(recorder.records), gw._cloud_calls_made))

    stream_recorder = _w5.DispatchRecorder(fail=False, stream_mode=True)
    stream_recorder.install(monkeypatch)
    gw = _w5.make_gateway(state, primary=_w5.CLOUD_PRIMARY, tier="performance")
    chunks = list(gw.chat_stream("extraction", [{"role": "user", "content": "hi"}]))
    assert chunks[-1].type == "done"
    rows.append(SiteRow("chat_stream", len(stream_recorder.records), gw._cloud_calls_made))

    assert rows == [
        SiteRow("chat", 1, 1),
        SiteRow("chat_stream", 1, 1),
    ], rows


def test_counter_equals_dispatch_at_every_site(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The measured dispatch-vs-increment table, as numbers.

    This is the table the register records (RT-026, RT-027, RT-028, RT-029).
    Every row is a real dispatch count against a real increment count. The row
    set now measures dispatches against increments, not inequalities: the
    unknown-slot-primary row is 0 == 0 (R-01 fails it closed before the seam, so
    there is no dispatch to under-count) and the fallback-model row is 3 == 0
    (the cloud fallback is refused on the maximum tier, so only the three local
    primary dispatches happen and no cloud egress is recorded).
    """
    state = _w5.prepare_state(monkeypatch, tmp_path)
    registry = {**_w5.cloud_registry(), **_w5.local_registry()}
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)
    mark_pii_available()
    rows: list[SiteRow] = []

    # A retry batch: 2 failures then a success is one increment for 3 dispatches.
    flaky = FlakyDispatch(failures=2)
    flaky.install(monkeypatch)
    gw = _w5.make_gateway(state, primary=_w5.CLOUD_PRIMARY, tier="performance")
    assert gw.chat("extraction", [{"role": "user", "content": "hi"}]) == "ok"
    rows.append(SiteRow("chat, 2 retries", len(flaky.records), gw._cloud_calls_made))

    # The primary exhausts its retries and the configured fallback model is
    # refused by the maximum tier: three local dispatches, no cloud egress.
    fallback_runner = FlakyDispatch(failures=3)
    fallback_runner.install(monkeypatch)
    gw = _w5.make_gateway(
        state,
        primary="ollama/qwen3:8b",
        tier="maximum",
        fallback="anthropic/claude-3-5-haiku",
    )
    with pytest.raises(NoMatchingProviderError):
        gw.chat("extraction", [{"role": "user", "content": "hi"}])
    rows.append(SiteRow("chat, fallback model", len(fallback_runner.records), gw._cloud_calls_made))

    # A slot primary the registry cannot resolve: R-01 fails it closed, so the
    # guard blocks before the seam and the counter stays silent (0 == 0).
    unknown = _w5.DispatchRecorder()
    unknown.install(monkeypatch)
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", dict)
    gw = _w5.make_gateway(state, primary="mystery/model", tier="maximum")
    with contextlib.suppress(NoMatchingProviderError):
        gw.chat("extraction", [{"role": "user", "content": "hi"}])
    rows.append(SiteRow("chat, unknown slot primary", len(unknown.records), gw._cloud_calls_made))

    # An unclassifiable registry entry: guard calls it cloud, counter refuses.
    unclassifiable = _w5.DispatchRecorder()
    unclassifiable.install(monkeypatch)
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", _w5.unclassifiable_registry)
    gw = _w5.make_gateway(state, primary="bedrock/anthropic.claude-3-5-sonnet", tier="performance")
    with contextlib.suppress(UnclassifiedProviderError):
        gw.chat("extraction", [{"role": "user", "content": "hi"}])
    rows.append(
        SiteRow("chat, unclassifiable provider", len(unclassifiable.records), gw._cloud_calls_made)
    )

    assert rows == [
        SiteRow("chat, 2 retries", 3, 3),
        SiteRow("chat, fallback model", 3, 0),
        SiteRow("chat, unknown slot primary", 0, 0),
        SiteRow("chat, unclassifiable provider", 3, 3),
    ], rows


def test_retry_dispatches_increment_the_counter_once_each(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Expected: three attempts that reached the provider are three cloud calls."""
    state = _w5.prepare_state(monkeypatch, tmp_path)
    registry = _w5.cloud_registry()
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)
    mark_pii_available()
    flaky = FlakyDispatch(failures=2)
    flaky.install(monkeypatch)
    gw = _w5.make_gateway(state, primary=_w5.CLOUD_PRIMARY, tier="performance")

    assert gw.chat("extraction", [{"role": "user", "content": "hi"}]) == "ok"

    assert gw._cloud_calls_made == len(flaky.records) == 3


def test_every_dispatch_attempt_is_counted_inside_the_loop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """#143: the counter counts dispatches, so a retry batch counts every attempt.

    The count sits before the ``try`` in ``_call_with_fallback``, so the two
    attempts that raised are counted exactly like the one that succeeded.
    """
    state = _w5.prepare_state(monkeypatch, tmp_path)
    registry = _w5.cloud_registry()
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)
    mark_pii_available()
    flaky = FlakyDispatch(failures=2)
    flaky.install(monkeypatch)
    gw = _w5.make_gateway(state, primary=_w5.CLOUD_PRIMARY, tier="performance")

    assert gw.chat("extraction", [{"role": "user", "content": "hi"}]) == "ok"

    assert gw._cloud_calls_made == len(flaky.records) == 3
    assert get_total_cloud_calls() == 3


def test_an_unregistered_slot_primary_is_counted_as_cloud_on_a_permissive_tier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """#143/finding 6: an unregistered slot primary is counted as cloud per dispatch.

    Pre-T1 the post-dispatch counter read the slot primary, found nothing in the
    registry and counted 0 for the three dispatches that really happened.
    """
    state = _w5.prepare_state(monkeypatch, tmp_path)
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", dict)
    gw = _w5.make_gateway(state, primary="mystery/model", tier="performance")
    mark_pii_available()
    recorder = _w5.DispatchRecorder(fail=True)
    recorder.install(monkeypatch)

    with contextlib.suppress(UnclassifiedProviderError):
        gw.chat("extraction", [{"role": "user", "content": "hi"}])

    assert len(recorder.records) == 3
    assert gw._cloud_calls_made == 3
    assert get_total_cloud_calls() == 3


def test_a_cloud_fallback_model_is_blocked_on_the_strict_tier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """RT-029, inverted: the fallback model passes the same tier gate as the primary.

    Formerly ``test_fallback_model_is_dispatched_on_the_strict_tier``, it pinned
    the bug as observable behaviour. Now the maximum tier refuses the cloud
    fallback, so only the three local primary attempts dispatch.
    """
    state = _w5.prepare_state(monkeypatch, tmp_path)
    registry = {**_w5.cloud_registry(), **_w5.local_registry()}
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)
    runner = FlakyDispatch(failures=3)
    runner.install(monkeypatch)
    gw = _w5.make_gateway(
        state,
        primary="ollama/qwen3:8b",
        tier="maximum",
        fallback="anthropic/claude-3-5-haiku",
    )

    with pytest.raises(NoMatchingProviderError):
        gw.chat("extraction", [{"role": "user", "content": "hi"}])

    assert runner.models() == ["ollama/qwen3:8b"] * 3, runner.summary()
    assert runner.records[-1].api_base == _w5.OLLAMA_BASE_URL
    assert gw._cloud_calls_made == 0


def test_a_cloud_fallback_model_never_reaches_dispatch_on_the_strict_tier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Expected: every model that will hit the network passes the tier gate."""
    state = _w5.prepare_state(monkeypatch, tmp_path)
    registry = {**_w5.cloud_registry(), **_w5.local_registry()}
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)
    runner = FlakyDispatch(failures=3)
    runner.install(monkeypatch)
    gw = _w5.make_gateway(
        state,
        primary="ollama/qwen3:8b",
        tier="maximum",
        fallback="anthropic/claude-3-5-haiku",
    )

    with contextlib.suppress(Exception):
        gw.chat("extraction", [{"role": "user", "content": "hi"}])

    assert [model for model in runner.models() if "anthropic" in model] == []


def test_unknown_override_prefix_is_counted_as_cloud_even_when_the_sink_is_local(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """RT-031: a deliberate fail-closed over-count, pinned.

    ``router.py:793-799`` counts an unresolvable override as cloud on purpose.
    The request below left for ``localhost`` and was still counted — the exact
    opposite resolution of the same unknown-provider state in RT-027.
    """
    state = _w5.prepare_state(monkeypatch, tmp_path)
    registry = _w5.local_registry()
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)
    mark_pii_available()
    recorder = _w5.DispatchRecorder(fail=False)
    recorder.install(monkeypatch)
    gw = _w5.make_gateway(state, primary="ollama/qwen3:8b", tier="performance")

    assert gw.chat("extraction", [{"role": "user", "content": "hi"}], model="mystery/model") == "ok"

    assert recorder.records == [_w5.Dispatch("completion", "mystery/model", _w5.OLLAMA_BASE_URL)]
    assert gw._cloud_calls_made == 1
    assert get_total_cloud_calls() == 1


def test_a_tier_approved_local_override_and_the_destination_disagree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """RT-032 pinned: the gate judges the override, the request follows the primary.

    ``router.py:586-591`` enforces the tier against the ``model=`` override
    prefix; ``_get_litellm_kwargs`` (``router.py:368-371``) sets ``api_base``
    from the slot primary. Here the gate approved ``ollama`` (local) and the
    dispatch carried the primary's cloud host.
    """
    state = _w5.prepare_state(monkeypatch, tmp_path)
    registry = {**_w5.cloud_registry(), **_w5.local_registry()}
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)
    recorder = _w5.DispatchRecorder(fail=False)
    recorder.install(monkeypatch)
    gw = _w5.make_gateway(state, primary=_w5.CLOUD_PRIMARY, tier="maximum")

    assert classify_provider(registry["ollama"]) == "local"
    assert gw.chat("extraction", [{"role": "user", "content": "hi"}], model="ollama/llama3") == "ok"

    assert recorder.records == [_w5.Dispatch("completion", "ollama/llama3", _w5.ANTHROPIC_BASE_URL)]
    assert gw._cloud_calls_made == 0


@pytest.mark.xfail(strict=True, reason="RT-032")
def test_a_tier_approved_local_override_is_not_sent_to_a_cloud_host(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Expected: what the gate approved as local is not sent to a cloud host."""
    state = _w5.prepare_state(monkeypatch, tmp_path)
    registry = {**_w5.cloud_registry(), **_w5.local_registry()}
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)
    recorder = _w5.DispatchRecorder(fail=False)
    recorder.install(monkeypatch)
    gw = _w5.make_gateway(state, primary=_w5.CLOUD_PRIMARY, tier="maximum")

    with contextlib.suppress(Exception):
        gw.chat("extraction", [{"role": "user", "content": "hi"}], model="ollama/llama3")

    assert "anthropic.com" not in (recorder.records[0].api_base or "")


# ── The TUI egress summary, which classifies from the registry ──────────────


def test_is_cloud_classifies_from_the_registry_not_from_the_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RT-030 fixed: ``_is_cloud`` reads the registry, not a name allowlist.

    ``ollama`` is local because the registry declares it so; ``local`` is not in
    the registry, so it is cloud — the old allowlist's false negative.
    """
    from openreview_cli.gateway.models import ProviderInfo
    from openreview_cli.tui.domain import egress

    registry = {
        "ollama": ProviderInfo(name="ollama", is_local=True, base_url="http://localhost:11434/v1"),
    }
    monkeypatch.setattr(egress, "load_registry", lambda: registry)

    assert egress._is_cloud("ollama") is False
    assert egress._is_cloud("local") is True
    # Undeclared runtime names are cloud too: they have no registry entry, and a
    # name nobody declared cannot be asserted to be local.
    for name in ("lmstudio", "localai", "vllm", "llama-cpp"):
        with monkeypatch.context() as ctx:
            ctx.setattr(
                egress,
                "get_slot_configs",
                lambda provider=name: {"extraction": {"provider": provider, "model": "m"}},
            )
            ctx.setattr(egress, "read_privacy_tier", lambda: "maximum")
            summary = egress.build_egress_summary(disable_pii=True, extraction_model="extraction")
        assert summary.cloud_warning is True, name


def test_egress_summary_does_not_claim_cloud_for_a_registry_local_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The false-positive twin: a base_url-local provider is not a cloud destination."""
    from openreview_cli.gateway.models import ProviderInfo
    from openreview_cli.tui.domain import egress

    monkeypatch.setattr(
        egress,
        "load_registry",
        lambda: {"lmstudio": ProviderInfo(name="lmstudio", base_url="http://localhost:1234/v1")},
    )
    monkeypatch.setattr(
        egress, "get_slot_configs", lambda: {"extraction": {"provider": "lmstudio", "model": "m"}}
    )
    monkeypatch.setattr(egress, "read_privacy_tier", lambda: "maximum")

    summary = egress.build_egress_summary(disable_pii=True, extraction_model="extraction")

    assert summary.destinations == ("lmstudio/m",)
    assert summary.cloud_warning is False


def test_egress_summary_does_not_claim_cloud_for_a_local_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A provider the registry resolves as local is not a cloud destination.

    ``gateway provider add --name lmstudio --base-url http://localhost:1234/v1``
    is a real local provider that ``classify_provider`` returns "local" for. The
    registry is patched so the verdict cannot depend on the developer's
    ``~/.config/openreview/models.json``, while the reachability of the real
    bundled ``ollama`` entry is still asserted.
    """
    _w5.prepare_state(monkeypatch, tmp_path)
    from openreview_cli.gateway.models import ProviderInfo
    from openreview_cli.gateway.registry import load_registry
    from openreview_cli.tui.domain import egress

    info = load_registry().get("ollama")
    assert info is not None and info.is_local is True
    monkeypatch.setattr(
        egress,
        "load_registry",
        lambda: {"lmstudio": ProviderInfo(name="lmstudio", base_url="http://localhost:1234/v1")},
    )
    monkeypatch.setattr(
        egress, "get_slot_configs", lambda: {"extraction": {"provider": "lmstudio", "model": "m"}}
    )
    monkeypatch.setattr(egress, "read_privacy_tier", lambda: "maximum")

    summary = egress.build_egress_summary(disable_pii=True, extraction_model="extraction")

    assert summary.cloud_warning is False


def test_egress_summary_warns_when_a_cloud_provider_is_named_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A remote provider named ``local`` still raises the egress warning.

    ``local`` is not in the registry, so it is unresolvable and therefore cloud —
    the name is not evidence of locality.
    """
    from openreview_cli.tui.domain import egress

    monkeypatch.setattr(egress, "load_registry", dict)
    monkeypatch.setattr(
        egress, "get_slot_configs", lambda: {"extraction": {"provider": "local", "model": "m"}}
    )
    monkeypatch.setattr(egress, "read_privacy_tier", lambda: "maximum")

    summary = egress.build_egress_summary(disable_pii=True, extraction_model="extraction")

    assert summary.cloud_warning is True


# ── Negative control: the oracle must be able to fail ───────────────────────


def test_negative_control_no_dispatch_oracle_rejects_a_real_dispatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A permissive tier DOES dispatch; the oracle must reject it.

    ``assert_no_dispatch`` is the predicate every strict-tier case trusts. Fed a
    run that reached the seam it must raise, or a green suite certifies nothing
    (plan section 9.3 rule 1). Demonstrated failing for real in
    ``draft/evidence/W5_negative_control_egress.txt``.
    """
    state = _w5.prepare_state(monkeypatch, tmp_path)
    registry = _w5.cloud_registry()
    monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)
    mark_pii_available()
    recorder = _w5.DispatchRecorder(fail=False)
    recorder.install(monkeypatch)
    gw = _w5.make_gateway(state, primary=_w5.CLOUD_PRIMARY, tier="performance")

    assert gw.chat("extraction", [{"role": "user", "content": "hi"}]) == "ok"
    assert len(recorder.records) == 1

    with pytest.raises(AssertionError, match="the network was reached"):
        _w5.assert_no_dispatch(recorder, "permissive tier control")
