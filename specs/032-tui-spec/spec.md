# Feature Specification: Interactive TUI (Terminal User Interface)

**Feature Branch**: `feat/032-tui-spec`
**Created**: 2026-07-11
**Status**: Draft
**Source artifacts**: `TUI-Decisions.md`, `TUI-Tree.md` (in this directory)

## Overview

Add a full-screen, persistent **Terminal User Interface (TUI)** to the `openreview` CLI. Today the product is a one-shot command-line tool: every action requires re-invoking the binary with subcommands, flags, and arguments. Non-technical users find this hard to discover, hard to recover from errors, and hard to chain. The TUI makes the tool feel like a desktop application that lives inside the terminal: a session that opens, lets the user navigate, and exits only when they choose.

When the user runs `openreview` with no subcommand, the TUI launches and stays open until they pick "Quit" or press `Ctrl-C`. All existing subcommands (`openreview parse ...`, `openreview precheck review ...`, `openreview gateway setup ...`, etc.) continue to work exactly as before for scripts, CI, and power users. The TUI is an additional, default entry point — not a replacement.

The TUI organizes work into five top-level tabs — **Home**, **Review**, **Clients**, **Playbooks**, **Settings** — plus a persistent status bar and a one-line description bar. Long-running actions (a contract review) show a progress screen with cancel support. Destructive actions use modal confirmation overlays. Lists of items (modes, files, playbooks, clients, past reviews) support type-to-filter. Every list item, when focused, shows a one-line description in the status bar so users can see what an option does before selecting it.

## Clarifications

### Session 2026-07-11

- Q: What should happen if someone runs `openreview` (with no subcommand) in a non-interactive context (CI script, pipe, agent invocation)? → A: Detect non-TTY, print a friendly message explaining that the TUI needs an interactive terminal and pointing to `openreview --help`, exit cleanly with code 0.
- Q: Should the API key input field in the gateway wizard mask the user's typing (password-style) or show the key as they type? → A: Mask the input completely (password-style, each character shown as `*`). Pasting a key fills the masked field. Verification on save catches typos.
- Q: How accessible does the TUI need to be (screen readers, reduced mobility, WCAG compliance)? → A: Full keyboard navigation (already in spec) covers most cases. No screen reader optimization in v1. Document the limitation honestly in the spec and in the About section of the TUI so affected users know what to expect.
- Q: Are the "pricing tier" and "privacy tier" mentioned in the spec the same concept, or different? → A: They are different concepts and MUST be shown separately. Privacy tier (constitutionally defined as maximum / balanced / performance) is shown in the TUI status bar and About section with a clear "Privacy" label. Pricing tier (developer / standard / pro) is a separate business concept; its slot stays reserved and marked "—" (em-dash) in v1 until the pricing model is designed.
- Q: When a user opens a client detail page for a client that has zero reviews, what should the Reviews section show? → A: A friendly empty state with the same wording family as the Home tab's empty state, customized for the client context. The message MUST be actionable — it tells the user the next step.

## User Scenarios & Testing

### User Story 1 — First-time user reviews a contract (Priority: P1)

A non-technical user (lawyer, ops lead, business owner) installs `openreview` and wants to review a contract PDF without reading documentation. They run `openreview` and the TUI opens. They see the Home tab with two quick actions and a friendly welcome message. They pick **New review** with arrow keys and Enter. A four-step wizard appears: pick a mode, pick a document, pick a playbook (optional), confirm. They pick `precheck`, browse to their PDF, accept the default playbook, and run. A progress screen shows each pipeline step with a progress bar. When it finishes, they see a result screen with a clause list, summary counts (Green/Amber/Red), and the focused clause's details. They press **Export memo** to save the result as Markdown.

**Why this priority**: This is the primary value proposition of the product. If a non-technical user can complete a review end-to-end without leaving the TUI, the product's adoption barrier collapses.

**Independent test**: A tester with no prior CLI experience can complete the full first-review flow (launch TUI → review a sample PDF → export result) in under five minutes, using only arrow keys, Enter, and typing.

