from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()


@pytest.fixture
def sample_contract(tmp_path: Path) -> Path:
    path = tmp_path / "contract.pdf"
    path.write_bytes(b"%PDF-1.4\n")
    return path


def test_review_non_interactive_full(sample_contract: Path) -> None:
    result = runner.invoke(
        app,
        [
            "review",
            str(sample_contract),
            "--non-interactive",
            "--mode",
            "full",
            "--jurisdiction",
            "us-de",
            "--output",
            "json",
        ],
    )
    assert result.exit_code == 0
    assert "review ready" in result.stdout.lower()


def test_review_non_interactive_risk_scan(sample_contract: Path) -> None:
    result = runner.invoke(
        app,
        [
            "review",
            str(sample_contract),
            "--non-interactive",
            "--mode",
            "risk-scan",
        ],
    )
    assert result.exit_code == 0


def test_review_non_interactive_missing_mode(sample_contract: Path) -> None:
    result = runner.invoke(
        app,
        [
            "review",
            str(sample_contract),
            "--non-interactive",
        ],
    )
    assert result.exit_code != 0


def test_review_missing_file(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "review",
            str(tmp_path / "nonexistent.pdf"),
            "--non-interactive",
            "--mode",
            "full",
            "--jurisdiction",
            "us-de",
            "--output",
            "json",
        ],
    )
    assert result.exit_code != 0


def test_review_invalid_mode(sample_contract: Path) -> None:
    result = runner.invoke(
        app,
        [
            "review",
            str(sample_contract),
            "--non-interactive",
            "--mode",
            "invalid",
            "--jurisdiction",
            "us-de",
            "--output",
            "json",
        ],
    )
    assert result.exit_code != 0


def test_review_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "contract.txt"
    path.write_text("dummy")
    result = runner.invoke(
        app,
        [
            "review",
            str(path),
            "--non-interactive",
            "--mode",
            "full",
            "--jurisdiction",
            "us-de",
            "--output",
            "json",
        ],
    )
    assert result.exit_code != 0


def test_review_non_interactive_terminal_guard(tmp_path: Path) -> None:
    """Running review without --non-interactive in non-PTY env should warn."""
    path = tmp_path / "contract.pdf"
    path.write_bytes(b"%PDF-1.4\n")
    result = runner.invoke(
        app,
        [
            "review",
            str(path),
        ],
    )
    # CliRunner has no PTY, so _is_interactive() returns False
    assert result.exit_code != 0
    assert "non-interactive" in result.stdout.lower()
