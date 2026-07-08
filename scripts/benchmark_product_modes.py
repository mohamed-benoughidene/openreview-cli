"""Accuracy benchmark for 6 new product modes (Phase 10 / T077).

Measures pipeline/oracle accuracy: generates synthetic PDFs per mode,
runs ``run_review()`` with a deterministic monkeypatched AI gateway,
and reports recall, processing time, and peak memory.

Usage:
    uv run python scripts/benchmark_product_modes.py
"""

from __future__ import annotations

import gc
import json
import re
import time
import tracemalloc
from pathlib import Path
from typing import Any

import fitz

from openreview_cli.review.playbook import BUNDLED_PLAYBOOKS

FIXTURES = Path("tests/fixtures/benchmark")
REPORTS_DIR = Path(".benchmark-reports")

# Each mode: playbook ID → list of category IDs
# Category IDs per mode
MODE_CATEGORIES: dict[str, list[str]] = {
    "indemnitycheck": [
        "indemnity-scope",
        "liability-cap",
        "survival-period",
        "defense-obligations",
    ],
    "consultcheck": [
        "sow-specificity",
        "payment-terms",
        "ip-ownership",
        "confidentiality",
        "termination-rights",
    ],
    "workcheck": [
        "worker-classification",
        "ip-ownership",
        "payment-terms",
        "non-compete-restrictions",
        "termination",
    ],
    "loicheck": [
        "binding-provisions",
        "exclusivity-no-shop",
        "breakup-fees",
        "due-diligence-access",
        "expiration",
    ],
    "subcheck": [
        "flow-through",
        "payment-terms",
        "broad-form-indemnity",
        "change-order-process",
        "termination-rights",
    ],
    "settlementcheck": [
        "release-scope",
        "payment-terms-timing",
        "confidentiality-non-disparagement",
        "waiver-unknown-claims",
        "breach-consequences",
    ],
    "licensecheck": [
        "license-grant",
        "auto-renewal",
        "liability-cap",
        "data-deletion",
        "ip-ownership",
        "indemnification",
        "pricing-changes",
        "service-levels",
        "termination-convenience",
    ],
    "leasecheck": [
        "rent-escalation",
        "maintenance-obligations",
        "subletting-assignment",
        "term-length-renewal",
        "operating-expenses",
        "security-deposit",
        "termination-convenience",
        "triple-net",
        "use-restrictions",
    ],
    "privacycheck": [
        "processing-scope",
        "sub-processor-management",
        "breach-notification",
        "retention-deletion",
        "audit-rights",
        "international-transfers",
        "processing-instructions",
        "dpa-termination",
    ],
}