**Acceptance Scenarios**:
1. **Given** the user has run `openreview` for the first time and the TUI opens, **When** they pick "New review" from the Home tab, **Then** the wizard opens at step 1 (mode selection).
2. **Given** the wizard is on step 1 (mode), **When** the user types `pre`, **Then** the list filters to show only modes whose name or description contains "pre" (PreCheck, etc.).
3. **Given** the wizard is on step 2 (document), **When** the user navigates into a directory, **Then** the file picker shows only PDF and DOCX files by default, with hidden files (those starting with `.`) hidden.
4. **Given** the user has completed all four wizard steps, **When** they press "Run review", **Then** a progress screen appears with a list of pipeline steps and a progress bar that advances.
5. **Given** a review is in progress, **When** the user presses "Cancel review", **Then** a confirmation modal appears; confirming cancels the review and returns to the Home tab without crashing the session.
6. **Given** a review has completed, **When** the result screen is displayed, **Then** the user sees summary counts (e.g. "12 Green · 2 Amber · 1 Red · 15 clauses") and a clause list with the focused clause's details visible in a split view.
7. **Given** the result screen is displayed, **When** the user presses the layout toggle key, **Then** the layout switches between split view and full-screen scroll.
8. **Given** the result screen is displayed, **When** the user presses "Export memo", **Then** they can choose Markdown, JSON, or DOCX format and a save destination, and the file is written successfully.

---

### User Story 2 — Returning user re-opens a past review (Priority: P1)

A user has completed several reviews and wants to revisit one. They launch the TUI. On the Home tab, they see their most recent five reviews listed with filename, date, mode, and color counts. They press Down arrow to highlight the review they want, and press Enter. The result screen for that past review opens — same view as if they had just run it. They export the result again with a different format.

**Why this priority**: Re-opening past work is the second most common action after starting a new review. The Home tab's recent-reviews list makes it a one-keystroke action.

**Independent test**: A tester can complete a review, quit the TUI, relaunch it, and re-open that same review from the Home tab list, in under 30 seconds.

**Acceptance Scenarios**:
1. **Given** the user has completed at least one review in a previous session, **When** they open the TUI, **Then** the Home tab shows that review (and up to four more) in a recent-reviews list ordered by date descending.
2. **Given** the recent-reviews list is on the Home tab, **When** the user highlights a review with arrow keys, **Then** the description bar shows the review's mode, date, and color counts.
3. **Given** the recent-reviews list is on the Home tab, **When** the user presses Enter on a highlighted review, **Then** the result screen for that review opens in full-screen mode.
4. **Given** the user has completed zero reviews, **When** they open the TUI, **Then** the Home tab shows an empty-state message: "No reviews yet. Start one with [New review]."

---

### User Story 3 — Power user configures gateway providers (Priority: P2)

A user wants to use different AI providers for different model slots (e.g. Anthropic for `reasoning`, OpenRouter for `embedding`). They open the Settings tab and pick the **Gateway** section. They click **Run setup wizard**. A four-step wizard appears: pick a slot, pick a provider, pick a model, enter an API key. They configure six slots, reusing the same provider for some and using a different one for others. For providers they have already configured, the API key entry step is skipped automatically and the wizard shows "Using saved key for OpenAI" instead.

**Why this priority**: Multi-provider configuration is essential for users who want flexibility or cost optimization. Without it, the gateway wizard is annoying to use for the common case of "use the same provider for everything".

**Independent test**: A tester can configure all six model slots in under three minutes, entering the API key for each provider exactly once.

**Acceptance Scenarios**:
1. **Given** the Settings tab is open with Gateway section selected, **When** the user picks "Run setup wizard", **Then** step 1 of the gateway wizard opens, showing a list of six model slots (reasoning, extraction, embedding, reranking, graph, grounding).
2. **Given** the user has just completed step 1 (slot: reasoning) and is on step 2 (provider), **When** they type `anth`, **Then** the provider list filters to show Anthropic first.
3. **Given** the user has selected a provider that already has a key in `auth.json`, **When** the wizard reaches step 4 (key), **Then** the key entry field is replaced with a "Using saved key for [provider]" message and the [Save] button is enabled.
4. **Given** the user has selected a provider that does not yet have a key, **When** the wizard reaches step 4, **Then** a key entry field is shown and the [Save] button is disabled until a key is entered and verified.
5. **Given** a slot has been configured successfully, **When** the wizard finishes, **Then** the Gateway section of Settings shows the updated slot assignment.

---

### User Story 4 — User manages clients and playbooks (Priority: P2)

A user organizes their work by client. They open the Clients tab. They add a new client with ID `acme-corp` and name `Acme Corporation`. They press Enter on the client in the list to see its detail, which shows all reviews associated with that client. They import a custom playbook from a YAML file via the Playbooks tab, see its categories and positions, and view its version history.

