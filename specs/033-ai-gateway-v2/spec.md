# Feature Specification: AI Gateway v2 Redesign

**Feature Branch**: `033-ai-gateway-v2`

**Created**: 2026-07-13

**Status**: Draft

**Input**: User description: "Redesign the AI gateway to support both human (TUI per spec 032) and agent (CLI) use cases. Fix the 5 gaps from the first integration test. Add OS keyring, JSON-stdin setup, short-name model resolution, model discovery, cost tracking fix, and grounding slot schema. Hard break on config format (single user, no backward compat)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Agent configures the gateway non-interactively (Priority: P1)

An AI agent (or CI/CD pipeline) needs to set up the gateway without human intervention. It pipes a JSON config to `openreview gateway setup` and the gateway applies it: providers with their API keys, slots with their model assignments. Exit 0. No TTY prompts, no interactive questions. After setup, `gateway status --format json` returns machine-parseable state.

**Why this priority**: Agents and CI pipelines are primary consumers of the CLI. Without non-interactive setup, the gateway is unusable in automation contexts. This is the gateway's most fundamental agent-facing feature.

**Independent Test**: A test script can pipe a valid JSON config to `openreview gateway setup`, verify exit code 0, then run `openreview gateway status --format json` and confirm the configured providers and slots appear in the output.

**Acceptance Scenarios**:

1. **Given** a valid JSON config piped to stdin, **When** the agent runs `openreview gateway setup`, **Then** the gateway applies all providers and slots atomically and exits with code 0.
2. **Given** the config is applied, **When** the agent runs `openreview gateway status --format json`, **Then** the JSON output contains all configured providers and slots with their current assignments.
3. **Given** an invalid JSON config (missing required field), **When** the agent runs `openreview gateway setup`, **Then** the gateway writes no partial config and exits with code 1 with an error message naming the failed field.
4. **Given** no TTY and no stdin piped, **When** the agent runs `openreview gateway setup`, **Then** the gateway prints usage and exits non-zero with a message pointing to `openreview gateway setup --help`.

---

### User Story 2 — Agent lists models reachable with current keys (Priority: P1)

The agent has set up 2 providers (OpenRouter + Voyage) but does not know what models are reachable. It runs `openreview models available` (or `gateway models available`) and gets a list of (model_name, provider, slot_compatibility) tuples for every model the registry has AND that the user has keys for. The agent picks one and configures a slot.

**Why this priority**: Without model discovery, users must guess model strings or consult external docs. This is the gateway's discoverability feature — it answers "what can I use right now?".

**Independent Test**: After configuring two providers, the agent runs `openreview models available` and receives a non-empty list of models. Each entry includes a short name and at least one provider that can serve it.

**Acceptance Scenarios**:

1. **Given** two providers configured (OpenRouter + Voyage), **When** the agent runs `openreview models available`, **Then** the output lists all models from the registry that are served by these two providers.
2. **Given** a provider configured but unreachable (e.g. invalid key), **When** the agent runs `openreview models available`, **Then** the models from that provider are still listed (key validation is not a prerequisite for discovery).
3. **Given** no providers configured, **When** the agent runs `openreview models available`, **Then** the output is empty with a message "No API keys configured. Run `openreview gateway setup` to add providers."

---

### User Story 3 — Agent sets a slot by short name (Priority: P1)

The agent runs `openreview set reasoning gpt-4o` and the gateway resolves `gpt-4o` to the right provider based on available keys (OpenAI direct if user has `OPENAI_API_KEY`, else OpenRouter). No model string prefix required. `gateway test reasoning` confirms the call works.

**Why this priority**: Short-name resolution removes the need to remember `provider/model` format. It is the primary UX improvement for both agents and humans.

**Independent Test**: After configuring the OpenAI provider, the agent runs `openreview set reasoning gpt-4o` and `openreview test reasoning` returns a successful response from OpenAI, without ever typing `openai/gpt-4o`.

