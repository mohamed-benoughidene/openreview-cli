# Pre-Existing Test Failures — Investigation Debt

Collected 2026-07-23 during branch `fix/markdown-fence-json-parsing` (base `369ebaf`).
All failures below reproduce on the base commit — none were caused by that branch.
Evidence gathered per-test; fix directions are one-line starting points, not plans.

## Priority 1 — Real bugs (code or test)

### 1. `test_retrieval_fusion.py::TestRRFFusion::test_sparse_hybrid_correlation_less_than_one` — TEST BUG (mock signature drift)
- **Source:** `tests/integration/test_retrieval_fusion.py:211` — `def _mock_embed(slot: str, texts: list[str])` (no `requirement` param)
- **Call site:** `src/openreview_cli/retrieval/dense.py:33` — `gateway.embed("embedding", [text], requirement=CapabilityRequirement(capability="embedding"))`
- **Real signature:** `src/openreview_cli/gateway/router.py:484-490` — `embed(self, slot, texts, *, session_id=None, requirement=None)`
- **Mechanism:** `MagicMock.side_effect` receives all caller kwargs → `TypeError: _mock_embed() got an unexpected keyword argument 'requirement'` → dense path dies, falls back to BM25, assertion fails.
- **Fix:** `def _mock_embed(slot, texts, *, requirement=None, session_id=None)`.
- **Action:** sweep ALL `_mock_embed` definitions in tests/ for the same drift (at least `test_retrieval_fusion.py:211` and check `test_retrieval_benchmark.py:175`).

### 2. `test_gateway_cli.py` — 3 tests fail consistently on base AND branch (fully mocked — NOT environmental)
- `TestGatewayCli::test_gateway_providers` (asserts `'ollama' in result.stdout`; table renders providers with 0 models, ollama row absent)
- `TestGatewayCli::test_gateway_models`
- `TestGatewayCli::test_gateway_models_invalid_provider`
- **Source:** `test_gateway_cli.py:63,74` (`test_gateway_providers`) — both `ModelRegistry.load` and `ModelRegistry.list_providers` are monkeypatched; no network dependency exists.
- **Hypothesis:** real pre-existing failure — either the CLI command renders through a different registry path than the one mocked, or the mock's provider list doesn't include `ollama` while the assertion expects it. Needs actual debugging, not environment fixes.
- **Fix:** run `openreview gateway providers` with the mock active and trace which registry method the command actually calls.

## Priority 2 — Test-infra issues (environment-sensitive tests)

### 3. `test_benchmark_baseline.py::TestMockBaseline::test_mock_baseline_produces_correct_result_count` — network-dependent — **FIXED** (branch `fix/test-network-hermeticity`)
- **Chain:** `run_mock_baseline` → `BenchmarkRunner(cache_dir=None)` (`baseline.py:66-72`) → `runner.py:192-194` → `load_cuad_dataset(cache_dir=None)` → `cuad.py:109` `httpx.get(CUAD_URL, timeout=300)`. Sandbox has no/blocked network → 300s hang.
- **Fix applied:** class-level autouse fixture monkeypatches all three dataset loaders (`cuad`, `maud`, `contract_nli`) with canned 5-field items. Verified: 28 passed in 16.5s, no network.

### 4. `test_benchmark_modes.py::TestModeValidation::test_modes_validation_accepts_all_22` — network + 30s subprocess timeout — **FIXED** (branch `fix/test-network-hermeticity`)
- **Source:** `test_benchmark_modes.py:86-94` — `subprocess.run([... "-m", "openreview_cli", "benchmark", "run" ...], timeout=30)` → same `httpx.get(CUAD_URL, timeout=300)` chain. 30s wall-clock < 300s httpx timeout; chunk runs add bandwidth contention.
- **Fix applied:** converted subprocess → `CliRunner` invoke with monkeypatched loaders (pattern from `TestMultiMode` in same file). Verified: 6 passed in 8.8s hermetically.

### 5. `test_dense_offline_fallback_notice` — ambient-environment-dependent — **PARTIALLY MITIGATED**
- **Source:** `test_retrieval_offline.py:92-113` — NO gateway mock. Test passes only when `Gateway()` construction fails.
- **Dependency:** `src/openreview_cli/app.py:2069-2072` constructs real `Gateway()` → `router.py:118` `load_auth()` reads real `auth.json`. Dev machine has valid API keys → LiteLLM call succeeds → no "Dense retrieval unavailable" notice → assertion fails.
- **Fix:** add `@patch("openreview_cli.gateway.router.Gateway", side_effect=Exception("no auth"))` to force the fallback path deterministically.
- **2026-07-23 note:** passes under the new global `--disable-socket` (LiteLLM call blocked → fallback notice appears) but the test still has no explicit mock — deterministic fix above still owed (Phase 2).

## Priority 3 — Flakes