**Why this priority**: Client and playbook management are core product features. The TUI must make CRUD operations on these resources as smooth as the review flow.

**Independent test**: A tester can add a client, switch to the Playbooks tab, import a playbook, view its detail, and switch back to see the new client — all without leaving the TUI.

**Acceptance Scenarios**:
1. **Given** the Clients tab is open, **When** the user picks "+ Add client", **Then** a full-screen form opens with ID and Name fields.
2. **Given** the Add client form is open, **When** the user fills ID and Name and presses Enter, **Then** the client is saved and they return to the Clients list with the new client highlighted.
3. **Given** the Clients list is shown, **When** the user highlights a client, **Then** the description bar shows the client's name and review count.
4. **Given** the Clients list is shown, **When** the user presses Enter on a client, **Then** a client detail view opens showing that client's reviews.
5. **Given** the Playbooks tab is open, **When** the user picks "+ Import playbook", **Then** a file picker opens; selecting a YAML file shows a preview and validation status before the playbook is imported.
6. **Given** a playbook is highlighted in the list, **When** the user presses Enter, **Then** the playbook detail opens showing all categories with their default positions and exemplar descriptions.
7. **Given** a playbook detail is open, **When** the user picks "View versions", **Then** a version history list opens with the current version marked.
8. **Given** the user is viewing a client detail page for a client that has zero reviews, **When** the page renders, **Then** the Reviews section shows the empty-state message "No reviews for this client yet. Start one with [New review]." and pressing Enter on that message opens the Review tab's new-review wizard with that client pre-selected.

---

### User Story 5 — User searches globally (Priority: P3)

A user with many clients and reviews wants to find something quickly. They press `/` from anywhere in the TUI. A search overlay appears. They type a fragment. The TUI shows matching items across reviews, clients, and playbooks. They select one and navigate to it.

**Why this priority**: Search is a power feature. Useful for users with lots of data, but not required for the first-time flow.

**Independent test**: A tester with at least 10 clients and 10 reviews can find a specific review by filename fragment in under 10 seconds.

**Acceptance Scenarios**:
1. **Given** the TUI is open on any tab, **When** the user presses `/`, **Then** a search overlay appears with an input field.
2. **Given** the search overlay is open, **When** the user types a fragment, **Then** the results update as they type, showing matches across reviews (by filename), clients (by ID and name), and playbooks (by ID and description).
3. **Given** the search overlay shows results, **When** the user selects a result and presses Enter, **Then** the TUI navigates to that item's detail view.

---

### Edge Cases

- **What happens when the database is missing or corrupt?** The TUI shows an error screen with a clear message and an option to reinitialize. The session exits gracefully.
- **What happens when the gateway has zero providers configured?** The Gateway section shows a "Set up providers" prompt that launches the wizard. The status bar shows "Gateway: ⚠ No providers configured" instead of "All healthy".
- **What happens when the user presses Ctrl-C mid-review?** The review is cancelled, partial results are discarded, and the TUI returns to the Home tab.
- **What happens when the file picker is opened from inside a directory the user no longer has read access to?** The picker shows "Permission denied" and disables navigation into that directory.
- **What happens when a playbook file in the database is corrupt?** The playbook appears in the list with a "(corrupt)" marker; selecting it shows the parse error rather than the playbook content.
- **What happens when the user closes the terminal window while a review is running?** The review is cancelled by the OS signal handler; on next launch, the recent-reviews list does not include the cancelled review.
- **What happens when memory is constrained and the result has thousands of clauses?** The result screen paginates the clause list (e.g. 100 clauses per page) and the full report scrolls.
- **What happens when multiple slots share a provider and the user wants to change that provider for all of them at once?** Out of scope for v1; the user changes each slot individually. (A "bulk reassign" feature is a candidate for v2.)
- **What happens when the user enters an invalid API key?** The wizard shows a clear error message ("Invalid key for [provider]") and lets them retry without restarting the wizard.

## Requirements

### Functional Requirements