**Acceptance Scenarios**:

1. **Given** OpenAI is configured with a valid key, **When** the agent runs `openreview set reasoning gpt-4o`, **Then** the gateway resolves `gpt-4o` to `openai/gpt-4o` and configures the reasoning slot.
2. **Given** both OpenAI direct and OpenRouter are configured, **When** the agent runs `openreview set reasoning gpt-4o`, **Then** the gateway prefers the direct provider (OpenAI) over the proxy (OpenRouter).
3. **Given** the user explicitly specifies `openai/gpt-4o`, **When** the agent runs `openreview set reasoning openai/gpt-4o`, **Then** the gateway uses the explicit `provider/model` string without short-name resolution.

---

### User Story 4 — All CLI commands are agent-friendly (Priority: P1)

Every gateway CLI command works non-interactively. No TTY prompts. Errors are structured with machine-parseable output on request. All commands have `--format text|json`. Exit codes distinguish user error, config error, and provider error.

**Why this priority**: If any CLI command requires a TTY or produces unstructured output, agents cannot reliably use it. This is a correctness requirement for the entire gateway surface.

**Independent Test**: Every gateway subcommand can be run in a non-TTY context (e.g. piped through `echo | openreview ...`) without hanging, prompting, or producing parse-unfriendly output. A shell script can call each subcommand and branch on the exit code.

**Acceptance Scenarios**:

1. **Given** any gateway CLI command, **When** run with `--format json`, **Then** the output is valid JSON parsable by any JSON library.
2. **Given** any gateway CLI command that encounters an error, **When** run, **Then** it exits with a non-zero code (1=user error, 2=config error, 3=provider error).
3. **Given** any gateway CLI command, **When** run in a non-TTY context without piped stdin, **Then** it does not block or prompt for input.

---

### User Story 5 — User upgrades to v2 config without losing work (Priority: P2)

A user has a v1 `config.yml` with 5 slots configured. They upgrade. The `openreview migrate config` command reads the v1 config and writes a v2 config (provider-first format). The user's API keys in `auth.json` are preserved unchanged. After migration, the gateway works as before but with the new schema.

**Why this priority**: Migration is essential for existing users but does not affect new users. It is a one-time transitional feature.

**Independent Test**: A test can create a v1 config with known slot assignments, run `openreview migrate config`, and verify the resulting v2 config has the same effective model assignments and that `auth.json` is untouched.

**Acceptance Scenarios**:

1. **Given** a v1 config.yml with 5 slots configured, **When** the user runs `openreview migrate config`, **Then** the v2 config.yml contains the same slot assignments in the new provider-first format.
2. **Given** a v1 auth.json with 3 provider keys, **When** migration runs, **Then** auth.json is not modified (same content, same permissions).
3. **Given** an already-v2 config.yml, **When** the user runs `openreview migrate config`, **Then** the command is a no-op and exits with code 0.

---

### User Story 6 — API keys are stored in the OS keyring when available (Priority: P2)

A user installs the tool on a new Mac. They add their OpenRouter key via `openreview auth add openrouter sk-or-...`. The key is saved to the macOS Keychain (via the `keyring` library). On Linux, it goes to the Secret Service. On Windows, to Credential Manager. The `auth.json` file is no longer the primary store. If the `keyring` library is not installed, the tool falls back to `auth.json` with `chmod 600`.

**Why this priority**: OS keyring integration improves security for API keys — the most sensitive data the tool manages. This is a best-practice security improvement.

**Independent Test**: On a machine with `keyring` installed, running `openreview auth add openrouter sk-or-...` stores the key in the OS keyring. Listing auth shows the provider is configured. Removing it deletes from the keyring.

**Acceptance Scenarios**:

1. **Given** the `keyring` library is installed, **When** the user runs `openreview auth add openrouter sk-or-...`, **Then** the key is stored in the OS keyring and NOT written to `auth.json`.
2. **Given** the `keyring` library is not installed, **When** the user runs `openreview auth add openrouter sk-or-...`, **Then** the key is stored in `auth.json` with file permissions 600 and a one-time warning is printed.
3. **Given** the user runs `openreview auth list`, **When** keys exist in the keyring or auth.json, **Then** the output shows provider names with key sources ("keyring", "file") without revealing the full key value.
4. **Given** the user runs `openreview auth remove openrouter`, **When** the key exists in the keyring or auth.json, **Then** it is deleted from whichever store it came from.

---

### User Story 7 — Cost tracking works end-to-end (Priority: P2)

The user runs a review. After the review, `openreview gateway costs --today` shows the actual tokens used and estimated cost. The cost record references the session that generated it (no FK constraint failure). The user can filter by session ID: `openreview gateway costs --session <id>`.

**Why this priority**: Cost tracking is essential for users who want to monitor spending. The FK bug blocks the entire feature — fixing it is a correctness requirement.

**Independent Test**: A test can run a gateway call that generates cost data, then query `openreview gateway costs --today` and verify the cost record exists with non-zero token counts and no FK errors in the application logs.

**Acceptance Scenarios**:

1. **Given** a review has been run and generated API calls, **When** the user runs `openreview gateway costs --today`, **Then** the output shows at least one cost record with non-zero prompt_tokens and completion_tokens.
2. **Given** a cost record references a session, **When** the user runs `openreview gateway costs --session <id>`, **Then** only cost records for that session are shown.
3. **Given** the cost database has records, **When** queried, **Then** no foreign-key constraint failures occur (the FK between cost_records and sessions is either nullable or the session always exists before the cost record is written).

---

### User Story 8 — Grounding slot is in the config schema (Priority: P2)

A user runs `openreview set grounding anthropic/claude-sonnet-latest`. The model is saved. `openreview gateway status` shows the grounding slot as configured. `openreview gateway test grounding` calls the configured model and succeeds.

**Why this priority**: The grounding slot exists in `VALID_SLOTS` and in the router logic, but the Pydantic schema rejects it. This is a bug fix — the spec says grounding should work, but it silently fails.

**Independent Test**: Running `openreview set grounding <model>` followed by `openreview gateway status --format json` shows the grounding slot with the assigned model in the output.

**Acceptance Scenarios**:

1. **Given** a valid model is configured for the grounding slot, **When** the user runs `openreview gateway status`, **Then** the grounding slot is shown with the configured model.
2. **Given** the grounding slot is configured, **When** the user runs `openreview gateway test grounding`, **Then** a successful API call is made to the configured model and the response is returned.
3. **Given** no model is configured for the grounding slot, **When** the user runs `openreview gateway test grounding`, **Then** a clear error message is returned indicating the slot is not configured.

---

### User Story 9 — User customizes a provider with a custom base URL (Priority: P3)

A user wants to add a self-hosted OpenAI-compatible endpoint. They run `openreview auth add custom https://my-endpoint.example.com sk-...` and the gateway can call their endpoint.

**Why this priority**: Custom endpoints enable self-hosted and private deployments. This is power-user functionality that most users will not need.

**Independent Test**: After adding a custom provider with a base URL pointing to a local server, a gateway call to that provider reaches the custom endpoint instead of the default API.

**Acceptance Scenarios**:

1. **Given** the user adds a provider with `--base-url https://my-endpoint.example.com`, **When** the gateway makes a call using this provider, **Then** the request is sent to `https://my-endpoint.example.com` instead of the default API URL.
2. **Given** a provider is added without `--base-url`, **When** the gateway makes a call, **Then** the request uses the default API URL for that provider type.

---

### Edge Cases

