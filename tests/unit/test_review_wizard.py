from pathlib import Path

import pytest

from openreview_cli.cli.review import (
    OutputFormat,
    ReviewConfiguration,
    ReviewMode,
    ReviewWizard,
)


@pytest.fixture
def sample_contract(tmp_path: Path) -> Path:
    path = tmp_path / "contract.pdf"
    path.write_bytes(b"%PDF-1.4\n")
    return path


def test_review_configuration_valid() -> None:
    config = ReviewConfiguration(
        file_path=Path("/tmp"),
        mode=ReviewMode.FULL,
        jurisdiction="us-de",
        output_format=OutputFormat.JSON,
    )
    assert config.mode == ReviewMode.FULL
    assert config.jurisdiction == "us-de"


def test_review_configuration_missing_jurisdiction() -> None:
    with pytest.raises(ValueError, match="jurisdiction is required"):
        ReviewConfiguration(
            file_path=Path("/tmp"),
            mode=ReviewMode.FULL,
            output_format=OutputFormat.JSON,
        )


def test_review_configuration_risk_scan_no_jurisdiction_needed() -> None:
    config = ReviewConfiguration(
        file_path=Path("/tmp"),
        mode=ReviewMode.RISK_SCAN,
    )
    assert config.jurisdiction is None
    assert config.output_format is None


def test_review_wizard_non_interactive_full(sample_contract: Path) -> None:
    wizard = ReviewWizard(
        file_path=str(sample_contract),
        non_interactive=True,
        mode="full",
        jurisdiction="us-de",
        output_format="json",
    )
    config = wizard.run()
    assert config.mode == ReviewMode.FULL
    assert config.jurisdiction == "us-de"
    assert config.output_format == OutputFormat.JSON
    assert config.clauses is None


def test_review_wizard_non_interactive_risk_scan(sample_contract: Path) -> None:
    wizard = ReviewWizard(
        file_path=str(sample_contract),
        non_interactive=True,
        mode="risk-scan",
    )
    config = wizard.run()
    assert config.mode == ReviewMode.RISK_SCAN
    assert config.jurisdiction is None
    assert config.output_format is None


def test_review_wizard_non_interactive_missing_mode(sample_contract: Path) -> None:
    wizard = ReviewWizard(
        file_path=str(sample_contract),
        non_interactive=True,
    )
    with pytest.raises(SystemExit):
        wizard.run()


def test_review_wizard_non_interactive_missing_jurisdiction(sample_contract: Path) -> None:
    wizard = ReviewWizard(
        file_path=str(sample_contract),
        non_interactive=True,
        mode="full",
    )
    with pytest.raises(SystemExit):
        wizard.run()


def test_review_wizard_non_interactive_clauses(sample_contract: Path) -> None:
    wizard = ReviewWizard(
        file_path=str(sample_contract),
        non_interactive=True,
        mode="clause-by-clause",
        jurisdiction="us-de",
        output_format="json",
        clauses=["1", "5", "12"],
    )
    config = wizard.run()
    assert config.mode == ReviewMode.CLAUSE_BY_CLAUSE
    assert config.clauses == ["1", "5", "12"]


def test_review_wizard_file_not_found(tmp_path: Path) -> None:
    wizard = ReviewWizard(
        file_path=str(tmp_path / "nonexistent.pdf"),
        non_interactive=True,
        mode="full",
        jurisdiction="us-de",
        output_format="json",
    )
    with pytest.raises(SystemExit):
        wizard.run()


def test_review_wizard_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "contract.txt"
    path.write_text("dummy")
    wizard = ReviewWizard(
        file_path=str(path),
        non_interactive=True,
        mode="full",
        jurisdiction="us-de",
        output_format="json",
    )
    with pytest.raises(SystemExit):
        wizard.run()
