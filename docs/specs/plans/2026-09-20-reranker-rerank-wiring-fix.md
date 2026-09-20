# Reranker Rerank Wiring Fix Implementation Plan

> **For agentic workers:** Use tasks as checkboxes (`- [ ]`) for tracking.
>
> **Process note:** This plan was produced with the **writing-plans** skill
> (`~/.agents/skills/writing-plans/SKILL.md`) and its tasks are ordered by the
> **test-driven-development** skill (`~/.agents/skills/test-driven-development/SKILL.md`):
> every task writes a failing test first, watches it fail, implements the minimum, watches it
> pass, then commits.

**Goal:** Make `openreview retrieve --rerank` actually reorder retrieval results (it is currently a
silent no-op), so that a later "does the reranker help legal retrieval?" measurement is possible.

**Architecture:** Four small, independently testable fixes on one path, each behind its own
red-green cycle: (1) the gateway exposes the configured `reranking` slot model id;
(2) `Reranker.rerank` consumes the gateway's real response shape (`relevance_score`) and reorders;
(3) `RetrievalEngine` materializes a candidate pool of `rerank_depth` results (instead of `top_k`)
when reranking so a chunk ranked below `top_k` can be promoted; (4) the `retrieve` command resolves
"rerank enabled" from `retrieval.rerank_enabled`, passes the engine's full pool to the reranker,
records the slot's real model id, and never emits more than `--top-k` rows. All retrieval-path
behaviour when rerank is off is byte-identical to today.

**Tech Stack:** Python 3.12, Typer CLI, SQLite FTS5 (BM25) + cosine dense + RRF fusion, litellm via
the AI Gateway (`Gateway.rerank`), pytest + `unittest.mock`, `uv` for everything.

## Global Constraints

- Python 3.12 pinned; use `uv` only (`uv run ...`).
- `uv run ruff check . && uv run ruff format .` and `uv run mypy src/ tests/` (strict) must pass.
- No explanatory comments in code unless the logic is non-obvious (repo style).
- Conventional Commits.
- Do not edit `[tool.ruff]` / `[tool.mypy]` / pytest config.
- Tests must run offline: sockets are disabled by default
  (`pyproject.toml:154` → `addopts = "-v --tb=short --disable-socket --allow-unix-socket"`), so no
  test may construct a real `Gateway` that dispatches, and CLI tests must use `--method sparse`
  plus a patched `openreview_cli.gateway.router.Gateway` (or a `MagicMock`).
- Test markers: `tests/conftest.py:33-44` auto-assigns the `fast` marker to any test under
  `tests/unit/` or `tests/integration/`, so new tests need **no** marker decorator.
- Keep changes minimal and focused; do not refactor unrelated code.
- Never `git add -A`: the working tree already carries an unrelated, uncommitted docs reorg —
  `git status --short` reports `D ALPHA_RELEASE_NOTES.md`, `D ARCHITECTURE.md`, `D BENCHMARKS.md`,
  `D CLA.md`, `M README.md`, the two deleted `docs/specs/plans/2026-09-17-*.md` files, and the
  untracked `docs/ALPHA_RELEASE_NOTES.md`, `docs/ARCHITECTURE.md`, `docs/BENCHMARKS.md`,
  `docs/CLA.md`. Stage only the exact paths each commit lists.

---

## Verified defect evidence (read this once; each claim was re-checked against the working tree)

| # | Claim | Evidence |
|---|-------|----------|
| 1 | `Reranker.rerank` reads the wrong score key, so every score is `0.0` and the stable `sorted()` never reorders | writes `score_map[idx] = item.get("score", 0.0)` at `src/openreview_cli/retrieval/rerank.py:93`; the gateway returns `{"index": r["index"], "relevance_score": r["relevance_score"]}` at `src/openreview_cli/gateway/router.py:777-779`; sort at `rerank.py:101` |
| 2 | Candidate pool is inert | `src/openreview_cli/retrieval/engine.py:261` truncates fused results to `query.top_k`; `src/openreview_cli/app.py:2230` then slices `results[:rerank_depth]`, which can never add a candidate — the reranker only ever sees the top `top_k` |
| 3 | `retrieval.rerank_enabled` is dead config | declared at `src/openreview_cli/config/loader.py:66` and `loader.py:215`; `grep -rn rerank_enabled src/` returns only those two lines; the default is enforced solely by the flag default at `src/openreview_cli/app.py:2120-2122` |
| 4 | Reranker model bookkeeping is wrong | default `model_id: str = "qwen3-reranker-0.6b"` at `rerank.py:34`; `app.py:2229` constructs `Reranker(gateway)` with no `model_id`; that id is then used for the validation lookup at `app.py:2235-2238` even when the `reranking` slot is e.g. `voyage/rerank-2.5` (`config/loader.py:29-31` shows the slot default is `ollama/qwen3-reranker-0.6b`) |
| 5 | Tests mock the wrong key, hiding #1 | `tests/unit/test_retrieval_rerank.py:41-43, 94-95, 157-159, 234-235, 409-410, 463-464`; `tests/integration/test_retrieval_reranker.py:179-181, 228-230`; `tests/integration/test_retrieval_benchmark.py:314-318` (the integration mocks are doubly wrong: `chunk_id`/`score` instead of `index`/`relevance_score`) |

Root cause of the "silent" part: `sorted()` is stable (`rerank.py:101`) and the mapping default is
`0.0`, so a payload the code cannot parse produces exactly the input order with no error, no log,
and a green test suite.

**RED evidence (verified in a throwaway harness against the current code, not committed):** the
behavioural tests below were run before any fix and failed exactly as quoted —
`test_rerank_reorders_from_gateway_relevance_score` →
`assert ['c1', 'c2', 'c3'] == ['c3', 'c1', 'c2']`;
`test_rerank_raises_when_payload_lacks_relevance_score` → `Failed: DID NOT RAISE <class 'KeyError'>`;
`test_sparse_pool_reaches_rerank_depth` → `assert {'c3'} == {'c1', 'c3', 'c4', 'c5'}`;
`test_dense_pool_reaches_rerank_depth` and `test_hybrid_pool_reaches_rerank_depth` → `assert 1 == 5`;
`TestSlotPrimaryModel` → `AttributeError: 'Gateway' object has no attribute 'slot_primary_model'`;
the wiring helpers → `ImportError: cannot import name '_rerank_enabled_from_config'` and
`... '_reranker_model_id'`;
`test_rerank_reorders_emitted_results` →
`assert ['chunk-003', 'chunk-004', 'chunk-006'] == ['chunk-006', 'chunk-004', 'chunk-003']`;
`test_rerank_promotes_candidate_below_top_k` →
`assert ['chunk-003', 'chunk-004'] == ['chunk-008', 'chunk-004']` pre-Task-2 and
`assert ['chunk-004', 'chunk-003'] == ['chunk-008', 'chunk-004']` from Task 2's state onward;
`test_config_enables_rerank_without_the_flag` → `assert None == 0.99`.
`test_pool_keeps_the_plain_result_order`, `test_rerank_off_ignores_rerank_depth` and
`test_rerank_disabled_by_default` pass before and after; they are characterization guards.

