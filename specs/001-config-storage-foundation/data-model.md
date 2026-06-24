# Data Model: Config + Storage Foundation

**Phase**: 1 (Design)
**Source Spec**: [spec.md](spec.md)

## Configuration Model

### Config Schema (config.yml)

```yaml
version: 1
privacy:
  tier: balanced           # maximum | balanced | performance
  strip_pii: true
  log_ttl_days: 30
gateway:
  models:
    reasoning:
      primary: ollama/qwen3:8b
      fallback: null
      params:
        temperature: 0.1
        max_tokens: 4000
    extraction:
      primary: ollama/qwen3:4b
      fallback: null
      params:
        temperature: 0.0
        max_tokens: 2000
    embedding:
      primary: ollama/nomic-embed-text
    reranking:
      primary: ollama/qwen3-reranker-0.6b
    graph:
      primary: ollama/qwen3:8b
      fallback: null
      params:
        temperature: 0.0
        max_tokens: 4000
  fallback:
    retries: 2
    retry_delay: 1.0
    timeout: 60
    on_failure: error
  cost_limits:
    per_review_cents: 100
    daily_cents: 1000
  model_registry_refresh_days: 7  # inactive until Phase 4
storage:
  reviews_keep_forever: true
  logs_keep_days: 30
```

### Auth Schema (auth.json)

```json
{
  "openai": "sk-...",
  "anthropic": "sk-ant-...",
  "openrouter": "...",
  "cohere": "...",
  "huggingface": "...",
  "google": "..."
}
```

Flat key-value format. Only providers the user uses need to be present. Created with chmod 600 on Unix.

### Config Validation Rules

| Field | Type | Default | Validation |
|-------|------|---------|------------|
| version | int | 1 | Required, must be ≤ app schema version |
| privacy.tier | str | "balanced" | Must be "maximum", "balanced", or "performance" |
| privacy.strip_pii | bool | true | None |
| privacy.log_ttl_days | int | 30 | Must be ≥ 1 |
| gateway.fallback.retries | int | 2 | Must be ≥ 0 |
| gateway.fallback.retry_delay | float | 1.0 | Must be ≥ 0 |
| gateway.fallback.timeout | int | 60 | Must be ≥ 1 |
| gateway.fallback.on_failure | str | "error" | Must be "error", "skip", or "warn" |
| gateway.cost_limits.per_review_cents | int | 100 | Must be ≥ 1 |
| gateway.cost_limits.daily_cents | int | 1000 | Must be ≥ 1 |
| storage.logs_keep_days | int | 30 | Must be ≥ 1 |

### Config Resolution Priority (highest to lowest)

```
1. CLI flags          (--debug, --quiet, --non-interactive)
2. CLI arguments      (contract path, --client, --format)
3. Environment vars   (OPENREVIEW_* and provider API keys)
4. config.yml         (~/.config/openreview/config.yml)
5. auth.json          (~/.config/openreview/auth.json)
6. Built-in defaults  (hardcoded in code)
```

---

## SQLite Database Schemas

### Main Database: `openreview.db`

#### Table: `schema_version`
| Column | Type | Description |
|--------|------|-------------|
| version | INTEGER PRIMARY KEY | Current schema version |
| applied_at | TEXT | ISO 8601 timestamp |

Used with `PRAGMA user_version` for efficient version checking.

#### Table: `clients`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | Slug (e.g., "acme") |
| name | TEXT | NOT NULL | Display name |
| created_at | TEXT | NOT NULL DEFAULT (datetime('now')) | ISO 8601 |
| updated_at | TEXT | NOT NULL DEFAULT (datetime('now')) | ISO 8601 |

