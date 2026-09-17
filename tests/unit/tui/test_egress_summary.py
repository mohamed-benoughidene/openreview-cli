"""Egress summary builder for the pre-flight modal (Phase 4).

``openreview_cli.tui.domain.egress`` describes what a review will send to
external providers.  It must stay litellm-free so the TUI import graph never
pulls the ~160 MB gateway router.
"""

from __future__ import annotations

import subprocess
import sys

# ── Summary construction ──────────────────────────────────────────────


def test_egress_summary_flags_local_only(monkeypatch) -> None:
    from openreview_cli.tui.domain import egress

    monkeypatch.setattr(egress, "read_privacy_tier", lambda: "maximum")
    monkeypatch.setattr(
        egress,
        "get_slot_configs",
        lambda: {"extraction": {"provider": "ollama", "model": "qwen3:8b", "configured": True}},
    )
    summary = egress.build_egress_summary(disable_pii=False, extraction_model="extraction")
    assert summary.privacy_tier == "maximum"
    assert summary.pii_stripped is True
    assert summary.cloud_warning is False
    assert any("ollama" in d for d in summary.destinations)


def test_egress_summary_warns_when_pii_off_with_cloud(monkeypatch) -> None:
    from openreview_cli.tui.domain import egress

    monkeypatch.setattr(egress, "read_privacy_tier", lambda: "performance")
    monkeypatch.setattr(
        egress,
        "get_slot_configs",
        lambda: {"extraction": {"provider": "openai", "model": "gpt-4o-mini", "configured": True}},
    )
    summary = egress.build_egress_summary(disable_pii=True, extraction_model="extraction")
    assert summary.pii_stripped is False
    assert summary.cloud_warning is True
    assert any("openai" in d for d in summary.destinations)
    # The warning appears in the rendered lines.
    assert any("uploaded" in line.lower() or "no pii" in line.lower() for line in summary.lines())


def test_egress_summary_no_cloud_warning_when_pii_stripped(monkeypatch) -> None:
    """A cloud destination with PII stripping ON is not a warning."""
    from openreview_cli.tui.domain import egress

    monkeypatch.setattr(egress, "read_privacy_tier", lambda: "balanced")
    monkeypatch.setattr(
        egress,
        "get_slot_configs",
        lambda: {"extraction": {"provider": "openai", "model": "gpt-4o-mini", "configured": True}},
    )
    summary = egress.build_egress_summary(disable_pii=False, extraction_model="extraction")
    assert summary.pii_stripped is True
    assert summary.cloud_warning is False
    assert not any("uploaded" in line.lower() for line in summary.lines())


def test_egress_summary_lists_distinct_slots_in_order(monkeypatch) -> None:
    """Extraction then QA, de-duplicated, in a deterministic order."""
    from openreview_cli.tui.domain import egress

    monkeypatch.setattr(egress, "read_privacy_tier", lambda: "performance")
    monkeypatch.setattr(
        egress,
        "get_slot_configs",
        lambda: {
            "extraction": {"provider": "openai", "model": "gpt-4o-mini", "configured": True},
            "qa": {"provider": "anthropic", "model": "claude-3", "configured": True},
        },
    )
    summary = egress.build_egress_summary(
        disable_pii=True, extraction_model="extraction", qa_model="qa"
    )
    assert summary.destinations == ("openai/gpt-4o-mini", "anthropic/claude-3")
    assert summary.cloud_warning is True


def test_egress_summary_deduplicates_shared_slot(monkeypatch) -> None:
    """Same model in extraction and QA must appear once."""
    from openreview_cli.tui.domain import egress

    monkeypatch.setattr(egress, "read_privacy_tier", lambda: "maximum")
    monkeypatch.setattr(
        egress,
        "get_slot_configs",
        lambda: {"extraction": {"provider": "ollama", "model": "qwen3:8b", "configured": True}},
    )
    summary = egress.build_egress_summary(
        disable_pii=False, extraction_model="extraction", qa_model="extraction"
    )
    assert summary.destinations == ("ollama/qwen3:8b",)


def test_egress_summary_handles_unconfigured_gateway(monkeypatch) -> None:
    """No slot config at all must not crash and must report no destinations."""
    from openreview_cli.tui.domain import egress

    monkeypatch.setattr(egress, "read_privacy_tier", lambda: "—")
    monkeypatch.setattr(egress, "get_slot_configs", lambda: {})
    summary = egress.build_egress_summary(disable_pii=False, extraction_model="extraction")
    assert summary.privacy_tier == "—"
    assert summary.destinations == ()
    assert summary.cloud_warning is False
    assert any("none configured" in line for line in summary.lines())


def test_egress_summary_skips_slot_without_provider(monkeypatch) -> None:
    """A configured-but-empty primary must not produce a blank destination."""
    from openreview_cli.tui.domain import egress

    monkeypatch.setattr(egress, "read_privacy_tier", lambda: "maximum")
    monkeypatch.setattr(
        egress,
        "get_slot_configs",
        lambda: {"extraction": {"provider": "", "model": "", "configured": False}},
    )
    summary = egress.build_egress_summary(disable_pii=False, extraction_model="extraction")
    assert summary.destinations == ()


# ── Rendering ─────────────────────────────────────────────────────────


def test_egress_summary_lines_report_privacy_state(monkeypatch) -> None:
    """The rendered lines state the tier, the PII state and the destinations."""
    from openreview_cli.tui.domain import egress

    monkeypatch.setattr(egress, "read_privacy_tier", lambda: "maximum")
    monkeypatch.setattr(
        egress,
        "get_slot_configs",
        lambda: {"extraction": {"provider": "ollama", "model": "qwen3:8b", "configured": True}},
    )
    lines = egress.build_egress_summary(disable_pii=False, extraction_model="extraction").lines()
    joined = "\n".join(lines)
    assert "maximum" in joined
    assert "PII stripped before egress: Yes" in joined
    assert "ollama/qwen3:8b" in joined


def test_egress_summary_lines_flag_disabled_pii(monkeypatch) -> None:
    from openreview_cli.tui.domain import egress

    monkeypatch.setattr(egress, "read_privacy_tier", lambda: "maximum")
    monkeypatch.setattr(
        egress,
        "get_slot_configs",
        lambda: {"extraction": {"provider": "ollama", "model": "qwen3:8b", "configured": True}},
    )
    lines = egress.build_egress_summary(disable_pii=True, extraction_model="extraction").lines()
    assert any("PII stripped before egress: NO" in line for line in lines)


# ── Litellm-free guard ────────────────────────────────────────────────


def test_egress_module_import_does_not_pull_litellm() -> None:
    """Importing tui.domain.egress must NOT pull litellm into sys.modules."""
    code = (
        "import openreview_cli.tui.domain.egress, sys; "
        "sys.exit(1 if 'litellm' in sys.modules else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode()