def _clause_text(category_id: str, position: str, idx: int) -> str:
    """Generate clause text containing category name (for match_category) + body."""
    # Prepend category name explicitly so match_category() can find it.
    # e.g. "Indemnity Scope clause body: Each party shall indemnify..."
    cat_name = category_id.replace("-", " ").title()
    bodies: dict[str, list[str]] = {
        "indemnity-scope": [
            "Each party shall indemnify, defend, and hold harmless the other party "
            "from and against any and all third-party claims arising out of or "
            "related to the indemnifying party's breach of this Agreement.",
            "The Company agrees to indemnify the Consultant against any and all "
            "claims, damages, losses, and expenses arising from the Services.",
            "Indemnification obligations under this Section shall be mutual, "
            "with each party indemnifying the other to the same extent.",
            "The Indemnitor shall indemnify the Indemnitee against all losses "
            "arising from third-party claims related to the subject matter hereof.",
            "Notwithstanding anything to the contrary, indemnification shall cover "
            "all claims including those for intellectual property infringement.",
        ],
        "liability-cap": [
            "Notwithstanding anything to the contrary, neither party's aggregate "
            "liability shall exceed the total fees paid under this Agreement.",
            "In no event shall either party be liable for any indirect, special, "
            "incidental, or consequential damages arising out of this Agreement.",
            "Liability Cap. The total liability of either party shall not exceed "
            "the sum of one million dollars ($1,000,000).",
            "Each party's maximum aggregate liability for all claims shall be "
            "limited to three times the fees paid during the preceding twelve months.",
            "No party shall be liable for any loss of profits, loss of business, "
            "or interruption of business under any theory of liability.",
        ],
        "survival-period": [
            "The representations and warranties contained in this Agreement shall "
            "survive for a period of two (2) years following the termination hereof.",
            "Indemnification obligations set forth in this Agreement shall survive "
            "the termination or expiration of this Agreement indefinitely.",
            "All obligations under this Agreement shall survive for a period of "
            "three (3) years from the date of termination.",
            "Confidentiality obligations shall survive termination of this Agreement "
            "for a period of five (5) years.",
            "Survival. The parties agree that all covenants and agreements contained "
            "herein shall survive for one (1) year after the termination date.",
        ],
        "defense-obligations": [
            "The Indemnitor shall have the right, at its own expense, to assume "
            "the defense of any third-party claim subject to indemnification.",
            "The Indemnitee shall cooperate fully in the defense of any claim, "
            "including making available relevant records and personnel.",
            "No settlement of a claim subject to indemnification shall be entered "
            "into without the prior written consent of both parties.",
            "The Indemnitor shall defend, at its sole cost and expense, any claim "
            "brought against the Indemnitee that is covered by the indemnity.",
            "Defense Obligations. Upon receipt of notice of a claim, the Indemnitor "
            "shall promptly assume the defense with counsel reasonably acceptable.",
        ],
        "sow-specificity": [
            "The Services to be performed by Consultant are described in detail "
            "in the Statement of Work attached hereto as Exhibit A.",
            "Each SOW shall specify the deliverables, milestones, fees, and "
            "acceptance criteria for the services to be provided.",
            "Consultant agrees to perform the services described in Exhibit A "
            "in a professional and timely manner.",
            "The scope of work shall be defined in a written SOW signed by both "
            "parties prior to the commencement of any services.",
            "Changes to the scope of services shall be documented in a written "
            "change order executed by both parties.",
        ],
        "payment-terms": [
            "Consultant shall submit monthly invoices for services rendered, and "
            "Client shall pay all undisputed amounts within thirty (30) days.",
            "All invoices are due and payable within thirty (30) days of the date "
            "of invoice. Late payments shall accrue interest at 1.5% per month.",
            "Consultant shall be compensated at the hourly rate of $150 for all "
            "services performed under this Agreement.",
            "Client agrees to reimburse Consultant for all reasonable out-of-pocket "
            "expenses incurred in connection with the Services.",
            "Payment Terms. Consultant shall invoice Client monthly and payment "
            "shall be made within forty-five (45) days of receipt of invoice.",
        ],
        "ip-ownership": [
            "All work product and deliverables created by Consultant shall be "
            "owned exclusively by Client as works made for hire.",
            "Consultant retains all right, title, and interest in and to its "
            "pre-existing materials and grants Client a perpetual license.",
            "Consultant's tools, methodologies, and know-how shall remain the "
            "sole and exclusive property of Consultant.",
            "IP Ownership. Consultant hereby assigns to Client all rights in "
            "all work product created under this Agreement.",
            "Ownership of all intellectual property arising from the Services "
            "shall vest in Client upon full payment of all fees due.",
        ],
        "confidentiality": [
            "Both parties agree to hold each other's Confidential Information in "
            "strict confidence and not to disclose it to third parties.",
            "Confidential Information shall not include information that is or "
            "becomes publicly available through no fault of the receiving party.",
            "Each party may disclose Confidential Information to its employees "
            "and advisors on a need-to-know basis for the purposes of this Agreement.",
            "Confidentiality obligations set forth herein shall survive termination "
            "of this Agreement for a period of three (3) years.",
            "The receiving party shall use the disclosing party's Confidential "
            "Information solely for the purposes of performing its obligations.",
        ],
        "termination-rights": [
            "Either party may terminate this Agreement at any time upon thirty "
            "(30) days prior written notice to the other party.",
            "This Agreement may be terminated by either party for material breach "
            "if the breaching party fails to cure within thirty (30) days of notice.",
            "Upon termination, Consultant shall be entitled to payment for all "
            "services performed through the effective date of termination.",
            "Termination for convenience shall not affect the parties' rights "
            "and obligations that have accrued prior to the termination date.",
            "Consultant shall return all Client materials and Confidential "
            "Information upon termination or expiration of this Agreement.",
        ],
        "worker-classification": [
            "Consultant is an independent contractor and not an employee of Client "
            "for any purpose, including tax withholding and benefits.",
            "Consultant retains sole discretion over the manner, method, and means "
            "of performing all services under this Agreement.",
            "Consultant may perform services for other clients and is not required "
            "to devote full time or attention to Client's projects.",
            "Consultant shall provide all equipment, tools, and materials necessary "
            "to perform the services at Consultant's own expense.",
            "Classification. The parties expressly agree that Consultant is an "
            "independent contractor and not an employee of Client.",
        ],
        "non-compete-restrictions": [
            "Consultant agrees that during the term and for twelve (12) months "
            "thereafter, Consultant shall not provide services to direct competitors.",
            "Consultant shall not solicit or attempt to solicit any employee of "
            "Client for a period of twelve (12) months after termination.",
            "The non-compete obligations set forth herein shall apply only to "
            "the specific geographic region where Consultant provided services.",
            "Consultant is free to provide services to any other client and is "
            "not restricted from working in the same industry generally.",
            "Non-Compete. Consultant agrees not to work for any client of Client "
            "for a period of six (6) months following termination of this Agreement.",
        ],
        "termination": [
            "Either party may terminate this Agreement for any reason upon "
            "fourteen (14) days' written notice to the other party.",
            "Termination for Cause. Either party may terminate this Agreement "
            "immediately upon written notice if the other party breaches.",
            "Upon termination, Consultant shall be paid for all services performed "
            "through the effective date of termination.",
            "Consultant shall return or destroy all Client property and "
            "Confidential Information upon termination of this Agreement.",
            "The provisions of this Agreement that by their nature should survive "
            "termination shall survive, including confidentiality and IP ownership.",
        ],
        "binding-provisions": [
            "This Letter of Intent is intended to be non-binding except for the "
            "provisions relating to confidentiality and exclusivity.",
            "Only Sections 3 (Confidentiality) and 4 (Exclusivity) of this LOI "
            "shall create legally binding obligations between the parties.",
            "No binding agreement shall exist between the parties until the "
            "execution of a definitive agreement incorporating these terms.",
            "The parties agree to negotiate in good faith, but this LOI does not "
            "create any legally binding obligation to consummate a transaction.",
            "This LOI sets forth the current understanding of the parties and is "
            "not intended to be a legally binding agreement.",
        ],
        "exclusivity-no-shop": [
            "Seller shall not, directly or indirectly, solicit or engage in "
            "discussions with third parties regarding an alternative transaction.",
            "The exclusivity period shall commence on the date hereof and "
            "continue for a period of forty-five (45) days.",
            "Seller may respond to unsolicited acquisition proposals if required "
            "to do so by its fiduciary duties to shareholders.",
            "During the exclusivity period, Seller shall promptly notify Buyer "
            "of any inquiry or offer received from a third party.",
            "Exclusivity. Seller agrees not to shop the Company to third parties "
            "during the term of this LOI.",
        ],
        "breakup-fees": [
            "If the transaction does not close due to Seller's acceptance of a "
            "superior proposal, Seller shall pay Buyer a breakup fee.",
            "Neither party shall be obligated to pay any breakup fee or expense "
            "reimbursement in the event the transaction does not close.",
            "Breakup Fee. In the event this LOI is terminated under specified "
            "circumstances, a breakup fee of 3% of the transaction value applies.",
            "Seller shall reimburse Buyer for its reasonable out-of-pocket "
            "expenses incurred in connection with the proposed transaction.",
            "A reverse breakup fee shall be payable by Buyer to Seller if the "
            "transaction fails due to Buyer's failure to obtain financing.",
        ],
        "due-diligence-access": [
            "Seller shall provide Buyer and its representatives with reasonable "
            "access to the Company's records, facilities, and management.",
            "Buyer shall have a period of sixty (60) days to conduct due "
            "diligence, commencing on the date of this LOI.",
            "Seller shall establish a virtual data room containing all relevant "
            "documents for Buyer's due diligence review.",
            "Access to competitively sensitive information may be limited "
            "subject to appropriate confidentiality protections.",
            "Buyer and its advisors may inspect all books, records, and "
            "facilities of the Company upon reasonable advance notice.",
        ],
        "expiration": [
            "This LOI shall automatically expire on the date that is ninety (90) "
            "days from the date hereof if a definitive agreement is not executed.",
            "Either party may terminate this LOI at any time by providing written "
            "notice to the other party prior to the expiration date.",
            "The parties intend to negotiate and execute a definitive agreement "
            "within sixty (60) days of the date of this LOI.",
            "This LOI shall remain open for acceptance until 5:00 p.m. Eastern "
            "Time on the date specified in Section 1 above.",
            "Expiration. If a definitive agreement is not signed within the "
            "exclusivity period, this LOI shall terminate automatically.",
        ],
        "flow-through": [
            "Subcontractor agrees to be bound by all terms and conditions of the "
            "prime contract that are applicable to the scope of work.",
            "The relevant provisions of the prime contract are attached hereto "
            "as Exhibit A and incorporated by reference.",
            "Subcontractor shall comply with all laws, regulations, and "
            "ordinances applicable to the performance of the work.",
            "Contractor shall provide Subcontractor with copies of all prime "
            "contract modifications that affect the scope of work.",
            "Flow-through. Subcontractor assumes all obligations of Contractor "
            "under the prime contract to the extent they relate to the Work.",
        ],
        "broad-form-indemnity": [
            "Subcontractor shall indemnify and hold harmless Contractor from "
            "any and all claims arising out of Subcontractor's work.",
            "Each party shall indemnify the other for claims arising from its "
            "own negligence or breach of this Agreement.",
            "Subcontractor shall defend Contractor against any claim arising "
            "from Subcontractor's performance at Subcontractor's sole cost.",
            "Indemnity obligations shall be mutual, with each party indemnifying "
            "the other to the extent of its proportionate fault.",
            "Subcontractor's indemnity obligations shall not apply to claims "
            "arising from Contractor's sole negligence or wilful misconduct.",
        ],
        "change-order-process": [
            "Any change to the scope of work, schedule, or contract price shall "
            "be documented in a written change order signed by both parties.",
            "Subcontractor shall not be required to perform any changed work "
            "until a change order has been fully executed.",
            "Changes to the work shall be priced at Subcontractor's then-current "
            "standard rates for the applicable trade.",
            "Oral change directives shall be confirmed in writing within three "
            "(3) business days and documented as a change order.",
            "Change Orders. All changes must be approved in writing by both "
            "parties prior to the commencement of changed work.",
        ],
        "release-scope": [
            "Each party hereby releases the other from any and all claims, "
            "demands, and causes of action arising from the dispute described herein.",
            "This release does not extend to any obligations created by this "
            "Settlement Agreement or to claims that cannot be waived by law.",
            "The release set forth herein is a mutual general release of all "
            "claims known or unknown relating to the subject matter of this dispute.",
            "Claimant releases Respondent from all claims arising from or relating "
            "to the facts alleged in the Complaint.",
            "This release shall be binding upon and inure to the benefit of the "
            "parties and their respective successors and assigns.",
        ],
        "payment-terms-timing": [
            "Respondent shall pay Claimant the sum of Fifty Thousand Dollars "
            "($50,000) within thirty (30) days of the Effective Date.",
            "Payment shall be made by wire transfer of immediately available "
            "funds to the account designated in writing by Claimant.",
            "Late payment of any instalment shall constitute a material breach "
            "and shall accelerate all remaining amounts due.",
            "Respondent shall make six (6) equal monthly payments of Ten Thousand "
            "Dollars ($10,000) commencing on the first day of the month following.",
            "Payment obligations under this Section are subject to Claimant's "
            "execution and delivery of a general release in the form attached.",
        ],
        "confidentiality-non-disparagement": [
            "The parties agree to keep the terms and conditions of this Settlement "
            "Agreement strictly confidential.",
            "Each party agrees not to disparage, defame, or make any negative "
            "statements about the other party.",
            "Confidentiality shall not apply to disclosures required by law or "
            "to disclosures to professional advisors on a need-to-know basis.",
            "Claimant may disclose the terms of this Agreement to immediate "
            "family members and legal and tax advisors.",
            "Non-Disparagement. Neither party shall make any public statements "
            "regarding the facts or circumstances underlying this dispute.",
        ],
        "waiver-unknown-claims": [
            "Each party expressly waives any and all rights under California "
            "Civil Code Section 1542 regarding unknown claims.",
            "The parties acknowledge they have been advised to consult with legal "
            "counsel before executing this Agreement.",
            "This waiver includes claims that are unknown, unanticipated, "
            "or unsuspected by the parties as of the Effective Date.",
            "Claimant acknowledges that it may hereafter discover claims or facts "
            "in addition to those now known and nevertheless waives them.",
            "The waiver of unknown claims is knowing, voluntary, and made with "
            "the advice of legal counsel.",
        ],
        "breach-consequences": [
            "In the event of a material breach of this Agreement by Respondent, "
            "Claimant may seek specific performance or damages.",
            "If Claimant breaches the confidentiality provisions, Respondent "
            "shall be entitled to seek injunctive relief without posting bond.",
            "Breach of any payment obligation shall entitle Claimant to seek "
            "judgment for the full amount due plus interest.",
            "The non-breaching party shall provide thirty (30) days' written "
            "notice and an opportunity to cure before declaring a breach.",
            "Breach Consequences. Any breach of this Agreement by either party "
            "shall entitle the non-breaching party to pursue all available remedies.",
        ],
        # ── LicenseCheck (saas-license-v1) ────────────────────
        "license-grant": [
            "Licensor grants Licensee a perpetual, non-exclusive license to use "
            "the Software for its internal business purposes.",
            "Licensee may use the Software for its internal business operations "
            "subject to the terms and conditions of this Agreement.",
            "Licensor grants a non-exclusive, non-transferable license for the "
            "term of this Agreement, limited to the number of users specified.",
            "Licensee is licensed for the number of users specified in the Order "
            "Form and may use the Software solely for its internal operations.",
            "Licensee may only use the Software in its designated department "
            "and not for any purpose competitive with Licensor.",
        ],
        "auto-renewal": [
            "This Agreement shall auto-renew for successive renewal periods "
            "unless either party provides at least thirty days' notice of non-renewal.",
            "This Agreement shall automatically renew for successive one-year "
            "periods unless either party provides notice of non-renewal.",
            "Either party may provide notice of non-renewal at least sixty days "
            "before the end of the current term.",
            "This Agreement shall automatically renew indefinitely unless Licensee "
            "provides written notice of non-renewal at least ninety days before renewal.",
            "Licensee may not terminate this Agreement before the end of the "
            "initial term, and non-renewal notice must be provided at least sixty days prior.",
        ],
        "data-deletion": [
            "Upon termination, Licensor shall delete all Customer Data within "
            "thirty days and provide a certification of deletion upon request.",
            "Licensee may request an export of its data before deletion, and "
            "Licensor shall comply within a reasonable timeframe.",
            "Upon termination, Licensor shall make Customer Data available for "
            "export for a period of thirty days before deletion.",
            "Either party shall return or destroy the other's Confidential "
            "Information upon request within sixty days of termination.",
            "Licensor has no obligation to delete Customer Data after termination "
            "and may retain data for its legitimate business purposes.",
        ],
        "indemnification": [
            "Each party agrees to indemnify the other for third-party claims "
            "arising from its breach of this Agreement or applicable law.",
            "Licensor shall defend and indemnify Licensee against any third-party "
            "claim that the Software infringes any intellectual property right.",
            "Each party indemnifies the other for claims arising from its "
            "negligence or breach of confidentiality obligations.",
            "Indemnification excludes claims arising from Licensee's modification "
            "or combination of the Software with other products.",
            "Licensee agrees to indemnify Licensor against all third-party claims "
            "arising from Licensee's use of the Software in violation of law.",
        ],
        "pricing-changes": [
            "Fees shall remain fixed during the initial term and any renewal "
            "term, with no unilateral price increases.",
            "Licensor may increase fees on renewal with at least sixty days' "
            "notice, and Licensee may terminate if the increase exceeds ten percent.",
            "If fees increase by more than five percent upon renewal, Licensee "
            "may terminate this Agreement without penalty.",
            "Licensor may increase fees effective the next renewal period with "
            "thirty days' notice, and increases are limited to seven percent annually.",
            "Licensor reserves the right to change fees at any time upon notice, "
            "and usage overage fees may be changed without prior notice.",
        ],
        "service-levels": [
            "Licensor shall maintain uptime of at least 99.9% and provide service "
            "credits for each hour of downtime exceeding the SLA.",
            "Critical issue response time shall be within four hours, and "
            "service credits accrue for extended downtime.",
            "Licensor will use commercially reasonable efforts to maintain 99.5% "
            "uptime, with service credits available for extended downtime.",
            "Support is available during business hours with a twenty-four hour "
            "response time for standard issues.",
            "Licensor provides the Software 'as is' with no uptime guarantee, "
            "and no service level credits are available under any circumstances.",
        ],
        "termination-convenience": [
            "Either party may terminate this Agreement for convenience with thirty "
            "days' notice, and Licensor shall refund any prepaid fees on a pro-rata basis.",
            "Licensee may terminate for convenience at any time with written notice, "
            "and no refund of prepaid fees will be provided.",
            "Either party may terminate this Agreement for any reason with sixty "
            "days' written notice to the other party.",
            "Licensee may terminate for convenience, but no refund of prepaid fees "
            "will be provided, and termination is available after the initial term.",
            "Licensor may terminate this Agreement at any time for convenience, "
            "and Licensee may not terminate before the end of the term.",
        ],
        # ── LeaseCheck (commercial-lease-v1) ──────────────────
        "rent-escalation": [
            "Annual rent increase shall be tied to CPI with a cap of four percent "
            "per year, and no double-escalation shall apply.",
            "Rent shall increase by no more than three percent annually, based "
            "on the Consumer Price Index for the applicable region.",
            "Annual rent increase of three percent per year, compounded annually "
            "on each anniversary of the Commencement Date.",
            "Rent may be adjusted to fair market value at renewal, with the right "
            "for Tenant to contest the adjustment.",
            "Annual rent increase of CPI plus two percent with no cap, or at "
            "Landlord's sole discretion in lieu of CPI.",
        ],
        "maintenance-obligations": [
            "Landlord shall maintain the roof, foundation, structural elements, "
            "and all major building systems at Landlord's sole cost.",
            "Tenant is responsible only for interior non-structural repairs and "
            "routine maintenance within the Premises.",
            "Landlord maintains structural components and common areas; Tenant "
            "maintains the interior of the Premises.",
            "HVAC maintenance is shared between Landlord and Tenant, with "
            "Landlord covering capital replacements.",
            "Tenant shall maintain and repair all portions of the Premises at "
            "its sole cost, including structural and major systems.",
        ],
        "subletting-assignment": [
            "Tenant may sublet the Premises or assign this Lease with Landlord's "
            "consent, not to be unreasonably withheld or delayed.",
            "Tenant may assign this Lease to an affiliate without Landlord's "
            "consent, provided Tenant gives prior written notice.",
            "Tenant may sublet with Landlord's prior written consent, not to be "
            "unreasonably withheld, conditioned, or delayed.",
            "Tenant may sublet with Landlord's consent, and Landlord may recapture "
            "the space if the proposed subtenant is a competitor.",
            "Tenant may not sublet or assign without Landlord's prior written "
            "consent, which may be withheld in Landlord's sole discretion.",
        ],
        "term-length-renewal": [
            "Initial term of five years with two renewal options of five years "
            "each, and Tenant has the right of first refusal on adjacent space.",
            "Initial term of three years with three renewal options of three "
            "years each at the same rent escalation terms.",
            "Initial term of seven years with one five-year renewal option at "
            "fair market rent, renewable by written notice.",
            "Initial term of five years with one renewal option, provided Tenant "
            "gives written notice at least one hundred eighty days before expiration.",
            "Initial term of fifteen years with no renewal options, and renewal "
            "is at Landlord's sole discretion.",
        ],
        "operating-expenses": [
            "Tenant's share of operating expenses is capped at three percent "
            "increase per year, with full audit rights.",
            "Capital improvements and leasing commissions are excluded from "
            "operating expenses, and Tenant may audit expenses annually.",
            "Tenant pays its pro-rata share of operating expenses, which "
            "exclude leasing commissions and legal fees.",
            "Tenant pays its pro-rata share of operating expenses with no cap, "
            "and may audit expenses with reasonable notice.",
            "Tenant shall pay all operating expenses without limitation, and "
            "operating expenses include capital improvements and a management fee.",
        ],
        "security-deposit": [
            "Security deposit equal to two months' base rent, bearing interest "
            "at the rate of two percent per year.",
            "Security deposit of one month's rent, returned within thirty days "
            "of lease expiration with itemized deductions.",
            "Security deposit of three months' Base Rent, returned within "
            "sixty days, less any amounts for damages.",
            "Security deposit of two months' rent, and Landlord shall return "
            "deposit within forty-five days of termination.",
            "Security deposit of six months' rent, and Landlord may commingle "
            "deposit with its own funds with no interest payable.",
        ],
        "triple-net": [
            "Base rent includes all operating expenses, taxes, and insurance. "
            "Tenant's only additional costs are utilities and janitorial.",
            "Tenant pays its pro-rata share of taxes, insurance, and CAM, "
            "with annual increases capped at four percent.",
            "Pass-through expenses exclude capital improvements and management "
            "fees, and annual increases are capped at five percent.",
            "Tenant pays its pro-rata share of taxes, insurance, and CAM, "
            "including capital improvements and structural repairs.",
            "Tenant shall pay all taxes, insurance, maintenance, and capital "
            "improvements with no cap on pass-through expenses.",
        ],
        "use-restrictions": [
            "The Premises may be used for any lawful business purpose, and "
            "no exclusive-use rights granted to other tenants restrict Tenant.",
            "The Premises shall be used for general office purposes, and "
            "Tenant may operate during all hours permitted by law.",
            "The Premises shall be used for general office purposes consistent "
            "with a first-class office building.",
            "The Premises may be used for the specific business type identified "
            "in the Lease, subject to Landlord's reasonable approval.",
            "The Premises may only be used for the specific business type listed "
            "in Section 1.1, and Tenant may not change use without Landlord's consent.",
        ],
        # ── PrivacyCheck (dpa-v1) ─────────────────────────────
        "processing-scope": [
            "Processor shall process Personal Data only for the purposes specified "
            "in Schedule A, limited to the data categories listed therein.",
            "The processing is limited to the following data categories: contact "
            "information, account credentials, and transaction history.",
            "Processor shall process Personal Data to provide the Services under "
            "the Agreement, including customer support and account management.",
            "Processing may include name, email, and usage data for the purposes "
            "of service delivery, billing, and support.",
            "Processor may process Personal Data for any business purpose "
            "related to its operations, as determined by Processor.",
        ],
        "sub-processor-management": [
            "Processor shall obtain Controller's prior written consent before "
            "engaging any sub-processor, and Controller may object within thirty days.",
            "Processor shall maintain an up-to-date list of sub-processors and "
            "notify Controller of any intended changes.",
            "Processor shall notify Controller of any intended sub-processor "
            "changes, and Controller authorizes the sub-processors listed in Schedule B.",
            "Processor shall impose the same data protection obligations on "
            "sub-processors by way of a written contract.",
            "Processor may engage sub-processors without Controller's consent "
            "and is not required to maintain a list of sub-processors.",
        ],
        "breach-notification": [
            "Processor shall notify Controller within forty-eight hours of "
            "becoming aware of a personal data breach.",
            "Notification shall include the nature of the breach, categories "
            "of data affected, and mitigation measures taken.",
            "Processor shall notify Controller without undue delay, and no "
            "later than seventy-two hours after becoming aware of a breach.",
            "Processor shall provide reasonable assistance with breach "
            "investigation and notification to supervisory authorities.",
            "Processor shall notify Controller of a breach within five business "
            "days if Processor determines a breach has occurred.",
        ],
        "retention-deletion": [
            "Processor shall delete all Personal Data within thirty days of "
            "Controller's instruction and provide a certification of deletion.",
            "Controller may request a copy of Personal Data before deletion, "
            "and Processor shall comply within a reasonable timeframe.",
            "Processor shall delete or return Personal Data within ninety days "
            "of termination of the Agreement.",
            "Processor may retain Personal Data for the period required by "
            "applicable law, but not longer than twelve months after termination.",
            "Processor has no obligation to delete Personal Data after termination "
            "and may retain data for its legitimate business purposes.",
        ],
        "audit-rights": [
            "Controller may conduct an audit upon thirty days' notice, no more "
            "than annually, and Processor shall provide access to relevant systems.",
            "Processor shall provide access to all systems, records, and premises "
            "relevant to the processing of Personal Data.",
            "Controller may audit Processor's compliance with this DPA upon "
            "thirty days' notice during business hours.",
            "Audits shall be conducted during business hours and shall not "
            "unreasonably interfere with Processor's operations.",
            "Controller has no right to audit Processor's facilities, and "
            "Processor's SOC 2 report serves as the sole audit mechanism.",
        ],
        "international-transfers": [
            "Transfers shall be governed by the EU Standard Contractual Clauses "
            "Module Two, attached hereto as Schedule C.",
            "Processor shall only transfer Personal Data to countries with an "
            "adequacy decision by the European Commission.",
            "Transfers are governed by the Standard Contractual Clauses attached "
            "as Schedule C, and Processor shall notify of destination changes.",
            "Processor shall ensure that all sub-processors are bound by SCCs "
            "for any international data transfers.",
            "Processor may transfer Personal Data to any jurisdiction without "
            "additional safeguards or restrictions.",
        ],
        "processing-instructions": [
            "Processor shall process Personal Data only on Controller's documented "
            "instructions, and shall inform Controller of any conflicting instruction.",
            "If Processor believes an instruction violates data protection law, "
            "it shall immediately inform Controller and suspend execution.",
            "Processor shall process Personal Data in accordance with the terms "
            "of this Agreement and any additional written instructions.",
            "Any additional processing instructions must be agreed in writing "
            "by both parties before implementation.",
            "Processor may use Personal Data for its own legitimate business "
            "purposes and may deviate from instructions as it deems necessary.",
        ],
        "dpa-termination": [
            "This DPA shall terminate automatically upon termination of the "
            "Master Agreement, and data protection obligations shall survive.",
            "Controller may terminate this DPA if Processor materially breaches "
            "data protection obligations under applicable law.",
            "This DPA forms part of the Master Agreement and terminates with "
            "it, with obligations regarding data deletion surviving for ninety days.",
            "Either party may terminate this DPA on material breach that remains "
            "uncured for thirty days following written notice.",
            "This DPA survives termination of the Master Agreement indefinitely, "
            "and Controller may not terminate for data protection breach.",
        ],
    }
    body = bodies.get(category_id, [f"Standard clause text for {category_id}."])[idx % 5]
    # PONTAIL: marker at START so it's never truncated by page boundary.
    # Include raw category_id so match_category() via cat.id in text works.
    return f"[EXPECTED:{position}] [{category_id}] {cat_name} clause body: {body}"


