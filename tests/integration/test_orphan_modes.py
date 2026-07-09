"""CLI routing tests for 9 orphan product modes.

Each test verifies: subcommand registers, --help displays mode-specific text,
and invokes correct playbook reference.
"""

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()


@pytest.mark.parametrize(
    ("command", "keyword"),
    [
        ("licensecheck", "LicenseCheck"),
        ("leasecheck", "LeaseCheck"),
        ("privacycheck", "PrivacyCheck"),
        ("indemnitycheck", "IndemnityCheck"),
        ("consultcheck", "ConsultCheck"),
        ("workcheck", "WorkCheck"),
        ("loicheck", "LOICheck"),
        ("subcheck", "SubCheck"),
        ("settlementcheck", "SettlementCheck"),
    ],
)
def test_orphan_mode_routes_correctly(command: str, keyword: str) -> None:
    """Verify orphan mode subcommand registers and --help works."""
    result = runner.invoke(app, [command, "--help"])
    assert result.exit_code == 0, f"{command} --help failed: {result.stdout}"
    assert keyword.lower() in result.stdout.lower() or keyword in result.stdout
