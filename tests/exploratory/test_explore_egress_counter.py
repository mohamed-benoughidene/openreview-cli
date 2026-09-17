"""Exploratory probes: egress summary, pre-flight modal data, cloud counter.

Covers the ``feat/design-ux-remediation`` egress-review feature (Phase 4):
``openreview_cli.tui.domain.egress`` (local vs cloud classification) and the
process-wide cloud-call counter in ``openreview_cli.gateway.models``.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import threading
from dataclasses import FrozenInstanceError

import pytest

from openreview_cli.tui.domain import egress as eg


def _patch(monkeypatch: pytest.MonkeyPatch, *, tier: str, slots: dict) -> None:
    monkeypatch.setattr(eg, "read_privacy_tier", lambda: tier)
    monkeypatch.setattr(eg, "get_slot_configs", lambda: slots)


# ── _is_cloud classification ───────────────────────────────────────────────


@pytest.mark.fast
def test_is_cloud_matches_only_literal_ollama_and_local() -> None:
    """FINDING (edge case): ``_LOCAL_PREFIXES`` is misnamed — matching is an
    exact, case-sensitive set membership, not a prefix scan.  Other common
    locally-hosted runtimes (``lmstudio``, ``vllm``, ``localai``) and even
    ``"Ollama"`` are classified as *cloud*."""
    assert eg._is_cloud("ollama") is False
    assert eg._is_cloud("local") is False
    assert eg._is_cloud("") is False
    for provider in ("openai", "anthropic", "localai", "lmstudio", "vllm", "Ollama", "ollama2"):
        assert eg._is_cloud(provider) is True, provider


# ── Local vs cloud slot combinations ───────────────────────────────────────


@pytest.mark.fast
@pytest.mark.parametrize(
    ("provider", "model", "expected_cloud_warning", "expected_dest"),
    [
        ("ollama", "qwen3:8b", False, "ollama/qwen3:8b"),
        ("local", "llama", False, "local/llama"),
        ("openai", "gpt-4o-mini", True, "openai/gpt-4o-mini"),
        ("anthropic", "claude-3", True, "anthropic/claude-3"),
    ],
)
def test_local_vs_cloud_warning_requires_pii_disabled(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    model: str,
    expected_cloud_warning: bool,
    expected_dest: str,
) -> None:
    _patch(
        monkeypatch,
        tier="balanced",
        slots={"extraction": {"provider": provider, "model": model, "configured": True}},
    )
    with_pii = eg.build_egress_summary(disable_pii=False, extraction_model="extraction")
    assert with_pii.destinations == (expected_dest,)
    assert with_pii.cloud_warning is False  # PII stripped -> never warns

    no_pii = eg.build_egress_summary(disable_pii=True, extraction_model="extraction")
    assert no_pii.cloud_warning is expected_cloud_warning
    assert no_pii.pii_stripped is False


@pytest.mark.fast
def test_provider_without_model_reports_bare_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch, tier="balanced", slots={"extraction": {"provider": "openai", "model": ""}})
    summary = eg.build_egress_summary(disable_pii=True, extraction_model="extraction")
    assert summary.destinations == ("openai",)
    assert summary.cloud_warning is True


@pytest.mark.fast
def test_model_without_provider_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch, tier="balanced", slots={"extraction": {"provider": "", "model": "gpt"}})
    summary = eg.build_egress_summary(disable_pii=True, extraction_model="extraction")
    assert summary.destinations == ()
    assert summary.cloud_warning is False


@pytest.mark.fast
def test_missing_slot_config_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, tier="balanced", slots={})
    summary = eg.build_egress_summary(disable_pii=True, extraction_model="extraction")
    assert summary.destinations == ()
    assert any("none configured" in line for line in summary.lines())


@pytest.mark.fast
def test_empty_extraction_model_yields_no_destinations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(
        monkeypatch,
        tier="balanced",
        slots={"extraction": {"provider": "openai", "model": "x"}},
    )
    summary = eg.build_egress_summary(disable_pii=True, extraction_model="")
    assert summary.destinations == ()


@pytest.mark.fast
def test_extraction_empty_qa_set_reports_qa_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(
        monkeypatch,
        tier="balanced",
        slots={
            "extraction": {"provider": "ollama", "model": "gemma"},
            "qa": {"provider": "openai", "model": "gpt"},
        },
    )
    summary = eg.build_egress_summary(disable_pii=True, extraction_model="", qa_model="qa")
    assert summary.destinations == ("openai/gpt",)
    assert summary.cloud_warning is True


@pytest.mark.fast
def test_distinct_slots_are_deduplicated_and_ordered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(
        monkeypatch,
        tier="performance",
        slots={
            "extraction": {"provider": "openai", "model": "gpt-4o-mini"},
            "qa": {"provider": "anthropic", "model": "claude-3"},
        },
    )
    summary = eg.build_egress_summary(
        disable_pii=True, extraction_model="extraction", qa_model="qa"
    )
    assert summary.destinations == ("openai/gpt-4o-mini", "anthropic/claude-3")


@pytest.mark.fast
def test_shared_slot_between_extraction_and_qa_is_listed_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(
        monkeypatch,
        tier="maximum",
        slots={"extraction": {"provider": "ollama", "model": "qwen3:8b"}},
    )
    summary = eg.build_egress_summary(
        disable_pii=False, extraction_model="extraction", qa_model="extraction"
    )
    assert summary.destinations == ("ollama/qwen3:8b",)


# ── Rendering ──────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_lines_render_full_local_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch,
        tier="maximum",
        slots={"extraction": {"provider": "ollama", "model": "qwen3:8b"}},
    )
    lines = eg.build_egress_summary(disable_pii=False, extraction_model="extraction").lines()
    assert lines[0] == "Privacy tier: maximum"
    assert lines[1] == "PII stripped before egress: Yes"
    assert lines[2] == ""
    assert lines[3] == "Destinations that may receive document text:"
    assert "  • ollama/qwen3:8b" in lines
    assert not any("uploaded" in line.lower() for line in lines)


@pytest.mark.fast
def test_lines_render_none_configured_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, tier="—", slots={})
    lines = eg.build_egress_summary(disable_pii=False, extraction_model="extraction").lines()
    assert "  (none configured — local only)" in lines


@pytest.mark.fast
def test_lines_flag_pii_disabled_and_cloud_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch,
        tier="balanced",
        slots={"extraction": {"provider": "openai", "model": "gpt-4o-mini"}},
    )
    lines = eg.build_egress_summary(disable_pii=True, extraction_model="extraction").lines()
    joined = "\n".join(lines)
    assert "PII stripped before egress: NO" in joined
    assert "raw document text will be uploaded" in joined


@pytest.mark.fast
def test_summary_is_frozen() -> None:
    summary = eg.EgressSummary(
        privacy_tier="maximum", pii_stripped=True, destinations=(), cloud_warning=False
    )
    with pytest.raises(FrozenInstanceError):
        summary.pii_stripped = False  # type: ignore[misc]


@pytest.mark.fast
def test_egress_module_import_is_litellm_free() -> None:
    code = (
        "import sys, openreview_cli.tui.domain.egress; "
        "sys.exit(1 if 'litellm' in sys.modules else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr.decode()


# ── Cloud-call counter ─────────────────────────────────────────────────────


@pytest.mark.fast
def test_counter_round_trip_and_router_reexport() -> None:
    from openreview_cli.gateway import models

    models.reset_total_cloud_calls()
    assert models.get_total_cloud_calls() == 0
    for _ in range(5):
        models.record_cloud_call()
    assert models.get_total_cloud_calls() == 5

    from openreview_cli.gateway.router import (
        get_total_cloud_calls,
        reset_total_cloud_calls,
    )

    assert get_total_cloud_calls() == 5
    reset_total_cloud_calls()
    assert models.get_total_cloud_calls() == 0


@pytest.mark.fast
def test_counter_is_exact_under_threads() -> None:
    """Rapid multithreaded increments stay exact.

    FINDING: ``record_cloud_call`` is a bare module-global ``+= 1`` with no
    lock, yet under CPython's GIL no lost updates were observable (16 threads
    times 50k increments, and at a 1e-6 s switch interval, all exact).  The counter is
    *effectively* thread-safe on this interpreter but not formally guarded.
    """
    from openreview_cli.gateway import models

    n_threads, per_thread = 16, 20_000
    models.reset_total_cloud_calls()

    def work() -> None:
        for _ in range(per_thread):
            models.record_cloud_call()

    threads = [threading.Thread(target=work) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert models.get_total_cloud_calls() == n_threads * per_thread


@pytest.mark.fast
def test_counter_is_exact_under_asyncio_tasks() -> None:
    from openreview_cli.gateway import models

    models.reset_total_cloud_calls()

    async def bump() -> None:
        for _ in range(1_000):
            models.record_cloud_call()

    async def main() -> None:
        await asyncio.gather(*(bump() for _ in range(8)))

    asyncio.run(main())
    assert models.get_total_cloud_calls() == 8_000


@pytest.mark.fast
def test_reset_racing_with_increments_does_not_crash() -> None:
    """Resetting while other threads increment leaves a non-negative count and
    never raises (the reset is a plain store, so no torn/invalid state)."""
    from openreview_cli.gateway import models

    models.reset_total_cloud_calls()
    stop = threading.Event()

    def spin() -> None:
        while not stop.is_set():
            models.record_cloud_call()

    workers = [threading.Thread(target=spin) for _ in range(4)]
    for t in workers:
        t.start()
    try:
        for _ in range(2_000):
            models.reset_total_cloud_calls()
    finally:
        stop.set()
        for t in workers:
            t.join()

    assert models.get_total_cloud_calls() >= 0


@pytest.mark.fast
def test_status_bar_read_helper_is_litellm_free_safe() -> None:
    """``read_cloud_call_count`` reflects the counter without importing litellm."""
    from openreview_cli.gateway import models
    from openreview_cli.tui.domain.gateway import read_cloud_call_count

    models.reset_total_cloud_calls()
    models.record_cloud_call()
    models.record_cloud_call()
    assert read_cloud_call_count() == 2
    models.reset_total_cloud_calls()


@pytest.mark.fast
def test_record_cloud_call_classifies_local_vs_cloud_slots() -> None:
    """``Gateway._record_cloud_call`` only counts *cloud* dispatches.

    Builds a ``Gateway`` without running ``__init__`` (which would read the real
    config/auth and import the full litellm stack) so the classification can be
    probed in isolation against synthetic slots.
    """
    from openreview_cli.gateway import models
    from openreview_cli.gateway.models import ProviderInfo
    from openreview_cli.gateway.router import Gateway

    models.reset_total_cloud_calls()

    gateway = Gateway.__new__(Gateway)
    gateway._cloud_calls_made = 0  # type: ignore[attr-defined]

    local = ProviderInfo(name="ollama", is_local=True, base_url="http://localhost:11434/v1")
    localhost = ProviderInfo(name="custom", base_url="http://127.0.0.1:8000/v1")
    cloud = ProviderInfo(name="openai", base_url="https://api.openai.com/v1")

    gateway._resolve_provider_info = lambda slot: local  # type: ignore[method-assign]
    gateway._record_cloud_call("extraction")
    assert (gateway._cloud_calls_made, models.get_total_cloud_calls()) == (0, 0)

    gateway._resolve_provider_info = lambda slot: localhost  # type: ignore[method-assign]
    gateway._record_cloud_call("extraction")
    assert gateway._cloud_calls_made == 0, "localhost base_url is local"

    gateway._resolve_provider_info = lambda slot: cloud  # type: ignore[method-assign]
    gateway._record_cloud_call("extraction")
    gateway._record_cloud_call("qa")
    assert (gateway._cloud_calls_made, models.get_total_cloud_calls()) == (2, 2)

    # Unknown slot config -> no provider -> nothing counted.
    gateway._resolve_provider_info = lambda slot: None  # type: ignore[method-assign]
    gateway._record_cloud_call("extraction")
    assert gateway._cloud_calls_made == 2

    # Unclassifiable provider (not local, no base_url) -> not counted as cloud.
    unclassifiable = ProviderInfo(name="bedrock", is_local=False, base_url=None)
    gateway._resolve_provider_info = lambda slot: unclassifiable  # type: ignore[method-assign]
    gateway._record_cloud_call("extraction")
    assert gateway._cloud_calls_made == 2, "resolution error must not coerce to cloud"

    # A recovery-driven model override: unknown prefix -> fail closed to cloud.
    gateway._record_cloud_call("extraction", provider_prefix="mystery-provider")
    assert gateway._cloud_calls_made == 3, "unknown override counts as cloud"

    # A known local override prefix is not counted.
    gateway._record_cloud_call("extraction", provider_prefix="ollama")
    assert gateway._cloud_calls_made == 3

    models.reset_total_cloud_calls()
