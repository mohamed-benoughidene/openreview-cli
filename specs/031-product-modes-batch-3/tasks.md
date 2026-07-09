---
description: "Task list for Product Modes Batch 3 — FranchiseCheck, OpCheck, PartnerCheck, SponsorCheck, DistroCheck"
---

# Tasks: Product Modes Batch 3 (FranchiseCheck, OpCheck, PartnerCheck, SponsorCheck, DistroCheck)

**Input**: `specs/031-product-modes-batch-3/`

**Branch**: `feat/031-product-modes-batch-3`

**Design artifacts**: plan.md, data-model.md, contracts/ (5 contract files), spec.md, research.md

**TDD enforcement**: Tests MUST be written BEFORE implementation code (constitutional Principle V). Each implementation task has a corresponding failing-test task preceding it.

## Format

`- [ ] [TaskID] [P?] [Group?] Description with file path`

- `[P]` = Parallelizable — different files, no dependencies on incomplete tasks
- `[Group]` = Maps to execution group: `[A]` (scaffolding, serial), `[B]` (mode tests), `[C]` (baselines), `[D]` (final integration)

---

## File Ownership Matrix

| Group | Files Touched | Disjoint From |
|-------|---------------|---------------|
| **A** | `src/openreview_cli/review/playbooks/{franchise,operating-agreement,partnership,sponsorship,distribution}-v1.yaml` (5 new), `src/openreview_cli/review/playbook.py`, `src/openreview_cli/review/prompts.py`, `src/openreview_cli/app.py`, `src/openreview_cli/benchmark/cli.py`, `tests/fixtures/{franchise,operating,partnership,sponsorship,distribution}-agreement.pdf` (5 new) | (none — A is the only group touching these shared source files) |
| **B** | `tests/unit/test_franchisecheck_playbook.py`, `tests/unit/test_opcheck_playbook.py`, `tests/unit/test_partnercheck_playbook.py`, `tests/unit/test_sponsorcheck_playbook.py`, `tests/unit/test_distrocheck_playbook.py`, `tests/integration/test_franchisecheck_e2e.py`, `tests/integration/test_opcheck_e2e.py`, `tests/integration/test_partnercheck_e2e.py`, `tests/integration/test_sponsorcheck_e2e.py`, `tests/integration/test_distrocheck_e2e.py`, `tests/integration/test_benchmark_modes.py`, `tests/integration/test_no_pii_flag.py` | **C** (different files entirely — B only touches test files, C touches docs/benchmarks/ and test_benchmark_baseline.py) |
| **C** | `docs/benchmarks/franchisecheck.json`, `docs/benchmarks/opcheck.json`, `docs/benchmarks/partnercheck.json`, `docs/benchmarks/sponsorcheck.json`, `docs/benchmarks/distrocheck.json`, `tests/integration/test_benchmark_baseline.py` | **B** (different files entirely — C only touches docs/benchmarks/ and test_benchmark_baseline.py) |
| **D** | `README.md`, `specs/DEFERRED.md`, (read-only) `git diff`, `specs/031-product-modes-batch-3/spec.md`, `specs/031-product-modes-batch-3/plan.md` | A, B, C (only writes to README.md and DEFERRED.md, neither touched by A/B/C) |

## Execution Order

```
Group A ──serial──> Complete ──> Groups B + C (parallel)
                                      │
                                      └──> Group D (serial after both complete)
```

**Group A** (serial): All scaffolding. ONE agent does all A tasks in order. Touches shared source files that Groups B/C depend on.

**Group B + C** (parallel after A completes): Mode tests and baselines. Completely disjoint file sets — can run in parallel across 2 agents.

**Group D** (serial after B+C): Final integration, verification, documentation.

---

## Group A — Scaffolding (serial, 1 agent, 24 tasks)

**Purpose**: Create all production scaffolding. ONE @medium agent does ALL of these tasks in order (they touch shared files or depend on prior A tasks).

**Files owned**: `src/openreview_cli/review/playbooks/*.yaml` (5 new), `src/openreview_cli/review/playbook.py`, `src/openreview_cli/review/prompts.py`, `src/openreview_cli/app.py`, `src/openreview_cli/benchmark/cli.py`, `tests/fixtures/*.pdf` (5 new)

### A-i: Fixture PDF Generation (must come first — tests depend on fixtures)