**TUI shell and navigation**
- **FR-001**: System MUST launch the TUI when `openreview` is run with no subcommand and no flags, AND a real terminal (TTY) is attached.
- **FR-001a**: System MUST detect when `openreview` is run with no subcommand but no TTY is attached (CI script, pipe, agent invocation, or redirected stdin/stdout), print a short friendly message explaining that the TUI needs an interactive terminal and pointing to `openreview --help` for available commands, then exit cleanly with code 0. This MUST NOT print a stack trace or an error code.
- **FR-002**: System MUST keep the TUI session open until the user selects Quit, presses `Ctrl-C` twice, or closes the terminal.
- **FR-003**: System MUST provide a persistent tab bar with five tabs (Home, Review, Clients, Playbooks, Settings) and a Quit option, visible on every screen.
- **FR-004**: System MUST support tab navigation via `Tab`/`Shift+Tab` (cycle), number keys 1-5 (jump to a specific tab), and mouse click.
- **FR-005**: System MUST support a one-line description bar at the bottom of every screen that displays the description of the currently focused item.

**Status bar**
- **FR-006**: System MUST display a status bar on every screen showing: current client (or "—"), gateway status, **privacy tier (constitutionally defined: maximum / balanced / performance, prefixed with a "Privacy:" label), and pricing tier (marked "—" for v1)**.
- **FR-007**: System MUST display gateway status as "✓ All healthy" when all six slots are reachable, or "⚠ <slot> (<provider>): <error>" for exactly one failing slot, or "⚠ <N>/6 slots: <slot1>, <slot2>" for multiple failing slots, or "✗ All slots unreachable" for total failure.
- **FR-008**: System MUST make the gateway status bar item clickable; clicking it opens the Settings tab with the Gateway section selected.

**Lists and filtering**
- **FR-009**: System MUST support type-to-filter on every list with more than five items, including: mode picker, file picker, playbook picker, client list, playbook list, past reviews list, and global search.
- **FR-010**: System MUST update filter results in real time as the user types, with no explicit "apply" step.
- **FR-011**: System MUST show the focused item's description in the description bar for every list item.

**Review wizard**
- **FR-012**: System MUST provide a four-step new-review wizard: pick mode, pick document, pick playbook, confirm and run.
- **FR-013**: System MUST group the 22 product modes by category (Basic, Employment, Commercial, Specialized, Settlement) in the mode picker, with collapsible groups.
- **FR-014**: System MUST show a default playbook option ("Use default for [Mode]") pre-selected in step 3.
- **FR-015**: System MUST show a confirmation screen at step 4 with a summary of the chosen options and two optional checkboxes: "Override model" and "Disable PII stripping".
- **FR-016**: System MUST show a progress screen during a review with one row per pipeline step (parsing, PII stripping, extraction, QA verification, report building), a progress bar, and elapsed time.
- **FR-017**: System MUST show a Cancel button on the progress screen; pressing it opens a confirmation modal, confirming cancels the review.

**Result screen**
- **FR-018**: System MUST show the result screen in a split view by default (clause list on the left, focused clause details on the right).
- **FR-019**: System MUST provide a layout toggle that switches between split view and full-screen scroll.
- **FR-020**: System MUST show summary counts (Green/Amber/Red/total) in a header bar on the result screen.
- **FR-021**: System MUST update the description bar with the focused clause's status and confidence score as the user navigates the clause list.
- **FR-022**: System MUST provide an Export action on the result screen that writes the review memo to a user-selected destination in Markdown, JSON, or DOCX format.

**Clients and Playbooks**
- **FR-023**: System MUST provide a Clients tab with: a filterable list of clients, an Add client button, a search filter that matches against both client ID and name, and a client detail view showing that client's reviews.
- **FR-024**: System MUST provide an Add/Edit client form (full screen) with ID, Name, and Notes fields; pressing Enter on any field saves the form; pressing Escape cancels.
- **FR-025**: System MUST show a delete-confirmation modal when the user picks "Delete client", with an "Also delete all reviews" checkbox if the client has reviews.
- **FR-025a**: System MUST display a friendly empty state in a client's Reviews section when that client has zero reviews. The message MUST be: "No reviews for this client yet. Start one with [New review]." Pressing Enter on the message (or clicking it) MUST open the Review tab and start the new-review wizard, with the client pre-selected if the wizard supports a client parameter.
- **FR-026**: System MUST provide a Playbooks tab with: a filterable list (text + mode dropdown filter), an Import button, a detail view showing all categories and their default positions inline, and a versions view.
- **FR-027**: System MUST auto-detect the playbook's mode from the YAML filename in the Import flow, but allow the user to confirm or edit the detected mode before saving.
- **FR-028**: System MUST show a "Set as current" confirmation modal before changing a playbook's current version.
- **FR-029**: System MUST show a full-screen playbook version diff view (added, removed, changed categories, with exemplar-level changes).