**Fixture facts relied on by the CLI tests** (measured offline against
`tests/fixtures/retrieval/sample_contract.ndax`, 12 chunks, ingested sparse):
query `"confidential information"` at pool depth ≥ 6 returns, in order,
`chunk-003, chunk-004, chunk-006, chunk-009, chunk-005, chunk-008` — so candidate index `5` is
`chunk-008`, i.e. rank 6, outside a `--top-k 2` window.

---

## File structure

**Create**
- `tests/unit/test_retrieve_rerank_wiring.py` — unit tests for the two new `app.py` helpers
  (`_rerank_enabled_from_config`, `_reranker_model_id`).
- `docs/specs/plans/2026-09-20-reranker-rerank-wiring-fix.md` — this plan.

**Modify**
- `src/openreview_cli/gateway/router.py` — add `Gateway.slot_primary_model(slot) -> str | None`
  (single responsibility: read a slot's configured primary id without raising).
- `src/openreview_cli/retrieval/rerank.py` — consume the gateway's real payload keys; name the
  bundled default model id once (`DEFAULT_RERANK_MODEL`).
- `src/openreview_cli/retrieval/engine.py` — one private helper `_result_limit(query)` plus three
  call sites, so a rerank query materializes `rerank_depth` candidates and a non-rerank query is
  unchanged.
- `src/openreview_cli/app.py` — the two helpers above, and the `retrieve` command wiring
  (config default, model id, pass the whole pool, cap to `top_k` on failure).
- `tests/unit/test_gateway_router.py` — `TestSlotPrimaryModel`.
- `tests/unit/test_retrieval_rerank.py` — reorder guard + loud-failure guard; correct 7 mock
  payloads.
- `tests/unit/test_retrieval_engine.py` — pool-depth tests + a pool fixture.
- `tests/integration/test_retrieval_reranker.py` — CLI reorder test, promotion test,
  config-enabled test, malformed-payload fallback test; correct 2 mock payloads.
- `tests/integration/test_retrieval_benchmark.py` — correct 1 mock payload.

**Explicitly NOT touched:** `src/openreview_cli/config/loader.py` (the keys already exist),
`src/openreview_cli/retrieval/models.py`, `RetrievalQuery` validation, `Reranker.validate`,
formatters, TUI, and every file outside the list above. No doc edits (see Open Questions #6).

---

### Task 0: Create the working branch

**Files:** none (git only).

**Interfaces:**
- Consumes: `main` at `43f4a80`.
- Produces: branch `fix/reranker-rerank-wiring`, checked out, with the pre-existing unrelated
  working-tree changes still uncommitted.

- [ ] **Step 1: Create and switch to the branch**

```bash
cd /home/mohamed/lab/openreview
git switch main
git switch --create fix/reranker-rerank-wiring
```

- [ ] **Step 2: Confirm the branch and the untouched dirty tree**

```bash
git branch --show-current
git status --short
```

Expected:

```
fix/reranker-rerank-wiring
 D ALPHA_RELEASE_NOTES.md
 D ARCHITECTURE.md
 ...
?? docs/ARCHITECTURE.md
```

The `D`/`??` entries are the pre-existing docs reorg. Leave them alone for the whole plan; they are
never staged by the commits below. Do not start any task on `main`.

---

### Task 1: `Gateway.slot_primary_model` (prerequisite for bug #4)

**Files:**
- Modify: `src/openreview_cli/gateway/router.py:225-227` (insert between `_resolve_provider_info`
  and `_enforce_tier`)
- Test: `tests/unit/test_gateway_router.py:352-354` (insert between `TestRerank` and
  `TestGetLitellmKwargs`)

**Interfaces:**
- Consumes: `self._config["gateway"]["models"]`, already loaded by `Gateway.__init__`
  (`router.py:161-161`).
- Produces: `Gateway.slot_primary_model(self, slot: str) -> str | None` — returns the configured
  primary model id, or `None` for an unknown/unconfigured slot. Never raises (contrast
  `_get_slot_config`, `router.py:211-219`, which raises `SlotNotConfiguredError`). Task 4's
  `_reranker_model_id` calls it.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_gateway_router.py`, immediately after the `TestRerank` class (after line
352) and before `class TestGetLitellmKwargs:`:

```python
class TestSlotPrimaryModel:
    def test_returns_configured_primary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        assert gw.slot_primary_model("reranking") == "cohere/rerank-english-v3.0"

    def test_returns_none_for_unconfigured_slot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        assert gw.slot_primary_model("grounding") is None
```

`COMMON_CONFIG` (`tests/unit/test_gateway_router.py:85-108`) declares
`reranking: primary: cohere/rerank-english-v3.0` and no `grounding` slot. `_gateway` (line 59)
builds a fully offline `Gateway` from a temp config.

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/unit/test_gateway_router.py::TestSlotPrimaryModel -v
```

Expected: 2 failed, both with
`AttributeError: 'Gateway' object has no attribute 'slot_primary_model'`.

- [ ] **Step 3: Write the minimal implementation**

Insert into `src/openreview_cli/gateway/router.py` between the end of `_resolve_provider_info`
(line 225) and `def _enforce_tier(` (line 227):

```python
    def slot_primary_model(self, slot: str) -> str | None:
        """Return the configured primary model id for a slot, or None.

        Unlike ``_get_slot_config``, an unknown or unconfigured slot returns None
        instead of raising: callers use this for validation bookkeeping, where a
        missing slot must fall back to a default.
        """
        models = self._config.get("gateway", {}).get("models", {})
        cfg = models.get(slot)
        if not isinstance(cfg, dict):
            return None
        primary = cfg.get("primary")
        return primary if isinstance(primary, str) and primary else None
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/unit/test_gateway_router.py::TestSlotPrimaryModel -v
```

Expected: `2 passed`.

- [ ] **Step 5: Run the whole gateway-router file to prove nothing regressed**

```bash
uv run pytest tests/unit/test_gateway_router.py -v
```

Expected: all passed (this is the file that pins `Gateway.rerank`'s
`{"index", "relevance_score"}` contract, `test_returns_ranked_results` at line 258).

- [ ] **Step 6: Lint, format, type-check**

```bash
uv run ruff check . && uv run ruff format .
uv run mypy src/ tests/
```

Expected: `All checks passed!`, formatter reports no re-wrapping (or only the files you touched),
`Success: no issues found`.

- [ ] **Step 7: Commit**

```bash
git add src/openreview_cli/gateway/router.py tests/unit/test_gateway_router.py
git commit -m "feat(gateway): expose configured slot primary model id"
```

---

### Task 2: `Reranker` consumes `relevance_score` and actually reorders (bug #1)

**Files:**
- Modify: `src/openreview_cli/retrieval/rerank.py:17` (constant), `rerank.py:31-44` (default),
  `rerank.py:88-93` (score map)
- Test: `tests/unit/test_retrieval_rerank.py:13-35` (helper), `tests/unit/test_retrieval_rerank.py:177-180`
  (new tests at the end of `TestRerankerRerank`), plus 6 mock payload blocks corrected in that file
- Test: `tests/integration/test_retrieval_reranker.py:164-216` (new CLI test inside
  `TestRetrieveRerankFlag`)

**Interfaces:**
- Consumes: `Gateway.rerank(slot, query, documents, top_n=..., requirement=...) ->
  list[dict[str, Any]]` whose dicts are exactly `{"index": int, "relevance_score": float}`
  (`src/openreview_cli/gateway/router.py:777-779`).
- Produces: `DEFAULT_RERANK_MODEL: str = "qwen3-reranker-0.6b"` (module constant, consumed by
  `Reranker.__init__` and by Task 4's `_reranker_model_id`), and `Reranker.rerank(query, candidates,
  top_k) -> list[RetrievalResult]` which now returns results genuinely ordered by the gateway's
  `relevance_score` (descending) and truncated to `top_k`. Missing `index`/`relevance_score` keys
  raise `KeyError` instead of silently zeroing every score.

- [ ] **Step 1: Write the failing tests (unit reorder guards + CLI reorder guard)**

In `tests/unit/test_retrieval_rerank.py`, add this helper right after the import block (after line
12, before `class TestRerankerInit:`):

```python
def _candidate(chunk_id: str, score: float) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        text=f"text {chunk_id}",
        clause_heading=f"Article {chunk_id}",
        clause_level=0,
        hierarchy_chain=[f"Article {chunk_id}"],
        parent_chunk_id=None,
        score=score,
        method="hybrid",
    )
```

Then append these two tests at the end of `TestRerankerRerank` (after
`test_rerank_top_k_respected`, i.e. after line 178, before `class TestRerankerValidate:`):

```python
    def test_rerank_reorders_from_gateway_relevance_score(self) -> None:
        """Regression guard for B1: gateway scores must change the order, not just annotate it."""
        mock_gateway = MagicMock()
        mock_gateway.rerank.return_value = [
            {"index": 2, "relevance_score": 0.9},
            {"index": 0, "relevance_score": 0.5},
            {"index": 1, "relevance_score": 0.1},
        ]
        reranker = Reranker(mock_gateway, model_id="test-cross-encoder")
        candidates = [_candidate("c1", 0.9), _candidate("c2", 0.6), _candidate("c3", 0.1)]

        results = reranker.rerank("test query", candidates, top_k=3)

        assert [r.chunk_id for r in results] == ["c3", "c1", "c2"]
        assert [r.rerank_score for r in results] == [0.9, 0.5, 0.1]

    def test_rerank_raises_when_payload_lacks_relevance_score(self) -> None:
        """A payload the code cannot parse must fail loudly, not silently keep the input order."""
        mock_gateway = MagicMock()
        mock_gateway.rerank.return_value = [{"index": 0, "score": 0.9}]
        reranker = Reranker(mock_gateway, model_id="test-cross-encoder")

        with pytest.raises(KeyError):
            reranker.rerank("test query", [_candidate("c1", 0.5)], top_k=1)
```

Then append this CLI test to `class TestRetrieveRerankFlag` in
`tests/integration/test_retrieval_reranker.py` (after `test_retrieve_without_rerank_has_null_rerank_score`,
line 163):

```python
    @patch("openreview_cli.gateway.router.Gateway")
    def test_rerank_reorders_emitted_results(
        self,
        mock_gateway_class: MagicMock,
        runner: CliRunner,
        indexed_db: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """B1 end-to-end guard: the emitted order must change, not just the rerank_score field."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_config"))
        mock_gw = MagicMock()
        mock_gw.rerank.return_value = [
            {"index": 2, "relevance_score": 0.99},
            {"index": 1, "relevance_score": 0.50},
        ]
        mock_gateway_class.return_value = mock_gw

        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidential information",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--top-k",
                "3",
                "--rerank",
                "--format",
                "json",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        data = _extract_json_from_output(result.output)
        assert [r["chunk_id"] for r in data["results"]] == [
            "chunk-006",
            "chunk-004",
            "chunk-003",
        ]
        assert data["results"][0]["rerank_score"] == 0.99
```

`--method sparse` keeps this test offline (no embedding call); `Gateway` is patched, so `Gateway()`
builds a `MagicMock` and `mock_gw.rerank` never reaches litellm.

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
uv run pytest "tests/unit/test_retrieval_rerank.py::TestRerankerRerank::test_rerank_reorders_from_gateway_relevance_score" "tests/unit/test_retrieval_rerank.py::TestRerankerRerank::test_rerank_raises_when_payload_lacks_relevance_score" "tests/integration/test_retrieval_reranker.py::TestRetrieveRerankFlag::test_rerank_reorders_emitted_results" -v
```

Expected: 3 failed —
`AssertionError: assert ['c1', 'c2', 'c3'] == ['c3', 'c1', 'c2']`,
`Failed: DID NOT RAISE <class 'KeyError'>`, and
`AssertionError: assert ['chunk-003', 'chunk-004', 'chunk-006'] == ['chunk-006', 'chunk-004', 'chunk-003']`
(the CLI run does reach `Reranker.rerank`, but every score is dropped, so the stable sort keeps the
plain order).

- [ ] **Step 3: Write the minimal implementation**

In `src/openreview_cli/retrieval/rerank.py`, three edits.

(a) After `RERANK_SLOT = "reranking"` (line 17):

```python
DEFAULT_RERANK_MODEL = "qwen3-reranker-0.6b"
```

(b) Replace the constructor default (formerly line 34):

```python
    def __init__(
        self,
        gateway: Any | None,
        model_id: str = DEFAULT_RERANK_MODEL,
    ) -> None:
```

(c) Replace the score-map loop (formerly lines 88-93):

```python
        # Build a mapping from original index to reranker score
        score_map: dict[int, float] = {}
        for item in scores:
            if isinstance(item, dict):
                score_map[int(item["index"])] = float(item["relevance_score"])
```

Nothing else in `rerank()` changes: the `r.rerank_score = score_map.get(i, 0.0)` assignment
(line 97), `r.method = "hybrid+rerank"` (line 98) and the stable descending sort (line 101) stay as
they are.

- [ ] **Step 4: Run the new tests to verify they pass**

```bash
uv run pytest "tests/unit/test_retrieval_rerank.py::TestRerankerRerank" -v
```

Expected: all `TestRerankerRerank` tests pass, including the two new ones.

- [ ] **Step 5: Correct the mock payloads that were hiding the bug (#5)**

These mocks feed the *old* key, so they can never exercise the mapping. Change all of them to the
gateway's real shape. The line numbers below refer to the files **before** Step 1's insertions —
match on the exact text shown, not on the numbers.

In `tests/unit/test_retrieval_rerank.py`, replace **all** occurrences of the block

```python
            {"score": 0.9, "index": 0},
            {"score": 0.7, "index": 1},
            {"score": 0.5, "index": 2},
```

(lines 41-43) with

```python
            {"index": 0, "relevance_score": 0.9},
            {"index": 1, "relevance_score": 0.7},
            {"index": 2, "relevance_score": 0.5},
```

replace **all** occurrences of

```python
            {"score": 0.9, "index": 0},
            {"score": 0.7, "index": 1},
```

(lines 94-95) with

```python
            {"index": 0, "relevance_score": 0.9},
            {"index": 1, "relevance_score": 0.7},
```

replace **all** occurrences of

```python
            {"score": 0.9, "index": 0},
            {"score": 0.8, "index": 1},
            {"score": 0.7, "index": 2},
```

(lines 157-159) with

```python
            {"index": 0, "relevance_score": 0.9},
            {"index": 1, "relevance_score": 0.8},
            {"index": 2, "relevance_score": 0.7},
```

replace **all** occurrences of

```python
            {"score": 0.9, "index": 0},
            {"score": 0.8, "index": 1},
```

(lines 234-235) with

```python
            {"index": 0, "relevance_score": 0.9},
            {"index": 1, "relevance_score": 0.8},
```

and replace **all** occurrences (lines 409-410 and 463-464 — the two blocks are byte-identical) of

```python
            {"score": 0.1, "index": 0},
            {"score": 0.05, "index": 1},
```

with

```python
            {"index": 0, "relevance_score": 0.1},
            {"index": 1, "relevance_score": 0.05},
```

In `tests/integration/test_retrieval_reranker.py`, replace **all** occurrences (lines 179-181 and
228-230 — byte-identical) of

```python
            {"chunk_id": "c1", "score": 0.95, "text": "test"},
            {"chunk_id": "c2", "score": 0.90, "text": "test"},
            {"chunk_id": "c3", "score": 0.85, "text": "test"},
```

with

```python
            {"index": 0, "relevance_score": 0.95},
            {"index": 1, "relevance_score": 0.90},
            {"index": 2, "relevance_score": 0.85},
```

In `tests/integration/test_retrieval_benchmark.py`, replace the block at lines 313-319

```python
        mock_gw.rerank.return_value = [
            {"chunk_id": "chunk-004", "score": 0.95, "text": "test"},
            {"chunk_id": "chunk-003", "score": 0.90, "text": "test"},
            {"chunk_id": "chunk-008", "score": 0.85, "text": "test"},
            {"chunk_id": "chunk-005", "score": 0.80, "text": "test"},
            {"chunk_id": "chunk-012", "score": 0.75, "text": "test"},
        ]
```

with

```python
        mock_gw.rerank.return_value = [
            {"index": 1, "relevance_score": 0.95},
            {"index": 0, "relevance_score": 0.90},
            {"index": 2, "relevance_score": 0.85},
        ]
```

- [ ] **Step 6: Run the three touched test files**

```bash
uv run pytest tests/unit/test_retrieval_rerank.py tests/integration/test_retrieval_reranker.py tests/integration/test_retrieval_benchmark.py -v
```

Expected: all pass. `test_validate_returns_degraded_flag_after_three` (line 375) and
`test_validate_logs_degraded_without_claiming_disable` (line 429) still pass because the corrected
payloads leave the candidate order unchanged (score 0.1 > 0.05 on indices 0,1), so
`degradation_pp <= 0` and the consecutive-degradation counter still reaches 3
(`retrieval/storage.py:259-262`).

- [ ] **Step 7: Lint, format, type-check**

```bash
uv run ruff check . && uv run ruff format .
uv run mypy src/ tests/
```

Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add src/openreview_cli/retrieval/rerank.py tests/unit/test_retrieval_rerank.py tests/integration/test_retrieval_reranker.py tests/integration/test_retrieval_benchmark.py
git commit -m "fix(retrieval): reorder rerank results from gateway relevance_score"
```

---

### Task 3: Candidate pool reaches `rerank_depth` (bug #2)

**Files:**
- Modify: `src/openreview_cli/retrieval/engine.py:29` (helper), `engine.py:145,173`
  (`_retrieve_sparse`), `engine.py:196-201` (`_retrieve_dense`), `engine.py:236-261`
  (`_retrieve_hybrid`)
- Test: `tests/unit/test_retrieval_engine.py:101-102` (new fixture), and a new test class appended
  after line 339
- Test: `tests/integration/test_retrieval_reranker.py` (new CLI test)

**Interfaces:**
- Consumes: `RetrievalQuery.rerank` / `RetrievalQuery.rerank_depth` (`retrieval/models.py:27-28`;
  `rerank_depth >= top_k` is already enforced at `models.py:40-41`).
- Produces: `RetrievalEngine.retrieve(query) -> list[RetrievalResult]` returns up to
  `query.rerank_depth` results *in fused order* when `query.rerank` is True, and exactly the old
  `top_k`-truncated list when it is False. `_result_limit(query) -> int` is the single source of
  that decision. Callers that rerank apply `top_k` themselves (`Reranker.rerank` truncates at
  `rerank.py:102`; `app.py` caps on failure in Task 4). `RetrieveStage`
  (`pipeline/adapters/retrieve.py:71`) builds a non-rerank query, so it is unaffected.

- [ ] **Step 1: Write the failing pool tests**

In `tests/unit/test_retrieval_engine.py`, add this fixture after the `populated_db` fixture (after
line 100):

```python
@pytest.fixture
def pooled_db(tmp_path: Path) -> str:
    """Index with four chunks matching one term plus one chunk that does not."""
    db_path = str(tmp_path / "pool.db")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE index_meta (
            document_id TEXT PRIMARY KEY, document_path TEXT NOT NULL DEFAULT '',
            index_version INTEGER NOT NULL DEFAULT 1, index_status TEXT NOT NULL DEFAULT 'indexed',
            index_timestamp TEXT, chunk_count INTEGER NOT NULL DEFAULT 0,
            method TEXT NOT NULL DEFAULT 'hybrid', embedding_model TEXT, embedding_dim INTEGER,
            db_size_bytes INTEGER DEFAULT 0
        );
        INSERT INTO index_meta (document_id, index_status, chunk_count, method, embedding_dim)
        VALUES ('test-doc', 'indexed', 5, 'hybrid', 4);
        CREATE TABLE chunks (
            chunk_id TEXT PRIMARY KEY, document_id TEXT NOT NULL DEFAULT 'test-doc',
            text TEXT NOT NULL, clause_heading TEXT NOT NULL, clause_level INTEGER NOT NULL DEFAULT 0,
            parent_chunk_id TEXT, heading_chain TEXT NOT NULL DEFAULT '[]',
            char_start INTEGER NOT NULL DEFAULT 0, char_end INTEGER NOT NULL DEFAULT 0
        );
        INSERT INTO chunks VALUES
            ('c1','test-doc','confidential information shall be protected','Article 3',0,NULL,'["Article 3"]',0,100),
            ('c2','test-doc','governing law is delaware','Section 7.2',1,'c1','["Article 7","Section 7.2"]',200,300);
        CREATE VIRTUAL TABLE chunk_fts USING fts5(
            chunk_id UNINDEXED, text, clause_heading, content='chunks', content_rowid='rowid',
            tokenize='unicode61', prefix='2 3'
        );
        INSERT INTO chunk_fts (rowid, chunk_id, text, clause_heading)
        SELECT rowid, chunk_id, text, clause_heading FROM chunks;
        CREATE TABLE chunk_embeddings (
            chunk_id TEXT PRIMARY KEY, embedding BLOB NOT NULL, model_id TEXT NOT NULL,
            dimension INTEGER NOT NULL, chunk_norm REAL NOT NULL
        );
    """)
    extra = {"c3": [0.8, 0.1, 0.3, 0.5], "c4": [0.2, 0.4, 0.7, 0.2], "c5": [0.3, 0.2, 0.9, 0.1]}
    for chunk_id, vector in extra.items():
        heading = f"Article {chunk_id}"
        conn.execute(
            "INSERT INTO chunks VALUES (?, 'test-doc', ?, ?, 0, NULL, ?, 1000, 1100)",
            (chunk_id, f"confidential obligation {chunk_id}", heading, f'["{heading}"]'),
        )
        conn.execute(
            "INSERT INTO chunk_fts (rowid, chunk_id, text, clause_heading) "
            "SELECT rowid, chunk_id, text, clause_heading FROM chunks WHERE chunk_id = ?",
            (chunk_id,),
        )
    vectors = {
        "c1": [0.5, 0.3, 0.1, 0.8],
        "c2": [0.1, 0.9, 0.2, 0.1],
        **extra,
    }
    for chunk_id, vector in vectors.items():
        conn.execute(
            "INSERT INTO chunk_embeddings VALUES (?, ?, 'test-model', 4, ?)",
            (chunk_id, struct.pack("<4f", *vector), (sum(v * v for v in vector)) ** 0.5),
        )
    conn.commit()
    conn.close()
    return db_path
```

`struct` is already imported at line 82 inside `populated_db`; move that import to the top of the
file (after `import sqlite3`) and delete the local one so the new fixture can use it:

```python
import sqlite3
import struct
```

Then append this class at the end of the file (after `test_hierarchy_chain_hybrid`, line 339):

```python
class TestRerankCandidatePool:
    """B2: a rerank query must materialize rerank_depth candidates, a plain one must not."""

    def test_sparse_pool_reaches_rerank_depth(self, pooled_db: str) -> None:
        engine = RetrievalEngine(pooled_db)
        query = RetrievalQuery(
            query_text="confidential", method="sparse", top_k=1, rerank=True, rerank_depth=4
        )

        results = engine.retrieve(query)

        assert {r.chunk_id for r in results} == {"c1", "c3", "c4", "c5"}

    def test_dense_pool_reaches_rerank_depth(self, pooled_db: str) -> None:
        mock_gateway = MagicMock()
        mock_gateway.embed.return_value = [[0.3, 0.5, 0.2, 0.7]]
        engine = RetrievalEngine(pooled_db, gateway=mock_gateway)
        query = RetrievalQuery(
            query_text="confidential", method="dense", top_k=1, rerank=True, rerank_depth=5
        )

        results = engine.retrieve(query)

        assert len(results) == 5

    def test_hybrid_pool_reaches_rerank_depth(self, pooled_db: str) -> None:
        mock_gateway = MagicMock()
        mock_gateway.embed.return_value = [[0.3, 0.5, 0.2, 0.7]]
        engine = RetrievalEngine(pooled_db, gateway=mock_gateway)
        query = RetrievalQuery(
            query_text="confidential", method="hybrid", top_k=1, rerank=True, rerank_depth=5
        )

        results = engine.retrieve(query)

        assert len(results) == 5

    def test_rerank_off_ignores_rerank_depth(self, pooled_db: str) -> None:
        engine = RetrievalEngine(pooled_db)
        query = RetrievalQuery(query_text="confidential", method="sparse", top_k=2, rerank_depth=4)

        results = engine.retrieve(query)

        assert len(results) == 2

    def test_pool_keeps_the_plain_result_order(self, pooled_db: str) -> None:
        engine = RetrievalEngine(pooled_db)
        plain = engine.retrieve(
            RetrievalQuery(query_text="confidential", method="sparse", top_k=2)
        )
        pooled = engine.retrieve(
            RetrievalQuery(
                query_text="confidential", method="sparse", top_k=2, rerank=True, rerank_depth=4
            )
        )

        assert [r.chunk_id for r in pooled[:2]] == [r.chunk_id for r in plain]
```

`test_rerank_off_ignores_rerank_depth` and `test_pool_keeps_the_plain_result_order` are deliberate
characterization tests: they pass before and after this task and exist to prove the requirement
"do not change the default retrieval results when rerank is off". Run them first and expect PASS;
do not "fix" them.

- [ ] **Step 2: Write the failing CLI promotion test**

Append to `class TestRetrieveRerankFlag` in `tests/integration/test_retrieval_reranker.py` (after the
`test_rerank_reorders_emitted_results` test added in Task 2):

```python
    @patch("openreview_cli.gateway.router.Gateway")
    def test_rerank_promotes_candidate_below_top_k(
        self,
        mock_gateway_class: MagicMock,
        runner: CliRunner,
        indexed_db: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """B2 guard: candidate index 5 (chunk-008, plain rank 6) must be promotable to rank 1."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_config"))
        mock_gw = MagicMock()
        mock_gw.rerank.return_value = [
            {"index": 5, "relevance_score": 0.99},
            {"index": 1, "relevance_score": 0.50},
        ]
        mock_gateway_class.return_value = mock_gw

        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidential information",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--top-k",
                "2",
                "--rerank",
                "--rerank-depth",
                "6",
                "--format",
                "json",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        data = _extract_json_from_output(result.output)
        assert [r["chunk_id"] for r in data["results"]] == ["chunk-008", "chunk-004"]
```

- [ ] **Step 3: Run the new tests to verify they fail**

```bash
uv run pytest tests/unit/test_retrieval_engine.py::TestRerankCandidatePool "tests/integration/test_retrieval_reranker.py::TestRetrieveRerankFlag::test_rerank_promotes_candidate_below_top_k" -v
```

Expected: 3 failed, 2 passed, 1 failed —
`assert {'c3'} == {'c1', 'c3', 'c4', 'c5'}`, `assert 1 == 5`, `assert 1 == 5` (pool is only
`top_k` wide), and `assert ['chunk-004', 'chunk-003'] == ['chunk-008', 'chunk-004']` (the reranker
never saw a sixth candidate, so `chunk-008` cannot be promoted).

- [ ] **Step 4: Write the minimal implementation**

In `src/openreview_cli/retrieval/engine.py`:

(a) insert after `logger = logging.getLogger(__name__)` (line 27):

```python
def _result_limit(query: RetrievalQuery) -> int:
    """Number of candidates to materialize (the rerank pool when reranking)."""
    return query.rerank_depth if query.rerank else query.top_k
```

(b) `_retrieve_sparse` — replace lines 145 and 173:

```python
        limit = _result_limit(query)
        raw_results = search_bm25(storage, query.query_text, limit)
```

```python
        return results[:limit]
```

(c) `_retrieve_dense` — replace the two `query.top_k` uses at lines 197 and 201:

```python
        limit = _result_limit(query)
        dense_ranks: dict[str, int] = {
            cid: rank for rank, (cid, _) in enumerate(scored[:limit], start=1)
        }
```

```python
        for cid, sim in scored[:limit]:
```

(d) `_retrieve_hybrid` — replace lines 237-241 and 247-251 and 261:

```python
        # Step 1: BM25 search
        limit = _result_limit(query)
        search_depth = max(limit * 3, 30)
        raw_sparse = search_bm25(storage, query.query_text, search_depth)
        sparse_ranks = normalize_bm25_scores(raw_sparse)
        sparse_ranks = dict(list(sparse_ranks.items())[:search_depth])
```

```python
                scored = self._search_dense_candidates(storage, self.gateway, query.query_text)
                dense_ranks = {
                    cid: rank for rank, (cid, _) in enumerate(scored[:search_depth], start=1)
                }
```

```python
        for _rank, (cid, rrf_score) in enumerate(fused[:limit], start=1):
```

With `rerank=False`, `limit == query.top_k` and `search_depth == max(query.top_k * 3, 30)`, i.e.
every expression above is what it is today.

- [ ] **Step 5: Run the pool tests to verify they pass**

```bash
uv run pytest tests/unit/test_retrieval_engine.py -v
```

Expected: all pass, including the 5 new pool tests.

- [ ] **Step 6: Run the existing retrieval suite to prove the default path is unchanged**

```bash
uv run pytest tests/unit/test_retrieval_engine.py tests/unit/test_retrieval_bm25.py tests/unit/test_retrieval_dense.py tests/unit/test_retrieval_rrf.py tests/integration/test_retrieve_command.py tests/integration/test_retrieval_fusion.py tests/integration/test_retrieval_engine.py tests/integration/test_retrieval_offline.py -v
```

Expected: all pass with no edits to those files.

- [ ] **Step 7: Run the CLI class to verify the promotion test passes**

```bash
uv run pytest "tests/integration/test_retrieval_reranker.py::TestRetrieveRerankFlag" -v
```

Expected: all five tests pass.

- [ ] **Step 8: Lint, format, type-check**

```bash
uv run ruff check . && uv run ruff format .
uv run mypy src/ tests/
```

Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add src/openreview_cli/retrieval/engine.py tests/unit/test_retrieval_engine.py tests/integration/test_retrieval_reranker.py
git commit -m "fix(retrieval): build the rerank candidate pool to rerank_depth"
```

---

### Task 4: `retrieve` wiring — config default, real model id, pool pass-through (bugs #3 and #4)

**Files:**
- Modify: `src/openreview_cli/app.py:2093` (insert two helpers before
  `_should_warn_reranker_degradation`), `app.py:2186-2195` (enabled resolution + query),
  `app.py:2202` (gateway construction), `app.py:2223-2231` (rerank block), `app.py:2251-2252`
  (failure fallback)
- Test: create `tests/unit/test_retrieve_rerank_wiring.py`
- Test: `tests/integration/test_retrieval_reranker.py` (two new CLI tests)

**Interfaces:**
- Consumes: `Gateway.slot_primary_model(slot) -> str | None` (Task 1),
  `DEFAULT_RERANK_MODEL` (Task 2), `engine.retrieve` pool semantics (Task 3),
  `retrieval.rerank_enabled` / `retrieval.reranker_model` from
  `load_config(get_config_dir() / "config.yml")` (`config/loader.py:66,214`).
- Produces: `_rerank_enabled_from_config() -> bool` (flag-independent config read) and
  `_reranker_model_id(gateway: Any) -> str` (slot primary → `retrieval.reranker_model` →
  `DEFAULT_RERANK_MODEL`). Behaviour of `openreview retrieve`: `--rerank` OR
  `retrieval.rerank_enabled` enables reranking; the validation record is read with the resolved
  model id; the emitted list is never longer than `--top-k`.

- [ ] **Step 1: Write the failing helper unit tests**

Create `tests/unit/test_retrieve_rerank_wiring.py`:

```python
"""Unit tests for the retrieve --rerank wiring (config default and bookkeeping model id)."""

from __future__ import annotations

from pathlib import Path

import pytest

from openreview_cli.app import _rerank_enabled_from_config, _reranker_model_id
from openreview_cli.config.loader import load_config, set_config_value
from openreview_cli.config.paths import get_config_dir


class _StubGateway:
    def __init__(self, primary: str | None) -> None:
        self._primary = primary

    def slot_primary_model(self, slot: str) -> str | None:
        return self._primary


@pytest.fixture(autouse=True)
def _isolated_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_config"))


def _write_config_value(key: str, value: str) -> None:
    config_path = get_config_dir() / "config.yml"
    load_config(config_path)
    set_config_value(config_path, key, value)


def test_rerank_disabled_by_default() -> None:
    assert _rerank_enabled_from_config() is False


def test_rerank_enabled_from_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENREVIEW_RETRIEVAL__RERANK_ENABLED", "true")

    assert _rerank_enabled_from_config() is True


def test_rerank_enabled_from_config_file() -> None:
    _write_config_value("retrieval.rerank_enabled", "true")

    assert _rerank_enabled_from_config() is True


def test_reranker_model_id_prefers_gateway_slot() -> None:
    assert _reranker_model_id(_StubGateway("voyage/rerank-2.5")) == "voyage/rerank-2.5"


def test_reranker_model_id_falls_back_to_config() -> None:
    _write_config_value("retrieval.reranker_model", "voyage/rerank-2.5")

    assert _reranker_model_id(_StubGateway(None)) == "voyage/rerank-2.5"


def test_reranker_model_id_defaults_to_bundled_model() -> None:
    assert _reranker_model_id(None) == "qwen3-reranker-0.6b"
```

- [ ] **Step 2: Run the helper tests to verify they fail**

```bash
uv run pytest tests/unit/test_retrieve_rerank_wiring.py -v
```

Expected: collection error —
`ImportError: cannot import name '_rerank_enabled_from_config' from 'openreview_cli.app'`. For a
brand-new helper this import error *is* the red state; there is no earlier point at which these
tests can fail.

- [ ] **Step 3: Write the minimal implementation of the two helpers**

Insert into `src/openreview_cli/app.py` immediately before
`def _should_warn_reranker_degradation(` (line 2093):

```python
def _rerank_enabled_from_config() -> bool:
    """Return `retrieval.rerank_enabled` from config.yml (OPENREVIEW_* overrides included)."""
    config = load_config(get_config_dir() / "config.yml")
    retrieval = config.get("retrieval", {})
    return bool(retrieval.get("rerank_enabled", False))


def _reranker_model_id(gateway: Any) -> str:
    """Resolve the model id used for reranker validation bookkeeping.

    Prefers the configured `reranking` gateway slot (the model that actually
    scores), then `retrieval.reranker_model`, then the bundled default.
    """
    from openreview_cli.retrieval.rerank import DEFAULT_RERANK_MODEL, RERANK_SLOT

    if gateway is not None:
        primary = gateway.slot_primary_model(RERANK_SLOT)
        if isinstance(primary, str) and primary:
            return primary
    config = load_config(get_config_dir() / "config.yml")
    fallback: object = config.get("retrieval", {}).get("reranker_model")
    if isinstance(fallback, str) and fallback:
        return fallback
    return DEFAULT_RERANK_MODEL
```

`load_config` and `get_config_dir` are already imported at module scope (`app.py:15-16`), and
`Any` at `app.py:9`. The `isinstance(primary, str)` guard is what makes a stubbed or partially
configured gateway fall through instead of recording a non-string id.

- [ ] **Step 4: Run the helper tests to verify they pass**

```bash
uv run pytest tests/unit/test_retrieve_rerank_wiring.py -v
```

Expected: `6 passed`.

- [ ] **Step 5: Write the failing CLI wiring tests**

Append to `class TestRetrieveRerankFlag` in `tests/integration/test_retrieval_reranker.py`:

```python
    @patch("openreview_cli.gateway.router.Gateway")
    def test_config_enables_rerank_without_the_flag(
        self,
        mock_gateway_class: MagicMock,
        runner: CliRunner,
        indexed_db: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """B3: retrieval.rerank_enabled must be honoured, not just the --rerank flag."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_config"))
        monkeypatch.setenv("OPENREVIEW_RETRIEVAL__RERANK_ENABLED", "true")
        mock_gw = MagicMock()
        mock_gw.rerank.return_value = [{"index": 1, "relevance_score": 0.99}]
        mock_gateway_class.return_value = mock_gw

        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidential information",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--top-k",
                "2",
                "--format",
                "json",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        data = _extract_json_from_output(result.output)
        assert data["results"][0]["chunk_id"] == "chunk-004"
        assert data["results"][0]["rerank_score"] == 0.99

    @patch("openreview_cli.gateway.router.Gateway")
    def test_unparseable_rerank_payload_falls_back_to_top_k(
        self,
        mock_gateway_class: MagicMock,
        runner: CliRunner,
        indexed_db: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A payload the reranker cannot parse must not widen the emitted list past --top-k."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_config"))
        mock_gw = MagicMock()
        mock_gw.rerank.return_value = [{"index": 0, "score": 0.9}]
        mock_gateway_class.return_value = mock_gw

        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidential information",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--top-k",
                "2",
                "--rerank",
                "--rerank-depth",
                "6",
                "--format",
                "json",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        data = _extract_json_from_output(result.output)
        assert [r["chunk_id"] for r in data["results"]] == ["chunk-003", "chunk-004"]
