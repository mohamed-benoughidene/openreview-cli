# Research: Product Modes Batch 3 — FranchiseCheck, OpCheck, PartnerCheck, SponsorCheck, DistroCheck

**Date**: 2026-07-09
**Phase**: Phase 0 (Research)
**Status**: Complete — no NEEDS CLARIFICATION remaining

## Method

Per-mode research conducted via pattern analysis of prior batches (L-4a spec 028, L-4b spec 029), existing codebase archetypes (playbook format, MODE_VOCABULARY, CLI wiring, test patterns), and spec 031 assumptions. Five research topics resolved below.

## Research Questions

### Q1: Pattern reuse from specs 028/029

**Finding**: Prior batches established a stable pattern that L-4c should replicate exactly. No new infrastructure, no pipeline changes, no new abstractions.

| Aspect | L-4a (028) Pattern | L-4b (029) Pattern | L-4c (031) Decision |
|--------|-------------------|-------------------|---------------------|
| CLI wiring | `_register_product_mode()` helper in `app.py` | Same | Reuse |
| Playbook location | `src/openreview_cli/review/playbooks/` | Same | Reuse |
| MODE_VOCABULARY dict | `prompts.py` | Same | Reuse |
| BUNDLED_PLAYBOOKS | `playbook.py` registration | Same | Reuse |
| VALID_MODES frozenset | `benchmark/cli.py` | Same | Reuse |
| Integration tests | `test_<mode>.py` per mode | Same | Reuse |
| Fixture format | Synthetic PDF, ≤5 pages | Same | Reuse |
| Baseline JSON | Single fixture per mode, 2+ colors | Same | Reuse |

**Key difference from prior batches**: Franchise-classification boundary flag (FR-09) is a new prompt-template feature for DistroCheck and FranchiseCheck. Implementation: add `[FRANCHISE_BOUNDARY: yes|no|borderline]` instruction to both extraction prompts. No pipeline changes.

**Key difference from prior batches**: OpCheck help text must spell out "Operating Agreement" (FR-10). This is a CLI help string change only.

**Sources**: specs/028-product-modes-batch-1/plan.md, specs/029-product-modes-batch-2/plan.md

### Q2: Fixture PDF sourcing strategy

**Finding**: Five fixture PDFs needed (one per mode). Prior batches used synthetic PDFs generated inline in tests or placed in `tests/fixtures/`. Decision: generate synthetic fixtures using the same approach as prior batches.

| Mode | Fixture File | Contract Type | Pages | Assessment Colors Triggered |
|------|-------------|---------------|-------|----------------------------|
| FranchiseCheck | `franchise-agreement.pdf` | Franchise agreement (FDD excerpt + franchise terms) | 3-5 | Green (territory rights), Amber (ad fund contribution cap), Red (unilateral termination) |
| OpCheck | `operating-agreement.pdf` | LLC operating agreement | 3-5 | Green (member-managed with equal voting), Amber (capital call provisions), Red (disproportionate voting dilution) |
| PartnerCheck | `partnership-agreement.pdf` | General partnership agreement | 3-5 | Green (clear profit allocation), Amber (for-cause expulsion), Red (joint/several liability without shield) |
| SponsorCheck | `sponsorship-agreement.pdf` | Event sponsorship agreement | 2-3 | Green (mutual termination with cure), Amber (broad exclusivity clause), Red (unilateral indemnification) |
| DistroCheck | `distribution-agreement.pdf` | Distribution/reseller agreement | 3-5 | Green (defined territory), Amber (minimum purchase without market adjustment), Red (boundary-flag franchise-like control terms) |

**Decision**: Synthetic fixtures. Rationale:
- Real contracts may contain PII (even redacted, raises privacy concerns for test repo)
- Real contracts are copyrighted by law firms
- Synthetic fixtures can be precisely designed to trigger specific assessment colors
- Prior batches (028, 029) used synthetic fixtures successfully

**Edge case — franchise boundary in DistroCheck fixture**: The DistroCheck fixture MUST include at least one clause (pricing control, operating standards, or mandatory supplier requirement) that triggers the `[FRANCHISE_BOUNDARY: borderline]` flag.

### Q3: Baseline JSON format from spec 030

**Finding**: Baseline JSON format defined by `src/openreview_cli/benchmark/baseline.py`. Each baseline records:

