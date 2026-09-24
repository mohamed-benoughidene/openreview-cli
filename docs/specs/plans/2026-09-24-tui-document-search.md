# TUI Document Search Workflow Implementation Plan

> **For agentic workers:** Use tasks as checkboxes (`- [ ]`) for tracking.

**Goal:** Let a user chunk a document, index it, and search inside it from the TUI, as one guided flow, without ever leaving the app.

**Architecture:** A new `Retrieve` tab holds a single button that opens `RetrieveScreen`, which walks the user through choose-document -> Chunk -> Ingest -> Search in order, keeps the index status visible, and puts a confirmation in front of the destructive Clear. All heavy work is delegated to a thin domain adapter that calls the existing `retrieval/ingest.py` and `retrieval/engine.py` functions; no chunking, indexing, embedding or scoring logic is reimplemented.

**Tech Stack:** Python 3.12, Textual (TUI), Typer (CLI, untouched except one shared function), SQLite FTS5 + BM25 (sparse retrieval), pytest + Textual `run_test`/`Pilot`.

**Revision note:** cycle 1 of 2. Rewritten against two independent reviews. The two blockers they found are in T3 and T2; every cut they justified is applied; the two disagreements are logged at the end.

## Global Constraints

- **Python 3.12, uv only.** No new dependencies; `uv add` is not used in this plan.
- **No module-level import of `openreview_cli.gateway.router` in `tui/`.** `gateway/__init__.py` is a lazy facade (`gateway/__init__.py:1-4`: "importing the package never pulls litellm"), so importing `gateway.models` (pydantic only) is safe and already happens via `retrieval/dense.py:12`; `gateway.router` is the module that imports litellm (measured: 3.17 s) and must stay out of `tui/`. This plan never constructs a `Gateway`, so litellm is never imported.
- **Privacy first.** No document text, chunk text, PII or query may be logged. The new code logs counts and durations only.
- **Local CLI only.** No web server, no daemon, no long-running process.
- **TDD.** Failing test first, minimal code to pass, then refactor. No production code without a prior test.
- **Conventional Commits.** `feat:`/`fix:`/`docs:`/`test:`/`refactor:`/`chore:`.
- **Do not weaken an existing test to make a new one pass.**
- **The only shared-code change is T1.** The CLI's five commands keep working exactly as they do today.
- **TUI tests are auto-marked `slow`** (`tests/integration/tui/conftest.py`) and each file is run in isolation; `run_test()` leaves residual terminal state in a shared process.
- **Every TUI test that touches the index must use the `isolated_xdg` fixture** (`tests/conftest.py:227-265`), and the adapter must accept `db_dir` so a test can redirect it. Without this, a test writes `<sha256(nda_with_pii.pdf)[:32]>.db` and a rewritten `last_indexed.json` into the developer's real `~/.local/share/openreview/indexes/`, silently changing what the CLI's bare `retrieve "<query>"` targets.
- **Known-broken test to leave alone:** `tests/integration/tui/test_app.py::test_sigterm_mid_review_cancels_cleanly` (xfail, pre-existing).

## The real sequence (verified at HEAD, with evidence)

**parse -> chunk -> ingest -> retrieve.** `chunk` never touches the index; `ingest` never parses a PDF; `retrieve` never chunks.

| Step | Callable | Evidence |
|---|---|---|
| Parse | `parse_document(path, *, allow_password_prompt=True) -> tuple[Document, list[Clause]]` | `parsing/stream.py:74` |
| Chunk | `stream_chunks(clauses, config=None) -> Iterator[Chunk]`; `ChunkConfig()` defaults `chunk_size=512, chunk_overlap=50, group_short_clauses=True` | `chunking/stream.py:13`, `chunking/models.py:32-36` |
| Ingest | `ingest_document(chunks, db_path, gateway=None, method="hybrid", model_id=None, progress_callback=None, document_id=None) -> dict` | `retrieval/ingest.py:164-172` |
| Search | `RetrievalEngine(db_path, gateway=None).retrieve(RetrievalQuery(...)) -> list[RetrievalResult]` | `retrieval/engine.py:38,82` |

Four facts that drive the design:

1. **Nothing in this repository writes a `.ndax` file.** `chunk` prints JSON to stdout (`app.py:1801-1806`); the documented workflow is `openreview chunk x.pdf --format json > x.ndax`. The TUI therefore needs no `.ndax` at all: it chunks in memory and hands the dicts straight to `ingest_document`, whose `_normalize_chunk` (`retrieval/ingest.py:137-161`) accepts exactly the `dataclasses.asdict(Chunk)` shape (verified by the reviewer, who ingested it).
2. **`stream_chunks` renders a Rich progress bar** (`chunking/stream.py:32-35`) that would write over the Textual display.
3. **Document identity is the caller's job.** Chunks carry no `document_id`; the CLI derives `chunks[0]["document_id"]` or `sha256(file bytes)` (`app.py:332-340`) and addresses the index as `{db_dir}/{doc_id[:32]}.db` (`app.py:2105`). `_resolve_doc_id` ends in `typer.Exit` (via `_load_ndax_chunks`, `app.py:320-328`), so the TUI must not call it.
4. **`index_meta`-only reads create the database file.** `RetrievalStorage.conn` is `sqlite3.connect(...)` (`retrieval/storage.py:26-28`) and `get_index_meta()` swallows the resulting `no such table` error (`:232-233`), so a status read on a never-indexed path leaves a 4096-byte `.db` behind. The CLI guards against this (`app.py:2450-2452`); the adapter must too.

