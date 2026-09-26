# Feature Specification: Config + Storage Foundation

**Feature Branch**: `001-config-storage-foundation`

**Created**: 2026-06-24

**Status**: Draft

**Input**: User description: "Phase 1 from build order roadmap: config.yml loader, auth.json handler, SQLite schema for main DB and review DB"

## Clarifications

### Session 2026-06-24

- Q: What timezone does "reset at midnight" for daily cost limits use? → A: System local time.
- Q: How should auth.json permissions be handled on Windows? → A: Warning only, no enforcement.
- Q: Should operational logging exist in Phase 1? → A: Yes — log to file by default, DEBUG level via `--debug` flag.
- Q: When do SQLite migrations run? → A: On every command invocation.
- Q: Should the Review entity have explicit lifecycle states? → A: Yes — status column with `in_progress` and `completed`.
- Q: Should the shared_positions table be in Phase 1? → A: No — defer to Phase 7 (Playbook).
- Q: Is the model_registry_refresh_days config field needed in Phase 1? → A: Keep the field but mark it inactive until Phase 4 (AI Gateway).
- Q: Should client delete support --force? → A: Yes.
- Q: What happens to stale session data after a crash? → A: N/A — no session concept; review data is per-review, not per-session.
- Q: Should review processing data persist between CLI sessions? → A: Yes — chunks, vectors, and graph data live in a per-review DB, not a session DB.
- Q: What happens when a config value is missing at one priority level in the hierarchy (FR-008)? → A: Fall through to the next level. Each level overrides the one below it, missing keys pass through.
- Q: When is the per-review SQLite DB created (FR-010)? → A: When the review record is first created in the main `reviews` table — the directory and review.db are created at that point.
- Q: What happens if an SQLite migration fails mid-way (FR-011)? → A: Rollback and refuse to run — version stays unchanged, app exits with code 5. User must fix the migration file or restore from backup.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First-Time Setup (Priority: P1)

A lawyer installs openreview and runs their first command. The system creates a default `config.yml` with sensible defaults (local Ollama models, balanced privacy tier, $1.00 per-review cost limit) and an empty `auth.json` with secure permissions. The lawyer sees their configuration via `openreview config show` and can add API keys or adjust settings. Once later phases ship the review pipeline, no manual config setup will be needed.

**Why this priority**: Without a working config, no other feature can run. This is the foundation for all subsequent phases.

**Independent Test**: Can be fully tested by running `openreview --version` on a fresh install and verifying config files are created with correct defaults and permissions.

**Acceptance Scenarios**:

1. **Given** a fresh install with no config files, **When** the user runs any openreview command, **Then** the system creates `~/.config/openreview/config.yml` (or `%APPDATA%\openreview\config.yml` on Windows) with default values from the Defaults Table in Configuration.md
2. **Given** a fresh install, **When** config files are created, **Then** `auth.json` has file permissions `600` (owner read/write only on Unix) or equivalent restricted permissions on Windows
3. **Given** a fresh install, **When** config files are created, **Then** the main SQLite database `openreview.db` is initialized with schema version 1 and tables: `schema_version`, `clients`, `reviews` (with `status` column), `review_diffs`, `cost_logs`

---

### User Story 2 - View and Modify Configuration (Priority: P1)

A lawyer wants to see their current configuration or change a specific setting (e.g., switch privacy tier from balanced to maximum). They use CLI commands to inspect and modify config values without manually editing YAML.

**Why this priority**: Configuration visibility and modification is essential for daily use. Lawyers need to understand what's configured and change it safely.

**Independent Test**: Can be fully tested by running `openreview config show`, `openreview config get privacy.tier`, and `openreview config set privacy.tier maximum`, verifying each command produces correct output and updates the config file.

**Acceptance Scenarios**:

1. **Given** a valid config.yml exists, **When** the user runs `openreview config show`, **Then** the system displays the full merged configuration (file + env vars) in human-readable format
2. **Given** a valid config.yml exists, **When** the user runs `openreview config get privacy.tier`, **Then** the system displays the current value of that setting (e.g., "balanced")
3. **Given** a valid config.yml exists, **When** the user runs `openreview config set privacy.tier maximum`, **Then** the system updates config.yml, creates a backup `config.yml.bak`, and confirms the change
4. **Given** an invalid config value is provided, **When** the user runs `openreview config set`, **Then** the system displays a clear error message with valid options and does not modify the config file

---

### User Story 3 - Environment Variable Overrides (Priority: P2)

A lawyer working in CI or on a shared machine wants to temporarily override configuration without editing files. They set environment variables (e.g., `OPENREVIEW_PRIVACY_TIER=maximum`, `OPENAI_API_KEY=sk-...`) that take precedence over config files for that session.

**Why this priority**: Environment variable overrides are essential for CI/CD pipelines, shared machines, and temporary provider switches. They enable automation and flexibility without file editing.

**Independent Test**: Can be fully tested by setting `OPENREVIEW_PRIVACY_TIER=maximum` and running `openreview config show`, verifying the env var value is displayed instead of the file value.

**Acceptance Scenarios**:

1. **Given** config.yml has `privacy.tier: balanced` and env var `OPENREVIEW_PRIVACY_TIER=maximum` is set, **When** the user runs `openreview config show`, **Then** the system displays `privacy.tier: maximum` (env var wins)
2. **Given** auth.json has an OpenAI key and env var `OPENAI_API_KEY` is set to a different key, **When** the system needs the OpenAI key, **Then** it uses the env var value (env var wins)
3. **Given** no env vars are set, **When** the user runs any command, **Then** the system uses values from config.yml and auth.json (file values win)

---

### User Story 4 - Cost Tracking (Priority: P2)

A lawyer runs a review and wants to see how much it cost. The system logs every API call (model, provider, tokens, cost) to the SQLite database and enforces daily and per-review cost limits.

**Why this priority**: Cost tracking is essential for budget control. Lawyers need to know what they're spending and prevent runaway costs.

**Independent Test**: Can be fully tested by running a mock review (with mocked API calls) and verifying cost logs are written to the database and cost limits are enforced.

**Acceptance Scenarios**:

1. **Given** a review is in progress, **When** an API call completes, **Then** the system logs the model, provider, prompt tokens, completion tokens, and cost (in cents) to the `cost_logs` table
2. **Given** the daily cost limit is 1000 cents ($10.00) and the lawyer has already spent 950 cents today, **When** they start a new review, **Then** the system allows it (under limit)
3. **Given** the daily cost limit is 1000 cents and the lawyer has already spent 1000 cents today, **When** they start a new review, **Then** the system exits with code 6 and a clear message: "Daily cost limit reached ($10.00). Reset at local midnight or increase limit in config.yml"
4. **Given** the per-review cost limit is 100 cents ($1.00) and a review has already cost 95 cents, **When** the next API call would cost 10 cents, **Then** the system exits with code 6 and a clear message: "Per-review cost limit reached ($1.00). Increase limit in config.yml or use a cheaper model"

---

### User Story 5 - Client Management (Priority: P3)

A lawyer wants to organize their reviews by client. They can create, list, and delete clients. Each client gets a unique slug (e.g., "acme") that's used in review IDs and playbook paths.

**Why this priority**: Client management is useful for organization but not blocking for Phase 1. A lawyer could technically run reviews without clients (using a default client), but client management makes the system more usable.

**Independent Test**: Can be fully tested by running `openreview client add acme "Acme Corp"`, `openreview client list`, and `openreview client delete acme`, verifying each command works correctly.

**Acceptance Scenarios**:

1. **Given** no clients exist, **When** the user runs `openreview client add acme "Acme Corp"`, **Then** the system creates a client record with id="acme", name="Acme Corp" in the `clients` table
2. **Given** clients exist, **When** the user runs `openreview client list`, **Then** the system displays all clients with their id, name, and creation date
3. **Given** a client exists with no reviews, **When** the user runs `openreview client delete acme`, **Then** the system deletes the client record
4. **Given** a client exists with reviews, **When** the user runs `openreview client delete acme`, **Then** the system exits with an error: "Cannot delete client 'acme' — 5 reviews exist. Delete reviews first or use --force"

