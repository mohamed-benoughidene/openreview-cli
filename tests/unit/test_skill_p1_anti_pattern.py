"""Skill content tests for Phase 7 P1: cost-limit, recovery, and privacy tier.

P1.a — Cost-Limit Behavior (Phase 6 B3)
P1.b — Recovery Subsystem (current product behavior, not invented)
P1.c — Privacy Tier vs PII Stripping (Capability #10 expansion)

These are content tests on skill/SKILL.md. They encode the behavior
already established in the live CLI (P0 execution report) and in the
source (router.py:397, recovery/coordinator.py, recovery/models.py).
They are RED when the section is missing, GREEN when it documents the
actual behavior correctly.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SKILL_PATH = Path(__file__).resolve().parents[2] / "skill" / "SKILL.md"


@pytest.fixture(scope="module")
def skill_text() -> str:
    assert SKILL_PATH.exists(), f"SKILL.md not found at {SKILL_PATH}"
    return SKILL_PATH.read_text(encoding="utf-8")


def _section(text: str, heading_regex: str) -> str:
    """Return the body of the first H3/H4 section matching heading_regex."""
    # Find the heading line, then take everything until the next heading
    # at the same or higher level.
    match = re.search(heading_regex, text, re.MULTILINE)
    assert match, f"heading matching {heading_regex!r} not found"
    start = match.end()
    # Find the next ### or ## line after start.
    next_heading = re.search(r"^#{2,4} ", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


# ---------------------------------------------------------------------------
# P1.a — Cost-Limit Behavior
# ---------------------------------------------------------------------------


def test_p1a_section_exists(skill_text: str) -> None:
    """P1.a section must exist as a dedicated subsection in the skill."""
    pattern = re.compile(
        r"^#{2,4}\s+[^#\n]*Cost[- ]?Limit[^#\n]*$",
        re.MULTILINE | re.IGNORECASE,
    )
    assert pattern.search(skill_text), (
        "Skill must contain a dedicated Cost-Limit Behavior subsection. "
        "The Phase 6 B3 cost-limit behavior (exit 6, daily/session limits) "
        "is not currently documented in the skill."
    )


def test_p1a_documents_exit_code_6(skill_text: str) -> None:
    """P1.a must document that cost-limit breach terminates with exit 6."""
    section = _section(skill_text, r"^#{2,4}\s+[^#\n]*Cost[- ]?Limit[^#\n]*$")
    assert "6" in section, (
        "Cost-Limit section must mention exit code 6. Observed live: "
        "`Cost limit exceeded: ...` followed by `exit=6`."
    )


def test_p1a_distinguishes_daily_and_session(skill_text: str) -> None:
    """P1.a must distinguish daily and per-review/session limits."""
    section = _section(skill_text, r"^#{2,4}\s+[^#\n]*Cost[- ]?Limit[^#\n]*$")
    # The implementation checks daily_cents and per_review_cents separately.
    section_lower = section.lower()
    has_daily = "daily" in section_lower
    has_session = (
        "per-review" in section_lower or "per review" in section_lower or "session" in section_lower
    )
    assert has_daily and has_session, (
        "Cost-Limit section must distinguish daily limit from per-review/session "
        "limit. The implementation enforces both: `daily_cents` resets at local "
        "midnight; `per_review_cents` is per-session. See gateway/router.py:411-438."
    )


def test_p1a_no_blind_retry(skill_text: str) -> None:
    """P1.a must tell the agent NOT to blind-retry on cost-limit failure."""
    section = _section(skill_text, r"^#{2,4}\s+[^#\n]*Cost[- ]?Limit[^#\n]*$")
    section_lower = section.lower()
    # Must explicitly forbid blind retry. The Phase 6 B3 implementation
    # exits hard (sys.exit(6)); retrying the same command at the same
    # limit hits the same limit immediately.
    assert "do not" in section_lower or "never" in section_lower, (
        "Cost-Limit section must include a 'do not' or 'never' instruction "
        "covering blind retry. Phase 6 B3 is a hard exit, not a recoverable error."
    )
    assert "retry" in section_lower, (
        "Cost-Limit section must mention 'retry' so the no-retry rule is "
        "scoped to the failure mode, not interpreted as a blanket ban."
    )


def test_p1a_documents_remediation(skill_text: str) -> None:
    """P1.a must document the two remediation paths."""
    section = _section(skill_text, r"^#{2,4}\s+[^#\n]*Cost[- ]?Limit[^#\n]*$")
    section_lower = section.lower()
    # Two remediations: raise the limit, or wait for reset.
    has_raise = "raise" in section_lower or "increase" in section_lower
    has_wait = "wait" in section_lower or "reset" in section_lower or "midnight" in section_lower
    assert has_raise, (
        "Cost-Limit section must mention raising/increasing the limit as one "
        "remediation (config set gateway.cost_limits.daily_cents ...)."
    )
    assert has_wait, (
        "Cost-Limit section must mention waiting/reset as the other remediation "
        "(daily limit resets at local midnight; per-review is per-session)."
    )


def test_p1a_differs_from_provider_failure(skill_text: str) -> None:
    """P1.a must state that cost-limit differs from ordinary provider failure."""
    section = _section(skill_text, r"^#{2,4}\s+[^#\n]*Cost[- ]?Limit[^#\n]*$")
    # The implementation routes provider failures through recovery, but
    # cost-limit is a hard pre-call exit. The skill must call this out so
    # an agent does not invoke recovery for a cost-limit breach.
    has_diff = "not" in section.lower() and (
        "recover" in section.lower()
        or "provider" in section.lower()
        or "fallback" in section.lower()
    )
    assert has_diff, (
        "Cost-Limit section must explain that cost-limit differs from "
        "ordinary provider failure (no recovery, no fallback — it is a hard "
        "pre-call exit at gateway/router.py:418 / 434)."
    )


# ---------------------------------------------------------------------------
# P1.b — Recovery Subsystem
# ---------------------------------------------------------------------------


def test_p1b_section_exists(skill_text: str) -> None:
    """P1.b section must exist as a dedicated subsection in the skill."""
    pattern = re.compile(
        r"^#{2,4}\s+[^#\n]*Recovery[^#\n]*(Subsystem|Behavior|Strategy|Fallback)[^#\n]*$",
        re.MULTILINE | re.IGNORECASE,
    )
    assert pattern.search(skill_text), (
        "Skill must contain a dedicated Recovery Subsystem section. "
        "The current skill does not document the recovery coordinator, "
        "its four strategies, or its privacy-tier interaction. See "
        "graphify-out communities 'Any (recovery)', 'coordinator.py "
        "(recovery)' for structural evidence; see "
        "src/openreview_cli/recovery/coordinator.py:50-60 for strategy "
        "selection."
    )


def test_p1b_documents_strategy_chain(skill_text: str) -> None:
    """P1.b must name the four strategies and their dispatch logic."""
    section = _section(
        skill_text,
        r"^#{2,4}\s+[^#\n]*Recovery[^#\n]*(Subsystem|Behavior|Strategy|Fallback)[^#\n]*$",
    )
    section_lower = section.lower()
    # Four strategies from coordinator.py:31-35.
    strategies = [
        ("auto_retry", "auto-retry" in section_lower or "auto retry" in section_lower),
        ("provider_fallback", "fallback" in section_lower or "provider" in section_lower),
        ("stage_isolation", "isolation" in section_lower or "stage" in section_lower),
        ("graceful_degradation", "degradation" in section_lower or "graceful" in section_lower),
    ]
    missing = [name for name, found in strategies if not found]
    assert not missing, (
        f"Recovery section must document all four strategies. Missing: {missing}. "
        "See recovery/coordinator.py:31-35 (imports) and :50-60 (selection)."
    )


def test_p1b_documents_privacy_tier_interaction(skill_text: str) -> None:
    """P1.b must document that strict tier blocks cloud fallback (SC-04)."""
    section = _section(
        skill_text,
        r"^#{2,4}\s+[^#\n]*Recovery[^#\n]*(Subsystem|Behavior|Strategy|Fallback)[^#\n]*$",
    )
    # Strict tier (= product maximum) blocks cloud fallback.
    assert "maximum" in section.lower() or "strict" in section.lower(), (
        "Recovery section must mention that the maximum/strict tier blocks "
        "cloud fallback. See recovery/strategies/provider_fallback.py:84 — "
        "if user_privacy_tier == strict and provider is cloud, skip."
    )
    assert "fallback" in section.lower() or "cloud" in section.lower(), (
        "Recovery section must explicitly connect tier to fallback/cloud behavior."
    )


def test_p1b_documents_cost_limit_exclusion(skill_text: str) -> None:
    """P1.b must state that cost-limit failures bypass recovery."""
    section = _section(
        skill_text,
        r"^#{2,4}\s+[^#\n]*Recovery[^#\n]*(Subsystem|Behavior|Strategy|Fallback)[^#\n]*$",
    )
    section_lower = section.lower()
    has_cost = "cost" in section_lower and "limit" in section_lower
    has_bypass = "not" in section_lower and (
        "recover" in section_lower or "bypass" in section_lower or "skip" in section_lower
    )
    assert has_cost, (
        "Recovery section must mention cost-limit (the cost-limit case is a "
        "hard exit that recovery does not catch — see errors.py:10-12 and "
        "router.py:418 / 434 — cost_limit_error calls sys.exit(6))."
    )
    assert has_bypass, "Recovery section must state that cost-limit failures bypass recovery."


def test_p1b_documents_when_to_stop(skill_text: str) -> None:
    """P1.b must tell the agent when to stop and surface a user-guided error."""
    section = _section(
        skill_text,
        r"^#{2,4}\s+[^#\n]*Recovery[^#\n]*(Subsystem|Behavior|Strategy|Fallback)[^#\n]*$",
    )
    section_lower = section.lower()
    # When all strategies exhausted, recovery produces a user-guided error
    # (coordinator.py:181-188) — agent must surface it and stop.
    has_stop = "stop" in section_lower or "halt" in section_lower or "abort" in section_lower
    has_user = "user" in section_lower
    assert has_stop, (
        "Recovery section must include a 'stop/halt' instruction for when "
        "all strategies are exhausted (coordinator.py:181-188 → user_guided_recovery)."
    )
    assert has_user, (
        "Recovery section must state that the agent must surface the "
        "user-guided error to the user (no silent retry)."
    )


def test_p1b_no_blind_retry(skill_text: str) -> None:
    """P1.b must tell the agent NOT to blind-retry on unrecoverable errors."""
    section = _section(
        skill_text,
        r"^#{2,4}\s+[^#\n]*Recovery[^#\n]*(Subsystem|Behavior|Strategy|Fallback)[^#\n]*$",
    )
    section_lower = section.lower()
    has_no_retry = (
        "do not" in section_lower or "never" in section_lower
    ) and "retry" in section_lower
    assert has_no_retry, (
        "Recovery section must include a no-blind-retry rule. Recovery itself "
        "exhausts strategies; the agent must not loop with the same command."
    )


# ---------------------------------------------------------------------------
# P1.c — Privacy Tier vs PII Stripping
# ---------------------------------------------------------------------------


def test_p1c_section_exists(skill_text: str) -> None:
    """P1.c must be a dedicated subsection in or after Capability #10."""
    # Match a section that explicitly addresses the distinction between
    # privacy tier and PII stripping.
    pattern = re.compile(
        r"^#{2,4}\s+[^#\n]*(Privacy\s*Tier\s*vs|Privacy.*PII\s*Strip|Tier.*PII\s*Strip|Tier\s*vs\s*PII)[^#\n]*$",
        re.MULTILINE | re.IGNORECASE,
    )
    assert pattern.search(skill_text), (
        "Skill must contain a dedicated subsection that explicitly addresses "
        "the distinction between privacy tier and PII stripping. The current "
        "Capability #10 mentions the distinction in one sentence; the Phase 7 "
        "live P0 evidence shows an agent can still conflate them (S-5 reproduced "
        "exfiltration under balanced + --no-pii)."
    )