def _expected_position(category_id: str, idx: int) -> str:
    """Cycle through positions to get coverage of all three."""
    positions = ["preferred", "acceptable", "walkaway", "acceptable", "preferred"]
    return positions[(hash(category_id) + idx) % len(positions)]


def _generate_pdfs() -> dict[str, list[dict[str, Any]]]:
    """Generate 5 synthetic PDFs per mode. Returns {mode: [ground_truth_doc]}."""
    ground_truth: dict[str, list[dict[str, Any]]] = {}

    for mode, categories in MODE_CATEGORIES.items():
        mode_dir = FIXTURES / mode
        mode_dir.mkdir(parents=True, exist_ok=True)
        docs: list[dict[str, Any]] = []

        for doc_idx in range(5):
            pdf_path = mode_dir / f"doc_{doc_idx + 1}.pdf"
            cat_count = len(categories)
            # Each doc covers different categories (cycle through them)
            cats_in_doc = categories[(doc_idx * 2) % cat_count : ((doc_idx * 2) % cat_count) + 2]
            # Pad/reduce to exactly 2 categories per doc for simplicity
            if len(cats_in_doc) < 2:
                cats_in_doc = categories[:2]

            expected_categories: list[dict[str, str]] = []
            doc = fitz.open()

            for ci, cat_id in enumerate(cats_in_doc):
                pos = _expected_position(cat_id, doc_idx + ci)
                text = _clause_text(cat_id, pos, doc_idx + ci)
                page = doc.new_page()
                # Insert twice to ensure text fills enough of the page
                page.insert_text(
                    fitz.Point(50, 50),
                    text,
                    fontsize=11,
                    fontname="helv",
                )
                page.insert_text(
                    fitz.Point(50, 80),
                    text[: len(text) // 2],
                    fontsize=11,
                    fontname="helv",
                )
                expected_categories.append({"category_id": cat_id, "expected_position": pos})

            doc.save(str(pdf_path), garbage=1)
            doc.close()

            docs.append(
                {
                    "path": str(pdf_path),
                    "expected_categories": expected_categories,
                    "doc_index": doc_idx + 1,
                }
            )

        ground_truth[mode] = docs

    return ground_truth


def _save_ground_truth(ground_truth: dict[str, list[dict[str, Any]]]) -> None:
    """Save ground truth JSON per mode."""
    for mode, docs in ground_truth.items():
        gt_path = FIXTURES / mode / "ground_truth.json"
        gt_path.write_text(json.dumps(docs, indent=2))
        print(f"  Wrote {gt_path}")


def _adapt_clauses(raw_clauses: list[Any]) -> list[Any]:
    """Wrap parsing Clause objects (id/text) with clause_id/clause_text attrs."""
    adapted = []
    for c in raw_clauses:
        adapted.append(
            type(
                "_ClauseAdapter",
                (),
                {
                    "clause_id": c.id,
                    "clause_text": c.text,
                    "id": c.id,
                    "text": c.text,
                    "title": c.title,
                    "level": c.level,
                    "parent_id": c.parent_id,
                    "source_page": c.source_page,
                    "source_paragraph": c.source_paragraph,
                    "source_span": c.source_span,
                    "paragraph_count": getattr(c, "paragraph_count", None),
                },
            )()
        )
    return adapted


def _run_doc_pipeline(
    doc_path: str,
    playbook_path: str,
    mode: str,
) -> list[Any] | None:
    """Run full review pipeline for one document with monkeypatched gateway
    and clause adapter. Returns ReviewReport assessments list or None."""
    import asyncio

    # Patch gateway
    import openreview_cli.review._gateway as gw_mod

    def _det_gw(slot: str, messages: list[dict[str, str]]) -> str:
        all_text = " ".join(m.get("content", "") for m in messages)
        m = re.search(r"\[EXPECTED:(\w+)\]", all_text)
        if slot == "extraction" and m:
            pos = m.group(1)
            return json.dumps(
                {
                    "position": pos,
                    "confidence": 0.95,
                    "citation": "Deterministic benchmark response.",
                    "category_match": True,
                }
            )
        return json.dumps(
            {
                "verdict": "agree",
                "revised_position": None,
                "rationale": "QA verification passed.",
                "citation_valid": True,
                "position_valid": True,
                "category_valid": True,
                "confidence_valid": True,
            }
        )

    gw_mod.call_gateway_chat = _det_gw

    # Build pipeline manually — use our own StripStage adapter
    from openreview_cli.pipeline.adapters.parse import ParseStage
    from openreview_cli.pipeline.runner import Pipeline
    from openreview_cli.review.pipeline import ReviewStage
    from openreview_cli.review.playbook import load_playbook

    playbook = load_playbook(Path(playbook_path))
    review_stage = ReviewStage(playbook=playbook, verbose=False, mode=mode)

    pipeline = Pipeline(
        stages=[ParseStage(), review_stage],
        progress_callback=lambda e: None,
    )

    # Monkeypatch ReviewStage.run to adapt clauses before processing.
    # Must do this after Pipeline construction but before running.
    _orig_review_run = review_stage.run

    async def _patched_review_run(ctx: dict[str, Any]) -> dict[str, Any] | None:
        ctx["stripped_clauses"] = _adapt_clauses(ctx.get("clauses", []))
        return await _orig_review_run(ctx)

    review_stage.run = _patched_review_run  # type: ignore[method-assign]

    try:
        asyncio.run(pipeline.run({"document_path": doc_path}))
    except Exception:
        return None

    if review_stage.report is None:
        return None
    return review_stage.report.assessments


def _run_mode_benchmark(mode: str, docs: list[dict[str, Any]]) -> dict[str, Any]:
    """Run benchmark for a single mode over its 5 documents."""
    matched = 0
    total_expected = 0
    total_time = 0.0
    current_peak = 0

    for doc in docs:
        total_expected += len(doc["expected_categories"])

        gc.collect()
        tracemalloc.start()

        t0 = time.perf_counter()
        assessments = _run_doc_pipeline(
            doc_path=doc["path"],
            playbook_path=str(BUNDLED_PLAYBOOKS[mode]),
            mode=mode,
        )
        elapsed = time.perf_counter() - t0
        total_time += elapsed

        current_peak, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        if assessments:
            matched_cats = set()
            for expected in doc["expected_categories"]:
                for assessment in assessments:
                    if assessment.playbook_category == expected["category_id"]:
                        matched_cats.add(expected["category_id"])
                        break
            matched += len(matched_cats)

    recall = matched / total_expected if total_expected > 0 else 0.0

    return {
        "mode": mode,
        "playbook_path": str(BUNDLED_PLAYBOOKS[mode]),
        "documents_processed": len(docs),
        "expected_categories": total_expected,
        "matched_categories": matched,
        "recall": round(recall, 4),
        "processing_time_seconds": round(total_time, 3),
        "peak_memory_bytes": current_peak,
    }


def main() -> None:
    print("=" * 60)
    print("Product Modes Accuracy Benchmark (Phase 10 / T077)")
    print("=" * 60)

    # Generate synthetic PDFs
    print("\nGenerating synthetic PDFs...")
    ground_truth = _generate_pdfs()
    _save_ground_truth(ground_truth)

    # Run benchmark for each mode
    all_results: list[dict[str, Any]] = []
    print("\nRunning benchmarks...")
    for mode, docs in ground_truth.items():
        print(f"  {mode}: {len(docs)} documents...", end=" ")
        result = _run_mode_benchmark(mode, docs)
        all_results.append(result)
        print("DONE")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(
        f"{'Mode':<20} {'Docs':>5} {'Expected':>9} {'Matched':>8} {'Recall':>7} "
        f"{'Time(s)':>8} {'Peak(B)':>10}"
    )
    print("-" * 70)
    for r in all_results:
        print(
            f"{r['mode']:<20} {r['documents_processed']:>5} {r['expected_categories']:>9} "
            f"{r['matched_categories']:>8} {r['recall']:>7.2%} "
            f"{r['processing_time_seconds']:>8.3f} {r['peak_memory_bytes']:>10}"
        )

    # Save reports
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "product_modes_benchmark.json"
    report_path.write_text(
        json.dumps({"benchmark": "product_modes_accuracy", "results": all_results}, indent=2)
    )
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
