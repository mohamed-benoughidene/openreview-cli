# AGENTS.md

Command Code instructions for `openreview`. Read this before touching anything in the repo. (Legacy OpenCode config artifacts remain in place: `opencode.json`, `.opencode/`, and the `.tools/ponytail` submodule.)

## Status

Python 3.12 project, pre-alpha but far along: document parsing (PDF/DOCX/clause detection), PII stripping (Presidio, encrypted mapping), AI Gateway (routing, cost tracking, registry, wizard, redaction), review pipeline (extraction → QA → comparison, memo generation, 24 bundled playbooks), chunking/retrieval/grounding/negotiation/bilateral/recovery/graph/benchmark modules, a Textual TUI, and a Typer CLI with 40 top-level subcommands (`parse`, `chunk`, `ingest`, `retrieve`, `index-status`, `index-clear`, `negotiate`, `export`, `precheck`, `gateway`, `playbook`, `pii`, `client`, `config`, `graph`, `benchmark`, `prompt`, plus 23 product-mode review commands such as `licensecheck`, `leasecheck`, `privacycheck`, `dealcheck`, `hirecheck`).

Product design lives in `products/openreview/` (gitignored) and is **preliminary, not final**. Spec-driven development via spec-kit: specs in `specs/` (001–034; 33 specs, `023` unused), deferred work tracked in `specs/DEFERRED.md` — check it before touching a module with open deferrals.

## Tracked vs. local

- **Gitignored:** `products/` (product design), `Papers/`, `data/` (benchmark corpora), `draft/`, `review_results/` and `.benchmark-reports/` (run outputs, decision D5), `graphify-out/` + `src/graphify-out/` (regenerable graph), `.venv/`, `.drafts`, and local agent/tooling state `.commandcode/`. (`.opencode/` and `.impeccable/` are gitignore-listed but each retains tracked files; `AGENTS.md` itself is tracked, not gitignored.)
- **Tracked:** `specs/`, `.specify/` (constitution at `.specify/memory/constitution.md`), the retained `.opencode/commands/*.md` spec-kit files (the `.opencode/` dir itself is gitignore-listed as local tooling state; `.opencode/AGENTS.md` was removed), everything in "Layout" below.
- **Submodule:** `.tools/ponytail` — after clone, `git submodule update --init`, or the OpenCode-only `opencode.json` (harness since superseded by Command Code) points at a missing path and its plugin won't load.

## Audience

The product's user audience is **intentionally not mentioned** in repo metadata (`pyproject.toml` description, `README.md`, AGENTS.md) or in spec excerpts quoted into user-facing artifacts. Strip audience references from text you draft into the repo. `products/` may mention it — internal material, not metadata.

## Layout

```
src/openreview_cli/          # Package (src layout). Entry: app.py (Typer), __main__.py
  ├─ slots.py                # VALID_SLOTS — outside gateway/ on purpose (see Gotchas)
  ├─ llm_json.py             # Shared LLM JSON/fence-stripping helper
  ├─ product_modes.py        # Single source of truth for 23 named modes + precheck (CLI/TUI/benchmark)
  ├─ errors.py               # EXIT_* exit-code registry + fail()/…_error() helpers; intended single source, but only app.py and gateway/router.py import it
  ├─ config/ storage/        # Auth, paths, YAML config loader; SQLite layer
  ├─ parsing/                # PdfParser (PyMuPDF streaming), DocxParser, clause detector
  ├─ pii/                    # Presidio engine, recognizers, encryption, mapping, audit
  ├─ gateway/                # Model routing, registry (models.json), cost, wizard
  ├─ review/                 # Pipeline + agents + memo; playbooks/ (24 YAML)
  ├─ pipeline/ chunking/ retrieval/ grounding/ negotiation/ bilateral/ recovery/ graph/ benchmark/ prompts/
  └─ tui/                    # Textual app (app.py, screens/, domain/, tabs/)
tests/{unit,integration,fixtures,helpers}   # 207 unit + 149 integration test files
tests/exploratory/           # 87 adversarial CLI/TUI probes (feat/design-ux-remediation); in the default -m fast pool
Makefile                     # make test = test-offline + test-memory; also test-fast / test-slow
scripts/                     # 9 standalone benchmark scripts (top level); parity/ inventories
specs/                       # spec-kit specs 001–034 + DEFERRED.md
.github/workflows/{ci,release}.yml
docs/                        # User-facing docs (25 files, all git-tracked): architecture, benchmarks, parity, release, specs/plans
  ├─ ARCHITECTURE.md         # How the CLI/TUI, stage pipeline, AI Gateway, SQLite and retrieval fit together
  ├─ cli-tui-parity-matrix.md # Generated CLI↔TUI feature-parity matrix (scripts/parity/build_parity_matrix.py)
  └─ benchmarks/             # 15 committed benchmark JSONs: 5 mode baselines + 10 receipts under results/
PRODUCT.md                   # Product framing (platform, users, purpose, positioning, constraints); check before altering scope or claims
DESIGN.md                    # Design system: YAML design tokens + TUI visual/component rules; obey its do's/don'ts on TUI changes
LICENSE                      # Full AGPL-3.0 text (root); AGPL half of the dual license (Hard constraints).
COMMERCIAL_LICENSE.md        # Commercial half of the dual license: when/why to buy, grants, pricing (Hard constraints).
NOTICE.md                    # Project notice (license/CLA/trademarks/contact); L3 names the audience ("solo lawyers") — flag stands (not in the Audience section's scoped list).
```

