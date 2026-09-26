# Plan: Typer CLI Test Routing Fix

**Spec**: 015-typer-cli-test-routing
**Branch**: `fix/015-typer-cli-test-routing`

---

## Approach

### Production Code Fix (2 files changed)

| File | Change |
|------|--------|
| `src/openreview_cli/app.py` | `document_path`: `Argument` → `Option(None, "--document", "-d")` |
| `src/openreview_cli/app.py` | `_validate_threshold()`: accept `None` input |

### Test Code Update (3 files updated)

| File | Change |
|------|--------|
| `tests/integration/test_precheck_pii.py` | Use `--document` flag instead of positional arg |
| `tests/integration/test_no_pii_flag.py` | Use `--document` flag instead of positional arg |
| `tests/integration/test_config_change.py` | Use `--document` flag instead of positional arg |

### Test Code Create (1 file new)

`tests/integration/test_bilateral_flags.py` — subprocess-based CLI flag tests:
- `run_compare()` helper → `subprocess.run([sys.executable, "-m", "openreview_cli", "precheck", "compare", ...])`
- 7 tests across 5 task areas (T050–T053, T055)
- Flag-only tests paired with `--align-only` to avoid AI gateway dependency

### Spec Update (1 file)

`specs/014-bilateral-comparison/tasks.md` — remove "deferred" annotations from T050–T053, T055.

---

## Verification

```bash
uv run pytest tests/integration/test_bilateral_flags.py -v  # 7 new tests
uv run pytest tests/integration/ -q                          # no regression
uv run pytest tests/unit/ -q                                 # unit tests intact
```
