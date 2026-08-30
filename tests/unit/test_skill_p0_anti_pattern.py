"""Skill anti-pattern guard: --no-pii on a non-maximum privacy tier.

Phase 7 P0 (CRITICAL). The skill must contain an explicit rule that
prevents the agent from silently running --no-pii on a cloud tier. This
test asserts the rule is present and structurally correct. It does NOT
exercise the runtime guard (that is the execution phase) — it is a
content test on skill/SKILL.md so a regression in the skill text is
caught by CI.

The rule must:

1. Be a numbered rule in the "Command Selection Rules" section.
2. Be labelled as critical (CRITICAL or similar).
3. Name the specific anti-pattern: --no-pii + balanced/performance tier.
4. Require the agent to check the active tier before running.
5. Require explicit user confirmation before running with raw text to
   cloud.
6. Name the destination provider in the warning.
7. State the two acceptable resolutions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

SKILL_PATH = Path(__file__).resolve().parents[2] / "skill" / "SKILL.md"


@pytest.fixture(scope="module")
def skill_text() -> str:
    assert SKILL_PATH.exists(), f"SKILL.md not found at {SKILL_PATH}"
    return SKILL_PATH.read_text(encoding="utf-8")


def test_rule_13_present_and_numbered(skill_text: str) -> None:
    """Rule 13 must exist as a numbered rule under Command Selection Rules."""
    # The rule is introduced by "13." at the start of a line followed by
    # bold text (**...**). This matches the style of the other rules.
    import re

    pattern = re.compile(
        r"^13\.\s+\*\*CRITICAL[^*]*\*\*",
        re.MULTILINE,
    )
    assert pattern.search(skill_text), (
        "Skill must contain a numbered Rule 13 introduced with "
        "**CRITICAL** bold styling. Either the rule was deleted or the "
        "wording changed."
    )


def test_rule_13_names_anti_pattern(skill_text: str) -> None:
    """Rule 13 must name the --no-pii + non-maximum tier combination."""
    # The rule must explicitly mention the dangerous combination.
    assert "--no-pii" in skill_text, "Rule text must reference --no-pii"
    # "maximum" must appear (it is the safe tier).
    assert "maximum" in skill_text, "Rule must name the maximum tier as the safe state"
    # The rule must name at least one of the cloud tiers.
    cloud_tiers = ("balanced", "performance")
    assert any(tier in skill_text for tier in cloud_tiers), (
        "Rule must name at least one non-maximum tier to identify the anti-pattern"
    )


def test_rule_13_requires_tier_check(skill_text: str) -> None:
    """Rule 13 must require the agent to check the tier before running."""
    # The rule must instruct the agent to read the tier value.
    assert "config get privacy.tier" in skill_text, (
        "Rule must instruct the agent to read the active tier with "
        "`config get privacy.tier` before running --no-pii on a workflow"
    )


def test_rule_13_requires_user_confirmation(skill_text: str) -> None:
    """Rule 13 must require explicit user confirmation before running."""
    # "confirmation" or "confirm" must appear in the rule.
    rule13_section = skill_text.split("13.", 1)[1].split("## ", 1)[0]
    assert "confirmation" in rule13_section.lower() or "confirm" in rule13_section.lower(), (
        "Rule 13 must require explicit user confirmation before running "
        "--no-pii on a non-maximum tier"
    )


def test_rule_13_names_destination_provider(skill_text: str) -> None:
    """Rule 13 must instruct the agent to name the destination provider."""
    rule13_section = skill_text.split("13.", 1)[1].split("## ", 1)[0]
    assert "provider" in rule13_section.lower(), (
        "Rule 13 must require the warning to name the destination provider"
    )


def test_rule_13_states_two_resolutions(skill_text: str) -> None:
    """Rule 13 must list the two acceptable resolutions."""
    rule13_section = skill_text.split("13.", 1)[1].split("## ", 1)[0]
    # The two resolutions are: (1) set tier to maximum, (2) drop --no-pii.
    assert "tier maximum" in rule13_section, (
        "Rule 13 must mention setting tier to maximum as one resolution"
    )
    # Removing --no-pii is the other resolution.
    assert "remove" in rule13_section.lower() and "--no-pii" in rule13_section, (
        "Rule 13 must mention removing --no-pii as the other resolution"
    )


def test_rule_13_exempts_negotiate(skill_text: str) -> None:
    """Rule 13 must note that negotiate is exempt (no --no-pii flag)."""
    rule13_section = skill_text.split("13.", 1)[1].split("## ", 1)[0]
    assert "negotiate" in rule13_section, (
        "Rule 13 must note that negotiate is exempt (no --no-pii flag)"
    )


def test_rule_12_unchanged(skill_text: str) -> None:
    """The pre-existing Rule 12 (Privacy routing) must still be present."""
    # Rule 12 must still be present and contain its key text.
    assert "12. **Privacy routing.**" in skill_text, "Rule 12 (Privacy routing) must remain intact"
    assert "config set privacy.tier maximum" in skill_text, "Rule 12's remediation text must remain"
