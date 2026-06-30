# Quickstart: AI Gateway Validation

**Date**: 2026-06-25 | **Spec**: [spec.md](../specs/004-ai-gateway/spec.md)

## Overview

This guide provides runnable validation scenarios to prove the AI Gateway works end-to-end. Each scenario tests a specific user story or critical path.

## Prerequisites

- Python 3.12+ installed
- `openreview-cli` package installed (`uv sync`)
- At least one AI provider configured (OpenAI, Anthropic, Ollama, etc.)
- For local testing: Ollama installed and running (`ollama serve`)

## Scenario 1: Interactive Setup Wizard (US2)

**Goal**: Complete first-time setup using the interactive wizard.

**Steps**:
```bash
# 1. Ensure no existing config
rm -f ~/.config/openreview/config.yml
rm -f ~/.config/openreview/auth.json

# 2. Run setup wizard
openreview gateway setup

# 3. Follow wizard prompts:
#    - Step 1/5: Select provider for reasoning (e.g., OpenAI)
#    - Enter API key (masked input, copy-to-clipboard available)
#    - Select model (e.g., gpt-4o)
#    - Apply to extraction and graph? (Y/n)
#    - Step 2/5: Select provider for embedding (e.g., Ollama)
#    - Select model (e.g., nomic-embed-text)
#    - Continue for remaining slots...
#    - Review summary and confirm

# 4. Verify config files created
cat ~/.config/openreview/config.yml
cat ~/.config/openreview/auth.json  # Should show chmod 600

# 5. Verify permissions
ls -l ~/.config/openreview/auth.json  # Should show -rw-------
```

**Expected Outcome**:
- Config file created with all 5 slots configured
- Auth file created with API keys (chmod 600)
- Wizard completed in <5 minutes (SC-001)

**Validation**:
```bash
# Check status
openreview gateway status

# Test each slot
openreview gateway test reasoning
openreview gateway test extraction
openreview gateway test embedding
openreview gateway test reranking
openreview gateway test graph
```

---

## Scenario 2: Non-Interactive Setup with Flags (US2, SC-009)

**Goal**: Configure all slots via command-line flags without wizard.

**Steps**:
```bash
# 1. Clear existing config
rm -f ~/.config/openreview/config.yml
rm -f ~/.config/openreview/auth.json

# 2. Set API keys via environment variables
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export COHERE_API_KEY="..."

# 3. Configure all slots via flags
openreview gateway setup \
  --reasoning openai/gpt-4o \
  --extraction openai/gpt-4o-mini \
  --embedding ollama/nomic-embed-text \
  --reranking cohere/rerank-3.5 \
  --graph openai/gpt-4o

# 4. Verify completion time (<30 seconds, SC-009)
time openreview gateway setup \
  --reasoning openai/gpt-4o \
  --extraction openai/gpt-4o-mini \
  --embedding ollama/nomic-embed-text \
  --reranking cohere/rerank-3.5 \
  --graph openai/gpt-4o
```

**Expected Outcome**:
- Config created without any interactive prompts
- Completion time <30 seconds (SC-009)
- All 5 slots configured

**Validation**:
```bash
openreview gateway status
```

---

## Scenario 3: YAML Config Import (US6, SC-011)

**Goal**: Import configuration from a YAML file.

**Steps**:
```bash
# 1. Create import file
cat > ~/my-gateway-config.yml <<'EOF'
reasoning:
  provider: openai
  model: gpt-4o
  params:
    temperature: 0.1
    max_tokens: 4000

extraction:
  provider: openai
  model: gpt-4o-mini
  params:
    temperature: 0.0

embedding:
  provider: ollama
  model: nomic-embed-text
  params:
    dimensions: 512

# reranking: (optional — LightRAG graph retrieval is the default)
#   provider: cohere
#   model: rerank-3.5

graph:
  provider: openai
  model: gpt-4o
  params:
    temperature: 0.0

api_key_env:
  openai: OPENAI_API_KEY
  cohere: COHERE_API_KEY
EOF

# 2. Set environment variables
export OPENAI_API_KEY="sk-..."
export COHERE_API_KEY="..."

# 3. Import config
time openreview gateway import ~/my-gateway-config.yml

# 4. Verify import time (<10 seconds, SC-011)
```

**Expected Outcome**:
- Config imported without interactive prompts
- Import time <10 seconds (SC-011)
- API keys resolved from environment variables

**Validation**:
```bash
openreview gateway status
```

---

## Scenario 4: Routing Through Slots (US1)

**Goal**: Verify requests are routed correctly through each slot.