**Gateway wizard**
- **FR-030**: System MUST provide a four-step gateway setup wizard: pick slot, pick provider, pick model, enter key.
- **FR-031**: System MUST skip the API key entry step (step 4) automatically when the chosen provider already has a key in `auth.json`, showing "Using saved key for [provider]" instead.
- **FR-032**: System MUST verify the API key before saving when the user enters a new one, and show a clear error message if verification fails.
- **FR-032a**: System MUST mask the API key input field so each typed character is displayed as `*` (password-style), to prevent shoulder-surfing. Pasting a key from the clipboard MUST fill the masked field.
- **FR-032b**: System MUST document the TUI's accessibility scope clearly: full keyboard navigation is supported (Tab/Shift+Tab, number keys, arrow keys, Enter, Escape, `/`, `Ctrl-C`); screen reader optimization is NOT supported in v1. The About section of the TUI MUST include a one-line accessibility note ("Keyboard navigation only. Screen reader support is not yet available.") so affected users are not surprised.

**File picker**
- **FR-033**: System MUST provide a full-screen file picker that supports directory navigation with arrow keys, type-to-filter on filenames, and direct path entry.
- **FR-034**: System MUST hide hidden files (those starting with `.`) by default and support toggling visibility with `Ctrl-H`.
- **FR-035**: System MUST start the file picker at the user's current working directory by default.

**Settings**
- **FR-036**: System MUST provide a Settings tab with a two-panel layout: a sections list (Gateway, Configuration, Pricing tier, About) and a content area for the selected section.
- **FR-037**: System MUST display pricing tier as "—" (em-dash) in the status bar and About section, with a note that pricing is not yet implemented. Privacy tier MUST be displayed separately with its current value (maximum / balanced / performance) and a "Privacy:" prefix.
- **FR-038**: System MUST provide an About section showing the application version, license, Python version, database path, config path, and documentation URL, with copy-to-clipboard buttons for paths and URLs.
- **FR-039**: System MUST show usage statistics in the Pricing tier section (prompt tokens, completion tokens, estimated cost) even though tier upgrades are not available.

**Global search**
- **FR-040**: System MUST open a global search overlay when the user presses `/` from any tab, with results matching across reviews (by filename), clients (by ID and name), and playbooks (by ID and description).
- **FR-041**: System MUST navigate to the selected result's detail view when the user confirms a search result.

**Backwards compatibility and CLI parity**
- **FR-042**: System MUST keep every existing CLI subcommand working exactly as before. The TUI is an additional entry point, not a replacement.
- **FR-043**: System MUST exit with the same exit codes (0-10) for one-shot commands whether invoked from the TUI or from the command line.
- **FR-044**: System MUST allow passing `--no-tui` to force command-line behavior even when no subcommand is given (e.g. `openreview --no-tui parse foo.pdf`).

**Privacy and security**
- **FR-045**: System MUST strip PII from any document text before any external API call, even when invoked from the TUI.
- **FR-046**: System MUST display a privacy-tier indicator in the About section and in the status bar, with values from the constitutional model (maximum / balanced / performance). Pricing tier is a separate indicator; do not conflate them. (Note: an earlier draft of this spec incorrectly listed privacy-tier values as "developer / standard / pro" — those are pricing-tier values and have been corrected here.)
- **FR-046a**: System MUST read the current privacy tier from configuration at TUI startup and display it in the status bar with a "Privacy:" prefix. If the configured value is unknown, the status bar MUST show "Privacy: unknown" rather than failing.
- **FR-047**: System MUST NEVER log raw contract text, PII, or API keys, even when the TUI is run in debug mode.

### Key Entities

- **TUI session**: a single running instance of the interactive TUI. Holds the current tab, current focus position, recent-reviews cache, and any in-progress wizard state. Created on launch; destroyed on quit.

- **Tab**: one of Home, Review, Clients, Playbooks, Settings, Quit. Each tab is a screen container with its own content and key bindings.

- **Wizard**: a multi-step flow shown as a modal-style full-screen overlay. Two wizards exist: new-review (4 steps) and gateway-setup (4 steps). Each wizard has a step counter, a back/cancel/next button row, and a per-step content area.

- **Modal**: a centered overlay used for confirmations (delete, cancel review) and global search. Modals capture input until dismissed.

