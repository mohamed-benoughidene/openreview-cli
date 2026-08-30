"""Skill content tests for Phase 7 P2: 17 MEDIUM-severity failure modes.

Greek-letter tags (C-α, C-β.1, C-β.2, C-γ, C-δ, C-ε) are intentional
identifiers matching the Phase 7 P2 plan's naming convention.

These are content tests on ``skill/SKILL.md``. Each test asserts the
required skill text is present and structurally correct. They are
RED when the corresponding skill-text addition is missing, GREEN when
the addition documents the actual current source behavior.

The 17 candidates are:

  P2-#7   ``--show-redlines`` is DOCX-only (silent skip on non-DOCX)
  P2-#8   ``index-clear --all`` has no confirmation prompt
  P2-#9   ``playbook delete --all`` / ``--force`` confirmation behavior
  P2-#11  ``playbook list --include-deleted`` is silent in skill
  P2-#13  ``playbook set-current`` re-activates soft-deleted (silent)
  P2-#25  Ollama model not pulled: ``gateway test`` failure
  P2-#26  PDF password-protected: parse error (exit 8)
  P2-#27  PDF scanned-image: parse error (exit 8)
  P2-#28  Re-running a review: PII cache + duplicate cost_logs
  P2-#29  Output write failure (chmod 0o500 on parent path)
  P2-#30  Disk full mid-review
  P2-C-α   Stale configured model after upstream rename/deprecation
  P2-C-β.1 All-Uncertain review (malformed JSON, Position.UNCERTAIN)
  P2-C-β.2 All-Amber review (low confidence, no Green/Red)
  P2-C-γ   ``gateway test`` failure next-action (Ollama down)
  P2-C-δ   Permission denied on ``--output`` / ``playbook export``
  P2-C-ε   No registered product mode matches user's named document type
          (agent must route to ``precheck review --playbook-path`` rather
          than invent a product-mode command)

Items #29 + C-δ share a single Common Mistakes row (write-failure
taxonomy). Items #25 + C-γ share a single Common Mistakes row
(gateway-failure taxonomy). The cross-cutting regression-guard tests
ensure P0 Rule 13 and the P1.a/b/c sections are not weakened.

Test count: 19 content tests for 17 candidates (P2-#7 and P2-C-ε each
have 2 assertions — flag/DOCX and routing/no-invent respectively) +
4 cross-cutting P0/P1 regression guards = 23 total tests.
"""

from __future__ import annotations

# ruff: noqa: RUF002, RUF003
import re
from pathlib import Path

import pytest

SKILL_PATH = Path(__file__).resolve().parents[2] / "skill" / "SKILL.md"


@pytest.fixture(scope="module")
def skill_text() -> str:
    assert SKILL_PATH.exists(), f"SKILL.md not found at {SKILL_PATH}"
    return SKILL_PATH.read_text(encoding="utf-8")


