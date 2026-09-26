# Tasks: Typer CLI Test Routing Fix

**Spec**: 015-typer-cli-test-routing
**Branch**: `fix/015-typer-cli-test-routing`

---

- [x] T001 **Fix callback positional arg** — `document_path`: `Argument` → `Option(None, "--document", "-d")` in `app.py`
- [x] T002 **Fix `_validate_threshold`** — guard against `None` (latent bug masked by broken routing)
- [x] T003 **Update `test_precheck_pii.py`** — positional arg → `--document` flag
- [x] T004 **Update `test_no_pii_flag.py`** — positional arg → `--document` flag
- [x] T005 **Update `test_config_change.py`** — positional arg → `--document` flag
- [x] T006 **Create `test_bilateral_flags.py`** — subprocess-based CLI flag tests with `run_compare()` helper
- [x] T007 **Write T050** — `--align-only` test
- [x] T008 **Write T051** — `--format json --output` test
- [x] T009 **Write T052** — `--confidence-threshold` acceptance + rejection tests
- [x] T010 **Write T053** — `--conservative` acceptance + mutual exclusion tests
- [x] T011 **Write T055** — `--verbose` test
- [x] T012 **Unblock spec 014** — remove "deferred" from T050–T053, T055 in `014/tasks.md`
- [x] T013 **Verify** — `uv run pytest tests/integration/test_bilateral_flags.py -v` → 7 passed
- [x] T014 **Regression check** — 14 existing integration tests + 715 unit tests all green
