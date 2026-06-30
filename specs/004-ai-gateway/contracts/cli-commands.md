# Contract: Gateway CLI Commands

**Date**: 2026-06-25 | **Spec**: [spec.md](../../specs/004-ai-gateway/spec.md)

## Overview

The gateway CLI provides subcommands for managing AI model configuration, testing connectivity, viewing costs, and importing config files. All commands are under the `openreview gateway` command group.

## Command Group

```python
gateway_app = typer.Typer(
    name="gateway",
    help="AI model gateway management",
    no_args_is_help=True
)
app.add_typer(gateway_app)
```

## Commands

### 1. `openreview gateway setup`

**Purpose**: Interactive first-time setup wizard for configuring gateway slots (4 required + 1 optional).

**Usage**:
```bash
openreview gateway setup [OPTIONS]
```

**Options**:
- `--reasoning <provider/model>`: Pre-configure reasoning slot (skip wizard for this slot)
- `--extraction <provider/model>`: Pre-configure extraction slot
- `--embedding <provider/model>`: Pre-configure embedding slot
- `--reranking <provider/model>`: Pre-configure reranking slot (optional, disabled by default)
- `--graph <provider/model>`: Pre-configure graph slot
- `--no-interactive`: Force non-interactive mode (error if config incomplete)

**Behavior**:
1. If flags provided, configure those slots without wizard
2. If no flags and no existing config, start interactive wizard
3. If no flags and existing config, show current config and ask "Reconfigure? (y/N)"
4. Wizard flow:
   - Welcome message explaining purpose and privacy
   - For each slot (reasoning, extraction, embedding, graph — required; reranking — optional):
     - Show "Step X of 4" progress indicator (reranking step is skipped unless user opts in)
     - List available providers (OpenAI, Anthropic, Google, Ollama, OpenRouter, Cohere, HuggingFace, Custom)
     - User selects provider
     - If cloud provider: prompt for API key (masked input, copy-to-clipboard, immediate validation)
     - List available models for selected provider
     - User selects model
     - Offer to apply same provider to compatible remaining slots
     - Allow skip
   - Show summary of all configured slots
   - Confirm and save to config.yml and auth.json

**Exit Codes**:
- 0: Success
- 1: User cancelled
- 5: Config error
- 7: Gateway error (API key validation failed, etc.)

**Examples**:
```bash
# Interactive setup
openreview gateway setup

# Non-interactive with flags
openreview gateway setup \
  --reasoning openai/gpt-4o \
  --extraction openai/gpt-4o-mini \
  --embedding ollama/nomic-embed-text \
  --reranking cohere/rerank-3.5 \
  --graph openai/gpt-4o

# Mixed: some slots via flags, rest via wizard
openreview gateway setup --reasoning openai/gpt-4o
```

---

### 2. `openreview gateway status`

**Purpose**: Show current configuration and provider health status.

**Usage**:
```bash
openreview gateway status
```

**Output**:
```
Gateway Status
==============

Slots:
  reasoning   openai/gpt-4o              ✓ healthy
  extraction  openai/gpt-4o-mini         ✓ healthy
  embedding   ollama/nomic-embed-text    ✓ healthy (local)
  reranking   cohere/rerank-3.5          ✓ healthy
  graph       ollama/qwen3:8b            ✓ healthy (local)

Fallback:
  retries: 2
  retry_delay: 1.0s
  timeout: 60s
  on_failure: error

Cost Limits:
  per_review: $1.00
  daily: $10.00

Today's Usage:
  total_cost: $0.23
  total_tokens: 12,345
  api_calls: 42
```

**Exit Codes**:
- 0: Success
- 5: No config found

---

### 3. `openreview gateway providers`

**Purpose**: List all supported providers and their configuration status.

**Usage**:
```bash
openreview gateway providers
```

**Output**:
```
Supported Providers
===================

Provider      Status        Auth Method          Base URL
────────────────────────────────────────────────────────────────
openai        ✓ configured  API key              https://api.openai.com/v1
anthropic     ✓ configured  API key              https://api.anthropic.com
google        ✗ not configured  API key          https://generativelanguage.googleapis.com
ollama        ✓ configured  None (local)         http://localhost:11434
openrouter    ✗ not configured  API key          https://openrouter.ai/api/v1
cohere        ✓ configured  API key              https://api.cohere.com/v2
huggingface   ✗ not configured  API key          https://api-inference.huggingface.co
custom        ✗ not configured  API key + URL    (user-defined)
```