## Design decisions

**D1. The flow lives on a `Screen`, not on a tab.** `RetrieveScreen(Screen)` in `src/openreview_cli/tui/screens/retrieve.py` owns the flow and the five `action_*` methods. A ~15-line `RetrieveTab(Static)` in `tabs/retrieve.py` (new tab id `retrieve`, key `7`) holds one button that pushes the screen, following the `ReviewTab` -> `ReviewWizard` pattern (`tui/tabs/review.py:35`).
**Why this is a blocker fix, not a preference:** `scripts/parity/inventory_tui.py:328-336` records a class only when it subclasses `App` or `Screen`; everything else is skipped. A `Tab` therefore contributes **zero** rows, the five commands would stay unmatched, and the goal's step 5 could not pass. Verified: the committed matrix contains no `*Tab` class at all except `_ImportModal(Screen)` under `tabs/`.

**D2. The five CLI commands map to five real action methods on that screen.** Four of them are driven by their own button and by Enter in the relevant input; `action_index_status` is the screen's refresh routine, called on mount and after every step, so it is a real action but deliberately has no user-facing control (Cycle 1 removed its button as redundant):
`action_chunk_document`, `action_ingest_document`, `action_retrieve`, `action_index_status`, `action_index_clear`.
Verified against the generator's own tokenizer: each shares a significant token with its command (`chunk`, `ingest`, `retrieve`, `index`+`statu`, `index`+`clear`), and none of those tokens is in `GENERIC_TOKENS`.

**D3. Search before ingest fails gracefully, in two layers, and the not-indexed state is normal rather than an error.**
Layer 1: `index_meta(db_path)` returns `None` immediately when `db_path` does not exist, and the screen refuses to search. This is the flow's normal first state, so it is written **persistently to `#retrieve-status`** - never only as a transient toast - using `Not indexed yet. Press Ingest to build the index.` No engine is constructed.
Layer 2: the engine can still raise on a file that exists but has no `index_meta` row (it raises `IndexNotFoundError`, `retrieval/engine.py:110-113`), or has status `ingesting`/`corrupt`. **Do not display the engine's own message.** Its copy is CLI copy that names a shell command which cannot fix the state: ``Document not indexed. Run `openreview ingest <file>` first.`` - and per D4 that command writes a *different* index and leaves this one untouched, so the screen would be telling the user to do something that visibly does nothing. Map by exception type to TUI copy instead:
- `IndexNotFoundError`, no `index_meta` row -> `Not indexed yet. Press Ingest to build the index.`
- `IndexCorruptError` (stored status `corrupt`) -> `This document's index is damaged. Press Clear index, then Ingest to rebuild it.`
- `IndexNotFoundError` for status `ingesting` (an interrupted build) -> `An earlier Ingest was interrupted. Press Ingest to rebuild the index.` This case must **not** be relabelled "corrupt": nothing is damaged, and D7 already rebuilds it.
No traceback, ever. This is an acceptance criterion.

**D4. Identity is `sha256` of the source file's bytes**, passed explicitly as `document_id=` to `ingest_document`, and recomputed identically for status, search and clear: one index per source document, and every step agrees which one. Consequences to document, not hide (T7):
- The CLI addresses an index by the hash of the `.ndax`, so it will not address the same file for the same source document. A bare `openreview retrieve "<query>"` *will* still find the TUI's index, because `last_indexed.json` records it (`retrieval/ingest.py:309`), but `openreview index-clear <pdf>` **cannot** remove a TUI-created index by source path (it re-parses its argument as `.ndax`, `app.py:2515`).
- Editing a document after ingest changes its hash: the old index becomes unreachable from the TUI (the TUI only addresses the current hash) and is only removable by hand.

**D5. `sparse` only in v1.** `method="sparse"` is a first-class supported mode (`retrieval/engine.py:143`) that needs no gateway, no Ollama, no network and no API key. The reasons that matter: a live Ollama server plus one embedding round-trip per chunk, on a machine with no GPU; and the CLI's own `ingest` already degrades to sparse when embeddings are unavailable (`retrieval/ingest.py:270-282`). **Deferred, with the reason recorded:** `hybrid`/`dense`, and the whole `--rerank*` family.

**D6. Confirmation before clear, and it names what it destroys.** `ConfirmModal(..., danger=True)` (existing, `tui/screens/confirm.py:25`), already focusing "No" on mount (`:50-58`). `ConfirmModal` is 40 columns wide with 1-2 padding, so the copy is composed to fit roughly 36 usable columns. Pinned exactly:
- title: `Clear index`
- message: `Clear the index for {filename}?\n\n{chunk_count} chunks are indexed for this document.\n\nThe source file is not touched. Ingesting it again rebuilds this index.`

**D7. Ingest is a no-op when already indexed, exactly like the CLI.** If `index_meta.index_status == "indexed"`, write `Already indexed ({chunks} chunks). Clear index first to rebuild.` to `#retrieve-status` and do not rebuild. This is data-loss handling, not politeness: `ingest_document` calls `clear_index(db_path)` on **every** call (`retrieval/ingest.py:199-201`), so a reflexive second Ingest destroys a good index. Mirrors `app.py:2107-2121`. Rebuilding deliberately = Clear (confirmed) then Ingest, and the already-indexed message says so.

