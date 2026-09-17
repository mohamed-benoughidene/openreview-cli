"""Exploratory probes: CLI flag validation on ``feat/design-ux-remediation``.

Targets commit ``450b951 fix(cli): standardize exit codes and validate inputs``
plus the ``--format`` / ``--weights`` / ``--pii-threshold`` guards.

The probes deliberately push past the documented "happy path" to characterise
boundary behaviour (case sensitivity, empty strings, ``nan``/``inf``, option
placement) and to record anything surprising.  Findings are annotated in the
docstrings.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import Result

EXIT_USAGE = 2


def _text(result: Result) -> str:
    raw = (getattr(result, "output", "") or "") + (getattr(result, "stderr", "") or "")
    return " ".join(raw.split())


# ── parse / chunk: --format validation ────────────────────────────────────


@pytest.mark.fast
@pytest.mark.parametrize("cmd", ["parse", "chunk"])
@pytest.mark.parametrize(
    "fmt",
    ["xml", "yaml", "TEXT", "JSON", "", " json", "table", "memo", "Text"],
)
def test_parse_chunk_reject_unknown_format_case_sensitively(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], cmd: str, fmt: str
) -> None:
    """Unknown, empty, whitespace-padded and wrong-case formats all exit 2.

    FINDING: validation is exact-match and case-sensitive — ``JSON``/``Text``
    are rejected even though users reasonably expect case-insensitive enums.
    """
    result = invoke([cmd, "nonexistent.pdf", "--format", fmt])
    assert result.exit_code == EXIT_USAGE, (cmd, fmt, result.exit_code, _text(result))
    assert "format" in _text(result).lower(), _text(result)


@pytest.mark.fast
@pytest.mark.parametrize("cmd", ["parse", "chunk"])
@pytest.mark.parametrize("fmt", ["text", "json"])
def test_parse_chunk_accept_documented_formats(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], cmd: str, fmt: str
) -> None:
    """Documented formats clear validation and fail later for a missing file."""
    result = invoke([cmd, "nonexistent.pdf", "--format", fmt])
    assert result.exit_code != EXIT_USAGE, (cmd, fmt, result.exit_code, _text(result))
    assert "format" not in _text(result).lower()


@pytest.mark.fast
def test_parse_missing_file_is_parse_error_exit_8(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    """``parse`` maps a missing file to ParseError -> exit 8."""
    result = invoke(["parse", "nonexistent.pdf", "--format", "text"])
    assert result.exit_code == 8, (result.exit_code, _text(result))


@pytest.mark.fast
def test_chunk_missing_file_is_exit_1_not_8(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    """FINDING: ``chunk`` funnels the same missing file through a generic
    handler and exits 1, inconsistent with ``parse``'s exit 8."""
    result = invoke(["chunk", "nonexistent.pdf", "--format", "text"])
    assert result.exit_code == 1, (result.exit_code, _text(result))


@pytest.mark.fast
def test_parse_summary_still_validates_format(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    """``--summary`` must not bypass ``--format`` validation."""
    result = invoke(["parse", "nonexistent.pdf", "--summary", "--format", "xml"])
    assert result.exit_code == EXIT_USAGE, (result.exit_code, _text(result))


# A real fixture proves the *valid* format branches actually render output.
_DOCX = Path(__file__).resolve().parents[1] / "fixtures" / "docx" / "simple_contract.docx"


@pytest.mark.fast
@pytest.mark.skipif(not _DOCX.exists(), reason="simple_contract.docx fixture missing")
@pytest.mark.parametrize("fmt", ["text", "json"])
def test_parse_valid_format_with_real_document(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], fmt: str
) -> None:
    result = invoke(["parse", str(_DOCX), "--format", fmt])
    assert result.exit_code == 0, (fmt, result.exit_code, _text(result))
    assert (result.output or "").strip(), "valid parse must emit output"
    if fmt == "json":
        import json

        assert isinstance(json.loads(result.output), list)


@pytest.mark.fast
@pytest.mark.skipif(not _DOCX.exists(), reason="simple_contract.docx fixture missing")
def test_parse_summary_with_real_document(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    result = invoke(["parse", str(_DOCX), "--summary"])
    assert result.exit_code == 0, (result.exit_code, _text(result))
    assert "clauses across" in _text(result)


@pytest.mark.fast
@pytest.mark.skipif(not _DOCX.exists(), reason="simple_contract.docx fixture missing")
@pytest.mark.parametrize("fmt", ["text", "json"])
def test_chunk_valid_format_with_real_document(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], fmt: str
) -> None:
    result = invoke(["chunk", str(_DOCX), "--format", fmt])
    assert result.exit_code == 0, (fmt, result.exit_code, _text(result))
    assert (result.output or "").strip()
    if fmt == "json":
        import json

        assert isinstance(json.loads(result.output), list)


