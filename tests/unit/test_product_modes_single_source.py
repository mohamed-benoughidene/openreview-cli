"""R9/D7: the product-mode list has exactly one source of truth.

``openreview_cli.product_modes`` owns the names, their group and their CLI help.
The Typer app, the TUI wizard and the benchmark ``--modes`` validator all derive
from it, and the names must stay equal to the bundled playbooks (one playbook per
named mode, plus ``precheck``).
"""

from __future__ import annotations

from openreview_cli.benchmark.cli import VALID_MODES
from openreview_cli.product_modes import GENERIC_MODE, GROUP_ORDER, MODE_GROUPS, PRODUCT_MODES
from openreview_cli.review.playbook import BUNDLED_PLAYBOOKS
from openreview_cli.tui.screens.review_wizard import PRODUCT_MODES as TUI_PRODUCT_MODES


def test_grouping_covers_every_bundled_playbook() -> None:
    grouped = [name for names in MODE_GROUPS.values() for name in names]
    assert set(grouped) == set(BUNDLED_PLAYBOOKS)
    assert len(grouped) == len(set(grouped)) == 24
    assert list(MODE_GROUPS) == list(GROUP_ORDER)
    assert all(MODE_GROUPS[group] for group in GROUP_ORDER)


# Literal expected spec, transcribed BY HAND from src/openreview_cli/app.py:3343-3459 as
# (name, help, path_help), in app order. It is deliberately NOT derived from PRODUCT_MODES:
# a reorder or a typo in product_modes.py (or in the app.py derivation) must fail here.
EXPECTED_NAMED_MODES: tuple[tuple[str, str, str], ...] = (
    (
        "licensecheck",
        "Review a SaaS/software license agreement with LicenseCheck.",
        "Path to a SaaS/software license agreement (PDF or DOCX).",
    ),
    (
        "leasecheck",
        "Review a commercial lease agreement with LeaseCheck.",
        "Path to a commercial lease agreement (PDF or DOCX).",
    ),
    (
        "privacycheck",
        "Review a Data Processing Agreement with PrivacyCheck.",
        "Path to a Data Processing Agreement (PDF or DOCX).",
    ),
    (
        "privacycheck_v2",
        "Review a Data Processing Agreement (v2) with PrivacyCheck.",
        "Path to a Data Processing Agreement (PDF or DOCX).",
    ),
    (
        "dealcheck",
        "Review a vendor/service agreement with DealCheck.",
        "Path to a vendor or service agreement (PDF or DOCX).",
    ),
    (
        "hirecheck",
        "Review an employment agreement with HireCheck.",
        "Path to an employment agreement (PDF or DOCX).",
    ),
    (
        "indemnitycheck",
        "Review an indemnification agreement with IndemnityCheck.",
        "Path to an indemnification agreement (PDF or DOCX).",
    ),
    (
        "consultcheck",
        "Review a consulting services agreement with ConsultCheck.",
        "Path to a consulting services agreement (PDF or DOCX).",
    ),
    (
        "workcheck",
        "Review an independent contractor/work-for-hire agreement with WorkCheck.",
        "Path to an independent contractor agreement (PDF or DOCX).",
    ),
    (
        "loicheck",
        "Review a letter of intent or MOU with LOICheck.",
        "Path to a letter of intent or MOU (PDF or DOCX).",
    ),
    (
        "subcheck",
        "Review a subcontractor agreement with SubCheck.",
        "Path to a subcontractor agreement (PDF or DOCX).",
    ),
    (
        "settlementcheck",
        "Review a settlement/release agreement with SettlementCheck.",
        "Path to a settlement or release agreement (PDF or DOCX).",
    ),
    (
        "settlementcheck_v2",
        "Review a complex settlement/release agreement (v2) with SettlementCheck.",
        "Path to a complex settlement or release agreement (PDF or DOCX).",
    ),
    (
        "assetcheck",
        "Review an asset transfer/assignment agreement with AssetCheck.",
        "Path to an asset transfer or assignment agreement (PDF or DOCX).",
    ),
    (
        "buycheck",
        "Review an asset purchase/business acquisition agreement with BuyCheck.",
        "Path to an asset purchase or acquisition agreement (PDF or DOCX).",
    ),
    (
        "engagecheck",
        "Review a professional services engagement letter with EngageCheck.",
        "Path to an engagement letter (PDF or DOCX).",
    ),
    (
        "guaranteecheck",
        "Review a personal guarantee/suretyship agreement with GuaranteeCheck.",
        "Path to a personal guarantee or suretyship agreement (PDF or DOCX).",
    ),
    (
        "loancheck",
        "Review a loan agreement/promissory note with LoanCheck.",
        "Path to a loan agreement or promissory note (PDF or DOCX).",
    ),
    (
        "franchisecheck",
        "Review a franchise agreement or franchise disclosure document.",
        "Path to a franchise agreement or FDD (PDF or DOCX).",
    ),
    (
        "opcheck",
        "Review an Operating Agreement (LLC governance document).",
        "Path to an operating agreement (PDF or DOCX).",
    ),
    (
        "partnercheck",
        "Review a general or limited partnership agreement.",
        "Path to a partnership agreement (PDF or DOCX).",
    ),
    (
        "sponsorcheck",
        "Review a sponsorship agreement.",
        "Path to a sponsorship agreement (PDF or DOCX).",
    ),
    (
        "distrocheck",
        "Review a distribution or reseller agreement.",
        "Path to a distribution agreement (PDF or DOCX).",
    ),
)