```

- [ ] **Step 6: Run the CLI tests to verify they fail**

```bash
uv run pytest "tests/integration/test_retrieval_reranker.py::TestRetrieveRerankFlag" -v
```

Expected: 2 failed, 5 passed —
`assert None == 0.99` (config does not enable reranking yet) and
`assert ['chunk-003', 'chunk-004', 'chunk-006', 'chunk-009', 'chunk-005', 'chunk-008'] ==
['chunk-003', 'chunk-004']` (the un-reranked fallback emits the whole `rerank_depth` pool instead of
`--top-k`).

- [ ] **Step 7: Wire the helpers into the command**

Five edits in `src/openreview_cli/app.py`.

(a) Resolve the effective flag and use it in the query:

```python
    rerank_enabled = rerank or _rerank_enabled_from_config()

    # Build query
    try:
        rq = RetrievalQuery(
            query_text=query,
            method=method,
            top_k=top_k,
            rerank=rerank_enabled,
            rerank_depth=rerank_depth,
            force_rerank=force_rerank,
        )
```

(b) Build the gateway when reranking is effectively on:

```python
    if method in ("dense", "hybrid") or rerank_enabled:
```

(c) Replace the rerank block header, the `Reranker` construction and the candidate slicing
(formerly lines 2224-2231) — the engine now hands over the pool, so the slice is deleted:

```python
    # ── Reranker integration (T031) ──
    if rerank_enabled and results:
        from openreview_cli.retrieval.rerank import Reranker
        from openreview_cli.retrieval.storage import RetrievalStorage

        try:
            reranker = Reranker(gateway, model_id=_reranker_model_id(gateway))
            results = reranker.rerank(query, results, top_k)
