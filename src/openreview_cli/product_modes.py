"""Single source of truth for the named product modes (D7/R9).

Three consumers derive from this module:

* ``openreview_cli.app`` registers one Typer subcommand per named mode,
* ``openreview_cli.tui.screens.review_wizard`` renders the grouped mode picker,
* ``openreview_cli.benchmark.cli`` validates ``--modes``.

The names must stay equal to ``review.playbook.BUNDLED_PLAYBOOKS`` (one bundled
playbook per named mode, plus the generic ``precheck`` mode);
``tests/unit/test_product_modes_single_source.py`` enforces that, so adding a
playbook without a group entry fails the suite instead of silently shipping a mode
the TUI cannot select.
"""

from __future__ import annotations

from dataclasses import dataclass

# The base NDA mode. It has its own `openreview precheck …` sub-app, so it is not
# registered as a <mode> review subcommand, but the TUI selectlist does offer it.
GENERIC_MODE = "precheck"

GROUP_ORDER: tuple[str, ...] = ("Basic", "Employment", "Commercial", "Specialized", "Settlement")


@dataclass(frozen=True)
class ProductMode:
    """One selectable product mode: its name, picker group and CLI help text."""

    name: str
    group: str
    help: str
    path_help: str
    generic: bool = False


PRODUCT_MODES: tuple[ProductMode, ...] = (
    ProductMode(
        GENERIC_MODE,
        "Basic",
        "Review an NDA with PreCheck.",
        "Path to an NDA (PDF or DOCX).",
        generic=True,
    ),
    # The 23 named modes below are in the exact order of app.py's literal (3343-3459),
    # so `_PRODUCT_MODES` keeps today's `openreview --help` ordering byte-for-byte.
    # Every `help`/`path_help` is transcribed verbatim from app.py:3343-3459; the
    # generic `precheck` entry above is the ONLY invented one (it has no subcommand
    # in app.py, so there was no literal to copy).
    ProductMode(
        "licensecheck",
        "Commercial",
        "Review a SaaS/software license agreement with LicenseCheck.",
        "Path to a SaaS/software license agreement (PDF or DOCX).",
    ),
    ProductMode(
        "leasecheck",
        "Commercial",
        "Review a commercial lease agreement with LeaseCheck.",
        "Path to a commercial lease agreement (PDF or DOCX).",
    ),
    ProductMode(
        "privacycheck",
        "Specialized",
        "Review a Data Processing Agreement with PrivacyCheck.",
        "Path to a Data Processing Agreement (PDF or DOCX).",
    ),
    ProductMode(
        "privacycheck_v2",
        "Specialized",
        "Review a Data Processing Agreement (v2) with PrivacyCheck.",
        "Path to a Data Processing Agreement (PDF or DOCX).",
    ),
    ProductMode(
        "dealcheck",
        "Commercial",
        "Review a vendor/service agreement with DealCheck.",
        "Path to a vendor or service agreement (PDF or DOCX).",
    ),
    ProductMode(
        "hirecheck",
        "Employment",
        "Review an employment agreement with HireCheck.",
        "Path to an employment agreement (PDF or DOCX).",
    ),
    ProductMode(
        "indemnitycheck",
        "Specialized",
        "Review an indemnification agreement with IndemnityCheck.",
        "Path to an indemnification agreement (PDF or DOCX).",
    ),
    ProductMode(
        "consultcheck",
        "Employment",
        "Review a consulting services agreement with ConsultCheck.",
        "Path to a consulting services agreement (PDF or DOCX).",
    ),
    ProductMode(
        "workcheck",
        "Employment",
        "Review an independent contractor/work-for-hire agreement with WorkCheck.",
        "Path to an independent contractor agreement (PDF or DOCX).",
    ),
    ProductMode(
        "loicheck",
        "Specialized",
        "Review a letter of intent or MOU with LOICheck.",
        "Path to a letter of intent or MOU (PDF or DOCX).",
    ),
    ProductMode(
        "subcheck",
        "Specialized",
        "Review a subcontractor agreement with SubCheck.",
        "Path to a subcontractor agreement (PDF or DOCX).",
    ),
    ProductMode(
        "settlementcheck",
        "Settlement",
        "Review a settlement/release agreement with SettlementCheck.",
        "Path to a settlement or release agreement (PDF or DOCX).",
    ),
    ProductMode(
        "settlementcheck_v2",
        "Settlement",
        "Review a complex settlement/release agreement (v2) with SettlementCheck.",
        "Path to a complex settlement or release agreement (PDF or DOCX).",
    ),
    ProductMode(
        "assetcheck",
        "Commercial",
        "Review an asset transfer/assignment agreement with AssetCheck.",
        "Path to an asset transfer or assignment agreement (PDF or DOCX).",
    ),
    ProductMode(
        "buycheck",
        "Commercial",
        "Review an asset purchase/business acquisition agreement with BuyCheck.",
        "Path to an asset purchase or acquisition agreement (PDF or DOCX).",
    ),
    ProductMode(
        "engagecheck",
        "Employment",
        "Review a professional services engagement letter with EngageCheck.",
        "Path to an engagement letter (PDF or DOCX).",
    ),
    ProductMode(
        "guaranteecheck",
        "Commercial",
        "Review a personal guarantee/suretyship agreement with GuaranteeCheck.",
        "Path to a personal guarantee or suretyship agreement (PDF or DOCX).",
    ),
    ProductMode(
        "loancheck",
        "Specialized",
        "Review a loan agreement/promissory note with LoanCheck.",
        "Path to a loan agreement or promissory note (PDF or DOCX).",
    ),
    ProductMode(
        "franchisecheck",
        "Commercial",
        "Review a franchise agreement or franchise disclosure document.",
        "Path to a franchise agreement or FDD (PDF or DOCX).",
    ),
    ProductMode(
        "opcheck",
        "Specialized",
        "Review an Operating Agreement (LLC governance document).",
        "Path to an operating agreement (PDF or DOCX).",
    ),
    ProductMode(
        "partnercheck",
        "Commercial",
        "Review a general or limited partnership agreement.",
        "Path to a partnership agreement (PDF or DOCX).",
    ),
    ProductMode(
        "sponsorcheck",
        "Specialized",
        "Review a sponsorship agreement.",
        "Path to a sponsorship agreement (PDF or DOCX).",
    ),
    ProductMode(
        "distrocheck",
        "Commercial",
        "Review a distribution or reseller agreement.",
        "Path to a distribution agreement (PDF or DOCX).",
    ),
)

MODE_GROUPS: dict[str, list[str]] = {
    group: [mode.name for mode in PRODUCT_MODES if mode.group == group] for group in GROUP_ORDER
}