def test_p1c_names_all_three_tiers(skill_text: str) -> None:
    """P1.c must name all three tiers: maximum, balanced, performance."""
    section = _section(
        skill_text,
        r"^#{2,4}\s+[^#\n]*(Privacy\s*Tier\s*vs|Privacy.*PII\s*Strip|Tier.*PII\s*Strip|Tier\s*vs\s*PII)[^#\n]*$",
    )
    section_lower = section.lower()
    for tier in ("maximum", "balanced", "performance"):
        assert tier in section_lower, (
            f"Privacy Tier vs PII Stripping section must name the {tier!r} tier. "
            "Source: gateway/tier_config.py:13-15 (PrivacyTier enum)."
        )


def test_p1c_explains_what_no_pii_does(skill_text: str) -> None:
    """P1.c must clearly state what --no-pii actually does (disables stripping)."""
    section = _section(
        skill_text,
        r"^#{2,4}\s+[^#\n]*(Privacy\s*Tier\s*vs|Privacy.*PII\s*Strip|Tier.*PII\s*Strip|Tier\s*vs\s*PII)[^#\n]*$",
    )
    section_lower = section.lower()
    assert "--no-pii" in section_lower, (
        "Privacy Tier vs PII Stripping section must reference --no-pii explicitly."
    )
    # Must say it disables stripping, not that it controls tier/locality.
    assert "strip" in section_lower, (
        "Section must say --no-pii disables/affects stripping (it does NOT "
        "control inference locality; the tier does)."
    )


