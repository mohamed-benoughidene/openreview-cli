# Data Model: PII-to-Chunk Pipeline Bridge

**Date**: 2026-07-01

No new data models are introduced. The bridge operates on existing entities:

## Existing Entities (reused)

### Clause (`src/openreview_cli/parsing/models.py`)

Used as both input and output of `strip_pii_clauses()`.

| Field | Type | Preserved |
|-------|------|-----------|
| id | str | Yes |
| title | str\|None | Yes |
| text | str | **Replaced** with PII-stripped version |
| level | int | Yes |
| parent_id | str\|None | Yes |
| source_page | int\|None | Yes |
| source_paragraph | int\|None | Yes |
| source_span | tuple[int,int]\|None | Yes |

### PiiResult (`src/openreview_cli/pii/models.py`)

Returned alongside the stripped clause list. Contains unified mapping across all clauses.

| Field | Notes |
|-------|-------|
| stripped_text | Joined text of all stripped clauses (space-separated) |
| mapping | Unified placeholder→original dict across all clauses |
| entities | All detected entities with placeholders |
| warnings | Includes per-clause failure warnings if any |
| failed_pages | Pages that had PII detection failures |

## New Function Signature

```python
def strip_pii_clauses(
    clauses: list[Clause],
    document: Any,
    *,
    threshold: float = 0.7,
    strip_pii_enabled: bool = True,
    strip_metadata: bool = True,
    engine: PiiEngine | None = None,
) -> tuple[list[Clause], PiiResult]:
```

Returns a tuple of:
1. `list[Clause]` — same input clauses, each with text replaced by PII-stripped version
2. `PiiResult` — unified PII stripping result across all clauses
