# Task Grounding Context: 032-tui-spec

**Generated**: 2026-07-12 by `speckit.task-grounding`
**Feature**: Interactive TUI (Terminal User Interface)

---

## Verified Dependencies

All 6 dependencies confirmed from `verified-sources.md`:

| # | Dep | Plan Version | Verified Version | Status | Drift |
|---|-----|-------------|-----------------|--------|-------|
| 1 | textual | >=8.2.8 | 8.2.8 | CONFIRMED | None |
| 2 | pytest-asyncio | >=0.24.0 | 1.4.0 | CONFIRMED | ⚠ Major (0.x → 1.x) |
| 3 | pydantic | >=2.13.4 | 2.13.4 | CONFIRMED | None |
| 4 | rich | >=15.0.0 | 15.0.0 | CONFIRMED | None |
| 5 | typer | >=0.26.7 | 0.26.8 | CONFIRMED | Minor patch |
| 6 | questionary | >=2.1.1 | 2.1.1 | CONFIRMED | None |

**Behavioral claims verified**: `Input(password=True)`, `ModalScreen`, `DirectoryTree`, `app.run_test()` async Pilot, `asyncio_mode="auto"`, Rich as Textual foundation.

---

## Project Structure (actual)

### src/openreview_cli/ — full package tree (level 2)

```
src/openreview_cli/
├── __init__.py
├── __main__.py
├── app.py
├── benchmark/
├── bilateral/
├── chunking/
├── config/
├── errors.py
├── gateway/
├── graph/
├── grounding/
├── negotiation/
├── parsing/
├── pii/
├── pipeline/
├── prompts/
├── py.typed
├── recovery/
├── retrieval/
├── review/
├── storage/
└── tui/                         ← Feature 032 location
    ├── __init__.py
    ├── app.py
    ├── launcher.py
    ├── domain/
    │   ├── __init__.py
    │   ├── clients.py
    │   ├── gateway.py
    │   ├── playbooks.py
    │   ├── privacy.py
    │   ├── review.py
    │   └── search.py            ← EXTRA (not in plan)
    ├── screens/
    │   ├── __init__.py
    │   ├── client_detail.py     ← EXTRA (not in plan)
    │   ├── client_form.py
    │   ├── confirm.py
    │   ├── db_error.py          ← EXTRA (not in plan)
    │   ├── gateway_wizard.py
    │   ├── playbook_detail.py   ← EXTRA (not in plan)
    │   ├── progress.py          ← EXTRA (not in plan)
    │   ├── result.py
    │   ├── review_wizard.py
    │   └── search.py
    ├── tabs/
    │   ├── __init__.py
    │   ├── clients.py
    │   ├── home.py
    │   ├── playbooks.py
    │   ├── review.py
    │   └── settings.py
    └── widgets/
        └── __init__.py          ← EMPTY shell only
```

### tests/ — TUI test layout

```
tests/
├── unit/
│   └── tui/
│       ├── __init__.py
│       ├── test_clients_domain.py
│       ├── test_privacy_domain.py
│       └── test_review_domain_wrapper.py
└── integration/
    └── tui/
        ├── __init__.py
        ├── README.md
        ├── test_app.py
        ├── test_app_cold_start.py
        ├── test_app_memory.py
        ├── test_client_form.py
        ├── test_clients_tab.py
        ├── test_confirm_modal.py
        ├── test_flow_wiring.py
        ├── test_gateway_wizard.py
        ├── test_playbooks_tab.py
        ├── test_progress_screen.py
        ├── test_recent_reviews.py
        ├── test_result_screen.py
        ├── test_review_wizard.py
        ├── test_search_screen.py
        └── test_settings_tab.py
```

---

## Existing Files

All `.py` files in `src/openreview_cli/` are tracked above. The TUI subpackage has **28 files** total (including `__init__.py`s). Key modules with exports not read (beyond plan scope); all are `EXISTS: <path>`.

---

## Plan vs Filesystem

### Paths in plan that are NEW (don't exist yet)

| Plan Path | Status |
|-----------|--------|
| `tui/widgets/status_bar.py` | NEW |
| `tui/widgets/description_bar.py` | NEW |
| `tui/widgets/filter_list.py` | NEW |
| `tui/widgets/file_picker.py` | NEW |
| `tui/tcss/app.tcss` | NEW |
| `tui/tcss/tabs.tcss` | NEW |
| `tui/tcss/widgets.tcss` | NEW |
| `tests/unit/tui/test_launcher.py` | NEW |
| `tests/unit/tui/test_status_bar.py` | NEW |
| `tests/unit/tui/test_filter_list.py` | NEW |
| `tests/unit/tui/test_widgets.py` | NEW |

**TOTAL NEW: 11**

### Paths in filesystem but NOT in plan (extras)

| Actual Path | Note |
|-------------|------|
| `tui/domain/search.py` | Extra domain module |
| `tui/screens/client_detail.py` | Extra screen |
| `tui/screens/db_error.py` | Extra screen |
| `tui/screens/playbook_detail.py` | Extra screen |
| `tui/screens/progress.py` | Extra screen |
| `tests/unit/tui/test_clients_domain.py` | Extra unit test |
| `tests/unit/tui/test_privacy_domain.py` | Extra unit test |
| `tests/unit/tui/test_review_domain_wrapper.py` | Extra unit test |
| `tests/integration/tui/README.md` | Extra doc |
| `tests/integration/tui/test_app_cold_start.py` | Extra integration test |
| `tests/integration/tui/test_app_memory.py` | Extra integration test |
| `tests/integration/tui/test_client_form.py` | Extra integration test |
| `tests/integration/tui/test_confirm_modal.py` | Extra integration test |
| `tests/integration/tui/test_flow_wiring.py` | Extra integration test |
| `tests/integration/tui/test_progress_screen.py` | Extra integration test |
| `tests/integration/tui/test_recent_reviews.py` | Extra integration test |
| `tests/integration/tui/test_result_screen.py` | Extra integration test |
| `tests/integration/tui/test_search_screen.py` | Extra integration test |

**TOTAL EXTRA: 18**

### Mismatches

| Issue | Detail |
|-------|--------|
| **MISMATCH** | Plan says `tui/widgets/status_bar.py` but filesystem has `tui/widgets/__init__.py` (empty shell, no modules) |
| **MISMATCH** | Plan says `tui/widgets/description_bar.py` but filesystem has only `__init__.py` |
| **MISMATCH** | Plan says `tui/widgets/filter_list.py` but filesystem has only `__init__.py` |
| **MISMATCH** | Plan says `tui/widgets/file_picker.py` but filesystem has only `__init__.py` |
| **MISMATCH** | Plan says `tests/unit/tui/test_launcher.py` but filesystem has `test_clients_domain.py`, `test_privacy_domain.py`, `test_review_domain_wrapper.py` (different tests) |
| **EXTRA** | Filesystem has 5 extra TUI modules not in plan (search domain, client_detail, db_error, playbook_detail, progress screens) |
| **EXTRA** | Filesystem has 9 extra integration test files not in plan |

---

## Summary

| Metric | Count |
|--------|-------|
| TOTAL EXISTING FILES (TUI package) | 28 |
| TOTAL NEW PATHS (plan says missing) | 11 |
| TOTAL EXTRA PATHS (filesystem has beyond plan) | 18 |
| MISMATCHES (plan vs filesystem) | 7 |