def test_p1c_explains_when_pii_stripping_occurs(skill_text: str) -> None:
    """P1.c must state when PII stripping occurs (always except --no-pii)."""
    section = _section(
        skill_text,
        r"^#{2,4}\s+[^#\n]*(Privacy\s*Tier\s*vs|Privacy.*PII\s*Strip|Tier.*PII\s*Strip|Tier\s*vs\s*PII)[^#\n]*$",
    )
    section_lower = section.lower()
    # Must state PII stripping is automatic, separate from tier.
    has_automatic = (
        "automatic" in section_lower
        or "always" in section_lower
        or "by default" in section_lower
        or "default" in section_lower
    )
    assert has_automatic, (
        "Section must state that PII stripping is automatic / by default / "
        "always (independent of tier). Source: pii/engine.py: strip stage "
        "runs unless no_pii=True (review/runner.py:268-269)."
    )


def test_p1c_explains_no_pii_danger_under_cloud(skill_text: str) -> None:
    """P1.c must explain why --no-pii is dangerous under cloud-capable tiers."""
    section = _section(
        skill_text,
        r"^#{2,4}\s+[^#\n]*(Privacy\s*Tier\s*vs|Privacy.*PII\s*Strip|Tier.*PII\s*Strip|Tier\s*vs\s*PII)[^#\n]*$",
    )
    section_lower = section.lower()
    # Must mention the danger: --no-pii under balanced/performance sends raw
    # text to cloud.
    mentions_cloud = "cloud" in section_lower
    mentions_danger = (
        "danger" in section_lower
        or "exfil" in section_lower
        or "raw" in section_lower
        or "unredact" in section_lower
        or "leak" in section_lower
        or "sensitive" in section_lower
    )
    assert mentions_cloud, (
        "Section must mention cloud (the danger is --no-pii under "
        "cloud-capable tiers sending raw text to the cloud LLM)."
    )
    assert mentions_danger, (
        "Section must describe why --no-pii under cloud is dangerous "
        "(e.g. raw, unredacted, sensitive, exfiltration)."
    )


