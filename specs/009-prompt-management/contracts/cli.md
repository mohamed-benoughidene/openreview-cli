# CLI Contracts: Prompt Management

**Feature**: 009-prompt-management | **Date**: 2026-07-02

## Command Tree

```
openreview prompt
├── create      # Create version 1 of a new prompt
├── update      # Create new version of existing prompt
├── list        # Show all prompts with latest version
├── show        # View specific prompt version
├── delete      # Remove a prompt and all its versions
├── diff        # Show content changes between two versions
├── bind        # Associate a prompt version with a model slot
├── unbind      # Remove a binding
├── bindings    # List all active bindings
├── test        # Run A/B test on prompt versions
├── optimize    # Run GRPO optimization
├── history     # Show version history with test results
├── export      # Export prompts as YAML
└── import      # Import prompts from YAML
```

## Command Signatures

### `openreview prompt create`

```
openreview prompt create --name TEXT --content TEXT [--tags TEXT] [--description TEXT]
```

**Arguments**:
- `--name` (required): Unique prompt identifier
- `--content` (required): Prompt instruction text (max 16 KB)
- `--tags` (optional): Comma-separated tags
- `--description` (optional): Human-readable description

**Behavior**:
- Creates version 1 of the prompt
- Rejects if prompt with same name already exists
- Validates content length ≤ 16 KB

**Exit codes**:
- 0: Success
- 1: Prompt already exists
- 2: Content exceeds 16 KB

### `openreview prompt update`

```
openreview prompt update NAME --content TEXT [--tags TEXT] [--description TEXT]
```

**Arguments**:
- `NAME` (positional): Prompt name
- `--content` (required): New prompt content
- `--tags` (optional): Updated tags
- `--description` (optional): Updated description

**Behavior**:
- Creates new version (auto-incremented)
- Previous versions remain accessible
- Validates content length ≤ 16 KB

**Exit codes**:
- 0: Success
- 1: Prompt not found
- 2: Content exceeds 16 KB

### `openreview prompt list`

```
openreview prompt list [--page INT] [--per-page INT]
```

**Arguments**:
- `--page` (optional, default 1): Page number
- `--per-page` (optional, default 25): Items per page

**Behavior**:
- Lists all prompts with latest version number
- Shows name, latest version, created_at
- Paginated (basic pagination for >25 entries)

**Output**: Rich table

### `openreview prompt show`

```
openreview prompt show NAME [--version INT]
```

**Arguments**:
- `NAME` (positional): Prompt name
- `--version` (optional): Specific version (default: latest)

**Behavior**:
- Displays prompt content, metadata, version number

**Exit codes**:
- 0: Success
- 1: Prompt not found
- 2: Version not found

### `openreview prompt delete`

```
openreview prompt delete NAME [--force]
```

**Arguments**:
- `NAME` (positional): Prompt name
- `--force` (optional): Skip confirmation

**Behavior**:
- Deletes all versions of the prompt
- Removes any bindings referencing this prompt
- Prompts for confirmation unless `--force`

**Exit codes**:
- 0: Success
- 1: Prompt not found

### `openreview prompt diff`

```
openreview prompt diff NAME --from INT --to INT
```

**Arguments**:
- `NAME` (positional): Prompt name
- `--from` (required): Source version
- `--to` (required): Target version

**Behavior**:
- Shows unified diff between two versions
- Uses `difflib.unified_diff()`

**Exit codes**:
- 0: Success
- 1: Prompt not found
- 2: Version not found

### `openreview prompt bind`

```
openreview prompt bind --slot TEXT --prompt TEXT --version INT
```

**Arguments**:
- `--slot` (required): Gateway slot name (extraction, reasoning, etc.)
- `--prompt` (required): Prompt name
- `--version` (required): Prompt version

**Behavior**:
- Creates binding between slot and prompt version
- Validates slot is in `VALID_SLOTS`
- Validates prompt version exists

**Exit codes**:
- 0: Success
- 1: Invalid slot
- 2: Prompt version not found