- **Recent review entry**: a record of a completed review, stored in the local database. Includes filename, date, mode, and color counts. The Home tab shows the five most recent entries.

- **Status bar item**: an element of the persistent status bar (current client, gateway status, pricing tier). Each item is updated reactively when its underlying state changes.

- **Description bar item**: the one-line description of the currently focused list item. Updates as focus moves.

- **List with type-to-filter**: a list widget that supports an inline text input. Typing filters the list in real time. Used for mode picker, file picker, playbook picker, client list, playbook list, past reviews list, and global search.

## Success Criteria

- **SC-001**: A user with no prior CLI experience can complete a full end-to-end contract review (open TUI → pick mode → pick document → run review → view result → export memo) in under five minutes, using only arrow keys, Enter, typing, and Tab.
- **SC-002**: A user can re-open any of their last five reviews from the Home tab in under 10 seconds, with a maximum of 3 keystrokes.
- **SC-003**: A user can configure all six gateway model slots in under three minutes, entering each provider's API key exactly once.
- **SC-004**: The TUI launches from a cold start in under 1 second on the reference 8 GB / 2-core machine.
- **SC-005**: The TUI's incremental memory overhead (above the one-shot CLI baseline) stays under 50 MB on the reference machine, keeping the total peak under the 100 MB target (110 MB floor) defined in the constitution.
- **SC-006**: Every existing CLI subcommand continues to pass its existing test suite with zero changes required.
- **SC-007**: 100% of PII-stripping rules from the one-shot CLI apply unchanged when a review is run from the TUI; no document text containing PII ever reaches an external API call.
- **SC-008**: 90% of test users can find a specific review from a list of 20+ past reviews using global search (`/`) in under 15 seconds.

## Assumptions

- **Target users**: non-technical users who can use a terminal at a basic level (typing, arrow keys) but not necessarily command-line arguments and flags. Power users continue to use one-shot CLI commands for scripts and CI.
- **Terminal compatibility**: standard xterm-compatible terminals with at least 16 colors and basic mouse support. The TUI does not require a specific terminal emulator.
- **Session scope**: the TUI is a single-user, single-session application. Multiple concurrent sessions on the same machine are not supported in v1.
- **Existing review pipeline**: the TUI reuses the existing three-agent review pipeline (extraction, QA verification, comparison) and the existing playbook format without modification. The TUI is a presentation layer.
- **Pricing tier**: pricing is not implemented in v1. The status bar and About section reserve a slot for it, marked as "—" (em-dash) and labeled "not available yet".
- **No new third-party dependencies**: the TUI is built on Textual, which uses the same dependency family as `rich` (already in `pyproject.toml`). Adding `textual` to `pyproject.toml` is the only dependency change required.
- **Backwards compatibility**: the TUI does not change the public CLI surface. All existing subcommands, flags, exit codes, and output formats remain stable. The TUI is additive.
- **Concurrent reviews**: only one review can be in progress at a time per TUI session. Cancelling a review discards partial results.
- **File picker security**: the file picker cannot navigate above the user's home directory in v1; restricting to the user's CWD or below is out of scope.
- **Bulk operations**: bulk reassign of provider across multiple slots, bulk import of playbooks, and bulk delete of clients are not supported in v1.
- **Collaborative features**: no multi-user, no real-time sync, no shared sessions in v1.
- **Accessibility scope**: The TUI is keyboard-navigable in v1. Screen reader support is not implemented in v1 due to fragmented terminal screen reader support across platforms. The About section of the TUI states this limitation so users with assistive technology needs are not surprised. This is a candidate for v2 if user demand warrants the engineering investment.
- **Tier terminology**: "Privacy tier" refers to the constitutional data-flow classification (maximum / balanced / performance — see `.specify/memory/constitution.md` Principle I and the Privacy Tier section). "Pricing tier" refers to a not-yet-defined commercial pricing model. They are independent concepts and the TUI MUST label and slot them separately. An earlier draft of this spec conflated them by listing "developer / standard / pro" under FR-046; this has been corrected.
- **Empty-state messaging**: All empty states in the TUI follow a consistent pattern: a one-line friendly message that tells the user the current state ("No reviews yet", "No reviews for this client yet", "No clients yet") and the next action ("Start one with [New review]", "Add one with [+ Add client]"). Empty states MUST be actionable, never just blank tables or generic "(no items)" text.