def test_p1c_references_rule_13(skill_text: str) -> None:
    """P1.c must cross-reference Rule 13 (the CRITICAL anti-pattern rule)."""
    section = _section(
        skill_text,
        r"^#{2,4}\s+[^#\n]*(Privacy\s*Tier\s*vs|Privacy.*PII\s*Strip|Tier.*PII\s*Strip|Tier\s*vs\s*PII)[^#\n]*$",
    )
    assert "Rule 13" in section or "rule 13" in section.lower(), (
        "Privacy Tier vs PII Stripping section must cross-reference Rule 13 "
        "so the agent connects the P1.c guidance to the existing anti-pattern "
        "guard. Rule 13 is the enforcement mechanism; P1.c is the explanation."
    )


# ---------------------------------------------------------------------------
# Cross-cutting — Rule 13 must still be present and unchanged (regression).
# ---------------------------------------------------------------------------


def test_rule_13_still_present(skill_text: str) -> None:
    """P0 Rule 13 must remain intact after P1 edits (no regression)."""
    assert re.search(r"^13\.\s+\*\*CRITICAL[^*]*\*\*", skill_text, re.MULTILINE), (
        "P0 Rule 13 (CRITICAL anti-pattern) must remain in the skill. "
        "P1 must NOT remove or weaken it."
    )


# ---------------------------------------------------------------------------
# HEAVY-review follow-ups: UTC reset, allow-partial-pii, dispatch split,
# persistence wiring, Rule 13 back-references, Common Mistakes row.
# ---------------------------------------------------------------------------


def test_p1a_documents_utc_reset(skill_text: str) -> None:
    """P1.a must state the daily limit resets at UTC midnight, not local."""
    section = _section(skill_text, r"^#{2,4}\s+[^#\n]*Cost[- ]?Limit[^#\n]*$")
    section_lower = section.lower()
    has_utc = "utc" in section_lower
    has_local = "local" in section_lower
    assert has_utc, (
        "Cost-Limit section must mention UTC. Source: storage/costs.py:41 uses "
        "`date(created_at) = date('now')`; SQLite's date('now') returns UTC. "
        "The user-facing message in router.py:420 says 'local midnight' but the "
        "SQL is UTC — this is a documented drift."
    )
    assert has_local, (
        "Cost-Limit section must also call out 'local midnight' to flag the "
        "drift in the CLI's user-facing message."
    )


