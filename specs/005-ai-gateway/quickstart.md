# Quickstart — AI Gateway Validation

**Date**: 2026-07-01
**Feature**: specs/005-ai-gateway

## Prerequisites

1. Python 3.12 with `uv` installed
2. The `openreview-cli` package installed (`uv sync`)
3. At least ONE of:
   - An OpenAI API key (set `OPENAI_API_KEY` env var)
   - Ollama running locally with at least one model pulled

## Scenario 1: Verify Gateway Loads Config

```bash
# Show the current gateway configuration
uv run openreview gateway status
```

**Expected output**: A table showing all 5 slots with their configured models and provider reachability status.

## Scenario 2: Test a Chat Request (Cloud)

```bash
# Set your API key
export OPENAI_API_KEY="sk-proj-..."

# Assign a model to the reasoning slot
uv run openreview gateway set reasoning openai/gpt-4o

# Test the slot
uv run openreview gateway test reasoning
```

**Expected output**: A test response from OpenAI, token count, and estimated cost.

## Scenario 3: Test a Chat Request (Local/Ollama)

```bash
# Make sure Ollama is running
ollama serve &

# Pull a model
ollama pull qwen3:8b

# Assign the model
uv run openreview gateway set reasoning ollama/qwen3:8b

# Test the slot
uv run openreview gateway test reasoning
```

**Expected output**: A test response from Ollama, token count, cost = $0.00.

## Scenario 4: Test Embedding (Local)

```bash
ollama pull nomic-embed-text

uv run openreview gateway set embedding ollama/nomic-embed-text
uv run openreview gateway test embedding
```

**Expected output**: Embedding generated, 768 dimensions confirmed.

## Scenario 5: Run the Setup Wizard

```bash
uv run openreview gateway setup
```

**Expected output**: Interactive wizard walks through all 5 slots, saves config.yml and auth.json.

## Scenario 6: Check Costs

```bash
uv run openreview gateway costs --today
```

**Expected output**: Token usage and cost summary for today's API calls.

## Scenario 7: Refresh Model Registry

```bash
uv run openreview gateway refresh
```

**Expected output**: Registry refreshed from GitHub, showing count of models updated.

## Scenario 8: List Models for a Provider

```bash
uv run openreview gateway models openai
uv run openreview gateway models ollama
```

**Expected output**:
- OpenAI: cached list with slot compatibility
- Ollama: dynamically discovered local models + recommended list

## Unit Test Validation

```bash
# Run gateway unit tests (no network, no API keys needed)
uv run pytest tests/unit/test_gateway_router.py tests/unit/test_gateway_registry.py tests/unit/test_gateway_cost.py tests/unit/test_gateway_models.py tests/unit/test_gateway_redaction.py -v

# Run gateway integration tests (mocked prompts/network)
uv run pytest tests/integration/test_gateway_wizard.py tests/integration/test_gateway_cli.py -v
```

**Expected output**: All tests pass. No network calls made. No API keys required.
