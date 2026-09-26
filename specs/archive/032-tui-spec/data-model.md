# Data Model: Interactive TUI

This is a presentation-layer feature. The TUI does NOT introduce new persistent storage. All data shown in the TUI is read from existing tables in the local SQLite database (`openreview.db`) or existing in-memory state from the running CLI session.

## Existing entities (read-only from TUI)

The TUI reads from these existing entities. No schema changes for v1.

### Review (existing)
- **Source**: `openreview_cli.review.models.ReviewReport`
- **Read by**: Home tab (recent reviews list), Review tab (past reviews), Result screen
- **Fields used**: `document_path`, `completed_at`, `summary.green_count`, `summary.amber_count`, `summary.red_count`, `summary.total`, `mode`

### Client (existing)
- **Source**: `openreview_cli.storage.database.clients` table
- **Read by**: Clients tab, Settings tab (current client), Status bar
- **Fields used**: `id`, `name`, `created_at`, `updated_at`
- **Written by**: Add/Edit client form (uses existing `add_client`, `update_client` functions)

### Playbook (existing)
- **Source**: `openreview_cli.storage.database.playbooks` table
- **Read by**: Playbooks tab, Review wizard (step 3)
- **Fields used**: `id`, `mode`, `version`, `is_current`, `description`, `categories`, `default_position`
- **Written by**: Import form (uses existing `import_playbook_yaml`)

### Gateway slot (existing)
- **Source**: `openreview_cli.gateway.router` (6 slots: reasoning, extraction, embedding, reranking, graph, grounding)
- **Read by**: Status bar, Settings > Gateway
- **Written by**: Gateway wizard (uses existing `set_config_value`)

### Auth key (existing)
- **Source**: `~/.config/openreview/auth.json` (chmod 600)
- **Read by**: Gateway wizard (step 4 — skip if key exists)
- **Written by**: Gateway wizard (when user enters new key)

### Privacy tier (existing)
- **Source**: `.specify/memory/constitution.md` Principle I, `openreview_cli.config.tier_config` or equivalent config path
- **Values**: maximum | balanced | performance
- **Read by**: Status bar (FR-046a), About section

### Pricing tier (placeholder for v1)
- **Source**: configuration (not yet implemented per spec assumptions)
- **Display**: "—" (em-dash) in status bar and About section, per spec FR-037
- **Note**: Distinct from privacy tier. The spec explicitly separates these two concepts. Pricing tier implementation is deferred.

## Session-scoped entities (in-memory only)

These live only for the duration of one TUI session. They are NOT persisted.

### TuiSession
- **Lifecycle**: created on `app.run()` start, destroyed on `app.exit()`
- **Fields**:
  - `current_client: str | None` — ID of the currently selected client, used in status bar
  - `last_review_id: str | None` — for "open last result" (though recent list shows it as first row instead)
  - `recent_reviews_cache: list[ReviewSummary]` — cached last 5 reviews
  - `gateway_health_cache: dict[str, SlotHealth]` — cached health check (refreshed on tab change)
  - `active_wizard: WizardState | None` — current wizard state if any

### WizardState
- **Lifecycle**: created when wizard opens, destroyed on wizard close
- **Fields**:
  - `kind: Literal["review", "gateway"]`
  - `current_step: int` (0-3)
  - `data: dict` — collected answers per step
  - `on_complete: Callable` — what to do when wizard finishes

## Validation rules

No new validation. TUI reuses existing validation in domain layer:
- Client ID format (lowercase, hyphens, no spaces) — enforced in form
- Playbook YAML schema — enforced at import
- API key format — verified by provider before save
- Document path exists and is readable — enforced at file picker

## Lifecycle / state transitions

TUI session:
```
launch → home tab (default) → user navigates → user quits → exit(0)
                ↓
                user triggers action → push modal/screen → user confirms/cancels → pop
                ↓
                user runs review → push progress screen → review completes → push result screen
                ↓
                user clicks Quit → push quit confirm modal → confirm → exit
```

Wizard:
```
[not started] → push wizard screen → step 0 → step 1 → step 2 → step 3 → [complete or cancel]
                                                              ↓
                                                              on complete: invoke on_complete(data), pop wizard
                                                              on cancel: discard data, pop wizard
```

## Cross-references

- Functional requirements: see spec.md FR-001 through FR-047
- Storage layer: `src/openreview_cli/storage/database.py` (no changes)
- Review pipeline: `src/openreview_cli/review/` (no changes)
- Gateway: `src/openreview_cli/gateway/` (no changes)
- PII: `src/openreview_cli/pii/` (no changes)
- TUI design artifacts: `TUI-Decisions.md`, `TUI-Tree.md` (in this directory)