def test_p1c_documents_allow_partial_pii(skill_text: str) -> None:
    """P1.c must mention --allow-partial-pii as a related PII-skip path."""
    section = _section(
        skill_text,
        r"^#{2,4}\s+[^#\n]*(Privacy\s*Tier\s*vs|Privacy.*PII\s*Strip|Tier.*PII\s*Strip|Tier\s*vs\s*PII)[^#\n]*$",
    )
    assert "--allow-partial-pii" in section, (
        "Privacy Tier vs PII Stripping section must mention --allow-partial-pii. "
        "It is a different PII-skip path (only failed pages leak) but still "
        "falls under Rule 13's anti-pattern check when paired with a non-`maximum` "
        "tier. See pii/engine.py:191-197 (allow_partial=True) and "
        "pipeline/adapters/strip.py:91-98 (PartialProcessingError)."
    )


def test_p1b_dispatch_table_split_by_site(skill_text: str) -> None:
    """P1.b dispatch table must distinguish gateway-failure from stage-failure paths."""
    section = _section(
        skill_text,
        r"^#{2,4}\s+[^#\n]*Recovery[^#\n]*(Subsystem|Behavior|Strategy|Fallback)[^#\n]*$",
    )
    # The HEAVY review found that `transient` in the gateway-failure path goes
    # to `provider_fallback` only (no auto_retry), while the same category in
    # the stage-failure path chains `auto_retry -> stage_isolation`. The table
    # must split these.
    assert "gateway-failure path" in section.lower(), (
        "Recovery dispatch table must name the gateway-failure path explicitly. "
        "Source: coordinator.py:220-239."
    )
    assert "stage-failure path" in section.lower(), (
        "Recovery dispatch table must name the stage-failure path explicitly. "
        "Source: coordinator.py:142-176."
    )


def test_p1b_persistence_paragraph_honest(skill_text: str) -> None:
    """P1.b persistence paragraph must state the user-facing pipeline does NOT wire db_path."""
    section = _section(
        skill_text,
        r"^#{2,4}\s+[^#\n]*Recovery[^#\n]*(Subsystem|Behavior|Strategy|Fallback)[^#\n]*$",
    )
    section_lower = section.lower()
    # The HEAVY review found that review/runner.py:248-251 constructs the
    # coordinator without db_path, so persistence is test-only. The skill
    # must not promise the user a row exists.
    assert (
        "db_path" in section or "test-only" in section_lower or "not currently" in section_lower
    ), (
        "Recovery persistence paragraph must state that the user-facing "
        "review pipeline does not currently wire db_path. The persistence "
        "lifecycle is exercised in tests only; no row is created in "
        "review/runner.py:248-251."
    )


def test_rule_13_has_back_references(skill_text: str) -> None:
    """Rule 13 must point forward to P1.c and the Recovery section."""
    rule13 = re.search(
        r"^13\.\s+\*\*CRITICAL[^*]*\*\*.*?(?=\n## |\Z)",
        skill_text,
        re.MULTILINE | re.DOTALL,
    )
    assert rule13, "Rule 13 not found"
    rule13_text = rule13.group(0)
    assert "Privacy Tier vs PII Stripping" in rule13_text, (
        "Rule 13 must back-reference the Capability 10 'Privacy Tier vs PII "
        "Stripping' subsection so an agent reading Rule 13 first knows where "
        "the rationale lives."
    )
    assert "Recovery Subsystem" in rule13_text, (
        "Rule 13 must back-reference the Recovery Subsystem subsection so the "
        "tier ↔ fallback interaction is findable from Rule 13."
    )


def test_common_mistakes_table_has_cost_limit_row(skill_text: str) -> None:
    """The Common Mistakes table must include a row for the cost-limit exit."""
    # The table is in Section 7; the new row is identified by the "Cost limit
    # exceeded" string and the explicit reference to (P1.a).
    assert "Cost limit exceeded" in skill_text, (
        "Common Mistakes table must include a row for the cost-limit exit "
        "so an agent scanning the table alone can route to (P1.a)."
    )
    assert "exit code 6" in skill_text or "code 6" in skill_text, (
        "Cost-limit row must mention exit code 6 so the agent can map the "
        "observed exit status to the failure mode."
    )
