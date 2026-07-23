# AGENTS.md

OpenCode instructions for `openreview`. Read this before touching anything in the repo.

## Status

Python 3.12 project, pre-alpha but far along: document parsing (PDF/DOCX/clause detection), PII stripping (Presidio, encrypted mapping), AI Gateway (routing, cost tracking, registry, wizard, redaction), review pipeline (extraction → QA → comparison, memo generation, 24 bundled playbooks), chunking/retrieval/grounding/negotiation/bilateral/recovery/graph/benchmark modules, a Textual TUI, and a Typer CLI with many subcommands (`parse`, `chunk`, `ingest`, `retrieve`, `negotiate`, `export`, `precheck`, `gateway`, `playbook`, `pii`, `client`, `config`, `graph`, `benchmark`, `prompt`).

Product design lives in `products/openreview/` (gitignored) and is **preliminary, not final**. Spec-driven development via spec-kit: specs in `specs/` (001–034), deferred work tracked in `specs/DEFERRED.md` — check it before touching a module with open deferrals.

## Tracked vs. local

- **Gitignored:** `AGENTS.md` (this file — local only), `products/`, `Papers/`, `.venv/`.
- **Tracked:** `specs/`, `.specify/` (constitution at `.specify/memory/constitution.md`), `.opencode/`, everything in "Layout" below.
- **Submodule:** `.tools/ponytail` — after clone, `git submodule update --init` or `opencode.json` points at a missing path and the ponytail plugin won't load.

## Audience

The product's user audience is **intentionally not mentioned** in repo metadata (`pyproject.toml` description, `README.md`, AGENTS.md) or in spec excerpts quoted into user-facing artifacts. Strip audience references from text you draft into the repo. `products/` may mention it — internal material, not metadata.

## Layout

```
src/openreview_cli/          # Package (src layout). Entry: app.py (Typer), __main__.py
  ├─ slots.py                # VALID_SLOTS — outside gateway/ on purpose (see Gotchas)
  ├─ llm_json.py             # Shared LLM JSON/fence-stripping helper
  ├─ config/ storage/        # Auth, paths, YAML/TOML loader; SQLite layer
  ├─ parsing/                # PdfParser (PyMuPDF streaming), DocxParser, clause detector
  ├─ pii/                    # Presidio engine, recognizers, encryption, mapping, audit
  ├─ gateway/                # Model routing, registry (models.json), cost, wizard
  ├─ review/                 # Pipeline + agents + memo; playbooks/ (24 YAML)
  ├─ pipeline/ chunking/ retrieval/ grounding/ negotiation/ bilateral/ recovery/ graph/ benchmark/ prompts/
  └─ tui/                    # Textual app (app.py, screens/, domain/, widgets/)
tests/{unit,integration,fixtures,helpers}   # ~110 unit + ~93 integration files
scripts/                     # 4 standalone benchmark scripts
specs/                       # spec-kit specs 001–034 + DEFERRED.md
.github/workflows/{ci,release}.yml
```

Version is hardcoded in **two** places: `pyproject.toml` and `src/openreview_cli/__init__.py` (`__version__`). Bump both.

## Setup

```bash
git submodule update --init   # required — ponytail plugin
uv sync                       # runtime + dev deps into .venv
```

## Commands

```bash
uv run openreview --help
uv run pytest -m "not slow" -q          # fast feedback — skips TUI + memory
uv run pytest -m slow                   # ~105 TUI tests (Textual run_test startup cost)
uv run pytest -m memory -q --timeout=300  # ALWAYS run solo, never in full suite (see Gotchas)
uv run pytest tests/unit/test_x.py::test_y  # single test
uv run ruff check . && uv run ruff format .
uv run mypy src/ tests/                 # strict
uv run pre-commit run --all-files       # before every commit
```

Pytest markers (pyproject.toml): `slow`, `integration`, `e2e`, `memory`, `benchmark`, `accuracy`, `network`.

**CI** (`ci.yml`, push to main + PRs): 5 parallel jobs — `lint`, `types`, `test` (unit only), `memory` (installs spaCy model), `benchmark` (main only, `|| true`). Uses `actions/checkout@v7` + `astral-sh/setup-uv@v8.2.0`.

**Pre-commit**: hygiene hooks, `ruff --fix`, `ruff-format`, `mypy` (`uv run mypy src/ tests/`), `pytest-fast` (collect-only). `uv run pre-commit install` once per clone; sub-agents in fresh shells must verify `.git/hooks/pre-commit` exists or run `uv run pre-commit run --all-files` before `git add` and stage reformats.

**Release** (`release.yml`): tag `v*.*.*` → build → GitHub release → PyPI (`UV_PUBLISH_TOKEN`). Do not push release tags casually — tag protection restricts them to the owner anyway.

## Hard constraints