**D8. Nothing fires while something is in flight.** **Why this is a fix, not polish:** two concurrent `ingest_document` calls on one `db_path` were measured to produce `DatabaseError: database disk image is malformed` - an index that neither search nor a metadata read can open. A double press of Ingest is enough, because `ingest_document` deletes the database before rebuilding. `chunking/stream.py:25`'s `reset_chunk_counter()` is also process-global, so two concurrent chunk runs would interleave chunk ids.

Four invariants, all required:
1. `self._busy` is set **synchronously, before the first `await`** in every action. A flag set after an `await` lets a second handler read `False` in the same event-loop turn.
2. The flag gates **all five actions and `on_input_submitted`**. Disabling buttons is not enough: `#retrieve-path` and `#retrieve-query` stay live and reachable by Enter, and a `disabled` button is unpressable anyway (Textual's own `Button.press()` returns early, `_button.py:429`), so the disabled state is a visible signal for the user rather than the guard itself.
3. `#btn-back` is disabled while busy too. `asyncio.to_thread` cannot be cancelled, so leaving the screen mid-parse lets the worker resume against an unmounted screen (`query_one` -> `NoMatches`).
4. The adapter additionally takes a module-level `threading.Lock` around `ingest_chunks` and `clear_index`. Work already runs on a worker thread, so a threading lock is the right primitive, and it makes the corruption impossible for any caller rather than only for callers that remember the flag.

`self._busy` is per-screen-instance, which is sufficient here because the screen covers its launcher.

**D9. Long work never runs on the UI thread, and v1 promises a busy state, not a progress bar.** `await asyncio.to_thread(...)` inside the action keeps the app painting; there is no task bookkeeping, because nothing in this flow can be cancelled. Two reasons not to promise progress: parsing dominates and has **no progress hook at all** (measured: 2.72 s cold for the one-page fixture, versus 0.21 s for the chunking that does report progress), and a large ingest is fast (5001 chunks in 2.4 s sparse). `progress_callback` is left unwired.
But the busy state must be *visible*, using the glyph vocabulary `DESIGN.md` already defines and `ProgressScreen` already renders. Every step writes its own line to `#retrieve-status`:
- `● Chunking {filename}...` then `✓ Chunked {filename} - {clauses} clauses, {chunks} chunks.`
- `● Ingesting {chunks} chunks...` then `✓ Indexed {filename} - {chunks} chunks.`
- `● Searching...` then the result line from D3's sibling rule below.
Without these, a user watching four disabled buttons for two multi-second stretches cannot tell working from hung.

**D10. Display-only CLI options are deliberately not built.** `chunk --format/--summary`, `retrieve --format json`, `retrieve --no-header`, `retrieve --force-rerank`, `--model`, `--db-dir` (the default index directory is used), `--method`, `retrieve`'s "omit FILE to use the last indexed document" (the screen always has a selected document), and `index-clear --all`. `top_k`: no widget; read `retrieval.top_k` from config the way the CLI does (`app.py:2289-2290`) so the two surfaces cannot disagree.
The status line shows **`Status` and `Chunks` only**. `method` and `embedding_model` are omitted: under D5 they can never vary (`method` is always `"sparse"` and `embedding_model` is always NULL), and rendering a constant as data is noise. The fact they are constant is stated **once**, as a subtitle in `#retrieve-header`: `sparse index - no embeddings, no network`. No DB-size display either: the CLI's own number is stale by construction (it prints `index_meta.db_size_bytes`, committed before the final update, measured 49x under the real file).
Because nothing states the result cut otherwise, a successful search reports it: `Showing top {top_k} matches for "{query}".`

**D11. Keyboard: buttons, `Input.Submitted`, Escape to go back, and no single-letter bindings.** Single-letter widget bindings are dead while a focused `Input` consumes printable keys (`textual/widgets/_input.py:743-754`), and the reference list-plus-actions pattern (`tui/tabs/clients.py`, `tui/tabs/prompts.py`) declares no bindings at all. Typing a path and pressing Enter runs Chunk; typing a query and pressing Enter runs Search (`on_input_submitted`, as in `tui/screens/amber_queue.py:90`); everything else is a button.
**Escape is required, not optional.** Verified against the installed Textual 8.2.8: `Screen.BINDINGS` carries only `tab`, `shift+tab` and `ctrl+c` (`textual/screen.py:269-273`), and `Input` does not bind Escape, so the key is free. Every peer screen binds it (`pii_data.py`, `result.py`, `amber_queue.py`, `review_wizard.py`). Without it the user must Shift-Tab past the destructive control or reach for the mouse. Add `Binding("escape", "go_back", "Back")`, and gate **that one binding** with `check_action` returning `False` while `_busy` (D8 invariant 3 - an uncancellable thread must not resume against an unmounted screen). Cycle 1's "no `check_action` needed" reasoning was circular: it was redundant only because there were no bindings.

**Order and labels.** Compose order fixes Tab order, so it is: `#retrieve-header`, `#retrieve-path`, the Chunk/Ingest buttons, `#retrieve-status`, `#retrieve-query`, the Search button, `#retrieve-results`, then a docked bottom action bar holding Clear index and Back - the shape of `#pii-actions` and `#result-nav`. The destructive control comes last and carries `variant="error"` (as `btn-delete-pii` does), so Tab cannot walk a user into Clear on the way to the search box. `#retrieve-path` takes focus in `on_mount`. Labels: `Chunk`, `Ingest`, `Search`, `Clear index`, `Back (Esc)`.

**Markup is off everywhere text is rendered.** Every `Label`/`Static`/`ListItem` that shows a path, a filename, a query or contract text passes `markup=False` - `DESIGN.md`'s first rule, and load-bearing here: contract text contains `[Party A]`-style brackets that Rich style parsing would consume, and the test fixture is a real NDA. This applies to `#retrieve-header`, `#retrieve-status`, every result row, and the empty and no-match rows.

**D12. Honest documentation of the parity result.** The matrix's `CERTAIN` verdict is a name join; the generator says so itself (`scripts/parity/build_parity_matrix.py:1263-1271`). Here the names correspond to real implementations, which is the strongest thing that generator can express, and T7 states that plainly instead of implying the matrix proves behaviour. The plan does **not** modify the parity tooling to chase a verdict.

**D13. Testing split.** Fast unit tests for the domain adapter (no Textual, no `slow` marker, no `run_test` cost). Two TUI test files, one concern each, each run in isolation. One of them is a real end-to-end assertion, not a render check.

**D14. The flow has one persistent voice, and every state's words are pinned here.** The screen does not rely on the user inferring the sequence: `#retrieve-header` states what the screen is for, and `#retrieve-status` always states what is true now and what to press next, rewritten after every step. All seven states, exactly:

| State | `#retrieve-status` |
|---|---|
| First run, nothing selected | `No document selected. Enter a path above, then Chunk and Ingest before searching.` |
| Chunked | `Chunked {filename} - {clauses} clauses, {chunks} chunks. Press Ingest to index it.` |
| Busy | the `●` lines from D9 |
| Indexed | `Indexed {filename} - {chunks} chunks. Enter a phrase below to search.` |
| Not indexed (search attempted) | `Not indexed yet. Press Ingest to build the index.` |
| Search returned nothing | `No matches for "{query}" in {filename}.` |
| Error | the mapped copy from D3 and T3 Step 3 |

The results list is **cleared at the start of every search**, so a query with no matches can never leave the previous query's rows on screen - and on zero rows the list itself also holds a single `No matches for "{query}".` row, so the pane is never silently blank (`SearchScreen` does both).
Result rows are `{rank}. [{heading chain}] · {score:.2f} · {first ~60 chars of the chunk}`, with `markup=False`. Empty and no-match rows use the same treatment.
`#retrieve-header` is bold on `$primary` with `padding: 1 2`, matching `#pii-header`, `#result-header` and `#step-indicator`, and carries the D10 subtitle.
The tab, not just the screen, says what it is for: `RetrieveTab` renders `Search inside a document` and `Chunk and index a contract, then search its text.` above its one button, so the capability is discoverable before it is opened.

## Files

- Create: `src/openreview_cli/tui/domain/retrieval.py` - the adapter: identity, chunk, ingest, status, search. No Textual import, so it is unit-testable.
- Create: `src/openreview_cli/tui/screens/retrieve.py` - `RetrieveScreen`: the guided flow.
- Create: `src/openreview_cli/tui/tabs/retrieve.py` - `RetrieveTab`: the launcher.
- Modify: `src/openreview_cli/tui/app.py` - register the tab (compose, `TabPane`, `BINDINGS` key `7`).
- Modify: `src/openreview_cli/chunking/stream.py` - add `show_progress`.
- Create: `tests/unit/tui/test_retrieval_domain.py`.
- Create: `tests/integration/tui/test_retrieve_screen.py`, `tests/integration/tui/test_retrieve_flow_e2e.py`.
- Modify: `docs/ARCHITECTURE.md`, `docs/cli-tui-parity-matrix.md` (regenerated by script).

## Tasks

### Task 1: Chunking must be callable without a Rich progress bar

**Files:**
- Modify: `src/openreview_cli/chunking/stream.py` (`stream_chunks`, :13-52)
- Test: `tests/unit/test_chunking_stream.py`

**Interfaces:**
- Produces: `stream_chunks(clauses, config=None, *, show_progress: bool = True) -> Iterator[Chunk]`. Identical yield order and content either way; the default is today's behaviour, so the CLI is unchanged.

- [x] **Step 1: Write the failing test.** Assert three things: calling it with `show_progress=False` writes **nothing** to stdout or stderr (`capsys`); the chunks it yields are identical to the default path for the same input; and the default path still enters the progress context. For the third, monkeypatch `chunking.stream.Progress` with a recorder and assert it was constructed with `show_progress=True` and never with `False`. Do **not** assert on printed progress text: measured, with stdout not a tty Rich's transient bar emits only `"\n"`, so such an assertion would be environment-dependent and brittle - but without the recorder, a refactor that returns the inner generator from inside the `with` block would pass the silence test while silently killing the CLI's bar.
- [x] **Step 2: Run it and confirm it fails** with `TypeError: stream_chunks() got an unexpected keyword argument 'show_progress'`.
- [x] **Step 3: Implement** by extracting the existing loop into a private generator and entering `with Progress(transient=True)` around it only when `show_progress` is true.
- [x] **Step 4: Run** `uv run pytest tests/unit/test_chunking_stream.py tests/unit/test_chunking_splitter.py -q`, then confirm the CLI is untouched: `uv run openreview chunk tests/fixtures/nda_with_pii.pdf --summary`.
- [x] **Step 5: Commit** `refactor(chunking): let callers suppress the progress bar`.

### Task 2: The retrieval domain adapter

**Files:**
- Create: `src/openreview_cli/tui/domain/retrieval.py`
- Test: `tests/unit/tui/test_retrieval_domain.py`

**Interfaces (consumed by T3-T6):**
- `resolve_document(path: Path, *, db_dir: Path | None = None) -> tuple[str, Path]` - validates and raises (see the contract below), returns `(document_id, db_path)` where `document_id = sha256(path.read_bytes()).hexdigest()` and `db_path = (db_dir or _ensure_db_dir(None)) / f"{document_id[:32]}.db"`.
- `chunk_document(path: Path) -> list[dict[str, Any]]` - `parse_document(path, allow_password_prompt=False)` then `stream_chunks(clauses, ChunkConfig(), show_progress=False)`, returned as `dataclasses.asdict(chunk)` per chunk. May raise `ParseError`/`OSError`; the caller catches them.
- `index_meta(db_path: Path) -> dict[str, Any] | None` - **`if not db_path.exists(): return None` first**, then `RetrievalEngine(db_path).get_index_meta()`. The guard is mandatory (fact 4).
- `ingest_chunks(chunks, db_path, *, document_id: str) -> dict[str, Any]` - `ingest_document(..., method="sparse", document_id=document_id)`.
- `search(db_path: Path, query: str, *, top_k: int | None = None) -> list[RetrievalResult]` - `RetrievalEngine(db_path).retrieve(RetrievalQuery(query_text=query, method="sparse", top_k=top_k or _configured_top_k()))`. Raises `IndexNotFoundError`/`IndexCorruptError` unchanged. **The field is `query_text`, not `query`** (`retrieval/models.py`), and `_configured_top_k()` reads the same `retrieval.top_k` key the CLI reads (`app.py:2289-2290`) via `load_config()` directly - **not** via `openreview_cli.app`, which `tui/` has never imported and which would drag the whole CLI module into the TUI's import graph.
- A module-level `threading.Lock` guards `ingest_chunks` and `clear_index` (D8 invariant 4).

Five functions, no more: no `human_size` (no size display, D10), no `is_indexed` (one code path; the screen reads the meta it already has), no notices return (always empty under sparse), no `clear() -> bool` wrapper (the screen calls `clear_index` and re-reads status).

- [ ] **Step 1: Write the failing tests** under `isolated_xdg`, always passing `db_dir` explicitly: identity is stable, 64 hex chars, and differs when the bytes differ; chunking the fixture yields at least one dict carrying every key `_normalize_chunk` reads (`id`, `text`, `source_clause_title`, `source_clause_level`, `char_offset_start`, `char_offset_end`, `parent_chunk_id`, `structural_location`); `index_meta` returns `None` for a path that does not exist **and creates no file** (assert the directory listing is unchanged - this is the regression guard for fact 4); a missing document raises `FileNotFoundError` and a directory raises before parsing; after `ingest_chunks` the meta says `indexed` with the right chunk count; `search` on an un-indexed path raises `IndexNotFoundError`; `search` after ingest returns results for a phrase in the document.
- [ ] **Step 2: Run and confirm they fail** (module does not exist).
- [ ] **Step 3: Implement the adapter.** No logic of its own beyond identity and the adapters above. No `openreview_cli.gateway.router` import; no Textual import.
- [ ] **Step 4: Run** `uv run pytest tests/unit/tui/test_retrieval_domain.py -q`.
- [ ] **Step 5: Commit** `feat(tui): add a retrieval domain adapter for the TUI`.

### Task 3: The guided screen

**Files:**
- Create: `src/openreview_cli/tui/screens/retrieve.py`
- Create: `src/openreview_cli/tui/tabs/retrieve.py`
- Modify: `src/openreview_cli/tui/app.py` (compose, `BINDINGS`, `TabPane`)
- Test: `tests/integration/tui/test_retrieve_screen.py`

**Interfaces:**
- Consumes: every function from T2.
- Produces: `RetrieveScreen(Screen)` with widgets `#retrieve-header` (Static, bold on `$primary`, subtitle per D10), `#retrieve-path` (Input), `#btn-chunk`, `#btn-ingest`, `#retrieve-status` (Static), `#retrieve-query` (Input), `#btn-search`, `#retrieve-results` (ListView), and a docked bottom bar with `#btn-clear` (`variant="error"`) and `#btn-back`. Compose order, labels, focus and the `escape` binding are pinned in D11; the seven states and their exact copy are pinned in D14; every text widget passes `markup=False`. Actions: `action_chunk_document`, `action_ingest_document`, `action_retrieve`, `action_index_status`, `action_index_clear`, plus `action_go_back`. `RetrieveTab(Static)` with a title, a one-line description and `#btn-open-retrieve`.

- [ ] **Step 1: Write the failing tests.** The tab renders its title and description and pushes the screen; the screen mounts with `#retrieve-path` focused and `#retrieve-status` showing the first-run string from D14; entering the fixture path and submitting `#retrieve-path` chunks it and writes the chunked string from D14; pressing Search un-indexed writes `Not indexed yet. Press Ingest to build the index.` to `#retrieve-status` (persistently, not only as a notification) with `pilot.app._exception is None`; a search that matches nothing writes the no-match string and leaves **no** rows from a previous query on screen; `escape` pops the screen; each of a directory, a missing path, a zero-byte file and a password-protected PDF produces a notification and leaves the screen mounted with `pilot.app._exception is None`; a second Ingest submitted while the first is in flight is ignored (D8); and a result row whose chunk text contains `[Party A]` renders those eight characters verbatim rather than swallowing them as markup.
  **`#btn-search` and `#btn-ingest` stay enabled in the not-indexed state.** An earlier draft disabled Search until indexed, which would have made this test - and T5's and T6's not-indexed cases - unexecutable, because a disabled button cannot be pressed; the graceful message is the required behaviour, so it must be reachable. Buttons are disabled only while `_busy`.
- [ ] **Step 2: Run and confirm they fail.**
- [ ] **Step 3: Implement the screen.** Follow the existing list-plus-actions pattern (`tui/tabs/clients.py`, `tui/screens/pii_data.py`): one `_set_busy` helper drives D8 and the button `disabled` states; `self._meta` holds the last status read and is refreshed by `action_index_status` after every step; all rendered text passes `markup=False`.
  **The index-state copy is chosen from `self._meta`, not from an exception message.** One helper, `_index_state_message(meta) -> str | None`, returns D3's three strings by inspecting the stored state (`None`/no row -> not indexed; `"ingesting"` -> interrupted; `"corrupt"` -> damaged) and `None` when the index is usable. The screen calls it before constructing the engine (D3 layer 1) and again in the `except` for `IndexNotFoundError`/`IndexCorruptError` (layer 2, for the race where the state changed underneath), so both layers speak with one voice and the engine's CLI copy never reaches a user.
  **Never read `.message` on those two exceptions:** they are bare `Exception` subclasses (`retrieval/errors.py:13,20`) with no such attribute, so reading one raises `AttributeError` from inside the except block and escapes to `_handle_exception` - the exact failure this mapping exists to prevent. The mapping is by type and by `self._meta`, never by message text. `ParseError` does guarantee `.message` and `.action` (`parsing/models.py:107-110` rejects empty values).
  **The file-error copy is specific and leaks no errno:** `FileNotFoundError` -> `No file found at {path}.`; `IsADirectoryError` -> `That is a directory, not a file.`; `PermissionError` -> `Permission denied reading {path}.`; any other `OSError` -> `Could not read {path}.` A raw `[Errno 2] No such file or directory: '/tmp/x.pdf'` is worse than the CLI's own wording for the same condition, and must not appear.
  **`ParseError` goes to both channels.** Its text is written to `#retrieve-status` (persistent, so the user can read it while fixing the input) and notified. For the password case specifically, append the fact that the environment variable is read when the document is parsed, so the fix takes effect after restarting the app - the parser's own `action` text (`parsing/pdf_parser.py:123-129`) does not say that, and the TUI has no password prompt at all.
  **The catch-all does not print a Python class name.** Any other exception is logged with its traceback (`logger.exception`) and notified as `Unexpected error: {e}`; the branch that catches what nobody anticipated is not the least designed one.
  **This error mapping is an acceptance requirement, not polish:** unhandled, a `ParseError` raised inside an `await asyncio.to_thread(...)` in an action handler reaches `app._handle_exception`, whose documented behaviour is app exit with a traceback (`textual/app.py:3263-3283`).
- [ ] **Step 4: Run** `uv run pytest tests/integration/tui/test_retrieve_screen.py -v` (isolated file).
- [ ] **Step 5: Commit** `feat(tui): add the guided retrieve screen`.

### Task 4: End to end - chunk, ingest and search a real document

**Files:**
- Test: `tests/integration/tui/test_retrieve_flow_e2e.py`

- [ ] **Step 1: Write the test** under `isolated_xdg`, driving the UI on `tests/fixtures/nda_with_pii.pdf`: submit the path, ingest, then submit a query containing a phrase that exists in the document; assert a result row appears whose text contains that phrase, that the top score is a float, that `#retrieve-status` carries the `Showing top {top_k} matches` line from D10, and that the index file exists on disk afterwards. Then press Ingest again and assert (a) `#retrieve-status` reads `Already indexed (` and names Clear as the rebuild route (D7), and (b) the on-disk file's mtime is unchanged - the direct proof of D7.
- [ ] **Step 2: Run and confirm it fails for the right reason** (no flow yet).
- [ ] **Step 3: Fix whatever the flow gets wrong.** This test is the acceptance criterion; adjust the flow until it passes honestly, and never relax the assertion to match buggy behaviour.
- [ ] **Step 4: Run** `uv run pytest tests/integration/tui/test_retrieve_flow_e2e.py -v`.
- [ ] **Step 5: Commit** `test(tui): prove the chunk-ingest-search flow end to end`.

### Task 5: Un-indexed, interrupted and corrupt indexes

**Files:**
- Test: `tests/integration/tui/test_retrieve_screen.py` (same file as T3; one file per screen, per `tests/integration/tui/README.md`)
- Modify: `src/openreview_cli/tui/screens/retrieve.py` if a gap is found.

- [ ] **Step 1: Write the tests.** Searching a never-indexed document shows the not-indexed message and raises nothing; searching a document whose `.db` exists with **no `index_meta` row** shows the not-indexed message too (the engine raises `IndexNotFoundError` there, `retrieval/engine.py:110-113` - **not** the corrupt one; an earlier draft asserted corrupt, which would have had the implementer change production code to match a wrong test); searching one whose stored status is `corrupt` shows the corrupt message; searching one whose status is `ingesting` (an interrupted build) shows the engine's interrupted message, **not** "corrupt"; searching after Clear shows the not-indexed message again; in every case the screen is still mounted and `pilot.app._exception is None`.
- [ ] **Step 2: Run and confirm they fail or expose a gap.**
- [ ] **Step 3: Close the gap** (D3's second layer, with the `ingesting` branch).
- [ ] **Step 4: Run** the file.
- [ ] **Step 5: Commit** `test(tui): cover un-indexed, interrupted and corrupt index searches`.

### Task 6: Clear requires confirmation

**Files:**
- Test: `tests/integration/tui/test_retrieve_screen.py`
- Modify: `src/openreview_cli/tui/screens/retrieve.py`

- [ ] **Step 1: Write the tests.** After ingest, pressing Clear shows a modal naming the document, and the index still exists while it is open; clicking `#no` leaves the index in place; clicking `#yes` removes it, the status line reads not-indexed, and a subsequent Search reports not-indexed.
- [ ] **Step 2: Run and confirm they fail.**
- [ ] **Step 3: Implement** the `ConfirmModal(..., danger=True)` call per D6, using the existing `clear_index` (`retrieval/ingest.py:29`) with no change to it. (Cycle 1 cut the `-wal`/`-shm` unlink: a reviewer measured that a clean close leaves no sidecars, that they survive only an unclean kill, and that a stale `-wal` does not resurrect data on SQLite 3.45.1. Recorded as its own follow-up, not built here.)
- [ ] **Step 4: Run** the file plus `uv run pytest tests/integration/test_retrieval_index.py -q`.
- [ ] **Step 5: Commit** `feat(tui): require confirmation before clearing an index`.

### Task 7: Documentation and the parity matrix

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/cli-tui-parity-matrix.md` (regenerate, never hand-edit)

- [ ] **Step 1:** Add a TUI section to `docs/ARCHITECTURE.md`: the flow and its order; sparse-only and why; the identity rule and its three consequences from D4 (including that the CLI cannot clear a TUI-created index by source path); the deliberate omissions (D10); and the fact that an edited document orphans its old index.
- [ ] **Step 2:** Record the `index-clear --all` discrepancy found during review: `app.py:2486-2488` advertises "requires confirmation" and `specs/016-hierarchical-retrieval/contracts/cli.md:187` says "prompt required", but `app.py:2496-2504` clears every index immediately with no prompt (contrast `playbook delete --all`, which does confirm, `app.py:1040-1048`). The regenerated matrix will quote that help text, so the discrepancy must be stated in the docs rather than silently reproduced. The CLI fix is **out of scope for this plan** and is reported to the user as a separate item.
- [ ] **Step 3:** Run `uv run python scripts/parity/build_parity_matrix.py` and confirm the five commands (`chunk`, `ingest`, `retrieve`, `index-status`, `index-clear`) now appear as matched in Table C, quoting the rows.
- [ ] **Step 4:** State in the docs that the match is a name join (quoting `build_parity_matrix.py:1263-1271`) that here corresponds to real action methods, so the matrix provisionally strengthens D2 while proving nothing about behaviour.
- [ ] **Step 5:** Commit `docs: document the TUI search workflow and regenerate the parity matrix`.

## Self-review against the goal

| Goal requirement | Task |
|---|---|
| Chunk, ingest and search a real document through the TUI | T2, T3, T4 |
| A guided order, not five disconnected buttons | T3 (D1, D2) |
| A way to see whether a document is already indexed | T2 `index_meta` + existence guard, T3 status line, T4 second-ingest assertion |
| Clear requires confirmation | T6 |
| Searching an un-indexed document fails gracefully | T3, T5 (D3) |
| Reuse `retrieval/ingest.py` and `retrieval/engine.py`, no reimplementation | T2 (adapter only), D10 |
| Full suite passes with no new failures | T8 below |
| The five commands show as matched in the regenerated matrix | T7 (D1, D2, D12) |

### Task 8: Verification (separate agent, no part in building)

- [ ] Full suite: the CI jobs via a draft PR; locally only the tests not covered by CI plus the new files.
- [ ] An agent that built none of this reproduces: real chunk -> ingest -> search from the UI; the un-indexed path; the confirmed Clear; and confirms no pre-existing test regressed.

## Cycle-1 record: what the reviews changed

**Adopted (both reviewers agreed):**
1. The flow moved from a `Tab` to a `Screen` (D1) - otherwise the goal's step-5 criterion is unreachable.
2. `index_meta` must check `db_path.exists()` first (fact 4) - otherwise a status read fabricates an index and turns a later Search into a bogus "corrupt" report.
3. A busy guard on all actions (D8) - measured data corruption from a double press.
4. Catch `ParseError`/`OSError` at the screen (T3 Step 3) - otherwise a password-protected PDF, a directory or a zero-byte file exits the whole app.
5. Distinguish `ingesting` from `corrupt` (T5).
6. Cut: `human_size`, `is_indexed`, the notices return, the `config` parameter, `clear() -> bool`, all single-letter bindings, `check_action`, the separate Index-status button, the `clear_index` sidecar change, the separate un-indexed test file, and the task bookkeeping.
7. `isolated_xdg` mandatory in every TUI test, and `db_dir` threaded through the adapter.
8. No progress-bar promise; parse dominates and has no hook (D9).
9. T1's test asserts silence, not progress text (measured: not a tty emits only `"\n"`).
10. Corrected factual errors in the plan itself: the stale litellm import chain, `clear_index`'s return type, the `ingesting` exception type, two line-number citations, the missing `T8`, and `human_size` being a copy rather than an existing callable.

## Cycle-2 record: the corrections the second review forced

Both reviewers re-read the revised plan. Ponytail **approved** and withdrew its objection to the tab; Caveman **withheld approval on one line**, and supplied these corrections, all now applied above:

1. **T5 asserted the wrong exception** (Caveman's blocker). A `.db` that exists with no `index_meta` row raises `IndexNotFoundError`, not `IndexCorruptError`, and Step 3 would have instructed the implementer to change production code to satisfy the wrong expectation. T5 now expects the not-indexed message for that case, and only `index_status='corrupt'` produces the corrupt message.
2. **`RetrievalQuery(query=...)` would have raised `TypeError`** (Ponytail). The field is `query_text`.
3. **A disabled Search button made three tests unexecutable** (Ponytail). `#btn-search` and `#btn-ingest` stay enabled; the graceful message is the behaviour under test.
4. **The busy flag alone did not cover the inputs** (Caveman). `#retrieve-path` and `#retrieve-query` stay live and reachable by Enter, so the flag must gate `on_input_submitted`, must be set before the first `await`, must disable `#btn-back` (an uncancellable thread resuming against an unmounted screen), and is now backed by a `threading.Lock` in the adapter so the guarantee does not depend on any caller.
5. **`e.message` on the retrieval errors would have raised `AttributeError` from inside the except block** (Caveman) - the one place a mistake re-creates the crash the mapping exists to prevent. Use `str(e)`.
6. **T1's test needed a recorder** (Caveman): asserting silence alone would pass a refactor that kills the CLI's progress bar.
7. **`top_k` must not be read through `openreview_cli.app`** (Caveman): that would be the first `tui -> app` import in the repo. Read `load_config()` directly, as `tui/domain/privacy.py:23` already does.
8. **D2's wording was wrong** (Caveman): `action_index_status` has no button, by Cycle-1's own cut.

## Cycle-3 record: the impeccable review

A third review, with the `impeccable` skill, was run after Cycles 1-2 at the user's request. It found what the first two reviews were structurally unable to see: the plan was a correct engineering document that was **largely silent about the interface it produced**. It pinned nine widget ids and zero user-visible strings, so the goal's own first requirement - a guided flow rather than five disconnected buttons - was claimed in the self-review and delivered by nothing in the tasks. Findings, all now applied:

1. **No state, no guidance.** Added `#retrieve-header` and made `#retrieve-status` the flow's single persistent voice, with all seven states and their exact copy pinned in D14.
2. **No first-run state anywhere.** Pinned the tab's title and description, the screen's first-run string, and both input placeholders.
3. **The results region could lie or go blank.** The list is now cleared at the start of every search (so a no-match query cannot leave the previous query's rows on screen), zero rows write a no-match string *and* a no-match row, and a successful search discloses its `top_k` cut.
4. **Focus order put Clear and Back before the query box.** Compose order is pinned in D11, Clear is last in a docked action bar with `variant="error"`, and `#retrieve-path` takes focus on mount.
5. **Escape-to-back was missing.** `Screen.BINDINGS` has no `escape`, so the key was free and unused while every peer screen binds it. Added `Binding("escape", "go_back", "Back")` with `check_action` gating it while `_busy` - which also makes Cycle 1's "no `check_action` needed" reasoning explicitly circular, since it was only true while there were no bindings.
6. **The not-indexed state was an error toast.** It is the flow's *normal* first state, so it now goes to `#retrieve-status` persistently, and its verb was fixed from "Run Ingest" (a shell verb) to "Press Ingest" (the control that exists).
7. **Layer 2 displayed CLI copy that cannot fix the state.** The engine's messages name `openreview ingest <file>`, and per D4 that command writes a *different* index, so following it visibly does nothing. Copy is now chosen from `self._meta` and the exception type, never from the engine's message.
8. **The busy state was a greyed button and the promised counts line was never written.** Both `●`/`✓` strings are pinned in D9.
9. **Two of the status line's four fields could not vary.** `method` and `embedding_model` are constants under D5, so they moved out of the per-document line into one header subtitle.
10. **`markup=False` appeared nowhere.** Made explicit for every text widget, with a test that `[Party A]` survives rendering.
11. **The confirmation's copy was unspecified** for a modal only 36 columns wide. Title and message pinned in D6.

Its verdict was **NEEDS WORK**, and its "one change that matters most" was the persistent voice in items 1/2/3/6/8/9 - which is D14.

**Logged disagreements (resolved, not hidden):**
- **The Retrieve tab itself.** Ponytail's final cut was to drop the new tab and put the launcher on Home, on the grounds that no criterion requires a tab. **Kept**: the app exposes peer capabilities as tabs (Review, Clients, Playbooks, Settings, Prompts), the goal asks for a discoverable guided flow rather than a hidden one, and the cost is a `TabPane` plus a key binding. The reviewers' substantive point - that the flow must not live *on* the tab - is adopted in full.
- **`top_k`.** Ponytail offered "read config, or hardcode 5 and document it". **Chose reading config**, so the TUI and CLI cannot disagree about a number the user already configured.