- **Duplicate model across providers**: When 2 providers serve the same model (e.g. `gpt-4o` via OpenAI direct and via OpenRouter), short-name resolution must prefer the direct provider (cheaper, lower latency). The user can override with explicit `provider/model` string.
- **Invalid JSON piped to gateway setup**: Non-zero exit, clear error message naming the field that failed validation, no partial write to config.
- **OS keyring unavailable**: On headless Linux without Secret Service daemon, fall back to `auth.json` with a one-time warning printed to stderr.
- **gateway setup with no TTY and no stdin**: Print usage to stderr, exit non-zero with a message pointing to `openreview gateway setup --help`.
- **Slot points to model with no key**: `openreview gateway test <slot>` returns a clear error: "No API key for provider [provider_name]".
- **migrate config on already-v2 config**: No-op, exit 0, no files modified.
- **Empty provider list during model discovery**: `openreview models available` with no providers configured shows empty output, not an error.
- **Cost record with no associated session**: Cost record's `session_id` must be nullable; the cost write must succeed even when no session context exists.

## Requirements *(mandatory)*

### Functional Requirements

**Config Schema (v2)**

- **FR-001**: v2 config MUST use a provider-first format: the top-level key is `providers`, each provider entry contains the provider name, `apiKey` (or key source reference), optional `baseURL`, and `enabled` flag.
- **FR-002**: v2 config MUST include a `slots` object mapping each slot name (reasoning, extraction, embedding, reranking, graph, grounding) to a `{provider, model, fallback}` assignment.
- **FR-003**: v2 config MUST support `defaultModel` and `fallback` fields at the root level for commands that do not specify a slot.
- **FR-004**: v2 config MUST include an optional `costLimits` object with per-provider and per-session spending caps.

**gateway setup (JSON-stdin applier)**

- **FR-005**: `openreview gateway setup` MUST accept a JSON config on stdin and apply it atomically (all-or-nothing write to config.yml and auth.json).
- **FR-006**: `openreview gateway setup` MUST validate the entire JSON input against the v2 schema before writing any data. On validation failure, it MUST exit with code 1 and print an error message naming the specific field that failed, with no partial write.
- **FR-007**: `openreview gateway setup` with no TTY and no stdin MUST print usage to stderr and exit with code 1.
- **FR-008**: `openreview gateway setup` MUST support `--dry-run` flag that validates the piped JSON and reports what would be written without modifying any files.

**gateway status**

- **FR-009**: `openreview gateway status --format json` MUST return a JSON object containing all slots with their current model assignments, all configured providers, and gateway health status per provider.
- **FR-010**: `openreview gateway status` (without --format json) MUST return a human-readable table with the same information using the Rich library.

**Model short-name resolution**

- **FR-011**: The gateway MUST resolve short model names (e.g. `gpt-4o`, `sonnet`, `haiku`) to full `provider/model` strings using a built-in alias map and the user's configured providers.
- **FR-012**: When multiple configured providers serve the same short name, the gateway MUST prefer the direct provider (e.g. OpenAI over OpenRouter for `gpt-4o`).
- **FR-013**: The user MUST be able to bypass short-name resolution by providing an explicit `provider/model` string.

**models available command**

- **FR-014**: `openreview models available` MUST list all models from the static registry (`models.json`) that can be reached with the user's currently configured API keys, as `(short_name, provider, [slot_compatibility])` tuples.
- **FR-015**: `openreview models available --provider <name>` MUST filter the list to a single provider.
- **FR-016**: `openreview models available` MUST complete in under 1 second for up to 3 configured providers and the full 33-model registry.

**OS keyring integration**

- **FR-017**: `openreview auth add <provider> <key>` MUST store the API key in the OS keyring via the `keyring` library when it is installed and the system keyring is accessible.
- **FR-018**: When the `keyring` library is not installed or the OS keyring is unavailable, `openreview auth add` MUST fall back to writing the key to `auth.json` with file permissions set to 600 and MUST print a one-time warning to stderr.
- **FR-019**: `openreview auth list` MUST show each configured provider and its key source (`keyring`, `file`, `env`) without revealing the full key value. Only the last 4 characters of the key SHOULD be shown for identification.
- **FR-020**: `openreview auth remove <provider>` MUST delete the key from whichever store it was read from (keyring or auth.json) and confirm the deletion.