- [ ] A-01 [A] Generate fixture PDF at `tests/fixtures/franchise-agreement.pdf` — 3-5 page synthetic franchise agreement covering: franchise fee structure, territory rights, renewal/termination, advertising fund, transfer restrictions. Must trigger at least 2 assessment colors. No real PII (placeholder names/addresses). Parseable in <1s.
- [ ] A-02 [A] Generate fixture PDF at `tests/fixtures/operating-agreement.pdf` — 3-5 page synthetic LLC operating agreement covering: membership structure (member-managed), capital contributions, profit/loss allocation, voting rights, transfer restrictions/dissolution. Must trigger at least 2 assessment colors. No real PII.
- [ ] A-03 [A] Generate fixture PDF at `tests/fixtures/partnership-agreement.pdf` — 3-5 page synthetic partnership agreement covering: capital contributions, management authority, withdrawal/expulsion, liability allocation, dispute resolution. Must trigger at least 2 assessment colors. No real PII.
- [ ] A-04 [A] Generate fixture PDF at `tests/fixtures/sponsorship-agreement.pdf` — 2-3 page synthetic sponsorship agreement covering: fee/payment, rights/benefits, IP license, termination, indemnification. Must trigger at least 2 assessment colors. No real PII.
- [ ] A-05 [A] Generate fixture PDF at `tests/fixtures/distribution-agreement.pdf` — 3-5 page synthetic distribution agreement covering: territory/exclusivity, minimum purchases, pricing/payment, IP license, termination/non-compete. Must trigger at least 2 assessment colors. No real PII.
- [ ] A-06 [P] [A] Verify each fixture PDF is parseable: `uv run python -c "from openreview_cli.parsing.pdf_parser import PdfParser; p = PdfParser(); d = p.parse('tests/fixtures/franchise-agreement.pdf'); print(len(d.pages), 'pages')"` — repeat for all 5. Each must parse in <1s.

**Checkpoint**: 5 fixture PDFs exist, parseable, no real PII.

### A-ii: FranchiseCheck Scaffolding

