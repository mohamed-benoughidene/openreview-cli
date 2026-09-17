"""P2T5 — validate ``--pii-threshold`` and parse ``--weights`` eagerly.

``--pii-threshold`` must reject out-of-range values at parse time (exit 2,
``EXIT_USAGE``). ``--weights`` must be parsed and validated at the **top** of
``negotiate`` — before any document I/O — so a malformed value fails with a
clear message and ``EXIT_USAGE`` (2) instead of being silently ignored or
raising an uncaught ``ValueError``.

The downstream payoff model (``openreview_cli.negotiation.payoffs``) consumes
three components — ``risk,financial,obligation`` — so ``--weights`` takes
exactly three comma-separated, non-negative floats.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner, Result

import openreview_cli.negotiation as negotiation_mod
import openreview_cli.parsing.stream as stream_mod
from openreview_cli.app import app
from openreview_cli.errors import EXIT_USAGE

runner = CliRunner()


def _invoke(args: list[str]) -> Result:
    return runner.invoke(app, args)


def _combined(result: Result) -> str:
    """stdout + stderr (Click >= 8.2 keeps the two streams separate)."""
    return (result.output or "") + (result.stderr or "")


# ── --pii-threshold range validation ──────────────────────────────────────


@pytest.mark.parametrize("value", ["1.5", "-0.1", "2"])
def test_pii_threshold_out_of_range_rejected(value: str) -> None:
    result = _invoke(["precheck", "--document", "x.pdf", "--pii-threshold", value])
    assert result.exit_code == EXIT_USAGE, (result.exit_code, _combined(result))
    assert "pii-threshold" in _combined(result).lower()


@pytest.mark.parametrize("value", ["0.0", "0.5", "1.0"])
def test_pii_threshold_in_range_accepted(value: str) -> None:
    """An in-range threshold clears validation and fails later on the missing file."""
    result = _invoke(["precheck", "--document", "x.pdf", "--pii-threshold", value])
    assert result.exit_code == 1, (result.exit_code, _combined(result))


# ── --weights validation (before document I/O) ────────────────────────────


def _write_fake_pdf(tmp_path: Path) -> str:
    doc = tmp_path / "d.pdf"
    doc.write_bytes(b"%PDF-1.4")
    return str(doc)


def test_weights_wrong_count_rejected(tmp_path: Path) -> None:
    result = _invoke(["negotiate", _write_fake_pdf(tmp_path), "--weights", "0.5,0.5"])
    assert result.exit_code == EXIT_USAGE, (result.exit_code, _combined(result))
    assert "--weights" in _combined(result).lower()


def test_weights_non_numeric_rejected(tmp_path: Path) -> None:
    result = _invoke(["negotiate", _write_fake_pdf(tmp_path), "--weights", "a,b,c"])
    assert result.exit_code == EXIT_USAGE, (result.exit_code, _combined(result))
    assert "--weights" in _combined(result).lower()


def test_weights_negative_rejected(tmp_path: Path) -> None:
    result = _invoke(["negotiate", _write_fake_pdf(tmp_path), "--weights", "1.2,-0.1,0.5"])
    assert result.exit_code == EXIT_USAGE, (result.exit_code, _combined(result))
    assert "--weights" in _combined(result).lower()


def test_weights_validated_before_parsing(tmp_path: Path) -> None:
    """A malformed --weights must fail even when the document is missing."""
    missing = tmp_path / "does-not-exist.pdf"
    result = _invoke(["negotiate", str(missing), "--weights", "0.5,0.5"])
    assert result.exit_code == EXIT_USAGE, (result.exit_code, _combined(result))
    assert "--weights" in _combined(result).lower()
    assert "file not found" not in _combined(result).lower()


def test_weights_valid_values_clear_validation(tmp_path: Path) -> None:
    """A well-formed triple clears weight validation and reaches document I/O."""
    missing = tmp_path / "does-not-exist.pdf"
    result = _invoke(["negotiate", str(missing), "--weights", "0.7,0.15,0.15"])
    # Weights cleared -> the command proceeds to the missing-file guard (exit 1).
    combined = _combined(result).lower()
    assert result.exit_code == 1, (result.exit_code, combined)
    assert "file not found" in combined, combined
    assert "--weights" not in combined, combined


def test_weights_valid_values_map_into_run_negotiation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A valid triple is forwarded to run_negotiation as risk/financial/obligation."""
    doc = tmp_path / "d.pdf"
    doc.write_bytes(b"%PDF-1.4")

    def fake_parse_document(_path: str) -> tuple[SimpleNamespace, list[SimpleNamespace]]:
        clause = SimpleNamespace(text="Confidentiality clause", heading="confidentiality")
        return SimpleNamespace(filename="d.pdf"), [clause]

    captured: dict[str, object] = {}

    def fake_run_negotiation(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(summary=SimpleNamespace(amber_count=0))

    monkeypatch.setattr(stream_mod, "parse_document", fake_parse_document)
    monkeypatch.setattr(negotiation_mod, "run_negotiation", fake_run_negotiation)
    monkeypatch.setattr(negotiation_mod, "format_json", lambda _report: "{}")

    result = _invoke(["negotiate", str(doc), "--weights", "0.7,0.15,0.15", "--format", "json"])
    assert result.exit_code == 0, (result.exit_code, _combined(result))
    assert captured.get("weights") == {
        "risk": 0.7,
        "financial": 0.15,
        "obligation": 0.15,
    }