**Cost tracking FK fix**

- **FR-021**: The `CostRecord` database model MUST have a nullable `session_id` foreign key to the `Session` table. The cost write MUST succeed and produce a valid record regardless of whether a session reference is provided.
- **FR-022**: `openreview gateway costs` MUST support `--today`, `--session <id>`, and `--since <date>` filters. Output MUST include prompt_tokens, completion_tokens, estimated cost in cents, provider, and model for each record.

**Grounding slot schema**

- **FR-023**: The Pydantic `GatewayModels` schema MUST include the `grounding` slot (string field, optional, default None) alongside the existing 5 slots.
- **FR-024**: `openreview set grounding <model>` MUST persist the value to config.yml and `openreview gateway status` MUST display it. Any command that currently validates slot names MUST accept `grounding` as a valid slot.

**Migration command**

- **FR-025**: `openreview migrate config` MUST read a v1 config.yml (slot-first format) and rewrite it as a v2 config.yml (provider-first format), preserving all slot assignments and provider information.
- **FR-026**: `openreview migrate config` MUST NOT modify auth.json under any circumstances.
- **FR-027**: When run on an already-v2 config, `openreview migrate config` MUST detect the current version, exit with code 0, and make no changes.

**Custom provider support**

- **FR-028**: `openreview auth add` MUST accept an optional `--base-url` argument for custom/self-hosted endpoints. When provided, the gateway MUST route all calls for that provider to the custom base URL instead of the default.
- **FR-029**: The gateway MUST support OpenAI-compatible API endpoints via custom base URLs, using the same request/response format as the standard OpenAI API.

**TTY detection and structured errors**

- **FR-030**: Every CLI command MUST detect whether it is connected to a TTY. Commands requiring interactive input MUST exit with code 1 and a clear message when no TTY is detected and no alternative input method (stdin, flag) is available.
- **FR-031**: All CLI errors MUST return a non-zero exit code following this scheme: 1=user error (invalid input, missing args), 2=config error (missing/invalid config, schema violation), 3=provider error (API failure, auth failure, rate limit).
- **FR-032**: Every CLI command that supports `--format json` MUST, on error, output a JSON object with `{error: string, code: int, message: string}` fields to stderr. The JSON error output MUST be parsable regardless of whether the command succeeded or failed.

### Key Entities

