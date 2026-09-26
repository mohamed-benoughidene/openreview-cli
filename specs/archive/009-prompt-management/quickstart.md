# Quickstart: Prompt Management Validation

**Feature**: 009-prompt-management | **Date**: 2026-07-02

## Prerequisites

- Python 3.12+
- `uv` package manager
- Project dependencies installed (`uv sync`)

## Validation Scenarios

These scenarios prove the feature works end-to-end. Each scenario is runnable and verifiable.

### Scenario 1: Basic Lifecycle (P1)

**Goal**: Create, update, list, show, diff, delete a prompt.

```bash
# 1. Create a prompt
uv run openreview prompt create \
  --name extract-clauses \
  --content "Extract all clauses from the contract. Return a JSON array." \
  --description "Clause extraction prompt" \
  --tags "extraction,default"

# Expected: Prompt created with version 1

# 2. Update the prompt (creates version 2)
uv run openreview prompt update extract-clauses \
  --content "Extract all clauses from the contract. Return a JSON array with clause_id, text, and section_number." \
  --description "Improved clause extraction prompt"

# Expected: Version 2 created, version 1 still accessible

# 3. List all prompts
uv run openreview prompt list

# Expected: Table showing extract-clauses with latest version 2

# 4. Show specific version
uv run openreview prompt show extract-clauses --version 1

# Expected: Shows version 1 content

# 5. Diff between versions
uv run openreview prompt diff extract-clauses --from 1 --to 2

# Expected: Unified diff showing the content change

# 6. Delete the prompt
uv run openreview prompt delete extract-clauses --force

# Expected: All versions deleted
```

**Verification**: Each command exits with code 0. Output matches expectations.

### Scenario 2: Prompt-to-Model Binding (P1)

**Goal**: Bind a prompt to a gateway slot, verify it's used.

```bash
# 1. Create a prompt
uv run openreview prompt create \
  --name test-prompt \
  --content "You are a helpful assistant."

# 2. Bind it to the extraction slot
uv run openreview prompt bind \
  --slot extraction \
  --prompt test-prompt \
  --version 1

# Expected: Binding created

# 3. List bindings
uv run openreview prompt bindings

# Expected: Table showing extraction → test-prompt:v1

# 4. Verify gateway uses the prompt (requires mock or debug output)
# Run a review command and check debug output for the prompt content
uv run openreview precheck test.pdf --debug 2>&1 | grep "You are a helpful assistant"

# Expected: Prompt content appears in API call

# 5. Unbind
uv run openreview prompt unbind --slot extraction

# Expected: Binding removed, pipeline falls back to default
```

**Verification**: Binding created, gateway uses bound prompt, unbind works.

### Scenario 3: Variable Substitution (P1)

**Goal**: Verify `{key}` variables are resolved at runtime.

```bash
# 1. Create a prompt with variables
uv run openreview prompt create \
  --name variable-test \
  --content "Extract {clause_count} clauses from this {document_type} document."

# 2. Bind to extraction slot
uv run openreview prompt bind \
  --slot extraction \
  --prompt variable-test \
  --version 1

# 3. Run a review (variables resolved at runtime)
# The gateway resolves {clause_count} and {document_type} before sending to model
uv run openreview precheck test.pdf --debug 2>&1 | grep "Extract.*clauses from this.*document"

# Expected: Variables replaced with actual values
```

**Verification**: Variables resolved correctly in the API call.

### Scenario 4: Export/Import (P2)

**Goal**: Export prompts to YAML, import into fresh database.

```bash
# 1. Create a prompt
uv run openreview prompt create \
  --name export-test \
  --content "Test prompt for export."

# 2. Export to YAML
uv run openreview prompt export export-test --output /tmp/prompts.yaml

# Expected: YAML file created with prompt content

# 3. Verify YAML content
cat /tmp/prompts.yaml

# Expected:
# name: export-test
# versions:
#   - version: 1
#     content: "Test prompt for export."
#     created_at: "..."
#     metadata: {...}

# 4. Delete the prompt
uv run openreview prompt delete export-test --force

# 5. Import from YAML
uv run openreview prompt import /tmp/prompts.yaml

# Expected: Prompt re-created with version 1

# 6. Verify
uv run openreview prompt show export-test

# Expected: Shows the imported prompt
```