- **Python 3.12** pinned. **uv** only — no pip/poetry/pipx. New deps via `uv add <pkg>`, never hand-edited, and only when the feature needing them lands.
- **AGPL-3.0 + Commercial dual-license** — no license-incompatible code.
- **Local CLI only.** No web server, FastAPI/Flask, or long-running processes.
- **Privacy first.** PII stripped before any external API call. API keys in `auth.json` (chmod 600) only. Never log raw contract text, PII, or keys — redact even in `--debug`.
- **Memory budget.** Peak < 100 MB (floor 110 MB, enforced by `memory_tracker` fixture). Stream parsers page-by-page; don't load full documents.
- **Forbidden by spec** (`TechStack.md` rationale): `langchain`, `llama-index`, `FAISS`, `spaCy` *for PII* (Presidio uses it internally — the ban is on direct use), `sentence-transformers` (use Ollama), `loguru`/`structlog` (stdlib logging), `FastAPI`/`Flask`. Note: `click` is a direct dep despite the spec preferring Typer — pyproject.toml is the source of truth for what's installed; surface conflicts instead of "fixing" them silently.
- `torch`/`transformers` are direct deps (ML features). Respect the 8 GB / no-GPU target when wiring them.

## Naming

Repo `openreview` · PyPI `openreview-cli` · CLI `openreview` · import `openreview_cli` · modes `PreCheck`/`HireCheck`/… with lowercase subcommands.

**Name collision:** `openreview.net` (academic peer-review platform) is unrelated. Qualify web searches/package lookups with `openreview-cli`; never import or link to openreview.net.

## Conventions

- **TDD**: failing test first, minimal code to pass, refactor. No production code without a prior test.
- Conventional Commits (`feat:`/`fix:`/`docs:`/`test:`/`refactor:`/`chore:`); branches `feat/`/`fix/`/`docs/`.
- GitHub protection: `main` needs PR + approval + code-owner review + passing checks; no force-push. Secret scanning + push protection active.

## Gotchas (hard-earned)

- **TUI must not import litellm at module level.** `gateway/__init__.py` → `gateway.cost` → litellm (~4.5s import). `VALID_SLOTS` lives in `openreview_cli/slots.py` for this reason; `tui/domain/gateway.py` imports lazily. Rule: no module-level `from openreview_cli.gateway...` in any `tui/` module.
- **Memory tests hang in the full suite** — spaCy `en_core_web_lg` (~600 MB) + Presidio aren't fully GC'd after ~1900 tests. Always `-m memory` standalone (CI does this). Don't let sub-agents include memory tests in a full `uv run pytest`.
- **`tests/conftest.py` caches one `PiiEngine`/spaCy model per session** and autouse-injects it into `strip_pii`/`strip_pii_clauses`. Don't instantiate `PiiEngine` per test — use the `pii_engine` fixture.
- **TUI tests auto-marked `slow`** via `tests/integration/tui/conftest.py` (`pytest_collection_modifyitems`).
- **Known-broken test:** `test_sigterm_mid_review_cancels_cleanly` — `tui/app.py:167` `_on_signal` calls `sys.exit`, escapes Textual `run_test`. Pre-existing; don't "fix" the test by accident when nearby.
- **`tests/integration/test_no_pii_flag.py`, `test_pii_memory.py`, `test_pii_accuracy.py`, `test_config_change.py` are real tests now** — older notes calling them skeletons are stale.

## Don'ts

- No product logic without an approved spec entry (spec-kit workflow; `specs/`).
- No spec deps pre-installed ahead of their feature.
- Don't treat `products/` specs as final — confirm scope before committing to an interpretation.
- Don't mention the audience in repo metadata (see above).
- Don't link openreview.net.
- Don't change `[tool.ruff]`/`[tool.mypy]`/pytest config without updating the spec docs they mirror (`DevelopmentSetup.md`, `TestingStrategy.md`).

## Hallucination detection — transition plan (spec 010)

`benchmark/hallu_detect.py` uses a ROUGE-L lexical-overlap placeholder (EXPERIMENTAL). Real method: CG-DPO (capability C-21, TRL 3). Contract: `HallucinationDetector.detect(claims, sources) -> list[bool]`; `LexicalOverlapDetector` now, `CGDPODetector` later behind `--hallucination-method=lexical|cg-dpo`. Default stays `lexical` until C-21 is TRL 7+. Swap = new class + CLI wiring; no harness breaking changes.

## Reports (for the non-technical stakeholder)

Plain-English phase reports in `.specify/memory/reports/` (date-prefixed, regenerated on demand). Template: Part 1 Status (always), Part 2 Concepts (new domain concepts), Part 3 Walkthrough (new files). Teaching method: **Pain → Recipe → Practice** (calibration: `_calibration-2026-06-23.md`). Re-calibrate only when a new domain concept lands (LLM, embedding, vector DB, …).

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/034-multifield-provider-auth/plan.md
<!-- SPECKIT END -->