**Exit Codes**:
- 0: Success

---

### 4. `openreview gateway models`

**Purpose**: List available models for a specific provider.

**Usage**:
```bash
openreview gateway models <provider>
```

**Arguments**:
- `provider`: Provider name (openai, anthropic, google, ollama, openrouter, cohere, huggingface, custom)

**Output**:
```
Available Models: openai
========================

Model              Slots                    Context    Price (per MTok)
─────────────────────────────────────────────────────────────────────────
gpt-4o             reasoning, extraction    128K       $5.00 / $15.00
gpt-4o-mini        extraction, graph        128K       $0.15 / $0.60
gpt-4o-2024-08-06  reasoning                128K       $5.00 / $15.00
gpt-4-turbo        reasoning                128K       $10.00 / $30.00
text-embedding-3-small  embedding           8K         $0.02 / $0.02
text-embedding-3-large  embedding           8K         $0.13 / $0.13
```

**Exit Codes**:
- 0: Success
- 5: Provider not configured
- 7: Failed to fetch models

---

### 5. `openreview gateway set`

**Purpose**: Configure a specific slot with a model.

**Usage**:
```bash
openreview gateway set <slot> <provider/model> [OPTIONS]
```

**Arguments**:
- `slot`: Slot name (reasoning, extraction, embedding, reranking, graph)
- `provider/model`: Model identifier (e.g., `openai/gpt-4o`, `ollama/llama3.1`)

**Options**:
- `--fallback <provider/model>`: Set fallback model
- `--temperature <float>`: Set temperature parameter
- `--max-tokens <int>`: Set max_tokens parameter
- `--dimensions <int>`: Set dimensions parameter (embedding only)

**Output**:
```
✓ Updated reasoning slot: openai/gpt-4o
  fallback: anthropic/claude-3-5-sonnet-20241022
  temperature: 0.1
  max_tokens: 4000
```

**Exit Codes**:
- 0: Success
- 1: Invalid slot name
- 5: Config error
- 7: Model not found

**Examples**:
```bash
# Set reasoning slot
openreview gateway set reasoning openai/gpt-4o

# Set with fallback
openreview gateway set reasoning openai/gpt-4o --fallback anthropic/claude-3-5-sonnet-20241022

# Set with parameters
openreview gateway set extraction openai/gpt-4o-mini --temperature 0.0 --max-tokens 2000

# Set embedding with dimensions
openreview gateway set embedding openai/text-embedding-3-small --dimensions 512
```

---

### 6. `openreview gateway test`

**Purpose**: Test connectivity and API key validity for a slot.

**Usage**:
```bash
openreview gateway test <slot>
```

**Arguments**:
- `slot`: Slot name to test

**Behavior**:
1. Load config for specified slot
2. Call provider's models list endpoint (`GET /v1/models`)
3. If list endpoint not supported, fall back to 1-token chat completion
4. Report success/failure with latency

**Output**:
```
Testing slot: reasoning
  provider: openai
  model: gpt-4o
  
  ✓ API key valid
  ✓ Models list retrieved (42 models available)
  ✓ Latency: 234ms
  
Test passed.
```

**Exit Codes**:
- 0: Test passed
- 1: Slot not configured
- 7: Test failed (API key invalid, provider unreachable, etc.)

---

### 7. `openreview gateway refresh`

**Purpose**: Refresh the cached model registry from remote source.

**Usage**:
```bash
openreview gateway refresh
```

**Behavior**:
1. Fetch model registry from remote URL (config: `gateway.registry.remote_url`)
2. Validate response
3. Update local cache (`~/.cache/openreview/model_registry.json`)
4. If fetch fails, retain existing cache

**Output**:
```
Refreshing model registry...
  remote: https://example.com/models.json
  ✓ Fetched 342 models from 8 providers
  ✓ Cache updated: ~/.cache/openreview/model_registry.json
  ✓ Next refresh: 2026-07-02
```

**Exit Codes**:
- 0: Success
- 7: Fetch failed (cache retained)

---

### 8. `openreview gateway costs`

**Purpose**: View cost tracking and usage statistics.

**Usage**:
```bash
openreview gateway costs [OPTIONS]
```