#### Table: `reviews`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | e.g., "2026-06-21_acme-nda" |
| client_id | TEXT | NOT NULL REFERENCES clients(id) | |
| contract_path | TEXT | NOT NULL | Path to original contract file |
| contract_hash | TEXT | NOT NULL | SHA-256 hash for dedup |
| playbook_version | INTEGER | DEFAULT 0 | Version of playbook used |
| mode | TEXT | NOT NULL | Which mode (precheck, hirecheck, ...) |
| status | TEXT | NOT NULL DEFAULT 'in_progress' CHECK(status IN ('in_progress', 'completed')) | Lifecycle state |
| total_questions | INTEGER | DEFAULT 0 | |
| deviations | INTEGER | DEFAULT 0 | Count of non-preferred answers |
| cost_cents | INTEGER | DEFAULT 0 | Total cost in cents |
| created_at | TEXT | NOT NULL DEFAULT (datetime('now')) | |
| memo_path | TEXT | | Path to generated memo file |

#### Table: `review_diffs`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | UUID |
| review_id | TEXT | NOT NULL REFERENCES reviews(id) | |
| question_key | TEXT | NOT NULL | e.g., "confidentiality_period" |
| contract_answer | TEXT | | What the contract says |
| playbook_value | TEXT | | P, A, or W |
| status | TEXT | NOT NULL CHECK(status IN ('match', 'deviation', 'missing')) | |
| created_at | TEXT | NOT NULL DEFAULT (datetime('now')) | |

#### Table: `cost_logs`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | UUID |
| review_id | TEXT | NOT NULL REFERENCES reviews(id) | |
| model | TEXT | NOT NULL | Model name used |
| provider | TEXT | NOT NULL | openai, anthropic, ollama, etc. |
| prompt_tokens | INTEGER | DEFAULT 0 | |
| completion_tokens | INTEGER | DEFAULT 0 | |
| cost_cents | INTEGER | NOT NULL | Cost in cents (integer, no floats) |
| created_at | TEXT | NOT NULL DEFAULT (datetime('now')) | |

### Per-Review Database: `~/.config/openreview/reviews/<review_id>/review.db`

Created by Phase 2+ (document parsing). Schema defined here for reference.

#### Table: `chunks`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | e.g., "chunk_0001" |
| clause_id | TEXT | | Reference to source clause |
| text | TEXT | NOT NULL | Chunk text content |
| vector | BLOB | | Embedding (float32 array) |
| level | INTEGER | DEFAULT 0 | Heading level (0 = root) |
| parent_id | TEXT | REFERENCES chunks(id) | Parent chunk ID |
| node_type | TEXT | DEFAULT 'node' CHECK(node_type IN ('node', 'ancestor', 'descendant')) | |

#### Table: `graph_nodes`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | UUID |
| type | TEXT | NOT NULL | Clause / DefinedTerm / Party / Obligation / Right / Prohibition / Condition / Reference / Value |
| label | TEXT | NOT NULL | Human-readable label |
| text | TEXT | | Raw text span |
| metadata | TEXT | | JSON extras |

#### Table: `graph_edges`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | UUID |
| source_id | TEXT | NOT NULL REFERENCES graph_nodes(id) | |
| target_id | TEXT | NOT NULL REFERENCES graph_nodes(id) | |
| relation | TEXT | NOT NULL | IS_PART_OF / REFERENCES / DEFINES / USES / MODIFIES / CONTRADICTS / SUPERSEDES / DEPENDS_ON / PRECEDES / FOLLOWS |
| metadata | TEXT | | JSON extras |

---

## Entity Relationships

```text
Client (1) ──→ Review (many)
  │               │
  │               ├── ReviewDiff (many)
  │               ├── CostLog (many)
  │               └── review.db (1 per review)
  │                    ├── Chunk (many)
  │                    ├── GraphNode (many)
  │                    └── GraphEdge (many)
  │
  └── playbook.db (1 per client)  ← Phase 7
```

## State Transitions

### Review Lifecycle

```text
[Created] ──→ in_progress ──→ completed
                    │
                    └── [crash] ──→ in_progress (resumed on next run)
```

- `in_progress`: Review is being processed. Partial data exists in review DB.
- `completed`: All questions answered, memo generated. Immutable.

No "cancelled" or "failed" states in Phase 1. These can be added later if needed.
