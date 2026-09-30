# Graph build tree — TUI design (one screen that builds a contract graph and shows it)

**Scope:** the new TUI screen that builds one contract's clause graph and displays it as a foldable
tree. Files: new `src/openreview_cli/tui/screens/graph_build.py`; extended
`src/openreview_cli/tui/domain/graph.py`; reach added in `src/openreview_cli/tui/screens/result.py`
and `src/openreview_cli/tui/screens/retrieve.py`; one **conditional** extraction in
`src/openreview_cli/graph/view.py`.

**Base:** worktree `035-post-measurement-cleanup`, branch `feat/035-post-measurement-cleanup`
at `c49ee21` (the `feat/slm-measurement` head).

**Status:** design only — nothing implemented. Master plan §5 (Phase 2) is the source; this doc is
the per-item sub-plan §0 promises, written in Phase 0 as the approved plan requires. Per the
plan's own caveat, re-check the reach bindings at the start of Phase 2 if Phase 1 changed
`tui/screens/retrieve.py`.

**Deliverable:** one screen, one domain change, one conditional refactor, one test file (§8).

Every `file:line` below was verified against the worktree sources on 2026-09-30; §9 lists what was
taken from the master plan rather than re-read, and what could not be verified.

---

## 1. The job

| | |
|---|---|
| **Job** | See *this contract's clause structure* — the hierarchy, what references what, what defines what — without leaving the TUI and without a prior `openreview parse --format json` step. |
| **Who** | The operator already inside the TUI: they just finished a review (`ResultScreen`) or are searching a document (`RetrieveScreen`). |
| **Mode** | **Operate** (DESIGN.md's instrument vocabulary: the screen does work and reports a result; it is not a triage/decide surface). |
| **What success looks like** | Press the key; the screen names the file and its node/edge counts, then in one worker round-trip shows a foldable tree whose node labels carry the same annotations the CLI's `graph view` prints. Nothing is written to disk. Escape returns. A flat document says so instead of looking broken. |

The gap this closes is measured, not assumed: the TUI has **no** `graph build` and **no**
`graph view` today. `render_tree` (`graph/view.py:6`) has exactly one caller — the CLI at
`app.py:3060-3062` — and nothing under `tui/` imports it. The only TUI graph surface is the
read-only metrics screen. `docs/cli-tui-parity-matrix.md` marks those two commands "CERTAIN", but
that verdict is a shared-name-token join and the generator says so itself; it is not evidence of
coverage (record W11).

---

## 2. Shape decisions already made with the user (recorded, not re-litigated)

| # | Decision | Why / source |
|---|---|---|
| G1 | **One screen** that builds *and* shows the tree. Not two screens, not a build-then-view flow. | User decision, 2026-09-30; master plan §5 T2.4. |
| G2 | The document is **parsed in-process** by the TUI. No `parsed.json` requirement. | The CLI's `graph build` takes a parsed-JSON file (`app.py:2719-2756`, `builder.py:160-172`); the TUI already has the path and the parser. |
| G3 | **No file is written unless the user presses the save key.** | Master plan §5 T2.4; asserted in §8. |
| G4 | Reachable from **both** `ResultScreen` and `RetrieveScreen`. | Master plan §5 T2.4. |
| G5 | The tree is a **foldable widget** (Textual `Tree`), not plain text. | Master plan §5 T2.4; `Tree` is in the pinned `textual>=8.2.8` (`pyproject.toml:30`), verified importable — no new dependency. |
| G6 | **No second parse+build path**: the graph is exposed from the existing TUI domain helper. | Master plan §5 T2.3 + §12 (ponytail). |
| G7 | The annotations helper (`compute_annotations`) is extracted **only if it ends up with two callers**. | Master plan §5 T2.2 + §12. §6 states the condition and the fallback. |
| G8 | Folding this into the existing read-only metrics screen was **considered and rejected**. | Master plan §5 T2.4 + §12. Reason recorded in §7. |

Keys are `(Esc)` and `(S)`, in parentheses, never square brackets (`DESIGN.md:167`, `:193`).

---

## 3. What already exists (the reuse map)

| Need | Reuse | Where (verified) |
|---|---|---|
| Parse + build one graph, in-process | `graph_summary_via_tui(document_path)` — already parses and builds, then throws the graph away | `tui/domain/graph.py:43`, build at `:70-76`, return at `:78-85` |
| Metrics / health (not duplicated here) | `GraphSummaryScreen` | `tui/screens/graph.py:63-64` |
| Node/edge count text | the metrics screen's own subtitle form: `"{filename} · {n} nodes · {e} edges"` | `tui/screens/graph.py:139-143` |
| Busy/worker pattern | `RetrieveScreen`: `_busy`, `check_action`, `_set_busy`, `_set_status`, `_run_step` | `tui/screens/retrieve.py:404-443` |
| Parse-failure handling | `GraphSummaryScreen._load`'s three `except` branches (FileNotFoundError / ParseError / OSError), one line each | `tui/screens/graph.py:113-135` |
| Late-render guard + worker cancellation | `GraphSummaryScreen._show` (`is_running` guard) and `on_unmount` | `tui/screens/graph.py:155-175`, `:180-188` |
| Save format | `ContractGraph.to_file` / `to_json` — the CLI's own serializer | `graph/models.py:68-92`, `:130-131`; CLI writes via the same call at `app.py:2763` |
| Reach from results | `_document_path_for_active_report()` + `check_action` | `tui/screens/result.py:292-315`, `:326-335`; existing `g` action at `:317-324` |
| Annotation vocabulary | `[N refs out]`, `[DEF-REF: n]`, `[DEFINES: "term"]`, `[ORPHAN]` | `graph/view.py:49-66` |

---

## 4. Layout and interaction

**Widget tree (new screen `GraphBuildScreen(Screen[None])`):**

```
GraphBuildScreen                       padding: 1 2
├── Static  #graph-build-header        filename · N nodes · E edges   (bold on $primary)
├── Tree    #graph-tree                height: 1fr
├── Static  #graph-build-status        one line, one voice
└── Horizontal #graph-build-actions    dock: bottom; height: 3
    ├── Button("Save graph (S)", id="btn-graph-save", variant="primary")
    └── Button("Back (Esc)",     id="btn-graph-back")
```

CSS follows the metrics screen's shape (`tui/screens/graph.py:66-72`) with the content container on
`padding: 1 2` (`DESIGN.md:144`). The action bar takes the results screen's docked-bar form
(`result.py:47-48`: `dock: bottom; height: 3; align: center middle`).

**Header.** Exactly the metrics screen's subtitle string (`"{filename} · {n} nodes · {e} edges"`,
`graph.py:140-142`), so the two screens cannot disagree about a document's counts. The numbers come
from the built graph itself (`len(graph.nodes)`, `len(graph.edges)`), never recomputed.