- **Provider**: A named AI service (e.g. `openai`, `anthropic`, `openrouter`, `ollama`, `voyage`). Attributes: name, apiKey (or key source reference), baseURL (optional, for custom endpoints), enabled flag. Provider definitions live in the `providers` section of v2 config.yml.
- **Model**: A specific AI model identified by its short name (e.g. `gpt-4o`) and its full name (`provider/model`, e.g. `openai/gpt-4o`). Models are defined in the static `models.json` registry. Each model lists compatible slots, supported capabilities (chat, embed, rerank), and limits.
- **Slot**: A named role in the gateway pipeline that accepts exactly one model assignment. The 6 slots are: reasoning, extraction, embedding, reranking, graph, grounding. Each slot has a primary model and an optional fallback model. Slots are defined in the `slots` section of v2 config.yml.
- **Config (v2)**: The gateway configuration file (`config.yml`) in provider-first format. Top-level keys: `version` (set to 2), `providers`, `slots`, `defaultModel`, `fallback`, `costLimits`. Single user, no multi-tenant.
- **AuthEntry**: A credential record for one provider. Attributes: provider name, keySource (`keyring`, `file`, `env`), keyRef (environment variable name, or key fingerprint). AuthEntries are stored in `auth.json` and/or the OS keyring.
- **Session**: An execution context for a group of related gateway calls. Attributes: id (UUID), startedAt (timestamp), userId, toolVersion (the openreview-cli version). Created at the start of a review or other multi-step operation.
- **CostRecord**: A single API call cost entry. Attributes: sessionId (nullable FK to Session), slot, model, provider, promptTokens, completionTokens, costCents (estimated), createdAt (timestamp). Written after every successful gateway API call.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An AI agent can fully configure the gateway (providers + slots) in a single `openreview gateway setup` command with JSON piped to stdin. No TTY required. Confirmed by `openreview gateway status --format json` returning the expected configuration. Exit code 0 throughout.
- **SC-002**: A user with 2 providers (OpenRouter + Voyage) can run `openreview models available` and receive a list of all reachable models in under 1 second wall-clock time.
- **SC-003**: A user can resolve `gpt-4o` to a working provider with a single `openreview set reasoning gpt-4o` command. The output confirms the slot is configured. `openreview gateway test reasoning` succeeds without requiring the user to type `openai/gpt-4o`.
- **SC-004**: 100% of gateway CLI commands work non-interactively. A shell script can call every gateway subcommand in a non-TTY context (stdin=/dev/null) without any command hanging, prompting, or producing non-JSON output when `--format json` is specified.
- **SC-005**: A user migrating from v1 to v2 config loses zero provider keys and zero slot assignments. `openreview migrate config` followed by `openreview gateway status` shows the same effective model assignments as before migration.
- **SC-006**: When the `keyring` library is installed and the OS keyring is accessible, 100% of new API keys added via `openreview auth add` go to the OS keyring. Zero keys are written to `auth.json` unless the keyring is unavailable. Verified by inspecting both stores.
- **SC-007**: After running a review that generates at least one API call, `openreview gateway costs --today` returns actual token counts and estimated cost for every call made. Zero foreign-key constraint failures are logged.
- **SC-008**: A user can configure the grounding slot via `openreview set grounding <model>` and the value persists across gateway restarts (config reload). `openreview gateway status` shows the grounding slot with the configured model. `openreview gateway test grounding` makes a successful API call.
- **SC-009**: Every CLI error returns a non-zero exit code (1, 2, or 3). When `--format json` is specified, the error output is a valid JSON object with `error`, `code`, and `message` fields parsable by `jq` or any JSON library.

## Assumptions

- **Single user per machine**: No multi-tenant auth. The config and auth stores assume one user per installation. This matches the current design in pyproject.toml and auth.json.
- **LiteLLM SDK continues as the routing layer**: All existing LiteLLM integration (provider SDK calls, request formatting, retry, error translation) remains in place. The v2 redesign touches configuration, credential storage, model resolution, and CLI commands — not the routing internals.
- **TUI per spec 032 handles human setup**: The TUI wizard (Settings > Gateway > Run setup wizard) writes to the same config.yml and auth.json files. CLI commands are the non-interactive counterpart. No CLI wizard is needed.
- **OS keyring is optional**: The `keyring` library is optional. When absent or when the OS keyring is unavailable (e.g., headless Linux without Secret Service), the file fallback (`auth.json` with chmod 600) is always available and works identically for all auth operations.
- **Static `models.json` registry is sufficient**: The existing `models.json` (33 models across 8 providers) is the model catalog. No remote registry refresh is added in this spec. Model discovery queries this static file.
- **`auth.json` format remains unchanged**: The on-disk format of `auth.json` (JSON object mapping provider name to key) does not change. Only the primary storage location changes from file to OS keyring when available. The file fallback uses the same format.
- **v1 config format gets migration only**: The v1 slot-first config format is supported only through the `openreview migrate config` command. The gateway itself only reads v2 config. No auto-detection of v1 format.
- **No LiteLLM proxy mode**: The gateway remains a direct single-user CLI tool. No LiteLLM proxy server or multi-user gateway server is built.
