"""Integration tests for per-operation tier change detection (D-36 / D-50).

Uses ``typer.testing.CliRunner`` to invoke the CLI and ``XDG_CONFIG_HOME``
to redirect the config directory into a temp path, so no real config is
touched and no monkeypath of import bindings is needed.
"""

from __future__ import annotations

import json
import logging
from io import StringIO
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.gateway.tier_tracker import TierTracker
from openreview_cli.parsing.models import Clause, Document

runner = CliRunner()


class TestTierChangeNotice:
    """End-to-end: tier change detection via CLI."""

    @pytest.mark.integration
    def test_tier_change_logged_on_precheck(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When privacy.tier differs from last_tier, log message emitted."""
        # Redirect config dir via XDG_CONFIG_HOME so platformdirs uses our path
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_config"))
        # get_config_dir() will return  {XDG_CONFIG_HOME}/openreview  =  tmp_path/xdg_config/openreview
        config_dir = tmp_path / "xdg_config" / "openreview"
        config_dir.mkdir(parents=True)
        (config_dir / "config.yml").write_text("privacy:\n  tier: performance\n")
        # Write previous tier so a change is detected
        (config_dir / ".last_tier").write_text(json.dumps({"tier": "maximum"}))

        # Create dummy file that passes exists() check
        doc_path = tmp_path / "test.pdf"
        doc_path.write_text("fake content")

        # Mock document parsing to avoid real PDF processing
        from openreview_cli.review.base import ReviewCommand

        clause = Clause(
            id="1",
            title="Test Clause",
            text="test clause text",
            level=1,
            parent_id=None,
            source_page=None,
            source_paragraph=None,
            source_span=None,
        )
        document = Document(
            source_path=doc_path,
            format="pdf",
            page_count=1,
            clause_count=1,
            parse_duration_seconds=0.0,
            warnings=[],
        )

        monkeypatch.setattr(
            ReviewCommand,
            "_parse_document",
            lambda self: ([clause], document),
        )

        # Also need to patch app.py's module-level refs for _init() to use the right paths
        monkeypatch.setattr(
            "openreview_cli.app.get_config_dir",
            lambda: config_dir,
        )
        monkeypatch.setattr(
            "openreview_cli.app.get_data_dir",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "openreview_cli.app.get_log_dir",
            lambda: tmp_path / "logs",
        )

        # Capture log output
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

        try:
            result = runner.invoke(app, ["precheck", "--document", str(doc_path), "--no-pii"])
            assert result.exit_code == 0, f"CLI exited {result.exit_code}: {result.output}"
            log_output = log_stream.getvalue()
            assert "Tier changed from maximum to performance" in log_output
        finally:
            root_logger.removeHandler(handler)

    @pytest.mark.integration
    def test_no_change_no_notice(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When tier unchanged, no log message emitted."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_config"))
        config_dir = tmp_path / "xdg_config" / "openreview"
        config_dir.mkdir(parents=True)
        (config_dir / "config.yml").write_text("privacy:\n  tier: balanced\n")
        (config_dir / ".last_tier").write_text(json.dumps({"tier": "balanced"}))

        doc_path = tmp_path / "test.pdf"
        doc_path.write_text("fake")

        from openreview_cli.review.base import ReviewCommand

        clause = Clause(
            id="1",
            title="Test",
            text="test",
            level=1,
            parent_id=None,
            source_page=None,
            source_paragraph=None,
            source_span=None,
        )
        document = Document(
            source_path=doc_path,
            format="pdf",
            page_count=1,
            clause_count=1,
            parse_duration_seconds=0.0,
            warnings=[],
        )

        monkeypatch.setattr(
            ReviewCommand,
            "_parse_document",
            lambda self: ([clause], document),
        )
        monkeypatch.setattr("openreview_cli.app.get_config_dir", lambda: config_dir)
        monkeypatch.setattr("openreview_cli.app.get_data_dir", lambda: tmp_path)
        monkeypatch.setattr("openreview_cli.app.get_log_dir", lambda: tmp_path / "logs")

        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

        try:
            result = runner.invoke(app, ["precheck", "--document", str(doc_path), "--no-pii"])
            assert result.exit_code == 0, f"CLI exited {result.exit_code}: {result.output}"
            log_output = log_stream.getvalue()
            assert "Tier changed" not in log_output
        finally:
            root_logger.removeHandler(handler)

    @pytest.mark.integration
    def test_tier_change_detected_build_report(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TierTracker + TierConfig integration through real config loading."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_config"))
        config_dir = tmp_path / "xdg_config" / "openreview"
        config_dir.mkdir(parents=True)
        (config_dir / "config.yml").write_text("privacy:\n  tier: performance\n")
        (config_dir / ".last_tier").write_text(json.dumps({"tier": "maximum"}))

        from openreview_cli.config.loader import load_config
        from openreview_cli.gateway.tier_config import TierConfig

        tracker = TierTracker()
        config = load_config(config_dir / "config.yml")
        tier_cfg = TierConfig.from_config(config)

        msg = tracker.check_and_record(tier_cfg.tier)
        assert msg == "Tier changed from maximum to performance"
