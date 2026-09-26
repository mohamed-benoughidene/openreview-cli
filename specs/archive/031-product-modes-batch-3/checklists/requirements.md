# Requirements Checklist — Spec 031: Product Modes Batch 3

**Feature**: FranchiseCheck, OpCheck, PartnerCheck, SponsorCheck, DistroCheck
**Stage**: Specify (pre-implementation)
**Last Updated**: 2026-07-09

---

## Scope & Coverage

- [ ] All 5 modes are listed in the Overview table with contract type and playbook file name
- [ ] Each mode references the correct playbook YAML from existing naming convention (`<mode>-v1.yaml`)
- [ ] No orphan-mode wiring is included (orphans were handled in spec 029)

## User Scenarios (S1–S5)

### S1: FranchiseCheck
- [ ] Contract type: franchise agreement / FDD
- [ ] User: prospective franchisee
- [ ] 3-color assessment flow demonstrated (Green/Amber/Red examples)
- [ ] Edge case: franchise-classification boundary flag mentioned
- [ ] Why-priority rationale present

### S2: OpCheck
- [ ] Contract type: operating agreement (LLC governance)
- [ ] User: LLC member
- [ ] 3-color assessment flow demonstrated
- [ ] Term "Operating Agreement" spelled out (not "Op Agreement")
- [ ] IRC §704(b) referenced only as clause-recognition feature, not tax advice
- [ ] Why-priority rationale present

### S3: PartnerCheck
- [ ] Contract type: general/limited partnership agreement
- [ ] User: incoming partner
- [ ] 3-color assessment flow demonstrated
- [ ] Edge case: PartnerCheck vs. OpCheck overlap explicitly addressed with distinguishing criteria
- [ ] Joint and several personal liability mentioned as key risk
- [ ] Why-priority rationale present

### S4: SponsorCheck
- [ ] Contract type: sponsorship agreement
- [ ] User: nonprofit/event organizer
- [ ] 3-color assessment flow demonstrated
- [ ] Why-priority rationale present

### S5: DistroCheck
- [ ] Contract type: distribution/reseller agreement
- [ ] User: prospective distributor
- [ ] 3-color assessment flow demonstrated
- [ ] Edge case: DistroCheck vs. FranchiseCheck boundary explicitly addressed
- [ ] Franchise-classification boundary flag mentioned
- [ ] Why-priority rationale present

## Functional Requirements

### FR-01: Bundled playbook YAML
- [ ] Each mode has a playbook YAML file
- [ ] Playbook follows 3-position (preferred/acceptable/walkaway) format
- [ ] Playbook parses without error by `Playbook.load()`
- [ ] Blueprint mapping cited (product modes framework reference)

### FR-02: MODE_VOCABULARY entry
- [ ] Each mode has a MODE_VOCABULARY dictionary entry
- [ ] Entry includes: mode_key, display_name, description, playbook_file
- [ ] Blueprint mapping cited (product modes framework reference)

### FR-03: CLI subcommand
- [ ] Each mode has Typer subcommand via `_register_product_mode` pattern
- [ ] CLI command matches table (e.g., `openreview franchisecheck review <file>`)
- [ ] Subcommand accepts PDF or DOCX file path
- [ ] Subcommand produces 3-color assessment and memo PDF
- [ ] Subcommand discoverable via `openreview --help`
- [ ] Blueprint mapping cited (product modes framework reference)

### FR-04: `--no-pii` flag
- [ ] Each CLI subcommand accepts `--no-pii`
- [ ] T033/T035 unblock explicitly mentioned
- [ ] Blueprint mapping cited (product mode expansion framework reference)

### FR-05: 3-color assessment output
- [ ] Output format: Green/Amber/Red
- [ ] Green: all preferred positions met
- [ ] Amber: acceptable positions, attention needed
- [ ] Red: walkaway position present
- [ ] Blueprint mapping cited (product mode expansion framework reference)

### FR-06: VALID_MODES frozenset
- [ ] All 5 mode keys in VALID_MODES: `franchisecheck`, `opcheck`, `partnercheck`, `sponsorcheck`, `distrocheck`
- [ ] Blueprint mapping cited (product modes framework reference)