### 6. `test_retrieval_benchmark.py::TestRerankerBenchmark::test_reranker_returns_results` — chunk-ordering flake
- Fails inside a ~30-file chunk run; passes isolated on the same code.
- **Source:** `test_retrieval_benchmark.py:297-336`; fixtures are function-scoped `tmp_path` (no shared DB state found).
- **Hypothesis:** module-level `@patch("openreview_cli.gateway.router.Gateway")` affects all importers in the same process; interaction with neighboring tests.
- **Fix:** narrow patch scope or isolate the test's process.

### 6b. TUI suite (`tests/integration/tui/`) — non-deterministic flake storm under full-suite load
- Two consecutive full `-m slow` runs on identical code: run 1 = 16 failed/96 passed, run 2 = 18 failed/94 passed, with **different failure sets** (overlap partial; `test_settings_tab`, `test_result_screen`, `test_search_screen`, `test_review_wizard`, `test_gateway_wizard`, `test_client_form`, `test_clients_tab`, `test_progress_screen`, `test_recent_reviews` variously).
- Targeted rerun of `test_settings_tab.py` + `test_app.py` in isolation: 37/37 passed — including `test_sigterm_mid_review_cancels_cleanly` (see #7: flaky, sometimes passes).
- **Hypothesis:** Textual `run_test` startup is ~30s/test and timing-sensitive; under cumulative suite load (after ~2500 prior tests, spaCy/litellm resident) pilots race app startup. Failures are timing/assertion-visibility races, not logic.
- **Proven unrelated to the fence branch:** zero imports of `llm_json`, `review.prompts`, `review.extraction`, `bilateral.comparison`, or `benchmark.baseline` anywhere under `src/openreview_cli/tui/` or `tests/integration/tui/`.
- **Fix:** run TUI tests in a separate process group (CI already separates memory tests the same way); consider per-test watchdog/Retry; long-term, investigate Textual pilot startup races.

## Known and already documented (AGENTS.md)

### 7. `tests/integration/tui/test_app.py::test_sigterm_mid_review_cancels_cleanly`
- **Test:** `tests/integration/tui/test_app.py:589-657` — sends `SIGTERM` via `os.kill` (line 643), wraps `run_test` in `try/except SystemExit` (line 651).
- **Code:** `src/openreview_cli/tui/app.py:148-167` — `_on_signal` calls `sys.exit(128 + signum)` (line 167); `SystemExit` escapes Textual's `run_test` async context, cleanup may never run.
- **Fix:** replace `sys.exit` in the signal handler with cancel-and-return (set flag, cancel tasks, let the event loop wind down).

## Summary table

| # | Test | Class | One-line fix |
|---|------|-------|--------------|
| 1 | test_sparse_hybrid_correlation_less_than_one | TEST BUG (mock drift) | add `requirement=None` to `_mock_embed` |
| 2 | test_gateway_cli ×3 | REAL FAILURE (unknown) | trace which registry method the CLI calls vs mocks |
| 3 | test_mock_baseline_produces_correct_result_count | network-dependent | **FIXED** — canned loader monkeypatch |
| 4 | test_modes_validation_accepts_all_22 | network + 30s timeout | **FIXED** — CliRunner + canned loaders |
| 5 | test_dense_offline_fallback_notice | ambient auth-dependent | force-patch Gateway to fail |
| 6 | test_reranker_returns_results | ordering flake | narrow patch scope |
| 7 | test_sigterm_mid_review_cancels_cleanly | known TUI bug (AGENTS.md) | cancel-and-return in `_on_signal` |

## Discovered 2026-07-23 (network-hermeticity branch, full integration run)

### 8. Test-suite repo pollution — tests write artifacts into the working tree
- One full `tests/integration` run created **565 untracked YAML files in repo root** (`bulk-*`, `diff-*`, `export-*`, `del-*`, `hist-*`, `set-*`, …) and **modified tracked fixtures** `tests/fixtures/nda_corpus/pairs/*.json` + `manifest.json`.
- **Mechanism:** playbook/client CLI tests pass relative output paths (or default to cwd) instead of `tmp_path`.
- **Impact:** dirty tree after every verification run; risk of committing artifacts; fixture mutation can leak across tests (ordering-dependent behavior).
- **Fix:** sweep the offending tests to use `tmp_path`/isolated cwd (`CliRunner`'s `isolated_filesystem` or `monkeypatch.chdir`), and assert tree cleanliness in CI.

### 9. `test_pii_accuracy.py::TestPiiAccuracy::test_finds_pii_on_real_contracts` — ordering-dependent failure
- Failed inside the full integration run; passed isolated on identical code (104s). Not network-related (no socket use).
- **Hypothesis:** shared session-scoped PII engine state or fixture pollution (#8) interaction. Needs investigation alongside #6.

### 10. `test_benchmark_tier.py::test_benchmark_tier_all_runs` — borderline 30s subprocess timeout — **FIXED** (branch `fix/test-network-hermeticity`)
- `--benchmark-tier all` runs 3 tiers sequentially in one subprocess; 29.78s observed on main vs 30s limit. Raised to 90s with comment.