**Options**:
- `--session <uuid>`: Show costs for specific review session
- `--days <int>`: Show costs for last N days (default: 1)
- `--clear`: Clear all cost records
- `--json`: Output in JSON format

**Output** (default):
```
Cost Summary (Last 24 Hours)
=============================

Total Cost: $2.34
Total Tokens: 123,456
  Input: 98,765
  Output: 24,691
API Calls: 89

By Slot:
  reasoning   $1.23  52,340 tokens  34 calls
  extraction  $0.67  41,234 tokens  32 calls
  embedding   $0.23  23,456 tokens  12 calls
  reranking   $0.12  4,567 tokens   8 calls
  graph       $0.09  1,859 tokens   3 calls

By Provider:
  openai      $1.90  93,574 tokens  66 calls
  ollama      $0.00  23,456 tokens  12 calls  (local)
  cohere      $0.44  6,426 tokens   11 calls

Cost Limits:
  per_review: $1.00 / $1.00 (100%)
  daily: $2.34 / $10.00 (23%)
```

**Exit Codes**:
- 0: Success
- 1: Session not found (if `--session` specified)

---

### 9. `openreview gateway import`

**Purpose**: Import gateway configuration from a YAML file.

**Usage**:
```bash
openreview gateway import <file> [OPTIONS]
```

**Arguments**:
- `file`: Path to YAML config file

**Options**:
- `--force`: Skip confirmation prompt (overwrite existing config)
- `--dry-run`: Validate file without applying changes

**Behavior**:
1. Read and parse YAML file
2. Validate entire file (report all errors at once)
3. If errors found, display all errors and exit without applying
4. If no errors and existing config, prompt for confirmation (unless `--force`)
5. Apply changes to config.yml
6. If `api_key_env` section present, resolve env vars and write to auth.json

**Output**:
```
Importing config from: ~/my-config.yml

Validating...
  ✓ All 5 slots defined
  ✓ All providers recognized
  ✓ All model IDs valid
  ✓ No inline API keys detected

Summary:
  reasoning:   openai/gpt-4o
  extraction:  openai/gpt-4o-mini
  embedding:   ollama/nomic-embed-text
  reranking:   cohere/rerank-3.5
  graph:       openai/gpt-4o

Existing config will be overwritten. Continue? [y/N]: y

✓ Config imported successfully
✓ API keys written to auth.json (chmod 600)
```

**Exit Codes**:
- 0: Success
- 1: File not found
- 5: Validation errors (all errors displayed)
- 7: Import failed

**Examples**:
```bash
# Import with confirmation
openreview gateway import ~/my-config.yml

# Import without confirmation
openreview gateway import ~/my-config.yml --force

# Validate without applying
openreview gateway import ~/my-config.yml --dry-run
```

---

### 10. `openreview gateway install-models`

**Purpose**: Install local models via Ollama.

**Usage**:
```bash
openreview gateway install-models <model> [<model> ...]
```

**Arguments**:
- `model`: One or more Ollama model names (e.g., `llama3.1`, `nomic-embed-text`)

**Behavior**:
1. Check if Ollama is running
2. For each model, pull via Ollama API
3. Show progress for each download

**Output**:
```
Installing Ollama models...

[1/3] llama3.1
  ✓ Downloaded (4.7 GB)
  
[2/3] nomic-embed-text
  ✓ Downloaded (274 MB)
  
[3/3] qwen3-reranker-0.6b
  ✓ Downloaded (350 MB)

All models installed successfully.
```

**Exit Codes**:
- 0: Success
- 7: Ollama not running or download failed

---

## Global Options

All gateway commands support these global options (inherited from root app):

- `--version`: Show version
- `--debug`: Enable debug logging
- `--config <path>`: Override config file path
- `--data-dir <path>`: Override data directory path

## Exit Codes Summary

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error (invalid arguments, user cancelled, etc.) |
| 5 | Config error (missing config, invalid format, etc.) |
| 6 | Cost limit exceeded |
| 7 | Gateway error (API key invalid, provider unreachable, etc.) |

## Implementation Notes

- All commands use lazy imports for heavy dependencies (litellm, rich)
- Rich tables and progress bars for interactive output
- JSON output available via `--json` flag for scripting
- All commands respect `--debug` flag for verbose logging
- API keys are redacted in all output (except masked entry in setup)
- Config file writes use atomic writes (temp → fsync → rename)
- Auth file writes enforce chmod 600