### FR-07: Fixture PDF for E2E testing
- [ ] Each mode has at least one fixture file under `tests/fixtures/`
- [ ] Fixture parseable by PyMuPDF (PDF) or python-docx (DOCX)
- [ ] Fixture contains realistic contract language
- [ ] Fixture triggers at least 2 assessment colors
- [ ] Fixture contains no real PII
- [ ] Fixture ≤5 pages, parses in <1 second
- [ ] Blueprint mapping cited (product mode expansion framework reference)

### FR-08: Baseline entry in docs/benchmarks/
- [ ] Each mode has baseline JSON in `docs/benchmarks/`
- [ ] Baseline includes: mode key, display name, fixture path, expected colors, time budgets
- [ ] Blueprint mapping cited (product mode expansion framework reference)

### FR-09: DistroCheck franchise-classification boundary flag
- [ ] DistroCheck extraction prompt includes `[FRANCHISE_BOUNDARY: yes|no|borderline]` flag
- [ ] Flag is advisory only (no legal classification)
- [ ] Blueprint mapping cited (product mode expansion framework reference)

### FR-10: OpCheck --help spells "Operating Agreement"
- [ ] `openreview opcheck --help` shows full name "Operating Agreement" not "Op Agreement"
- [ ] Blueprint mapping cited (product mode expansion framework reference)

## Success Criteria

- [ ] SC-01: E2E invocation passes for all 5 modes
- [ ] SC-02: VALID_MODES frozenset contains all 5 keys
- [ ] SC-03: E2E integration tests pass for all 5 modes
- [ ] SC-04: Baseline JSON files exist for all 5 modes
- [ ] SC-05: `--no-pii` flag works for all 5 modes
- [ ] SC-06: DistroCheck extraction output contains `FRANCHISE_BOUNDARY:` flag

## Key Entities

- [ ] Playbook entity defined (mode_key, positions, clauses, thresholds)
- [ ] ReviewReport entity defined (mode_key, clause_assessments, overall_color, memo_path)
- [ ] Mode entity defined (mode_key, display_name, playbook_file, cli_command, vocabulary_entry)
- [ ] Assessment entity defined (Green/Amber/Red)
- [ ] Fixture entity defined (mode_key, file_path, page_count, expected_assessment, contains_pii)
- [ ] Baseline entity defined (mode_key, fixture_path, expected_colors, time_budgets)

## Assumptions

- [ ] A-01: Pattern reuse from L-4a/L-4b — no new infrastructure needed
- [ ] A-02: Multi-party semantics — single-party-first with Amber default; multi-party comparison gap documented
- [ ] A-03: OpCheck = "Operating Agreement" (LLC governance), spelled out in user-facing text
- [ ] A-04: DistroCheck ↔ FranchiseCheck boundary is known edge case
- [ ] A-05: No new dependencies needed — existing deps sufficient
- [ ] A-06: No public benchmark for these 5 types — custom corpus / mock-only baseline

## Constitution Check

- [ ] Principle I (Privacy First): Pass — PII stripped before API call, boundary flag is advisory text
- [ ] Principle II (Local-First, CLI-Only): Pass — no server, no daemon
- [ ] Principle III (Hardware-Bounded): Pass — streaming parsers, no new per-invocation memory
- [ ] Principle IV (Dependency Minimalism): Pass — no new dependencies
- [ ] Principle V (Spec-Driven, YAGNI): Pass — spec before code, minimum per-mode cost

## Out of Scope Check

- [ ] Multi-party bilateral comparison (deferred research gap) explicitly excluded
- [ ] Tax/regulatory advice explicitly excluded (OpCheck IRC §704(b) is recognition only)
- [ ] Franchise registration services explicitly excluded
- [ ] State-specific LLC statute database explicitly excluded
- [ ] Public benchmark accuracy validation explicitly excluded
- [ ] Document format expansion explicitly excluded (PDF/DOCX only)

## Blueprint Code Leak Check

- [ ] No product-mode-expansion capability codes in spec (mode source list references allowed)
- [ ] No multi-party-comparison-gap codes in spec
- [ ] No legal-section-number references
- [ ] No technology-readiness-level references
- [ ] No product-mode-framework codes in spec (mode source list references allowed)
- [ ] Spec-internal codes only: FR-N, SC-N, US-N, AC-N, T-NNN, D-N

## Cross-Reference Check

- [ ] All FR-N have corresponding SC-N verification
- [ ] All SC-N are measurable and technology-agnostic
- [ ] All assumptions reference risk level
- [ ] Out-of-scope items have rationale
