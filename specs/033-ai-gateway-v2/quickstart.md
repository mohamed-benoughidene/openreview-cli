# Quickstart: AI Gateway v2 — Validation Guide

> Audience: developer running the spec end-to-end. Run each validation step in order. Expected outputs shown. If a step fails, the spec is not ready to close.

---

## Phase A: Bug Fixes (Non-Breaking)

Fix 3 concrete bugs: grounding slot schema, JSON-stdin setup, cost tracking FK.

### Setup

```bash
# From repo root
uv sync
uv run openreview gateway setup --dry-run < .speckit/validate/v2-minimal.json
# If this fails, create the file with:
echo '{"version": 2, "providers": {"openai": {"name": "openai", "env_key": "OPENAI_API_KEY", "api_key_source": "file"}}, "slots": {"reasoning": {"provider": "openai", "model": "gpt-4o"}}}' > /tmp/v2-test.json
```

### Validation 1: Grounding Slot Persists

**Prerequisite**: None (uses config validation only).

```bash
# Set grounding slot
uv run openreview set grounding anthropic/claude-sonnet-latest

# Verify in status output
uv run openreview gateway status --format json | grep grounding
```

**Expected output**:
```json
"grounding": {"provider": "anthropic", "model": "claude-sonnet-latest"}
```

**Success**: Grounding slot appears in the JSON output. The value persists across `gateway status` calls.

### Validation 2: JSON-Stdin Setup Works

**Prerequisite**: No existing v2 config (or use `--dry-run`).

```bash
# Create a minimal valid config
cat > /tmp/v2-test.json << 'EOF'
{
    "version": 2,
    "providers": {
        "openai": {
            "name": "openai",
            "env_key": "OPENAI_API_KEY",
            "api_key_source": "file",
            "enabled": true
        },
        "voyage": {
            "name": "voyage",
            "env_key": "VOYAGE_API_KEY",
            "api_key_source": "file",
            "enabled": true
        }
    },
    "slots": {
        "reasoning": { "provider": "openai", "model": "gpt-4o" },
        "embedding": { "provider": "voyage", "model": "voyage-3" }
    }
}
EOF

# Dry run (validate without writing)
uv run openreview gateway setup --dry-run < /tmp/v2-test.json
echo "Exit code: $?"  # Should be 0

# Apply for real
uv run openreview gateway setup < /tmp/v2-test.json
echo "Exit code: $?"  # Should be 0

# Verify
uv run openreview gateway status --format json
```

**Expected output** (status JSON):
```json
{
    "version": 2,
    "providers": ["openai", "voyage"],
    "slots": {
        "reasoning": { "provider": "openai", "model": "gpt-4o" },
        "embedding": { "provider": "voyage", "model": "voyage-3" }
    }
}
```

**Error case — invalid JSON**:
```bash
echo '{"version": 2, "providers": {"bad": {}}}' | uv run openreview gateway setup
# Should exit 1 with: "Validation error: providers.bad.name: field required"
```

**Error case — no stdin, no TTY**:
```bash
echo "" | uv run openreview gateway setup  # stdin empty
# Should exit 1 with: "No config provided on stdin. See --help for usage."
```

**Success**: Dry-run validates and reports what would be written. Real run writes config atomically. Invalid JSON produces specific error with no partial write.

### Validation 3: Cost Tracking Works

**Prerequisite**: Gateway configured with at least one functional provider.

```bash
# Run a review that generates API calls (needs API key)
uv run openreview precheck --nda --fast < /path/to/document.pdf

# Query costs for today
uv run openreview gateway costs --today

# Query costs with session filter
uv run openreview gateway costs --session <session-id>  # Use id from previous output
```

**Expected output** (costs):
```
Date       Slot        Model       Provider   Prompt  Completion  Cost(cents)
2026-07-13 reasoning   gpt-4o      openai     1,234   567         3.2
```

**Success**: Cost records appear with non-zero token counts. No FK constraint errors in stderr or application logs. `--session` filter returns only matching records.

---

## Phase B: Additive Features (Non-Breaking)

### Setup

```bash
# Ensure at least one provider is configured
uv run openreview auth add openai sk-test-..."  # Or set env var
```

### Validation 1: `openreview models available` Works

```bash
# List all reachable models
uv run openreview models available

# Filter by provider
uv run openreview models available --provider openai

# No providers configured case
uv run openreview models available
```

