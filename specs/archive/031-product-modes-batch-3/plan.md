# Implementation Plan: FranchiseCheck, OpCheck, PartnerCheck, SponsorCheck, DistroCheck

**Branch**: `feat/031-product-modes-batch-3` | **Date**: 2026-07-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/031-product-modes-batch-3/spec.md`

## Summary

Add five new product modes to the `openreview` CLI for entity-formation and multi-party contract types: **FranchiseCheck** (franchise agreements/FDDs), **OpCheck** (LLC operating agreements), **PartnerCheck** (partnership agreements), **SponsorCheck** (sponsorship agreements), **DistroCheck** (distribution/reseller agreements). This is the final batch (batch 3 of 3), completing the 22-mode product line. Each mode reuses the existing single-party review pipeline — playbook YAML, extraction prompt template, three-agent verification, three-color output, memo export. No pipeline changes required. Follows the pattern established by L-4a (spec 028, 6 modes) and L-4b (spec 029, 5 modes + 9 orphan wiring).

Key differences from prior batches: multi-party complexity (franchisor-franchisee-territory, LLC members-managers, manufacturer-distributor-customer) handled by single-party-first with Amber default for multi-party clauses. Franchise-classification boundary flags in DistroCheck and FranchiseCheck prompt templates.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: No new runtime dependencies. Reuses existing stack: httpx, pydantic, rich, typer, PyMuPDF, python-docx, presidio-analyzer, presidio-anonymizer, cryptography, litellm, questionary, platformdirs, pyyaml.

**Storage**: SQLite (existing database layer) — no new tables required. Playbooks stored as YAML files in `src/openreview_cli/review/playbooks/`.

**Testing**: pytest (existing suite). Unit tests for playbook schema validation. Integration tests per mode with fixture documents. E2E tests in the orphan-modes pattern. Baseline JSON validation in benchmark tooling.

**Target Platform**: Linux, macOS, Windows (CLI)

**Project Type**: CLI tool (single-party contract review modes)

**Performance Goals**: <100 MB peak memory budget (110 MB hard floor, per constitution). No new memory pressure from playbook-only changes. Parse + assess within existing pipeline timing. Per-fixture processing ≤30s end-to-end (5-page document). PII stripping ≤3s.

**Constraints**: Same constraints as established single-party review pipeline. No per-mode model routing overrides (task-level routing only). Single-party review only; multi-party bilateral comparison deferred. SLM-first/task-level model routing.

**Scale/Scope**: Five new CLI subcommands, five playbook YAML files, five extraction prompt templates, five integration test files, five fixture documents, five baseline JSON files, updated unit tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Privacy First | **Pass** | All five modes reuse existing PII stripping engine identically. No new PII-related code. PII stripped before any external API call. Franchise-classification boundary flag is advisory text only, no PII. |
| II. Local-First, CLI-Only | **Pass** | No server, no daemon, no telemetry. Five new subcommands on existing CLI-only architecture. All modes operable offline with local model slots. |
| III. Hardware-Bounded | **Pass** | Playbook-only changes + prompt additions. <1 MB additional per mode. No new parsers, no new in-memory collections. Streaming parsers reused. NLP model memory exemption applies identically. |
| IV. Dependency Minimalism | **Pass** | Zero new runtime dependencies. Reuses existing deps for YAML parsing (pyyaml) and prompt management. No new packages. |
| V. Spec-Driven, YAGNI | **Pass** | Spec 031 defined before implementation. No speculative abstractions. Each mode = minimal change set: playbook + prompt + CLI wiring. No per-mode model overrides, no multi-party review, no custom output templates. |

**Constitution Gate Verdict**: PASS — all five principles satisfied.

## Project Structure

### Documentation (this feature)

```
specs/031-product-modes-batch-3/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 design
├── quickstart.md        # Phase 1 validation scenarios
├── contracts/           # Phase 1 CLI contracts (5 files)
│   ├── FRANCHISECHECK.md
│   ├── OPCHECK.md
│   ├── PARTNERCHECK.md
│   ├── SPONSORCHECK.md
│   └── DISTROCHECK.md
├── tasks.md             # Phase 2 output (speckit.tasks)
└── spec.md              # Feature specification
```

### Source Code (repository root)

No new source directories. Changes to these existing files:

```
src/openreview_cli/
├── review/
│   ├── playbooks/
│   │   ├── precheck-nda-v1.yaml             # existing
│   │   ├── franchise-v1.yaml                # new
│   │   ├── operating-agreement-v1.yaml      # new
│   │   ├── partnership-v1.yaml              # new
│   │   ├── sponsorship-v1.yaml              # new
│   │   └── distribution-v1.yaml             # new
│   ├── prompts.py                           # append 5 mode entries to MODE_VOCABULARY
│   └── playbook.py                          # register 5 new playbooks in BUNDLED_PLAYBOOKS
├── benchmark/
│   ├── cli.py                               # add 5 mode keys to VALID_MODES frozenset
│   └── baseline.py                          # no changes needed (dynamic loading)
└── app.py                                   # append 5 CLI subcommands via _register_product_mode