```json
{
  "mode_key": "franchisecheck",
  "display_name": "FranchiseCheck",
  "fixture": "tests/fixtures/franchise-agreement.pdf",
  "expected_assessment": {
    "overall_color": "AMBER",
    "per_category": {
      "franchise-fee": {"position": "acceptable", "color": "AMBER"},
      "territory-rights": {"position": "preferred", "color": "GREEN"},
      "renewal-termination": {"position": "walkaway", "color": "RED"},
      "advertising-fund": {"position": "acceptable", "color": "AMBER"},
      "transfer-assignment": {"position": "acceptable", "color": "AMBER"}
    }
  },
  "time_budget_s": 30,
  "pii_time_budget_s": 3,
  "page_count": 5
}
```

**Decision**: Create 5 baseline JSON files matching this format. Per-mode assessment colors must align with fixture content.

**Sources**: `src/openreview_cli/benchmark/baseline.py` — Baseline class uses `mode_key`, `fixture`, `expected_assessment`, `time_budget_s`, `pii_time_budget_s`.

### Q4: DistroCheck ↔ FranchiseCheck boundary detection

**Finding**: DistroCheck and FranchiseCheck both require a franchise-classification boundary flag (FR-09, Assumption A-04). This is a cross-mode boundary detection feature.

**Implementation approach**: Add `[FRANCHISE_BOUNDARY: yes|no|borderline]` instruction to both extraction prompt templates. The prompt instructs the LLM to evaluate each clause against FTC Franchise Rule 16 CFR §436 criteria:
1. Trademark license (franchisor grants right to use trademark)
2. Significant control or assistance (franchisor exercises significant control over operations)
3. Franchise fee (franchisee pays a fee)

If a clause meets 2+ criteria, flag `borderline`. If it meets all 3 criteria, flag `yes`.

**Separation from FranchiseCheck**: FranchiseCheck always flags `yes` for franchise-like clauses (the document is presumed to be a franchise). The boundary flag in FranchiseCheck identifies clauses that may NOT qualify as franchise terms despite the document label. DistroCheck flags when a distribution agreement term may approach franchise territory.

**CLI help text**: Both modes should mention the boundary flag. Example text for DistroCheck `--help`:
> "Note: This tool includes a franchise-classification boundary flag that alerts you when distribution terms may approach a franchise-like relationship under FTC or state law. This flag is advisory only and does not constitute legal classification."

**Sources**: FTC Franchise Rule 16 CFR §436, spec.md FR-09, Assumption A-04.

### Q5: OpCheck "Operating Agreement" naming

**Finding**: Spec FR-10 and Assumption A-03 require OpCheck CLI help text to spell out "Operating Agreement". The shorthand "OpCheck" is the command name only.

**Text that must appear in user-facing output**:

| Location | Text |
|----------|------|
| `openreview opcheck --help` first line | `Review an Operating Agreement (LLC governance document)` |
| Default extraction prompt specialization | `specializing in operating agreements` |
| `openreview --help` product modes list | `opcheck         Review an Operating Agreement (LLC governance document)` |
| Memo PDF filename prefix | `{filename}-opcheck.pdf` (uses shorthand — follows existing convention) |
| Memo document title | `OpCheck — Operating Agreement Review` (shorthand + full name) |

**Rationale**: "OpCheck" is unambiguous to users familiar with the product line but meaningless to new users. Spelling out "Operating Agreement" in help text and memo titles provides discoverability without renaming the CLI command (which would break the mode naming convention and require a MAJOR constitutional amendment per Constraints section).

**Sources**: spec.md FR-10, Assumption A-03.

## Architecture Implications

| Implication | Source | Impact |
|-------------|--------|--------|
| Pipeline reuse confirmed for all 5 modes | A-01 | No pipeline changes needed |
| Playbook-only changes: no new deps | A-05 | Zero new runtime dependencies |
| Task-level model routing unchanged | A-01 | All modes share model slot config |
| Franchise-classification boundary flag | FR-09 | Prompt template addition only (no pipeline change) |
| Multi-party Amber default | A-02 | User-facing docs must note limitation |
| OpCheck "Operating Agreement" naming | FR-10 | Help text strings only |
| Baseline from custom fixtures | A-06 | Regression detection only; no generalization claims |
| Synthetic fixtures sufficient | Q2 finding | Follows 028/029 pattern |
| VALID_MODES frozenset update | FR-06 | Add 5 keys to benchmark/cli.py |

## Decisions

1. **Synthetic fixtures**: Follow prior batch pattern. No real contracts.
2. **Franchise-classification flag**: Prompt-level instruction only. No pipeline changes.
3. **Single-party-first with Amber default**: Multi-party clauses get Amber. Document in help text.
4. **OpCheck help text**: Full "Operating Agreement" spelling in all user-facing help and output.
5. **No per-mode model routing**: Confirmed by A-01.
6. **Memo export uses mode shorthand prefix**: Follow existing convention.
7. **Baseline JSON files**: One per mode, fixture-specific, following baseline.py format.
