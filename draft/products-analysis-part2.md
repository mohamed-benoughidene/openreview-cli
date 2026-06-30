═══════════════════════════════════════════
PRODUCT SPEC PR-17: modes/AssetCheck.md
───────────────────────────────────────────

PURPOSE
Reviews asset purchase agreements for solo lawyers against their own standard template for small to mid-market business acquisitions, flagging missing provisions, unbalanced risk allocation, tax structuring traps, and missing due diligence follow-through.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set my standard asset purchase agreement template once so I don't have to remember or re-find my positions every time.
US2: As a solo lawyer, I want to upload an asset purchase agreement and see instantly which provisions match, differ from, or are missing from my standard.
US3: As a solo lawyer, I want to export a short memo to my client with what's in the agreement, matching/different/missing terms, purchase price allocation summary, due diligence checklist, and a recommended action.
___

PRODUCT DECISIONS MADE
D1: Two-sided mode — buyer-side and seller-side with separate question sets.
D2: Practice-area overlays: General business (default), Real estate heavy, Intellectual property heavy, Professional practice.
D3: Green/yellow/red comparison output: matches, differs, or missing clause.
D4: Deal size tiers: Under $1M, $1–5M, $5–10M (adjusts thresholds and standard practices).
D5: Shared questionnaire across products for common terms (governing law, dispute resolution, confidentiality, non-compete/non-solicit, indemnification, attorney's fees).
D6: Export memo includes purchase price allocation summary and due diligence checklist.
D7: Excluded from this version: stock purchase agreements, mergers, Section 338(h)(10) election analysis, full due diligence services, tax advice, international transactions, public company/SEC requirements, financing commitment review, Arabic support.
D8: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Solo lawyers only — no paralegal support, charge by the hour.
C2: Asset purchase agreements are the most complex contract most small business clients ever sign.
C3: References specific legal statutes: IRC Section 1060 (Form 8594), IRC Section 197 (non-compete amortization), WARN Act, COBRA, ERISA, CERCLA, California and Delaware bulk sales laws.
C4: Target hardware: 8 GB RAM, no GPU, 2-core CPU (from project-wide constitution). Pipeline peak memory under 110 MB.
___

ASSUMPTIONS MADE
A1: The lawyer has a "standard template" or standard positions for asset purchase agreements.
A2: The lawyer has pre-existing positions they can articulate during a one-time setup.
A3: The tool can distinguish buyer vs seller and apply the correct question set.
A4: The tool can read PDF or Word documents automatically.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-18: modes/BuyCheck.md
───────────────────────────────────────────

PURPOSE
Reviews Stock Purchase Agreements (SPAs) against each client's standard position, flagging inherited liability risks, stale capitalization tables, missing indemnification protections, and earnout traps. Supports two modes — buyer-side and seller-side.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set a client's SPA playbook so I don't have to search past positions each time.
US2: As a solo lawyer, I want to upload an SPA and see green/yellow/red comparison for each of seven clause areas.
US3: As a solo lawyer, I want to export a client memo with matching terms, differing terms, and an overall verdict.
___

PRODUCT DECISIONS MADE
D1: Two modes — buyer-side and seller-side with different question sets.
D2: Seven clause areas: representations and warranties, indemnification, purchase price and adjustments, closing conditions, covenants, earnout provisions, stock vs asset purchase structure.
D3: Saved client "playbook" per client.
D4: Green/yellow/red output per clause area.
D5: Export memo with three sections (matching, differing, overall verdict).
D6: Excluded: securities law compliance, 409A valuation review, antitrust (HSR) analysis, regulatory approval tracking, due diligence services, cross-deal comparison, earnout scenario modeling, Arabic support.
___

CONSTRAINTS IDENTIFIED
C1: The buyer inherits ALL liabilities (known and unknown) in a stock purchase — unlike asset purchases where buyer cherry-picks.
C2: Solo lawyers with no paralegal support.
C3: Seven critical areas must be evaluated quickly and accurately — "a single missing indemnification cap can cost the client millions."
___

ASSUMPTIONS MADE
A1: The client has established positions on SPA terms that can be saved as a playbook.
A2: The tool can read PDF or Word SPAs automatically.
A3: The lawyer can articulate standard positions during a one-time client setup.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-19: modes/ConsultCheck.md
───────────────────────────────────────────

PURPOSE
Reviews consulting agreements and independent contractor agreements for ongoing/retainer-based consulting relationships (not fixed-scope project work), flagging IRS misclassification risk, two-layer structure conflicts, indemnification, and insurance gaps. Supports both consultant-side and hirer-side.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to check both consultant-side and hirer-side positions against a consulting agreement.
US2: As a solo lawyer, I want to check SOWs against the master agreement for conflicts.
US3: As a solo lawyer, I want to review both master agreements and individual SOWs efficiently with two checks per SOW.
___

PRODUCT DECISIONS MADE
D1: Boundary with WorkCheck: ConsultCheck covers ongoing consulting relationships (fractional executives, advisors, ongoing services); WorkCheck covers fixed-scope project-based work (web design, app development).
D2: Boundary with DealCheck: ConsultCheck covers consulting and professional services (advice/ongoing services); DealCheck covers SaaS/technology/services MSAs where the provider delivers a product or platform.
D3: Two question sets: Set A (consultant-side) and Set B (hirer-side).
D4: Master agreement + SOW two-layer structure support with conflict detection between them.
D5: SOW-specific checks: (1) matches standard scope/price/deadlines, (2) doesn't contradict master agreement.
D6: Green/yellow/red output with SOW-specific conflict flags.
D7: Excluded: employment agreements (see HireCheck), MSAs (see DealCheck), full contract drafting, multi-state classification compliance checking, Arabic support, long-term storage of signed contracts.
D8: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: IRS misclassification risk — if the agreement sounds like employment but calls the person a contractor, the company owes back taxes and penalties.
C2: Consulting agreements involve a two-layer structure (master agreement + SOWs) that must be checked together.
C3: Indemnification is common in consulting but rare in employment — lawyers must check who pays if something goes wrong.
C4: Missing insurance requirements means the consultant is personally on the hook.
___

ASSUMPTIONS MADE
A1: The tool can remember a master agreement and check subsequent SOWs against it.
A2: Master agreements and SOWs are uploaded separately and can be linked.
A3: Lawyers have standard positions for both consultant-side and hirer-side clients.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-20: modes/DealCheck.md
───────────────────────────────────────────

PURPOSE
Reviews Master Services Agreements (MSAs) — the umbrella agreement between two companies for ongoing service relationships — flagging liability caps, indemnification, IP ownership, termination, data security, and SOW conflicts. Supports both service provider and customer modes.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set each client's standard MSA positions for either provider-side or customer-side.
US2: As a solo lawyer, I want to upload an MSA and see clause-by-clause green/yellow/red comparison.
US3: As a solo lawyer, I want to check SOWs against the already-reviewed MSA for conflicts.
___

PRODUCT DECISIONS MADE
D1: Two modes — service provider and customer.
D2: Five key clauses highlighted as most review-time-consuming: liability cap, indemnification, IP ownership, termination and exit, data security.
D3: MSA-specific question sets for provider and customer with distinct concerns.
D4: SOW conflict checking against already-reviewed MSA.
D5: Green/yellow/red output.
D6: Excluded: employment agreements (see HireCheck), consulting agreements (see ConsultCheck), NDAs (see PreCheck), full contract drafting, multi-state compliance checking, Arabic support, long-term storage of signed contracts.
D7: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: MSAs are the heaviest contract type solo lawyers see — longer than NDAs, more complex than employment agreements, carry bigger financial risk.
C2: MSAs introduce unique clauses not found in simpler contracts: SLAs, consequence waivers, and contract assignment rules.
C3: MSAs are paired with SOWs that must be checked for conflicts with the umbrella agreement.
___

ASSUMPTIONS MADE
A1: MSAs are always paired with SOWs that come later.
A2: The client has standard positions on MSA terms that can be captured during setup.
A3: The tool can read PDF or Word files automatically.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-21: modes/DistroCheck.md
───────────────────────────────────────────

PURPOSE
Reviews Distribution Agreements against the lawyer's standard — flagging exclusive territory traps, Robinson-Patman Act risks, minimum purchase quota issues, and termination gaps. Supports both manufacturer-side and distributor-side.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to build a distribution playbook per client (manufacturer or distributor).
US2: As a solo lawyer, I want to upload a distribution agreement and see clause-by-clause comparison.
US3: As a solo lawyer, I want to export a client memo with findings and recommendations.
___

PRODUCT DECISIONS MADE
D1: Two modes — manufacturer-side and distributor-side with different question sets.
D2: Seven key clauses: scope of distribution rights, exclusivity and territory, minimum purchase requirements/quota, pricing and resale price maintenance, termination provisions, IP licensing, non-compete.
D3: Manual selection of client role determines which playbook applies.
D4: Saved client playbook.
D5: Green/yellow/red output.
D6: Excluded: full antitrust compliance review beyond basic flagging, FTC Franchise Rule analysis, state dealer protection law database, international distribution agreements, Arabic support.
D7: "It runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Distribution agreements carry hidden antitrust and franchise-formation risks despite looking straightforward.
C2: References Robinson-Patman Act compliance specifically.
C3: Targets solo lawyers and small law firms, no paralegal support.
___

ASSUMPTIONS MADE
A1: Distribution agreements can be read as PDF or Word.
A2: The client has established distribution standards that can be captured in a playbook.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-22: modes/EngageCheck.md
───────────────────────────────────────────

PURPOSE
Reviews Letters of Engagement (legal engagement letters) for solo lawyers against their own standard — flagging scope creep, fee structure gaps, conflict waiver issues, and malpractice exposure. Supports lawyer-reviewing-own-letter and client-reviewing-another-firm's-letter modes.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to review my own engagement letter before sending it to a client against my standard positions.
US2: As a solo lawyer, I want to review another firm's engagement letter for a client switching firms.
US3: As a solo lawyer, I want the tool to check scope of services, fee structure, client identity, conflict disclosure, withdrawal rights, communication standards, and file retention against my standard.
___

PRODUCT DECISIONS MADE
D1: Two modes — lawyer (setting/sending engagement terms) and client (reviewing another lawyer's letter).
D2: Seven key clauses: scope of services, fee structure, client identity, conflict disclosure, right of withdrawal, communication standards, file retention and disengagement.
D3: Shared questions across products: governing law, dispute resolution.
D4: Green/yellow/red output.
D5: Excluded: malpractice insurance procurement, bar association compliance review, trust account compliance, conflict check services (just flagging), fee arbitration analysis, Arabic support.
D6: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Engagement letters are the lawyer's own protection — a vague engagement letter is a malpractice claim waiting to happen.
C2: Vague scope leads to scope creep and malpractice claims — precise scope description is essential.
C3: The spec is for solo lawyers reviewing their own engagement letters or those of other firms.
___

ASSUMPTIONS MADE
A1: The lawyer has a standard template or standard positions for engagement letters.
A2: The tool can read PDF or Word engagement letters.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-23: modes/FranchiseCheck.md
───────────────────────────────────────────

PURPOSE
Reviews Franchise Agreements against the lawyer's standard template — flagging hidden fees, restrictive territory rights, supply chain traps, and FDD (Franchise Disclosure Document) gaps. Supports both franchisee-side and franchisor-side.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to build a franchise playbook per client (franchisee or franchisor).
US2: As a solo lawyer, I want to upload a franchise agreement and see clause-by-clause comparison.
US3: As a solo lawyer, I want to export a client memo with findings and recommendations.
___

PRODUCT DECISIONS MADE
D1: Two modes — franchisee-side and franchisor-side with different question sets.
D2: Ten key clauses: FDD compliance (23 mandatory items, 14-day delivery), fees and ongoing royalties, territory rights, renewal and termination, supply chain restrictions, post-termination non-compete, transfer and assignment restrictions, ongoing obligations, governing law/arbitration, fee stacking.
D3: Manual role selection determines which playbook applies.
D4: Saved client playbook.
D5: Green/yellow/red output.
D6: Excluded: FDD preparation, state franchise registration services, franchise relationship law compliance checking, multi-unit area development agreements, international franchise agreements, Arabic support.
D7: "It runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Franchise agreements are 30–50 page "take it or leave it" contracts drafted by the franchisor.
C2: 23 mandatory FDD items must be disclosed; 14-day delivery rule before signing.
C3: Targets solo lawyers and small law firms, no paralegal support.
___

ASSUMPTIONS MADE
A1: Lawyers have standard positions on franchise terms that can be captured in a playbook.
A2: The tool can read PDF or Word agreements.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-24: modes/GuaranteeCheck.md
───────────────────────────────────────────

PURPOSE
Reviews Guarantee and Suretyship Agreements against each client's standard position — flagging personal liability traps, continuing guarantee exposure, waived defenses, and missing duration limits. Supports both creditor-side and guarantor-side modes.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set a guarantee playbook per client (creditor-side or guarantor-side).
US2: As a solo lawyer, I want to upload a guarantee agreement and see green/yellow/red comparison per clause area.
US3: As a solo lawyer, I want to export a client memo with matching, differing, and missing clauses plus an overall verdict.
___

PRODUCT DECISIONS MADE
D1: Two modes — creditor-side and guarantor-side with different question sets.
D2: Seven key clauses: type of guarantee, surety defenses, duration and termination, waiver of defenses, subrogation rights, contribution among co-guarantors, notice requirements.
D3: Saved client playbook.
D4: Green/yellow/red output.
D5: Includes OCR for scanned PDFs.
D6: Excluded: surety bond analysis, UCC Article 3 comprehensive review, credit analysis, personal financial advice/solvency analysis, cross-guarantor comparison, automatic calculation of maximum exposure under continuing guarantees, Arabic support.
___

CONSTRAINTS IDENTIFIED
C1: "A guarantee is the most dangerous document most people sign" — personal assets (home, savings, future wages) are on the line.
C2: Guarantees are typically 5–15 pages.
C3: The guarantor receives nothing in return except the obligation to pay if the borrower defaults.
C4: A continuing guarantee can snowball without the guarantor realizing it — open-ended, no limit on amount or time.
___

ASSUMPTIONS MADE
A1: Guarantors often don't understand what type of guarantee they're signing (payment vs performance vs collection).
A2: Most guarantors don't know they may be on the hook for everything via joint and several liability.
A3: Clients have established positions on guarantee terms.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-25: modes/HireCheck.md
───────────────────────────────────────────

PURPOSE
Reviews employment agreements for solo lawyers — when a client receives a job offer or needs to send an offer to a new hire. Compares the agreement against the client's playbook and shows what's different.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set each client's standard employment positions (shared and employment-specific) during a one-time setup.
US2: As a solo lawyer, I want to upload an employment agreement and see green/yellow/red comparison per clause.
US3: As a solo lawyer, I want to export a client memo with matching terms, differing terms, and an overall verdict.
___

PRODUCT DECISIONS MADE
D1: Shared questions across products: confidentiality, IP assignment, non-solicit, governing law, dispute resolution.
D2: Employment-specific questions: role type, non-compete, severance, equity, benefits, termination notice, duty of loyalty, relocation, expenses.
D3: Two directions: client receiving an offer OR client sending an offer.
D4: Green/yellow/red output.
D5: Excluded: independent contractor and consulting agreements (see ConsultCheck), full contract drafting, multi-state compliance checking, Arabic support, long-term storage of signed contracts.
D6: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Employment agreements typically have 10–15 clauses that must be reviewed.
C2: The lawyer must find past positions on non-compete scope, severance, and equity terms each time without the tool.
C3: Targets solo lawyers and small firms.
___

ASSUMPTIONS MADE
A1: Clients have standard positions that can be saved and reused.
A2: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-26: modes/IndemnityCheck.md
───────────────────────────────────────────

PURPOSE
Reviews standalone Indemnification Agreements and indemnification provisions within other contracts — flagging one-sided obligations, defense cost traps, and survival period gaps. Supports both indemnitor (paying) and indemnitee (protected) sides.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to build an indemnification playbook per client (indemnitor or indemnitee).
US2: As a solo lawyer, I want to upload a contract and see clause-by-clause comparison per clause area.
US3: As a solo lawyer, I want to export a client memo with findings and recommendations.
___

PRODUCT DECISIONS MADE
D1: Two modes — indemnitor (the party paying) and indemnitee (the party protected).
D2: Seven key clauses: "indemnify, defend, and hold harmless" (three separate obligations), scope of covered claims ("arising out of" broad vs "caused by" narrow), notice requirements, control of defense, caps/baskets/deductibles, survival period, subrogation and contribution rights.
D3: Checks whether the governing state has anti-indemnity statutes (construction, oil and gas states).
D4: Saved client playbook.
D5: Green/yellow/red output.
D6: Excluded: insurance coverage analysis, anti-indemnity statute database by state, full contract drafting beyond indemnification clauses, Arabic support.
D7: "It runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: "Indemnify, defend, and hold harmless" are three separate legal obligations often conflated into one sentence.
C2: The word "defend" forces the party to pay the other side's legal fees before anyone is found at fault.
C3: Some states have anti-indemnity statutes, particularly in construction and oil and gas.
C4: Indemnification is the most misunderstood clause in contract law.
___

ASSUMPTIONS MADE
A1: Clients have standard positions on indemnification terms.
A2: The tool can read PDF or Word.
A3: Lawyers know which state's law applies and whether it has anti-indemnity statutes.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-27: modes/LeaseCheck.md
───────────────────────────────────────────

PURPOSE
Reviews commercial lease agreements — whether the client is renting space (tenant) or leasing property (landlord) — flagging lease type traps, CAM charge exposure, personal guarantee risks, maintenance/repair obligations, and use clause restrictions.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set a client's commercial lease standard positions (tenant or landlord) during setup.
US2: As a solo lawyer, I want to upload a lease (or amendment or LOI) and see clause-by-clause comparison.
US3: As a solo lawyer, I want to know the real total monthly cost (base rent plus estimated CAM, taxes, insurance).
US4: As a solo lawyer with a retail or restaurant client, I want to check for retail/restaurant-specific add-ons and traps.
___

PRODUCT DECISIONS MADE
D1: Two modes — tenant and landlord with separate question sets.
D2: Seven key clauses: lease type (gross, triple-net, modified gross), operating expenses/CAM, personal guarantee, maintenance and repairs, use clause, assignment and subletting, default and remedies.
D3: Retail and restaurant add-ons: exclusivity, hours of operation, percentage rent, outdoor operations, liquor license, HVAC/kitchen maintenance, drive-through rights.
D4: Support for full lease, lease amendment, and letter of intent uploads.
D5: Automated calculation of true monthly cost (base + pass-throughs).
D6: Shared questions across products: governing law, dispute resolution, force majeure, confidentiality.
D7: Green/yellow/red output.
D8: Excluded: residential leases, purchase and sale agreements (see BuyCheck), full contract drafting, multi-state tenant rights compliance, CAM audit service (just flagging whether audit rights exist), sublease review, Arabic support.
D9: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Commercial leases are the most expensive contract most small businesses ever sign — a five-year lease at $5,000/month is a $300,000 commitment before extras.
C2: Most businesses sign a lease once every 5–10 years and don't know what's standard or negotiable.
C3: CAM charges can push real rent 30–50% above base rent.
C4: Personal guarantee means business owner's personal assets are on the line.
___

ASSUMPTIONS MADE
A1: The property location can auto-detect governing law.
A2: Lawyers have standard positions on lease terms.
A3: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-28: modes/LicenseCheck.md
───────────────────────────────────────────

PURPOSE
Reviews SaaS subscription agreements and software license agreements — whether the client is buying software (customer) or selling software (vendor) — flagging auto-renewal traps, data lock-in risks, audit rights, uncapped price increases, and beta feature gaps.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set standard SaaS positions per client (customer or vendor).
US2: As a solo lawyer, I want to upload a SaaS agreement and see green/yellow/red comparison.
US3: As a solo lawyer, I want to export a client memo with findings.
___

PRODUCT DECISIONS MADE
D1: Two modes — customer (buying software) and vendor (selling software) with separate question sets.
D2: SaaS-specific traps highlighted: auto-renewal, data lock-in, audit rights, usage restrictions, price increases with no cap, beta features (no warranty/liability), support levels.
D3: Shared questions across products: confidentiality, IP ownership, governing law, dispute resolution, data security, force majeure, liability cap, indemnification.
D4: Green/yellow/red output.
D5: Excluded: MSAs (see DealCheck), employment agreements (see HireCheck), consulting agreements (see ConsultCheck), NDAs (see PreCheck), full contract drafting, per-user pricing calculations, Arabic support.
D6: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: SaaS agreements have unique traps a general contract reviewer would miss: auto-renewal, data lock-in, audit penalties, uncapped price increases, beta features with no warranty.
C2: Auto-renewal silently continues unless cancelled 30–90 days before the end.
C3: Audit rights can result in back fees plus penalties if usage exceeds limits.
___

ASSUMPTIONS MADE
A1: Clients have standard positions on SaaS terms.
A2: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-29: modes/LoanCheck.md
───────────────────────────────────────────

PURPOSE
Reviews loan agreements and promissory notes against the lawyer's standard — flagging usury traps, acceleration risks, security interest gaps, and financial covenant dangers. Supports both lender-side and borrower-side.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set standard loan agreement positions per client (lender or borrower).
US2: As a solo lawyer, I want to upload a loan agreement and see per-clause comparison.
US3: As a solo lawyer, I want to export a memo with findings and usury notes for the client to discuss with a tax professional.
___

PRODUCT DECISIONS MADE
D1: Two modes — lender-side and borrower-side with separate question sets.
D2: Seven key clauses: interest rate and usury compliance, payment terms (interest-only, amortizing, balloon), default provisions/cure periods, acceleration clause, security interests (UCC Article 9), financial covenants, prepayment and penalty provisions.
D3: Shared questions: governing law, dispute resolution.
D4: Usury notes included in export memo.
D5: Green/yellow/red output.
D6: Excluded: usury law database (just flagging), SBA loan compliance, securities law analysis, tax advice, loan brokerage/matching services, Arabic support.
D7: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Usury laws set maximum allowable interest rates — exceeding them can void the entire loan.
C2: Balloon payments are a major trap — borrower faces a large lump sum with no guaranteed refinancing.
C3: Breach of a financial covenant is an event of default even if payments are current.
___

ASSUMPTIONS MADE
A1: Clients have standard positions on loan terms.
A2: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-30: modes/LOICheck.md
───────────────────────────────────────────

PURPOSE
Reviews Letters of Intent (LOIs) for business transactions — flagging binding vs non-binding ambiguity, missing exclusivity terms, and inadequate due diligence timelines before the deal locks in. Supports both buyer (offeror) and seller (offeree) modes.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set a client's LOI playbook (buyer or seller).
US2: As a solo lawyer, I want to upload an LOI and see clause-by-clause green/yellow/red comparison.
US3: As a solo lawyer, I want to export a client memo with findings and recommendations.
___

PRODUCT DECISIONS MADE
D1: Two modes — buyer (offeror) and seller (offeree) with different question sets.
D2: Seven key clauses: binding vs non-binding provisions, exclusivity/no-shop, confidentiality, due diligence timelines, break-up fees/termination, transaction structure (asset vs stock), purchase price allocation.
D3: Saved client playbook.
D4: Green/yellow/red output.
D5: Excluded: definitive agreement drafting, due diligence management/data room setup, state securities law compliance review, tax advice on deal structure, Arabic support, long-term storage, multi-user accounts, AI training.
___

CONSTRAINTS IDENTIFIED
C1: LOIs look like informal documents but create real legal obligations.
C2: The binding vs non-binding distinction is where most mistakes happen — some clauses are binding (confidentiality, exclusivity, governing law), others are not (price, deal structure).
___

ASSUMPTIONS MADE
A1: Lawyers have established positions on LOI terms that can be saved.
A2: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-31: modes/OpCheck.md
───────────────────────────────────────────

PURPOSE
Reviews LLC Operating Agreements against the client's standard position — flagging missing buy-sell provisions, capital account traps, fiduciary duty gaps, and tax election misalignment. Supports both member-side and manager-side.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set an operating agreement playbook (member-side or manager-side).
US2: As a solo lawyer, I want to upload an operating agreement and see green/yellow/red comparison per clause area.
US3: As a solo lawyer, I want to export a client memo with findings and recommendations.
___

PRODUCT DECISIONS MADE
D1: Two modes — member-side and manager-side with different question sets.
D2: Seven key clauses: management structure (member-managed vs manager-managed), capital accounts/contribution obligations, profit/loss allocation and distributions, buy-sell provisions, fiduciary duties, transfer restrictions, dissolution and continuation.
D3: Saved client playbook.
D4: Green/yellow/red output.
D5: OCR for scanned PDFs.
D6: Excluded: state-specific LLC statute database, tax election advice (pass-through vs entity-level), Articles of Organization drafting, multi-member vs single-member comparative analysis, cross-LLC comparison, automatic tax distribution calculation, Arabic support.
___

CONSTRAINTS IDENTIFIED
C1: Most operating agreements are downloaded from the internet and miss critical provisions.
C2: A missing buy-sell provision can leave a client's family stuck with an illiquid interest in a business.
C3: Operating agreements are typically 15–40 pages with cross-references.
C4: Default in most states is member-managed, which may not match the client's intent.
___

ASSUMPTIONS MADE
A1: References IRC Section 704(b) (profit/loss allocation) are familiar to the lawyer.
A2: References IRC Section 754 (inside basis adjustment) are familiar.
A3: Clients have established standard positions on operating agreement terms.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-32: modes/PartnerCheck.md
───────────────────────────────────────────

PURPOSE
Reviews partnership agreements against the lawyer's own standard for a well-drafted partnership — flagging missing clauses, dangerous default rules, and tax traps. Handles three partnership types: General Partnership, Limited Partnership, and Limited Liability Partnership.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set my standard template for partnership agreements (not per-client history, but my own framework).
US2: As a solo lawyer, I want to upload a partnership agreement and see per-clause comparison against my standard.
US3: As a solo lawyer, I want partnership-type-specific checks (GP, LP, LLP) with extra questions for each.
US4: As a solo lawyer, I want to select review context: pre-signing, amendment, or new partner admission.
___

PRODUCT DECISIONS MADE
D1: Three partnership type variants: General Partnership, Limited Partnership, Limited Liability Partnership, each with specific extras.
D2: Three review contexts: pre-signing review, amendment review, new partner admission.
D3: Core questions apply to all types; GP-specific (joint and several liability, mutual agency, apparent authority), LP-specific (limited partner safe harbor, GP control, key person, investor protections, anti-Holzman language, special tax allocations, transfer of interests), LLP-specific (professional regulatory compliance, insurance, locked capital, partner retirement, client continuity, succession).
D4: Green/yellow/red output with type-specific examples.
D5: Excluded: LLC operating agreements (see OpCheck), corporate bylaws/shareholder agreements, full contract drafting, international partnership agreements (non-US law), tax return preparation/tax advice/IRC analysis, partnership dissolution services, Arabic support.
D6: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Partnership agreements are governance documents between people who trust each other — not arm's-length buyer/seller deals.
C2: General partners are jointly and severally liable for everything.
C3: In Limited Partnerships, exercising management rights can cost Limited Partners their liability shield.
C4: A 50/50 partnership with no deadlock mechanism is paralyzed on every disagreement.
___

ASSUMPTIONS MADE
A1: The lawyer has a standard "best-practice framework" for partnership agreements (not per-client history).
A2: The spec assumes familiarity with Section 754 election, Section 179 deduction allocation, Section 704(b) compliant capital account maintenance, and "anti-Holzman language."
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-33: modes/PreCheck.md
───────────────────────────────────────────

PURPOSE
Reviews incoming Non-Disclosure Agreements (NDAs) and instantly shows what's different from what each client normally accepts. The simplest product mode — 6 setup questions, green/yellow/red comparison, one-click memo.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set a client's NDA playbook with 6 standard positions so I don't have to search "what did this client accept last time."
US2: As a solo lawyer, I want to upload an NDA and see clause-by-clause green/yellow/red comparison.
US3: As a solo lawyer, I want to export a client memo with findings and recommendations.
___

PRODUCT DECISIONS MADE
D1: Six client setup questions: one-way or mutual, confidentiality duration, definition of confidential information, exclusions (public info, independently developed, known), governing law, remedy for breach.
D2: Saved client playbook.
D3: Green/yellow/red output.
D4: Export memo with three sections (matching, differing, overall verdict).
D5: Excluded: other contract types (MSA, employment, lease), Arabic support, long-term storage, multi-user accounts, AI training.
D6: "It runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Solo lawyers waste time hunting for "what did this client accept last time" for each NDA.
C2: Lawyers charge by the hour and have no paralegal support.
___

ASSUMPTIONS MADE
A1: Clients have standard positions on 6 NDA dimensions that can be captured.
A2: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-34: modes/PrivacyCheck.md
───────────────────────────────────────────

PURPOSE
Reviews Data Processing Agreements (DPAs) — the privacy add-on attached to MSAs and SaaS agreements whenever personal data is involved — flagging controller/processor role confusion, cross-border transfer gaps, sub-processor notice issues, and breach notification timeline problems. Checks for conflicts between the DPA and the main agreement.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set standard data processing positions per client (controller or processor).
US2: As a solo lawyer, I want to upload a DPA and see clause-by-clause comparison.
US3: As a solo lawyer, I want the DPA checked against the main agreement (MSA or SaaS) for conflicts.
___

PRODUCT DECISIONS MADE
D1: Two modes — controller (data owner) and processor (data handler) with separate question sets.
D2: Combined review with the main agreement (MSA or SaaS) for conflicts between the two documents.
D3: Shared questions across products: IP ownership, governing law, dispute resolution, force majeure, liability cap, indemnification.
D4: Specific DPA checks: cross-border transfers (SCCs, UK Addendum, DPF), sub-processors (general auth vs specific approval, notice period), breach notification (hours), data return timeline, data subject rights assistance, audit rights, security measures.
D5: Green/yellow/red output with conflict flags.
D6: Excluded: SaaS agreements (see LicenseCheck), MSAs (see DealCheck), NDAs (see PreCheck), full contract drafting, multi-regulatory compliance checking, Arabic support.
D7: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: DPAs are always an add-on to another agreement — never standalone. The lawyer must read two documents together and check for conflicts.
C2: Most DPA clauses are required by law (GDPR Article 28), not by negotiation.
C3: Cross-border data transfers need specific legal mechanisms: Standard Contractual Clauses, UK Addendum, or Data Privacy Framework.
C4: Missing breach notification timeline can mean fines.
C5: Missing data security annex makes the DPA incomplete (GDPR Article 32).
___

ASSUMPTIONS MADE
A1: The main agreement (MSA or SaaS) may already be in the system for conflict checking.
A2: Clients have standard positions on data processing terms.
A3: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-35: modes/SettlementCheck.md
───────────────────────────────────────────

PURPOSE
Reviews settlement and release agreements against the lawyer's own standard — flagging dangerous release language, hidden tax consequences, government reporting obligations (Medicare/Medicaid), and practice-area-specific traps (employment, personal injury, commercial). Supports plaintiff and defendant roles.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set my standard settlement template (best-practice framework) for settlement agreements.
US2: As a solo lawyer, I want to upload a settlement agreement and see per-clause green/yellow/red comparison.
US3: As a solo lawyer, I want practice-area-specific checks (employment, personal injury, or commercial) with extra rules for each.
US4: As a solo lawyer, I want to select role (plaintiff or defendant), practice area, and context (pre-litigation, litigation, post-judgment).
___

PRODUCT DECISIONS MADE
D1: Two roles — plaintiff (receiving payment) and defendant (paying and seeking finality), each with core and context-specific question sets.
D2: Three practice areas: employment, personal injury, commercial — each with specific extras.
D3: Three contexts: pre-litigation settlement, litigation settlement, post-judgment settlement.
D4: Nine key clauses: release of claims, tax allocation, Medicare/Medicaid compliance, confidentiality/non-disparagement, non-admission of liability, waiver of unknown claims, indemnification/hold harmless, payment terms/timing, ongoing obligations.
D5: Green/yellow/red output with role- and practice-area-specific examples.
D6: Export memo includes tax notes on how proceeds are likely to be taxed.
D7: Excluded: corporate bylaws/shareholder agreements, class action settlement review, tax advice (just flagging), full contract drafting, bankruptcy settlement review, international settlements, Arabic support.
D8: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Settlement agreements are "the most dangerous type of contract on a per-clause basis" — they permanently extinguish rights, often including rights the client doesn't know they have.
C2: Cites specific statutes: IRC Section 104(a)(2) (physical injury tax-free), IRC Section 409A (deferred compensation), OWBPA (21-day consideration, 7-day revocation for ADEA claims), California Civil Code Section 1542 (unknown claims waiver), Medicare/Medicaid SCHIP Extension Act Section 111 ($1,000/day non-compliance penalty), Speak Out Act (2022), Silenced No More Act, IRC Section 130 (structured settlement assignments).
C3: Wrong tax characterization can trigger IRS audit and tax deficiency.
C4: Medicare non-compliance penalty: $1,000 per day per claim.
___

ASSUMPTIONS MADE
A1: The lawyer has a standard template for settlement agreements.
A2: The lawyer has practice areas they typically handle (employment, personal injury, or commercial).
A3: The lawyer can select role, practice area, and context for each review.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-36: modes/SponsorCheck.md
───────────────────────────────────────────

PURPOSE
Reviews sponsorship agreements — flagging vague deliverables, missing brand usage rights, tax deductibility traps, and termination gaps before the money starts flowing. Supports both sponsor (paying) and sponsee (receiving) modes.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set a sponsorship playbook per client (sponsor or sponsee).
US2: As a solo lawyer, I want to upload a sponsorship agreement and see clause-by-clause green/yellow/red comparison.
US3: As a solo lawyer, I want to export a client memo with findings and recommendations.
___

PRODUCT DECISIONS MADE
D1: Two modes — sponsor (paying for exposure) and sponsee (receiving sponsorship) with different question sets.
D2: Seven key clauses: scope and deliverables, brand usage/IP licensing, exclusivity provisions, payment terms/timing, termination and refund provisions, indemnification/insurance, content approval rights.
D3: Saved client playbook.
D4: Green/yellow/red output.
D5: Excluded: tax advice on UBIT (Unrelated Business Income Tax), nonprofit compliance review, FTC disclosure analysis, ASC 606 revenue recognition analysis, Arabic support, long-term storage, multi-user accounts, AI training.
___

CONSTRAINTS IDENTIFIED
C1: Sponsorship agreements sit at the intersection of marketing, IP, tax, and contract law.
C2: Vague deliverables are a key risk — "reasonable promotional support" is too vague to enforce.
C3: Exclusivity provisions can be too broad ("all industries") with significant consequences.
___

ASSUMPTIONS MADE
A1: Clients have established positions on sponsorship terms.
A2: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-37: modes/SubCheck.md
───────────────────────────────────────────

PURPOSE
Reviews subcontractor agreements — flagging flow-down clause traps, pay-when-paid risks, one-sided indemnification, and insurance gaps. Supports both General Contractor (GC) and subcontractor modes.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set a subcontractor playbook per client (GC or subcontractor).
US2: As a solo lawyer, I want to upload a subcontract and see clause-by-clause green/yellow/red comparison.
US3: As a solo lawyer, I want to export a client memo with findings and recommendations.
___

PRODUCT DECISIONS MADE
D1: Two modes — general contractor and subcontractor with different question sets.
D2: Seven key clauses: scope of work/change orders, payment terms (pay-when-paid vs pay-if-paid, retainage), flow-down clause (inherits prime contract obligations), indemnification/hold harmless, insurance requirements (workers' comp, general liability, umbrella, additional insured), dispute resolution, termination provisions.
D3: Saved client playbook.
D4: Green/yellow/red output.
D5: Excluded: construction law compliance review, prevailing wage analysis, mechanic's lien filing guidance, OSHA compliance checks, contractor licensing verification, Arabic support, long-term storage, multi-user accounts, AI training.
___

CONSTRAINTS IDENTIFIED
C1: Subcontractor agreements are "the most dangerous documents in construction" — typically 30–50 pages of dense construction language.
C2: A single flow-down clause can inherit the entire prime contract obligations in one sentence.
C3: Indemnification using "arising out of" language covers even when the subcontractor did nothing wrong.
___

ASSUMPTIONS MADE
A1: Clients have established positions on subcontract terms.
A2: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-38: modes/WorkCheck.md
───────────────────────────────────────────

PURPOSE
Reviews independent contractor work agreements for project-based work (not ongoing/retainer-based; see ConsultCheck) — flagging misclassification risk, intellectual property gaps, vague scope, and payment traps. Supports both client (hiring) and contractor (being hired) modes.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set standard work agreement positions per client (client-side or contractor-side).
US2: As a solo lawyer, I want to upload a work agreement and see green/yellow/red comparison.
US3: As a solo lawyer, I want to export a memo with misclassification risk notes besides the standard findings.
___

PRODUCT DECISIONS MADE
D1: Boundary with ConsultCheck: WorkCheck covers project-based work with defined deliverables (web design, app development, content creation); ConsultCheck covers ongoing/retainer-based consulting relationships.
D2: Two modes — client-side (hiring the contractor) and contractor-side (being hired) with separate question sets.
D3: Seven key clauses: independent contractor status (IRS 20-Factor Test reference), scope of work/deliverables, IP assignment or work-for-hire, payment terms (deposit, milestones, late penalties), termination for cause and convenience, confidentiality, non-solicitation and non-compete.
D4: Shared questions across products: governing law, dispute resolution, confidentiality.
D5: Misclassification risk notes included in export memo.
D6: Green/yellow/red output.
D7: Excluded: misclassification legal advice (just flagging risk indicators), IRS 20-Factor Test analysis, state-specific worker classification guidance, tax filing/1099 preparation, full contract drafting, Arabic support.
D8: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: "A signed independent contractor agreement does NOT shield you if the actual working relationship shows employer control."
C2: Independent contractor agreements are the most misused contracts in small business.
C3: Silence on IP ownership means the contractor owns everything they create.
___

ASSUMPTIONS MADE
A1: Clients have standard positions on work agreement terms.
A2: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════
