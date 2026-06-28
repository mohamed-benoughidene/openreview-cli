"""Tests for the feedback module (format_error, format_success)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from openreview_cli.ui.feedback import format_error, format_success

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.logging import LogCaptureFixture


# ---------------------------------------------------------------------------
# format_error
# ---------------------------------------------------------------------------


class TestFormatError:
    """Tests for format_error()."""

    def test_three_part_format(self, capsys: CaptureFixture[str]) -> None:
        """format_error shows What / Why / How to fix sections."""
        result = format_error("Failed to load config", "File not found", "Check the path")
        captured = capsys.readouterr()
        assert "Failed to load config" in captured.out
        assert "File not found" in captured.out
        assert "Check the path" in captured.out
        assert "What failed" in captured.out
        assert "Why" in captured.out
        assert "How to fix" in captured.out
        assert result["what"] == "Failed to load config"
        assert result["why"] == "File not found"
        assert "Check the path" in result["fix"]
        assert "help" in result["fix"].lower()
        assert result["exit_code"] == 1

    def test_exit_code_default(self) -> None:
        """format_error defaults to exit_code=1."""
        result = format_error("x", "y", "z")
        assert result["exit_code"] == 1

    def test_exit_code_custom(self) -> None:
        """format_error accepts custom exit_code."""
        result = format_error("x", "y", "z", exit_code=4)
        assert result["exit_code"] == 4

    def test_does_not_exit(self) -> None:
        """format_error does NOT raise SystemExit (caller decides)."""
        result = format_error("x", "y", "z", exit_code=3)
        assert result["exit_code"] == 3


# ---------------------------------------------------------------------------
# format_success
# ---------------------------------------------------------------------------


class TestFormatSuccess:
    """Tests for format_success()."""

    def test_basic(self, capsys: CaptureFixture[str]) -> None:
        """format_success prints a success panel."""
        result = format_success("All checks passed")
        captured = capsys.readouterr()
        assert "All checks passed" in captured.out
        assert result == {"message": "All checks passed", "detail": ""}

    def test_with_detail(self, capsys: CaptureFixture[str]) -> None:
        """format_success with detail appends it."""
        result = format_success("Done", "42 contracts indexed")
        captured = capsys.readouterr()
        assert "Done" in captured.out
        assert "42 contracts indexed" in captured.out
        assert result == {"message": "Done", "detail": "42 contracts indexed"}


# ---------------------------------------------------------------------------
# Verbose logging / PII redaction
# ---------------------------------------------------------------------------


class TestVerboseLogging:
    """Tests for --verbose output (PII-redacted logging)."""

    def test_verbose_logs_error_dict(self, caplog: LogCaptureFixture) -> None:
        """format_error logs the result dict at debug level."""
        caplog.set_level(logging.DEBUG, logger="openreview_cli.ui.feedback")
        format_error("x", "y", "z", exit_code=2)
        assert "format_error:" in caplog.text
        assert "'what': 'x'" in caplog.text

    def test_verbose_logs_success_dict(self, caplog: LogCaptureFixture) -> None:
        """format_success logs the result dict at debug level."""
        caplog.set_level(logging.DEBUG, logger="openreview_cli.ui.feedback")
        format_success("done", "detail")
        assert "format_success:" in caplog.text
        assert "'message': 'done'" in caplog.text

    def test_pii_redaction_file_paths(self, caplog: LogCaptureFixture) -> None:
        """File paths in error messages are redacted in logs."""
        caplog.set_level(logging.DEBUG, logger="openreview_cli.ui.feedback")
        format_error(
            "Failed to open /home/user/.config/openreview/auth.json",
            "Permission denied",
            "Check the file at /home/user/.config/openreview/auth.json",
            exit_code=3,
        )
        # Log should not contain the raw path
        assert "/home/user/" not in caplog.text
        # Log should contain the redacted marker
        assert "[path]" in caplog.text

    def test_pii_redaction_api_keys(self, caplog: LogCaptureFixture) -> None:
        """API keys in error messages are redacted in logs."""
        caplog.set_level(logging.DEBUG, logger="openreview_cli.ui.feedback")
        format_error(
            "Invalid API key: sk-abc123",
            "Authentication failed",
            "Update your API key in config",
            exit_code=5,
        )
        # Log should not contain the raw API key
        assert "sk-abc123" not in caplog.text