**Steps**:
```python
# test_routing.py
from openreview_cli.gateway import route_request
import uuid

session_id = str(uuid.uuid4())

# Test chat completion (reasoning slot)
response = route_request(
    slot="reasoning",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say 'hello' in exactly 5 words."}
    ],
    session_id=session_id
)
print(f"Reasoning: {response.content}")
print(f"Model: {response.model}, Tokens: {response.input_tokens}+{response.output_tokens}")
print(f"Cost: ${response.cost_usd:.4f}")

# Test embedding (embedding slot)
response = route_request(
    slot="embedding",
    input_text=["Hello world", "Test embedding"],
    session_id=session_id
)
print(f"Embedding: {len(response.content)} vectors, dim={len(response.content[0])}")

# Test reranking (reranking slot)
response = route_request(
    slot="reranking",
    query="What is Python?",
    documents=[
        "Python is a programming language.",
        "Java is also a programming language.",
        "Snakes are reptiles."
    ],
    session_id=session_id
)
print(f"Reranking: {len(response.content)} results")
for result in response.content:
    print(f"  [{result.index}] score={result.score:.3f}")
```

**Run**:
```bash
uv run python test_routing.py
```

**Expected Outcome**:
- Each slot routes to correct provider/model
- Response contains content, token counts, cost
- No provider-specific imports in test code (FR-017)

---

## Scenario 5: Fallback on Failure (US3, SC-003)

**Goal**: Verify automatic fallback when primary model fails.

**Steps**:
```bash
# 1. Configure slot with invalid primary and valid fallback
openreview gateway set reasoning invalid/model --fallback openai/gpt-4o

# 2. Test slot (should fail on primary, succeed on fallback)
openreview gateway test reasoning

# 3. Verify fallback was used
openreview gateway costs --session <session-id>
# Should show fallback_used=True for the test call
```

**Python Test**:
```python
# test_fallback.py
from openreview_cli.gateway import route_request

response = route_request(
    slot="reasoning",
    messages=[{"role": "user", "content": "Test"}]
)
print(f"Model used: {response.model}")
print(f"Fallback used: {response.fallback_used}")
assert response.fallback_used == True
assert response.model == "openai/gpt-4o"
```

**Expected Outcome**:
- Primary model fails (invalid/model)
- Fallback model succeeds (openai/gpt-4o)
- Response indicates fallback was used (FR-016)
- Fallback activation within 30 seconds (SC-003)

---

## Scenario 6: Cost Tracking and Limits (US4, SC-004, SC-006)

**Goal**: Verify cost tracking accuracy and limit enforcement.

**Steps**:
```bash
# 1. Set low cost limit for testing
openreview gateway config set gateway.cost_limits.per_review_cents 10  # $0.10

# 2. Make several API calls
uv run python -c "
from openreview_cli.gateway import route_request
import uuid
session_id = str(uuid.uuid4())
for i in range(5):
    response = route_request(
        slot='reasoning',
        messages=[{'role': 'user', 'content': f'Call {i}'}],
        session_id=session_id
    )
    print(f'Call {i}: cost=\${response.cost_usd:.4f}')
"

# 3. Check costs
openreview gateway costs --session <session-id>

# 4. Verify limit enforcement (next call should fail)
uv run python -c "
from openreview_cli.gateway import route_request
try:
    response = route_request(
        slot='reasoning',
        messages=[{'role': 'user', 'content': 'This should fail'}]
    )
    print('ERROR: Should have raised GatewayError')
except Exception as e:
    print(f'✓ Cost limit enforced: {e}')
"
```

**Expected Outcome**:
- Token counts accurate within 1% of provider reporting (SC-004)
- Cost limit enforced before call (SC-006)
- Cost records persisted in SQLite

---

## Scenario 7: Fully Local Configuration (US1, SC-005)

**Goal**: Verify fully local operation with zero network calls.

**Steps**:
```bash
# 1. Install Ollama models
ollama pull llama3.1
ollama pull nomic-embed-text
# ollama pull qwen3-reranker (optional — only needed if using cross-encoder reranking)

# 2. Configure all slots to use Ollama
openreview gateway setup \
  --reasoning ollama/llama3.1 \
  --extraction ollama/llama3.1 \
  --embedding ollama/nomic-embed-text \
  # --reranking ollama/qwen3-reranker \  (optional — LightRAG graph retrieval is the default)
  --graph ollama/llama3.1

# 3. Disconnect from internet (or use firewall to block outbound)
sudo iptables -A OUTPUT -p tcp --dport 443 -j DROP

# 4. Run review (should succeed with zero network calls)
uv run python -c "
from openreview_cli.gateway import route_request
response = route_request(
    slot='reasoning',
    messages=[{'role': 'user', 'content': 'Test local operation'}]
)
print(f'✓ Local operation successful: {response.content[:50]}...')
"

# 5. Re-enable internet
sudo iptables -D OUTPUT -p tcp --dport 443 -j DROP
```