---

### Edge Cases

- What happens when config.yml is manually edited with invalid YAML syntax? The system displays a clear error with line number and refuses to load the config.
- What happens when auth.json has incorrect permissions on Unix (e.g., 644 instead of 600)? The system displays a warning: "auth.json has insecure permissions (644). Run: chmod 600 ~/.config/openreview/auth.json" but continues (non-fatal).
- What happens on Windows? The system displays a warning: "auth.json contains API keys. Ensure the file is stored in a secure location" — no permission enforcement.
- What happens when the SQLite database is corrupted? The system displays an error and suggests restoring from backup or deleting the DB to start fresh.
- What happens when a review process crashes mid-run? On the next run, the system finds the review with `status: in_progress` and resumes from the last logged step — processing data persists in the review's DB.
- What happens when the config directory is not writable (e.g., permissions issue)? The system displays a clear error with the path and suggests fixing permissions.
- What happens when an environment variable has an invalid value (e.g., `OPENREVIEW_PRIVACY_TIER=invalid`)? The system displays an error with valid options and exits with code 5.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST load configuration from `config.yml` on every command invocation
- **FR-002**: System MUST validate config.yml against the Pydantic model defined in Configuration.md (version field, privacy, gateway.models, gateway.fallback, gateway.cost_limits, storage sections)
- **FR-003**: System MUST create config.yml with default values and auth.json (empty, chmod 600 on Unix) if they do not exist (first-time setup)
- **FR-004**: System MUST load API keys from `auth.json` (flat key-value JSON format)
- **FR-005**: System MUST verify auth.json has file permissions `600` on Unix systems and display a warning if permissions are insecure. On Windows, the system MUST display a warning that API keys are present but MUST NOT attempt to enforce permissions
- **FR-006**: System MUST support environment variable overrides for all config.yml fields using the `OPENREVIEW_*` prefix (e.g., `OPENREVIEW_PRIVACY_TIER`, `OPENREVIEW_RETRIES`)
- **FR-007**: System MUST support environment variable overrides for provider API keys (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) that take precedence over auth.json
- **FR-008**: System MUST resolve configuration using the priority hierarchy: CLI flags > CLI arguments > environment variables > config.yml > auth.json > built-in defaults
- **FR-009**: System MUST create the main SQLite database `openreview.db` with schema version 1 and tables: `schema_version`, `clients`, `reviews` (with `status` column: `in_progress` or `completed`), `review_diffs`, `cost_logs`. The `shared_positions` table is deferred to Phase 7 (Playbook)
- **FR-010**: System MUST create a per-review SQLite database at `~/.config/openreview/reviews/<review_id>/review.db` (or platform-equivalent) with tables: `chunks`, `graph_nodes`, `graph_edges`. This database persists until the user deletes the review — it is NOT deleted on CLI exit
- **FR-011**: System MUST support forward-only schema migrations via a `schema_version` table and `.sql` migration files. Migrations MUST run on every command invocation (check version, apply pending)
- **FR-012**: System MUST provide CLI commands: `openreview config show`, `openreview config get <key>`, `openreview config set <key> <value>`
- **FR-013**: System MUST create a backup `config.yml.bak` before every `config set` operation
- **FR-014**: System MUST validate config values on `config set` and reject invalid values with clear error messages
- **FR-015**: System MUST log every API call (model, provider, prompt_tokens, completion_tokens, cost_cents, review_id, timestamp) to the `cost_logs` table
- **FR-016**: System MUST enforce per-review cost limits (exit code 6 when limit reached)
- **FR-017**: System MUST enforce daily cost limits (exit code 6 when limit reached)
- **FR-018**: System MUST use platform-aware paths: `~/.config/openreview/` on Linux/macOS, `%APPDATA%\openreview\` on Windows (via `platformdirs` library)
- **FR-019**: System MUST display clear error messages with exit codes for all configuration and storage errors (exit code 5 for config errors, exit code 6 for cost limit errors)
- **FR-020**: System MUST log operational information to `~/.config/openreview/logs/openreview.log` (or platform-equivalent) using stdlib logging. The `--debug` flag MUST enable DEBUG-level logging
- **FR-021**: System MUST support `--force` flag on `openreview client delete <client>` to bypass the "has reviews" check and delete the client and all associated reviews

### Key Entities

- **Client**: Represents a lawyer's client (e.g., "Acme Corp"). Key attributes: id (slug), name, created_at, updated_at. Relationships: has many reviews, has one playbook DB.
- **Review**: Represents a single contract review. Key attributes: id, client_id, contract_path, contract_hash, playbook_version, mode, status (in_progress/completed), total_questions, deviations, cost_cents, created_at, memo_path. Relationships: belongs to one client, has many review_diffs, has many cost_logs, has one review DB (chunks/vectors/graph).
- **ReviewDiff**: Represents a per-question comparison result. Key attributes: id, review_id, question_key, contract_answer, playbook_value, status (match/deviation/missing), created_at. Relationships: belongs to one review.
- **CostLog**: Represents an immutable cost tracking record for one API call. Key attributes: id, review_id, model, provider, prompt_tokens, completion_tokens, cost_cents, created_at. Relationships: belongs to one review.
- **Chunk**: Represents a hierarchical chunk of a contract document (persists with review). Key attributes: id, clause_id, text, vector (embedding), level, parent_id, node_type. Relationships: belongs to one review.
- **GraphNode**: Represents a node in the contract graph (persists with review). Key attributes: id, review_id, type, label, text, metadata. Relationships: belongs to one review, has many edges.
- **GraphEdge**: Represents a relationship between two graph nodes (persists with review). Key attributes: id, source_id, target_id, relation, metadata. Relationships: connects two graph nodes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can run their first openreview command on a fresh install and have a working config created in under 5 seconds
- **SC-002**: Configuration validation errors are displayed with clear messages (field name, problem, valid options, fix suggestion) in under 1 second
- **SC-003**: Environment variable overrides take effect immediately without requiring config file edits or restarts
- **SC-004**: Cost tracking logs are written to the database within 100ms of each API call completion
- **SC-005**: Cost limit enforcement prevents any API call that would exceed the limit (no overspending)
- **SC-006**: Config file operations (show/get/set) complete in under 500ms
- **SC-007**: SQLite database initialization (schema creation) completes in under 2 seconds on the reference hardware (8 GB RAM, 2-core CPU)
- **SC-008**: Platform-aware path resolution works correctly on Linux, macOS, and Windows without manual configuration

## Assumptions

- Users have Python 3.12 or later installed on their system
- Users have write permissions to the config directory (`~/.config/openreview/` or `%APPDATA%\openreview\`)
- The `PyYAML` and `platformdirs` libraries are available as runtime dependencies (will be added via `uv add`)
- SQLite is available via Python's stdlib `sqlite3` module (no additional dependency needed)
- File permissions (chmod 600) work on Unix systems; Windows uses equivalent restricted permissions via `os.chmod` or platform-specific APIs
- Environment variables are set in the shell before running openreview commands (not dynamically during execution)
- The config directory structure (`~/.config/openreview/`, `playbooks/`, `reviews/`, `logs/`) is created automatically on first run. Per-review DBs are created under `reviews/<review_id>/` on demand
- Schema migrations are forward-only; rollback is done by restoring from backup (not implemented in Phase 1)
- Cost tracking uses integer cents (not floating-point dollars) to avoid precision issues
- Platform-aware paths use the `platformdirs` library for cross-platform config directory resolution
- Daily cost limits reset at the system's local midnight time. No timezone configuration is needed
- Operational logging uses Python's stdlib `logging` module, writing to a file at `~/.config/openreview/logs/openreview.log` by default
- `gateway.model_registry_refresh_days` is defined in the config schema but is inactive until Phase 4 (AI Gateway) ships — no refresh logic runs in Phase 1
