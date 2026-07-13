# Research: AI Gateway v2 Design Decisions

> Phase 0 research artifact for spec 033. Resolves all open questions from the draft findings at `draft/findings/ai-gateway-research.md` against the finalized spec. Each section documents a decision, its rationale (with source), and alternatives considered and rejected.

---

## R-1: Provider-First Config Format (opencode pattern)

**Decision**: v2 config uses provider-first format — top-level `providers` object maps provider names to `ProviderConfig` blocks (apiKey source, baseURL, enabled). Slots reference providers by name.

**Rationale**: Every reference tool organizes config around providers, not models (opencode, Aider, Cline, Continue, LiteLLM). Providers are the scarce resource (small number of API keys); models are abundant (each provider serves many). Grouping by provider avoids key duplication when multiple slots use the same provider. Matches user mental model: "I have an OpenAI key, I assign models from it to slots."

**Source**: [opencode.ai/docs/providers](https://opencode.ai/docs/providers); opencode uses `providers.<id>` blocks with `apiKey`, `baseURL`, and nested `models`. Spec FR-001–FR-004 codify this.

**Alternatives considered**:
- **Model-first (v1 current)**: Slots reference `provider/model` strings directly. Rejected because: key is duplicated across every slot using the same provider; no natural place for provider-level settings (baseURL, enabled flag); makes `gateway auth add` ambiguous (which provider gets the key?).
- **Array-of-models (Continue-style)**: JSON array of model entries each with `provider`, `model`, `apiKey`. Rejected because: duplicates keys for same provider across multiple entries; no shareable config (keys embedded in config file); harder to validate.
- **Aider-style (env vars only)**: No config file for providers, pure env vars. Rejected because: no persistent slot assignments; env vars don't survive shell restarts; no way to declare "I want slot X to use model Y from provider Z" without a file.

---

## R-2: OS Keyring with File Fallback

**Decision**: Three-tier auth resolution: env var > OS keyring > `auth.json` file. `keyring` library is optional — when absent or when OS keyring is unavailable (headless Linux), write to `auth.json` with chmod 600. One-time warning on fallback.

**Rationale**: Industry standard across CLI tools (GitHub CLI, AWS CLI, gcloud). OS keyring provides encrypted-at-rest storage without the user managing file permissions. The `keyring` library abstracts across macOS Keychain, Windows Credential Manager, and Linux Secret Service (dbus). Making it optional avoids breaking installs on minimal Docker images, CI/CD runners, and headless servers.

**Source**: [GitHub CLI auth discussion](https://github.com/cli/cli/discussions/12488); [WorkOS CLI auth best practices](https://workos.com/guide/best-practices-for-cli-authentication-a-technical-guide); spec FR-017–FR-020.

**Alternatives considered**:
- **`auth.json` only (current)**: Simpler — no dependency, no keyring calls. Rejected because: flat file on disk is less secure than encrypted keyring; users must trust their filesystem permissions; no platform-native MFA/biometric support.
- **Env vars only (Aider-style)**: Simplest possible. Rejected because: env vars don't persist across sessions; forces users to set env vars in every shell profile; no `auth list`/`auth remove` UX.
- **Platform-specific crypto wrappers**: Implement direct macOS Keychain API via ctypes, Windows Credential Manager via pywin32, Linux Secret Service via dbus. Rejected because: 3x the code, platform testing burden, higher maintenance cost. The `keyring` library is the battle-tested abstraction.

---

## R-3: JSON-Stdin Applier for CLI Setup

**Decision**: `openreview gateway setup` accepts a complete JSON config on stdin and applies it atomically. No interactive wizard in CLI mode. TUI wizard (spec 032) writes the same config files.

**Rationale**: Non-interactive setup required for agents and CI/CD pipelines (spec User Story 1, P1). JSON-pipe pattern is the simplest machine-parseable input format — no TTY, no prompts, no special protocol. Atomic write prevents partial config from failed runs. Dry-run mode (`--dry-run`) validates without writing.

**Source**: [Cline headless mode](https://cline.bot) — decoupled setup from execution; spec FR-005–FR-008.

**Alternatives considered**:
- **Interactive wizard only (current, broken)**: `questionary`-based, crashes in non-TTY. Rejected because: spec requires 100% non-interactive operation for all CLI commands (FR-030).
- **Flag-based setup (`--provider openai --api-key ...`)**: Too many flags for 9 providers × 6 slots × optional settings. Rejected because: combinatorial flag explosion; harder to document and validate; non-atomic (must be parsed per-flag).
- **YAML stdin**: Alternative format. Rejected because: JSON is natively parseable with Python stdlib, has clear schema validation via Pydantic, and matches the config file format. YAML adds a parsing dependency (already have pyyaml but JSON is simpler).

---

## R-4: Short-Name Model Resolution

**Decision**: Resolver maps short names (e.g., `gpt-4o`, `sonnet`) to full `provider/model` strings. Resolution order: (1) if input contains `/`, pass through as explicit `provider/model`; (2) scan configured providers in priority order (direct > proxy); (3) first match wins. Error with listed available models on no match.

**Rationale**: Primary UX improvement for both agents and humans (spec User Story 3, P1). Removes need to remember `provider/model` format. Direct provider preference (OpenAI over OpenRouter for `gpt-4o`) matches user expectation: if you have the key, use the direct endpoint (cheaper, lower latency).

**Source**: Aider model aliases (`--sonnet` → full string), opencode's provider-block scoped names; spec FR-011–FR-013.

**Alternatives considered**:
- **Explicit `provider/model` only (current)**: No resolution. Rejected because: spec requires short-name support; every user reference tool provides aliases.
- **User-defined aliases only**: Let users define their own alias map in config. Rejected because: spec YAGNI — the static registry (33 models) provides sufficient resolution. User aliases can be added when users request them.
- **Fuzzy match (Levenshtein)**: Accept typos. Rejected because: spec doesn't require it; YAGNI — first version should be strict match with helpful error listing available models.

---

## R-5: Nullable `session_id` (Not New Sessions Table)

**Decision**: Make `cost_logs.session_id` nullable (remove FK constraint). Insert session rows lazily when session context exists. Cost write always succeeds regardless of session availability.

**Rationale**: Existing code has `cost_logs.session_id` as NOT NULL FK to a `sessions` table, but no session row is created before cost logging. This causes `sqlite3.IntegrityError` on every cost write. Making the FK nullable is the minimal fix — it unblocks all cost tracking immediately (spec User Story 7, P2). A session table exists as a FK target for when sessions are tracked, but cost records don't require one.

**Source**: spec FR-021–FR-022; Helicone session tracking pattern; research section 3.3 (three fix approaches evaluated).

**Alternatives considered**:
- **Create session row first (research recommendation #1)**: Generate `session_id = uuid.uuid4()`, INSERT into sessions, then log costs. Rejected for Phase A because: requires lifecycle changes throughout the router (all call sites must know the session). The nullable FK fix is smaller, backward-compatible, and unblocks cost tracking immediately. Session pre-creation can be layered on later.
- **INSERT OR IGNORE on sessions (research #3)**: Cheap, works if session_id is known. Rejected because: same lifecycle issue as #1 — callers must pass a session_id. Nullable FK is simpler.

---

## R-6: Hard Break on Config Format

**Decision**: Gateway v2 reads only v2 config format. No auto-detection of v1 format. Migration provided via `openreview migrate config` command. v1 config files produce a clear error: "Config format version 1 is no longer supported. Run `openreview migrate config` to upgrade."

**Rationale**: Spec explicitly requires "hard break on config format (single user, no backward compat)." This simplifies the gateway loader — no version detection, no format negotiation, no legacy path. Single user means no deployment where a rolling migration is needed. The migration command converts v1 → v2 in one step; auth.json is untouched.

**Source**: Spec User Description: "Hard break on config format (single user, no backward compat)." FR-025–FR-027.

**Alternatives considered**:
- **Auto-migrate on v1 load (research recommendation Q1)**: Read v1, convert to v2 in memory, warn user. Rejected because: spec explicitly requires hard break; auto-migration delays user action, leading to confusion when the deprecation window closes.
- **Dual-format support**: Read both v1 and v2. Rejected because: violates spec's hard break requirement; adds maintenance burden of two code paths for no spec-approved reason.

---

## R-7: No LiteLLM Proxy Mode

**Decision**: Gateway remains direct SDK mode. No LiteLLM proxy server, no multi-user gateway. Single-user CLI only.

**Rationale**: Spec explicitly states: "No LiteLLM proxy mode. The gateway remains a direct single-user CLI tool. No LiteLLM proxy server or multi-user gateway server is built." Constitution Principle II (Local-First, CLI-Only) forbids servers. The research confirms SDK mode is correct for single-user CLI.

**Source**: Spec Assumptions: "No LiteLLM proxy mode." Constitution Principle II. Research section 2.5.

**Alternatives considered**:
- **LiteLLM proxy as optional mode**. Rejected because: constitution forbids server-mode operation; spec explicitly rejects it; enterprise multi-user can deploy LiteLLM proxy separately (same dep stack, different mode).

---

## R-8: TUI Integration (Spec 032)

**Decision**: CLI is non-interactive. The TUI (spec 032, Settings > Gateway > Run setup wizard) writes to the same `config.yml` and `auth.json` files. The CLI wizard (`wizard.py`) is deprecated but kept for TUI compat — it is no longer called from CLI commands.

**Rationale**: Clean separation of concerns — spec 032 owns human-friendly setup, spec 033 owns agent-friendly CLI. Shared files mean no sync problems. No CLI wizard is needed.

**Source**: Spec Assumptions: "TUI per spec 032 handles human setup. The TUI wizard (Settings > Gateway > Run setup wizard) writes to the same config.yml and auth.json files. CLI commands are the non-interactive counterpart. No CLI wizard is needed."

**Alternatives considered**:
- **CLI has its own wizard**. Rejected because: spec assigns TUI responsibility to spec 032. CLI wizard would duplicate effort and risk inconsistent behavior.
- **Deprecate wizard.py entirely**. Rejected because: TUI (spec 032) still needs it. Keep as shared library, not CLI entry point.

---

## R-9: Cost Tracking Schema Choice (SQLite, Not Remote)

**Decision**: Cost tracking stays local SQLite. No remote cost aggregation, no HTTP cost logging endpoint. All cost data lives in `openreview.db`.

**Rationale**: Constitution Principle II (Local-First) forbids external services for operational data. SQLite is already the project's storage layer. Cost data is inherently local — there is no multi-user or cloud reporting requirement in scope.

**Source**: Constitution Principle II; existing `cost_logs` table in `database.py`; spec FR-021–FR-022.

**Alternatives considered**:
- **Remote cost aggregation endpoint**: Report costs to a cloud service for dashboards. Rejected because: constitution forbids phone-home telemetry; spec does not require it.
- **CSV file logging**: Append-only CSV for cost records. Rejected because: no query support (filter by session, today), no FK relationships, harder to maintain. SQLite is already present.

---

## R-10: Model Resolution Priority Order (Direct > Proxy)

**Decision**: When multiple providers serve the same model short name, resolver prefers the direct provider (e.g., OpenAI over OpenRouter for `gpt-4o`). Priority order: OpenAI > Anthropic > Google > Groq > OpenRouter > Others. User can override with explicit `provider/model`.

**Rationale**: Direct providers are cheaper (no proxy markup), lower latency (no intermediary), and more reliable (one less hop). The priority order matches user expectation: "if I have the key, use it directly." Explicit override always wins.

**Source**: Spec FR-012 (prefer direct provider), FR-013 (explicit override). Research section 6.4 (resolution algorithm).

**Alternatives considered**:
- **First-configured wins**: Whatever provider the user configured first. Rejected because: inconsistent behavior between users; a user who adds OpenRouter before OpenAI would pay proxy markup for no reason.
- **User-configurable priority order**. Rejected for now: spec doesn't require it; YAGNI. Can be added when users request provider priority control.
- **Cheapest first**: Query LiteLLM pricing table, pick cheapest. Rejected because: pricing data may be stale; adds latency to resolution; spec requires direct preference, not cheapest.
