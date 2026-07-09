"""Unit tests for the `precheck compare` CLI subcommand.

Covers flag validation, mutually exclusive options, file checks,
help output, format selection, error propagation, and dispatch.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from openreview_cli.app import DEFAULT_CONFIDENCE_THRESHOLD, _validate_threshold, app
from openreview_cli.bilateral.models import (
    AlignmentPair,
    AlignmentTable,
    ComparisonReport,
    ComparisonSummary,
    DivergenceVerdict,
    MatchingMethod,
    PairedAssessment,
)
from openreview_cli.parsing.models import Clause
from openreview_cli.review.models import ClauseAssessment, DocMeta, Position, QAVerdict

# typer.Exit is raised by compare(); catch it explicitly.
# Inherits click.exceptions.Exit (BaseException), not SystemExit.
_Exit = typer.Exit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_clause(clause_id: str = "c1", text: str = "Test clause") -> Clause:
    return Clause(
        id=clause_id,
        title="Test",
        text=text,
        level=1,
        parent_id=None,
        source_page=1,
        source_paragraph=None,
        source_span=(0, len(text)),
    )


def _make_assessment(
    clause_id: str = "c1",
    position: Position = Position.ACCEPTABLE,
    confidence: float = 0.9,
) -> ClauseAssessment:
    return ClauseAssessment(
        clause_id=clause_id,
        clause_text="Text",
        playbook_category="test",
        position=position,
        confidence=confidence,
        citation="excerpt",
        qa_verdict=QAVerdict.agree,
        extraction_model="test",
        qa_model="test",
    )


def _make_mock_report() -> ComparisonReport:
    ca = _make_clause("a1")
    cb = _make_clause("b1")
    pair = AlignmentPair("A0-B0", ca, cb, MatchingMethod.exact, 1.0)
    table = AlignmentTable(matched_pairs=[pair], unmatched_a=[], unmatched_b=[])
    pa = PairedAssessment(
        pair_id="p1",
        alignment=pair,
        party_a_assessment=_make_assessment("a1"),
        party_b_assessment=_make_assessment("b1"),
        divergence=DivergenceVerdict.aligned,
    )
    summary = ComparisonSummary()
    now = datetime.now(UTC)
    return ComparisonReport(
        document_a=DocMeta(
            filename="a.pdf",
            page_count=1,
            clause_count=1,
            pii_stripped=True,
            parsed_at=now,
        ),
        document_b=DocMeta(
            filename="b.pdf",
            page_count=1,
            clause_count=1,
            pii_stripped=True,
            parsed_at=now,
        ),
        alignment_table=table,
        assessments=[pa],
        summary=summary,
        playbook_id="test",
        generated_at=now,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def pdf_pair(tmp_path: Path) -> tuple[str, str]:
    a = tmp_path / "doc_a.pdf"
    b = tmp_path / "doc_b.pdf"
    a.write_bytes(b"%PDF-1.4\n%%EOF\n")
    b.write_bytes(b"%PDF-1.4\n%%EOF\n")
    return str(a), str(b)


# ---------------------------------------------------------------------------
# CLI registration and help output
# ---------------------------------------------------------------------------


class TestCliRegistration:
    """Compare command appears in help output with all flags documented."""

    def test_compare_in_precheck_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["precheck", "--help"])
        assert result.exit_code == 0
        assert "compare" in result.output
        assert "Compare two documents" in result.output

    def test_compare_help_shows_all_flags(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["precheck", "compare", "--help"])
        assert result.exit_code == 0
        output = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", result.stdout)
        for flag in (
            "--align-only",
            "--format",
            "--confidence-threshold",
            "--conservative",
            "--verbose",
            "--no-pii",
            "--grounding-mode",
            "--playbook",
            "--output",
            "--no-grounding",
            "--extraction-model",
            "--qa-model",
        ):
            assert flag in output, f"{flag} missing from compare --help"

    def test_compare_help_accuracy_disclosure(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["precheck", "compare", "--help"])
        assert result.exit_code == 0
        assert "experimental" in result.output.lower()
        assert "64%" in result.output

    def test_compare_missing_args_error(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["precheck", "compare"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Confidence-threshold validation
# ---------------------------------------------------------------------------


class TestThresholdValidation:
    """Unit tests for the confidence-threshold Typer callback."""

    def test_default_constant(self) -> None:
        assert DEFAULT_CONFIDENCE_THRESHOLD == 0.7

    def test_valid_values_accepted(self) -> None:
        for v in (0.0, 0.3, 0.5, 0.7, 0.9, 1.0):
            assert _validate_threshold(v) == v

    def test_none_passed_through(self) -> None:
        assert _validate_threshold(None) is None

    def test_negative_rejected(self) -> None:
        with pytest.raises(typer.BadParameter):
            _validate_threshold(-0.1)

    def test_above_one_rejected(self) -> None:
        with pytest.raises(typer.BadParameter):
            _validate_threshold(1.5)


# ---------------------------------------------------------------------------
# File existence validation
# ---------------------------------------------------------------------------


class TestFileExistence:
    """Missing file paths should produce an error."""

    def test_missing_both_files(self) -> None:
        from openreview_cli.app import compare

        with pytest.raises(_Exit) as exc:
            compare(
                doc_a="/nonexistent/a.pdf",
                doc_b="/nonexistent/b.pdf",
                playbook=None,
                extraction_model=None,
                qa_model=None,
                confidence_threshold=None,
                format="text",
                output=None,
                align_only=False,
                verbose=False,
                no_pii=False,
                conservative=False,
                grounding_mode="strict",
                no_grounding=False,
                history=False,
                comparison_model=None,
                show_redlines=False,
                version_label_a=None,
                version_label_b=None,
            )
        assert exc.value.exit_code == 1

    def test_missing_doc_a_only(self) -> None:
        from openreview_cli.app import compare

        with pytest.raises(_Exit) as exc:
            compare(
                doc_a="/nonexistent/a.pdf",
                doc_b="/tmp/exists.pdf",
                playbook=None,
                extraction_model=None,
                qa_model=None,
                confidence_threshold=None,
                format="text",
                output=None,
                align_only=False,
                verbose=False,
                no_pii=False,
                conservative=False,
                grounding_mode="strict",
                no_grounding=False,
                history=False,
                comparison_model=None,
                show_redlines=False,
                version_label_a=None,
                version_label_b=None,
            )
        assert exc.value.exit_code == 1

    def test_existing_pdfs_no_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pdf_pair: tuple[str, str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        mock_report = _make_mock_report()
        monkeypatch.setattr(
            "openreview_cli.bilateral.run_comparison",
            lambda **kw: mock_report,
        )
        monkeypatch.setattr(
            "openreview_cli.bilateral.report.format_comparison_terminal",
            lambda report, verbose=False: "",
        )
        compare(
            doc_a=a,
            doc_b=b,
            playbook=None,
            extraction_model=None,
            qa_model=None,
            confidence_threshold=None,
            format="text",
            output=None,
            align_only=False,
            verbose=False,
            no_pii=False,
            conservative=False,
            grounding_mode="strict",
            no_grounding=False,
            history=False,
            comparison_model=None,
            show_redlines=False,
            version_label_a=None,
            version_label_b=None,
        )


# ---------------------------------------------------------------------------
# Mutually exclusive flags
# ---------------------------------------------------------------------------


class TestMutualExclusion:
    """--conservative and --confidence-threshold cannot be used together."""

    def test_conservative_and_ct_conflict(self, pdf_pair: tuple[str, str]) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        with pytest.raises(_Exit) as exc:
            compare(
                doc_a=a,
                doc_b=b,
                playbook=None,
                extraction_model=None,
                qa_model=None,
                confidence_threshold=0.8,
                format="text",
                output=None,
                align_only=False,
                verbose=False,
                no_pii=False,
                conservative=True,
                grounding_mode="strict",
                no_grounding=False,
                history=False,
                comparison_model=None,
                show_redlines=False,
                version_label_a=None,
                version_label_b=None,
            )
        assert exc.value.exit_code == 3

    def test_conservative_alone_allowed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pdf_pair: tuple[str, str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        mock_report = _make_mock_report()
        monkeypatch.setattr(
            "openreview_cli.bilateral.run_comparison",
            lambda **kw: mock_report,
        )
        monkeypatch.setattr(
            "openreview_cli.bilateral.report.format_comparison_terminal",
            lambda report, verbose=False: "",
        )
        compare(
            doc_a=a,
            doc_b=b,
            playbook=None,
            extraction_model=None,
            qa_model=None,
            confidence_threshold=None,
            format="text",
            output=None,
            align_only=False,
            verbose=False,
            no_pii=False,
            conservative=True,
            grounding_mode="strict",
            no_grounding=False,
            history=False,
            comparison_model=None,
            show_redlines=False,
            version_label_a=None,
            version_label_b=None,
        )

    def test_ct_alone_allowed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pdf_pair: tuple[str, str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        mock_report = _make_mock_report()
        monkeypatch.setattr(
            "openreview_cli.bilateral.run_comparison",
            lambda **kw: mock_report,
        )
        monkeypatch.setattr(
            "openreview_cli.bilateral.report.format_comparison_terminal",
            lambda report, verbose=False: "",
        )
        compare(
            doc_a=a,
            doc_b=b,
            playbook=None,
            extraction_model=None,
            qa_model=None,
            confidence_threshold=0.6,
            format="text",
            output=None,
            align_only=False,
            verbose=False,
            no_pii=False,
            conservative=False,
            grounding_mode="strict",
            no_grounding=False,
            history=False,
            comparison_model=None,
            show_redlines=False,
            version_label_a=None,
            version_label_b=None,
        )


# ---------------------------------------------------------------------------
# Format validation
# ---------------------------------------------------------------------------


class TestFormatValidation:
    """--format must be 'text' or 'json'."""

    def test_invalid_format_rejected(self, pdf_pair: tuple[str, str]) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        with pytest.raises(_Exit) as exc:
            compare(
                doc_a=a,
                doc_b=b,
                playbook=None,
                extraction_model=None,
                qa_model=None,
                confidence_threshold=None,
                format="csv",
                output=None,
                align_only=False,
                verbose=False,
                no_pii=False,
                conservative=False,
                grounding_mode="strict",
                no_grounding=False,
                history=False,
                comparison_model=None,
                show_redlines=False,
                version_label_a=None,
                version_label_b=None,
            )
        assert exc.value.exit_code == 1

    def test_text_format_allowed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pdf_pair: tuple[str, str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        mock_report = _make_mock_report()
        monkeypatch.setattr(
            "openreview_cli.bilateral.run_comparison",
            lambda **kw: mock_report,
        )
        monkeypatch.setattr(
            "openreview_cli.bilateral.report.format_comparison_terminal",
            lambda report, verbose=False: "",
        )
        compare(
            doc_a=a,
            doc_b=b,
            playbook=None,
            extraction_model=None,
            qa_model=None,
            confidence_threshold=None,
            format="text",
            output=None,
            align_only=False,
            verbose=False,
            no_pii=False,
            conservative=False,
            grounding_mode="strict",
            no_grounding=False,
            history=False,
            comparison_model=None,
            show_redlines=False,
            version_label_a=None,
            version_label_b=None,
        )

    def test_json_format_allowed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pdf_pair: tuple[str, str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        mock_report = _make_mock_report()
        monkeypatch.setattr(
            "openreview_cli.bilateral.run_comparison",
            lambda **kw: mock_report,
        )
        monkeypatch.setattr(
            "openreview_cli.bilateral.report.format_comparison_json",
            lambda report: "{}",
        )
        compare(
            doc_a=a,
            doc_b=b,
            playbook=None,
            extraction_model=None,
            qa_model=None,
            confidence_threshold=None,
            format="json",
            output=None,
            align_only=False,
            verbose=False,
            no_pii=False,
            conservative=False,
            grounding_mode="strict",
            no_grounding=False,
            history=False,
            comparison_model=None,
            show_redlines=False,
            version_label_a=None,
            version_label_b=None,
        )


# ---------------------------------------------------------------------------
# Grounding mode validation
# ---------------------------------------------------------------------------


class TestGroundingModeValidation:
    """--grounding-mode must be 'strict' or 'lenient'."""

    def test_invalid_mode_rejected(self, pdf_pair: tuple[str, str]) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        with pytest.raises(_Exit) as exc:
            compare(
                doc_a=a,
                doc_b=b,
                playbook=None,
                extraction_model=None,
                qa_model=None,
                confidence_threshold=None,
                format="text",
                output=None,
                align_only=False,
                verbose=False,
                no_pii=False,
                conservative=False,
                grounding_mode="invalid",
                no_grounding=False,
                history=False,
                comparison_model=None,
                show_redlines=False,
                version_label_a=None,
                version_label_b=None,
            )
        assert exc.value.exit_code == 1

    def test_strict_mode_allowed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pdf_pair: tuple[str, str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        mock_report = _make_mock_report()
        monkeypatch.setattr(
            "openreview_cli.bilateral.run_comparison",
            lambda **kw: mock_report,
        )
        monkeypatch.setattr(
            "openreview_cli.bilateral.report.format_comparison_terminal",
            lambda report, verbose=False: "",
        )
        compare(
            doc_a=a,
            doc_b=b,
            playbook=None,
            extraction_model=None,
            qa_model=None,
            confidence_threshold=None,
            format="text",
            output=None,
            align_only=False,
            verbose=False,
            no_pii=False,
            conservative=False,
            grounding_mode="strict",
            no_grounding=False,
            history=False,
            comparison_model=None,
            show_redlines=False,
            version_label_a=None,
            version_label_b=None,
        )

    def test_lenient_mode_allowed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pdf_pair: tuple[str, str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        mock_report = _make_mock_report()
        monkeypatch.setattr(
            "openreview_cli.bilateral.run_comparison",
            lambda **kw: mock_report,
        )
        monkeypatch.setattr(
            "openreview_cli.bilateral.report.format_comparison_terminal",
            lambda report, verbose=False: "",
        )
        compare(
            doc_a=a,
            doc_b=b,
            playbook=None,
            extraction_model=None,
            qa_model=None,
            confidence_threshold=None,
            format="text",
            output=None,
            align_only=False,
            verbose=False,
            no_pii=False,
            conservative=False,
            grounding_mode="lenient",
            no_grounding=False,
            history=False,
            comparison_model=None,
            show_redlines=False,
            version_label_a=None,
            version_label_b=None,
        )


# ---------------------------------------------------------------------------
# --align-only flag
# ---------------------------------------------------------------------------


class TestAlignOnly:
    """--align-only skips inference in run_comparison."""

    def test_align_only_passed_true(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pdf_pair: tuple[str, str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        captured: dict[str, Any] = {}

        def fake_run(**kw: object) -> ComparisonReport:
            captured["align_only"] = kw.get("align_only")
            return _make_mock_report()

        monkeypatch.setattr(
            "openreview_cli.bilateral.run_comparison",
            fake_run,
        )
        monkeypatch.setattr(
            "openreview_cli.bilateral.report.format_comparison_terminal",
            lambda report, verbose=False: "",
        )
        compare(
            doc_a=a,
            doc_b=b,
            playbook=None,
            extraction_model=None,
            qa_model=None,
            confidence_threshold=None,
            format="text",
            output=None,
            align_only=True,
            verbose=False,
            no_pii=False,
            conservative=False,
            grounding_mode="strict",
            no_grounding=False,
            history=False,
            comparison_model=None,
            show_redlines=False,
            version_label_a=None,
            version_label_b=None,
        )
        assert captured.get("align_only") is True


# ---------------------------------------------------------------------------
# --verbose flag
# ---------------------------------------------------------------------------


class TestVerbose:
    """--verbose passes verbose=True to run_comparison."""

    def test_verbose_passed_true(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pdf_pair: tuple[str, str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        captured: dict[str, Any] = {}

        def fake_run(**kw: object) -> ComparisonReport:
            captured["verbose"] = kw.get("verbose")
            return _make_mock_report()

        monkeypatch.setattr(
            "openreview_cli.bilateral.run_comparison",
            fake_run,
        )
        monkeypatch.setattr(
            "openreview_cli.bilateral.report.format_comparison_terminal",
            lambda report, verbose=False: "",
        )
        compare(
            doc_a=a,
            doc_b=b,
            playbook=None,
            extraction_model=None,
            qa_model=None,
            confidence_threshold=None,
            format="text",
            output=None,
            align_only=False,
            verbose=True,
            no_pii=False,
            conservative=False,
            grounding_mode="strict",
            no_grounding=False,
            history=False,
            comparison_model=None,
            show_redlines=False,
            version_label_a=None,
            version_label_b=None,
        )
        assert captured.get("verbose") is True


# ---------------------------------------------------------------------------
# --conservative flag
# ---------------------------------------------------------------------------


class TestConservative:
    """--conservative sets confidence_threshold=0.8 and enables verbose."""

    def test_conservative_sets_threshold_and_verbose(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pdf_pair: tuple[str, str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        captured: dict[str, Any] = {}

        def fake_run(**kw: object) -> ComparisonReport:
            captured["confidence_threshold"] = kw.get("confidence_threshold")
            captured["verbose"] = kw.get("verbose")
            return _make_mock_report()

        monkeypatch.setattr(
            "openreview_cli.bilateral.run_comparison",
            fake_run,
        )
        monkeypatch.setattr(
            "openreview_cli.bilateral.report.format_comparison_terminal",
            lambda report, verbose=False: "",
        )
        compare(
            doc_a=a,
            doc_b=b,
            playbook=None,
            extraction_model=None,
            qa_model=None,
            confidence_threshold=None,
            format="text",
            output=None,
            align_only=False,
            verbose=False,
            no_pii=False,
            conservative=True,
            grounding_mode="strict",
            no_grounding=False,
            history=False,
            comparison_model=None,
            show_redlines=False,
            version_label_a=None,
            version_label_b=None,
        )
        assert captured.get("confidence_threshold") == 0.8
        assert captured.get("verbose") is True


# ---------------------------------------------------------------------------
# --format json
# ---------------------------------------------------------------------------


class TestJsonFormat:
    """--format json uses JSON output formatting and file writing."""

    def test_json_format_calls_json_formatter(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pdf_pair: tuple[str, str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        called: list[bool] = []

        def fake_json(report: ComparisonReport) -> str:
            called.append(True)
            return '{"key": "value"}'

        monkeypatch.setattr(
            "openreview_cli.bilateral.run_comparison",
            lambda **kw: _make_mock_report(),
        )
        monkeypatch.setattr(
            "openreview_cli.bilateral.report.format_comparison_json",
            fake_json,
        )
        compare(
            doc_a=a,
            doc_b=b,
            playbook=None,
            extraction_model=None,
            qa_model=None,
            confidence_threshold=None,
            format="json",
            output=None,
            align_only=False,
            verbose=False,
            no_pii=False,
            conservative=False,
            grounding_mode="strict",
            no_grounding=False,
            history=False,
            comparison_model=None,
            show_redlines=False,
            version_label_a=None,
            version_label_b=None,
        )
        assert called, "format_comparison_json was not called"

    def test_json_format_writes_file(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pdf_pair: tuple[str, str],
        tmp_path: Path,
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        output_file = tmp_path / "output.json"

        monkeypatch.setattr(
            "openreview_cli.bilateral.run_comparison",
            lambda **kw: _make_mock_report(),
        )
        monkeypatch.setattr(
            "openreview_cli.bilateral.report.format_comparison_json",
            lambda report: '{"key": "value"}',
        )
        compare(
            doc_a=a,
            doc_b=b,
            playbook=None,
            extraction_model=None,
            qa_model=None,
            confidence_threshold=None,
            format="json",
            output=str(output_file),
            align_only=False,
            verbose=False,
            no_pii=False,
            conservative=False,
            grounding_mode="strict",
            no_grounding=False,
            history=False,
            comparison_model=None,
            show_redlines=False,
            version_label_a=None,
            version_label_b=None,
        )
        assert output_file.exists()
        assert output_file.read_text(encoding="utf-8") == '{"key": "value"}'


# ---------------------------------------------------------------------------
# Error output messages
# ---------------------------------------------------------------------------


class TestErrorOutput:
    """Error messages go to stderr with appropriate descriptions."""

    def test_missing_file_error_message(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from openreview_cli.app import compare

        with pytest.raises(_Exit):
            compare(
                doc_a="/nonexistent/a.pdf",
                doc_b="/nonexistent/b.pdf",
                playbook=None,
                extraction_model=None,
                qa_model=None,
                confidence_threshold=None,
                format="text",
                output=None,
                align_only=False,
                verbose=False,
                no_pii=False,
                conservative=False,
                grounding_mode="strict",
                no_grounding=False,
                history=False,
                comparison_model=None,
                show_redlines=False,
                version_label_a=None,
                version_label_b=None,
            )
        stderr = capsys.readouterr().err
        assert "File not found" in stderr

    def test_mutual_exclusion_error_message(
        self,
        pdf_pair: tuple[str, str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        with pytest.raises(_Exit):
            compare(
                doc_a=a,
                doc_b=b,
                playbook=None,
                extraction_model=None,
                qa_model=None,
                confidence_threshold=0.8,
                format="text",
                output=None,
                align_only=False,
                verbose=False,
                no_pii=False,
                conservative=True,
                grounding_mode="strict",
                no_grounding=False,
                history=False,
                comparison_model=None,
                show_redlines=False,
                version_label_a=None,
                version_label_b=None,
            )
        stderr = capsys.readouterr().err
        assert "mutually exclusive" in stderr

    def test_invalid_format_error_message(
        self,
        pdf_pair: tuple[str, str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        with pytest.raises(_Exit):
            compare(
                doc_a=a,
                doc_b=b,
                playbook=None,
                extraction_model=None,
                qa_model=None,
                confidence_threshold=None,
                format="csv",
                output=None,
                align_only=False,
                verbose=False,
                no_pii=False,
                conservative=False,
                grounding_mode="strict",
                no_grounding=False,
                history=False,
                comparison_model=None,
                show_redlines=False,
                version_label_a=None,
                version_label_b=None,
            )
        stderr = capsys.readouterr().err
        assert "format" in stderr.lower()

    def test_invalid_grounding_error_message(
        self,
        pdf_pair: tuple[str, str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        with pytest.raises(_Exit):
            compare(
                doc_a=a,
                doc_b=b,
                playbook=None,
                extraction_model=None,
                qa_model=None,
                confidence_threshold=None,
                format="text",
                output=None,
                align_only=False,
                verbose=False,
                no_pii=False,
                conservative=False,
                grounding_mode="bad",
                no_grounding=False,
                history=False,
                comparison_model=None,
                show_redlines=False,
                version_label_a=None,
                version_label_b=None,
            )
        stderr = capsys.readouterr().err
        assert "grounding" in stderr.lower()


# ---------------------------------------------------------------------------
# Run-comparison error propagation
# ---------------------------------------------------------------------------


class TestRunComparisonErrors:
    """Errors from run_comparison are caught and re-raised with exit codes."""

    def test_file_not_found_propagated(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pdf_pair: tuple[str, str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair

        def fake_run(**kw: object) -> ComparisonReport:
            raise FileNotFoundError("Doc not found")

        monkeypatch.setattr(
            "openreview_cli.bilateral.run_comparison",
            fake_run,
        )
        monkeypatch.setattr(
            "openreview_cli.bilateral.report.format_comparison_terminal",
            lambda report, verbose=False: "",
        )
        with pytest.raises(_Exit) as exc:
            compare(
                doc_a=a,
                doc_b=b,
                playbook=None,
                extraction_model=None,
                qa_model=None,
                confidence_threshold=None,
                format="text",
                output=None,
                align_only=False,
                verbose=False,
                no_pii=False,
                conservative=False,
                grounding_mode="strict",
                no_grounding=False,
                history=False,
                comparison_model=None,
                show_redlines=False,
                version_label_a=None,
                version_label_b=None,
            )
        assert exc.value.exit_code == 1

    def test_generic_error_propagated(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pdf_pair: tuple[str, str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair

        def fake_run(**kw: object) -> ComparisonReport:
            raise RuntimeError("Pipeline crashed")

        monkeypatch.setattr(
            "openreview_cli.bilateral.run_comparison",
            fake_run,
        )
        monkeypatch.setattr(
            "openreview_cli.bilateral.report.format_comparison_terminal",
            lambda report, verbose=False: "",
        )
        with pytest.raises(_Exit) as exc:
            compare(
                doc_a=a,
                doc_b=b,
                playbook=None,
                extraction_model=None,
                qa_model=None,
                confidence_threshold=None,
                format="text",
                output=None,
                align_only=False,
                verbose=False,
                no_pii=False,
                conservative=False,
                grounding_mode="strict",
                no_grounding=False,
                history=False,
                comparison_model=None,
                show_redlines=False,
                version_label_a=None,
                version_label_b=None,
            )
        assert exc.value.exit_code == 2


# ---------------------------------------------------------------------------
# Multiple error paths
# ---------------------------------------------------------------------------


class TestMultipleErrorPaths:
    """Combinations of invalid inputs produce appropriate errors."""

    def test_missing_file_with_invalid_format(self) -> None:
        from openreview_cli.app import compare

        with pytest.raises(_Exit) as exc:
            compare(
                doc_a="/nonexistent/a.pdf",
                doc_b="/nonexistent/b.pdf",
                playbook=None,
                extraction_model=None,
                qa_model=None,
                confidence_threshold=None,
                format="html",
                output=None,
                align_only=False,
                verbose=False,
                no_pii=False,
                conservative=False,
                grounding_mode="strict",
                no_grounding=False,
                history=False,
                comparison_model=None,
                show_redlines=False,
                version_label_a=None,
                version_label_b=None,
            )
        # Format check runs before file check
        assert exc.value.exit_code == 1

    def test_missing_file_with_invalid_grounding(self) -> None:
        from openreview_cli.app import compare

        with pytest.raises(_Exit) as exc:
            compare(
                doc_a="/nonexistent/a.pdf",
                doc_b="/nonexistent/b.pdf",
                playbook=None,
                extraction_model=None,
                qa_model=None,
                confidence_threshold=None,
                format="text",
                output=None,
                align_only=False,
                verbose=False,
                no_pii=False,
                conservative=False,
                grounding_mode="bad",
                no_grounding=False,
                history=False,
                comparison_model=None,
                show_redlines=False,
                version_label_a=None,
                version_label_b=None,
            )
        # Grounding check runs before file check
        assert exc.value.exit_code == 1


# ---------------------------------------------------------------------------
# Dispatch correctness with various flag combos
# ---------------------------------------------------------------------------


class TestDispatchCombinations:
    """All flag combos pass correct values to run_comparison."""

    def test_default_args_passed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pdf_pair: tuple[str, str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        captured: dict[str, Any] = {}

        def fake_run(**kw: object) -> ComparisonReport:
            captured.update(kw)
            return _make_mock_report()

        monkeypatch.setattr(
            "openreview_cli.bilateral.run_comparison",
            fake_run,
        )
        monkeypatch.setattr(
            "openreview_cli.bilateral.report.format_comparison_terminal",
            lambda report, verbose=False: "",
        )
        compare(
            doc_a=a,
            doc_b=b,
            playbook=None,
            extraction_model=None,
            qa_model=None,
            confidence_threshold=None,
            format="text",
            output=None,
            align_only=False,
            verbose=False,
            no_pii=False,
            conservative=False,
            grounding_mode="strict",
            no_grounding=False,
            history=False,
            comparison_model=None,
            show_redlines=False,
            version_label_a=None,
            version_label_b=None,
        )
        assert captured.get("no_pii") is False
        assert captured.get("verbose") is False
        assert captured.get("confidence_threshold") == 0.7
        assert captured.get("align_only") is False
        assert captured.get("grounding_mode") == "strict"

    def test_all_flags_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pdf_pair: tuple[str, str],
    ) -> None:
        from openreview_cli.app import compare

        a, b = pdf_pair
        captured: dict[str, Any] = {}

        def fake_run(**kw: object) -> ComparisonReport:
            captured.update(kw)
            return _make_mock_report()

        monkeypatch.setattr(
            "openreview_cli.bilateral.run_comparison",
            fake_run,
        )
        monkeypatch.setattr(
            "openreview_cli.bilateral.report.format_comparison_json",
            lambda report: "{}",
        )
        compare(
            doc_a=a,
            doc_b=b,
            playbook=None,
            extraction_model="gpt4",
            qa_model="claude3",
            confidence_threshold=0.5,
            format="json",
            output=None,
            align_only=False,
            verbose=True,
            no_pii=True,
            conservative=False,
            grounding_mode="lenient",
            no_grounding=False,
            history=False,
            comparison_model=None,
            show_redlines=False,
            version_label_a=None,
            version_label_b=None,
        )
        assert captured.get("extraction_model") == "gpt4"
        assert captured.get("qa_model") == "claude3"
        assert captured.get("confidence_threshold") == 0.5
        assert captured.get("no_pii") is True
        assert captured.get("grounding_mode") == "lenient"