# ── pii list: --format validation ─────────────────────────────────────────


@pytest.mark.fast
@pytest.mark.parametrize("fmt", ["xml", "csv", "JSON", "csv", "", "table "])
def test_pii_list_rejects_unknown_format(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], fmt: str
) -> None:
    result = invoke(["pii", "list", "--format", fmt])
    assert result.exit_code == EXIT_USAGE, (fmt, result.exit_code, _text(result))
    assert "format" in _text(result).lower()


@pytest.mark.fast
@pytest.mark.parametrize("args", [["pii", "list"], ["pii", "list", "--format", "table"]])
def test_pii_list_table_and_default_succeed(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], args: list[str]
) -> None:
    result = invoke(args)
    assert result.exit_code == 0, (args, result.exit_code, _text(result))
    assert "Documents with PII data" in _text(result)


@pytest.mark.fast
def test_pii_list_json_on_empty_db_is_valid_empty_array(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    """``pii list --format json`` on a fresh data dir returns parseable ``[]``.

    ``_init`` runs first and creates the schema, so the query never hits a
    missing ``pii_cache`` table.
    """
    import json

    result = invoke(["pii", "list", "--format", "json"])
    assert result.exit_code == 0, (result.exit_code, _text(result))
    payload = json.loads((result.output or "").strip())
    assert payload == []


# ── precheck: --pii-threshold ─────────────────────────────────────────────


@pytest.mark.fast
@pytest.mark.parametrize(
    "value", ["1.5", "-0.1", "2", "-1", "100", "nan", "inf", "-inf", "abc", ""]
)
def test_pii_threshold_out_of_range_rejected(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], value: str
) -> None:
    """Out-of-range and non-numeric thresholds exit 2 at parse time.

    ``nan``/``inf`` are correctly rejected because ``0.0 <= nan <= 1.0`` is
    ``False``.
    """
    result = invoke(["precheck", "--document", "x.pdf", "--pii-threshold", value])
    assert result.exit_code == EXIT_USAGE, (value, result.exit_code, _text(result))
    assert "pii-threshold" in _text(result).lower()


@pytest.mark.fast
@pytest.mark.parametrize("value", ["0.0", "0.5", "1.0", "0.999"])
def test_pii_threshold_in_range_clears_validation(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], value: str
) -> None:
    result = invoke(["precheck", "--document", "x.pdf", "--pii-threshold", value])
    assert result.exit_code == 1, (value, result.exit_code, _text(result))


@pytest.mark.fast
def test_precheck_review_has_no_pii_threshold_option(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    """FINDING: ``precheck review`` does not define ``--pii-threshold``.

    ``--pii-threshold`` lives on the ``precheck`` group callback; the literal
    command ``openreview precheck review --pii-threshold ...`` therefore fails
    as an unknown option (still exit 2, but for a *different* reason than range
    validation).  The group-level form ``precheck --pii-threshold N review`` is
    the one that performs range validation.
    """
    result = invoke(["precheck", "review", "nonexistent.pdf", "--pii-threshold", "1.5"])
    assert result.exit_code == EXIT_USAGE, (result.exit_code, _text(result))
    assert "no such option" in _text(result).lower(), _text(result)


@pytest.mark.fast
def test_precheck_group_pii_threshold_is_range_checked_before_subcommand(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    """The group-level option is range-validated (BadParameter -> exit 2)."""
    result = invoke(["precheck", "--pii-threshold", "1.5", "review", "nonexistent.pdf"])
    assert result.exit_code == EXIT_USAGE, (result.exit_code, _text(result))
    assert "0.0 and 1.0" in _text(result)


@pytest.mark.fast
@pytest.mark.parametrize("value", ["1.5", "-0.1", "2"])
def test_precheck_review_confidence_threshold_validated(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], value: str
) -> None:
    result = invoke(["precheck", "review", "nonexistent.pdf", "--confidence-threshold", value])
    assert result.exit_code == EXIT_USAGE, (value, result.exit_code, _text(result))


@pytest.mark.fast
def test_precheck_review_in_range_threshold_reaches_missing_doc_guard(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    result = invoke(["precheck", "review", "nonexistent.pdf", "--confidence-threshold", "0.5"])
    assert result.exit_code == 1, (result.exit_code, _text(result))


# ── negotiate: --weights ──────────────────────────────────────────────────


@pytest.mark.fast
@pytest.mark.parametrize(
    "weights",
    ["0.5,0.5", "1.2,-0.1,0.5", "a,b,c", "0.7,,0.15", "0.7,0.15,0.15,0.0", "1,2", "1,2,3,4,5"],
)
def test_negotiate_malformed_weights_rejected(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], weights: str
) -> None:
    result = invoke(["negotiate", "nonexistent.pdf", "--weights", weights])
    assert result.exit_code == EXIT_USAGE, (weights, result.exit_code, _text(result))
    assert "--weights" in _text(result).lower()


@pytest.mark.fast
def test_negotiate_weights_validated_before_document_io(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], tmp_path: Path
) -> None:
    """A malformed triple must fail even when the document does not exist."""
    result = invoke(["negotiate", str(tmp_path / "missing.pdf"), "--weights", "0.5,0.5"])
    assert result.exit_code == EXIT_USAGE, (result.exit_code, _text(result))
    assert "file not found" not in _text(result).lower()