Version is hardcoded by hand in **three** places: `pyproject.toml`, `src/openreview_cli/__init__.py` (`__version__`), and `skill/SKILL.md` (frontmatter `version`). Bump all three. A fourth site, `uv.lock` (editable package entry), is generated — it is rewritten automatically by `uv run` (used by the mypy pre-commit hook), so commit it alongside (the hook will fail/rollback once if you don't stage it).

## Setup

```bash
git submodule update --init   # only needed for OpenCode (opencode.json → .tools/ponytail plugin); Command Code loads ponytail from ~/.agents/skills
uv sync                       # runtime + dev deps into .venv
```

## Commands

```bash
uv run openreview --help
uv run pytest -m "fast" -q              # auto-marked default pool (3550/3935 tests); not all sub-second
uv run pytest -m "fast or slow" -q      # all offline tests except memory + network/live (3910/3935)
uv run pytest -m slow                   # TUI suite + heavy non-TUI tests (~360; Textual run_test startup cost)
uv run pytest -m memory -q              # memory tests ALWAYS run solo (see Gotchas)
uv run pytest tests/unit/test_x.py::test_y  # single test
uv run ruff check . && uv run ruff format .
uv run mypy src/ tests/                 # strict
uv run pre-commit run --all-files       # before every commit (pre-commit is a global tool, not a dev-group dep)
```

Pytest markers (pyproject.toml): `fast`, `slow`, `integration`, `e2e`, `memory`, `no_memory`, `benchmark`, `accuracy`, `network`, `live`.

**CI** (`ci.yml`, push to main + PRs): 7 parallel jobs — `lint`, `types`, `test` (unit only), `memory` (installs spaCy model), `integration` (non-tui, non-memory/slow), `tui` (`-m slow --reruns 1`), `benchmark` (main only, `|| true`). Uses `actions/checkout@v7` + `astral-sh/setup-uv@v10.1.0`.

**Pre-commit**: hygiene hooks, `ruff --fix`, `ruff-format`, `mypy` (`uv run mypy src/ tests/`), `pytest-fast` (`uv run pytest tests/unit/ --collect-only -q`). `uv run pre-commit install` once per clone; sub-agents in fresh shells must verify `.git/hooks/pre-commit` exists or run `uv run pre-commit run --all-files` before `git add` and stage reformats. The source of truth for all of the above — hook ids, the pinned `rev`s, and the `mypy`/`pytest-fast` commands — is `.pre-commit-config.yaml`; edit that file whenever hook behavior changes, since the installed `.git/hooks/pre-commit` is generated from it.

**Release** (`release.yml`): tag `v*.*.*` → build → GitHub release → PyPI via **OIDC trusted publishing** (no API token; `environment: release` + required-reviewer approval gate). Publishing waits in "Review" until a human approves. Do not push release tags casually — tag protection restricts them to the owner anyway. Release chain: bump all three version files (`pyproject.toml`, `src/openreview_cli/__init__.py`, `skill/SKILL.md`) (+ commit `uv.lock`) → commit → `git tag vX.Y.Z` → push tag → approve in Actions → verify on PyPI.

## Benchmarks & measurements

Quick sanity checks and accuracy benchmarks. All are runnable locally (some need configured gateway or downloaded corpus).

### Quick profiling

```bash
# CLI startup latency + RSS
/usr/bin/time -v uv run openreview --help

# Parse latency (in-process, bypasses CLI overhead + registry-refresh stall)
uv run python -c "
import time; t=time.time()
from openreview_cli.parsing.stream import parse_document; doc, clauses = parse_document('tests/fixtures/nda_with_pii.pdf')
print(f'{time.time()-t:.3f}s, {len(clauses)} clauses')
"

# Test suite size + accuracy-test pass/fail
uv run pytest --collect-only -m 'fast or slow' 2>/dev/null | tail -1
uv run pytest -k 'accuracy' -v
```

### Gateway health

```bash
openreview gateway status           # slot/provider config
openreview gateway test <slot>      # connectivity check for one slot (slot is required)
openreview gateway costs --today    # cost ledger
```

### CUAD clause identification (public benchmark)

```bash
# Corpus at data/legalbenchrag/ (gitignored, 88 MB, 462 CUAD + 95 ContractNLI)
# scripts/benchmark_legalbenchrag.py reads the legacy /tmp/opencode/legalbenchrag_data/ path;
# fetch the corpus yourself or from atticusprojectai.org/cuad (CC BY 4.0)
uv run python -c "
from openreview_cli.parsing.clause_detector import _get_nupunkt
import json, time
with open('data/legalbenchrag/benchmarks/cuad.json') as f: data = json.load(f)
# … sentence-boundary recall loop (see BENCHMARKS.md § CUAD)
"
```

### PII accuracy (seeded corpus)

```bash
# Uses BenchmarkRunner.run_pii() with real PiiEngine
# Corpus: tests/fixtures/pii/seeded_contracts/ + ground_truth.json (50 contracts)
uv run python -c "
from pathlib import Path
from openreview_cli.benchmark.models import BenchmarkConfig
from openreview_cli.benchmark.runner import BenchmarkRunner
from openreview_cli.pii.engine import PiiEngine

engine = PiiEngine(threshold=0.7)
runner = BenchmarkRunner(config=BenchmarkConfig(datasets=['pii']), fixtures_root=Path('tests/fixtures'))
def detect_fn(text): return [{'value': e.original_value, 'type': e.entity_type} for e in engine.detect_on_page(text)]
result = runner.run_pii(detect_fn)
for k, v in result.metrics.items():
    print(f'{k}: {v.value:.4f}')
"
```

### PII throughput (corpus + stress)

```bash
# PII throughput (corpus + stress). Writes to a gitignored path by default.
# PASS --output to send the summary somewhere else.
uv run python scripts/benchmark_pii_stripping.py
```

### Review accuracy (real LLM, needs gateway)

```bash
# Needs: gateway configured (openreview gateway setup), OpenRouter key in auth.json
# Labeled NDA corpus: tests/fixtures/review/nda-corpus-v1/nda-corpus-v1.json (12 clauses)
# The exact models used were not recorded in the source artifact
# (receipt: docs/benchmarks/results/review-accuracy.json); configure the gateway
# extraction + reasoning slots (and embedding/reranking, if enabled) as usual.
# scripts/benchmark_review_accuracy.py is STRUCTURAL ONLY — it reads predicted_position
# from the corpus JSON, does NOT call real LLMs. For real accuracy, use inline:
uv run python -c "
import json, time
from pathlib import Path
from openreview_cli.review.extraction import extract_clause
from openreview_cli.review.qa import verify_assessment
from openreview_cli.review.playbook import load_bundled

corpus = json.loads(Path('tests/fixtures/review/nda-corpus-v1/nda-corpus-v1.json').read_text())
playbook = load_bundled()
categories = {c.id: c for c in playbook.categories}
tp = fp = fn = 0
for c in corpus['clauses']:
    cat = categories.get(c['expected_category'])
    if not cat: continue
    assessment = extract_clause(c['text'], c['id'], cat, 'extraction', mode='precheck')
    assessment = verify_assessment(assessment, cat, 'reasoning')
    pred = assessment.position.value if assessment.position else 'uncertain'
    if pred == c['expected_position']: tp += 1
    else: fp += 1
total = tp + fp
print(f'F1={(2*tp/(2*tp+fp)).:.2%}' if total else 'no clauses matched')
"
```

### Product-mode pipeline wiring (mocked, deterministic)

```bash
# Generates synthetic PDFs under tests/fixtures/benchmark/<mode>/ (tracked, byte-stable)
# and the report under .benchmark-reports/ (gitignored). 23 named modes, mocked gateway.
# --generate-only writes the fixtures and exits. Verify determinism: run it twice and
# check `git status --porcelain tests/fixtures/benchmark`.
uv run python scripts/benchmark_product_modes.py
```

### Known script issues

- `scripts/benchmark_pii_stripping.py` - fixed 2026-09-22: unpacks the 4-tuple
  `(entities, warnings, failed_pages, error_messages)`. Default output is
  `.benchmark-reports/metrics-pii.json` (gitignored); use `--output` to change it.
- `scripts/benchmark_review_accuracy.py` — structural only. Reads `predicted_position` from corpus JSON (line 97). Does not call real LLMs — see Review accuracy section above for inline version.
- `openreview benchmark run --all --ci` — uses mock pipeline for CUAD/MAUD/ContractNLI. Only PII dataset uses real `PiiEngine`.

### End-to-end smoke test

```bash
# Full pipeline: parse → PII strip → extract → QA on a fixture PDF
uv run openreview precheck review tests/fixtures/nda_with_pii.pdf --memo-format json --output review_results/review.json
```

## Hard constraints

- **Python 3.12** pinned. **uv** only — no pip/poetry/pipx. New deps via `uv add <pkg>`, never hand-edited, and only when the feature needing them lands.
- **AGPL-3.0 + Commercial dual-license** — no license-incompatible code.
- **Local CLI only.** No web server, or background daemons/services. (The interactive TUI is fine — it runs in the foreground while the user has it open, it's not a background process.)
- **Privacy first.** PII stripped before any external API call. API keys in `auth.json` (chmod 600) only. Never log raw contract text, PII, or keys — redact even in `--debug`.
- **Memory budget.** Target peak < 100 MB. Hard fail threshold is 110 MB (enforced by `memory_tracker` fixture) — the extra 10 MB is buffer, not a separate goal. Stream parsers page-by-page; don't load full documents.
- **Forbidden by spec:** `langchain`, `llama-index`, `FAISS`, `spaCy` *for PII* (Presidio uses it internally — the ban is on direct use), `sentence-transformers` (use Ollama), `loguru`/`structlog` (stdlib logging), `FastAPI`/`Flask`. These are hard bans — if a task seems to need one of them, stop and confirm before deviating, don't just swap it in. Note: `click` is a direct dep despite the spec preferring Typer — pyproject.toml is the source of truth for what's installed; surface conflicts instead of "fixing" them silently.
- `torch`/`transformers` are direct deps (ML features). Respect an 8 GB system RAM ceiling (no GPU assumed) when wiring them — this is separate from the CLI's own <100 MB baseline memory budget above, which only covers the CLI process before ML models are loaded.

## Naming

Repo `openreview` · PyPI `openreview-cli` · CLI `openreview` · import `openreview_cli` · modes `PreCheck`/`HireCheck`/… with lowercase subcommands.

**Name collision:** `openreview.net` (academic peer-review platform) is unrelated. Qualify web searches/package lookups with `openreview-cli`; never import or link to openreview.net.

## Conventions

- **TDD**: failing test first, minimal code to pass, refactor. No production code without a prior test.
- Conventional Commits (`feat:`/`fix:`/`docs:`/`test:`/`refactor:`/`chore:`); branches `feat/`/`fix/`/`docs/` (in practice also `chore/`, `ci/`, `test/`).
- GitHub protection (as configured in repo settings, not verifiable from tracked files): `main` needs PR + approval + code-owner review + passing checks; no force-push. Secret scanning + push protection active.

## Gotchas (hard-earned)

- **TUI must not import litellm at module level.** `gateway.cost` imports litellm (~4.5s) when actually used; `gateway/__init__.py` itself is now a lazy facade and no longer forces this import on package import. `VALID_SLOTS` lives in `openreview_cli/slots.py` for this reason; `tui/domain/gateway.py` imports lazily. Rule: no module-level `from openreview_cli.gateway...` in any `tui/` module.
- **Memory tests hang in the full suite** — spaCy `en_core_web_lg` (~600 MB) + Presidio aren't fully GC'd running alongside the rest of the suite (currently 3935 tests total). Always `-m memory` standalone (CI does this). Don't let sub-agents include memory tests in a full `uv run pytest`.
- **`tests/conftest.py` caches one `PiiEngine`/spaCy model per session** and autouse-injects it into `strip_pii`/`strip_pii_clauses`. Don't instantiate `PiiEngine` per test — use the `pii_engine` fixture.
- **TUI tests auto-marked `slow`** via `tests/integration/tui/conftest.py` (`pytest_collection_modifyitems`).
- **SIGTERM test (formerly known-broken, now passing):** `test_sigterm_mid_review_cancels_cleanly` (`tests/integration/tui/test_app.py`) passes — commit `10840a0` (2026-07-27) replaced `sys.exit` with Textual `self.exit()` in `_on_signal` (`tui/app.py:189`), so the handler no longer escapes `run_test`. The stale `xfail` marker was removed.
- **Sockets disabled in tests by default** (`pytest-socket`, `--disable-socket --allow-unix-socket` in addopts). Internet tests: `@pytest.mark.network` (conftest auto-enables). Local 127.0.0.1 test servers: `@pytest.mark.enable_socket` directly — localhost is AF_INET, still blocked. `--allow-unix-socket` is load-bearing: asyncio needs `socket.socketpair()`.
- **`tests/integration/test_no_pii_flag.py`, `test_pii_memory.py`, `test_pii_accuracy.py`, `test_config_change.py` are real tests now** — older notes calling them skeletons are stale.

## Don'ts

- No product logic without an approved spec entry (spec-kit workflow; `specs/`).
- No spec deps pre-installed ahead of their feature.
- Don't treat `products/` specs as final — confirm scope before committing to an interpretation.
- Don't mention the audience in repo metadata (see above).
- Don't link openreview.net.
- Don't change `[tool.ruff]`/`[tool.mypy]`/pytest config without confirming first — there's no longer a spec doc to sync it against.

## Hallucination detection — transition plan (spec 010)

`src/openreview_cli/benchmark/hallu_detect.py` uses a ROUGE-L lexical-overlap placeholder (EXPERIMENTAL). Contract: `HallucinationDetector.detect(claims, sources) -> list[bool]`; both `LexicalOverlapDetector` (default) and `CGDPODetector` are implemented and selected by `--hallucination-method=lexical|cg-dpo` (`VALID_HALLUCINATION_METHODS` in `benchmark/cli.py`). `CGDPODetector` currently wraps the Gateway-based `CitationGroundingDiscriminator`; the real CG-DPO method (capability C-21, research-proven concept, NOT BUILT) is a future swap of that class's internals — no harness breaking changes. Default stays `lexical` until the dedicated CG-DPO model lands (D-7 wiring: RESOLVED).

## Orchestrator

### Roles
- **Lead**: holds project context, never executes
  work itself, only dispatches fresh sub-agents per stage, does one final
  quality-control pass before anything reaches the human.
- Standing rule: a sub-agent's output is never accepted directly. It
  always routes to a second, independently-dispatched sub-agent before
  being treated as done.

### Size gate (Lead classifies, no sub-agent needed)
- **Small**: fits in one 2-5 minute unit, no real design decision, touches
  one file or a tightly related few → skip to: fresh sub-agent implements
  → fresh sub-agent reviews → Lead QC.
- **Big**: needs a design decision, touches multiple modules, or is
  unclear upfront → full pipeline below.

### Full pipeline (big tasks), each stage its own fresh sub-agent
1. **Brainstorm** — explores alternatives, produces a design doc, writes
   no code. If the task touches a TUI screen or flow, use impeccable's
   `shape`/`critique` here to think through the UX before code gets
   written.
2. **Worktree** — isolated git worktree for the work (local-only, no
   approval needed, doesn't push).
3. **Plan** — breaks the design into tasks (2-5 min each), exact file
   paths, verification steps.
   - Review the plan: `caveman-review` (terse pass) + `ponytail-audit`
     (over-engineering). Flagged items go back to the plan sub-agent,
     reject-and-redo loop.
4. **Subagent-driven development** — one fresh sub-agent per task; a
   fresh task-reviewer sub-agent checks spec compliance per task
   (Superpowers' own review), blocks on critical issues. While touching
   TUI code, apply impeccable's anti-pattern rules ambiently (spacing,
   hierarchy, contrast, touch targets), the same way `sys.exit` is
   already avoided in `tui/` without being told each time.
5. **TDD** — failing test first, minimal code, refactor, inside each
   task. Code written before its test gets deleted, not just flagged.
6. **Code review** — fresh sub-agent reviews finished work:
   `caveman-review` (quality pass) + `ponytail-audit` (over-engineering),
   both expanded to full Review Mode (Issue/Evidence/Why it
   fails/Exact fix) before reaching the Lead's report. For TUI work,
   also a deliberate impeccable pass (`audit`, `polish`, `harden`, etc.).

### Lead does final QC, then reports (see "Talking to the human")

### Standalone audits / fact-checks (outside the build pipeline)
Same pattern: fresh sub-agents dispatched for reads, one per section/area.
Sub-agent-to-sub-agent communication uses caveman (terse). Final report
to the human is always expanded to full format, never caveman-speak.

### Skill scoping
- **caveman**: commit messages (`/caveman-commit`), sub-agent-to-sub-agent
  chatter, internal review notes. Never the Lead's final report.
- **ponytail**: `-audit` on plans and finished code, for over-engineering.
- **impeccable**: applies as ambient guidance for any UI/UX decision, not
  just code edits — during Brainstorm or Plan (`shape`/`critique` before
  code gets written), during implementation (anti-pattern rules applied
  while building), and as a deliberate pass afterward (`audit`, `polish`,
  `harden`, etc.). `init`/`document` never run again without explicit
  approval — they regenerate PRODUCT.md/DESIGN.md, which already exist
  and are deliberate. Not officially listed as a supported tool for
  Command Code (unlike ponytail/caveman) — verify the automatic edit
  hook actually fires before relying on it; if it doesn't, apply the
  guidance as instruction only.
- **superpowers**: the pipeline skeleton above, enriched with the rules
  already in this file (worker/verifier, TDD, gh approval gate, CI via
  draft PR, issue filing).

## Talking to the human

Covers how the agent communicates when reporting after a task or review,
and when checking before starting.

### Before starting

- If a wrong assumption would cost real rework to fix, ask first using
  the interview/question tool rather than guessing and reporting back
  a result built on a guess.

### Reporting back

Applies after finishing a task or a review.

**Structure**
- Task/fix report: result first line (what changed, what's true now).
- Review/critique report: first line states issue count and severity
  (e.g. "4 issues found, 1 blocking"), not a summary verdict.
- Bullets or labeled lines for: changes made, decisions, risks, options.
  No cap here, this is the actual work product.
- Close with at most 3 short lines: what was assumed, what's next. If
  the closing explanation would run longer than that, cut it, not the
  bullets above.
- For a multi-step task, report progress in chunks, not one dump at the
  end. Each chunk ends with a "done when" check the human can see is
  true (a command that passed, a file that changed, a test that ran).
- Risky steps (deleting data, overwriting files, anything hard to undo)
  get their own explicit check before or after that step, not folded
  into a later summary.

**Plain language**
- On first use, explain any file path, line number, code term, or
  project-specific word in plain words. Don't assume familiarity.
- Don't reuse a word to mean two different things in the same report.

**Never cut, even to keep it short**
- Warnings.
- Risky-step checks.
- Fact / Assumption / Inference labels.
- Direct pushback (if something looks wrong, say so, don't soften it).
- Flags for missing information.

**Uncertainty**
- Label claims as Fact, Assumption, or Inference when uncertain about
  something checked or changed.
- For an Assumption that would change the result if wrong, add what
  would prove it wrong.
- If something couldn't be verified, say so. Don't fill the gap with a
  confident guess.

## Reports (for the non-technical stakeholder)

Plain-English phase reports in `.specify/memory/reports/` (date-prefixed, regenerated on demand). Template: Part 1 Status (always), Part 2 Concepts (new domain concepts), Part 3 Walkthrough (new files). Teaching method: **Pain → Recipe → Practice** (calibration: `_calibration-2026-06-23.md`). Re-calibrate only when a new domain concept lands (LLM, embedding, vector DB, …).

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/034-multifield-provider-auth/plan.md
<!-- SPECKIT END -->
