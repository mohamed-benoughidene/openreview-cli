"""Tests for --verbose mode: additional detail printed to stderr with PII redaction.

T072 — Verbose mode logs processing steps and config values to stderr,
with PII redaction active (file paths → [path], API keys → [key]).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from openreview_cli.ui.feedback import _redact_pii, format_error

if TYPE_CHECKING:
    import pytest

# ---------------------------------------------------------------------------
# PII redaction
# ---------------------------------------------------------------------------


class TestPiiRedaction:
    """Tests for the _redact_pii helper function."""

    def test_file_path_redacted(self) -> None:
        """Absolute Unix file paths are replaced with [path]."""
        text = "Failed to open /home/user/.config/openreview/auth.json"
        result = _redact_pii(text)
        assert "/home/user/" not in result
        assert "[path]" in result

    def test_api_key_redacted(self) -> None:
        """API key patterns are replaced with [key]."""
        text = "Invalid API key: sk-abc123def456"
        result = _redact_pii(text)
        assert "sk-abc123def456" not in result
        assert "[key]" in result

    def test_token_redacted(self) -> None:
        """Token patterns are replaced with [key]."""
        text = "token = ghp_abcdef123456"
        result = _redact_pii(text)
        assert "ghp_abcdef123456" not in result
        assert "[key]" in result

    def test_multiple_paths_redacted(self) -> None:
        """Multiple file paths in one string are all redacted."""
        text = "Source: /etc/config.yml, Dest: /var/log/output.log"
        result = _redact_pii(text)
        assert result.count("[path]") >= 2

    def test_clean_text_unchanged(self) -> None:
        """Text without sensitive patterns is not modified."""
        text = "Processing complete: 42 contracts indexed"
        result = _redact_pii(text)
        assert result == text

    def test_redact_api_key_variants(self) -> None:
        """Various API key formats are all redacted."""
        cases = [
            "api_key=sk-abc123",
            "api-key=ghp_xyz",
            "API_KEY=secret123",
            "api key : some-value",
        ]
        for text in cases:
            result = _redact_pii(text)
            assert "[key]" in result, f"Failed to redact: {text!r}"


# ---------------------------------------------------------------------------
# Verbose logging via format_error / format_success
# ---------------------------------------------------------------------------


class TestVerboseLoggingDetail:
    """Verbose mode detail output via debug-level logging."""

    def test_verbose_logs_what_to_stderr(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """format_error logs 'what' to stderr via debug logger."""
        caplog.set_level(logging.DEBUG, logger="openreview_cli.ui.feedback")
        result = format_error("Config load error", "Syntax error", "Check YAML")
        assert "[path]" not in result["what"]
        assert "format_error:" in caplog.text
        assert "Config load error" in caplog.text

    def test_verbose_redacts_paths_in_log(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """File paths in error messages are redacted in verbose log."""
        caplog.set_level(logging.DEBUG, logger="openreview_cli.ui.feedback")
        format_error(
            "Failed to open /home/user/config.yml",
            "File not found",
            "Check /home/user/config.yml",
        )
        assert "/home/user/" not in caplog.text
        assert "[path]" in caplog.text

    def test_verbose_redacts_api_keys_in_log(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """API keys in error messages are redacted in verbose log."""
        caplog.set_level(logging.DEBUG, logger="openreview_cli.ui.feedback")
        format_error(
            "Invalid api_key=sk-test123",
            "Auth failure",
            "Update key in config",
        )
        assert "sk-test123" not in caplog.text
        assert "[key]" in caplog.text
