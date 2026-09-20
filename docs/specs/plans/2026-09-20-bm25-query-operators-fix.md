# BM25 Query Operators & Term Semantics Fix — Implementation Plan

> **For agentic workers:** Use tasks as checkboxes (`- [ ]`) for tracking.
>
> **Process note:** This plan was produced with the **writing-plans** skill
> (`~/.agents/skills/writing-plans/SKILL.md`) and its tasks are ordered by the
> **test-driven-development** skill (`~/.agents/skills/test-driven-development/SKILL.md`):
> every task writes a failing test first, watches it fail, implements the minimum, watches it
> pass, then commits. Every "Expected" line below was produced by actually running the command
> in the three relevant states (current code, after Task 1, after Task 2) — see
> "Verified defect evidence".

**Goal:** Make the sparse/FTS retrieval leg match real natural-language queries (today it returns
zero rows for every CUAD-style question, and raises `sqlite3.OperationalError` on queries
containing a hyphenated name such as `I-Escrow`), and stop `preprocess_query` from destroying the
uppercase-only FTS5 boolean operators.

**Architecture:** One function changes — `preprocess_query`
(`src/openreview_cli/retrieval/bm25.py:12-24`) becomes a small FTS5 *expression builder*: strip
punctuation, lowercase and **quote** every term (so `"`, `*`, `-`, `:`, `NEAR`, unbalanced quotes
and column-filter syntax become inert instead of raising), and join the terms with **`OR`** (FTS5
reads a bare multi-term query as an implicit AND, which matches nothing for a long question).
Uppercase `AND` / `OR` / `NOT` that sit *between two terms* are emitted verbatim as operators, so
explicit operator queries keep their meaning. Callers do not change: `search_bm25`
(`bm25.py:44-58`) keeps its empty-expression guard, `RetrievalStorage.search_fts`
(`storage.py:177-188`) keeps executing the `MATCH`, and the storage schema, tokenizer
(`tokenize='unicode61'`) and prefix index (`prefix='2 3'`) are untouched.

**Tech Stack:** Python 3.12 pinned, `uv` only, SQLite **FTS5** (BM25 via `bm25(chunk_fts)`),
pytest 9 with `--disable-socket`, Ruff + mypy (strict), Conventional Commits.

## Global Constraints

- Python 3.12 pinned; `uv` only (`uv run ...`).
- `uv run ruff check . && uv run ruff format .` and `uv run mypy src/ tests/` (strict) must pass.
- No explanatory comments unless logic is non-obvious (repo style).
- Conventional Commits; do not edit `[tool.ruff]` / `[tool.mypy]` / pytest config.
- Tests must run offline: sockets are disabled by default
  (`pyproject.toml:154` → `addopts = "-v --tb=short --disable-socket --allow-unix-socket"`), so
  every test in this plan uses a temp SQLite file plus a `MagicMock`-free sparse path — no test
  may construct a real `Gateway`.
- Test markers: `tests/conftest.py:31-49` auto-assigns the `fast` marker to anything under
  `tests/unit/`, and *fails* any test without a speed marker, so new tests need **no** marker
  decorator.
- Keep changes minimal and focused; no unrelated refactors.
- Do not edit `src/openreview_cli/retrieval/storage.py` (schema, tokenizer, prefix index),
  `engine.py`, `rerank.py`, `app.py` or any config.
- Never `git add -A`: `git status --short` currently reports exactly one unrelated, untracked file
  (`?? scripts/benchmark_rerank_legalbenchrag.py`). Stage only the exact paths each commit lists.

---

## Verified defect evidence (each claim re-checked against the working tree)

All measurements below were made with Python 3.12 + this repo's SQLite, against an FTS5 table
declared exactly like the product's (`tokenize='unicode61'`, `prefix='2 3'`), and via
`RetrievalEngine.retrieve` on the repo's own fixtures.

