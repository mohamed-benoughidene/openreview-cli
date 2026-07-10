"""Controlled mutation catalog for synthetic NDA negotiation diffs.

Each mutation is a targeted text change to a specific clause category.
Mutations simulate realistic negotiation outcomes: shifting governing law,
shortening/lengthening terms, narrowing definitions, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

ChangeType = Literal["addition", "contradiction", "equivalent"]


class ClauseCategory(StrEnum):
    """NDA clause categories that can be mutated."""

    confidentiality_definition = "confidentiality_definition"
    exclusions = "exclusions"
    obligations = "obligations"
    term = "term"
    return_obligations = "return_obligations"
    permitted_disclosures = "permitted_disclosures"
    governing_law = "governing_law"
    jurisdiction = "jurisdiction"
    remedies = "remedies"
    assignment = "assignment"
    survival = "survival"
    no_license = "no_license"


@dataclass(frozen=True)
class MutationDef:
    """A single controlled mutation to apply to a template clause.

    Attributes
    ----------
    name : str
        Human-readable name (e.g. "governing_law_delaware_to_newyork").
    category : ClauseCategory
        Which clause category this mutation targets.
    find_text : str
        Primary substring to find in the clause text.
    replace_text : str
        Replacement text.
    expected_diff_type : ChangeType
        How the change should be classified:
        - "addition": content added that wasn't in the original
        - "contradiction": directly contradictory change
        - "equivalent": semantically equivalent rephrasing
    description : str
        Human-readable description of what this mutation simulates.
    find_text_alternatives : tuple[str, ...]
        Alternative text patterns to try if primary find_text does not match.
    """

    name: str
    category: ClauseCategory
    find_text: str
    replace_text: str
    expected_diff_type: ChangeType
    description: str = ""
    find_text_alternatives: tuple[str, ...] = ()


# ── Mutation definitions ──────────────────────────────────────────────

CONFIDENTIALITY_MUTATIONS: list[MutationDef] = [
    MutationDef(
        name="ci_broader_definition",
        category=ClauseCategory.confidentiality_definition,
        find_text="including without limitation all technical or business information, product plans, customer data, financial information, trade secrets, and know-how",
        replace_text="including without limitation all technical or business information, product plans, customer data, financial information, trade secrets, know-how, source code, algorithms, business strategies, and all communications between the parties",
        expected_diff_type="addition",
        description="Broaden CI definition by adding source code, algorithms, business strategies",
        find_text_alternatives=(
            "including technical or business information, product designs or roadmaps, requirements, pricing, security and compliance documentation, technology, inventions or know-how",
            "This includes business plans, financial data, technical specifications, customer lists, pricing, and trade secrets",
        ),
    ),
    MutationDef(
        name="ci_narrower_definition",
        category=ClauseCategory.confidentiality_definition,
        find_text="including without limitation all technical or business information, product plans, customer data, financial information, trade secrets, and know-how",
        replace_text="including without limitation all technical information and trade secrets that are marked confidential in writing",
        expected_diff_type="contradiction",
        description="Narrow CI definition to marked technical info only",
        find_text_alternatives=(
            "including technical or business information, product designs or roadmaps, requirements, pricing, security and compliance documentation, technology, inventions or know-how",
            "This includes business plans, financial data, technical specifications, customer lists, pricing, and trade secrets",
        ),
    ),
    MutationDef(
        name="ci_add_marked_requirement",
        category=ClauseCategory.confidentiality_definition,
        find_text="otherwise obtained by the Receiving Party from the Disclosing Party",
        replace_text="otherwise obtained by the Receiving Party from the Disclosing Party and expressly designated as confidential in writing at the time of disclosure",
        expected_diff_type="addition",
        description="Add written marking requirement for all CI",
        find_text_alternatives=(
            "disclosed by or on behalf of Discloser to Recipient",
            "disclosed by one party to the other",
        ),
    ),
    MutationDef(
        name="ci_remove_exclusions",
        category=ClauseCategory.confidentiality_definition,
        find_text="Confidential Information does not include information that the Receiving Party can demonstrate by written records:",
        replace_text="Confidential Information does not include information that the Receiving Party can demonstrate by clear and convincing evidence:",
        expected_diff_type="equivalent",
        description="Change exclusion standard from written records to clear and convincing evidence",
        find_text_alternatives=(
            "Recipient's obligations in this NDA do not apply to information that it can document:",
            "Confidential Information does not include information that",
        ),
    ),
    MutationDef(
        name="ci_add_oral_info",
        category=ClauseCategory.confidentiality_definition,
        find_text="in any form, disclosed by or on behalf of the Disclosing Party",
        replace_text="in any form, including oral, visual, or written, disclosed by or on behalf of the Disclosing Party",
        expected_diff_type="addition",
        description="Explicitly include oral and visual information",
        find_text_alternatives=("in any form, which", "in any form or medium"),
    ),
    MutationDef(
        name="ci_shorter_exclusion_period",
        category=ClauseCategory.confidentiality_definition,
        find_text="is or becomes generally available to the public through no fault of the Receiving Party",
        replace_text="is or becomes generally available to the public (other than as a result of a breach of this Agreement by the Receiving Party)",
        expected_diff_type="equivalent",
        description="Clarify public availability exclusion excludes breach-caused public disclosure",
        find_text_alternatives=(
            "is or becomes publicly available through no fault",
            "is or becomes public knowledge through no fault",
        ),
    ),
    MutationDef(
        name="ci_remove_independent_development",
        category=ClauseCategory.confidentiality_definition,
        find_text="(d) is independently developed by the Receiving Party without use of or reference to the Disclosing Party's Confidential Information",
        replace_text="",
        expected_diff_type="contradiction",
        description="Remove independent development exclusion entirely",
        find_text_alternatives=(
            "(d) it independently developed without using or referencing Confidential Information",
            "(d) is independently developed by the receiving party",
        ),
    ),
    MutationDef(
        name="ci_add_personal_data",
        category=ClauseCategory.confidentiality_definition,
        find_text="trade secrets, and know-how",
        replace_text="trade secrets, know-how, and personal data as defined under applicable data protection laws",
        expected_diff_type="addition",
        description="Include personal data in CI definition",
        find_text_alternatives=("inventions or know-how", "pricing, and trade secrets"),
    ),
]

EXCLUSIONS_EXTRA: list[MutationDef] = [
    MutationDef(
        name="excl_remove_third_party_exclusion",
        category=ClauseCategory.exclusions,
        find_text="third party without restriction",
        replace_text="third party without restriction, provided that Recipient has no knowledge that such third party disclosed the information in breach of a confidentiality obligation",
        expected_diff_type="contradiction",
        description="Qualify third party exclusion - recipient must not know of breach",
        find_text_alternatives=(
            "third party without confidentiality",
            "third party without restriction",
        ),
    ),
]

EXCLUSIONS_MUTATIONS: list[MutationDef] = [
    MutationDef(
        name="excl_add_compelled_disclosure",
        category=ClauseCategory.exclusions,
        find_text="lawfully disclosed to the Receiving Party by a third party without restriction on disclosure",
        replace_text="lawfully disclosed to the Receiving Party by a third party without restriction on disclosure; or (e) is required to be disclosed by applicable law, regulation, or court order",
        expected_diff_type="addition",
        description="Add compelled disclosure as an exclusion",
        find_text_alternatives=(
            "lawfully receives from a third party without confidentiality restrictions",
            "rightfully received from a third party without confidentiality restrictions",
        ),
    ),
    MutationDef(
        name="excl_raise_burden",
        category=ClauseCategory.exclusions,
        find_text="demonstrate by competent evidence",
        replace_text="demonstrate by written documentary evidence",
        expected_diff_type="equivalent",
        description="Raise burden of proof for exclusions from competent evidence to written evidence",
        find_text_alternatives=("document:", "prove:", "show:"),
    ),
    MutationDef(
        name="excl_remove_prior_knowledge",
        category=ClauseCategory.exclusions,
        find_text="(b) was in the Receiving Party's lawful possession prior to disclosure and was not obtained directly or indirectly from the Disclosing Party;",
        replace_text="",
        expected_diff_type="contradiction",
        description="Remove prior knowledge exclusion",
        find_text_alternatives=(
            "rightfully knew or possessed prior to receipt",
            "was known to the receiving party before disclosure",
            "was already known",
        ),
    ),
    MutationDef(
        name="excl_add_reverse_engineering",
        category=ClauseCategory.exclusions,
        find_text="(d) is independently developed by the Receiving Party without use of or reference to any Confidential Information of the Disclosing Party",
        replace_text="(d) is independently developed by the Receiving Party without use of or reference to any Confidential Information of the Disclosing Party; or (e) is reverse engineered from products or services made available by the Disclosing Party",
        expected_diff_type="contradiction",
        description="Add reverse engineering as an exclusion (party-friendly)",
        find_text_alternatives=(
            "independently developed without using or referencing Confidential Information",
            "independently developed by the receiving party",
        ),
    ),
]

TERM_MUTATIONS_EXTRA: list[MutationDef] = [
    MutationDef(
        name="term_3yr_to_perpetual",
        category=ClauseCategory.term,
        find_text="three (3) years",
        replace_text="perpetual, continuing indefinitely until terminated",
        expected_diff_type="contradiction",
        description="Change NDA term from 3 years to perpetual",
        find_text_alternatives=("3 years", "two (2) years", "for three"),
    ),
]

TERM_MUTATIONS: list[MutationDef] = [
    MutationDef(
        name="term_3yr_to_5yr",
        category=ClauseCategory.term,
        find_text="three (3) years",
        replace_text="five (5) years",
        expected_diff_type="contradiction",
        description="Extend NDA term from 3 to 5 years",
        find_text_alternatives=("3 years", "two (2) years", "2 years"),
    ),
    MutationDef(
        name="term_3yr_to_1yr",
        category=ClauseCategory.term,
        find_text="three (3) years",
        replace_text="one (1) year",
        expected_diff_type="contradiction",
        description="Shorten NDA term from 3 to 1 year",
        find_text_alternatives=("3 years", "two (2) years", "2 years"),
    ),
    MutationDef(
        name="term_survival_5yr_to_2yr",
        category=ClauseCategory.term,
        find_text="five (5) years from the date of disclosure",
        replace_text="two (2) years from the date of disclosure",
        expected_diff_type="contradiction",
        description="Shorten confidentiality survival from 5 to 2 years",
        find_text_alternatives=("five (5) years", "5 years", "survive for three (3) years"),
    ),
    MutationDef(
        name="term_survival_5yr_to_perpetual",
        category=ClauseCategory.term,
        find_text="five (5) years from the date of disclosure of such Confidential Information",
        replace_text="the duration of any applicable trade secret protection and three (3) years after disclosure for all other Confidential Information",
        expected_diff_type="addition",
        description="Change survival to perpetual for trade secrets",
        find_text_alternatives=("five (5) years", "survive for three (3) years"),
    ),
    MutationDef(
        name="term_add_automatic_renewal",
        category=ClauseCategory.term,
        find_text="Either party may terminate this Agreement upon thirty (30) days' written notice to the other party.",
        replace_text="This Agreement shall automatically renew for successive one (1) year periods unless either party provides written notice of non-renewal at least sixty (60) days prior to the end of the then-current term.",
        expected_diff_type="addition",
        description="Add automatic renewal provision",
        find_text_alternatives=(
            "Either party may terminate this NDA for any or no reason upon notice",
            "Either party may end this Agreement",
            "Either party may terminate this Agreement",
        ),
    ),
    MutationDef(
        name="term_remove_early_termination",
        category=ClauseCategory.term,
        find_text="Either party may terminate this Agreement upon thirty (30) days' written notice to the other party.",
        replace_text="This Agreement may not be terminated prior to its expiration except by mutual written agreement of the parties.",
        expected_diff_type="contradiction",
        description="Remove unilateral termination right",
        find_text_alternatives=(
            "Either party may terminate this NDA for any or no reason upon notice",
            "Either party may end this Agreement",
            "Either party may terminate this Agreement",
        ),
    ),
]

RETURN_MUTATIONS: list[MutationDef] = [
    MutationDef(
        name="return_add_audit_right",
        category=ClauseCategory.return_obligations,
        find_text="The Receiving Party shall provide written certification of such return or destruction upon the Disclosing Party's request.",
        replace_text="The Receiving Party shall provide written certification of such return or destruction upon the Disclosing Party's request. The Disclosing Party shall have the right to audit the Receiving Party's compliance with this Section upon reasonable notice and during normal business hours.",
        expected_diff_type="addition",
        description="Add audit right to verify return/destruction compliance",
        find_text_alternatives=(
            "confirm its compliance with these obligations in writing",
            "shall be provided if requested",
            "must certify this in writing",
        ),
    ),
    MutationDef(
        name="return_no_retention",
        category=ClauseCategory.return_obligations,
        find_text="the Receiving Party may retain copies of Confidential Information as required by law or its bona fide document retention policies",
        replace_text="the Receiving Party shall not retain any copies of Confidential Information for any reason, except as required by applicable law",
        expected_diff_type="contradiction",
        description="Remove document retention policy exception",
        find_text_alternatives=(
            "Retention of Confidential Information",
            "retain Confidential Information",
            "may retain copies",
        ),
    ),
    MutationDef(
        name="return_certification_deadline",
        category=ClauseCategory.return_obligations,
        find_text="promptly cease all use of the Confidential Information and shall either return to the Disclosing Party or destroy all copies",
        replace_text="within fifteen (15) business days, cease all use of the Confidential Information and shall either return to the Disclosing Party or destroy all copies",
        expected_diff_type="addition",
        description="Add specific deadline for return/destruction",
        find_text_alternatives=(
            "cease using Confidential Information",
            "return or destroy all Confidential Information",
            "stop using the Confidential Information",
        ),
    ),
    MutationDef(
        name="return_add_destruction_cert",
        category=ClauseCategory.return_obligations,
        find_text="provide written certification of such return or destruction upon the Disclosing Party's request",
        replace_text="provide a signed written certification within five (5) business days confirming such return or destruction, signed by an officer of the Receiving Party",
        expected_diff_type="addition",
        description="Strengthen certification requirement with officer signature",
        find_text_alternatives=(
            "certification of compliance",
            "confirm its compliance",
            "certify this in writing",
        ),
    ),
]

PERMITTED_DISCLOSURES_MUTATIONS: list[MutationDef] = [
    MutationDef(
        name="pd_narrow_representatives",
        category=ClauseCategory.permitted_disclosures,
        find_text="employees, officers, directors, agents, advisors, and contractors who need to know such information for the Purpose",
        replace_text="employees and contractors who have a specific need to know such information for the Purpose and who have signed a written confidentiality agreement",
        expected_diff_type="contradiction",
        description="Narrow permitted recipients to employees and contractors only",
        find_text_alternatives=(
            "employees, agents, advisors, contractors and other representatives",
            "employees and advisors with a need to know",
            "employees, directors, and professional advisors",
        ),
    ),
    MutationDef(
        name="pd_no_legal_advisor_carveout",
        category=ClauseCategory.permitted_disclosures,
        find_text="(c) to its legal and financial advisors in connection with the Purpose.",
        replace_text="",
        expected_diff_type="contradiction",
        description="Remove legal/financial advisor disclosure carveout",
        find_text_alternatives=(
            "legal and financial advisors",
            "professional advisors",
            "advisors",
        ),
    ),
    MutationDef(
        name="pd_add_investors",
        category=ClauseCategory.permitted_disclosures,
        find_text="(c) to its legal and financial advisors in connection with the Purpose",
        replace_text="(c) to its legal, financial, and insurance advisors in connection with the Purpose; and (d) to actual or potential investors, acquirers, or lenders in connection with a financing or transaction",
        expected_diff_type="addition",
        description="Add investor disclosure rights",
        find_text_alternatives=("professional advisors", "successors in interest"),
    ),
    MutationDef(
        name="pd_strict_notice_requirement",
        category=ClauseCategory.permitted_disclosures,
        find_text="gives the Disclosing Party prompt notice of such required disclosure (to the extent permitted by law) and reasonably cooperates",
        replace_text="gives the Disclosing Party prompt notice of such required disclosure (to the extent permitted by law), reasonably cooperates, and does not disclose any Confidential Information until the Disclosing Party has had a reasonable opportunity to seek a protective order",
        expected_diff_type="addition",
        description="Add waiting period before compelled disclosure",
        find_text_alternatives=(
            "provides Discloser reasonable advance notice",
            "prompt notice to the disclosing party",
            "advance notice to the Disclosing Party",
        ),
    ),
]

GOVERNING_LAW_MUTATIONS: list[MutationDef] = [
    MutationDef(
        name="gl_delaware_to_newyork",
        category=ClauseCategory.governing_law,
        find_text="laws of the State of Delaware",
        replace_text="laws of the State of New York",
        expected_diff_type="contradiction",
        description="Change governing law from Delaware to New York",
        find_text_alternatives=("State of Delaware", "laws of the State of Delaware govern"),
    ),
    MutationDef(
        name="gl_delaware_to_uk",
        category=ClauseCategory.governing_law,
        find_text="laws of the State of Delaware",
        replace_text="laws of England and Wales",
        expected_diff_type="contradiction",
        description="Change governing law from Delaware to England and Wales",
        find_text_alternatives=("State of Delaware", "laws of the State of Delaware govern"),
    ),
    MutationDef(
        name="gl_delaware_to_california",
        category=ClauseCategory.governing_law,
        find_text="laws of the State of Delaware",
        replace_text="laws of the State of California",
        expected_diff_type="contradiction",
        description="Change governing law from Delaware to California",
        find_text_alternatives=("State of Delaware", "laws of the State of Delaware govern"),
    ),
    MutationDef(
        name="gl_delaware_to_ontario",
        category=ClauseCategory.governing_law,
        find_text="laws of the State of Delaware",
        replace_text="laws of the Province of Ontario",
        expected_diff_type="contradiction",
        description="Change governing law from Delaware to Ontario, Canada",
        find_text_alternatives=("State of Delaware", "laws of the State of Delaware govern"),
    ),
    MutationDef(
        name="gl_add_arbitration_clause",
        category=ClauseCategory.governing_law,
        find_text="The United Nations Convention on Contracts for the International Sale of Goods shall not apply to this Agreement.",
        replace_text="The United Nations Convention on Contracts for the International Sale of Goods shall not apply to this Agreement. Any dispute arising out of or relating to this Agreement shall be finally settled by arbitration administered by the American Arbitration Association under its Commercial Arbitration Rules.",
        expected_diff_type="addition",
        description="Add arbitration clause alongside governing law",
        find_text_alternatives=(
            "CISG does not apply",
            "Convention on Contracts for the International Sale of Goods",
        ),
    ),
]

JURISDICTION_MUTATIONS: list[MutationDef] = [
    MutationDef(
        name="jur_delaware_to_southern_ny",
        category=ClauseCategory.jurisdiction,
        find_text="state and federal courts located in Delaware",
        replace_text="state and federal courts located in the Southern District of New York",
        expected_diff_type="contradiction",
        description="Change exclusive venue from Delaware to SDNY",
    ),
    MutationDef(
        name="jur_non_exclusive",
        category=ClauseCategory.jurisdiction,
        find_text="brought exclusively in the state and federal courts located in Delaware",
        replace_text="brought in the state and federal courts located in Delaware, and each party submits to the non-exclusive jurisdiction of such courts",
        expected_diff_type="contradiction",
        description="Change exclusive to non-exclusive jurisdiction",
    ),
    MutationDef(
        name="jur_add_waiver_jury",
        category=ClauseCategory.jurisdiction,
        find_text="waives any objection based on improper venue or forum non conveniens",
        replace_text="waives any objection based on improper venue or forum non conveniens. EACH PARTY IRREVOCABLY WAIVES ANY RIGHT TO TRIAL BY JURY IN ANY LEGAL PROCEEDING ARISING OUT OF THIS AGREEMENT",
        expected_diff_type="addition",
        description="Add jury trial waiver",
    ),
    MutationDef(
        name="jur_add_icc",
        category=ClauseCategory.jurisdiction,
        find_text="Each party consents to the personal jurisdiction and venue of such courts",
        replace_text="Each party consents to the personal jurisdiction and venue of such courts. The parties expressly exclude the application of the Convention on Contracts for the International Sale of Goods",
        expected_diff_type="equivalent",
        description="Add CISG exclusion to jurisdiction clause",
    ),
]

REMEDIES_MUTATIONS: list[MutationDef] = [
    MutationDef(
        name="rem_add_liquidated_damages",
        category=ClauseCategory.remedies,
        find_text="obtain injunctive relief and any other equitable remedies available to it without the necessity of posting a bond",
        replace_text="obtain injunctive relief and any other equitable remedies available to it without the necessity of posting a bond. In addition, the Disclosing Party shall be entitled to liquidated damages in the amount of $10,000 per breach, which the parties agree is reasonable under the circumstances",
        expected_diff_type="addition",
        description="Add liquidated damages provision",
    ),
    MutationDef(
        name="rem_add_bond_requirement",
        category=ClauseCategory.remedies,
        find_text="without the necessity of posting a bond",
        replace_text="upon posting a bond in an amount to be determined by the court",
        expected_diff_type="contradiction",
        description="Require bond for injunctive relief",
    ),
    MutationDef(
        name="rem_add_limitation",
        category=ClauseCategory.remedies,
        find_text="Such remedies shall be in addition to any other remedies available at law or equity.",
        replace_text="Notwithstanding the foregoing, in no event shall either party be liable for any indirect, incidental, special, consequential, or punitive damages arising out of or relating to this Agreement.",
        expected_diff_type="contradiction",
        description="Add limitation of liability excluding consequential damages",
    ),
    MutationDef(
        name="rem_add_cap",
        category=ClauseCategory.remedies,
        find_text="Such remedies shall be in addition to any other remedies available at law or equity.",
        replace_text="The Disclosing Party's aggregate liability under this Agreement shall not exceed $100,000. Such remedies shall be in addition to any other remedies available at law or equity.",
        expected_diff_type="addition",
        description="Add liability cap of $100,000",
    ),
]

ASSIGNMENT_MUTATIONS: list[MutationDef] = [
    MutationDef(
        name="ass_no_consent_needed",
        category=ClauseCategory.assignment,
        find_text="without the prior written consent of the other party, except that either party may assign this Agreement in connection with a merger, acquisition, sale of all or substantially all of its assets, or other corporate reorganization",
        replace_text="without prior written consent of the other party provided that the assignee agrees in writing to be bound by the terms of this Agreement",
        expected_diff_type="contradiction",
        description="Change to consent-based assignment with assignee agreement",
    ),
    MutationDef(
        name="ass_add_change_of_control",
        category=ClauseCategory.assignment,
        find_text="sale of all or substantially all of its assets, or other corporate reorganization",
        replace_text="sale of all or substantially all of its assets, change of control, or other corporate reorganization",
        expected_diff_type="addition",
        description="Include change of control as permitted assignment trigger",
    ),
    MutationDef(
        name="ass_restrictive",
        category=ClauseCategory.assignment,
        find_text="Neither party may assign this Agreement or any of its rights or obligations hereunder without the prior written consent of the other party, except that either party may assign this Agreement in connection with a merger, acquisition",
        replace_text="Neither party may assign this Agreement or any of its rights or obligations hereunder without the prior written consent of the other party. Any attempted assignment in violation of this Section shall be void.",
        expected_diff_type="contradiction",
        description="Remove merger exception - no assignment without consent",
    ),
    MutationDef(
        name="ass_add_notice",
        category=ClauseCategory.assignment,
        find_text="in connection with a merger, acquisition, sale of all or substantially all of its assets, or other corporate reorganization",
        replace_text="in connection with a merger, acquisition, sale of all or substantially all of its assets, or other corporate reorganization, provided that the assigning party provides the non-assigning party with at least thirty (30) days' prior written notice",
        expected_diff_type="addition",
        description="Add advance notice requirement for permitted assignment",
    ),
]

JURISDICTION_MUTATIONS_EXTRA: list[MutationDef] = [
    MutationDef(
        name="jur_change_venue_california",
        category=ClauseCategory.jurisdiction,
        find_text="Delaware",
        replace_text="California",
        expected_diff_type="contradiction",
        description="Change venue from Delaware to California",
        find_text_alternatives=("courts located in Delaware", "courts in Delaware"),
    ),
    MutationDef(
        name="jur_add_mediation",
        category=ClauseCategory.jurisdiction,
        find_text="waives any objection based on improper venue or forum non conveniens",
        replace_text="The parties shall first attempt to resolve any dispute through mediation administered by JAMS before resorting to litigation. Each party waives any objection based on improper venue or forum non conveniens",
        expected_diff_type="addition",
        description="Add mediation requirement before litigation",
        find_text_alternatives=("submits to the personal jurisdiction", "Each party submits to"),
    ),
]

REMEDIES_MUTATIONS_EXTRA: list[MutationDef] = [
    MutationDef(
        name="rem_add_specific_performance",
        category=ClauseCategory.remedies,
        find_text="injunctive relief",
        replace_text="specific performance, injunctive relief",
        expected_diff_type="addition",
        description="Add specific performance as an available remedy",
        find_text_alternatives=("injunction", "seek injunctive"),
    ),
    MutationDef(
        name="rem_add_indemnification",
        category=ClauseCategory.remedies,
        find_text="without the necessity of posting a bond",
        replace_text="without the necessity of posting a bond. Recipient shall indemnify and hold harmless Discloser from all losses arising from any breach of this Agreement",
        expected_diff_type="addition",
        description="Add indemnification for breach",
        find_text_alternatives=("posting a bond", "bond is not required"),
    ),
]

RETURN_MUTATIONS_EXTRA: list[MutationDef] = [
    MutationDef(
        name="return_add_destruction_deadline_30day",
        category=ClauseCategory.return_obligations,
        find_text="promptly",
        replace_text="within thirty (30) days",
        expected_diff_type="addition",
        description="Change promptly to specific 30-day deadline",
        find_text_alternatives=("prompt", "promptly"),
    ),
    MutationDef(
        name="return_add_irretrievable_deletion",
        category=ClauseCategory.return_obligations,
        find_text="return to the Disclosing Party or destroy all copies of the Confidential Information",
        replace_text="irretrievably delete or destroy all copies of the Confidential Information and provide a certificate of deletion signed by an authorized officer",
        expected_diff_type="addition",
        description="Add irretrievable deletion requirement with officer certification",
        find_text_alternatives=("return or destroy all copies", "return or destroy"),
    ),
]

ASSIGNMENT_MUTATIONS_EXTRA: list[MutationDef] = [
    MutationDef(
        name="ass_add_assignee_consent",
        category=ClauseCategory.assignment,
        find_text="Neither party may assign this Agreement without the prior written consent of the other party",
        replace_text="Neither party may assign this Agreement or any rights or obligations hereunder without the prior written consent of the other party, and any assignee must agree in writing to be bound by this Agreement",
        expected_diff_type="addition",
        description="Add requirement for assignee to agree in writing",
        find_text_alternatives=("Neither party may assign", "Neither party may transfer"),
    ),
]

SURVIVAL_MUTATIONS: list[MutationDef] = [
    MutationDef(
        name="surv_add_general_survival",
        category=ClauseCategory.survival,
        find_text="This Agreement constitutes the entire agreement between the parties",
        replace_text="Sections 2 (Confidential Information), 5 (Return of Materials), and 8 (Remedies) shall survive the termination of this Agreement. This Agreement constitutes the entire agreement between the parties",
        expected_diff_type="addition",
        description="Add explicit survival clause for key provisions",
    ),
    MutationDef(
        name="surv_add_trade_secret_perpetual",
        category=ClauseCategory.survival,
        find_text="The failure of either party to enforce any provision of this Agreement shall not be deemed a waiver",
        replace_text="Obligations with respect to trade secrets shall survive indefinitely. The failure of either party to enforce any provision of this Agreement shall not be deemed a waiver",
        expected_diff_type="addition",
        description="Add perpetual survival for trade secrets",
    ),
    MutationDef(
        name="surv_add_audit_survival",
        category=ClauseCategory.survival,
        find_text="This Agreement may not be amended except by a written instrument signed by both parties.",
        replace_text="This Agreement may not be amended except by a written instrument signed by both parties. The audit and inspection rights set forth in this Agreement shall survive for a period of two (2) years after the termination of this Agreement.",
        expected_diff_type="addition",
        description="Add survival of audit rights after termination",
    ),
    MutationDef(
        name="surv_add_one_year_claims",
        category=ClauseCategory.survival,
        find_text="If any provision of this Agreement is held to be invalid or unenforceable, the remaining provisions shall continue in full force and effect.",
        replace_text="No action arising out of or relating to this Agreement may be brought by either party more than one (1) year after the cause of action accrues. If any provision of this Agreement is held to be invalid or unenforceable, the remaining provisions shall continue in full force and effect.",
        expected_diff_type="addition",
        description="Add one-year statute of limitations for claims",
    ),
]

OBLIGATIONS_MUTATIONS_EXTRA: list[MutationDef] = [
    MutationDef(
        name="obl_add_employee_training",
        category=ClauseCategory.obligations,
        find_text="limit access to",
        replace_text="provide regular training on confidentiality obligations to all personnel with access to Confidential Information, and limit access to",
        expected_diff_type="addition",
        description="Add employee training requirement",
        find_text_alternatives=("restrict access to", "limit access to"),
    ),
    MutationDef(
        name="obl_add_encryption_requirement",
        category=ClauseCategory.obligations,
        find_text="reasonable standard of care",
        replace_text="industry-standard safeguards including encryption of data at rest and in transit, and a reasonable standard of care",
        expected_diff_type="addition",
        description="Add encryption requirement as minimum safeguard",
        find_text_alternatives=("reasonable care", "reasonable standard of care"),
    ),
]

OBLIGATIONS_MUTATIONS: list[MutationDef] = [
    MutationDef(
        name="obl_reasonable_to_best_efforts",
        category=ClauseCategory.obligations,
        find_text="less than a reasonable standard of care",
        replace_text="less than a high standard of care, and in no event less than best efforts",
        expected_diff_type="contradiction",
        description="Raise protection standard from reasonable care to best efforts",
    ),
    MutationDef(
        name="obl_add_data_protection",
        category=ClauseCategory.obligations,
        find_text="promptly notify the Disclosing Party upon discovery of any unauthorized disclosure or use of the Confidential Information",
        replace_text="promptly notify the Disclosing Party upon discovery of any unauthorized disclosure or use of the Confidential Information, and comply with all applicable data protection laws in its handling of such information",
        expected_diff_type="addition",
        description="Add data protection law compliance obligation",
    ),
    MutationDef(
        name="obl_add_breach_notification",
        category=ClauseCategory.obligations,
        find_text="promptly notify the Disclosing Party upon discovery of any unauthorized disclosure or use of the Confidential Information",
        replace_text="promptly notify the Disclosing Party within twenty-four (24) hours of discovery of any unauthorized disclosure or use of the Confidential Information, and provide a detailed remediation plan within five (5) business days",
        expected_diff_type="addition",
        description="Add strict breach notification timeline and remediation plan",
    ),
    MutationDef(
        name="obl_restrict_sublicensing",
        category=ClauseCategory.obligations,
        find_text="limit access to the Confidential Information to those of its employees, agents, and contractors who have a need to know",
        replace_text="limit access to the Confidential Information to its employees who have a specific need to know and who have signed individual non-disclosure agreements directly with the Disclosing Party",
        expected_diff_type="contradiction",
        description="Restrict access to employees only with individual NDAs",
    ),
]

ALL_MUTATIONS: list[MutationDef] = (
    CONFIDENTIALITY_MUTATIONS
    + EXCLUSIONS_MUTATIONS
    + EXCLUSIONS_EXTRA
    + TERM_MUTATIONS
    + TERM_MUTATIONS_EXTRA
    + RETURN_MUTATIONS
    + RETURN_MUTATIONS_EXTRA
    + PERMITTED_DISCLOSURES_MUTATIONS
    + GOVERNING_LAW_MUTATIONS
    + JURISDICTION_MUTATIONS
    + JURISDICTION_MUTATIONS_EXTRA
    + REMEDIES_MUTATIONS
    + REMEDIES_MUTATIONS_EXTRA
    + ASSIGNMENT_MUTATIONS
    + ASSIGNMENT_MUTATIONS_EXTRA
    + SURVIVAL_MUTATIONS
    + OBLIGATIONS_MUTATIONS
    + OBLIGATIONS_MUTATIONS_EXTRA
)

CLAUSE_CATEGORIES: set[ClauseCategory] = {m.category for m in ALL_MUTATIONS}