**Tree.**
- `Tree(Text(root_label), id="graph-tree")`, one `TreeNode` per `GraphNode`, nested by
  `parent_child` edges — the same walk `render_tree` does (`graph/view.py:72-78`: roots from
  `graph.roots`, children from the adjacency's `parent_child` edges, with a `visited` set so a
  cycle cannot loop forever).
- A node with children is foldable: `node.add(child_label, expand=...)`; roots are added
  `expand=True` one level deep so the hierarchy is visible immediately, deeper subtrees collapsed.
- **Labels are Rich `Text` objects, not markup strings** — the Literal Text Rule's second form
  (`DESIGN.md:135`: "rendered with `markup=False` or wrapped in Rich `Text(...)` primitives"). The
  node label is `Text(f"{node.label}  {snippet}")`, where `snippet` is the same 60-character,
  newline-collapsed slice `render_tree` uses (`graph/view.py:46`) — the two renderers must truncate
  identically or they will disagree about what a node shows.
- Annotations (when G7's helper exists, or formatted locally otherwise) are appended as separate
  `Text` spans with explicit styles, never as `[bold]…[/bold]` markup. `[ORPHAN]` and
  `[DEF-REF: 1]` are not valid Rich tags, but `[N refs out]` and any bare `[...]` in contract text
  would be parsed by Rich if the label were a plain string — a test pins the brackets (§8).
- `Tree` has its own scrolling and folding; no wrapper `ScrollableContainer`.

**Keys and buttons.**

| Binding | Action | Label |
|---|---|---|
| `escape` | `go_back` → `self.app.pop_screen()` | `Back (Esc)` |
| `s` | `save_graph` | `Save graph (S)` |

Both parenthesised (`DESIGN.md:167`). The metrics screen binds only `escape`
(`graph.py:74-76`); `s` is free there and on this screen.

**Busy / worker — reuse, do not invent.** The screen carries the same four members as
`RetrieveScreen` (`retrieve.py:404-443`), with the same invariants:

1. `self._busy` is set **synchronously, before the first `await`** (the retrieve plan's D8
   invariant 1: a flag set after an `await` lets a second handler read `False` in the same
   event-loop turn).
2. `check_action` returns `False` for `go_back` **and** `save_graph` while `_busy`, so an
   uncancellable `asyncio.to_thread` cannot resume against an unmounted screen
   (`retrieve.py:404-406`).
3. `_set_busy(True/False)` disables both buttons (`retrieve.py:408-412`).
4. `on_unmount` cancels the in-flight task (`graph.py:180-188`) — mirroring
   `GraphSummaryScreen`, not `RetrieveScreen` (whose steps are `call_later`-driven).

**State glyphs** (`DESIGN.md:158`): `○` pending, `●` active, `✓` complete, `✗` failed. The load
writes `● Building the clause tree…` then a terminal line; a failure writes `✗` on the same line.

**Status line = one voice.** Never a bare silent grey bar: every state writes a full sentence that
says what is true now and what to press next (§5).

---

## 5. States and their exact copy

| State | Trigger | `#graph-build-header` | `#graph-build-status` |
|---|---|---|---|
| Working | on mount, path present | `filename` | `● Building the clause tree…` |
| Tree shown (hierarchical) | `parent_child` edges > 0 | `filename · N nodes · E edges` | `✓ Built N nodes, E edges. Press S to save, or Esc to go back.` |
| No hierarchy detected (flat) | nodes > 0, `parent_child` edges == 0 | `filename · N nodes · 0 edges` | `✓ Built N nodes, 0 edges. No clause hierarchy was detected in this document, so the clauses are shown as a flat list.` |
| Empty document | nodes == 0 | `filename · 0 nodes · 0 edges` | `No clauses detected in this document.` |
| Parse failure | `ParseError` / `FileNotFoundError` / `OSError` | `filename` | `✗ Could not read {filename}: {one-line reason}` |
| Save succeeded | `s` pressed, write ok | unchanged | `✓ Saved the clause graph to {path}.` |
| Save failed | write raised `OSError` | unchanged | `✗ Could not write {path}: {one-line reason}` |

**The flat case must be said plainly, not look broken.** The NDA fixture is unnumbered prose, so the
real parse yields 5 nodes and **0 edges** (`tests/integration/tui/test_graph_screen.py:59-70`), and
hierarchy edges only exist when `link_parent_ids` has found numbering levels
(`parsing/clause_detector.py:170-193`, called from `docx_parser.py:220`). The copy above says that
in the status line. Do **not** reuse the metrics screen's `_HIERARCHY_CAVEAT`
(`graph.py:45-50`): that paragraph explains the *health score* ("a defect-free flat document scores
100"), which this screen does not show. Different screen, different sentence.

**Parse failure is a single line, no traceback** (`DESIGN.md:194`), produced by the same code path
the metrics screen already uses (`graph.py:113-135`) and asserted once (§8).

**The save target is `<source stem>.graph.json`,** beside the document — the CLI's own default
(`app.py:2762`: `path.with_suffix(".graph.json")`), and written with the CLI's own serializer
(`ContractGraph.to_file`, `models.py:130-131`). The success line names the resolved absolute path.

---

## 6. Domain change — expose the built graph, no second build path

`graph_summary_via_tui` already runs `parse_document` → `ClauseHierarchyBuilder().build` and then
discards the graph (`tui/domain/graph.py:70-85`). The change is to keep it:

- Add one field to the frozen `GraphSummary` dataclass (`tui/domain/graph.py:31-40`):
  `graph: ContractGraph`.
- Populate it at `:78-85` from the local `graph` variable that already exists — **no second parse,
  no second build**.
- `ContractGraph` joins the existing `TYPE_CHECKING` import block (`tui/domain/graph.py:27-28`
  already does this for `GraphMetrics`), so the runtime import stays function-local.

The metrics screen is unchanged: `GraphSummaryScreen._load` (`graph.py:114`) keeps reading
`.metrics` / `.score` and simply ignores the new field. Two consumers, one build.

**All `openreview_cli.graph.*` and `openreview_cli.parsing.*` imports stay function-local**
(inside `graph_summary_via_tui`, `tui/domain/graph.py:60-64`). This is the documented TUI rule —
`AGENTS.md:247` ("no module-level `from openreview_cli.gateway...` in any `tui/` module") plus the
module's own docstring (`tui/domain/graph.py:7-10`) — and it applies to `openreview_cli.graph` too:
the new screen must not grow a module-level graph import of its own.

**Explicitly rejected:** a second entry point (`graph_via_tui`, `build_graph_via_tui`, …) that
repeats the parse+build. The master plan names this as the failure mode to avoid (§5 T2.3, §12).

---

## 7. The alternative considered and rejected

**Fold this into the existing `GraphSummaryScreen`** (review suggestion, recorded in master plan §5
T2.4 and rejected in §12).

Rejected because that screen's contract is *read-only metrics*: its docstring is "Clause-graph
screen — read-only metrics and health score for one document" (`tui/screens/graph.py:1`), the class
docstring repeats it (`:64`), its body is one `Label: value` block plus a score (`:53-60`,
`:139-153`), and its only binding is `escape` (`:74-76`). Turning it into a build-and-save screen
would make its own docstring false, and the user's decision (G1) was a single build-and-show screen.
The one thing the two genuinely share — the domain build path — **is** taken, by G6.

---

## 8. Tests and acceptance criteria

### 8.1 `tests/unit/tui/test_graph_domain.py` (fast: no Textual, no `slow` marker)

1. `graph_summary_via_tui(path).graph` is a `ContractGraph` whose `len(nodes)` / `len(edges)` equal
   the summary's `node_count` / `edge_count` — summary and graph cannot disagree.
2. **Exactly one parse.** Monkeypatch `openreview_cli.parsing.stream.parse_document` with a
   counting wrapper and assert it is called **once** per `graph_summary_via_tui` call — the direct
   guard against a second build path.
3. `graph_summary_via_tui` still raises `FileNotFoundError` for a missing path
   (`tui/domain/graph.py:66-68`) — unchanged behaviour for the metrics screen.

### 8.2 `tests/integration/tui/test_graph_build_screen.py`

Pattern: `app.run_test(size=(120, 40))` + `pilot`, then `await screen._load_task` (never a fixed
sleep), then assert rendered text — as `tests/integration/tui/test_graph_screen.py:38-50` does. The
`slow` marker is applied automatically by `tests/integration/tui/conftest.py:4-13`.

1. **Numbered document → real tree.** Build a hierarchical `.docx` in `tmp_path` with
   python-docx, using `Heading 1` / `Heading 2` paragraph styles (the pattern already used at
   `tests/integration/test_precheck_review.py:74-81`, which builds a minimal DOCX with
   `d.add_heading(..., level=1)` / `level=2`, and at `tests/fixtures/generate_fixtures.py:208-212`
   (`_make_with_headings`)); the DOCX parser maps those to levels and calls `link_parent_ids`
   (`docx_parser.py:42-48`, `:159-161`, `:188-224`), so the graph has `parent_child` edges. Assert
   the tree renders the expected labels, that a parent node has children
   (`Tree.root.children` / `TreeNode.children` reflect the hierarchy), and that folding changes the
   displayed rows (`node.collapse()` then `expand()`).
2. **Flat document → the plain note.** `tests/fixtures/nda_with_pii.pdf` → 5 nodes, 0 edges
   (`test_graph_screen.py:59-70`); assert the state-3 copy from §5 verbatim and `app._exception is
   None`.
3. **Parse failure → one line, no traceback.** A missing path and a zero-byte file: assert the
   status line starts with `✗ Could not read`, contains no `Traceback`, the screen is still mounted,
   and `app._exception is None`.
4. **Only the save key writes.** Before any `s` press (and after a failed parse), assert
   `list(tmp_path.glob("*.graph.json")) == []`. After `pilot.press("s")` on the hierarchical
   document, assert exactly one file exists at `<stem>.graph.json`, that
   `ContractGraph.from_file(saved)` succeeds (it is the CLI's own format), and that its
   `to_json()` equals the `graph` the tree rendered.
5. **The CLI can consume what the TUI saved.** Assert `openreview graph view <saved>` exits 0 and
   prints a tree — run via the CLI's `app`/`CliRunner` in-process (NOT a new subprocess), or as a
   Phase-2 shell check (§8.4). This is the "content matches the CLI's graph JSON" criterion,
   proven from the consumer's side.
6. **Markup survival.** A document whose node label/text contains `[Party A]` renders those eight
   characters verbatim in the tree row (the retrieve screen already has this test shape).
7. **Reach + guard from results.** `ResultScreen(reports, document_paths=[...])` → `b` pushes
   `GraphBuildScreen`; with `document_paths=None` → `check_action("build_clause_graph", …)` is
   `False` and `b` pushes nothing (`result.py:326-335`).
8. **Reach from retrieve.** `RetrieveScreen` exposes a `Graph (B)` control in `#retrieve-actions`
   (see §9.2 for why it is a button, not a bare `b` binding): with a valid path in
   `#retrieve-path` it pushes the screen; with an empty or non-existent path it pushes nothing and
   writes a status line instead.

### 8.3 Conditional (only if G7's extraction is kept)

`tests/unit/test_graph_view.py` gains: `compute_annotations(graph)` returns the four annotation
kinds for a hand-built graph, and `render_tree`'s output on a hand-built graph is
**character-identical** before and after the extraction (a characterisation pin, so the CLI's
`graph view` output cannot shift under a "pure" refactor).

### 8.4 Acceptance criteria

```
uv run pytest tests/unit/tui/test_graph_domain.py -q                      # 8.1
uv run pytest tests/integration/tui/test_graph_build_screen.py -q         # isolated file
uv run pytest -m slow -q                                                  # whole TUI suite, no new failures
uv run pytest tests/unit/test_graph_view.py -q                            # only if T2.2 extraction kept
uv run openreview graph build <parsed.json> -o /tmp/g.json                # CLI path unchanged, exit 0
uv run openreview graph view /tmp/g.json | head                           # CLI path unchanged, exit 0
```

Plus, checked by review (not by a test):
- No module-level `openreview_cli.graph.*` / `openreview_cli.parsing.*` import was added to any
  `tui/` module.
- No file is written on mount, on parse, or on Escape — only on `s`.
- The new screen prints no metric rows: `density`, `max_depth`, `orphan_ratio`, `broken_ref_count`,
  `definition_coverage`, `Health score` appear nowhere in `graph_build.py`.

---

## 9. Risks and open points

1. **The `s` binding is a single letter.** On this screen there is no focused `Input`, so it is
   live (the retrieve plan's D11 measured that single-letter bindings are dead only while an
   `Input` consumes printable keys). If the screen ever gains an `Input`, the binding must become a
   button.
2. **Reach from `RetrieveScreen` is a button, and that is a deliberate deviation from "press (B) on
   both screens."** `RetrieveScreen` focuses `#retrieve-path` on mount (`retrieve.py:161`), and a
   single-letter widget binding is dead while an `Input` has focus. So the retrieve side gets a
   `Graph (B)` button in `#retrieve-actions` (labels in parentheses, per `DESIGN.md:167`), and the
   path it uses is whatever `#retrieve-path` currently names. *(This is this doc's call; the master
   plan says only "reached by `(B)`".)*
3. **`Tree` label truncation.** Textual's `Tree` may wrap or clip long labels depending on width.
   Pinning the 60-character snippet (`graph/view.py:46`) keeps the tree and the CLI's text tree
   honest about the *same* amount of node text, but the rendered line can still wrap at narrow
   widths; the tests assert substrings, not full lines.
4. **Cycle safety.** `render_tree` guards with a `visited` set (`graph/view.py:37-40,76-78`); the
   tree builder must carry the same guard, or a malformed `parent_child` cycle would nest forever.
   Not covered by a dedicated test (no cyclic fixture exists); the walk is copied from the proven
   implementation.
5. **The save-next-to-source target** (`path.with_suffix(".graph.json")`) is inherited from
   `app.py:2762`. No user decision names the directory. If the document's directory is read-only the
   save fails and the state-7 line reports it — no fallback directory is invented.
6. **T2.1's `link_parent_ids` test is not here.** Master plan §5 T2.1 owns it as a separate
   checklist item; this screen is a *consumer* of the hierarchy that test protects.

---

## 10. Not in scope

- **No metrics duplication.** The new screen shows no density/depth/orphan/broken-ref/definition-
  coverage numbers and no health score. That is `GraphSummaryScreen`'s job (`tui/screens/graph.py`),
  and it stays the only metrics surface.
- **The CLI is untouched.** `openreview graph build`, `graph view`, `graph metrics`, `graph diff`,
  `graph health` keep their behaviour and their `--from-db` / `--store` / `--cluster-clauses`
  options (`app.py:2718-3062`). The only permitted change to `graph/` is G7's behaviour-preserving
  `compute_annotations` extraction, and only if the condition holds.
- **No `graph --cluster-clauses`, no `--store`, no `graph diff` in the TUI.**
- **No new dependency.** Textual's `Tree` ships in the pinned `textual>=8.2.8`
  (`pyproject.toml:30`) — verified importable in the worktree venv (`textual 8.2.8`).
- **No change to `link_parent_ids`**, to the parsers, or to `graph/health.py`.
- **No parity-matrix edit.** `docs/cli-tui-parity-matrix.md` is regenerated by script in Phase 4;
  hand-editing it is forbidden (the retrieve plan's T7 rule).
- **No second parse+build entry point in `tui/domain/graph.py`.**
- **No plan to make the graph an AI/model feature.** The graph slot is removed in Phase 1; the
  graph stays rule-based.