| # | Claim | Evidence |
|---|-------|----------|
| 1 | **Lowercasing destroys FTS5 operators** | `preprocess_query` runs `query_text.lower()` at `src/openreview_cli/retrieval/bm25.py:20`. FTS5 boolean keywords are uppercase-only: on one index, `MATCH 'confidential OR governing'` → 4 rows, `MATCH 'confidential or governing'` → **0 rows**. `OR`/`AND` are *not* errors lowercase — they silently become ordinary terms in an implicit-AND query |
| 2 | **Bare multi-term = implicit AND → zero rows** | `MATCH 'confidential governing'` → 0 rows; `MATCH 'confidential or governing'` → 0 rows; the same terms with explicit `OR` → 4 rows. The repo's own ground-truth query `'return or destroy confidential information'` (`tests/fixtures/retrieval/ground_truth.json`) returns **0 rows** today. This is the observed CUAD symptom: ~24 real queries, sparse leg zero rows for every one |
| 3 | **Real CUAD questions do not merely return zero — they raise** | `preprocess_query("Consider [PARTY_C] between I-Escrow, Inc. and [PARTY_A]; …")` → `consider party_c between i-escrow inc and …`; FTS5 parses the hyphenated bareword as a column filter and raises `sqlite3.OperationalError: no such column: escrow`. Nothing catches it: the sparse entry points are `engine.py:152` and `engine.py:247`, and the try/except at `engine.py:253-261` wraps only the *dense* leg (the untracked measurement harness had to work around this, see `scripts/benchmark_rerank_legalbenchrag.py:168-186`) |
| 4 | **Stray hyphens are syntax errors too** | `preprocess_query("-")` → `-` → `fts5: syntax error near ""`; `preprocess_query("-confidential")` → `-confidential` → `no such column: confidential`; `preprocess_query("data-processing agreement")` → `data-processing agreement` → `no such column: processing` (verified against `RetrievalEngine.retrieve`) |
| 5 | **The guard test is vacuous, not failing** | `tests/unit/test_retrieval_engine.py:201-207` (identical test at `main:142-148` — the range the bug report cites; the branch's numbers shifted because `pooled_db` inserted 59 lines above it) asserts only `len(results) <= 2`. Measured: current code → `[]` (0 rows); fixed → `['c3', 'c1']` (2 rows). It passes in both states, so it never caught the defect. Same for `test_result_ordering_by_score` (`tests/unit/test_retrieval_engine.py:277-285`), whose assertions are guarded by `if len(results) >= 2:` |
| 6 | **Blast radius is one function + four stale assertions** | Running the **full unit suite** with the proposed `preprocess_query` swapped in (before changing any file): `2389 passed, 4 failed` — the 4 failures are exactly the stale expectations at `tests/unit/test_retrieval_bm25.py:11-32`. **Full integration suite** with the same swap: `621 passed, 4 skipped, 2 failed`, both unrelated (one pre-existing PII-threshold failure that also fails on the untouched tree; one 50 s timing flake that passes in isolation with the swap in place). The hard-coded chunk orders in `tests/integration/test_retrieval_reranker.py:202-206, 248, 284, 323` stay valid because `confidential information` returns the identical order `['chunk-003','chunk-004','chunk-006','chunk-009','chunk-005','chunk-008']` before and after |

## Decision: what the new query semantics are

Two candidate fixes were considered. **Operators-only** (preserve uppercase `AND/OR/NOT`, leave
bare terms as an implicit AND) fixes claim 1 but *not* claim 2 — real queries contain no operators,
so the CUAD corpus would still record zero rows for the sparse leg. **OR-ify bare terms** (this
plan) fixes both, at the cost of changing default recall semantics.

| | Operators-only | OR-ify bare terms (**chosen**) |
|---|---|---|
| `confidential OR governing` | works | works (operator preserved) |
| `confidential or governing` | **0 rows** (lowercase `or` is a term) | matches both terms; `"or"` is just a useless extra term |
| Long NL question | **0 rows** (implicit AND over ~15 terms) | matches on any term, BM25 ranks by how many/how rare |
| `a b AND c` | `a AND b AND c` | `a OR (b AND c)` (FTS5 precedence: `AND` binds tighter) |
| Risk | defect survives | queries that "meant" AND now return more rows (recall up, precision down); mitigated by `bm25()` ranking + `LIMIT`, and recoverable by writing `AND`/`NOT` explicitly |

**Recommendation: OR-ify bare terms while preserving uppercase operators.** It is the only option
that fixes the measured failure, it makes lowercase `or` harmless by construction, and it matches
the default of mainstream sparse engines (Lucene/Elasticsearch default to `OR` with
`minimum_should_match` available for callers that want AND). See "Open decisions" for the parts a
human must still sign off.

## File structure

- **Modify** `src/openreview_cli/retrieval/bm25.py` — replace `preprocess_query` (`:12-24`) and add
  a private `_tokenize` helper; add one `_FTS_OPERATORS` constant in Task 2. Only file with
  production changes.
- **Modify** `tests/unit/test_retrieval_bm25.py` — replace the stale expectations in
  `TestPreprocessQuery` (`:8-40`) with the new query-expression contract (Task 1) and add operator
  tests (Task 2).
- **Modify** `tests/unit/test_retrieval_engine.py` — new `nl_query_db` fixture + new
  `TestSparseNaturalLanguageQueries` class (Task 1), strengthen
  `test_retrieve_sparse_top_k_respected` (`:201-207`, Task 1), add `TestOperatorSemantics`
  (Task 2).
- **Create** `docs/specs/plans/2026-09-20-bm25-query-operators-fix.md` — this plan (Task 0).
- **Not touched:** `retrieval/storage.py`, `retrieval/engine.py`, `retrieval/rerank.py`, `app.py`,
  config, and the untracked `scripts/benchmark_rerank_legalbenchrag.py` (see "Out of scope").

---

### Task 0: Create the working branch (stacked on `fix/reranker-rerank-wiring`)

**Files:**
- Create: `docs/specs/plans/2026-09-20-bm25-query-operators-fix.md` (this plan, already written)

**Interfaces:**
- Consumes: nothing.
- Produces: branch `fix/bm25-query-operators`, whose base is `fix/reranker-rerank-wiring`.

- [ ] **Step 1: Confirm the starting point**

```bash
git status --short
git branch --show-current
```

Expected: branch is `fix/reranker-rerank-wiring`; `git status --short` prints only
`?? scripts/benchmark_rerank_legalbenchrag.py` (unrelated and untracked — never stage it).

- [ ] **Step 2: Create the stacked branch**

```bash
git switch --create fix/bm25-query-operators
git branch --show-current
git log --oneline -1
```

Expected: `fix/bm25-query-operators`; `git log --oneline -1` prints
`edd2652 chore(retrieval): align rerank comments and degradation tests`. Do **not** work on `main`.

- [ ] **Step 3: Commit this plan**

```bash
git add docs/specs/plans/2026-09-20-bm25-query-operators-fix.md
git commit -m "docs: add BM25 query operator fix plan"
```

---

### Task 1: `preprocess_query` builds a quoted OR expression (fixes the zero-result / crash path)

**Files:**
- Modify: `src/openreview_cli/retrieval/bm25.py:12-24`
- Test: `tests/unit/test_retrieval_bm25.py` (`TestPreprocessQuery`, `:8-40`)
- Test: `tests/unit/test_retrieval_engine.py` (new fixture after `:161`; strengthen `:201-207`; new
  class appended after `:457`)

**Interfaces:**
- Consumes: `_NON_ALPHANUM_RE` and `_WHITESPACE_RE` (`bm25.py:8-9`); the empty-expression guard in
  `search_bm25` (`bm25.py:54-56`), which already returns `[]` for `""`.
- Produces:
  - `_tokenize(query_text: str) -> list[str]` — punctuation-free tokens, inner hyphens preserved.
  - `preprocess_query(query_text: str) -> str` — an FTS5 `MATCH` expression: every term lowercased
    and wrapped in `"..."`, joined with `` OR ``; `""` when the input has no terms. Task 2 extends
    this function.

- [ ] **Step 1: Write the failing engine tests**

In `tests/unit/test_retrieval_engine.py`, insert this fixture immediately after the `pooled_db`
fixture (i.e. after line 161, before `class TestRetrievalEngine:` at line 164):

```python
@pytest.fixture
def nl_query_db(tmp_path: Path) -> str:
    """Sparse-only index of natural-language contract clauses (no embeddings)."""
    db_path = str(tmp_path / "nl_query.db")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE index_meta (
            document_id TEXT PRIMARY KEY, document_path TEXT NOT NULL DEFAULT '',
            index_version INTEGER NOT NULL DEFAULT 1,
            index_status TEXT NOT NULL DEFAULT 'indexed',
            index_timestamp TEXT, chunk_count INTEGER NOT NULL DEFAULT 0,
            method TEXT NOT NULL DEFAULT 'sparse', embedding_model TEXT,
            embedding_dim INTEGER, db_size_bytes INTEGER DEFAULT 0
        );
        INSERT INTO index_meta (document_id, index_status, chunk_count, method)
        VALUES ('nl-doc', 'indexed', 4, 'sparse');
        CREATE TABLE chunks (
            chunk_id TEXT PRIMARY KEY, document_id TEXT NOT NULL DEFAULT 'nl-doc',
            text TEXT NOT NULL, clause_heading TEXT NOT NULL,
            clause_level INTEGER NOT NULL DEFAULT 0, parent_chunk_id TEXT,
            heading_chain TEXT NOT NULL DEFAULT '[]',
            char_start INTEGER NOT NULL DEFAULT 0, char_end INTEGER NOT NULL DEFAULT 1
        );
        INSERT INTO chunks VALUES
            ('n1','nl-doc','the expiration date of this contract is twelve months from the effective date','Section 9.1',0,NULL,'["Section 9.1"]',0,100),
            ('n2','nl-doc','either party may terminate this agreement for material breach','Section 12',0,NULL,'["Section 12"]',200,300),
            ('n3','nl-doc','governing law is the state of delaware','Section 7',0,NULL,'["Section 7"]',400,500),
            ('n4','nl-doc','confidential information shall be protected by the receiving party','Section 3',0,NULL,'["Section 3"]',600,700);
        CREATE VIRTUAL TABLE chunk_fts USING fts5(
            chunk_id UNINDEXED, text, clause_heading, content='chunks', content_rowid='rowid',
            tokenize='unicode61', prefix='2 3'
        );
        INSERT INTO chunk_fts (rowid, chunk_id, text, clause_heading)
        SELECT rowid, chunk_id, text, clause_heading FROM chunks;
    """)
    conn.commit()
    conn.close()
    return db_path
```

Then append this class at the end of the same file (after `test_pool_keeps_the_plain_result_order`
at line 457):

```python
class TestSparseNaturalLanguageQueries:
    """The sparse leg must match real questions, not just single keywords."""

    def test_natural_language_question_returns_rows(self, nl_query_db: str) -> None:
        engine = RetrievalEngine(nl_query_db)
        query = RetrievalQuery(
            query_text="What is the expiration date of this contract?",
            method="sparse",
            top_k=3,
        )

        results = engine.retrieve(query)

        assert [r.chunk_id for r in results] == ["n1", "n3", "n2"]

    def test_cuad_style_question_with_hyphenated_name_returns_rows(self, nl_query_db: str) -> None:
        engine = RetrievalEngine(nl_query_db)
        query = RetrievalQuery(
            query_text=(
                "Consider [PARTY_C] between I-Escrow, Inc. and [PARTY_A]; "
                "What is the expiration date of this contract?"
            ),
            method="sparse",
            top_k=3,
        )

        results = engine.retrieve(query)

        assert [r.chunk_id for r in results] == ["n1", "n3", "n2"]

    def test_lowercase_or_does_not_empty_the_result_set(self, nl_query_db: str) -> None:
        engine = RetrievalEngine(nl_query_db)
        query = RetrievalQuery(query_text="expiration or terminate", method="sparse", top_k=5)

        results = engine.retrieve(query)

        assert {r.chunk_id for r in results} == {"n1", "n2"}

    def test_uppercase_or_query_returns_rows(self, nl_query_db: str) -> None:
        engine = RetrievalEngine(nl_query_db)
        query = RetrievalQuery(query_text="expiration OR terminate", method="sparse", top_k=5)

        results = engine.retrieve(query)

        assert {r.chunk_id for r in results} == {"n1", "n2"}

    def test_realistic_multi_word_query_returns_matching_clause(self, nl_query_db: str) -> None:
        engine = RetrievalEngine(nl_query_db)
        query = RetrievalQuery(
            query_text="return or destroy confidential information", method="sparse", top_k=5
        )

        results = engine.retrieve(query)

        assert results[0].chunk_id == "n4"

    @pytest.mark.parametrize(
        "query_text",
        [
            '"',
            "*",
            "NEAR",
            "-",
            "data-processing",
            "-confidential",
            'he said "confidential"',
            "confid* -term",
            "a NEAR/3 b",
            "text:confidential",
            ":",
        ],
    )
    def test_fts_metacharacters_do_not_raise(self, nl_query_db: str, query_text: str) -> None:
        engine = RetrievalEngine(nl_query_db)

        results = engine.retrieve(RetrievalQuery(query_text=query_text, method="sparse", top_k=3))

        assert isinstance(results, list)
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
uv run pytest tests/unit/test_retrieval_engine.py::TestSparseNaturalLanguageQueries -v
```

Expected: **9 failed, 7 passed**. The 9 failures are
`test_natural_language_question_returns_rows` and
`test_lowercase_or_does_not_empty_the_result_set` (`assert [] == [...]` — zero rows),
`test_uppercase_or_query_returns_rows` (zero rows), `test_realistic_multi_word_query_returns_matching_clause`
(`IndexError` — zero rows), `test_cuad_style_question_with_hyphenated_name_returns_rows`
(`sqlite3.OperationalError: no such column: escrow`) and four metacharacter cases
(`[-]` → `fts5: syntax error near ""`, `[data-processing]` → `no such column: processing`,
`[-confidential]` → `no such column: confidential`, `[confid* -term]` → `no such column: term`).
The 7 that already pass are `'"'`, `'*'`, `'NEAR'`, `'he said "confidential"'`, `'a NEAR/3 b'`,
`'text:confidential'`, `':'` — they are the guard against *new* breakage.

- [ ] **Step 3: Strengthen the vacuous guard test**

Replace `tests/unit/test_retrieval_engine.py:201-207` with:

```python
    def test_retrieve_sparse_top_k_respected(self, populated_db: str) -> None:
        engine = RetrievalEngine(populated_db)
        query = RetrievalQuery(
            query_text="confidential OR governing OR indemnification", method="sparse", top_k=2
        )

        results = engine.retrieve(query)

        assert [r.chunk_id for r in results] == ["c3", "c1"]
        assert all(r.method == "sparse" for r in results)
```

- [ ] **Step 4: Run it to verify it fails**

```bash
uv run pytest tests/unit/test_retrieval_engine.py::TestRetrievalEngine::test_retrieve_sparse_top_k_respected -v
```

Expected: **1 failed** with `assert [] == ['c3', 'c1']` — today the lowercase `or` kills the query
and the old `<= 2` assertion passed on zero rows.

- [ ] **Step 5: Write the failing builder tests**

Replace the whole `TestPreprocessQuery` class body (`tests/unit/test_retrieval_bm25.py:8-40`) with:

```python
class TestPreprocessQuery:
    """Tests for query preprocessing."""

    def test_lowercase(self) -> None:
        assert preprocess_query("CONFIDENTIALITY") == '"confidentiality"'

    def test_strip_punctuation(self) -> None:
        result = preprocess_query("confidentiality, obligations!")
        assert result == '"confidentiality" OR "obligations"'

    def test_preserve_hyphens(self) -> None:
        result = preprocess_query("data-processing agreement")
        assert result == '"data-processing" OR "agreement"'

    def test_mixed_punctuation_and_hyphens(self) -> None:
        result = preprocess_query("Return of Confidential Information? (Section 5.1)")
        assert (
            result
            == '"return" OR "of" OR "confidential" OR "information" OR "section" OR "5" OR "1"'
        )

    def test_whitespace_collapse(self) -> None:
        result = preprocess_query("  wide   spaces  ")
        assert result == '"wide" OR "spaces"'

    def test_empty_query_returns_empty(self) -> None:
        result = preprocess_query("")
        assert result == ""

    def test_query_with_only_punctuation(self) -> None:
        result = preprocess_query("?!,.;:")
        assert result == ""

    def test_terms_are_quoted_so_metacharacters_are_inert(self) -> None:
        result = preprocess_query('he said "confidential"')
        assert result == '"he" OR "said" OR "confidential"'

    def test_multi_term_query_is_or_joined(self) -> None:
        result = preprocess_query("governing law delaware")
        assert result == '"governing" OR "law" OR "delaware"'

    def test_lowercase_or_is_a_term_not_an_operator(self) -> None:
        result = preprocess_query("confidential or governing")
        assert result == '"confidential" OR "or" OR "governing"'
```

- [ ] **Step 6: Run them to verify they fail**

```bash
uv run pytest tests/unit/test_retrieval_bm25.py::TestPreprocessQuery -v
```

Expected: **8 failed, 2 passed** (only `test_empty_query_returns_empty` and
`test_query_with_only_punctuation` pass today). The 8 failures show the old output, e.g.
`assert 'confidentiality' == '"confidentiality"'` and
`assert 'confidential or governing' == '"confidential" OR "or" OR "governing"'`.

- [ ] **Step 7: Write the minimal implementation**

Replace `src/openreview_cli/retrieval/bm25.py:12-24` with:

```python
def _tokenize(query_text: str) -> list[str]:
    """Split query text into punctuation-free tokens, preserving inner hyphens."""
    stripped = _NON_ALPHANUM_RE.sub(" ", query_text)
    return [token for token in _WHITESPACE_RE.split(stripped.strip()) if token]


def preprocess_query(query_text: str) -> str:
    """Build a safe FTS5 MATCH expression from raw query text.

    Steps:
    1. Strip punctuation (preserve hyphens in legal terms like "data-processing")
    2. Lowercase and quote each term, so FTS5 metacharacters (" * - : NEAR)
       cannot raise a syntax error
    3. Join terms with OR — FTS5 reads a bare multi-term query as an implicit
       AND, which matches nothing for natural-language questions
    """
    return " OR ".join(f'"{token.lower()}"' for token in _tokenize(query_text))
```

Nothing else changes: `search_bm25` (`bm25.py:44-58`) passes the expression through and still
returns `[]` for `""` (guard at `bm25.py:54-56`), so an operator-only or punctuation-only query
never reaches SQLite.

- [ ] **Step 8: Run the builder tests to verify they pass**

```bash
uv run pytest tests/unit/test_retrieval_bm25.py -v
```

Expected: `TestPreprocessQuery` **10 passed**; the whole file (`TestNormalizeBm25Scores` included,
6 tests — the file has 13 tests today) **16 passed**.

- [ ] **Step 9: Run the engine tests to verify the defect is gone**

```bash
uv run pytest tests/unit/test_retrieval_engine.py -v
```

Expected: **all passed** (the 9 red tests from Step 2 plus the strengthened guard from Step 4).

- [ ] **Step 10: Prove nothing downstream regressed**

```bash
uv run pytest tests/integration/test_retrieval_reranker.py tests/integration/test_retrieval_benchmark.py tests/integration/test_retrieve_command.py tests/integration/test_retrieval_performance.py tests/integration/test_retrieval_offline.py -v
```

Expected: **39 passed, 1 skipped** — in particular the hard-coded chunk orders in
`tests/integration/test_retrieval_reranker.py:202-206` (`["chunk-006", "chunk-004", "chunk-003"]`),
`:248` (`["chunk-008", "chunk-004"]`), `:284` (`chunk-004`) and `:323`
(`["chunk-003", "chunk-004"]`) must still hold, and
`tests/integration/test_retrieval_benchmark.py` gains the previously dead
`'return or destroy confidential information'` query (`tests/fixtures/retrieval/ground_truth.json`).

- [ ] **Step 11: Lint and type-check**

```bash
uv run ruff check . && uv run ruff format . && uv run mypy src/ tests/
```

Expected: no changes from `format`, no errors from `check`/`mypy`.

- [ ] **Step 12: Commit**

```bash
git add src/openreview_cli/retrieval/bm25.py tests/unit/test_retrieval_bm25.py tests/unit/test_retrieval_engine.py
git commit -m "fix(retrieval): OR-join quoted terms in the BM25 query expression"
```

---

### Task 2: Preserve uppercase FTS5 operators (`AND` / `OR` / `NOT`)

**Files:**
- Modify: `src/openreview_cli/retrieval/bm25.py` (add the operator constant; extend
  `preprocess_query`)
- Test: `tests/unit/test_retrieval_bm25.py` (`TestPreprocessQuery`)
- Test: `tests/unit/test_retrieval_engine.py` (new `TestOperatorSemantics` class appended)

**Interfaces:**
- Consumes: `_tokenize` and `preprocess_query` from Task 1.
- Produces: `preprocess_query(query_text: str) -> str` — same signature and same quoted-term
  format, but an uppercase `AND`/`OR`/`NOT` that separates two terms is emitted verbatim instead
  of `OR`; an operator with a missing left or right neighbour is dropped; operator-only input still
  yields `""`.

- [ ] **Step 1: Write the failing builder tests**

Append to `TestPreprocessQuery` in `tests/unit/test_retrieval_bm25.py`:

```python
    def test_uppercase_or_is_preserved_as_an_operator(self) -> None:
        result = preprocess_query("confidential OR governing")
        assert result == '"confidential" OR "governing"'

    def test_uppercase_and_is_preserved_as_an_operator(self) -> None:
        result = preprocess_query("confidential AND governing")
        assert result == '"confidential" AND "governing"'

    def test_uppercase_not_is_preserved_as_an_operator(self) -> None:
        result = preprocess_query("a NOT b NOT c")
        assert result == '"a" NOT "b" NOT "c"'

    def test_operator_without_a_left_term_is_dropped(self) -> None:
        assert preprocess_query("OR confidential") == '"confidential"'
        assert preprocess_query("NOT confidential") == '"confidential"'

    def test_operator_without_a_right_term_is_dropped(self) -> None:
        assert preprocess_query("confidential OR") == '"confidential"'

    def test_operator_only_query_returns_empty(self) -> None:
        assert preprocess_query("AND") == ""
        assert preprocess_query("OR OR") == ""

    def test_repeated_operators_collapse(self) -> None:
        assert preprocess_query("a OR OR b") == '"a" OR "b"'

    def test_implicit_or_applies_around_an_explicit_operator(self) -> None:
        assert preprocess_query("a b AND c") == '"a" OR "b" AND "c"'
```

- [ ] **Step 2: Run them to verify they fail**

```bash
uv run pytest tests/unit/test_retrieval_bm25.py::TestPreprocessQuery -v
```

Expected: **8 failed, 10 passed**. The failures show Task 1's output, e.g.
`assert '"confidential" OR "or" OR "governing"' == '"confidential" OR "governing"'` and
`assert '"and"' == ''` for the operator-only query.

- [ ] **Step 3: Write the failing engine test**

Append to `tests/unit/test_retrieval_engine.py`:

```python
class TestOperatorSemantics:
    """Uppercase FTS5 operators must narrow, not be OR-ified away."""

    def test_uppercase_and_matches_only_chunks_with_both_terms(self, nl_query_db: str) -> None:
        engine = RetrievalEngine(nl_query_db)
        query = RetrievalQuery(query_text="expiration AND contract", method="sparse", top_k=5)

        results = engine.retrieve(query)

        assert [r.chunk_id for r in results] == ["n1"]

    def test_uppercase_and_excludes_chunks_without_both_terms(self, nl_query_db: str) -> None:
        engine = RetrievalEngine(nl_query_db)
        query = RetrievalQuery(query_text="expiration AND breach", method="sparse", top_k=5)

        results = engine.retrieve(query)

        assert results == []
```

- [ ] **Step 4: Run them to verify they fail**

```bash
uv run pytest tests/unit/test_retrieval_engine.py::TestOperatorSemantics -v
```

Expected: **1 failed, 1 passed** — `test_uppercase_and_excludes_chunks_without_both_terms` fails
with `assert ['n2', 'n1'] == []`, because Task 1 OR-ifies the `AND` (the first test happens to pass
in both the current and the Task-1 state, since no chunk contains both terms today; it is the
positive guard for the new behaviour).

- [ ] **Step 5: Write the minimal implementation**

In `src/openreview_cli/retrieval/bm25.py`, add the constant directly after
`_WHITESPACE_RE` (line 9):

```python
_FTS_OPERATORS = frozenset({"AND", "OR", "NOT"})
```

and replace the `preprocess_query` body added in Task 1 with:

```python
def preprocess_query(query_text: str) -> str:
    """Build a safe FTS5 MATCH expression from raw query text.

    Steps:
    1. Strip punctuation (preserve hyphens in legal terms like "data-processing")
    2. Lowercase and quote each term, so FTS5 metacharacters (" * - : NEAR)
       cannot raise a syntax error
    3. Join terms with OR — FTS5 reads a bare multi-term query as an implicit
       AND, which matches nothing for natural-language questions
    4. Keep uppercase AND/OR/NOT as operators where they separate two terms;
       FTS5 operators are uppercase-only, so a lowercased operator would be
       silently demoted to an ordinary term
    """
    expression: list[str] = []
    pending_operator: str | None = None
    for token in _tokenize(query_text):
        if token in _FTS_OPERATORS:
            if expression:
                pending_operator = token
            continue
        if expression:
            expression.append(pending_operator or "OR")
        expression.append(f'"{token.lower()}"')
        pending_operator = None
    return " ".join(expression)
```

`_tokenize` is unchanged, and so is every caller. No `"` can reach a quoted literal because
`_NON_ALPHANUM_RE` (`bm25.py:8`) removes it first, so the FTS5 string literals are always closed.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
uv run pytest tests/unit/test_retrieval_bm25.py tests/unit/test_retrieval_engine.py -v
```

Expected: all passed (18 builder tests; the engine file with both new classes green).

- [ ] **Step 7: Re-run the wider retrieval suites**

```bash
uv run pytest tests/integration/test_retrieval_reranker.py tests/integration/test_retrieval_benchmark.py tests/integration/test_retrieve_command.py tests/integration/test_retrieval_performance.py tests/integration/test_retrieval_offline.py -v
```

Expected: **39 passed, 1 skipped** (same set and counts as Task 1 Step 10 — operators must not
change the fixture order).

- [ ] **Step 8: Lint and type-check**

```bash
uv run ruff check . && uv run ruff format . && uv run mypy src/ tests/
```

Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add src/openreview_cli/retrieval/bm25.py tests/unit/test_retrieval_bm25.py tests/unit/test_retrieval_engine.py
git commit -m "fix(retrieval): preserve uppercase FTS5 operators in BM25 queries"
```

---

## Manual verification (not part of CI — needs network and API keys)

After Task 2, re-run the LegalBenchRAG CUAD pilot to confirm the product's own sparse leg is alive.
This is measurement, not a test: it is skipped by the offline pytest default
(`pyproject.toml:154`).

1. `scripts/benchmark_rerank_legalbenchrag.py` is **untracked** and must be fixed by whoever runs
   it: `safe_bm25` (`:168-186`) exists only to work around this defect — it re-quotes
   `preprocess_query`'s output (now already quoted, so it would emit `""term""`) and its
   `mode="and"` arm reproduces the old implicit-AND zero rows. Delete `safe_bm25` and call
   `search_bm25` (`bm25.py:44`) directly; the docstring at `:171-177` ("the unmodified product
   sparse path crashes on real CUAD queries") describes the state this plan removes.
2. Record, for the same pilot slice: sparse-leg rows per query (must be > 0 for every query),
   sparse P@5, hybrid P@5, and reranked P@5. The pre-fix baseline was 0 rows for all queries with
   P@5 0.158 for the OR-joined variant.

## Self-review against the requirements

- Uppercase `OR` matches → `tests/unit/test_retrieval_bm25.py::test_uppercase_or_is_preserved_as_an_operator`
  (builder) + `tests/unit/test_retrieval_engine.py::TestSparseNaturalLanguageQueries::test_uppercase_or_query_returns_rows`
  (end-to-end).
- Lowercase `or` no longer silently kills the query →
  `test_lowercase_or_is_a_term_not_an_operator` +
  `test_lowercase_or_does_not_empty_the_result_set` (+ the strengthened `test_retrieve_sparse_top_k_respected`).
- Long natural-language question returns results instead of zero →
  `test_natural_language_question_returns_rows`; realistic multi-word regression →
  `test_realistic_multi_word_query_returns_matching_clause` and the CUAD-style
  `test_cuad_style_question_with_hyphenated_name_returns_rows`.
- Metacharacters (`"`, `*`, `NEAR`, `-`, `:`) do not raise →
  `test_fts_metacharacters_do_not_raise` (11 parametrized cases) and `test_terms_are_quoted_so_metacharacters_are_inert`.
- Minimality: one production function + one private helper; no schema, engine, CLI, config or
  storage change; the four stale assertions were updated because they encoded the old contract.
- Type consistency: `_tokenize(query_text: str) -> list[str]` and
  `preprocess_query(query_text: str) -> str` are the only new/changed signatures, and no caller
  passes anything else (`engine.py:152, 247` and `rerank.py:144, 149` all call `search_bm25`, whose
  own signature is unchanged).

## Open decisions for a human

1. **Sign off the semantics change.** OR-ifying bare terms is a product behaviour change: `a b AND c`
   becomes `a OR (b AND c)`, and queries a user "meant" as AND now return more rows. If that is not
   wanted, the alternative is operators-only — but then the measured zero-row failure on the default
   path survives, so the sparse leg should be treated as a rerank-recall booster only.
2. **Quoted phrases.** A user-typed `"confidential information"` is still stripped to two OR-ed
   terms (identical to today, so no regression, but also no phrase search). Supporting phrases means
   preserving the quote pair before stripping; out of scope here.
3. **`NEAR` support.** `NEAR` and `NEAR/n` are treated as ordinary terms (`NEAR/3` cannot work while
   `/` is stripped as punctuation). Decide whether proximity search is ever wanted; it is a larger
   grammar change.
4. **Query-term count.** Long questions now produce a long `OR` chain (a 15-term CUAD question is
   one `OR` chain). BM25 ranking and `LIMIT` keep it correct and bounded, but if latency matters for
   very long queries, a term cap or stop-word list is the follow-up (not part of this fix; the perf
   budget at `tests/integration/test_retrieval_performance.py:112` passes today).
5. **Spec drift.** `specs/016-hierarchical-retrieval/contracts/api.md:254-264` and
   `specs/016-hierarchical-retrieval/tasks.md:89` still document the old "lowercase, split, rejoin
   with spaces" contract. Like the sibling reranker plan, this plan leaves the closed spec untouched —
   decide whether to annotate it.

## Out of scope (deliberately not changed)

- `RetrievalStorage.search_fts` (`storage.py:177-188`) does not gain a `try/except sqlite3.OperationalError`.
  FTS5 syntax errors are structurally impossible once every term is quoted, and swallowing errors
  there would hide real schema/index bugs.
- `_retrieve_hybrid`'s candidate depth (`engine.py:246`, `search_depth = max(limit * 3, 30)`) and RRF
  fusion are left alone: with a live sparse leg the fusion now has real sparse ranks to combine.
- `tests/unit/test_retrieval_engine.py:277-285` (`test_result_ordering_by_score`) stays as-is; it is
  still guarded by `if len(results) >= 2:`, but it is no longer vacuous now that the query returns
  rows. Strengthening it further is optional.
- `scripts/benchmark_rerank_legalbenchrag.py` (untracked; see Manual verification).