```

(d) Cap the fallback to `--top-k` (formerly lines 2251-2252):

```python
        except Exception as exc:
            logger.warning("Reranker integration failed (%s); returning raw results.", exc)
            results = results[:top_k]
```

(e) Confirm the block that reads the validation record is unchanged and now uses the resolved id:

```python
            with RetrievalStorage(db_path) as store:
                val = store.get_rerank_validation(
                    model_id=reranker.model_id,
                    document_type="legal-nda",
                )
```

- [ ] **Step 8: Run the CLI tests to verify they pass**

```bash
uv run pytest "tests/integration/test_retrieval_reranker.py::TestRetrieveRerankFlag" -v
```

Expected: `7 passed`.

- [ ] **Step 9: Run every retrieval/rerank test plus the app boundary tests**

```bash
uv run pytest tests/unit/test_retrieve_rerank_wiring.py tests/unit/test_rerank_warning.py tests/unit/test_retrieval_rerank.py tests/unit/test_retrieval_engine.py tests/integration/test_retrieval_reranker.py tests/integration/test_retrieve_command.py tests/integration/test_retrieval_benchmark.py -v
```

Expected: all pass. `test_retrieve_warns_when_stored_degraded` (line 170) keeps seeding
`qwen3-reranker-0.6b`: its `Gateway` is a `MagicMock`, so `slot_primary_model` returns a non-string
and `_reranker_model_id` falls through to `DEFAULT_RERANK_MODEL`, which is that same id.

- [ ] **Step 10: Lint, format, type-check**

```bash
uv run ruff check . && uv run ruff format .
uv run mypy src/ tests/
```

Expected: clean.

- [ ] **Step 11: Commit**

```bash
git add src/openreview_cli/app.py tests/unit/test_retrieve_rerank_wiring.py tests/integration/test_retrieval_reranker.py
git commit -m "fix(cli): wire retrieve rerank config default and slot model id"
```

---

## Self-review against the requirements

1. **Bug #1 (score key)** — Task 2, Steps 1-4 (unit reorder guard + loud-failure guard), Step 5
   (mocks corrected), Step 6 (CLI reorder guard, written red in Step 1).
2. **Bug #2 (inert pool)** — Task 3, Steps 1-3 (unit pool tests + characterization guards + CLI
   promotion test, all written and run red first) and Steps 4-7 (implementation + CLI promotion from
   plain rank 6).
3. **Bug #3 (dead config)** — Task 4, Steps 1-4 (`_rerank_enabled_from_config` unit tests) and
   Steps 5-8 (CLI runs with the flag absent).
4. **Bug #4 (model bookkeeping)** — Task 1 (accessor) + Task 4, Steps 1-4 and 7-9
   (`_reranker_model_id` chain: slot → config → default).
5. **Bug #5 (mocks hide the bug)** — Task 2, Step 5 (all 9 wrong payload blocks corrected across
   three files).
6. **Offline tests** — every new test uses `--method sparse` + a patched/`MagicMock` gateway, or a
   local tmp SQLite index; nothing opens a socket (`pyproject.toml:154`).
7. **Minimal, focused** — 4 source files, 6 test files, no config/schema/model changes, no
   refactors of unrelated code, no doc edits.
8. **No placeholders** — every step carries the exact code, command and expected output.

---

## Open questions and unresolved conflicts

1. **`--rerank` cannot switch reranking *off* when `retrieval.rerank_enabled: true`.** Task 4
   implements `rerank_enabled = flag or config`, so config can enable but the flag cannot veto.
   Making it fully symmetric needs a tri-state (`bool | None = typer.Option(None, "--rerank/--no-rerank")`)
   plus a `--no-rerank` path; Typer's `Optional[bool]` handling is the risky part, and the repo has
   no precedent for it (`grep "bool | None = typer" src/` → nothing), so I left it out. If you want
   the veto, add one task: `--no-rerank` flag + `rerank_enabled = flag if flag is not None else config`.
2. **Sibling dead config keys stay dead.** `retrieval.rerank_depth` (`config/loader.py:216`) and
   `retrieval.top_k` / `retrieval.default_method` (`loader.py:60-61`) are still only read from the
   CLI defaults; `specs/016-hierarchical-retrieval/tasks.md:303-304` says the config values should
   be the flag defaults, so this fix leaves that spec item partially unimplemented. Wiring
   `rerank_depth` needs `int | None = typer.Option(None, "--rerank-depth")` (unambiguous, unlike
   the bool) — deliberately out of scope here.
3. **Does the pool fix risk changing existing results?** No for `rerank=False`: `_result_limit`
   returns `top_k`, so `search_bm25`, `scored[:…]`, `max(limit * 3, 30)` and `fused[:…]` all see the
   same values as today. With `rerank=True` the fused *prefix* is unchanged but the *pool* is
   longer, and the hybrid BM25/dense search depth grows from `max(top_k * 3, 30)` to
   `max(rerank_depth * 3, 30)` (30 → 60 with the defaults) — more FTS rows scanned, no extra
   embedding or network calls.
   `tests/unit/test_retrieval_engine.py::TestRerankCandidatePool::test_pool_keeps_the_plain_result_order`
   pins the prefix invariant for the sparse path. Residual, accepted: with `rerank=True` and a
   failing reranker, the *un-reranked* fallback inside `Reranker.rerank` returns the pool's first
   `top_k` (`rerank.py:70,86`), i.e. the plain top-`top_k` with `rerank_score = None` — same ids,
   same order as without reranking.
4. **No provider-shape fallback on the score key.** Task 2 reads `item["relevance_score"]` and
   `item["index"]` directly, so an unexpected payload raises `KeyError` (caught by `app.py:2251`,
   which logs and returns the un-reranked top-`top_k`) instead of silently zeroing every score the
   way `item.get("score", 0.0)` did. The gateway's dict shape is fixed at `router.py:777-779`, and
   litellm normalises providers to `relevance_score`, so a `score`-key fallback would only
   re-create the silent no-op this plan removes. If a provider is ever found returning `score`,
   that belongs in `Gateway.rerank` (one place, with its own test), not in the reranker.
5. **Users with existing `rerank_validation` rows will not see the degradation warning.** After
   Task 4 the lookup key becomes the configured slot primary (default
   `ollama/qwen3-reranker-0.6b`, `config/loader.py:30`) instead of the bare
   `qwen3-reranker-0.6b`, so records seeded under the old key no longer match. That is the intended
   correction of bug #4; there is no data migration, and `storage.get_rerank_validation`
   (`retrieval/storage.py:292`) simply returns `None`.
6. **Docs are mid-reorg and deliberately untouched.** `docs/ARCHITECTURE.md:85`, `docs/BENCHMARKS.md:216`
   and `docs/BENCHMARKS.md:142` still describe the reranker as unmeasured/`--rerank`-only;
   `docs/ARCHITECTURE.md:59` does not mention `retrieval.rerank_enabled`. Those files are
   *untracked* in the current working tree (`git status` → `D ARCHITECTURE.md`, `?? docs/ARCHITECTURE.md`),
   so editing them would mix this fix into the unrelated docs reorg commit. Recommend updating them
   in the reorg commit instead; if you disagree, add a doc task after Task 4.
7. **Pre-existing, unrelated defect found while writing this plan (do not fix here).**
   `preprocess_query` lowercases the query (`src/openreview_cli/retrieval/bm25.py:20`), which
   destroys FTS5's uppercase-only boolean operators: `MATCH 'confidential OR governing'` returns
   rows, `MATCH 'confidential or governing'` returns nothing. Verified offline — the engine returns
   `[]` for `"confidential OR governing OR indemnification"`, and the existing test at
   `tests/unit/test_retrieval_engine.py:140-146` passes only because of that. This constrained how
   the new tests are written (single terms, no `OR`), and it is a real retrieval-quality bug worth
   its own issue.
8. **`Reranker.validate()` and `Reranker.rerank`'s `method` label.** `validate()` has no production
   caller (`grep -rn "Reranker(\|\.validate(" src/` → only `app.py:2229`), so the degradation
   warning can only fire against records inserted outside the CLI; and `rerank.py:98` labels every
   reranked row `method = "hybrid+rerank"` even for `--method sparse`. Both are out of scope for a
   wiring fix but will matter to the later CUAD measurement (it needs a caller and honest labels).