def test_named_modes_pin_the_literal_23_in_app_order_with_their_help() -> None:
    """Pin the 23 names IN ORDER and each help/path_help to a literal string.

    ``_PRODUCT_MODES`` is derived from ``PRODUCT_MODES``, so comparing the two to each
    other is tautological. This compares them to the hand-transcribed literal above, so a
    reorder or a typo in ``product_modes.py`` (and in the app.py derivation) actually fails.
    """
    from openreview_cli.app import _PRODUCT_MODES

    named = [(mode.name, mode.help, mode.path_help) for mode in PRODUCT_MODES if not mode.generic]
    assert named == list(EXPECTED_NAMED_MODES), (
        "named mode order/help drifted from the literal app.py:3343-3459 transcription"
    )
    assert list(EXPECTED_NAMED_MODES) == _PRODUCT_MODES
    assert len(named) == 23
    assert GENERIC_MODE not in [name for name, _, _ in EXPECTED_NAMED_MODES]


# Literal expected picker, transcribed BY HAND: the 5 group keys in GROUP_ORDER order and the
# 24 member names in the order the MODE_GROUPS derivation yields (within a group, the
# PRODUCT_MODES declaration order). `review_wizard.py` now BUILDS its dict from MODE_GROUPS, so
# comparing TUI_PRODUCT_MODES to MODE_GROUPS is tautological and can never fail; this literal is
# what makes a broken derivation fail.
EXPECTED_TUI_MODES: dict[str, list[str]] = {
    "Basic": ["precheck"],
    "Employment": ["hirecheck", "consultcheck", "workcheck", "engagecheck"],
    "Commercial": [
        "licensecheck",
        "leasecheck",
        "dealcheck",
        "assetcheck",
        "buycheck",
        "guaranteecheck",
        "franchisecheck",
        "partnercheck",
        "distrocheck",
    ],
    "Specialized": [
        "privacycheck",
        "privacycheck_v2",
        "indemnitycheck",
        "loicheck",
        "subcheck",
        "loancheck",
        "opcheck",
        "sponsorcheck",
    ],
    "Settlement": ["settlementcheck", "settlementcheck_v2"],
}


def test_tui_renders_every_named_mode_plus_the_generic_mode() -> None:
    assert TUI_PRODUCT_MODES == EXPECTED_TUI_MODES
    rendered = [name for names in TUI_PRODUCT_MODES.values() for name in names]
    assert len(rendered) == 24
    assert GENERIC_MODE in rendered
    assert {mode.name for mode in PRODUCT_MODES} == set(rendered)


def test_benchmark_valid_modes_derives_from_the_single_source() -> None:
    expected = frozenset({GENERIC_MODE, *(m.name for m in PRODUCT_MODES if not m.generic)})
    assert expected == VALID_MODES
    assert len(VALID_MODES) == 24


def test_every_mode_has_cli_help_and_a_path_help() -> None:
    for mode in PRODUCT_MODES:
        assert mode.help.strip()
        assert mode.path_help.strip()
        assert mode.group in GROUP_ORDER
