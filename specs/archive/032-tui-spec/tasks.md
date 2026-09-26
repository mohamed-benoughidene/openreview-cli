---

description: "Task list for Interactive TUI (Terminal User Interface) feature implementation"
---

# Tasks: Interactive TUI (Terminal User Interface)

**Input**: Design documents from `/specs/032-tui-spec/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md

**Tests**: Every user story phase includes 1-2 test tasks marked [P], to be written BEFORE implementation (TDD style). All integration tests use Textual's `Pilot` via `app.run_test()` (`asyncio_mode=auto` per T002a removes need for explicit `@pytest.mark.asyncio`). Unit tests in `tests/unit/tui/` are synchronous.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/openreview_cli/`, `tests/` at repository root
- All file paths are absolute from `/home/mohamed/lab/openreview/`
- TUI lives in new subpackage `src/openreview_cli/tui/` under existing package
- Tests in `tests/unit/tui/` (sync) and `tests/integration/tui/` (async with Pilot)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add dependencies, create directory tree, wire TUI entry point

- [X] T001 Add `textual>=8.2.8` runtime dependency to `/home/mohamed/lab/openreview/pyproject.toml` using `uv add textual>=8.2.8`
- [X] T002 Add `pytest-asyncio` dev dependency to `/home/mohamed/lab/openreview/pyproject.toml` using `uv add --dev pytest-asyncio` (needed for async Pilot tests; source: https://github.com/textualize/textual/blob/main/docs/guide/testing.md)
- [X] T002a Configure `asyncio_mode = auto` in `/home/mohamed/lab/openreview/pyproject.toml` under `[tool.pytest.ini_options]` — removes the need for `@pytest.mark.asyncio` decoration on every async test.
- [X] T003 Create `tui/` package directory tree (tabs/, widgets/, screens/, domain/, tcss/) under `/home/mohamed/lab/openreview/src/openreview_cli/tui/` using `mkdir -p`
- [X] T004 [P] Create `tui/__init__.py` exposing `launch_tui()` at `/home/mohamed/lab/openreview/src/openreview_cli/tui/__init__.py` — re-exports `launch_tui` from launcher module
- [X] T005 [P] Create launcher.py with `sys.stdin.isatty()` check at `/home/mohamed/lab/openreview/src/openreview_cli/tui/launcher.py` — check TTY BEFORE Textual imports (per research.md); if non-TTY, print friendly message pointing to `--help` and `sys.exit(0)` (per FR-001a); if TTY, import and run `OpenReviewApp`. The TTY check MUST be on `sys.stdin.isatty()` (NOT stdout) so that piping stdout to a log file (with stdin still a TTY) still launches the TUI normally. Only when stdin is not a TTY (piped input, CI without terminal allocation, agent invocation) does the launcher exit with the friendly message.
- [X] T006 Modify `app.py` dispatch logic at `/home/mohamed/lab/openreview/src/openreview_cli/app.py` — in the `_root` callback, add (a) TTY detection via `sys.stdin.isatty()` BEFORE any Textual import, (b) dispatch to `launch_tui()` when no subcommand is invoked and TTY is attached, (c) `--no-tui` flag to force CLI behavior when set (per FR-044). TUI imports must be lazy (deferred inside the function call) so non-TUI invocations don't pay the Textual import cost.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core widgets, base app shell, domain wrappers, and test infrastructure that ALL user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T007 [P] Write unit tests for all widgets (status_bar, description_bar, filter_list, file_picker) in `/home/mohamed/lab/openreview/tests/unit/tui/test_widgets.py` and `/home/mohamed/lab/openreview/tests/unit/tui/test_filter_list.py` — test status_bar formatting (FR-006) and gateway status display (FR-007), description_bar updates (FR-005), filter_list type-to-filter (FR-009, FR-010), file_picker directory navigation (FR-033-035); sync tests (no asyncio)
- [X] T008 [P] Create `tcss/` directory with `app.tcss`, `tabs.tcss`, `widgets.tcss` at `/home/mohamed/lab/openreview/src/openreview_cli/tui/tcss/` AND create `__init__.py` files for `tabs/`, `widgets/`, `screens/`, `domain/` subpackages in `/home/mohamed/lab/openreview/src/openreview_cli/tui/`
- [X] T009 [P] Create `status_bar.py` widget at `/home/mohamed/lab/openreview/src/openreview_cli/tui/widgets/status_bar.py` AND `description_bar.py` widget at `/home/mohamed/lab/openreview/src/openreview_cli/tui/widgets/description_bar.py` — status_bar shows current client (or "—"), gateway status (FR-007), privacy tier (FR-046a), pricing tier em-dash (FR-037), clickable gateway item (FR-008); description_bar shows one-line focused item description (FR-005, FR-011)
- [X] T010 [P] Create `filter_list.py` widget at `/home/mohamed/lab/openreview/src/openreview_cli/tui/widgets/filter_list.py` AND `file_picker.py` widget at `/home/mohamed/lab/openreview/src/openreview_cli/tui/widgets/file_picker.py` — filter_list: type-to-filter with Textual ListView/ListItem, real-time rebuild (FR-009, FR-010); file_picker: DirectoryTree, CWD start (FR-035), arrow navigation, hidden-files toggle Ctrl-H (FR-034), full-screen (FR-033)
- [X] T011 Create `ConfirmModal` screen at `/home/mohamed/lab/openreview/src/openreview_cli/tui/screens/confirm.py` — Textual `ModalScreen` for delete and cancel-review confirmations; optional "Also delete all reviews" checkbox (FR-025)
- [X] T012 Create domain layer wrappers in `/home/mohamed/lab/openreview/src/openreview_cli/tui/domain/` — five files: `gateway.py` (wraps `openreview_cli.gateway.router.Gateway.health_check` for gateway status), `review.py` (wraps `openreview_cli.review.run_review`; PII stripping enabled by default when `no_pii=False`), `clients.py` (wraps `openreview_cli.storage.database` client CRUD: `add_client`, `delete_client`, etc.), `playbooks.py` (wraps `openreview_cli.review.playbook.load_playbook` and `compute_playbook_diff` + storage functions `import_playbook_yaml`, `get_latest_playbook_version`), `privacy.py` (reads privacy tier from `openreview_cli.gateway.tier_config.TierConfig.from_config` per FR-046a; returns 'unknown' if the configured value is not one of maximum/balanced/performance, so the status bar shows 'Privacy: unknown' as specified)
- [X] T013 Create `OpenReviewApp` base shell in `/home/mohamed/lab/openreview/src/openreview_cli/tui/app.py` — `OpenReviewApp(Textual App)` with `CSS_PATH`, `TabbedContent` + five `TabPane` stubs (Home, Review, Clients, Playbooks, Settings), persistent `status_bar` and `description_bar`, `BINDINGS` (Tab/Shift+Tab, Ctrl-C), `on_mount` default tab; all tabs start as placeholder content
- [X] T013a Add two-press Ctrl-C quit behavior to `OpenReviewApp` in `/home/mohamed/lab/openreview/src/openreview_cli/tui/app.py` — first Ctrl-C shows a brief 'Press Ctrl-C again to quit' notification in the status bar; second Ctrl-C within 2 seconds calls `app.exit()` (per FR-002). Add an integration test in `/home/mohamed/lab/openreview/tests/integration/tui/test_app.py` that presses Ctrl-C twice via Pilot and asserts the app exits with code 0.
- [X] T014 Write integration test for app launch and tab navigation using Pilot in `/home/mohamed/lab/openreview/tests/integration/tui/test_app.py` — async def test with `app.run_test()` (asyncio_mode=auto per T002a); test tab bar rendering, Tab/number-key switching, quit, non-TTY dispatch with `sys.stdin.isatty()` monkeypatch (source: https://github.com/textualize/textual/blob/main/docs/guide/testing.md). test_app.py is the home for cross-tab tests; per-tab tests live in their own files (test_review_wizard.py, test_clients_tab.py, test_playbooks_tab.py, test_gateway_wizard.py, test_settings_tab.py).

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 — First-time user reviews a contract (P1) 🎯 MVP

**Goal**: A non-technical user launches TUI, picks "New review", completes a 4-step wizard, watches progress, views results with split view, and exports memo — using only arrow keys, Enter, and typing.

**Independent Test**: Tester with no prior CLI experience can complete the full first-review flow (launch TUI → review a sample PDF → export result) in under 5 minutes.

### Tests for User Story 1 (Write FIRST, ensure they FAIL before implementation) ⚠️

- [X] T015 [P] [US1] Write integration test for review wizard flow using Pilot in `/home/mohamed/lab/openreview/tests/integration/tui/test_review_wizard.py` — async def test with `app.run_test()`; test full 4-step wizard navigation (mode selection with type-to-filter per FR-013, file picker per FR-033-FR-035, playbook step, confirm step), test cancel returns to Home tab (FR-017), test progress screen appears (FR-016) (source: https://github.com/textualize/textual/blob/main/docs/guide/testing.md)
- [X] T016 [P] [US1] Write integration test for result screen and export in `/home/mohamed/lab/openreview/tests/integration/tui/test_review_wizard.py` — async def test; verify split view layout (FR-018), layout toggle (FR-019), summary counts header (FR-020), description bar updates on clause focus (FR-021), export action writes file (FR-022)
- [X] T016a [P] [US1] Write integration test for clickable gateway status bar in `/home/mohamed/lab/openreview/tests/integration/tui/test_app.py` — via Pilot, click the gateway status bar item; assert the Settings tab opens with the Gateway section selected (per FR-008).

### Implementation for User Story 1

- [X] T017 [P] [US1] Create `HomeTab` at `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/home.py` — Textual Screen (as TabPane content) with welcome message, two quick action buttons ("New review" and "Import document" per TUI-Tree.md design), empty state when no reviews exist (per US2 AS-4: "No reviews yet. Start one with [New review].")
- [X] T017a [P] [US1] Write unit test asserting PII stripping is enabled by default when review is invoked from the TUI wizard in `/home/mohamed/lab/openreview/tests/unit/tui/test_review_domain_wrapper.py` — mock `openreview_cli.review.run_review`, invoke the TUI's `domain/review.py` wrapper with wizard-collected parameters, assert `no_pii=False` is passed and the PII stripping threshold is non-None (per FR-045 and SC-007). Also add an integration smoke test that runs the wizard with a tiny sample document and asserts the result file's content shows PII placeholders, not raw PII.
- [X] T018 [P] [US1] Create `ReviewTab` shell at `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/review.py` — TabPane content that launches the review wizard; provides "New review" button; this tab is the programmatic target for starting a new review
- [X] T019 [US1] Implement 4-step review wizard in `/home/mohamed/lab/openreview/src/openreview_cli/tui/screens/review_wizard.py` — Textual Screen with step counter, back/cancel/next buttons, per-step content area; Step 1: mode picker with 22 modes grouped by category (collapsible groups per FR-013), type-to-filter (FR-012); Step 2: file picker showing PDF/DOCX files (FR-033); Step 3: playbook picker with default pre-selected (FR-014); Step 4: confirmation summary with "Override model" and "Disable PII stripping" checkboxes (FR-015); on confirm, triggers review execution
- [X] T020 [US1] Implement progress screen during review in `/home/mohamed/lab/openreview/src/openreview_cli/tui/screens/progress.py` — after wizard confirms, push progress screen with one row per pipeline step (parsing, PII stripping, extraction, QA verification, report building), progress bar, elapsed time (FR-016); Cancel button opens ConfirmModal (FR-017); on complete, push result screen
- [X] T021 [US1] Implement result screen with split view in `/home/mohamed/lab/openreview/src/openreview_cli/tui/screens/result.py` — Textual Screen with clause list (left pane) and focused clause details (right pane) by default (FR-018); layout toggle key switches between split and full-screen scroll (FR-019); summary counts header "N Green · N Amber · N Red · N clauses" (FR-020); description bar updates with clause status and confidence (FR-021); Export action button (FR-022)
- [X] T022 [US1] Implement export action on result screen in `/home/mohamed/lab/openreview/src/openreview_cli/tui/screens/result.py` — Export button opens format chooser (Markdown, JSON, DOCX per FR-022); after format selection, shows file save destination prompt; writes memo to chosen path; shows success/error notification
- [X] T023 [US1] Wire HomeTab → ReviewTab → wizard → progress → result flow in `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/home.py` and `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/review.py` — pressing "New review" on HomeTab opens ReviewTab; ReviewTab launches review_wizard screen; wizard pushes progress, then result; closing result returns to HomeTab

**Checkpoint**: At this point, US1 should be fully functional — a first-time user can complete an end-to-end review and export results.

---

## Phase 4: User Story 2 — Returning user re-opens past review (P1)

**Goal**: User sees their 5 most recent reviews on the Home tab and re-opens any past review result screen with one Enter press.

**Independent Test**: Tester can complete a review, quit the TUI, relaunch, and re-open the same review from the Home tab list in under 30 seconds.

### Tests for User Story 2 (Write FIRST, ensure they FAIL before implementation) ⚠️

- [X] T024 [P] [US2] Write integration test for re-open past review flow in `/home/mohamed/lab/openreview/tests/integration/tui/test_app.py` — async def test with Pilot; simulate completing a review (via monkeypatched domain layer), quit, relaunch app, verify recent-reviews list appears on Home tab, press Enter on first item, verify result screen opens (source: https://github.com/textualize/textual/blob/main/docs/guide/testing.md)

### Implementation for User Story 2

- [X] T025 [US2] Add recent-reviews list to HomeTab in `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/home.py` — fetch 5 most recent reviews from database ordered by date descending; show filename, date, mode, color counts (Green/Amber/Red) per entry; type-to-filter support when >5 items (FR-009); description bar shows review mode, date, color counts on focus (per US2 AS-2); empty state "No reviews yet. Start one with [New review]." (US2 AS-4)
- [X] T026 [US2] Implement re-open flow from recent-reviews list to result screen in `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/home.py` — pressing Enter on a recent review entry loads saved ReviewReport from database and pushes result screen (same `screens/result.py` view as if just completed); result screen shows full split view with clause list and details

**Checkpoint**: US1 AND US2 both work independently — user can review and re-open past reviews.

---

## Phase 5: User Story 3 — Power user configures gateway providers (P2)

**Goal**: User opens Settings tab, runs gateway setup wizard, configures all 6 model slots, API key is entered only once per provider.

**Independent Test**: Tester can configure all six gateway model slots in under 3 minutes, entering each provider's API key exactly once.

### Tests for User Story 3 (Write FIRST, ensure they FAIL before implementation) ⚠️

- [X] T027 [P] [US3] Write integration test for gateway wizard using Pilot in `/home/mohamed/lab/openreview/tests/integration/tui/test_gateway_wizard.py` — async def test; verify 4-step gateway wizard: slot selection from 6 slots (FR-030), provider filtering by typing (FR-030 AS-2), model selection, key entry with `Input(password=True)` masking (FR-032a), key-skip-if-exists (FR-031); verify slot assignment updates in Settings after completion (source: https://github.com/textualize/textual/blob/main/docs/guide/testing.md)
- [X] T027a [P] [US3] Write integration test for API key paste into masked field in `/home/mohamed/lab/openreview/tests/integration/tui/test_gateway_wizard.py` — via Pilot, set the masked `Input` field's value directly (simulating paste) and assert the value is accepted (i.e., the field's internal `value` matches the pasted string, even though display is masked) per FR-032a.
- [X] T028 [P] [US3] Write integration test for Settings tab in `/home/mohamed/lab/openreview/tests/integration/tui/test_settings_tab.py` — async def test with Pilot; verify two-panel layout (sections list + content area per FR-036), Gateway section shows slot status, Configuration/About sections render without errors, pricing tier shows "—" (FR-037)

### Implementation for User Story 3

- [X] T029 [US3] Create `SettingsTab` with two-panel layout in `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/settings.py` — left panel: sections list (Gateway, Configuration, Pricing tier, About per FR-036); right panel: content area showing selected section's content; pricing tier section shows "—" (em-dash) with "not available yet" note (FR-037); About section shows version, license, Python version, database path, config path, documentation URL (FR-038)
- [X] T030 [US3] Implement Gateway section content in Settings tab in `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/settings.py` — show all 6 model slots (reasoning, extraction, embedding, reranking, graph, grounding) with their current provider/model assignments; each slot shows health status; "Run setup wizard" button launches gateway_wizard screen
- [X] T031 [US3] Implement 4-step gateway wizard in `/home/mohamed/lab/openreview/src/openreview_cli/tui/screens/gateway_wizard.py` — Textual Screen with step counter and back/cancel/next; Step 1: pick slot from 6 (FR-030); Step 2: pick provider with type-to-filter (FR-030 AS-2); Step 3: pick model for selected provider; Step 4: if provider has saved key in `auth.json`, show "Using saved key for [provider]" message (FR-031) and skip to save; if no saved key, show `Input(password=True)` masked field (FR-032a), verify key before saving (FR-032), show error and retry on failure; on complete, save slot config and pop back to Settings

**Checkpoint**: US1, US2, AND US3 all work independently.

---

## Phase 6: User Story 4 — User manages clients and playbooks (P2)

**Goal**: User adds a client, imports a playbook, views details and version history — all without leaving the TUI.

**Independent Test**: Tester can add a client, switch to Playbooks tab, import a playbook, view its detail, and switch back to see the new client — without leaving the TUI.

### Tests for User Story 4 (Write FIRST, ensure they FAIL before implementation) ⚠️

- [X] T032 [P] [US4] Write integration test for Clients tab CRUD using Pilot in `/home/mohamed/lab/openreview/tests/integration/tui/test_clients_tab.py` — async def test with Pilot; test add client from form, validate client appears in filterable list, test client detail view shows reviews, test delete confirmation modal (FR-025), test empty state "No reviews for this client yet" (FR-025a) (source: https://github.com/textualize/textual/blob/main/docs/guide/testing.md)
- [X] T033 [P] [US4] Write integration test for Playbooks tab using Pilot in `/home/mohamed/lab/openreview/tests/integration/tui/test_playbooks_tab.py` — async def test with Pilot; test import playbook from YAML via file picker, test playbook detail view shows categories with default positions (FR-026), test version history list with current version marked (FR-027), test version diff view (FR-029) (source: https://github.com/textualize/textual/blob/main/docs/guide/testing.md)

### Implementation for User Story 4

- [X] T034 [US4] Create `ClientsTab` with filterable list in `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/clients.py` — filterable list of clients matching against ID and name (FR-023); "+ Add client" button; description bar shows client name and review count on focus (FR-024); pressing Enter opens client detail view showing that client's reviews; zero-reviews client shows "No reviews for this client yet. Start one with [New review]." (FR-025a)
- [X] T035 [US4] Create client add/edit form screen in `/home/mohamed/lab/openreview/src/openreview_cli/tui/screens/client_form.py` — full-screen form with ID, Name, Notes fields (FR-024); Enter on any field saves; Escape cancels; validates ID format (lowercase, hyphens); on save, calls `domain/clients.py` and returns to Clients list with new client highlighted
- [X] T036 [US4] Implement delete client flow in `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/clients.py` — delete button on client detail view opens `ConfirmModal` (T011) with "Also delete all reviews" checkbox if client has reviews (FR-025); on confirm, calls `domain/clients.py` delete; returns to Clients list
- [X] T037 [US4] Create `PlaybooksTab` in `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/playbooks.py` — filterable list of playbooks with text search + mode dropdown filter (FR-026); "+ Import playbook" button opens file picker for YAML files; auto-detects mode from filename with user confirmation (FR-027); on import, shows preview and validation status before saving; pressing Enter on a playbook opens detail view
- [X] T038 [US4] Implement playbook detail view in `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/playbooks.py` — shows all categories with default positions and exemplar descriptions inline (FR-026); "View versions" button opens version history list with current version marked (FR-028); "Set as current" shows confirmation modal (FR-028); "View diff" opens full-screen version diff showing added/removed/changed categories with exemplar-level changes (FR-029)

**Checkpoint**: US1 through US4 all work independently — core product management flows complete.

---

## Phase 7: User Story 5 — User searches globally (P3)

**Goal**: User presses `/` from any tab, types a fragment, sees matching results across reviews, clients, and playbooks, and navigates to the selected result.

**Independent Test**: Tester with at least 10 clients and 10 reviews can find a specific review by filename fragment in under 10 seconds.

### Tests for User Story 5 (Write FIRST, ensure they FAIL before implementation) ⚠️

- [X] T039 [P] [US5] Write integration test for global search using Pilot in `/home/mohamed/lab/openreview/tests/integration/tui/test_app.py` — async def test with Pilot; seed reviews and clients, press `/`, type fragment, verify results update in real time (FR-040), select a result and verify navigation to detail view (FR-041) (source: https://github.com/textualize/textual/blob/main/docs/guide/testing.md)

### Implementation for User Story 5

- [X] T040 [US5] Create global search `ModalScreen` in `/home/mohamed/lab/openreview/src/openreview_cli/tui/screens/search.py` — Textual ModalScreen with Input field; as user types, results update in real time across reviews (by filename), clients (by ID and name), and playbooks (by ID and description) (FR-040); results grouped by type with type labels; pressing Enter on a result navigates to that item's detail view (FR-041); Escape closes search
- [X] T041 [US5] Bind `/` key in `OpenReviewApp` to open search overlay in `/home/mohamed/lab/openreview/src/openreview_cli/tui/app.py` — add `/` to `BINDINGS` dict; on key press, call `app.push_screen('search')` to open `SearchScreen`; ensure `/` keybinding works from any tab (FR-040)

**Checkpoint**: All 5 user stories are independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, about section, copy-to-clipboard, accessibility note, and minor improvements across all stories.

- [X] T042 Create About section content in Settings tab at `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/settings.py` — show application version (from `openreview_cli.__version__`), license (AGPL-3.0), Python version, database path, config path, documentation URL (FR-038); all paths and URLs have copy-to-clipboard buttons
- [X] T043 Create Configuration section and Pricing tier section stubs in Settings tab at `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/settings.py` — Configuration section shows current config file path and last-saved time; Pricing tier section shows usage statistics (prompt tokens, completion tokens, estimated cost per FR-039) with "—" for tier selection and "not available yet" note (FR-037)
- [X] T044 Add copy-to-clipboard support for paths and URLs in About section at `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/settings.py` — use Textual clipboard API or `pyperclip` (if available) to copy database path, config path, documentation URL on button press; show brief "Copied!" confirmation
- [X] T045 Add accessibility note per FR-032b in Settings tab About section at `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/settings.py` — add one-line text: "Keyboard navigation only. Screen reader support is not yet available." (FR-032b); this is a documentation/communication task, not a feature task
- [X] T046 [P] Add docstrings and module-level documentation for all TUI modules — one-line docstring in each `__init__.py`, class docstrings in all widget/tab/screen modules, `__all__` exports where applicable
- [X] T047 (placeholder / conditional) Run quickstart.md validation — this task requires `quickstart.md` to exist; when present, verify that all TUI entry points and commands documented in quickstart.md work as described. (validated 2026-07-11, see README.md for known test isolation caveat)
- [X] T047a Add a cold-start timing test in `/home/mohamed/lab/openreview/tests/integration/tui/test_app_cold_start.py` — measure wall-clock time from `launch_tui()` call to first screen render using Pilot; assert it is under 1.0 second on the reference machine (per SC-004). Mark this test with `@pytest.mark.slow` and add to `[tool.pytest.ini_options]` markers so it can be skipped in fast CI. (Note: real timing is hardware-dependent; consider a relative threshold with a documented baseline.)
- [X] T047b Add TUI memory-budget integration test in `/home/mohamed/lab/openreview/tests/integration/tui/test_app_memory.py` — uses `tracemalloc` to measure peak memory increase from `launch_tui()` to first interactive screen; assert the increase is under 50 MB on the reference machine (per SC-005). Mark with `@pytest.mark.memory` and document in test docstring that this test must be run in isolation (per AGENTS.md caveat about cumulative test load causing memory pressure). Add to `[tool.pytest.ini_options] markers` list if not already there.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Phase 2 completion
  - User stories can proceed sequentially in priority order (P1 → P2 → P3)
  - Or in parallel if team capacity allows (once Phase 2 is done)
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependencies on other stories
- **US2 (P1)**: Depends on US1 (HomeTab must exist to add recent-reviews list; result screen must exist to re-open)
- **US3 (P2)**: Can start after Phase 2 — no dependencies on US1/US2 (Settings tab is independent tab)
- **US4 (P2)**: Can start after Phase 2 — no dependencies on US1/US2 (Clients/Playbooks are independent tabs)
- **US5 (P3)**: Depends on Phase 2 (app.py bindings) + data from Phases 3-6 (searches reviews, clients, playbooks)

### Within-Story Order

- Tests MUST be written first and FAIL before implementation (TDD)
- Widgets/models before screens
- Screens before wiring
- Single-file tasks before multi-file integration
- Story complete before moving to next priority

### Parallel Opportunities

- T004 [P] and T005 [P] can run in parallel (Phase 1)
- T007-T008 [P] can run in parallel (Phase 2 test+init files)
- T009-T010 [P] can run in parallel (Phase 2 widget implementations)
- T015-T016 [P] can run in parallel (US1 test files)
- T017-T018 [P] can run in parallel (US1 HomeTab + ReviewTab)
- T024 [P] and T025-T026 can run sequentially (US2 test then implementation)
- US3 can start simultaneously with US1 if team capacity allows
- US4 can start simultaneously with US1 if team capacity allows

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 in parallel:
Task: "Write integration test for review wizard flow"
  → pytest tests/integration/tui/test_review_wizard.py -k "test_wizard_navigation or test_progress"
Task: "Write integration test for result screen and export"
  → pytest tests/integration/tui/test_review_wizard.py -k "test_result_split_view or test_export"

# Launch all Tab implementations for User Story 1 in parallel:
Task: "Create HomeTab"
  → uv run ruff format src/openreview_cli/tui/tabs/home.py
  → uv run mypy src/openreview_cli/tui/tabs/home.py
Task: "Create ReviewTab shell"
  → uv run ruff format src/openreview_cli/tui/tabs/review.py
  → uv run mypy src/openreview_cli/tui/tabs/review.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (deps, directory, launcher, app dispatch)
2. Complete Phase 2: Foundational (widgets, app shell, domain wrappers, tests)
3. Complete Phase 3: US1 (review wizard, result screen, export)
4. **STOP and VALIDATE**: Test US1 independently per independent test criteria
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Test → Deploy/Demo (MVP!)
3. Add US2 → Test → Deploy/Demo (returning user flow)
4. Add US3 → Test → Deploy/Demo (power user config)
5. Add US4 → Test → Deploy/Demo (client/playbook management)
6. Add US5 → Test → Deploy/Demo (global search)
7. Add Polish → Final validation

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 + US2 (sequential — US2 depends on US1)
   - Developer B: US3 (independent)
   - Developer C: US4 (independent)
   - US5 can be picked up by any developer after US1-US4 are stable
3. Stories remain independently testable per their criteria

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Integration tests use Textual's `Pilot` via `app.run_test()` (source: https://github.com/textualize/textual/blob/main/docs/guide/testing.md), with `asyncio_mode = auto` in pyproject.toml per T002a
- Unit tests in `tests/unit/tui/` are synchronous (no asyncio)
- Write tests BEFORE implementation (TDD: watch them fail, then implement)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same-file conflicts, cross-story dependencies that break independence
- `uv add textual>=8.2.8` is the only new runtime dependency (per spec assumptions)
- `uv add --dev pytest-asyncio` is the only new dev dependency
- TUI dispatches from `src/openreview_cli/app.py` when no subcommand + TTY (per FR-001)
- Non-TTY → friendly message, exit 0 (per FR-001a)
- ModalScreen for confirmations; Screen for wizards (per research.md)
- `Input(password=True)` for API key masking (per research.md, https://github.com/textualize/textual/blob/main/docs/widgets/input.md)
- Memory tests for TUI deferred from this task list (per AGENTS.md caveat about `test_pii_memory.py` hanging under cumulative suite load)
- quickstart.md validation task (T047) is conditional on its future creation

---

## Phase 9: Convergence

**Purpose**: Close gaps between spec/plan and the current code identified by `/speckit.converge`. Each task traces to a specific source-ref and gap-type. No task may modify spec.md, plan.md, or any existing task in tasks.md.

**Source**: Generated 2026-07-11 from in-session convergence assessment. 14 checks (A1-N5) across FRs, plan decisions, and constitution principles. 14 actionable findings emitted below; 1 false positive (F15 checkboxes) excluded.

- [X] T048 CRITICAL [Convergence] Wire gateway health check into status bar per FR-007 in `/home/mohamed/lab/openreview/src/openreview_cli/tui/app.py` — replace static `Button("Gateway: —", id="status-gateway")` with a label that calls `gateway_health_check()` on mount AND on a 5-second interval; render one of the four formats per FR-007: "✓ All healthy" when all 6 slots reachable; "⚠ <slot> (<provider>): <error>" for exactly one failing slot; "⚠ <N>/6 slots: <slot1>, <slot2>" for multiple failing; "✗ All slots unreachable" for total failure. (missing)

- [X] T049 CRITICAL [Convergence] Restore 22-mode grouped list in review wizard per FR-013 in `/home/mohamed/lab/openreview/src/openreview_cli/tui/screens/review_wizard.py` — the shrink pass collapsed `PRODUCT_MODES` to a 5-entry flat list; FR-013 requires all 22 product modes grouped into 5 collapsible categories (Basic: precheck, fullreview; Employment: hirecheck, termcheck; Commercial: dealcheck, leasecheck, salecheck; Specialized: ipcheck, compcheck, riskcheck; Settlement: settlecheck, releasecheck). Use Textual's `Collapsible` widget (or equivalent) for each category header. Type-to-filter must still work across the groups. (missing)

- [X] T050 CRITICAL [Convergence] Hide hidden files in wizard file picker per FR-034 in `/home/mohamed/lab/openreview/src/openreview_cli/tui/screens/review_wizard.py` — `DirectoryTree(path=os.getcwd(), id="file-tree")` currently shows hidden files (those starting with `.`); pass `show_hidden=False` (or whatever Textual 8.x API exposes) so hidden files are hidden by default. Then add a Ctrl-H keybinding on the wizard that toggles `show_hidden` between True and False, and add a unit test in `/home/mohamed/lab/openreview/tests/integration/tui/test_review_wizard.py` that verifies hidden files are hidden by default and Ctrl-H reveals them. (missing)

- [X] T051 CRITICAL [Convergence] Add client detail view per FR-025a in `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/clients.py` and a new `/home/mohamed/lab/openreview/src/openreview_cli/tui/screens/client_detail.py` — currently `_on_list_view_selected` only tracks selection for delete; it must push a `ClientDetailScreen(client_id)` when Enter is pressed on a client. The detail screen shows that client's reviews (use `list_recent_reviews_via_tui` filtered by client_id, or a new `domain/clients.list_reviews_for_client_via_tui`). If the client has zero reviews, show the empty-state message "No reviews for this client yet. Start one with [New review]." and pressing Enter on that message must push `ReviewWizard` with the client pre-selected. (missing) — Migration 011 uses ALTER TABLE which is not idempotent in SQLite; see _exec_migration_safely in storage/database.py for the fix

- [X] T052 HIGH [Convergence] Gateway status click selects Gateway section per FR-008 in `/home/mohamed/lab/openreview/src/openreview_cli/tui/app.py` — `on_button_pressed` currently calls only `self.action_show_tab("settings")`; it must also call a new `action_show_section("gateway")` (or equivalent) on the SettingsTab so the Gateway section is auto-selected when the user clicks the gateway status bar item. Add a test in `/home/mohamed/lab/openreview/tests/integration/tui/test_app.py` that clicks `#status-gateway` and asserts the Gateway section is the active section in the Settings tab. (partial)

- [X] T053 HIGH [Convergence] Enter to save and Escape to cancel in client form per FR-024 in `/home/mohamed/lab/openreview/src/openreview_cli/tui/screens/client_form.py` — add `on_key(self, event)` handler that calls `self._save()` on `event.key == "enter"` and `self.dismiss(None)` on `event.key == "escape"`. Add tests in `/home/mohamed/lab/openreview/tests/integration/tui/test_client_form.py` for both behaviors. (missing)

- [X] T054 HIGH [Convergence] Add type-to-filter and direct path entry to wizard file picker per FR-033 in `/home/mohamed/lab/openreview/src/openreview_cli/tui/screens/review_wizard.py` — the file picker step currently has only `DirectoryTree`; add an `Input(placeholder="Type to filter files or enter path...", id="file-filter")` above the DirectoryTree. As the user types, the DirectoryTree's `filter` or `show_root` is set to filter visible files; if the typed string is a valid path (starts with `/` or `~`), navigate the DirectoryTree to that path. (missing)

- [X] T055 MEDIUM [Convergence] Add visible Quit option to tab bar per FR-003 in `/home/mohamed/lab/openreview/src/openreview_cli/tui/app.py` — FR-003 says the tab bar MUST include a "Quit option, visible on every screen". Add a `Button("Quit", id="btn-quit", variant="error")` to the compose layout (or a separate footer button), wire `on_button_pressed` to call `self.exit()`. (missing)

- [X] T056 MEDIUM [Convergence] Change status bar pricing tier label to "Pricing:" per FR-037 in `/home/mohamed/lab/openreview/src/openreview_cli/tui/app.py` — current label is "Tier:" which is ambiguous vs the "Privacy:" label; FR-037 requires them to be labeled separately with clear prefixes. Change `Static("Tier: —", id="status-tier")` to `Static("Pricing: —", id="status-tier")`. Update tests that assert on the label. (partial)

- [X] T057 MEDIUM [Convergence] Add database error screen per Edge case 1 in `/home/mohamed/lab/openreview/src/openreview_cli/tui/screens/db_error.py` (new file) and `/home/mohamed/lab/openreview/src/openreview_cli/tui/launcher.py` — when `init_database()` raises (DB missing or corrupt), catch the exception in `launcher.py` and push a `DatabaseErrorScreen` modal that shows the error message and offers a "Reinitialize" button which calls `init_database(force=True)` and re-launches the TUI. (missing)

- [X] T058 MEDIUM [Convergence] Add zero-provider gateway prompt per Edge case 2 in `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/settings.py` — when `gateway_health_check()` returns an empty dict (zero providers configured), the Gateway section should show a "Set up providers" prompt with a single button that launches the gateway wizard. The status bar gateway item should show "⚠ No providers configured" instead of the generic "Gateway: —". (missing)

- [X] T059 LOW [Convergence] Add "(corrupt)" marker for corrupt playbooks per Edge case 5 in `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/playbooks.py` — when a playbook row exists in storage but its YAML content fails to load, append " (corrupt)" to the list item label. Currently only a notification appears when the user tries to open the detail view. (missing)

- [X] T060 LOW [Convergence] Add usage statistics to Pricing tier section per FR-039 in `/home/mohamed/lab/openreview/src/openreview_cli/tui/tabs/settings.py` — FR-039 requires showing "usage statistics (prompt tokens, completion tokens, estimated cost) even though tier upgrades are not available." Re-add the `_get_usage_stats()` helper (deleted during the shrink pass) and display the three values in the Pricing tier section below the "—" line. Use `cost_logs` table in SQLite (queries: `SELECT SUM(prompt_tokens), SUM(completion_tokens), SUM(cost_cents) FROM cost_logs`). Add a test in `/home/mohamed/lab/openreview/tests/integration/tui/test_settings_tab.py` that seeds the cost_logs table and asserts the values are displayed. (partial)

**Notes**:
- T048-T060 are appended per `/speckit.converge` output 2026-07-11. No existing tasks were modified, renumbered, or deleted.
- All tasks trace to spec.md or plan.md source-refs. None introduces new product behavior outside the spec.
- Tasks are ordered CRITICAL → HIGH → MEDIUM → LOW for implementer priority.
- F15 (checkboxes on step 4) was excluded as a false positive — the checkboxes exist at `review_wizard.py:173-178`.
- F13 (click dep in pyproject.toml) was excluded — pre-existing, not introduced by TUI work; out of scope for this convergence pass.

---

## Phase 10: Convergence (round 2)

**Purpose**: Address 2 edge-case gaps that the Phase 9 convergence pass missed: signal handling for terminal close mid-review, and clause pagination for memory-constrained / large result sets.

- [X] T061 MEDIUM [Convergence] Add signal handler for terminal close mid-review per Edge case 6 in `/home/mohamed/lab/openreview/src/openreview_cli/tui/screens/progress.py` and `/home/mohamed/lab/openreview/src/openreview_cli/tui/launcher.py` — register handlers for `signal.SIGTERM` and `signal.SIGINT` in `OpenReviewApp.on_mount` (or in `launch_tui` after `OpenReviewApp()` is constructed) that cancel the in-progress `_review_task` in `ProgressScreen` (if one is active) and exit the app. Edge case 6 says "the review is cancelled by the OS signal handler; on next launch, the recent-reviews list does not include the cancelled review." This requires (a) the signal handler must NOT leave a partial report in the database; (b) on next launch, the recent-reviews list must reflect only completed reviews. Verify by adding a test that triggers SIGTERM mid-review via `os.kill(os.getpid(), signal.SIGTERM)` in a subprocess and asserts no report is added. (missing)

- [X] T062 MEDIUM [Convergence] Add clause pagination to result screen per Edge case 7 in `/home/mohamed/lab/openreview/src/openreview_cli/tui/screens/result.py` — currently the result screen renders all clauses in one `ListView`/`Vertical`, which would be slow for reports with thousands of clauses. Edge case 7 says "the result screen paginates the clause list (e.g. 100 clauses per page) and the full report scrolls." Add pagination: cap visible clauses to 100 per page, add "Next page" / "Previous page" buttons (or `>`/`<` keybindings), and update the summary header to show "Page N of M" alongside the Green/Amber/Red counts. The full report export (Markdown/JSON/DOCX) must still include ALL clauses, not just the visible page. (missing)