**Expected Outcome**:
- All API calls succeed with zero network calls to external providers (SC-005)
- No API keys required (Ollama needs none)
- Fully offline operation supported

---

## Scenario 8: CLI Management Commands (US5)

**Goal**: Verify all CLI subcommands work correctly.

**Steps**:
```bash
# Status
openreview gateway status

# Providers
openreview gateway providers

# Models
openreview gateway models openai
openreview gateway models ollama

# Set slot
openreview gateway set reasoning openai/gpt-4o --temperature 0.1

# Test slot
openreview gateway test reasoning

# Refresh registry
openreview gateway refresh

# View costs
openreview gateway costs
openreview gateway costs --days 7

# Install models
openreview gateway install-models llama3.1 nomic-embed-text
```

**Expected Outcome**:
- All commands execute successfully
- Output is clear and actionable
- Exit codes are correct (0 for success, non-zero for errors)

---

## Scenario 9: Error Handling (Edge Cases)

**Goal**: Verify error messages are clear and actionable.

**Steps**:
```bash
# Test unconfigured slot
rm -f ~/.config/openreview/config.yml
openreview gateway test reasoning
# Expected: "Slot 'reasoning' is not configured" + action

# Test invalid API key
export OPENAI_API_KEY="invalid-key"
openreview gateway test reasoning
# Expected: "Authentication failed for provider 'openai'" + action

# Test Ollama not running
pkill ollama
openreview gateway test embedding  # if configured for Ollama
# Expected: "Provider 'ollama' is not reachable" + action

# Test invalid model format
openreview gateway set reasoning "invalid-model-no-slash"
# Expected: Validation error
```

**Expected Outcome**:
- Error messages name the slot and provider
- Action suggestions are specific and actionable
- Exit codes are correct (7 for gateway errors)

---

## Scenario 10: Performance Validation (SC-007)

**Goal**: Verify gateway routing overhead <50ms.

**Steps**:
```python
# test_performance.py
import time
from openreview_cli.gateway import route_request

# Warm up
route_request(
    slot="reasoning",
    messages=[{"role": "user", "content": "Warm up"}]
)

# Measure overhead (excluding network latency)
start = time.perf_counter()
response = route_request(
    slot="reasoning",
    messages=[{"role": "user", "content": "Test"}]
)
total_time = (time.perf_counter() - start) * 1000

# Gateway overhead = total_time - network_latency
# Network latency ≈ response.latency_ms
gateway_overhead = total_time - response.latency_ms

print(f"Total time: {total_time:.1f}ms")
print(f"Network latency: {response.latency_ms}ms")
print(f"Gateway overhead: {gateway_overhead:.1f}ms")
assert gateway_overhead < 50, f"Overhead {gateway_overhead:.1f}ms exceeds 50ms limit"
print("✓ Performance validation passed")
```

**Expected Outcome**:
- Gateway routing overhead <50ms per request (SC-007)
- Overhead excludes network latency

---

## Validation Checklist

- [ ] Scenario 1: Interactive setup wizard works
- [ ] Scenario 2: Non-interactive setup with flags works
- [ ] Scenario 3: YAML import works
- [ ] Scenario 4: Routing through slots works
- [ ] Scenario 5: Fallback on failure works
- [ ] Scenario 6: Cost tracking and limits work
- [ ] Scenario 7: Fully local configuration works
- [ ] Scenario 8: CLI management commands work
- [ ] Scenario 9: Error handling is clear
- [ ] Scenario 10: Performance overhead <50ms

## Success Criteria Validation

| Criterion | Scenario | Metric |
|-----------|----------|--------|
| SC-001: Setup <5 min | 1 | Time to complete wizard |
| SC-003: Fallback <30s | 5 | Time to activate fallback |
| SC-004: Cost accuracy <1% | 6 | Compare to provider dashboard |
| SC-005: Zero network calls (local) | 7 | Verify no outbound traffic |
| SC-006: Cost limit enforced | 6 | Next call blocked after limit |
| SC-007: Overhead <50ms | 10 | Gateway routing time |
| SC-009: Non-interactive <30s | 2 | Time to configure via flags |
| SC-011: YAML import <10s | 3 | Time to import config |

## References

- [Spec](../specs/004-ai-gateway/spec.md): Full specification
- [Routing Contract](contracts/routing.md): API signatures
- [Config Schema](contracts/config-schema.md): YAML schema
- [CLI Commands](contracts/cli-commands.md): Command reference
- [Data Model](data-model.md): Entity definitions
