# Spec 031 — Product Modes Batch 3: FranchiseCheck, OpCheck, PartnerCheck, SponsorCheck, DistroCheck

**Status**: Draft — zero open clarifications
**Author**: Speckit Specify
**Date**: 2026-07-09

---

## Overview

Add five new product modes to the `openreview` CLI for entity and partnership contract types: **FranchiseCheck** (franchise agreements and franchise disclosure documents), **OpCheck** (operating agreements for LLCs), **PartnerCheck** (general and limited partnership agreements), **SponsorCheck** (sponsorship agreements), and **DistroCheck** (distribution and reseller agreements). These are the third and final batch of the product-mode expansion (22 product modes total — 17 built across prior specs, 5 delivered here).

Each mode reuses the existing single-party review pipeline (the three-agent review capability — extraction, verification, and reporting — with the three-position playbook format and three-color confidence output) with a domain-specific playbook YAML and extraction prompt template. This follows the pattern established by all seventeen prior modes across L-4a (spec 028, 6 modes), L-4b (spec 029, 5 modes + 9 orphan wiring), and the initial 6 wired modes (PreCheck, DealCheck, HireCheck, LicenseCheck, LeaseCheck, PrivacyCheck).

These five modes are distinguished from prior batches by their **multi-party complexity**. Franchise, operating agreement, partnership, and distribution contracts frequently involve more than two parties or multi-tier relationships (franchisor-franchisee-territory, distributor-manufacturer-customer, LLC members-managers). The single-party review pipeline handles this by reviewing from one party's perspective only; bilateral multi-party comparison is deferred (see Assumptions: multi-party comparison gap).

### New L-4c modes

| Mode | Contract Type | Playbook File |
|------|---------------|---------------|
| FranchiseCheck | Franchise agreements, franchise disclosure documents | `franchise-v1.yaml` |
| OpCheck | Operating agreements (LLC governance) | `operating-agreement-v1.yaml` |
| PartnerCheck | General and limited partnership agreements | `partnership-v1.yaml` |
| SponsorCheck | Sponsorship agreements | `sponsorship-v1.yaml` |
| DistroCheck | Distribution and reseller agreements | `distribution-v1.yaml` |

## Clarifications

No clarifications were needed. The pattern is fully validated by L-4a and L-4b, and the user briefed all required content in the task description.

## Why

The single-party review pipeline is production-ready and has been demonstrated across seventeen prior modes. Each new mode validates that the architecture scales across contract domains without per-mode pipeline changes. Each new mode requires only:

- A domain-specific playbook YAML (3-position categories — preferred, acceptable, walkaway — with confidence thresholds)
- An extraction prompt template tuned to the domain's vocabulary
- A CLI subcommand wiring (minimal routing)

Shipping five modes in one batch as the final batch completes the 22-mode product line. These five modes target entity-formation and multi-party contracts — the domain that solo practitioners and small-business owners encounter when structuring their business relationships (operating agreements, partnerships, distribution deals) or expanding through third-party channels (franchises, sponsorships).

The multi-party complexity of these modes tests the single-party pipeline's limits. By reviewing from one party's perspective only, the pipeline can handle multi-party documents without requiring bilateral comparison logic (which remains a research gap for future work).

## User Scenarios

### S1: Franchisee reviews a franchise agreement (FranchiseCheck)

A prospective franchisee receives a franchise disclosure document (FDD) and franchise agreement from a franchisor. They run:

```
openreview franchisecheck franchise-agreement.pdf
```

The tool parses the document, runs the three-agent extraction and verification pipeline with the franchise playbook, and outputs a three-color assessment: Green (clear territory rights, defined renewal terms, reasonable royalty and advertising fees, mutual termination rights), Amber (vague territory definition that could limit expansion, minimum purchase requirements with no market-adjustment clause, non-compete extending beyond franchise term), Red (unilateral termination by franchisor without cause, "best efforts" marketing obligation with no cap on ad fund contributions, broad release of franchisor liability in FDD Item 5 or Item 20). A memo is exported to `./memo/franchise-agreement-franchisecheck.pdf`.

