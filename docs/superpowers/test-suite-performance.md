# Test Suite Performance & Timeout Engineering Debt

Collected 2026-07-23 during branch `fix/markdown-fence-json-parsing`.
Companion to `pre-existing-test-failures.md` (correctness debt). This file is
**performance/ergonomics debt**: the suite is too slow and too fragile to run
whole, which kills automation (a subagent implementing a 1-line refactor died
because its verification command never returned inside its time budget).

## Measured reality (this session, 2-core dev sandbox)

| Suite | Tests | Duration | Notes |
|---|---|---|---|
| `tests/unit/` | 1956 | ~295-311 s | includes PII tests w/ session-cached spaCy engine (~66 s of it) |
| `tests/integration/ -m "not slow and not memory"` | ~584 | **>600 s — timed out twice** | had to be split into 4 chunks: 492 s + 128 s + 314 s + 10 s |
| `-m memory` (solo) | 22 | 89 s | must run alone (AGENTS.md: spaCy GC hang under cumulative load) |
| `-m slow` (TUI) | 112 | **~1500 s (25 min) per run** | ~30 s Textual `run_test` startup per test; flaky under load |
| live (`requires_openrouter`) | 4 | 14 s | skips without `OPENROUTER_API_KEY` |

**Full local pass = ~40+ min with manual chunking.** A naive
`pytest tests/` never completes inside a 10-min command budget.

## Root causes (evidence from this session)

1. **Marker taxonomy is advisory, not enforced.**
   `-m "not slow"` does NOT exclude `memory`-marked tests — memory tests then
   hang under cumulative load (documented in AGENTS.md). Correct local
   invocation is `-m "not slow and not memory"`, which nobody can guess.
   There is no `network` or `live` marker at all.

2. **Real network inside integration tests.**
   - Dataset loaders hit HuggingFace with `httpx.get(url, timeout=300)`
     (`benchmark/cuad.py:109`, `maud.py:130`, `contract_nli.py:42`) via
     `BenchmarkRunner(cache_dir=None)`. One test can burn 300 s.
   - Ollama discovery hits `http://localhost:11434/api/tags`
     (`gateway/registry.py:207-209`) — in a network-blackholed sandbox the
     socket connect hangs past httpx's own timeout; only `pytest-timeout`
     (180 s) kept chunks bounded.
   - `test_benchmark_modes.py:86-94` wraps this in a **30 s subprocess
     timeout** — guaranteed to lose against a 300 s httpx timeout.

3. **TUI suite cost structure.**
   104+ tests × ~30 s `run_test` startup. Under full-suite load the startup
   races produce a non-deterministic flake storm (two identical runs:
   16 vs 18 failures, different sets — see pre-existing-test-failures.md #6b).

4. **Cumulative memory pressure.**
   `en_core_web_lg` (~600 MB) + Presidio stay resident across the session;
   after ~1900 tests the memory-marked tests hang or breach the 110 MB peak
   budget. This is why memory tests can only run solo.

5. **No chunking/sharding tooling.**
   Splitting was done by hand with shell globs (`test_[a-c]*.py`).
   Not reproducible, not load-balanced.

6. **Timeout policy is per-command, not per-suite.**
   `pytest-timeout` exists but has no global default in config; each
   invocation must remember `--timeout=180`.

## Engineering backlog (so this never happens again)

Ordered by leverage. Each item is independently shippable.

1. **Enforce marker taxonomy in conftest.**
   Auto-mark by directory already exists for TUI (`tests/integration/tui/conftest.py`).
   Extend: every test must carry exactly one of `fast | slow | memory | live`;
   add `network` marker for anything that can open a socket. Add a conftest
   hook that FAILS collection of unmarked tests. Document the canonical local
   commands in AGENTS.md: fast feedback = `-m "fast"`, full = `-m "not live"`.

2. **Kill real network in tests.**
   - Add `pytest-socket` (or a small conftest fixture) disabling sockets by
     default; tests that need network must opt in via the `network` marker.
   - Pre-cache dataset fixtures (CUAD/MAUD/ContractNLI JSONs are small) and
     point `BenchmarkRunner(cache_dir=...)` at them in test fixtures.
   - Mock Ollama discovery at the `httpx` boundary everywhere it appears.

3. **Isolate the TUI suite in CI.**
   Give `-m slow` its own CI job (memory tests already got this treatment).
   Add `pytest-rerunfailures` with 1 retry for TUI only — the flake storm is
   timing, not logic. Long-term: investigate Textual pilot startup races and
   reduce per-test startup (shared app fixture where possible).

4. **Global per-test timeout in `pyproject.toml`.**
   `timeout = 60` default, `timeout = 300` on `memory`/`live` markers via
   `pytest.ini` marker-specific override (or per-test decorator). No command
   may rely on the operator remembering the flag.

5. **Deterministic sharding for local + CI.**
   Adopt `pytest-shard` or `pytest-xdist -n auto --dist loadfile` AFTER item 2
   lands (shared-state hazards exist: module-level
   `@patch("...gateway.router.Gateway")` leaks across same-process tests —
   see pre-existing-test-failures.md #6). Publish a `just test` /
   `make test` recipe that runs the 4 canonical suites in sequence:
   unit → integration (fast) → memory (solo) → tui (isolated).

6. **spaCy lifecycle hygiene.**
   Session-scoped engine cache already exists (`tests/conftest.py`). Add an
   explicit teardown that drops the model + `gc.collect()` between the unit
   and memory phases, so memory tests no longer need social-distancing rules.

7. **Suite duration budget + trend.**
   Assert wall-clock budgets in CI (unit < 8 min, integration-fast < 10 min,
   memory < 5 min, tui < 35 min) and fail on regression >20 %. Cheap: one
   `time` wrapper per job + a stored baseline.

## Why this matters (motivation)

A 1-import + 1-line refactor (Task 5 of the fence fix) could not be verified
by an autonomous agent inside its runtime budget — the verification step, not
the code, was the failure mode. If suites can't be run by agents and CI
without ceremony, verification gets skipped, and skipped verification is how
bugs like the markdown-fence one ship silently in the first place.
