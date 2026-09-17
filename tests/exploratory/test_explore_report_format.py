"""Exploratory probes: ``format_terminal`` rendering edge cases.

Covers the terminal-report work on ``feat/design-ux-remediation`` (P1/C1 colour,
P2/C4 width, mode-derived title) with adversarial inputs: very narrow and
ultra-wide consoles, empty reports, multibyte text, custom/empty mode names and
partially-coloured / inconsistently-summarised reports.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from openreview_cli.review.colors import AssessmentColor
from openreview_cli.review.models import (
    ClauseAssessment,
    DocMeta,
    Position,
    QAVerdict,
    ReviewReport,
    ReviewSummary,
)
from openreview_cli.review.report import format_terminal

_UNSET = object()


def _ca(
    clause_id: str,
    text: str,
    *,
    conf: float = 0.92,
    color: object = _UNSET,
    category: str = "confidentiality-term",
    position: Position = Position.PREFERRED,
) -> ClauseAssessment:
    assessment = ClauseAssessment(
        clause_id=clause_id,
        clause_text=text,
        playbook_category=category,
        position=position,
        confidence=conf,
        citation="clause",
        qa_verdict=QAVerdict.agree,
        extraction_model="m1",
        qa_model="m1",
    )
    if color is not _UNSET:
        assessment.color = color  # type: ignore[assignment]
    return assessment


def _report(
    assessments: list[ClauseAssessment],
    *,
    mode: str = "precheck",
    summary: ReviewSummary | None = None,
    overrides: dict[str, float] | None = None,
) -> ReviewReport:
    report = ReviewReport(
        document=DocMeta(
            filename="nda.docx", page_count=1, clause_count=len(assessments), pii_stripped=True
        ),
        assessments=assessments,
        summary=summary or ReviewSummary(avg_confidence=0.9),
        playbook_id="pb",
        generated_at=datetime.now(UTC),
        mode=mode,
    )
    if overrides is not None:
        report.mode_threshold_overrides = overrides
    return report


def _max_line(text: str) -> int:
    return max((len(line) for line in text.splitlines()), default=0)


# ── Width ──────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_narrow_40_cols_wraps_to_width() -> None:
    """At 40 cols the table squeezes and the clause text wraps across lines."""
    out = format_terminal(_report([_ca("c1", "Confidentiality term.")]), color=False, width=40)
    assert _max_line(out) <= 40, _max_line(out)
    # The phrase wraps ("Confidentiality" / "term."), so assert on the pieces.
    assert "Confidentiality" in out
    assert "term." in out
    assert "Summary" in out


@pytest.mark.fast
def test_ultra_wide_300_cols_does_not_overflow_or_truncate_content() -> None:
    long_text = "A" * 70
    out = format_terminal(
        _report([_ca("c1", long_text), _ca("c2", "short clause")]), color=False, width=300
    )
    assert _max_line(out) <= 300
    # The table stops growing at its natural width but content is intact.
    assert "short clause" in out
    assert "Clause" in out and "Status" in out


@pytest.mark.fast
@pytest.mark.parametrize("width", [0, 1, 2, -1, -100])
def test_degenerate_widths_do_not_raise(width: int) -> None:
    """FINDING: extreme widths degrade gracefully (empty/tiny output) instead
    of raising — Rich clamps the console."""
    out = format_terminal(_report([_ca("c1", "x")]), color=False, width=width)
    assert isinstance(out, str)


@pytest.mark.fast
def test_width_boundary_40_does_not_exceed_and_200_produces_table() -> None:
    narrow = format_terminal(_report([_ca("c1", "hello", color="green")]), color=False, width=40)
    wide = format_terminal(_report([_ca("c1", "hello", color="green")]), color=False, width=200)
    assert _max_line(narrow) <= 40
    assert _max_line(wide) <= 200
    assert "│" in wide  # the table border survives


# ── Empty assessments ──────────────────────────────────────────────────────


@pytest.mark.fast
def test_empty_assessments_prints_no_clauses_message() -> None:
    out = format_terminal(_report([]), color=False, width=100)
    assert "No clauses to assess." in out
    assert "Summary" not in out  # early return skips the summary block


@pytest.mark.fast
def test_empty_assessments_with_privacy_footer_appends_footer() -> None:
    out = format_terminal(
        _report([]), color=False, width=100, privacy_footer="Tier: maximum\nCloud calls: 3"
    )
    assert "No clauses to assess." in out
    assert "Tier: maximum" in out
    assert "Cloud calls: 3" in out


@pytest.mark.fast
def test_empty_assessments_without_footer_has_no_trailing_footer_block() -> None:
    out = format_terminal(_report([]), color=False, width=100)
    assert "Tier:" not in out


# ── Multibyte text ─────────────────────────────────────────────────────────


@pytest.mark.fast
def test_multibyte_clause_text_is_preserved_and_padded() -> None:
    out = format_terminal(
        _report(
            [
                _ca("c1", "保密条款 — confidentiality 【重要】"),
                _ca("c2", "Emoji 😀🚀 clause with combining é and CJK 日本語テキスト"),
            ]
        ),
        color=False,
        width=100,
    )
    assert "保密条款" in out
    assert "日本語テキスト" in out
    assert "😀" in out
    assert _max_line(out) <= 100


@pytest.mark.fast
def test_multibyte_does_not_overflow_ultra_wide() -> None:
    out = format_terminal(_report([_ca("c1", "日本語 テキスト " * 3)]), color=False, width=300)
    # Visual width of CJK is 2 cells; the character count stays bounded.
    assert _max_line(out) <= 300


# ── Mode-derived titles ────────────────────────────────────────────────────


@pytest.mark.fast
@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("precheck", "NDA Review Report"),
        ("licensecheck", "Licensecheck Review Report"),
        ("privacycheck_v2", "Privacycheck V2 Review Report"),
        ("a_b_c_d", "A B C D Review Report"),
        ("nda", "Nda Review Report"),
    ],
)
def test_title_derives_from_mode(mode: str, expected: str) -> None:
    out = format_terminal(_report([_ca("c1", "t")], mode=mode), color=False, width=100)
    assert expected in out


@pytest.mark.fast
def test_empty_mode_name_renders_title_with_leading_space() -> None:
    """FINDING (cosmetic): a report with mode ``""`` (never set) yields the
    title ``" Review Report"`` — a stray leading space where the mode goes."""
    out = format_terminal(_report([_ca("c1", "t")], mode=""), color=False, width=100)
    assert " Review Report" in out


@pytest.mark.fast
def test_unicode_mode_name_is_title_cased() -> None:
    out = format_terminal(_report([_ca("c1", "t")], mode="WÉIRD møde"), color=False, width=100)
    assert "Wéird Møde Review Report" in out


# ── Colours ────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_safety_net_assigns_colours_when_none_are_set() -> None:
    report = _report([_ca("c1", "a"), _ca("c2", "b")])
    assert report.assessments[0].color is None
    format_terminal(report, color=False, width=100)
    assert report.assessments[0].color is not None
    assert report.assessments[1].color is not None


@pytest.mark.fast
def test_partial_colour_assignment_renders_none_as_amber() -> None:
    """FINDING (edge case): the safety net only inspects ``assessments[0]``.

    When the first assessment is coloured but a later one is ``None``, the net
    is skipped and the ``None`` colour falls into the ``else`` branch of the
    status ladder — rendered as **AMBER** even though its colour is unassigned.
    """
    report = _report([_ca("c1", "first", color="green"), _ca("c2", "second")])
    out = format_terminal(report, color=False, width=120)
    assert report.assessments[1].color is None  # never assigned
    second_row = next(line for line in out.splitlines() if "second" in line)
    assert "AMBER" in second_row, second_row
    first_row = next(line for line in out.splitlines() if "first" in line)
    assert "AMBER" not in first_row


@pytest.mark.fast
def test_colour_flag_controls_ansi_and_preserves_text() -> None:
    report = _report([_ca("c1", "term", color="green")])
    plain = format_terminal(report, color=False, width=100)
    colored = format_terminal(report, color=True, width=100)
    assert "\x1b[" not in plain
    assert "\x1b[" in colored
    assert "}● OK" not in plain  # sanity: no stray markup leaked
    assert "term" in plain and "term" in colored


@pytest.mark.fast
def test_ballot_status_ladder_for_all_three_colours() -> None:
    report = _report(
        [
            _ca("c1", "green", color=AssessmentColor.green),
            _ca("c2", "amber", color=AssessmentColor.amber),
            _ca("c3", "red", color=AssessmentColor.red),
        ]
    )
    out = format_terminal(report, color=False, width=120)
    assert "● OK" in out
    assert "⚠ AMBER" in out
    assert "● RED" in out


# ── Summary robustness ─────────────────────────────────────────────────────


@pytest.mark.fast
def test_summary_counts_are_printed_verbatim_from_report_summary() -> None:
    """FINDING (edge case): the summary block trusts ``report.summary`` and is
    NOT recomputed from the assessments.  A stale/incorrect summary therefore
    shows ``Amber: 0`` next to an amber row."""
    report = _report(
        [_ca("c1", "amber clause", color="amber")],
        summary=ReviewSummary(amber_count=0, green_count=0, red_count=0),
    )
    out = format_terminal(report, color=False, width=120)
    assert "⚠ AMBER" in out
    assert "Amber flags:  0" in out


@pytest.mark.fast
def test_zero_avg_confidence_renders_dash_but_effective_always_numeric() -> None:
    report = _report([_ca("c1", "t", color="green")], summary=ReviewSummary(avg_confidence=0.0))
    out = format_terminal(report, color=False, width=120)
    assert "Avg confidence: —" in out
    assert "Avg effective confidence: 0.00" in out


@pytest.mark.fast
def test_mode_threshold_overrides_are_listed() -> None:
    report = _report(
        [_ca("c1", "t", color="green")],
        overrides={"licensecheck": 0.75, "precheck": 0.8},
    )
    out = format_terminal(report, color=False, width=120)
    assert "Mode threshold overrides: licensecheck=0.75, precheck=0.8" in out


@pytest.mark.fast
def test_confidence_out_of_range_is_rejected_at_model_construction() -> None:
    """The ``_confidence_bar`` helper can't see bogus values because the model
    validates confidence in ``__post_init__``."""
    for bad in (1.5, -0.01, 2.0):
        with pytest.raises(ValueError):
            _ca("c1", "t", conf=bad)


# ── Grounding column ───────────────────────────────────────────────────────


@pytest.mark.fast
def test_grounding_column_appears_only_when_a_verdict_is_present() -> None:
    from openreview_cli.grounding.models import GroundingVerdict

    without = _report([_ca("c1", "plain", color="green")])
    out_without = format_terminal(without, color=False, width=120)
    assert "Gnd" not in out_without
    assert "Grounding:" not in out_without

    grounded = _ca("c1", "picked", color="green")
    grounded.grounding_verdict = GroundingVerdict.GROUNDED
    ungrounded = _ca("c2", "dropped", color="red")
    ungrounded.grounding_verdict = GroundingVerdict.UNGROUNDED
    uncertain = _ca("c3", "unsure", color="amber")
    uncertain.grounding_verdict = GroundingVerdict.UNCERTAIN

    out = format_terminal(_report([grounded, ungrounded, uncertain]), color=False, width=140)
    assert "Gnd" in out
    assert "Grounding:" in out
    assert "1 grounded" in out
    assert "1 ungrounded" in out
    assert "1 uncertain" in out


@pytest.mark.fast
def test_grounding_summary_counts_not_processed_as_dim() -> None:
    from openreview_cli.grounding.models import GroundingVerdict

    processed = _ca("c1", "done", color="green")
    processed.grounding_verdict = GroundingVerdict.GROUNDED
    pending = _ca("c2", "not yet", color="green")  # grounding_verdict stays None

    out = format_terminal(_report([processed, pending]), color=False, width=140)
    assert "1 grounded" in out
    assert "1 not processed" in out
