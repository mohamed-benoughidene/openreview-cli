"""Integration tests for buycheck CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


class TestBuyCheckCli:
    """BuyCheck CLI integration tests (mock-free)."""

    @pytest.mark.integration
    def test_buycheck_help(self) -> None:
        result = runner.invoke(app, ["buycheck", "--help"])
        assert result.exit_code == 0
        assert "BuyCheck" in result.stdout or "purchase" in result.stdout.lower()

    @pytest.mark.integration
    def test_buycheck_no_args_shows_error(self) -> None:
        result = runner.invoke(app, ["buycheck"])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_buycheck_file_not_found(self) -> None:
        result = runner.invoke(app, ["buycheck", str(FIXTURES / "nonexistent.pdf")])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_help_shows_output_format(self) -> None:
        result = runner.invoke(app, ["buycheck", "--help"])
        assert "text" in result.stdout or "json" in result.stdout

    @pytest.mark.integration
    def test_buycheck_run_review_non_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def mock_extraction(_slot: str, _messages: list[dict[str, str]]) -> str:
            return json.dumps(
                {
                    "position": "preferred",
                    "confidence": 0.85,
                    "citation": "Clear asset purchase terms",
                    "category_match": True,
                }
            )

        def mock_qa(_slot: str, _messages: list[dict[str, str]]) -> str:
            return json.dumps(
                {
                    "verdict": "agree",
                    "revised_position": None,
                    "rationale": "",
                    "citation_valid": True,
                    "position_valid": True,
                    "category_valid": True,
                    "confidence_valid": True,
                }
            )

        monkeypatch.setattr(
            "openreview_cli.review.extraction.call_gateway_chat",
            mock_extraction,
        )
        monkeypatch.setattr(
            "openreview_cli.review.qa.call_gateway_chat",
            mock_qa,
        )

        fixture = FIXTURES / "asset-purchase.pdf"
        result = runner.invoke(app, ["buycheck", str(fixture)])
        assert result.exit_code == 0
        assert "asset-purchase-v1" in result.stdout

    @pytest.mark.integration
    def test_buycheck_playbook_override(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def mock_extraction(_slot: str, _messages: list[dict[str, str]]) -> str:
            return json.dumps(
                {
                    "position": "acceptable",
                    "confidence": 0.65,
                    "citation": "Custom playbook assessment",
                    "category_match": True,
                }
            )

        def mock_qa(_slot: str, _messages: list[dict[str, str]]) -> str:
            return json.dumps(
                {
                    "verdict": "agree",
                    "revised_position": None,
                    "rationale": "",
                    "citation_valid": True,
                    "position_valid": True,
                    "category_valid": True,
                    "confidence_valid": True,
                }
            )

        monkeypatch.setattr(
            "openreview_cli.review.extraction.call_gateway_chat",
            mock_extraction,
        )
        monkeypatch.setattr(
            "openreview_cli.review.qa.call_gateway_chat",
            mock_qa,
        )

        custom_playbook = tmp_path / "custom-buycheck.yaml"
        custom_playbook.write_text("""id: "custom-buycheck-test"
mode: "buycheck"
metadata:
  version: "1.0.0"
  description: "Custom test playbook for BuyCheck override"
  author: "test"
categories:
  - id: "custom-category"
    name: "Custom Category"
    description: "Custom test category for playbook override test"
    preferred:
      description: "Clear specific terms"
      exemplars: ["specific term 1", "specific term 2"]
    acceptable:
      description: "Standard terms"
      exemplars: ["standard term"]
    walkaway:
      description: "Unfavorable terms"
      exemplars: ["bad term"]
    default_position: "acceptable"
""")

        fixture = FIXTURES / "asset-purchase.pdf"
        result = runner.invoke(
            app,
            ["buycheck", str(fixture), "--playbook", str(custom_playbook)],
        )
        assert result.exit_code == 0
        assert "custom-buycheck-test" in result.stdout
