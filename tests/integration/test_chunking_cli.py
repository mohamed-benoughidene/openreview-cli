from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
runner = CliRunner()


pytestmark = pytest.mark.integration


def test_chunk_cli_smoke() -> None:
    """T020a: Chunk command runs on a real PDF and produces output."""
    pdf = FIXTURES_DIR / "pdf" / "simple_contract.pdf"
    if not pdf.exists():
        pytest.skip("simple_contract.pdf fixture not found")
    result = runner.invoke(app, ["chunk", str(pdf)])
    assert result.exit_code == 0
    assert "Chunk" in result.output
