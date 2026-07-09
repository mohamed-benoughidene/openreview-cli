"""Consolidated unit tests for L-4c product modes (FR-09 - FR-13).

Replaces 5 copy-paste playbook test files with a single parametrized file.
Unique assertions only: playbook schema, vocabulary structure, and VALID_MODES
are covered parametrically in test_playbook_schema.py.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.review.playbook import BUNDLED_PLAYBOOKS
from openreview_cli.review.prompts import MODE_VOCABULARY

L4C_MODES = ["distrocheck", "franchisecheck", "opcheck", "partnercheck", "sponsorcheck"]

# (mode, playbook_yaml_id, domain_keyword, help_keyword)
MODE_META: dict[str, tuple[str, str, str]] = {
    "distrocheck": ("distribution-v1", "Distribution", "distribution"),
    "franchisecheck": ("franchise-v1", "Franchise", "franchise"),
    "opcheck": ("operating-agreement-v1", "Operating Agreement", "Operating Agreement"),
    "partnercheck": ("partnership-v1", "Partnership", "partnership"),
    "sponsorcheck": ("sponsorship-v1", "Sponsorship", "sponsorship"),
}

runner = CliRunner()


class TestL4CPlaybooks:
    """BUNDLED_PLAYBOOKS has keys and paths for all L-4c modes."""

    @pytest.mark.parametrize("mode", L4C_MODES)
    def test_bundled_playbooks_key_exists(self, mode: str) -> None:
        assert mode in BUNDLED_PLAYBOOKS

    @pytest.mark.parametrize("mode", L4C_MODES)
    def test_bundled_playbooks_path_exists(self, mode: str) -> None:
        assert BUNDLED_PLAYBOOKS[mode].exists()


class TestL4CVocabulary:
    """MODE_VOCABULARY entries for L-4c modes — mode-specific domain check."""

    @pytest.mark.parametrize("mode", L4C_MODES)
    def test_vocabulary_entry_exists(self, mode: str) -> None:
        assert mode in MODE_VOCABULARY

    def test_opcheck_domain_is_operating_agreement(self) -> None:
        """FR-10: OpCheck MODE_VOCABULARY domain must be 'Operating Agreement'."""
        domain = MODE_VOCABULARY["opcheck"]["domain"]
        assert "Operating Agreement" in domain

    def test_distrocheck_vocabulary_has_franchise_boundary(self) -> None:
        """FR-09: DistroCheck vocabulary includes FRANCHISE_BOUNDARY flag."""
        assert "FRANCHISE_BOUNDARY" in MODE_VOCABULARY["distrocheck"]["vocabulary"]

    def test_franchisecheck_vocabulary_has_franchise_boundary(self) -> None:
        """FranchiseCheck vocabulary includes FRANCHISE_BOUNDARY flag."""
        assert "FRANCHISE_BOUNDARY" in MODE_VOCABULARY["franchisecheck"]["vocabulary"]


class TestL4CCLI:
    """CLI subcommand registration, --no-pii flag, and help text."""

    @pytest.mark.parametrize("mode", L4C_MODES)
    def test_subcommand_registered(self, mode: str) -> None:
        names = [c.name for c in app.registered_commands]
        assert mode in names

    @pytest.mark.parametrize("mode", L4C_MODES)
    def test_subcommand_has_no_pii_flag(self, mode: str) -> None:
        result = runner.invoke(app, [mode, "--help"])
        assert result.exit_code == 0
        assert "--no-pii" in result.stdout

    @pytest.mark.parametrize(("mode", "keyword"), [(m, MODE_META[m][2]) for m in L4C_MODES])
    def test_subcommand_help_text(self, mode: str, keyword: str) -> None:
        result = runner.invoke(app, [mode, "--help"])
        assert result.exit_code == 0
        assert keyword.lower() in result.stdout.lower()

    def test_opcheck_help_contains_operating_agreement(self) -> None:
        """FR-10: OpCheck --help must spell out 'Operating Agreement'."""
        result = runner.invoke(app, ["opcheck", "--help"])
        assert result.exit_code == 0
        assert "Operating Agreement" in result.stdout

    def test_opcheck_help_does_not_contain_op_agreement(self) -> None:
        """FR-10: OpCheck --help must not contain 'Op Agreement' standalone."""
        result = runner.invoke(app, ["opcheck", "--help"])
        assert result.exit_code == 0
        assert "Op Agreement" not in result.stdout

    def test_opcheck_help_includes_description(self) -> None:
        """OpCheck --help describes LLC governance context."""
        result = runner.invoke(app, ["opcheck", "--help"])
        assert result.exit_code == 0
        lower = result.stdout.lower()
        assert "llc" in lower or "limited liability company" in lower