@pytest.mark.fast
def test_negotiate_valid_weights_reach_document_io(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], tmp_path: Path
) -> None:
    result = invoke(["negotiate", str(tmp_path / "missing.pdf"), "--weights", "0.7,0.15,0.15"])
    assert result.exit_code == 1, (result.exit_code, _text(result))
    assert "file not found" in _text(result).lower()


@pytest.mark.fast
def test_negotiate_empty_weights_string_is_silently_ignored(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], tmp_path: Path
) -> None:
    """FINDING (edge case): ``--weights ""`` is falsy, so validation is skipped
    entirely and the run proceeds as if the flag were absent.  A user who
    passes an empty value expecting an error instead gets a silent default."""
    missing = str(tmp_path / "missing.pdf")
    result = invoke(["negotiate", missing, "--weights", ""])
    assert result.exit_code == 1, (result.exit_code, _text(result))
    assert "file not found" in _text(result).lower(), _text(result)
    assert "--weights" not in _text(result).lower()


@pytest.mark.fast
@pytest.mark.parametrize("weights", ["nan,nan,nan", "inf,0,0", "-0.0,1,0", "1,1,1", "0,0,0"])
def test_negotiate_weights_accept_nan_inf_and_unnormalised(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], tmp_path: Path, weights: str
) -> None:
    """FINDING (edge case): validation only checks count, numeric-ness, and
    non-negativity.  ``nan``/``inf`` slip through (``nan < 0`` is ``False``)
    and there is no "must sum to ~1.0" check despite the option help text."""
    missing = str(tmp_path / "missing.pdf")
    result = invoke(["negotiate", missing, "--weights", weights])
    assert result.exit_code == 1, (weights, result.exit_code, _text(result))
    assert "file not found" in _text(result).lower(), (weights, _text(result))


@pytest.mark.fast
@pytest.mark.parametrize("fmt", ["xml", "yaml", "TABLE", ""])
def test_negotiate_rejects_unknown_format(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], fmt: str
) -> None:
    result = invoke(["negotiate", "nonexistent.pdf", "--format", fmt])
    assert result.exit_code == EXIT_USAGE, (fmt, result.exit_code, _text(result))


@pytest.mark.fast
@pytest.mark.parametrize("fmt", ["table", "json", "memo"])
def test_negotiate_accepts_documented_formats(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], fmt: str
) -> None:
    result = invoke(["negotiate", "nonexistent.pdf", "--format", fmt])
    assert result.exit_code == 1, (fmt, result.exit_code, _text(result))


@pytest.mark.fast
@pytest.mark.parametrize("solver", ["bogus", "NASH", ""])
def test_negotiate_rejects_unknown_solver(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], solver: str
) -> None:
    result = invoke(["negotiate", "nonexistent.pdf", "--solver", solver])
    assert result.exit_code == EXIT_USAGE, (solver, result.exit_code, _text(result))


@pytest.mark.fast
def test_negotiate_bad_solver_message_lists_choices(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    result = invoke(["negotiate", "nonexistent.pdf", "--solver", "bogus"])
    text = _text(result)
    for choice in ("nash", "qre", "level_k"):
        assert choice in text
