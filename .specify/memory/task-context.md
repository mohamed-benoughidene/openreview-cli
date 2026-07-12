# Task Context: Feature 032-tui-spec

**Generated**: 2026-07-11
**Hook**: `speckit.task-grounding`
**Feature**: Interactive TUI (Terminal User Interface)

---

## Verified Dependencies

```
VERIFIED DEP: textual | VERSION: 8.2.8 | SOURCE: https://pypi.org/project/textual/
VERIFIED DEP: pytest-asyncio | VERSION: 1.4.0 | SOURCE: https://pypi.org/project/pytest-asyncio/
VERIFIED DEP: pydantic | VERSION: 2.13.4 | SOURCE: https://pypi.org/project/pydantic/
VERIFIED DEP: rich | VERSION: 15.0.0 | SOURCE: https://pypi.org/project/rich/
VERIFIED DEP: typer | VERSION: 0.26.8 | SOURCE: https://pypi.org/project/typer/
VERIFIED DEP: questionary | VERSION: 2.1.1 | SOURCE: https://pypi.org/project/questionary/
```

**Version Drift**:
- `pytest-asyncio`: pyproject.toml pins `>=0.24.0`, current stable is 1.4.0 (major jump). Constraint should be updated to `>=1.0.0`.
- `typer`: pyproject.toml pins `>=0.26.7`, current stable is 0.26.8. Minor patch drift, no action needed.

---

## Project Structure (actual)

```text
src/openreview_cli/
├── __init__.py
├── __main__.py
├── app.py                          # Typer CLI entry (3124 lines)
├── errors.py
├── py.typed
├── benchmark/                      # Benchmark harness
│   ├── __init__.py, baseline.py, cli.py, hallu_detect.py, memory.py
│   ├── metrics.py, metrics_pii.py, models.py, prompt_ab.py
│   ├── regression.py, report.py, runner.py, _utils.py
│   └── datasets/ (contract_nli, cuad, maud, pii_contracts)
├── bilateral/                      # Bilateral comparison
│   ├── __init__.py, align.py, colors.py, comparison.py
│   ├── models.py, prompts.py, report.py
├── chunking/                       # Document chunking
│   ├── __init__.py, models.py, splitter.py, stream.py, tokenizer.py
├── config/                         # Configuration
│   ├── __init__.py, auth.py, loader.py, paths.py
├── gateway/                        # AI Gateway
│   ├── __init__.py, cost.py, errors.py, models.py
│   ├── redaction.py, registry.py, router.py
│   ├── tier_accuracy.py, tier_config.py, tier_router.py
│   ├── tier_tracker.py, wizard.py
├── graph/                          # Contract graph
│   ├── __init__.py, builder.py, detectors.py, diff.py
│   ├── health.py, metrics.py, models.py, view.py
├── grounding/                      # Grounding/citation
│   ├── __init__.py, audit.py, corruption.py, discriminator.py
│   ├── metrics.py, models.py, prompts.py
├── negotiation/                    # Game-theoretic negotiation
│   ├── __init__.py, models.py, payoffs.py
│   ├── recommend.py, report.py, solvers.py
├── parsing/                        # Document parsing
│   ├── __init__.py, clause_clusterer.py, clause_detector.py
│   ├── docx_parser.py, models.py, pdf_parser.py, stream.py
├── pii/                            # PII stripping
│   ├── __init__.py, audit.py, cache.py, config_hash.py
│   ├── encryption.py, engine.py, mapping.py, models.py
│   ├── placeholders.py, recognizers.py, retention.py
├── pipeline/                       # Async pipeline framework
│   ├── __init__.py, base.py, errors.py, progress.py, runner.py
│   └── adapters/ (benchmark, chunk, comparison, generate, parse, retrieve, strip)
├── prompts/                        # Prompt management
│   ├── __init__.py, cli.py, defaults.py, models.py
│   ├── store.py, variables.py
├── recovery/                       # Error recovery
│   ├── __init__.py, coordinator.py, models.py
│   └── strategies/ (auto_retry, graceful_degradation, provider_fallback, stage_isolation, user_guided_recovery)
├── retrieval/                      # Hierarchical retrieval
│   ├── __init__.py, bm25.py, dense.py, engine.py, errors.py
│   ├── ingest.py, models.py, rerank.py, rrf.py, storage.py
├── review/                         # Review pipeline
│   ├── __init__.py, base.py, colors.py, comparison_agent.py
│   ├── extraction.py, _gateway.py, models.py, pipeline.py
│   ├── playbook.py, prompts.py, qa.py, report.py, templates.py
│   └── memo/ (exporter, filename, formats, models)
├── storage/                        # SQLite storage
│   └── __init__.py, database.py

tests/
├── conftest.py, __init__.py
├── helpers/ (mock_gateway.py)
├── fixtures/ (benchmark, docx, grounding, nda_corpus, negotiation, pdf, pii, playbooks, prompts, retrieval, review)
├── unit/                           # 120+ unit test files
├── integration/                    # 80+ integration test files
```