- [ ] A-07 [A] Write failing test for `franchise-v1` playbook schema in `tests/unit/test_franchisecheck_playbook.py` (new file). Test: `load_playbook(path_to_franchise_v1)` succeeds with 5 categories. Run: `uv run pytest tests/unit/test_franchisecheck_playbook.py -v` → expect FAIL (playbook doesn't exist yet).
- [ ] A-08 [A] Create playbook YAML at `src/openreview_cli/review/playbooks/franchise-v1.yaml` — 5 categories following existing 3-position schema: franchise fee structure, territory rights and exclusivity, renewal and termination, advertising and marketing fund, transfer/assignment restrictions. Uses same YAML schema as existing playbooks. Run A-07 test → expect PASS.
- [ ] A-09 [A] Write failing test for `"franchisecheck"` MODE_VOCABULARY entry in `tests/unit/test_franchisecheck_playbook.py`. Test: `from openreview_cli.review.prompts import MODE_VOCABULARY; assert "franchisecheck" in MODE_VOCABULARY`. Run → expect FAIL.
- [ ] A-10 [A] Add `"franchisecheck"` entry to `MODE_VOCABULARY` in `src/openreview_cli/review/prompts.py` — specialization: `" specializing in franchise law and franchisor-franchisee agreements"`, domain: `"franchise agreement"`, vocabulary: franchise, franchisor, franchisee, FDD, territory, royalty, advertising fund, renewal, termination, non-compete, transfer, right of first refusal, franchise fee. **Must include `[FRANCHISE_BOUNDARY: yes|no|borderline]` instruction in vocabulary** (FR-09). Run A-09 test → expect PASS.
- [ ] A-11 [A] Write failing test for `"franchisecheck"` BUNDLED_PLAYBOOKS entry in `tests/unit/test_franchisecheck_playbook.py`. Test: `from openreview_cli.review.playbook import BUNDLED_PLAYBOOKS; assert "franchisecheck" in BUNDLED_PLAYBOOKS; assert BUNDLED_PLAYBOOKS["franchisecheck"].exists()`. Run → expect FAIL.
- [ ] A-12 [A] Add `"franchisecheck"` entry to `BUNDLED_PLAYBOOKS` in `src/openreview_cli/review/playbook.py` — maps to `franchise-v1.yaml` in same directory pattern: `Path(__file__).parent / "playbooks" / "franchise-v1.yaml"`. Run A-11 test → expect PASS.
- [ ] A-13 [A] Write failing test for `franchisecheck` CLI subcommand in `tests/unit/test_franchisecheck_playbook.py`. Test: `from openreview_cli.app import app; assert any(c.name == "franchisecheck" for c in app.registered_commands)`. Run → expect FAIL.
- [ ] A-14 [A] Register `franchisecheck` CLI subcommand in `src/openreview_cli/app.py` via `_register_product_mode()` — help_text: `"Review a franchise agreement or franchise disclosure document."`, path_help: `"Path to a franchise agreement or FDD (PDF or DOCX)."`. Run A-13 test → expect PASS.

### A-iii: OpCheck Scaffolding

- [ ] A-15 [A] Write failing test for `operating-agreement-v1` playbook schema in `tests/unit/test_opcheck_playbook.py` (new file). Test: `load_playbook()` succeeds. Run → expect FAIL.
- [ ] A-16 [A] Create playbook YAML at `src/openreview_cli/review/playbooks/operating-agreement-v1.yaml` — 5 categories: membership structure (member-managed vs. manager-managed), capital contributions and additional calls, profit/loss allocation (IRC §704(b)), voting rights and decision-making, transfer restrictions and dissolution. Run A-15 test → expect PASS.
- [ ] A-17 [A] Write failing test for `"opcheck"` MODE_VOCABULARY entry in `tests/unit/test_opcheck_playbook.py`. Test: `"opcheck" in MODE_VOCABULARY`. Run → expect FAIL.
- [ ] A-18 [A] Add `"opcheck"` entry to `MODE_VOCABULARY` in `src/openreview_cli/review/prompts.py` — **domain MUST use "Operating Agreement"** (not "OpCheck") per FR-10. specialization: `" specializing in LLC operating agreements"`, domain: `"Operating Agreement"`, vocabulary: operating agreement, LLC, member, manager, capital contribution, capital call, profit share, distribution, voting, transfer, buy-sell, dissolution, indemnification, IRC 704(b). Run A-17 test → expect PASS.
- [ ] A-19 [A] Write failing test for `"opcheck"` BUNDLED_PLAYBOOKS entry in `tests/unit/test_opcheck_playbook.py`. Test: `BUNDLED_PLAYBOOKS["opcheck"].exists()`. Run → expect FAIL.
- [ ] A-20 [A] Add `"opcheck"` entry to `BUNDLED_PLAYBOOKS` in `src/openreview_cli/review/playbook.py` — maps to `operating-agreement-v1.yaml`. Run A-19 test → expect PASS.
- [ ] A-21 [A] Write failing test for `opcheck` CLI subcommand in `tests/unit/test_opcheck_playbook.py`. Test: subcommand `"opcheck"` registered. Run → expect FAIL.
- [ ] A-22 [A] Register `opcheck` CLI subcommand in `src/openreview_cli/review/playbook.py` (wait — should be `app.py`). Register in `src/openreview_cli/app.py` via `_register_product_mode()` — help_text: `"Review an Operating Agreement (LLC governance document)."` (MUST spell out "Operating Agreement" per FR-10), path_help: `"Path to an operating agreement (PDF or DOCX)."`. Run A-21 test → expect PASS.

### A-iv: PartnerCheck Scaffolding

- [ ] A-23 [A] Write failing test for `partnership-v1` playbook schema in `tests/unit/test_partnercheck_playbook.py` (new file). Run → expect FAIL.
- [ ] A-24 [A] Create playbook YAML at `src/openreview_cli/review/playbooks/partnership-v1.yaml` — 5 categories: capital contributions and profit/loss allocation, management authority and decision-making, withdrawal/expulsion/dissolution, liability allocation and indemnification, dispute resolution (mediation/arbitration). Run A-23 test → expect PASS.
- [ ] A-25 [A] Write failing test for `"partnercheck"` MODE_VOCABULARY entry in `tests/unit/test_partnercheck_playbook.py`. Run → expect FAIL.
- [ ] A-26 [A] Add `"partnercheck"` entry to `MODE_VOCABULARY` in `src/openreview_cli/review/prompts.py` — specialization: `" specializing in partnership agreements"`, domain: `"partnership agreement"`, vocabulary: partnership, general partner, limited partner, capital contribution, profit share, loss allocation, management, withdrawal, expulsion, dissolution, joint and several liability, UPA, RUPA, non-compete, non-solicit, mediation, arbitration. Run A-25 test → expect PASS.
- [ ] A-27 [A] Write failing test for `"partnercheck"` BUNDLED_PLAYBOOKS entry in `tests/unit/test_partnercheck_playbook.py`. Run → expect FAIL.
- [ ] A-28 [A] Add `"partnercheck"` entry to `BUNDLED_PLAYBOOKS` in `src/openreview_cli/review/playbook.py` — maps to `partnership-v1.yaml`. Run A-27 test → expect PASS.
- [ ] A-29 [A] Write failing test for `partnercheck` CLI subcommand in `tests/unit/test_partnercheck_playbook.py`. Run → expect FAIL.
- [ ] A-30 [A] Register `partnercheck` CLI subcommand in `src/openreview_cli/app.py` via `_register_product_mode()` — help_text: `"Review a general or limited partnership agreement."`, path_help: `"Path to a partnership agreement (PDF or DOCX)."`. Run A-29 test → expect PASS.

### A-v: SponsorCheck Scaffolding

- [ ] A-31 [A] Write failing test for `sponsorship-v1` playbook schema in `tests/unit/test_sponsorcheck_playbook.py` (new file). Run → expect FAIL.
- [ ] A-32 [A] Create playbook YAML at `src/openreview_cli/review/playbooks/sponsorship-v1.yaml` — 5 categories: sponsorship fee and payment schedule, sponsorship rights and benefits (logo/recognition/exclusivity), IP license (use of sponsor's trademarks), termination for breach or force majeure, indemnification and non-disparagement. Run A-31 test → expect PASS.
- [ ] A-33 [A] Write failing test for `"sponsorcheck"` MODE_VOCABULARY entry in `tests/unit/test_sponsorcheck_playbook.py`. Run → expect FAIL.
- [ ] A-34 [A] Add `"sponsorcheck"` entry to `MODE_VOCABULARY` in `src/openreview_cli/review/prompts.py` — specialization: `" specializing in sponsorship agreements"`, domain: `"sponsorship agreement"`, vocabulary: sponsorship, sponsor, organizer, fee, payment, exclusivity, logo placement, event recognition, trademark license, termination, force majeure, indemnification, non-disparagement. Run A-33 test → expect PASS.
- [ ] A-35 [A] Write failing test for `"sponsorcheck"` BUNDLED_PLAYBOOKS entry in `tests/unit/test_sponsorcheck_playbook.py`. Run → expect FAIL.
- [ ] A-36 [A] Add `"sponsorcheck"` entry to `BUNDLED_PLAYBOOKS` in `src/openreview_cli/review/playbook.py` — maps to `sponsorship-v1.yaml`. Run A-35 test → expect PASS.
- [ ] A-37 [A] Write failing test for `sponsorcheck` CLI subcommand in `tests/unit/test_sponsorcheck_playbook.py`. Run → expect FAIL.
- [ ] A-38 [A] Register `sponsorcheck` CLI subcommand in `src/openreview_cli/app.py` via `_register_product_mode()` — help_text: `"Review a sponsorship agreement."`, path_help: `"Path to a sponsorship agreement (PDF or DOCX)."`. Run A-37 test → expect PASS.

### A-vi: DistroCheck Scaffolding

- [ ] A-39 [A] Write failing test for `distribution-v1` playbook schema in `tests/unit/test_distrocheck_playbook.py` (new file). Run → expect FAIL.
- [ ] A-40 [A] Create playbook YAML at `src/openreview_cli/review/playbooks/distribution-v1.yaml` — 5 categories: territory definition and exclusivity, minimum purchase requirements and cure periods, pricing/payment/inventory terms, IP license (manufacturer's trademarks), termination rights/non-compete/channel restrictions. Run A-39 test → expect PASS.
- [ ] A-41 [A] Write failing test for `"distrocheck"` MODE_VOCABULARY entry in `tests/unit/test_distrocheck_playbook.py`. Run → expect FAIL.
- [ ] A-42 [A] Add `"distrocheck"` entry to `MODE_VOCABULARY` in `src/openreview_cli/review/prompts.py` — specialization: `" specializing in distribution and reseller agreements"`, domain: `"distribution agreement"`, vocabulary: distribution, distributor, manufacturer, territory, exclusivity, minimum purchase, cure period, pricing, payment, inventory, returns, trademark license, termination, non-compete, channel restriction, jurisdiction, venue. **Must include `[FRANCHISE_BOUNDARY: yes|no|borderline]` instruction in vocabulary** (FR-09). Run A-41 test → expect PASS.
- [ ] A-43 [A] Write failing test for `"distrocheck"` BUNDLED_PLAYBOOKS entry in `tests/unit/test_distrocheck_playbook.py`. Run → expect FAIL.
- [ ] A-44 [A] Add `"distrocheck"` entry to `BUNDLED_PLAYBOOKS` in `src/openreview_cli/review/playbook.py` — maps to `distribution-v1.yaml`. Run A-43 test → expect PASS.
- [ ] A-45 [A] Write failing test for `distrocheck` CLI subcommand in `tests/unit/test_distrocheck_playbook.py`. Run → expect FAIL.
- [ ] A-46 [A] Register `distrocheck` CLI subcommand in `src/openreview_cli/app.py` via `_register_product_mode()` — help_text: `"Review a distribution or reseller agreement."`, path_help: `"Path to a distribution agreement (PDF or DOCX)."`. Run A-45 test → expect PASS.

### A-vii: Shared Cross-Cutting Scaffolding

- [ ] A-47 [A] Write failing test for VALID_MODES completeness in `tests/unit/test_distrocheck_playbook.py` (or existing `test_benchmark_modes.py`). Test: `from openreview_cli.benchmark.cli import VALID_MODES; assert "franchisecheck" in VALID_MODES; assert "opcheck" in VALID_MODES; assert "partnercheck" in VALID_MODES; assert "sponsorcheck" in VALID_MODES; assert "distrocheck" in VALID_MODES`. Run → expect FAIL.
- [ ] A-48 [A] Add 5 entries to `VALID_MODES` frozenset in `src/openreview_cli/benchmark/cli.py` — add `"franchisecheck"`, `"opcheck"`, `"partnercheck"`, `"sponsorcheck"`, `"distrocheck"` to the frozenset. Update the ponytail comment line to reflect 22 total modes. Run A-47 test → expect PASS.

**Group A Checkpoint**: All 5 playbook YAMLs created, all 5 BUNDLED_PLAYBOOKS entries registered, all 5 MODE_VOCABULARY entries added (with boundary flags for distrocheck + franchisecheck, "Operating Agreement" for opcheck), all 5 CLI subcommands registered (with correct help text), VALID_MODES updated to 22 entries, all 5 fixture PDFs exist, all unit tests pass.

---

## Group B — Per-Mode Tests (parallel with Group C, 2 agents, 14 tasks)

**Purpose**: Unit + E2E tests for all 5 new modes. Completely disjoint from Group C files.

**Files owned**: `tests/unit/test_franchisecheck_playbook.py`, `tests/unit/test_opcheck_playbook.py`, `tests/unit/test_partnercheck_playbook.py`, `tests/unit/test_sponsorcheck_playbook.py`, `tests/unit/test_distrocheck_playbook.py`, `tests/integration/test_franchisecheck_e2e.py`, `tests/integration/test_opcheck_e2e.py`, `tests/integration/test_partnercheck_e2e.py`, `tests/integration/test_sponsorcheck_e2e.py`, `tests/integration/test_distrocheck_e2e.py`, `tests/integration/test_benchmark_modes.py`, `tests/integration/test_no_pii_flag.py`

### B-i: Unit Tests (one file per mode, validates scaffolding)

- [ ] B-01 [P] [B] Write unit test file `tests/unit/test_franchisecheck_playbook.py` — comprehensive tests: (1) playbook schema validation via `load_playbook()`, (2) `"franchisecheck"` in `MODE_VOCABULARY` with non-empty domain/vocabulary, (3) `"franchisecheck"` in `BUNDLED_PLAYBOOKS` with existing path, (4) CLI subcommand `franchisecheck` registered in `app.registered_commands`, (5) `VALID_MODES` contains `"franchisecheck"`, (6) MODE_VOCABULARY entry vocabulary contains `FRANCHISE_BOUNDARY` instruction. Run: `uv run pytest tests/unit/test_franchisecheck_playbook.py -v` → all PASS.
- [ ] B-02 [P] [B] Write unit test file `tests/unit/test_opcheck_playbook.py` — same pattern as B-01: (1) playbook schema, (2) MODE_VOCABULARY entry (assert domain == "Operating Agreement" per FR-10), (3) BUNDLED_PLAYBOOKS entry, (4) CLI subcommand, (5) VALID_MODES, (6) CLI help text contains "Operating Agreement". Run → all PASS.
- [ ] B-03 [P] [B] Write unit test file `tests/unit/test_partnercheck_playbook.py` — same pattern: (1) playbook schema, (2) MODE_VOCABULARY entry, (3) BUNDLED_PLAYBOOKS entry, (4) CLI subcommand, (5) VALID_MODES, (6) CLI help text. Run → all PASS.
- [ ] B-04 [P] [B] Write unit test file `tests/unit/test_sponsorcheck_playbook.py` — same pattern: (1) playbook schema, (2) MODE_VOCABULARY entry, (3) BUNDLED_PLAYBOOKS entry, (4) CLI subcommand, (5) VALID_MODES, (6) CLI help text. Run → all PASS.
- [ ] B-05 [P] [B] Write unit test file `tests/unit/test_distrocheck_playbook.py` — same pattern: (1) playbook schema, (2) MODE_VOCABULARY entry (assert vocabulary contains `FRANCHISE_BOUNDARY` per FR-09), (3) BUNDLED_PLAYBOOKS entry, (4) CLI subcommand, (5) VALID_MODES, (6) CLI help text. Run → all PASS.

### B-ii: E2E Integration Tests (one file per mode, uses mock gateway)

- [ ] B-06 [P] [B] Write E2E test file `tests/integration/test_franchisecheck_e2e.py` — parametrized mock-gateway test: parse `franchise-agreement.pdf`, strip PII, run `run_review(mode="franchisecheck")`, assert `ReviewReport` with `mode == "franchisecheck"`, assert `len(report.assessments) > 0`, assert each `assessment.color in (green, amber, red)`. Mock AI gateway via `monkeypatch.setattr("openreview_cli.gateway.router.Gateway.chat", mock_chat)`. Run: `uv run pytest tests/integration/test_franchisecheck_e2e.py -v` → PASS.
- [ ] B-07 [P] [B] Write E2E test file `tests/integration/test_opcheck_e2e.py` — same pattern as B-06 but for mode `"opcheck"` using `operating-agreement.pdf`. Additionally assert `--help` output contains "Operating Agreement". Run → PASS.
- [ ] B-08 [P] [B] Write E2E test file `tests/integration/test_partnercheck_e2e.py` — same pattern for `"partnercheck"` using `partnership-agreement.pdf`. Run → PASS.
- [ ] B-09 [P] [B] Write E2E test file `tests/integration/test_sponsorcheck_e2e.py` — same pattern for `"sponsorcheck"` using `sponsorship-agreement.pdf`. Run → PASS.
- [ ] B-10 [P] [B] Write E2E test file `tests/integration/test_distrocheck_e2e.py` — same pattern for `"distrocheck"` using `distribution-agreement.pdf`. Additionally assert extraction output contains `[FRANCHISE_BOUNDARY:]` flag. Run → PASS.

### B-iii: Cross-Cutting Integration Tests

- [ ] B-11 [P] [B] Add 5 parametrize entries to `tests/integration/test_benchmark_modes.py` — add `"franchisecheck"`, `"opcheck"`, `"partnercheck"`, `"sponsorcheck"`, `"distrocheck"` to the mode validation parametrize list. Each must: invoke `benchmark run --modes=<mode>` with fixture dataset, assert exit 0. Run: `uv run pytest tests/integration/test_benchmark_modes.py -v` → all PASS.
- [ ] B-12 [P] [B] T033 unblock — extend `tests/integration/test_no_pii_flag.py` with parametrized test for all 5 new modes. Each case: run `openreview <mode> --no-pii <fixture.pdf>`, assert raw text preserved (PII not stripped). Run: `uv run pytest tests/integration/test_no_pii_flag.py -v` → all PASS.
- [ ] B-13 [P] [B] Write DistroCheck ↔ FranchiseCheck boundary test in `tests/integration/test_distrocheck_e2e.py` (or separate `tests/integration/test_franchise_boundary.py`). Test: run extraction on distribution agreement fixture, assert output JSON key `franchise_boundary` exists with value `"yes"`, `"no"`, or `"borderline"`. Run → PASS.
- [ ] B-14 [P] [B] Write OpCheck CLI help text test in `tests/unit/test_opcheck_playbook.py` — add test: invoke `openreview opcheck --help`, capture stdout, assert `"Operating Agreement"` appears in output. Run → PASS.

---

## Group C — Baselines (parallel with Group B, 1 agent, 7 tasks)

**Purpose**: Per-mode baseline JSON files + benchmark baseline parametrize tests. Completely disjoint from Group B files.

**Files owned**: `docs/benchmarks/franchisecheck.json`, `docs/benchmarks/opcheck.json`, `docs/benchmarks/partnercheck.json`, `docs/benchmarks/sponsorcheck.json`, `docs/benchmarks/distrocheck.json`, `tests/integration/test_benchmark_baseline.py`

### C-i: Baseline JSON Files

- [ ] C-01 [P] [C] Create baseline JSON at `docs/benchmarks/franchisecheck.json` — follow existing schema from `docs/benchmarks/` (matching `BaselineResult`/`BaselineReport` format): `{"mode_key": "franchisecheck", "display_name": "FranchiseCheck", "fixture": "tests/fixtures/franchise-agreement.pdf", "expected_assessment": {"overall": "AMBER"}, "time_budget_s": 30, "pii_time_budget_s": 3, "page_count": 5}`. Validate: `python -c "import json; json.load(open('docs/benchmarks/franchisecheck.json'))"`.
- [ ] C-02 [P] [C] Create baseline JSON at `docs/benchmarks/opcheck.json` — mode_key: `"opcheck"`, fixture: `tests/fixtures/operating-agreement.pdf`, expected_overall: AMBER. Validate parseable JSON.
- [ ] C-03 [P] [C] Create baseline JSON at `docs/benchmarks/partnercheck.json` — mode_key: `"partnercheck"`, fixture: `tests/fixtures/partnership-agreement.pdf`, expected_overall: AMBER. Validate parseable JSON.
- [ ] C-04 [P] [C] Create baseline JSON at `docs/benchmarks/sponsorcheck.json` — mode_key: `"sponsorcheck"`, fixture: `tests/fixtures/sponsorship-agreement.pdf`, expected_overall: AMBER. Validate parseable JSON.
- [ ] C-05 [P] [C] Create baseline JSON at `docs/benchmarks/distrocheck.json` — mode_key: `"distrocheck"`, fixture: `tests/fixtures/distribution-agreement.pdf`, expected_overall: AMBER. Validate parseable JSON.

### C-ii: Benchmark Baseline Integration Tests

- [ ] C-06 [P] [C] Add 5 parametrize entries to `tests/integration/test_benchmark_baseline.py` — add `"franchisecheck"`, `"opcheck"`, `"partnercheck"`, `"sponsorcheck"`, `"distrocheck"` to baseline generation parametrize list. Each must: load `docs/benchmarks/<mode>.json`, validate against `BaselineReport` schema, assert mode_key matches. Run: `uv run pytest tests/integration/test_benchmark_baseline.py -v` → all PASS.
- [ ] C-07 [P] [C] Verify per-mode regression detection works — add test to `tests/integration/test_benchmark_baseline.py`: load all 5 new baselines, run mock baseline generation, compare each mode's result against expected_assessment from baseline JSON. Assert no regression (expected overall matches). Run → PASS.

---

## Group D — Final Integration (serial after B and C complete, 1 agent, 10 tasks)

**Purpose**: Full suite verification, lint, types, pre-commit, ponytail review, convergence, deferred items, documentation.

**Files owned**: `README.md`, `specs/DEFERRED.md` (writes), `specs/031-product-modes-batch-3/spec.md` (read-only), `specs/031-product-modes-batch-3/plan.md` (read-only), `git diff` (read-only)

- [ ] D-01 [D] Run full non-memory test suite: `uv run pytest tests/unit/ tests/integration/ -k 'not memory' -q`. All tests must PASS (existing + 5 new unit + 5 new E2E + benchmark + no-pii).
- [ ] D-02 [D] Run memory tests solo: `uv run pytest -m memory -q --timeout=300`. All PASS. Expected: PII memory tests pass within 110 MB floor.
- [ ] D-03 [D] Run lint: `uv run ruff check .`. No new errors.
- [ ] D-04 [D] Run types: `uv run mypy src/ tests/`. No new type errors. No `# type: ignore` or `Any` where concrete types exist.
- [ ] D-05 [D] Run pre-commit: `uvx pre-commit run --all-files`. All hooks pass (ruff, ruff-format, mypy, pytest-fast, stdlib hygiene).
- [ ] D-06 [D] Ponytail review — load `.tools/ponytail/skills/ponytail-review/SKILL.md`, review `git diff main` for over-engineering. Fix any findings: unused abstractions, unnecessary boilerplate, speculatively flexible parameters. Add `ponytail:` comments for deliberate shortcuts. Re-run D-01 through D-05 after fixes.
- [ ] D-07 [D] Convergence — run gap analysis against `specs/031-product-modes-batch-3/spec.md` and `plan.md`. Verify: each spec requirement has a corresponding task in tasks.md, each task has a testable acceptance criterion, no orphan requirements. Report findings as checklist diff.
- [ ] D-08 [D] DEFERRED.md update — scan all tasks for newly deferred items (D-N items). Append to `specs/DEFERRED.md` with spec reference and reason. Examples: multi-party bilateral comparison deferred, Amber ceiling limitation.
- [ ] D-09 [D] README update — load `readme-blueprint-generator` skill, update `README.md` with L-4c content: list 5 new product modes with one-line descriptions, update mode count to 22, add CLI usage examples. Do NOT mention audience in repo metadata.
- [ ] D-10 [D] Tweet thread draft — load `twitter-x-posts` skill, write 4-5 post thread announcing L-4c completion (22-mode product line). Focus on: 5 new contract types, franchise boundary detection, 22-mode milestone, CLI-first approach, single-party review pipeline. Save draft to `.specify/memory/social/l4c-tweet-thread.md`. Only if `.specify/memory/social/` exists — otherwise skip.

**Final Checkpoint**: All tests green, lint/types clean, pre-commit passes, no over-engineering found, gap analysis complete, DEFERRED.md updated, README updated, tweet thread drafted.

---

## Dependency Graph

```
Group A (serial — all scaffolding)
  │
  ├──> Group B (parallel — mode tests)
  │     │
  │     └──> Group D (serial — final integration)
  │
  └──> Group C (parallel — baselines)
        │
        └──> Group D (serial — final integration)
```

### Phase Dependencies

| Phase | Depends On | Blocks | Parallel With |
|-------|-----------|--------|---------------|
| A-i (Fixtures) | — | A-ii through A-vi | — |
| A-ii (FranchiseCheck) | A-i | — | A-iii, A-iv, A-v, A-vi (within A, but serial agent) |
| A-iii (OpCheck) | A-i | — | A-ii, A-iv, A-v, A-vi |
| A-iv (PartnerCheck) | A-i | — | A-ii, A-iii, A-v, A-vi |
| A-v (SponsorCheck) | A-i | — | A-ii, A-iii, A-iv, A-vi |
| A-vi (DistroCheck) | A-i | — | A-ii, A-iii, A-iv, A-v |
| A-vii (VALID_MODES) | A-ii through A-vi | Group B, Group C | — |
| Group B | Group A | Group D | Group C |
| Group C | Group A | Group D | Group B |
| Group D | Group B, Group C | — | — |

### Parallel Execution Strategy

```bash
# After Group A completes:
# Agent 1: Group B (mode tests) — 14 tasks
# Agent 2: Group C (baselines) — 7 tasks

# After both complete:
# Agent 1: Group D (final integration) — 10 tasks
```

## Implementation Strategy

### MVP First (FranchiseCheck only)

1. Complete A-i (fixtures) — all 5 fixtures
2. Complete A-ii (FranchiseCheck scaffolding) — playbook, prompts, playbook.py, app.py
3. Complete A-vii (VALID_MODES update with franchisecheck only)
4. Run B-01 (FranchiseCheck unit test) and B-06 (FranchiseCheck E2E)
5. Validate: `uv run pytest tests/unit/test_franchisecheck_playbook.py tests/integration/test_franchisecheck_e2e.py -v`
6. Continue with remaining 4 modes sequentially

### Incremental Delivery (recommended)

1. Group A → All 5 modes scaffolded and verified ✅
2. Group B → All 5 modes unit + E2E tested ✅
3. Group C → All 5 mode baselines validated ✅
4. Group D → Full suite green, docs updated ✅

## Success Criteria Verification Map

| Criteria | Description | Verifying Task |
|----------|-------------|----------------|
| SC-1 | All 5 playbooks pass `load_playbook()` schema validation | A-08, A-16, A-24, A-32, A-40 |
| SC-2 | All 5 mode keys in `MODE_VOCABULARY` with non-empty values | A-10, A-18, A-26, A-34, A-42 |
| SC-3 | All 5 mode keys in `BUNDLED_PLAYBOOKS` with valid paths | A-12, A-20, A-28, A-36, A-44 |
| SC-4 | All 5 CLI subcommands registered and show in `--help` | A-14, A-22, A-30, A-38, A-46 |
| SC-5 | `VALID_MODES` contains all 5 new modes (22 total) | A-48 |
| SC-6 | All 5 fixture PDFs parseable in <1s | A-06 |
| SC-7 | OpCheck help text contains "Operating Agreement" | B-14 |
| SC-8 | DistroCheck vocabulary includes `[FRANCHISE_BOUNDARY:]` flag | B-05 (assertion) |
| SC-9 | FranchiseCheck vocabulary includes `[FRANCHISE_BOUNDARY:]` flag | B-01 (assertion) |
| SC-10 | `--no-pii` flag preserves raw text for all 5 modes | B-12 |
| SC-11 | 5 baseline JSON files exist and validate against schema | C-01 through C-06 |
| SC-12 | All 5 modes produce valid JSON with correct `mode` field | B-06 through B-10 |
| SC-13 | All unit + integration tests pass | D-01 |
| SC-14 | Memory budget maintained (<110 MB) | D-02 |
| SC-15 | Ruff lint clean | D-03 |
| SC-16 | Mypy strict type clean | D-04 |
| SC-17 | Pre-commit all hooks pass | D-05 |

## Notes

- **No new runtime dependencies** — all changes are playbook YAMLs, dict entries, and test files.
- **No new database tables** — no SQLite changes. Playbooks are file-based YAML.
- **No pipeline modifications** — all 5 modes reuse existing single-party review pipeline identically.
- **Fixture PII**: All fixture PDFs must use placeholder names/addresses per data-model.md validation rule 7.
- **Multi-party Amber ceiling**: Single-party-first approach. Multi-party clauses get Amber default. Document limitation in help text.
- **Boundary flag advisory only**: `[FRANCHISE_BOUNDARY:]` is advisory text in prompt — no legal classification.
- **T033 unblocked**: `--no-pii` integration tests now possible with actual CLI subcommands.
- **Mock gateway pattern**: Follow existing `monkeypatch.setattr("openreview_cli.gateway.router.Gateway.chat", mock_chat)` pattern from `test_benchmark_cuad.py`.
- **No audience references** in repo metadata or help text.
- **Pre-commit**: Run `uvx pre-commit run --all-files` before any commit (not `uv run pre-commit install` assumed).
- **Memory tests**: Run solo with `--timeout=300` — do not include in `uv run pytest` without `-k 'not memory'`.