### `openreview prompt unbind`

```
openreview prompt unbind --slot TEXT
```

**Arguments**:
- `--slot` (required): Gateway slot name

**Behavior**:
- Removes binding for the slot
- Pipeline falls back to default prompt

**Exit codes**:
- 0: Success
- 1: No binding exists for slot

### `openreview prompt bindings`

```
openreview prompt bindings
```

**Behavior**:
- Lists all active bindings
- Shows slot → prompt_name:version

**Output**: Rich table

### `openreview prompt test`

```
openreview prompt test --prompt TEXT --versions TEXT [--benchmark TEXT]
```

**Arguments**:
- `--prompt` (required): Prompt name
- `--versions` (required): Comma-separated version numbers (e.g., "1,2")
- `--benchmark` (optional, default "standard"): Benchmark dataset name

**Behavior**:
- Runs each version through benchmark dataset
- Reports per-version metrics (F1, precision, recall)
- Shows comparison (which version wins each metric)
- Warns if <10 benchmark examples available

**Exit codes**:
- 0: Success
- 1: Prompt not found
- 2: Version not found
- 3: Benchmark not configured

**Note**: Requires benchmark harness (roadmap N-3). Integration contract defined, not implemented.

### `openreview prompt optimize`

```
openreview prompt optimize --prompt TEXT [--benchmark TEXT] [--iterations INT]
```

**Arguments**:
- `--prompt` (required): Prompt name
- `--benchmark` (optional, default "standard"): Benchmark dataset name
- `--iterations` (optional, default 5): Number of optimization iterations

**Behavior**:
- Runs GRPO-guided optimization offline
- Generates candidate variants, evaluates against benchmark
- Selects best performer, saves as new version
- Records optimization metadata (source version, iteration count, per-iteration metrics)
- Shows live progress per iteration
- Supports Ctrl+C to abort (preserves completed iterations)

**Exit codes**:
- 0: Success
- 1: Prompt not found
- 2: Benchmark not configured
- 3: Iterations must be ≥ 1
- 4: No improvement found

**Note**: Requires benchmark harness (roadmap N-3).

### `openreview prompt history`

```
openreview prompt history NAME
```

**Arguments**:
- `NAME` (positional): Prompt name

**Behavior**:
- Shows all versions with creation dates
- Includes A/B test results (if any)
- Includes GRPO optimization metadata (if any)

**Output**: Rich table

### `openreview prompt export`

```
openreview prompt export [NAME] [--output PATH]
```

**Arguments**:
- `NAME` (optional): Prompt name (default: export all)
- `--output` (optional): Output file path (default: stdout)

**Behavior**:
- Exports prompt(s) as YAML
- Includes all versions and metadata

**Exit codes**:
- 0: Success
- 1: Prompt not found

### `openreview prompt import`

```
openreview prompt import PATH
```

**Arguments**:
- `PATH` (positional): YAML file path

**Behavior**:
- Imports prompts from YAML file
- Preserves version numbers
- Cannot overwrite existing prompts (creates new entries)

**Exit codes**:
- 0: Success
- 1: File not found
- 2: Invalid YAML format

## Gateway Integration

### `PromptStore.resolve(slot_name) → str`

**Called by**: `Gateway.chat()`, `Gateway.embed()`, `Gateway.rerank()`

**Behavior**:
1. Check if binding exists for slot
2. If yes: load prompt content for bound (name, version)
3. If no: load latest version of default prompt for slot
4. Return prompt content string

**Fallback**: If default prompt not found, return empty string (no system message).

## Variable Substitution

### `{key}` Syntax

**Resolved at**: Pipeline runtime, before sending to model

**Per-slot variables**:
- `extraction`: `{document_type}`, `{clause_count}`, `{playbook_position}`
- `reasoning`: `{task_type}`, `{context_length}`
- `embedding`: `{chunk_type}`
- `reranking`: `{query_type}`
- `graph`: `{entity_type}`

**Behavior**:
- Known variables: replaced with values
- Unknown variables: logged as warning, left as-is