---

## Existing Files

### Flagged files (TUI will touch these)

- **EXISTS**: `src/openreview_cli/app.py` — Typer CLI entry, 3124 lines. Plan says MODIFIED (add TUI dispatch when no subcommand).
- **EXISTS**: `src/openreview_cli/review/__init__.py` — Review pipeline. Exports `run_review()`, `ReviewReport`.
- **EXISTS**: `src/openreview_cli/review/base.py` — `ReviewCommand` base class, PII orchestration.
- **EXISTS**: `src/openreview_cli/review/playbook.py` — Playbook loader (YAML parsing, validation).
- **EXISTS**: `src/openreview_cli/gateway/router.py` — `Gateway` class, routing, cost tracking.
- **EXISTS**: `src/openreview_cli/storage/database.py` — SQLite layer (725 lines), clients/reviews CRUD.
- **EXISTS**: `src/openreview_cli/gateway/tier_config.py` — `PrivacyTier` enum, tier parsing.
- **EXISTS**: `src/openreview_cli/config/loader.py` — Config loading (YAML), `load_config()`, `get_config_value()`.
- **EXISTS**: `src/openreview_cli/config/auth.py` — Auth credential management.
- **EXISTS**: `src/openreview_cli/gateway/wizard.py` — Interactive setup wizard (questionary).

### Package files (all exist)

- `src/openreview_cli/__init__.py` — `__version__`
- `src/openreview_cli/__main__.py` — `python -m openreview_cli`
- `src/openreview_cli/errors.py` — Exit codes, error formatting
- All 15 subpackages (benchmark, bilateral, chunking, config, gateway, graph, grounding, negotiation, parsing, pii, pipeline, prompts, recovery, retrieval, review, storage) exist with their respective modules.

---

## Plan vs Filesystem

### Plan-specified NEW paths