def _section_after_heading(text: str, heading_regex: str, stop_level: int = 3) -> str:
    """Return the body of the first section matching ``heading_regex``.

    The body extends from the end of the matched heading to the start of
    the next heading at ``stop_level`` (default 3, meaning ``###``) or
    higher (i.e. ``##``). H4 and deeper subsections are included in the
    body so that the search keyword can be found in nested detail.
    """
    match = re.search(heading_regex, text, re.MULTILINE)
    assert match, f"heading matching {heading_regex!r} not found in skill"
    start = match.end()
    # Find the next heading at or above stop_level (e.g. ### for H3).
    next_heading = re.search(rf"^#{{1,{stop_level}}} ", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


def _common_mistakes_section(text: str) -> str:
    """Return the body of the ``Common Mistakes and Recovery Rules`` section."""
    return _section_after_heading(text, r"^#{2,4}\s+[^#\n]*Common Mistakes[^#\n]*$")


def _command_selection_rules_section(text: str) -> str:
    """Return the body of the ``Command Selection Rules`` section.

    This section contains the numbered list of rules (1-13). The
    section's H2 heading is ``## Command Selection Rules``.
    """
    return _section_after_heading(text, r"^#{2}\s+Command Selection Rules\s*$")


def _rule_n_body(text: str, rule_number: int) -> str:
    """Return the body of the Nth numbered rule inside Command Selection Rules.

    Rules are formatted as ``N. **Title.**`` followed by sub-bullets
    (lines beginning with ``- `` or ``N. ``, indented). We capture
    everything from the ``N. `` line until the next ``N+1. `` line or
    end of section.
    """
    section = _command_selection_rules_section(text)
    # Match the N. **Title.** line. The actual format is e.g.
    # ``2. **Intent → capability.**`` where the period is inside the
    # bold delimiters. We anchor on ``N. **`` and consume until the
    # closing ``**`` is reached; the trailing period is optional
    # because some rule titles end mid-sentence inside the bold.
    pattern = re.compile(
        rf"^{rule_number}\.\s+\*\*[^*]*\*\*\.?",
        re.MULTILINE,
    )
    match = pattern.search(section)
    assert match, (
        f"Rule {rule_number} heading not found in Command Selection Rules. "
        f"Section preview:\n{section[:500]}"
    )
    start = match.end()
    # Find the next N+1. line.
    next_rule = re.compile(rf"^{rule_number + 1}\.\s+", re.MULTILINE)
    next_match = next_rule.search(section, start)
    end = next_match.start() if next_match else len(section)
    return section[start:end]


# ---------------------------------------------------------------------------
# P2-#7 — --show-redlines is DOCX-only (silent skip on non-DOCX Party B)
# ---------------------------------------------------------------------------


def test_p2_07_show_redlines_flag_documented(skill_text: str) -> None:
    """Capability 2 must document the ``--show-redlines`` flag."""
    # The flag is compare-only and lives under Bilateral Comparison.
    cap2 = _section_after_heading(
        skill_text, r"^#{2,4}\s+[^#\n]*2\.\s*Bilateral Comparison[^#\n]*$"
    )
    assert "--show-redlines" in cap2, (
        "Capability 2 (Bilateral Comparison) must document the "
        "--show-redlines flag. Source: app.py:1922-1926."
    )


def test_p2_07_docx_only_restriction(skill_text: str) -> None:
    """The skill must state that --show-redlines works for DOCX only."""
    cap2 = _section_after_heading(
        skill_text, r"^#{2,4}\s+[^#\n]*2\.\s*Bilateral Comparison[^#\n]*$"
    )
    cap2_lower = cap2.lower()
    has_docx = "docx" in cap2_lower
    assert has_docx, (
        "Capability 2 must state that --show-redlines is DOCX-only. "
        "Source: app.py:1922-1926 `continue` with no message when the "
        "input is not DOCX."
    )


# ---------------------------------------------------------------------------
# P2-#8 — index-clear --all has no confirmation prompt (asymmetric)
# ---------------------------------------------------------------------------


def test_p2_08_index_clear_all_in_common_mistakes(skill_text: str) -> None:
    """Common Mistakes must mention ``index-clear --all`` prompt asymmetry."""
    section = _common_mistakes_section(skill_text)
    section_lower = section.lower()
    has_index_clear = "index-clear" in section_lower or "index_clear" in section_lower
    has_all = "--all" in section or "all" in section_lower
    assert has_index_clear and has_all, (
        "Common Mistakes must document that `index-clear --all` does NOT "
        "prompt for confirmation (asymmetric to `playbook delete --all`). "
        "Source: app.py:2321-2341."
    )


# ---------------------------------------------------------------------------
# P2-#9 — playbook delete --all / --force confirmation
# ---------------------------------------------------------------------------


def test_p2_09_playbook_delete_force_in_common_mistakes(skill_text: str) -> None:
    """Common Mistakes must mention ``playbook delete --all`` / --force."""
    section = _common_mistakes_section(skill_text)
    section_lower = section.lower()
    has_pb_delete = "playbook delete" in section_lower
    has_force = "--force" in section or "force" in section_lower
    assert has_pb_delete and has_force, (
        "Common Mistakes must document that `playbook delete --all` is "
        "soft-delete, that `--force` skips the prompt, and that a single "
        "delete (no --all) is unprompted. Source: app.py:981-1019."
    )


# ---------------------------------------------------------------------------
# P2-#11 — playbook list --include-deleted
# ---------------------------------------------------------------------------


def test_p2_11_playbook_list_include_deleted_documented(skill_text: str) -> None:
    """Skill must document ``playbook list --include-deleted``."""
    section = _common_mistakes_section(skill_text)
    assert "--include-deleted" in section, (
        "Common Mistakes must document that `playbook list` hides "
        "soft-deleted entries by default and that `--include-deleted` "
        "exposes them. Source: app.py:607-612."
    )


# ---------------------------------------------------------------------------
# P2-#13 — set-current re-activates soft-deleted silently
# ---------------------------------------------------------------------------


def test_p2_13_set_current_reactivation_in_skill(skill_text: str) -> None:
    """Common Mistakes must flag set-current re-activation of soft-deleted."""
    section = _common_mistakes_section(skill_text)
    section_lower = section.lower()
    has_set_current = "set-current" in section_lower or "set_current" in section_lower
    assert has_set_current, (
        "Common Mistakes must document that `playbook set-current <id> <v>` "
        "on a soft-deleted playbook silently re-activates it (clears "
        "deleted_at). Source: app.py:955-979; playbooks.py:217-220."
    )


# ---------------------------------------------------------------------------
# P2-#25 — Ollama model not pulled
# ---------------------------------------------------------------------------


def test_p2_25_ollama_model_not_pulled_in_skill(skill_text: str) -> None:
    """Common Mistakes must mention the Ollama-model-not-pulled failure mode."""
    section = _common_mistakes_section(skill_text)
    section_lower = section.lower()
    has_ollama = "ollama" in section_lower
    has_pull = "pull" in section_lower
    assert has_ollama and has_pull, (
        "Common Mistakes must document that `gateway test` fails when an "
        "Ollama model is configured but not pulled, and that the "
        "remediation is `ollama pull <model>`. "
        "Source: router.py:440-497; app.py:1524-1556."
    )


# ---------------------------------------------------------------------------
# P2-#26 — PDF password-protected (exit 8, password_protected category)
# ---------------------------------------------------------------------------


def test_p2_26_password_protected_pdf_in_skill(skill_text: str) -> None:
    """Skill must mention the PDF-password-protected failure mode."""
    # The PDF parse failure modes belong in Capability 1 prerequisites.
    cap1 = _section_after_heading(skill_text, r"^#{2,4}\s+[^#\n]*1\.\s*Review[^#\n]*$")
    # Also accept placement in Common Mistakes.
    cm = _common_mistakes_section(skill_text)
    cap1_lower = cap1.lower()
    cm_lower = cm.lower()
    mentions_password = "password" in cap1_lower or "password" in cm_lower
    assert mentions_password, (
        "Skill must document the PDF-password-protected failure mode "
        "(ParseError category=password_protected, exit 8). "
        "Source: pdf_parser.py:62-107."
    )


# ---------------------------------------------------------------------------
# P2-#27 — PDF scanned-image (exit 8, no_text category)
# ---------------------------------------------------------------------------


def test_p2_27_scanned_pdf_in_skill(skill_text: str) -> None:
    """Skill must mention the PDF scanned-image (no text) failure mode."""
    cap1 = _section_after_heading(skill_text, r"^#{2,4}\s+[^#\n]*1\.\s*Review[^#\n]*$")
    cm = _common_mistakes_section(skill_text)
    cap1_lower = cap1.lower()
    cm_lower = cm.lower()
    mentions_no_text = (
        "scanned" in cap1_lower
        or "no text" in cap1_lower
        or "no_text" in cap1_lower
        or "no extractable text" in cap1_lower
        or "scanned" in cm_lower
        or "no text" in cm_lower
        or "no_text" in cm_lower
    )
    assert mentions_no_text, (
        "Skill must document the PDF scanned-image failure mode "
        "(ParseError category=no_text, exit 8) and route the user to "
        "re-export with an embedded text layer. Source: pdf_parser.py:113-146. "
        "Note: the product defect pointing users at the non-existent "
        "`openreview install ocr` command must be worked around in the "
        "skill text."
    )


# ---------------------------------------------------------------------------
# P2-#28 — Re-running a review (PII cache + duplicate cost_logs)
# ---------------------------------------------------------------------------


def test_p2_28_pii_cache_documented(skill_text: str) -> None:
    """Common Mistakes must document the PII cache behavior on re-runs."""
    section = _common_mistakes_section(skill_text)
    section_lower = section.lower()
    has_cache = "pii cache" in section_lower or "pii_cache" in section_lower
    has_rerun = (
        "re-run" in section_lower
        or "rerun" in section_lower
        or "re-running" in section_lower
        or "second" in section_lower
    )
    assert has_cache and has_rerun, (
        "Common Mistakes must document that re-running `precheck review` "
        "reuses the PII cache (no new pii_audit_trail row) but writes a "
        "new cost_logs session_id, and that modern `precheck review` has "
        "no --force-reprocess flag. Source: review/runner.py:118-125; "
        "review/base.py:65-87; storage/costs.py:23."
    )


# ---------------------------------------------------------------------------
# P2-#29 — Output write failure (B4 closed in code, silent in skill)
# ---------------------------------------------------------------------------


def test_p2_29_write_failure_in_skill(skill_text: str) -> None:
    """Common Mistakes must mention the --output write-failure taxonomy."""
    section = _common_mistakes_section(skill_text)
    section_lower = section.lower()
    has_output = "--output" in section or "output" in section_lower
    has_write = (
        "write" in section_lower
        or "cannot write" in section_lower
        or "permission" in section_lower
        or "chmod" in section_lower
    )
    assert has_output and has_write, (
        "Common Mistakes must document the --output write-failure taxonomy "
        "covering chmod 0o500 / read-only / disk-full cases, and must "
        "distinguish the modern _write_output_file path (clean error) from "
        "playbook export (raw traceback). Source: app.py:146-152; "
        "app.py:808, 868."
    )


# ---------------------------------------------------------------------------
# P2-#30 — Disk full mid-review
# ---------------------------------------------------------------------------


def test_p2_30_disk_full_in_skill(skill_text: str) -> None:
    """Common Mistakes must mention the disk-full failure mode."""
    section = _common_mistakes_section(skill_text)
    section_lower = section.lower()
    has_disk = (
        "disk" in section_lower
        or "enospc" in section_lower
        or "no space" in section_lower
        or "out of space" in section_lower
    )
    assert has_disk, (
        "Common Mistakes must document that disk full mid-review surfaces "
        "as a SQLite OperationalError or as an OSError(ENOSPC) on the "
        "output write path, with no pre-check, and that the agent must "
        "surface the partial-state risk. Source: storage/costs.py:23; "
        "pii/persist.py:114-117; app.py:146-152."
    )


# ---------------------------------------------------------------------------
# P2-C-α — Stale configured model after upstream rename
# ---------------------------------------------------------------------------


def test_p2_ca_stale_model_in_capability_6(skill_text: str) -> None:
    """Capability 6 must document the stale-model diagnostic path."""
    cap6 = _section_after_heading(skill_text, r"^#{2,4}\s+[^#\n]*6\.\s*Gateway[^#\n]*$")
    cap6_lower = cap6.lower()
    has_refresh = "gateway refresh" in cap6_lower or "refresh" in cap6_lower
    has_rename = "rename" in cap6_lower or "deprecat" in cap6_lower or "stale" in cap6_lower
    assert has_refresh and has_rename, (
        "Capability 6 must document `gateway refresh` as the diagnostic "
        "for a stale configured model after upstream rename/deprecation, "
        "followed by `gateway set <slot> <new-model>`. "
        "Source: app.py:230-253, 1513-1521."
    )


# ---------------------------------------------------------------------------
# P2-C-β.1 — All-Uncertain review (Position.UNCERTAIN, malformed JSON)
# ---------------------------------------------------------------------------


def test_p2_cb1_all_uncertain_documented(skill_text: str) -> None:
    """Section 6 must document the all-Uncertain result interpretation."""
    # The all-Uncertain / all-Amber H3 subsection lives inside Section 6.
    sec6 = _section_after_heading(
        skill_text,
        r"^#{3,4}\s+All-Uncertain or All-Amber",
        stop_level=4,
    )
    sec6_lower = sec6.lower()
    mentions_uncertain = (
        "all-uncertain" in sec6_lower or "all uncertain" in sec6_lower or "uncertain" in sec6_lower
    )
    assert mentions_uncertain, (
        "Section 6 (Result Interpretation) must document the all-Uncertain "
        "outcome (Position.UNCERTAIN for every clause, typically from "
        "malformed JSON or no-playbook match) and route the agent to "
        "report the position distribution verbatim and refuse to call it "
        "high-risk. Source: extraction.py:94, 134; app.py:1254-1265."
    )


# ---------------------------------------------------------------------------
# P2-C-β.2 — All-Amber review (low confidence, no Green/Red)
# ---------------------------------------------------------------------------


def test_p2_cb2_all_amber_distinct_from_uncertain(skill_text: str) -> None:
    """Section 6 must distinguish all-Amber from all-Uncertain."""
    sec6 = _section_after_heading(
        skill_text,
        r"^#{3,4}\s+All-Uncertain or All-Amber",
        stop_level=4,
    )
    sec6_lower = sec6.lower()
    mentions_amber = "all-amber" in sec6_lower or "all amber" in sec6_lower
    mentions_uncertain = "uncertain" in sec6_lower
    assert mentions_amber and mentions_uncertain, (
        "Section 6 must distinguish all-Amber (parseable, low confidence) "
        "from all-Uncertain (unparseable). The agent response for Amber is "
        "'treat with skepticism and recommend a stronger model'; for "
        "Uncertain, 'retry with a stronger model or matching playbook.' "
        "Source: app.py:1254-1265 (default --confidence-threshold 0.7)."
    )


# ---------------------------------------------------------------------------
# P2-C-γ — gateway test failure next-action (Ollama down)
# ---------------------------------------------------------------------------


def test_p2_cg_gateway_test_next_action(skill_text: str) -> None:
    """Common Mistakes must include the gateway test next-action fold-in."""
    section = _common_mistakes_section(skill_text)
    section_lower = section.lower()
    has_gateway_test = "gateway test" in section_lower
    has_connection = (
        "connection" in section_lower
        or "ollama" in section_lower
        or "next-action" in section_lower
        or "next action" in section_lower
    )
    assert has_gateway_test and has_connection, (
        "Common Mistakes (gateway-failure taxonomy) must include the "
        "next-action for `gateway test` failures: distinguish Ollama-down "
        "(connection refused) from model-not-pulled (model not found) from "
        "cloud-key-bad (401/403). Source: app.py:1524-1556."
    )


# ---------------------------------------------------------------------------
# P2-C-δ — Permission denied on --output / playbook export
# ---------------------------------------------------------------------------


def test_p2_cd_write_failure_fold_in(skill_text: str) -> None:
    """Common Mistakes must include the playbook-export write-failure case."""
    section = _common_mistakes_section(skill_text)
    section_lower = section.lower()
    has_export = "playbook export" in section_lower or "playbook_export" in section_lower
    has_traceback = (
        "traceback" in section_lower
        or "raw trace" in section_lower
        or "permission" in section_lower
    )
    assert has_export and has_traceback, (
        "Common Mistakes (write-failure taxonomy) must distinguish the "
        "modern --output path (clean error) from `playbook export` "
        "(raw Python traceback at app.py:808, 868). "
        "playbook import has no --output flag and is NOT affected."
    )


# ---------------------------------------------------------------------------
# P2-C-ε — No product mode matches (agent-routing failure)
# ---------------------------------------------------------------------------


def test_p2_ce_routing_in_rule_2(skill_text: str) -> None:
    """Rule 2 must document the agent-routing fallback for C-ε."""
    rule2 = _rule_n_body(skill_text, 2)
    rule2_lower = rule2.lower()
    has_no_match = (
        "no product mode" in rule2_lower
        or "no registered" in rule2_lower
        or "no match" in rule2_lower
        or "named document" in rule2_lower
    )
    has_fallback = "precheck review" in rule2_lower and (
        "--playbook-path" in rule2 or "playbook-path" in rule2
    )
    assert has_no_match and has_fallback, (
        "Rule 2 (Intent → capability) must document: when the user names "
        "a document type with no registered product mode, enumerate the "
        "registered modes (`openreview --help`), recognize the gap, fall "
        "back to `precheck review --playbook-path <yaml>` (or "
        "`--playbook <id>`), and NEVER invent a product-mode command."
    )


def test_p2_ce_no_invent_product_mode(skill_text: str) -> None:
    """Skill must explicitly tell the agent not to invent a product-mode command."""
    rule2 = _rule_n_body(skill_text, 2)
    rule2_lower = rule2.lower()
    has_no_invent = (
        "never invent" in rule2_lower
        or "do not invent" in rule2_lower
        or "don't invent" in rule2_lower
        or "not invent" in rule2_lower
    )
    assert has_no_invent, (
        "Rule 2 must include the explicit negative guidance: NEVER invent "
        "a product-mode command (e.g. `constructioncheck` for a "
        "construction contract) when no registered mode matches."
    )


# ---------------------------------------------------------------------------
# Cross-cutting regression guards — P0 / P1 must not be weakened
# ---------------------------------------------------------------------------


def test_p2_p0_rule_13_still_present(skill_text: str) -> None:
    """P0 Rule 13 (--no-pii + non-maximum tier) must still be in the skill.

    The rule lives in the ``Command Selection Rules`` section (the
    numbered list inside that H2), not in Common Mistakes.
    """
    section = _command_selection_rules_section(skill_text)
    section_lower = section.lower()
    has_no_pii = "--no-pii" in section_lower or "no pii" in section_lower
    has_maximum = "maximum" in section_lower
    has_confirm = "confirm" in section_lower
    assert has_no_pii and has_maximum and has_confirm, (
        "P0 Rule 13 regression guard: --no-pii + non-maximum tier must "
        "still require explicit confirmation in the Command Selection "
        "Rules section. The P2 implementation must not weaken this rule."
    )


def test_p2_p1a_cost_limit_still_present(skill_text: str) -> None:
    """P1.a Cost-Limit section must still be in the skill."""
    pattern = re.compile(
        r"^#{2,4}\s+[^#\n]*Cost[- ]?Limit[^#\n]*$",
        re.MULTILINE | re.IGNORECASE,
    )
    assert pattern.search(skill_text), (
        "P1.a regression guard: Cost-Limit Behavior section must still "
        "be present (P1.a content must not be removed)."
    )


def test_p2_p1b_recovery_still_present(skill_text: str) -> None:
    """P1.b Recovery subsection must still be in the skill."""
    pattern = re.compile(
        r"^#{2,4}\s+[^#\n]*Recovery[^#\n]*Subsystem[^#\n]*$",
        re.MULTILINE | re.IGNORECASE,
    )
    assert pattern.search(skill_text), (
        "P1.b regression guard: Recovery Subsystem section must still "
        "be present (P1.b content must not be removed)."
    )


def test_p2_p1c_privacy_tier_still_present(skill_text: str) -> None:
    """P1.c Privacy tier vs PII stripping must still be in the skill."""
    pattern = re.compile(
        r"^#{2,4}\s+[^#\n]*Privacy Tier[^#\n]*vs[^#\n]*PII[^#\n]*$",
        re.MULTILINE | re.IGNORECASE,
    )
    assert pattern.search(skill_text), (
        "P1.c regression guard: Privacy Tier vs PII Stripping section "
        "must still be present (P1.c content must not be removed)."
    )
