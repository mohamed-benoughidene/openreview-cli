"""Skill content tests for Phase 7 P3: 13 LOW-severity skill-doc gaps + 3 §11 LOW behavior gaps.

These are content tests on ``skill/SKILL.md``. Each test asserts the
required skill text is present and structurally correct. They are
RED when the corresponding skill-text addition is missing, GREEN when
the addition documents the actual current source behavior.

The 16 candidates are:

  P3-A1   ``precheck compare --format`` enum (text|json, exit 1 otherwise)
  P3-A6   ``playbook export --all``, ``--version``, ``--force`` flags
  P3-A10  ``playbook diff --json`` flag
  P3-A12  ``--mode-threshold MODE=VALUE`` (repeatable) for product modes
  P3-A14  ``retrieve --method dense`` formally documented
  P3-A15  ``retrieve --top-k``, ``--rerank-depth``, ``--no-header``, ``--db-dir``
  P3-A16  ``ingest --model``, ``--db-dir``
  P3-A18  Global ``--no-tui``, ``--debug`` flags
  P3-A19  ``chunk --summary`` flag
  P3-A20  ``negotiate --rationality``, ``--depth``, ``--weights``
  P3-A21  ``gateway providers --json``, ``gateway models --json``
  P3-A22  ``gateway costs --session <id>``
  P3-A23  ``export --template``, ``--mode``
  P3-B1   Two reviews in parallel: SQLite DB-level locking warning
  P3-B2   DOCX with no detectable clauses: "No documents processed." exit
  P3-B3   Empty file: "Provide a non-empty document file." ParseError

Items not in P3 (documented for completeness):
  P3-A17  ``precheck --force-reprocess`` flag location — verified OBSOLETE
          (no drift between skill line 116 and source at app.py:1148-1150).
  P3-C1   Runtime ``--no-pii`` cloud-provider abort — product fix in C1.
  P3-C2   UTC/local-midnight message — product fix in C2; skill side
          already CLOSED in P2 (skill lines 626, 642 correctly state
          "UTC midnight, not local midnight"). No P3 content test.
  P3-C3   PII ``Beta LLC``-style company names — skill doc added in
          P3 (Common Mistakes table). Covered by B1/B2/B3 table-row tests.
  P3-C4   Recovery persistence ``db_path`` wiring — product fix in C4.
  P3-C5   Skill frontmatter version mismatch — doc fix in C5.

Test count: 16 content tests for 16 candidates + 4 cross-cutting
P0/P1/P2 regression guards = 20 total tests.
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


def _section_after_heading(text: str, heading_regex: str, stop_level: int = 3) -> str:
    """Return the body of the first section matching ``heading_regex``.

    The body extends from the end of the matched heading to the start of
    the next heading at ``stop_level`` (default 3, meaning ``###``) or
    higher (i.e. ``##``). H4 and deeper subsections are included in
    the body so that the search keyword can be found in nested detail.
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


# ---------------------------------------------------------------------------
# A-items: skill-doc gaps for specific flags/subcommands
# ---------------------------------------------------------------------------


def test_p3_a1_compare_format_enum_documented(skill_text: str) -> None:
    """P3-A1: ``precheck compare --format`` enum (text|json) is documented."""
    body = _section_after_heading(skill_text, r"^#{3,4}\s+[^#\n]*Bilateral Comparison[^#\n]*$")
    assert "1782-1787" in body, "P3-A1: source line for compare format enum not cited"
    assert "text" in body and "json" in body, "P3-A1: text|json values not mentioned"
    assert "--format" in body, "P3-A1: --format flag not mentioned in Bilateral Comparison"


def test_p3_a6_playbook_export_flags_documented(skill_text: str) -> None:
    """P3-A6: ``playbook export --all``, ``--version``, ``--force`` documented."""
    body = _section_after_heading(skill_text, r"^#{3,4}\s+[^#\n]*Playbook Management[^#\n]*$")
    assert "--all" in body, "P3-A6: --all flag not mentioned"
    assert "--version" in body, "P3-A6: --version flag not mentioned"
    assert "--force" in body, "P3-A6: --force flag not mentioned"
    assert "export" in body, "P3-A6: export command not mentioned"


def test_p3_a10_playbook_diff_json_documented(skill_text: str) -> None:
    """P3-A10: ``playbook diff --json`` is documented."""
    body = _section_after_heading(skill_text, r"^#{3,4}\s+[^#\n]*Playbook Management[^#\n]*$")
    assert "playbook diff" in body, "P3-A10: playbook diff not mentioned"
    assert "--json" in body, "P3-A10: --json flag not mentioned in playbook section"


def test_p3_a12_mode_threshold_documented(skill_text: str) -> None:
    """P3-A12: ``--mode-threshold MODE=VALUE`` is documented."""
    body = _section_after_heading(skill_text, r"^#{3,4}\s+[^#\n]*Review & Produce Memo[^#\n]*$")
    assert "--mode-threshold" in body, "P3-A12: --mode-threshold flag not mentioned"
    assert "3111-3116" in body, "P3-A12: source line not cited"


def test_p3_a14_retrieve_method_dense_documented(skill_text: str) -> None:
    """P3-A14: ``retrieve --method dense`` is formally documented."""
    body = _section_after_heading(skill_text, r"^#{3,4}\s+[^#\n]*Retrieval[^#\n]*$")
    assert "--method" in body, "P3-A14: --method flag not mentioned"
    assert "dense" in body, "P3-A14: dense method not mentioned"
    assert "sparse" in body, "P3-A14: sparse method not mentioned (context for dense)"


def test_p3_a15_retrieve_flags_documented(skill_text: str) -> None:
    """P3-A15: ``retrieve --top-k``, ``--rerank-depth``, ``--no-header``, ``--db-dir`` documented."""
    body = _section_after_heading(skill_text, r"^#{3,4}\s+[^#\n]*Retrieval[^#\n]*$")
    assert "--top-k" in body, "P3-A15: --top-k flag not mentioned"
    assert "--rerank-depth" in body, "P3-A15: --rerank-depth flag not mentioned"
    assert "--no-header" in body, "P3-A15: --no-header flag not mentioned"
    assert "--db-dir" in body, "P3-A15: --db-dir flag not mentioned"


def test_p3_a16_ingest_flags_documented(skill_text: str) -> None:
    """P3-A16: ``ingest --model``, ``--db-dir`` documented."""
    body = _section_after_heading(skill_text, r"^#{3,4}\s+[^#\n]*Retrieval[^#\n]*$")
    assert "ingest --model" in body or "ingest` --model" in body, (
        "P3-A16: ingest --model not mentioned"
    )
    assert "1961" in body, "P3-A16: source line for ingest --model not cited"
    assert "1962" in body, "P3-A16: source line for ingest --db-dir not cited"


def test_p3_a18_global_flags_documented(skill_text: str) -> None:
    """P3-A18: Global ``--no-tui`` and ``--debug`` flags documented."""
    body = _section_after_heading(skill_text, r"^#{3,4}\s+[^#\n]*Review & Produce Memo[^#\n]*$")
    assert "--debug" in body, "P3-A18: --debug not mentioned"
    assert "--no-tui" in body, "P3-A18: --no-tui not mentioned"
    assert "309-313" in body, "P3-A18: --debug source line not cited"
    assert "33-35" in body, "P3-A18: --no-tui source line not cited"


def test_p3_a19_chunk_summary_documented(skill_text: str) -> None:
    """P3-A19: ``chunk --summary`` is documented."""
    body = _section_after_heading(skill_text, r"^#{3,4}\s+[^#\n]*Chunk \(standalone\)[^#\n]*$")
    assert "--summary" in body, "P3-A19: --summary flag not mentioned in Chunk section"
    assert "1657" in body, "P3-A19: source line not cited"


def test_p3_a20_negotiate_flags_documented(skill_text: str) -> None:
    """P3-A20: ``negotiate --rationality``, ``--depth``, ``--weights`` documented."""
    body = _section_after_heading(skill_text, r"^#{3,4}\s+[^#\n]*Negotiation[^#\n]*$")
    assert "--rationality" in body, "P3-A20: --rationality not mentioned"
    assert "--depth" in body, "P3-A20: --depth not mentioned"
    assert "--weights" in body, "P3-A20: --weights not mentioned"


def test_p3_a21_gateway_query_json_documented(skill_text: str) -> None:
    """P3-A21: ``gateway providers --json``, ``gateway models --json`` documented."""
    body = _section_after_heading(skill_text, r"^#{3,4}\s+[^#\n]*Gateway & Provider[^#\n]*$")
    assert "providers --json" in body or "providers` --json" in body, (
        "P3-A21: providers --json not mentioned"
    )
    assert "models" in body and "--json" in body, "P3-A21: models --json not mentioned"
    assert "1383" in body, "P3-A21: source line for providers not cited"


def test_p3_a22_gateway_costs_session_documented(skill_text: str) -> None:
    """P3-A22: ``gateway costs --session <id>`` documented."""
    body = _section_after_heading(skill_text, r"^#{3,4}\s+[^#\n]*Gateway & Provider[^#\n]*$")
    assert "--session" in body, "P3-A22: --session flag not mentioned"
    assert "1561-1573" in body, "P3-A22: source line not cited"


def test_p3_a23_export_flags_documented(skill_text: str) -> None:
    """P3-A23: ``export --template``, ``--mode`` documented."""
    body = _section_after_heading(skill_text, r"^#{3,4}\s+[^#\n]*Export Saved Reports[^#\n]*$")
    assert "--template" in body, "P3-A23: --template flag not mentioned"
    assert "--mode" in body, "P3-A23: --mode flag not mentioned"
    assert "3004-3010" in body, "P3-A23: source line not cited"


# ---------------------------------------------------------------------------
# B-items: behavior gaps from §11 (concurrent reviews, empty clauses, empty file)
# ---------------------------------------------------------------------------


def test_p3_b1_concurrent_reviews_documented(skill_text: str) -> None:
    """P3-B1: SQLite DB-level locking for concurrent reviews is documented."""
    body = _common_mistakes_section(skill_text)
    assert "Two reviews started in parallel" in body, "P3-B1: row header not present"
    assert "database is locked" in body, "P3-B1: SQLite locking error not documented"
    assert "platformdirs.user_data_dir" in body, "P3-B1: platformdirs anchor not cited"


def test_p3_b2_docx_no_clauses_documented(skill_text: str) -> None:
    """P3-B2: DOCX with 0 detectable clauses documented in Common Mistakes.

    Corrected after HEAVY review (H-2): the modern path tolerates
    0-clause DOCX (exit 0, "No clauses to assess."), it does NOT
    produce "No documents processed.". The skill must document the
    actual behavior.
    """
    body = _common_mistakes_section(skill_text)
    assert "DOCX with no detectable clauses" in body, "P3-B2: row not present"
    # The corrected behavior: exit 0, "No clauses to assess."
    assert "TOLERATES" in body or "No clauses to assess" in body, (
        "P3-B2 H-2: skill text still claims the wrong behavior. The modern "
        "path tolerates 0-clause DOCX (exit 0, 'No clauses to assess.'), it "
        "does NOT produce 'No documents processed.'. Update the row."
    )
    assert "parsing/stream.py" in body, "P3-B2: source anchor not cited"


def test_p3_b3_empty_file_documented(skill_text: str) -> None:
    """P3-B3: Empty file (0 bytes) handling documented in Common Mistakes."""
    body = _common_mistakes_section(skill_text)
    assert "empty file" in body, "P3-B3: row not present"
    assert "Provide a non-empty document file" in body, "P3-B3: ParseError message not documented"
    assert "0 bytes" in body, "P3-B3: file-size description not present"


# ---------------------------------------------------------------------------
# Cross-cutting: C3 (PII company names) is also in the Common Mistakes table.
# B1/B2/B3 tests above already verify the table structure; the C3 row
# is covered by test_p3_b1_concurrent_reviews_documented's "body"
# since C3 is in the same table.
# ---------------------------------------------------------------------------


def test_p3_c3_pii_company_names_documented(skill_text: str) -> None:
    """P3-C3: PII engine does NOT recognize company / organization names (skill doc)."""
    body = _common_mistakes_section(skill_text)
    assert "company names" in body.lower(), "P3-C3: company-name row not present"
    assert "Beta LLC" in body, "P3-C3: Beta LLC example not given"
    assert "pii/recognizers.py" in body, "P3-C3: source anchor not cited"


# ---------------------------------------------------------------------------
# Cross-cutting regression guards: P0 Rule 13 + P1.a/b/c sections intact
# ---------------------------------------------------------------------------


def test_p0_rule_13_preserved(skill_text: str) -> None:
    """P0 Rule 13 (CRITICAL --no-pii exfiltration rule) must still be present."""
    assert "Rule 13" in skill_text, "P0 regression: Rule 13 missing"
    assert "no_pii" in skill_text or "no-pii" in skill_text, "P0 regression: --no-pii not mentioned"


def test_p1a_cost_limit_section_preserved(skill_text: str) -> None:
    """P1.a Cost-Limit Behavior section must still be present."""
    body = _section_after_heading(skill_text, r"^#{3,4}\s+[^#\n]*Cost-Limit Behavior[^#\n]*$")
    assert "daily_cents" in body, "P1.a regression: daily_cents not in Cost-Limit section"
    assert "per_review_cents" in body, "P1.a regression: per_review_cents not in Cost-Limit section"


def test_p1b_recovery_section_preserved(skill_text: str) -> None:
    """P1.b Recovery Subsystem section must still be present."""
    body = _section_after_heading(skill_text, r"^#{3,4}\s+[^#\n]*Recovery Subsystem[^#\n]*$")
    assert "RecoveryCoordinator" in body or "auto_retry" in body, (
        "P1.b regression: recovery concepts missing"
    )


def test_p1c_privacy_tier_section_preserved(skill_text: str) -> None:
    """P1.c Privacy Tier vs PII Stripping section must still be present."""
    body = _section_after_heading(skill_text, r"^#{3,4}\s+[^#\n]*Privacy Tier vs PII[^#\n]*$")
    assert "Privacy tier" in body or "privacy tier" in body, "P1.c regression: tier concept missing"
    assert "PII stripping" in body or "PII strip" in body, (
        "P1.c regression: stripping concept missing"
    )