```
NEW: src/openreview_cli/tui/__init__.py              — DOES NOT EXIST
NEW: src/openreview_cli/tui/app.py                    — DOES NOT EXIST
NEW: src/openreview_cli/tui/launcher.py               — DOES NOT EXIST
NEW: src/openreview_cli/tui/tabs/__init__.py          — DOES NOT EXIST
NEW: src/openreview_cli/tui/tabs/home.py              — DOES NOT EXIST
NEW: src/openreview_cli/tui/tabs/review.py            — DOES NOT EXIST
NEW: src/openreview_cli/tui/tabs/clients.py           — DOES NOT EXIST
NEW: src/openreview_cli/tui/tabs/playbooks.py         — DOES NOT EXIST
NEW: src/openreview_cli/tui/tabs/settings.py          — DOES NOT EXIST
NEW: src/openreview_cli/tui/widgets/__init__.py       — DOES NOT EXIST
NEW: src/openreview_cli/tui/widgets/status_bar.py     — DOES NOT EXIST
NEW: src/openreview_cli/tui/widgets/description_bar.py — DOES NOT EXIST
NEW: src/openreview_cli/tui/widgets/filter_list.py    — DOES NOT EXIST
NEW: src/openreview_cli/tui/widgets/file_picker.py    — DOES NOT EXIST
NEW: src/openreview_cli/tui/screens/__init__.py       — DOES NOT EXIST
NEW: src/openreview_cli/tui/screens/confirm.py        — DOES NOT EXIST
NEW: src/openreview_cli/tui/screens/search.py         — DOES NOT EXIST
NEW: src/openreview_cli/tui/screens/review_wizard.py  — DOES NOT EXIST
NEW: src/openreview_cli/tui/screens/gateway_wizard.py — DOES NOT EXIST
NEW: src/openreview_cli/tui/screens/result.py         — DOES NOT EXIST
NEW: src/openreview_cli/tui/screens/client_form.py    — DOES NOT EXIST
NEW: src/openreview_cli/tui/domain/__init__.py        — DOES NOT EXIST
NEW: src/openreview_cli/tui/domain/gateway.py         — DOES NOT EXIST
NEW: src/openreview_cli/tui/domain/review.py          — DOES NOT EXIST
NEW: src/openreview_cli/tui/domain/clients.py         — DOES NOT EXIST
NEW: src/openreview_cli/tui/domain/playbooks.py       — DOES NOT EXIST
NEW: src/openreview_cli/tui/domain/privacy.py         — DOES NOT EXIST
NEW: src/openreview_cli/tui/tcss/app.tcss             — DOES NOT EXIST
NEW: src/openreview_cli/tui/tcss/tabs.tcss            — DOES NOT EXIST
NEW: src/openreview_cli/tui/tcss/widgets.tcss         — DOES NOT EXIST
NEW: tests/unit/tui/test_launcher.py                  — DOES NOT EXIST
NEW: tests/unit/tui/test_status_bar.py                — DOES NOT EXIST
NEW: tests/unit/tui/test_filter_list.py               — DOES NOT EXIST
NEW: tests/unit/tui/test_widgets.py                   — DOES NOT EXIST
NEW: tests/integration/tui/test_app.py                — DOES NOT EXIST
NEW: tests/integration/tui/test_review_wizard.py      — DOES NOT EXIST
NEW: tests/integration/tui/test_gateway_wizard.py     — DOES NOT EXIST
NEW: tests/integration/tui/test_clients_tab.py        — DOES NOT EXIST
NEW: tests/integration/tui/test_playbooks_tab.py      — DOES NOT EXIST
NEW: tests/integration/tui/test_settings_tab.py       — DOES NOT EXIST
```

### Plan-specified MODIFIED paths

```
MODIFIED: src/openreview_cli/app.py — EXISTS, add TUI dispatch when no subcommand
```

### Mismatches

```
NONE — all plan paths are either confirmed NEW (do not exist) or confirmed EXISTING (will be modified)
```

---

## Summary Counts

| Metric | Count |
|--------|-------|
| TOTAL EXISTING SOURCE FILES (src/openreview_cli/) | 143 |
| TOTAL NEW PATHS IN PLAN (source) | 32 |
| TOTAL NEW PATHS IN PLAN (tests) | 10 |
| TOTAL NEW PATHS IN PLAN (total) | 42 |
| MISMATCHES | 0 |
| FILES TUI WILL MODIFY | 1 (`app.py`) |

---

## Files TUI Will Modify (Existing)

For serialization dispatch:

1. **`src/openreview_cli/app.py`** — Add TTY check + TUI launcher dispatch when no subcommand provided. Plan says: add `sys.stdin.isatty()` guard before `app()` call; if TTY, import and call `launch_tui()` from `tui.launcher`; else fall through to Typer.