**Edge case — franchise classification boundary**: The prompt template includes a franchise-classification boundary flag to distinguish a true franchise agreement (trademark license + significant control/assistance + franchise fee, per FTC Franchise Rule 16 CFR §436) from a business-opportunity or licensing arrangement that looks like a franchise but falls outside the FTC Rule. The flag is advisory only and does not constitute legal classification.

**Why this priority**: Franchise agreements are heavily regulated (FTC Franchise Rule, state registration laws). Solo franchisees are the least likely to have legal counsel during the FDD review period (minimum 14 days by law). Early identification of walkaway terms before the franchisee signs is high-value.

### S2: LLC member reviews an operating agreement (OpCheck)

A new LLC member receives an operating agreement before joining an existing LLC or forming a new one. They run:

```
openreview opcheck operating-agreement.pdf
```

The playbook covers membership structure (member-managed vs. manager-managed), capital contributions and additional capital calls, profit and loss allocation (IRC §704(b) compliance), distributions and tax pass-through provisions, voting rights and decision-making authority, transfer restrictions (right of first refusal, buy-sell provisions), dissolution and winding-up provisions, and indemnification of members and managers. The tool flags a Red clause (disproportionate voting rights that dilute the member's vote below their economic interest without consent) and an Amber clause (broad manager authority to incur debt above a threshold without member approval).

**Why this priority**: Operating agreements are the governing document for LLCs, which are the most common business entity type for solo practitioners and small businesses in the United States. Members routinely sign operating agreements without understanding how capital call provisions or voting rights affect their control.

### S3: Partner reviews a partnership agreement (PartnerCheck)

A professional is invited to join a general partnership or limited partnership. They run:

```
openreview partnercheck partnership-agreement.pdf
```

The playbook covers capital contributions, profit and loss allocation ratios, management authority and decision-making, partner withdrawal and expulsion terms, transfer of partnership interests, dissolution events and winding-up, indemnification and liability allocation, dispute resolution (mediation/arbitration), and non-compete and non-solicitation restrictions. The tool flags a Red clause (joint and several personal liability for partnership debts in a general partnership context without liability shield confirmation) and an Amber clause (for-cause expulsion by majority vote without clear definition of what constitutes cause).

**Edge case — PartnerCheck vs. OpCheck overlap**: The PartnerCheck and OpCheck playbooks share similar concepts (capital contributions, profit allocation, voting, dissolution). The distinguishing factor is the legal entity type:
- **OpCheck**: reviews operating agreements under state LLC acts (Delaware LLC Act, state equivalents). Members have limited liability by default. Governance is defined by the operating agreement.
- **PartnerCheck**: reviews partnership agreements under the Uniform Partnership Act (UPA) or Revised Uniform Partnership Act (RUPA). General partners have joint and several personal liability unless the agreement specifies otherwise. The playbook prioritizes liability allocation and personal exposure.
- If a document is labeled with both "LLC" and "Partnership" terminology, the MODE_VOCABULARY and prompt template guide the user to the correct mode. The user is responsible for choosing the mode that matches the entity type.

**Why this priority**: Partnership agreements create personal liability that most small-business owners do not fully appreciate. The distinction between general partnership liability (unlimited, joint and several) and LLC liability (limited to capital contribution) is often misunderstood.

### S4: Sponsorship seeker reviews a sponsorship agreement (SponsorCheck)

A nonprofit organization or event organizer receives a sponsorship agreement from a corporate sponsor. They run:

```
openreview sponsorcheck sponsorship-agreement.pdf
```

The playbook covers sponsorship fee and payment schedule, sponsorship rights and benefits (logo placement, event recognition, exclusivity), intellectual property license (use of sponsor's trademarks), termination for breach or force majeure, reporting and marketing obligations, indemnification (sponsor activity liability at the event), and non-disparagement. The tool flags a Green clause (mutual termination rights with 30-day cure period) and an Amber clause (broad exclusivity clause preventing the organizer from accepting any competitor as a sponsor, even in unrelated categories).

**Why this priority**: Sponsorship agreements are the primary revenue vehicle for events, nonprofits, and content creators. The balance of rights between sponsor and organizer is often one-sided toward the sponsor, and small organizers may not negotiate.

### S5: Distributor reviews a distribution agreement (DistroCheck)

A small business considering becoming a distributor for a manufacturer receives a distribution agreement. They run:

```
openreview distrocheck distribution-agreement.pdf
```

The playbook covers territory definition and exclusivity, minimum purchase requirements (and cure periods for shortfall), pricing and payment terms, inventory management and returns, marketing and sales support, intellectual property license (use of manufacturer's trademarks), termination rights (with or without cause), non-compete and channel restrictions, and dispute resolution including jurisdiction and venue. The tool flags a Red clause (minimum purchase requirement that increases annually without a market-adjustment mechanism) and an Amber clause (broad non-compete preventing the distributor from handling any competing product line, even outside the distribution territory).

**Edge case — DistroCheck vs. FranchiseCheck boundary**: Distribution agreements and franchise agreements can overlap. The DistroCheck prompt template includes a franchise-classification boundary flag (matching the FranchiseCheck flag) that reports when a distribution agreement's level of control (pricing control, operating standards, mandatory supplier mandates) may approach franchise-like regulation under FTC or state law. This is advisory only and does not constitute classification.

**Why this priority**: Distribution agreements define the commercial relationship for getting products to market. Small distributors often sign aggressive minimum purchase or broad non-compete terms without understanding the financial commitment or exit cost.

## Functional Requirements

Each requirement is testable and cites a blueprint capability (PR-N for mode source list).

### FR-01: Each mode has a bundled playbook YAML file
For each of the five new modes, a playbook YAML file exists at `src/openreview_cli/review/playbooks/<playbook-file>` matching the table in Overview. The playbook follows the existing 3-position (preferred/acceptable/walkaway) format with confidence thresholds. Each playbook MUST parse without error by the Playbook loader (`Playbook.load()`).

Blueprint mapping: product modes framework — playbook YAML interface. Applies to all modes equally.

### FR-02: Each mode has a MODE_VOCABULARY entry
A `MODE_VOCABULARY` dictionary entry exists for each mode, mapping the mode key (e.g., `franchisecheck`) to a human-readable name and description. These entries are used by the CLI help text, mode listing, and prompt templates. The entry MUST include at minimum: `mode_key`, `display_name`, `description`, and `playbook_file`.

Blueprint mapping: product modes framework — mode registry.

### FR-03: Each mode has a CLI subcommand
Each mode is wired as a Typer subcommand via the existing `_register_product_mode` pattern. The CLI invocations are:

| Mode | CLI command |
|------|-------------|
| FranchiseCheck | `openreview franchisecheck review <file>` |
| OpCheck | `openreview opcheck review <file>` |
| PartnerCheck | `openreview partnercheck review <file>` |
| SponsorCheck | `openreview sponsorcheck review <file>` |
| DistroCheck | `openreview distrocheck review <file>` |

Each subcommand MUST accept a PDF or DOCX file path, produce a three-color assessment, and output a memo PDF. Each subcommand MUST be discoverable via `openreview --help`.

Blueprint mapping: product modes framework — CLI routing. Applies to all five modes.

### FR-04: Each mode supports `--no-pii` flag
Each CLI subcommand accepts `--no-pii` to skip PII stripping (for testing or when the document is already sanitized). This unblocks deferred tasks T033 and T035.

Blueprint mapping: product mode expansion framework — privacy tier integration.

### FR-05: Each mode outputs 3-color assessment
The review output for each mode follows the existing Green/Amber/Red assessment format:
- **Green**: All playbook positions are met or the document is in the preferred position.
- **Amber**: One or more positions are acceptable but not preferred; the document requires attention but is not a walkaway.
- **Red**: One or more positions are walkaway; the document should not be signed in its current form.

Blueprint mapping: product mode expansion framework — assessment format.

### FR-06: Each mode wired into VALID_MODES frozenset
The `VALID_MODES` frozenset in the benchmark validation module includes all five new mode keys: `franchisecheck`, `opcheck`, `partnercheck`, `sponsorcheck`, `distrocheck`.

Blueprint mapping: product modes framework — benchmark validation.

### FR-07: Each mode has at least one fixture PDF for E2E testing
A fixture PDF (or DOCX) file exists for each mode under `tests/fixtures/` with a naming convention matching the mode key and contract type. Each fixture MUST be parseable by the existing PDF parser (PyMuPDF) or DOCX parser (python-docx) without errors.

Fixture requirements:
- Must contain realistic contract language for the mode's domain
- Must include clauses that trigger at least two of the three assessment colors
- Must not contain real PII (use placeholder names and addresses)
- Must be small enough to parse in under 1 second (≤5 pages)

Blueprint mapping: product mode expansion framework — test infrastructure.

### FR-08: Each mode has a baseline entry in docs/benchmarks/
A per-mode baseline JSON file exists in `docs/benchmarks/` recording:
- Mode key and display name
- Fixture document identification
- Assessment result (expected Green/Amber/Red per clause position)
- Processing time budget (target ≤30 seconds end-to-end for a 5-page document)
- PII stripping time budget (target ≤3 seconds)

These baselines are used by the benchmark validation tooling to detect regressions.

Blueprint mapping: product mode expansion framework — benchmark framework.

### FR-09: DistroCheck and FranchiseCheck prompt templates include franchise-classification boundary flag
The DistroCheck and FranchiseCheck extraction prompt templates include a clause-level flag that identifies when a distribution or franchise agreement term (e.g., mandatory pricing control, operating standards, supplier restrictions, trademark license with significant control) may approach a franchise-like relationship under FTC Franchise Rule 16 CFR §436 or applicable state franchise law. The flag is rendered as `[FRANCHISE_BOUNDARY: yes|no|borderline]` in the extraction output. It is advisory only and does not constitute a legal classification.

Blueprint mapping: product mode expansion framework — cross-mode boundary detection.

### FR-10: OpCheck CLI --help text spells out "Operating Agreement"
The OpCheck subcommand's `--help` and the general `openreview opcheck --help` output MUST show the full name "Operating Agreement" with "OpCheck" as the shorthand command name. Example help text line:
```
  opcheck         Review an Operating Agreement (LLC governance document)
```

Blueprint mapping: product mode expansion framework — user-facing naming.

## Success Criteria

### SC-01: End-to-end invocation
Each of the five new modes can be invoked end-to-end from CLI: `openreview <mode> review <fixture-file>` succeeds, producing parse output, PII stripping, review assessment, and three-color output with memo PDF.

Measurement: CLI exit code 0, non-empty memo PDF in `./memo/`, stdout contains Green/Amber/Red assessment. All five modes pass.

### SC-02: VALID_MODES frozenset completeness
The `VALID_MODES` frozenset contains all five new mode keys: `franchisecheck`, `opcheck`, `partnercheck`, `sponsorcheck`, `distrocheck`.

Measurement: Import benchmark module, assert all five keys are in `VALID_MODES`.

### SC-03: E2E tests pass for all modes
E2E integration tests pass for all five modes. Each test:
- Invokes the CLI subcommand with a fixture document
- Verifies exit code 0
- Verifies stdout contains the expected assessment colors
- Verifies memo PDF is created

Measurement: `pytest tests/integration/ -k "test_franchisecheck or test_opcheck or test_partnercheck or test_sponsorcheck or test_distrocheck" --co` all pass.

### SC-04: Baseline JSON exists for all modes
Per-mode baseline JSON files exist in `docs/benchmarks/` for all five modes. Each baseline includes mode key, fixture path, expected assessment, and time budgets.

Measurement: `ls docs/benchmarks/` shows `franchisecheck.json`, `opcheck.json`, `partnercheck.json`, `sponsorcheck.json`, `distrocheck.json`.

### SC-05: `--no-pii` flag works for all modes
Each CLI subcommand accepts `--no-pii` and produces correct output (same assessment, no stripping) when invoked with the flag.

Measurement: `<mode> review --no-pii <fixture>` succeeds, output assessment matches invocation without `--no-pii`, and stdout confirms PII stripping was skipped.

### SC-06: DistroCheck prompts flag franchise-classification boundary
The DistroCheck extraction output includes the `[FRANCHISE_BOUNDARY:]` flag for at least one clause in the fixture document.

Measurement: Assert `FRANCHISE_BOUNDARY:` appears in DistroCheck extraction output for a fixture containing franchise-like distribution terms.

## Key Entities

| Entity | Description | Properties |
|--------|-------------|------------|
| **Playbook** | YAML file defining the three-position assessment framework for a contract domain | mode_key, positions (preferred/acceptable/walkaway), clauses, confidence thresholds |
| **ReviewReport** | The output of the three-agent review pipeline | mode_key, document_id, clause_assessments[], overall_color (Green/Amber/Red), timestamp, memo_path |
| **Mode** | A CLI-accessible product mode identified by a mode key | mode_key, display_name, description, playbook_file, cli_command, vocabulary_entry |
| **Assessment** | A per-clause or overall evaluation color | Green (preferred position), Amber (acceptable position, needs attention), Red (walkaway position) |
| **Fixture** | A test document (PDF or DOCX) used for E2E testing of a mode | mode_key, file_path, page_count, expected_assessment, contains_pii (bool) |
| **Baseline** | A JSON record of expected performance and accuracy for a mode on a fixture | mode_key, fixture_path, expected_colors{}, time_budget_s, pii_time_budget_s |

## Assumptions

### A-01: Pattern reuse from L-4a and L-4b (no new infrastructure)
The five new modes reuse the existing single-party review pipeline, CLI routing pattern (`_register_product_mode`), playbook YAML format, extraction prompt template pattern, three-agent verification pipeline, and test infrastructure. No new infrastructure, pipeline stages, or architectural changes are needed.

Risk: Low. Pattern has been validated across 17 prior modes.

### A-02: Multi-party semantics (single-party-first; Amber default for multi-party clauses)
Multi-party documents (franchise agreements between franchisor and multiple franchisees, partnership agreements with multiple partners, distribution agreements involving manufacturer-distributor-customer chains) are reviewed from one party's perspective only. The user selects their role (or the document context indicates it). Multi-party bilateral comparison is a deferred research gap — it would require new infrastructure (document graph, party-role mapping, bilateral negotiation logic) that is out of scope for the product-mode expansion. The single-party review pipeline defaults to Amber for any clause that the pipeline detects may involve multi-party rights or obligations that the single-party review cannot fully evaluate.

Rationale: Multi-party comparison would require new infrastructure (document graph, party-role mapping, bilateral negotiation logic) that is out of scope for the product-mode expansion. The Amber default ensures the user sees a caution flag without blocking the review.

Risk: Medium. Amber default may result in more cautious assessments for multi-party documents than a human reviewer would give. User-facing documentation and `--help` text should note this limitation.

### A-03: OpCheck = "Operating Agreement" (LLC governance document)
OpCheck reviews operating agreements for Limited Liability Companies (LLCs). The term "OpCheck" is a shorthand CLI command name. All user-facing text (help, output, memo) spells out "Operating Agreement". The playbook covers governance under state LLC acts (Delaware LLC Act, state equivalents). The tool does not distinguish between member-managed and manager-managed LLCs at the playbook level; the prompts include both patterns and assess based on the document's language.

Rationale: Operating agreements are the most common LLC governance document. The mode covers single-member and multi-member LLCs from the member's perspective. Manager-managed provisions are handled through the prompt template vocabulary.

### A-04: DistroCheck ↔ FranchiseCheck boundary is a known edge case
Distribution agreements and franchise agreements can overlap. A distribution agreement that includes significant franchisor-style controls (pricing, operating standards, mandatory supplies) may approach a franchise under FTC or state law. Both DistroCheck and FranchiseCheck include a franchise-classification boundary flag in their prompt templates to alert the user. The flag is advisory only — the tool does not classify documents as franchises or non-franchises.

Rationale: Legal classification of a business arrangement as a franchise is a fact-specific inquiry under the FTC Franchise Rule and state franchise laws. The tool does not and cannot make this determination. The boundary flag exists to inform the user that the agreement's terms may trigger regulatory requirements.

### A-05: No new dependencies needed
All five modes reuse existing dependencies:
- Document parsing: PyMuPDF (PDF), python-docx (DOCX)
- PII detection: Presidio Analyzer, Presidio Anonymizer
- AI model routing: litellm (via AI Gateway)
- CLI framework: typer
- Data models: pydantic
- Output formatting: rich
- Template rendering: Jinja2 (if template rendering is needed for prompts; otherwise string formatting)

No new runtime dependencies are required. No new dev dependencies are required.

### A-06: No public benchmark for these 5 contract types → custom corpus or mock-only baseline
No public benchmark dataset covers franchise agreements, operating agreements, partnership agreements, sponsorship agreements, or distribution agreements in the manner needed for single-party review assessment. Existing datasets (CUAD, MAUD, ContractNLI, LEDGAR) do not include these contract types. Baseline JSON files in `docs/benchmarks/` are generated from the fixture documents created for testing, not from a public corpus.

The benchmark therefore validates:
- Correctness: assessment matches expected values for known fixture content
- Performance: processing time meets budgets
- No regression: baselines detect changes to pipeline behavior

It does NOT validate:
- Generalization to unseen real-world documents (no public dataset exists)
- Comparison against human expert review for these specific contract types

Rationale: Creating a public benchmark for these five contract types is out of scope. The custom-corpus approach provides regression detection, which is the primary value of the benchmark for the product-mode expansion.

### A-07: Constitution Check — Principle I (Privacy First)
All five modes strip PII via Presidio before any external API call, following the existing PII stripping engine. The franchise-classification boundary flag in DistroCheck/FranchiseCheck prompts is advisory text only and does not transmit PII. Status: **Pass**.

### A-08: Constitution Check — Principle II (Local-First, CLI-Only)
All five modes are CLI subcommands with no web server or daemon. The one-network-path constraint (direct call to user's AI provider) applies uniformly. Status: **Pass**.

### A-09: Constitution Check — Principle III (Hardware-Bounded)
All five modes reuse the existing streaming parsers (page-by-page PDF, paragraph-by-paragraph DOCX). No new in-memory data structures beyond single-page processing. The 110 MB peak memory floor is unaffected. The NLP model memory exemption (Principle III) applies identically to all modes.

The mode count increase (17→22) does not increase per-invocation memory, because only one mode's assets (playbook, prompts) are loaded per invocation. Status: **Pass**.

### A-10: Constitution Check — Principle IV (Dependency Minimalism)
No new dependencies are required. The existing dependency set (PyMuPDF, python-docx, presidio, litellm, typer, pydantic, rich) covers all five modes. Status: **Pass**.

### A-11: Constitution Check — Principle V (Spec-Driven, YAGNI)
This specification exists before any implementation code for these five modes. The per-mode cost (playbook YAML + prompts + CLI wiring + tests) is the same minimum demonstrated across 17 prior modes. No speculative abstractions are introduced. Status: **Pass**.

## Out of Scope

### Multi-party bilateral comparison (deferred research gap)
The pipeline reviews from one party's perspective only. Comparing or reconciling obligations across multiple parties (franchisor vs. franchisee vs. territory manager; manufacturer vs. distributor vs. customer) requires new infrastructure (document graph, party-role mapping, bilateral negotiation analysis) that is a research gap flagged in the original blueprint. This spec does not address it.

### Tax or regulatory advice
OpCheck references IRC §704(b) (allocation of partnership/LLC tax items) as a clause-recognition feature in the extraction prompt. The tool does not provide tax advice, compute tax allocations, or validate §704(b) compliance. Users are directed to consult a tax professional for tax matters.

### Franchise registration services
The tool does not assist with franchise registration (FTC Franchise Rule filing requirements, state registration in franchise-registration states, renewal filings). The franchise-classification boundary flag is advisory only.

### State-specific LLC statute database
The OpCheck playbook references general principles of state LLC acts but does not maintain a database of state-specific requirements. Users in specific jurisdictions (e.g., Delaware, California, New York) should verify operating agreement provisions against their state's LLC statute.

### Public benchmark accuracy validation
No public benchmark dataset exists for these five contract types. The baseline JSON files are fixture-specific. Generalization to unseen documents is not validated by the benchmark harness (see Assumption A-06).

### Document format expansion
Only PDF and DOCX are supported for all modes. Scanned PDF (OCR) support via Docling is a separate capability and applies uniformly when available.