**Verification**: Export produces valid YAML. Import recreates the prompt.

### Scenario 5: Memory Budget (Constitutional)

**Goal**: Verify prompt operations stay under 100 MB.

```bash
# Run memory test
uv run pytest tests/integration/test_prompt_memory.py -v

# Expected: All tests pass, peak memory < 110 MB
```

**Verification**: `memory_tracker` fixture asserts peak < 110 MB.

### Scenario 6: A/B Testing (P2 — requires benchmark harness)

**Goal**: Run A/B test on two prompt versions.

**Note**: Requires benchmark harness (roadmap N-3). This scenario validates the integration contract.

```bash
# 1. Create two prompt versions
uv run openreview prompt create \
  --name ab-test \
  --content "Extract clauses."

uv run openreview prompt update ab-test \
  --content "Extract all clauses with clause_id and text."

# 2. Run A/B test
uv run openreview prompt test \
  --prompt ab-test \
  --versions 1,2 \
  --benchmark standard

# Expected: Table showing per-version metrics (F1, precision, recall)
# and comparison (which version wins each metric)
```

**Verification**: Metrics reported for each version. Comparison shown.

### Scenario 7: GRPO Optimization (P3 — requires benchmark harness)

**Goal**: Run GRPO optimization on a prompt.

**Note**: Requires benchmark harness (roadmap N-3).

```bash
# 1. Create a prompt
uv run openreview prompt create \
  --name optimize-test \
  --content "Extract clauses."

# 2. Run optimization
uv run openreview prompt optimize \
  --prompt optimize-test \
  --benchmark standard \
  --iterations 3

# Expected: New version created with optimization metadata
# Live progress shown per iteration

# 3. Verify metadata
uv run openreview prompt history optimize-test

# Expected: Shows version 2 with optimization_meta (source version, iteration count, metrics)
```

**Verification**: New version created. Metadata recorded.

## Test Commands

### Unit Tests

```bash
uv run pytest tests/unit/test_prompt_models.py -v
uv run pytest tests/unit/test_prompt_store.py -v
uv run pytest tests/unit/test_prompt_variables.py -v
uv run pytest tests/unit/test_prompt_defaults.py -v
uv run pytest tests/unit/test_prompt_cli.py -v
```

### Integration Tests

```bash
uv run pytest tests/integration/test_prompt_lifecycle.py -v
uv run pytest tests/integration/test_prompt_gateway.py -v
uv run pytest tests/integration/test_prompt_memory.py -v
```

### All Prompt Tests

```bash
uv run pytest tests/ -k prompt -v
```

## Expected Outcomes

| Scenario | Priority | Status |
|----------|----------|--------|
| Basic lifecycle | P1 | Should pass after P1 implementation |
| Prompt-to-model binding | P1 | Should pass after P1 implementation |
| Variable substitution | P1 | Should pass after P1 implementation |
| Export/Import | P2 | Should pass after P2 implementation |
| Memory budget | Constitutional | Should pass after any implementation |
| A/B testing | P2 | Requires benchmark harness (N-3) |
| GRPO optimization | P3 | Requires benchmark harness (N-3) |

## Troubleshooting

### "Prompt not found"

Check the prompt name is correct:
```bash
uv run openreview prompt list
```

### "Content exceeds 16 KB"

Prompt content is too large. Max is 16 KB (16,384 bytes).

### "Invalid slot"

Slot must be one of: `extraction`, `reasoning`, `embedding`, `reranking`, `graph`.

### "Benchmark not configured"

A/B testing and GRPO optimization require the benchmark harness (roadmap N-3). This is a separate feature.
