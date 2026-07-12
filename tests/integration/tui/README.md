# TUI Integration Tests

These tests use Textual's `app.run_test()` (Pilot) for async integration testing.

## Known Issue: Context Leak on Suite Run

Textual's `run_test()` leaves residual terminal state that causes tests to hang or interact badly when the full suite is run as a single pytest process.

**Workaround**: Run per-file or per-test:

```bash
uv run pytest tests/integration/tui/test_<name>.py -v
```

CI runs each file in isolation, so this is only a local development concern.

## Memory Test Isolation

The `test_app_memory.py` test uses `tracemalloc` and must be run in isolation
with `-m memory` and `--timeout=300` per the AGENTS.md caveat about cumulative
suite load:

```bash
uv run pytest tests/integration/tui/test_app_memory.py -v -m memory --timeout=300
```

## Per-Tab Tests

Each tab has its own test file:

- `test_app.py` — cross-tab tests (launch, navigation, quit, Ctrl-C, search)
- `test_clients_tab.py` — Clients tab CRUD
- `test_playbooks_tab.py` — Playbooks tab import/detail/version diff
- `test_settings_tab.py` — Settings tab sections
- `test_gateway_wizard.py` — Gateway setup wizard
- `test_review_wizard.py` — Review wizard flow + result screen + export
- `test_search_screen.py` — Global search overlay
- `test_recent_reviews.py` — Recent reviews on Home tab
- `test_flow_wiring.py` — End-to-end flow wiring

## Screens

- `test_confirm_modal.py` — ConfirmModal for delete/cancel
- `test_progress_screen.py` — Progress screen during review
- `test_result_screen.py` — Result screen split view
- `test_client_form.py` — Client add/edit form