**Expected output** (available models):
```
Model             Provider     Compatible Slots
gpt-4o            openai       reasoning, extraction
gpt-4o-mini       openai       reasoning, extraction
text-embedding-3  openai       embedding
...
```

**Success**: Non-empty list of models filtered by currently configured providers. Completes in <1s. With no providers, outputs "No API keys configured. Run `openreview gateway setup` to add providers."

### Validation 2: `openreview set reasoning gpt-4o` Resolves Short Name

```bash
# Resolve a short name against a configured provider
uv run openreview set reasoning gpt-4o

# Verify resolution
uv run openreview gateway status --format json | grep reasoning

# Explicit provider/model still works
uv run openreview set extraction openai/gpt-4o-mini

# Test resolution with proxy preference (OpenRouter + OpenAI both have gpt-4o)
uv run openreview set reasoning gpt-4o
# Should resolve to openai/gpt-4o (direct preferred over proxy)
```

**Expected output** (set command):
```
✓ reasoning → openai/gpt-4o (resolved from "gpt-4o")
```

**Success**: Short name resolves to the correct provider. Direct provider preferred over proxy. Explicit `provider/model` passes through unchanged.

### Validation 3: `openreview auth add` Stores to Keyring

```bash
# Add via keyring (keyring library available)
uv run openreview auth add openrouter sk-or-v2-...

# List configured providers
uv run openreview auth list

# Remove a provider
uv run openreview auth remove openrouter

# Fallback to file (keyring not available)
uv run openreview auth add openrouter sk-or-v2-...
# Should print: "⚠ OS keyring unavailable, storing in auth.json"
```

**Expected output** (auth list):
```
Provider     Source    Key
openai       env       ****-abc1
openrouter   keyring   ****-xyz3
voyage       file      ****-def4
```

**Success**: Key goes to keyring when available, file fallback otherwise. List shows provider, source, and masked key. Remove deletes from correct store.

---

## Phase C: Config Migration (Breaking)

### Setup

```bash
# Create a v1 config to test migration
cp ~/.config/openreview/config.yml ~/.config/openreview/config.yml.bak
cat > ~/.config/openreview/config.yml << 'EOF'
# v1 format (slot-first)
version: 1
reasoning:
  provider: openai
  model: gpt-4o
extraction:
  provider: openai
  model: gpt-4o-mini
embedding:
  provider: voyage
  model: voyage-3
EOF
```

### Validation 1: `openreview migrate config` Converts v1

```bash
# Run migration
uv run openreview migrate config

# Verify v2 config was written
cat ~/.config/openreview/config.yml

# Verify auth.json is untouched
# (compare timestamps or checksum)

# Verify gateway reads new config
uv run openreview gateway status --format json
```

**Expected output** (migrated config.yml):
```yaml
version: 2
providers:
  openai:
    name: openai
    env_key: OPENAI_API_KEY
    enabled: true
  voyage:
    name: voyage
    env_key: VOYAGE_API_KEY
    enabled: true
slots:
  reasoning:
    provider: openai
    model: gpt-4o
  extraction:
    provider: openai
    model: gpt-4o-mini
  embedding:
    provider: voyage
    model: voyage-3
  reranking:
    provider: ""
    model: ""
  graph:
    provider: ""
    model: ""
  grounding:
    provider: openai
    model: gpt-4o
default_model: null
fallback:
  retries: 2
  timeout: 60
cost_limits:
  per_session_cents: 100
  daily_cents: 1000
```

**Success**: All v1 slot assignments preserved in provider-first format. `auth.json` unchanged. Gateway status shows same effective model assignments.

### Validation 2: New v2 Config Works

```bash
# Verify gateway uses v2 config
uv run openreview gateway status

# Verify v1 produces error
# (create a temp v1 config and set CONFIG_PATH)
# uv run openreview --config /tmp/v1-config.yml gateway status
# Expected: "Config format version 1 is no longer supported. Run `openreview migrate config` to upgrade."
```

**Success**: Gateway reads and works with v2 config. v1 config produces clear error message pointing to migration command.

---

## Rollback Plan

If anything fails:

```bash
# Restore config files
mv ~/.config/openreview/config.yml.bak ~/.config/openreview/config.yml

# Restore database
sqlite3 ~/.config/openreview/openreview.db "DROP TABLE IF EXISTS cost_logs_new;"

# Uninstall new code
git checkout -- src/openreview_cli/gateway/
git checkout -- src/openreview_cli/config/
git checkout -- src/openreview_cli/app.py
```
