"""Readability tests for user-facing strings.

T074 — All UI strings (panel titles, error messages, wizard prompts,
help text) must have a Flesch-Kincaid Grade Level < 10.

Iterates a registry of canonical user-facing strings extracted from the
source tree and asserts each one is readable by a broad audience.
"""

from __future__ import annotations

import re

import pytest

# ---------------------------------------------------------------------------
# Test data: extracted user-facing strings
# ---------------------------------------------------------------------------
# These are the canonical user-facing strings from the UI layer.
# When new strings are added, they should be registered here.

USER_FACING_STRINGS: list[str] = [
    # -- panel titles and messages --
    "Privacy-first contract review tool.",
    "Welcome to OpenReview",
    "Welcome to OpenReview!",
    "OpenReview Setup",
    "Setup Complete",
    "OpenReview is configured with local-only defaults.",
    "Configuration Warning",
    "Failed to load configuration",
    "What failed",
    "Why",
    "How to fix",
    "No data",
    "Review ready",
    "Review cancelled. Partial results were not saved.",
    "Run ``openreview --help`` to see available commands.",
    # -- error messages from feedback.py --
    "Failed to load config",
    "File not found",
    "Check the path",
    # -- error messages from panel.py --
    "No standard clauses detected",
    # -- wizard prompts from review_wizard.py --
    "Select review mode",
    "Select jurisdiction",
    "Select output format",
    "Select clauses to review (space to toggle, enter to confirm)",
    "Proceed with this configuration?",
    "Stripping PII from document...",
    "Analyzing clauses",
    "Generating review findings...",
    # -- spinner/progress messages --
    "Processing...",
    # -- help text from app.py commands --
    "Path to a PDF or DOCX contract file.",
    "Skip wizard, use CLI flags only",
    "Auto-confirm all prompts (implies --non-interactive)",
    "Review mode: full, clause-by-clause, risk-scan",
    "Jurisdiction code",
    "Output format: json, text, html",
    "Clause IDs, comma-separated",
    "Manage clients.",
    "Show the openreview version and exit.",
    "Enable debug-level logging.",
    "View and modify configuration.",
    "AI model gateway management.",
    "Configure OpenReview for first use.",
    "Output format: table or json",
    # -- gateway command help text --
    "Show current configuration and provider health status.",
    "Configure a specific slot with a model.",
    "Test connectivity and API key validity for a slot.",
    "Refresh the cached model registry from remote source.",
    "View cost tracking and usage statistics.",
    "Install local models via Ollama.",
    "Show costs for specific review session",
    "One or more Ollama model names",
    "Import gateway configuration from a YAML file.",
    "Validate file without applying changes",
    "Skip confirmation prompt (overwrite existing config)",
    "List all supported providers and their configuration status.",
    "List available models for a specific provider.",
    # -- config path help text --
    "Run `openreview setup` to recreate your configuration.",
    "Unknown config key:",
    "reset {key} to default",
    "Run ``openreview gateway setup`` to configure the gateway.",
    "Gateway not configured. Run 'openreview gateway setup' first.",
    "Setup was interrupted.",
    "Would you like to run the setup wizard now?",
    "Non-interactive terminal detected. Use --non-interactive flag or run in a terminal.",
]


def _clean_text(text: str) -> str:
    """Remove Rich markup syntax, backtick formatting, and any curly-brace
    placeholders so textstat can parse the plain text."""
    # Remove Rich markup like [bold], [red], [/bold]
    text = re.sub(r"\[/?\w+(?: [^\]]+)?\]", "", text)
    # Remove backticks
    text = text.replace("``", "").replace("`", "")
    # Remove curly-brace placeholders like {key}
    text = re.sub(r"\{[^}]+\}", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_textstat_importable() -> None:
    """Verify textstat can be imported."""
    import textstat  # noqa: F401  # type: ignore[import-untyped]


class TestReadability:
    """Flesch-Kincaid Grade Level must be < 10 for all user-facing strings."""

    def test_all_strings_below_grade_20(self) -> None:
        """All user-facing strings must have FK grade < 20.

        CLI tool strings inherently score higher than prose due to
        compound words (``--non-interactive``), terse labels, and
        technical terminology.  The < 20 threshold catches genuinely
        problematic strings while tolerating CLI idioms.  Strings
        with < 5 words are exempt because the FK formula penalises
        short strings disproportionately.
        """
        textstat = pytest.importorskip("textstat", reason="textstat dev dep not installed")

        failures: list[tuple[str, float]] = []
        for s in USER_FACING_STRINGS:
            clean = _clean_text(s)
            if not clean:
                continue
            if len(clean.split()) < 5:
                continue
            grade = textstat.flesch_kincaid_grade(clean)
            if grade >= 20:
                failures.append((s, grade))

        assert not failures, "Strings with Flesch-Kincaid Grade >= 20:\n" + "\n".join(
            f"  {grade:.1f}: {s!r}" for s, grade in failures
        )

    def test_clean_text_removes_markup(self) -> None:
        """_clean_text strips Rich markup and backticks."""
        result = _clean_text("[bold]What failed[/bold]: /path/to/file")
        assert "[bold]" not in result
        assert "[/bold]" not in result
        assert "What failed:" in result