tests/
├── unit/
│   └── test_playbook_schema.py              # add 5 playbook validation tests
├── integration/
│   ├── test_franchisecheck.py               # new
│   ├── test_opcheck.py                      # new
│   ├── test_partnercheck.py                 # new
│   ├── test_sponsorcheck.py                 # new
│   └── test_distrocheck.py                  # new
└── fixtures/
    ├── franchise-agreement.pdf              # new
    ├── operating-agreement.pdf              # new
    ├── partnership-agreement.pdf            # new
    ├── sponsorship-agreement.pdf            # new
    └── distribution-agreement.pdf           # new

docs/benchmarks/
├── franchisecheck.json                      # new
├── opcheck.json                             # new
├── partnercheck.json                        # new
├── sponsorcheck.json                        # new
└── distrocheck.json                         # new
```

**Structure Decision**: Follows existing single-mode pattern from L-4a and L-4b. No new directories, no new abstractions. Each mode = playbook YAML file + prompt template entry + CLI wiring + fixture + test + baseline.

## Implementation Order

Each mode is independent. Implementation proceeds sequentially for testability.

### Mode 1: FranchiseCheck

| File | Action | Purpose |
|------|--------|---------|
| `src/openreview_cli/review/playbooks/franchise-v1.yaml` | Create | 5-category playbook (franchise fee, territory, renewal/termination, advertising/marketing, transfer/assignment) |
| `src/openreview_cli/review/prompts.py` | Modify | Add `"franchisecheck"` entry to `MODE_VOCABULARY` |
| `src/openreview_cli/review/playbook.py` | Modify | Register `franchise-v1.yaml` in `BUNDLED_PLAYBOOKS` |
| `src/openreview_cli/app.py` | Modify | Add `franchisecheck` CLI subcommand |
| `src/openreview_cli/benchmark/cli.py` | Modify | Add `"franchisecheck"` to `VALID_MODES` |
| `tests/fixtures/franchise-agreement.pdf` | Create | Test document |
| `tests/unit/test_playbook_schema.py` | Modify | Add `franchise-v1` schema validation test |
| `tests/integration/test_franchisecheck.py` | Create | E2E flow |
| `docs/benchmarks/franchisecheck.json` | Create | Baseline JSON |

**Playbook categories**: Franchise fee structure, Territory rights and exclusivity, Renewal and termination, Advertising and marketing fund, Transfer/assignment restrictions

**Prompt vocabulary**: franchise, franchisor, franchisee, FDD, territory, royalty, advertising fund, renewal, termination, non-compete, transfer, right of first refusal, franchise fee

**CLI wiring** (via `_register_product_mode`):
```python
_register_product_mode(
    app,
    name="franchisecheck",
    help_text="Review a franchise agreement or franchise disclosure document.",
    path_help="Path to a franchise agreement or FDD (PDF or DOCX).",
)
```

### Mode 2: OpCheck

| File | Action | Purpose |
|------|--------|---------|
| `src/openreview_cli/review/playbooks/operating-agreement-v1.yaml` | Create | 5-category playbook (membership, contributions, allocations, voting, transfer/dissolution) |
| `src/openreview_cli/review/prompts.py` | Modify | Add `"opcheck"` entry to `MODE_VOCABULARY` |
| `src/openreview_cli/review/playbook.py` | Modify | Register `operating-agreement-v1.yaml` in `BUNDLED_PLAYBOOKS` |
| `src/openreview_cli/app.py` | Modify | Add `opcheck` CLI subcommand |
| `src/openreview_cli/benchmark/cli.py` | Modify | Add `"opcheck"` to `VALID_MODES` |
| `tests/fixtures/operating-agreement.pdf` | Create | Test document |
| `tests/unit/test_playbook_schema.py` | Modify | Add `operating-agreement-v1` schema validation test |
| `tests/integration/test_opcheck.py` | Create | E2E flow |
| `docs/benchmarks/opcheck.json` | Create | Baseline JSON |

**Playbook categories**: Membership structure (member-managed vs. manager-managed), Capital contributions and additional calls, Profit/loss allocation (IRC §704(b)), Voting rights and decision-making, Transfer restrictions and dissolution

**Prompt vocabulary**: operating agreement, LLC, member, manager, capital contribution, capital call, profit share, distribution, voting, transfer, buy-sell, dissolution, indemnification, IRC 704(b)

**CLI naming note**: CLI help text MUST spell out "Operating Agreement" — see spec FR-10 and Assumption A-03.

**CLI wiring**:
```python
_register_product_mode(
    app,
    name="opcheck",
    help_text="Review an Operating Agreement (LLC governance document).",
    path_help="Path to an operating agreement (PDF or DOCX).",
)
```

### Mode 3: PartnerCheck

| File | Action | Purpose |
|------|--------|---------|
| `src/openreview_cli/review/playbooks/partnership-v1.yaml` | Create | 5-category playbook (contributions, management, withdrawal, liability, dispute resolution) |
| `src/openreview_cli/review/prompts.py` | Modify | Add `"partnercheck"` entry to `MODE_VOCABULARY` |
| `src/openreview_cli/review/playbook.py` | Modify | Register `partnership-v1.yaml` in `BUNDLED_PLAYBOOKS` |
| `src/openreview_cli/app.py` | Modify | Add `partnercheck` CLI subcommand |
| `src/openreview_cli/benchmark/cli.py` | Modify | Add `"partnercheck"` to `VALID_MODES` |
| `tests/fixtures/partnership-agreement.pdf` | Create | Test document |
| `tests/unit/test_playbook_schema.py` | Modify | Add `partnership-v1` schema validation test |
| `tests/integration/test_partnercheck.py` | Create | E2E flow |
| `docs/benchmarks/partnercheck.json` | Create | Baseline JSON |

**Playbook categories**: Capital contributions and profit/loss allocation, Management authority and decision-making, Withdrawal, expulsion, and dissolution, Liability allocation and indemnification, Dispute resolution (mediation/arbitration)

**Prompt vocabulary**: partnership, general partner, limited partner, capital contribution, profit share, loss allocation, management, withdrawal, expulsion, dissolution, joint and several liability, UPA, RUPA, non-compete, non-solicit, mediation, arbitration

**Playbook distinguishing factor vs. OpCheck**: Liability focus — PartnerCheck prioritizes personal liability exposure (joint and several) vs. OpCheck's limited-liability default.

**CLI wiring**:
```python
_register_product_mode(
    app,
    name="partnercheck",
    help_text="Review a general or limited partnership agreement.",
    path_help="Path to a partnership agreement (PDF or DOCX).",
)
```

### Mode 4: SponsorCheck

| File | Action | Purpose |
|------|--------|---------|
| `src/openreview_cli/review/playbooks/sponsorship-v1.yaml` | Create | 5-category playbook (fee, benefits, IP, termination, indemnification) |
| `src/openreview_cli/review/prompts.py` | Modify | Add `"sponsorcheck"` entry to `MODE_VOCABULARY` |
| `src/openreview_cli/review/playbook.py` | Modify | Register `sponsorship-v1.yaml` in `BUNDLED_PLAYBOOKS` |
| `src/openreview_cli/app.py` | Modify | Add `sponsorcheck` CLI subcommand |
| `src/openreview_cli/benchmark/cli.py` | Modify | Add `"sponsorcheck"` to `VALID_MODES` |
| `tests/fixtures/sponsorship-agreement.pdf` | Create | Test document |
| `tests/unit/test_playbook_schema.py` | Modify | Add `sponsorship-v1` schema validation test |
| `tests/integration/test_sponsorcheck.py` | Create | E2E flow |
| `docs/benchmarks/sponsorcheck.json` | Create | Baseline JSON |

**Playbook categories**: Sponsorship fee and payment schedule, Sponsorship rights and benefits (logo/recognition/exclusivity), IP license (use of sponsor's trademarks), Termination for breach or force majeure, Indemnification and non-disparagement

**Prompt vocabulary**: sponsorship, sponsor, organizer, fee, payment, exclusivity, logo placement, event recognition, trademark license, termination, force majeure, indemnification, non-disparagement

**CLI wiring**:
```python
_register_product_mode(
    app,
    name="sponsorcheck",
    help_text="Review a sponsorship agreement.",
    path_help="Path to a sponsorship agreement (PDF or DOCX).",
)
```

### Mode 5: DistroCheck

| File | Action | Purpose |
|------|--------|---------|
| `src/openreview_cli/review/playbooks/distribution-v1.yaml` | Create | 5-category playbook (territory, minimums, pricing, IP, termination) |
| `src/openreview_cli/review/prompts.py` | Modify | Add `"distrocheck"` entry to `MODE_VOCABULARY` |
| `src/openreview_cli/review/playbook.py` | Modify | Register `distribution-v1.yaml` in `BUNDLED_PLAYBOOKS` |
| `src/openreview_cli/app.py` | Modify | Add `distrocheck` CLI subcommand |
| `src/openreview_cli/benchmark/cli.py` | Modify | Add `"distrocheck"` to `VALID_MODES` |
| `tests/fixtures/distribution-agreement.pdf` | Create | Test document |
| `tests/unit/test_playbook_schema.py` | Modify | Add `distribution-v1` schema validation test |
| `tests/integration/test_distrocheck.py` | Create | E2E flow |
| `docs/benchmarks/distrocheck.json` | Create | Baseline JSON |

**Playbook categories**: Territory definition and exclusivity, Minimum purchase requirements and cure periods, Pricing, payment, and inventory terms, IP license (manufacturer's trademarks), Termination rights, non-compete, and channel restrictions

**Prompt vocabulary**: distribution, distributor, manufacturer, territory, exclusivity, minimum purchase, cure period, pricing, payment, inventory, returns, trademark license, termination, non-compete, channel restriction, jurisdiction, venue

**FR-9: Franchise-classification boundary flag**: The DistroCheck (and FranchiseCheck) extraction prompts include a clause-level `[FRANCHISE_BOUNDARY: yes|no|borderline]` flag. When a distribution agreement term (pricing control, operating standards, mandatory supplier mandates) approaches franchise-like regulation under FTC Franchise Rule 16 CFR §436 or state law, the flag renders as `yes` or `borderline`. Advisory only — no legal classification.

**CLI wiring**:
```python
_register_product_mode(
    app,
    name="distrocheck",
    help_text="Review a distribution or reseller agreement.",
    path_help="Path to a distribution agreement (PDF or DOCX).",
)
```

## Dependencies

| What | Spec Ref | Status |
|------|----------|--------|
| Single-party review pipeline | Established pattern | Complete, production-ready |
| Three-color confidence | Established pattern | Complete |
| Memo export | Established pattern | Complete |
| Prompt management / MODE_VOCABULARY | Established pattern | Complete |
| Playbook versioning / BUNDLED_PLAYBOOKS | Established pattern | Complete |
| Playbook schema (3-position, 3-5 questions) | Established pattern | Complete |
| Benchmark baseline + VALID_MODES | FR-06 | Complete (spec 030) |
| Franchise-classification boundary flag | FR-09 | New prompt template feature (DistroCheck + FranchiseCheck) |

## Architecture Implications

| Implication | Source | Impact |
|------------|--------|--------|
| Multi-party complexity handled single-party-first | A-02 | Amber default for multi-party clauses the pipeline cannot fully evaluate. User-facing docs note limitation. |
| Amber default for uncertain matches | Established pattern | All five modes use same thresholds as existing modes. |
| DistroCheck ↔ FranchiseCheck boundary flag | FR-09, A-04 | Both prompt templates get franchise-classification boundary flag. Advisory only. |
| OpCheck ↔ PartnerCheck overlap | Spec S3 edge case | Playbooks distinguish by liability type (limited vs. joint/several). User chooses mode by entity type. |
| OpCheck "Operating Agreement" naming | FR-10, A-03 | CLI help text spells out full name. "OpCheck" is shorthand only. |
| Per-mode model routing not supported | Established pattern | All five modes use same model slot config as existing modes. Task-level routing only. |
| Citation grounding required on every claim | Established pattern | All five modes reuse existing citation grounding. No changes. |
| Playbook-only changes; no pipeline modifications | A-01 | Each mode adds <1 KB to MODE_VOCABULARY dict, one YAML file, one CLI function. |
| Baseline from custom fixtures, not public corpus | A-06 | No public benchmark for these contract types. Baselines are fixture-specific for regression detection. |

## Risks

1. **Multi-party Amber ceiling** — Amber default for multi-party clauses may produce more cautious assessments than a human reviewer. Mitigation: document limitation in help text and memo. Revisit when multi-party comparison research gap is addressed.
2. **Franchise classification boundary false positives** — The `[FRANCHISE_BOUNDARY:]` flag may trigger on standard distribution terms (pricing, quality standards) that are not franchise-like. Mitigation: flag is advisory only, disclaimer in help text and output.
3. **OpCheck/PartnerCheck mode confusion** — User may run OpCheck on a partnership agreement or vice versa. Mitigation: help text clarifies entity-type distinction. Prompt templates guide via MODE_VOCABULARY domain text.
4. **Fixture quality** — Synthetic fixtures may not capture real-world clause variation. Mitigation: fixtures designed to trigger 2+ assessment colors; benchmark is regression-detection only, not generalization validation.
5. **22-mode sustainability** — Each mode adds maintenance surface. Mitigation: simpler playbook format (3-5 categories) for all modes keeps maintenance low. No per-mode pipeline customization.

## Test Plan

### Unit Tests

| Test | File | What it validates |
|------|------|-------------------|
| Playbook schema validation (×5) | `test_playbook_schema.py` | Each playbook YAML passes `load_playbook()` without error |
| Prompt vocabulary keys (×5) | Existing prompt tests | Each mode key exists in `MODE_VOCABULARY` with non-empty domain/vocabulary |
| VALID_MODES completeness | `test_benchmark_modes.py` | All five mode keys are in `VALID_MODES` frozenset |

### Integration Tests

| Test | File | What it validates |
|------|------|-------------------|
| FranchiseCheck E2E | `test_franchisecheck.py` | Parse → assess → output with `"mode": "franchisecheck"` |
| OpCheck E2E | `test_opcheck.py` | Parse → assess → output with `"mode": "opcheck"` |
| PartnerCheck E2E | `test_partnercheck.py` | Parse → assess → output with `"mode": "partnercheck"` |
| SponsorCheck E2E | `test_sponsorcheck.py` | Parse → assess → output with `"mode": "sponsorcheck"` |
| DistroCheck E2E | `test_distrocheck.py` | Parse → assess → output with `"mode": "distrocheck"` |

### Fixture Documents

Five fixture PDFs, each:
- Well-formed, valid PDF (no scanned images)
- 1-5 pages covering the mode's contract type
- Contains at least one clause matching each playbook category
- Triggers at least two of three assessment colors
- No real PII (placeholder names and addresses)
- Parseable in under 1 second
- English language
- Small-business-relevant factual scenario

### Verification Checklist

- [ ] `uv run openreview --help` lists all 5 new subcommands
- [ ] Each subcommand `--help` shows mode-specific help text (OpCheck shows "Operating Agreement")
- [ ] Each mode produces valid JSON via `--format json` with correct `mode` field
- [ ] Each playbook passes schema validation (`load_playbook()`)
- [ ] Memo export produces file > 1 KB with mode name prefix
- [ ] PII stripping produces identical placeholders across modes
- [ ] `--no-pii` flag preserves raw text
- [ ] `VALID_MODES` frozenset contains all 5 mode keys
- [ ] DistroCheck extraction output includes `[FRANCHISE_BOUNDARY:]` flag
- [ ] FranchiseCheck extraction output includes `[FRANCHISE_BOUNDARY:]` flag
- [ ] 5 baseline JSON files exist in `docs/benchmarks/`
- [ ] All tests pass in CI environment
