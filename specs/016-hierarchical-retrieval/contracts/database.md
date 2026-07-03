# Database Schema — Hierarchical Retrieval Index

**Spec**: specs/016-hierarchical-retrieval/spec.md (§FR-7)

---

## Overview

Each indexed document gets its own SQLite database file, stored at:
```
{platformdirs user_data_dir}/openreview/indexes/{doc_hash}.db
```

- **Driver**: `sqlite3` (stdlib)
- **Journal mode**: WAL (`PRAGMA journal_mode=WAL;`)
- **Synchronous mode**: NORMAL (`PRAGMA synchronous=NORMAL;`) — balances durability and write performance
- **Foreign keys**: ON (`PRAGMA foreign_keys=ON;`)
- **Encoding**: UTF-8

---

## Tables

### `index_meta`

Database-level metadata, single row.

```sql
CREATE TABLE index_meta (
    document_id      TEXT PRIMARY KEY,   -- SHA-256 of original document
    document_path    TEXT NOT NULL,       -- Original file path at ingest time
    index_version    INTEGER NOT NULL DEFAULT 1,  -- Schema version for migration
    index_status     TEXT NOT NULL DEFAULT 'empty' CHECK(index_status IN ('empty','ingesting','indexed','corrupt')),
    index_timestamp  TEXT,                -- ISO 8601 / NULL if not indexed
    chunk_count      INTEGER NOT NULL DEFAULT 0,
    method           TEXT NOT NULL DEFAULT 'sparse' CHECK(method IN ('sparse','hybrid')),
    embedding_model  TEXT,                -- NULL if sparse-only
    embedding_dim    INTEGER,             -- NULL if sparse-only
    db_size_bytes    INTEGER DEFAULT 0
);
```

**Notes**:
- `index_version` enables future schema migrations. If current code expects version N but DB has N-1, migrate. If N+1, print "incompatible index" and prompt re-ingest.
- `index_status = 'ingesting'` is set at start of ingest, cleared to 'indexed' on success. If left as 'ingesting' (crash/interrupt), next ingest detects and re-builds from scratch.

---

### `chunks`

One row per chunk (text fragment with hierarchy metadata).

```sql
CREATE TABLE chunks (
    chunk_id         TEXT PRIMARY KEY,
    document_id      TEXT NOT NULL REFERENCES index_meta(document_id),
    text             TEXT NOT NULL,
    clause_heading   TEXT NOT NULL,
    clause_level     INTEGER NOT NULL CHECK(clause_level >= 0),
    parent_chunk_id  TEXT REFERENCES chunks(chunk_id),
    heading_chain    TEXT NOT NULL,        -- JSON array of strings, e.g., '["Art 3","§3.1"]'
    char_start       INTEGER NOT NULL CHECK(char_start >= 0),
    char_end         INTEGER NOT NULL CHECK(char_end > char_start),
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX idx_chunks_document_id ON chunks(document_id);
CREATE INDEX idx_chunks_parent ON chunks(parent_chunk_id);
CREATE INDEX idx_chunks_clause_level ON chunks(clause_level);
```

**Notes**:
- `heading_chain` is stored as a JSON text array. SQLite has no native array type, but JSON functions (`json_extract`, `json_array_length`) are available at query time if needed for filtering.
- `parent_chunk_id` creates a self-referencing tree for the clause hierarchy.
- The `created_at` timestamp helps detect stale indexes.

---

### `chunk_fts` (FTS5 Virtual Table)

Full-text search index over chunk text, enabling BM25 ranking.

```sql
CREATE VIRTUAL TABLE chunk_fts USING fts5(
    chunk_id UNINDEXED,    -- stored but not full-text indexed
    text,                  -- primary search content
    clause_heading,        -- also searchable
    content='chunks',      -- content-sync table (data lives in chunks)
    content_rowid='rowid',
    tokenize='porter unicode61',  -- porter stemmer + unicode61 removes diacritics
    prefix='2 3'           -- prefix indexes for fast prefix queries
);
```

**Notes**:
- `content='chunks'` enables content-sync: FTS5 reads `text` and `clause_heading` from the `chunks` table by matching on `rowid`. Updates to `chunks.text` are reflected automatically.
- `porter unicode61` tokenizer provides basic stemming (porter stemmer) but only on the FTS5 side — query preprocessing does NOT apply porter (per spec FR-2, query preprocessing is minimal). The asymmetry means "indemnification" in the query might not match "indemnify" in the FTS5 index. **Decision**: Use `unicode61` WITHOUT `porter` to keep exact legal terminology matching. Update resolver note.
- `chunk_id` is marked UNINDEXED — it's stored in the FTS5 table for JOIN purposes but not full-text indexed.
- **CORRECTION** to the above: The spec says "No stemming or stop-word removal — legal text relies on precise terminology [P-9]." So the tokenizer should be `unicode61` only (remove `porter`):

```sql
CREATE VIRTUAL TABLE chunk_fts USING fts5(
    chunk_id UNINDEXED,
    text,
    clause_heading,
    content='chunks',
    content_rowid='rowid',
    tokenize='unicode61',
    prefix='2 3'
);
```

### Triggers for FTS5 sync

```sql
-- Keep FTS5 in sync with chunks table
CREATE TRIGGER chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunk_fts(rowid, chunk_id, text, clause_heading)
    VALUES (new.rowid, new.chunk_id, new.text, new.clause_heading);
END;

CREATE TRIGGER chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunk_fts(chunk_fts, rowid, chunk_id, text, clause_heading)
    VALUES ('delete', old.rowid, old.chunk_id, old.text, old.clause_heading);
END;

CREATE TRIGGER chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunk_fts(chunk_fts, rowid, chunk_id, text, clause_heading)
    VALUES ('delete', old.rowid, old.chunk_id, old.text, old.clause_heading);
    INSERT INTO chunk_fts(rowid, chunk_id, text, clause_heading)
    VALUES (new.rowid, new.chunk_id, new.text, new.clause_heading);
END;
```

---

### `chunk_embeddings`

One row per chunk (dense mode only). Stores the embedding vector as a raw float32 byte array.

```sql
CREATE TABLE chunk_embeddings (
    chunk_id    TEXT PRIMARY KEY REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    embedding   BLOB NOT NULL,             -- raw float32 bytes, row-major
    model_id    TEXT NOT NULL,             -- e.g., "nomic-embed-text"
    dimension   INTEGER NOT NULL CHECK(dimension > 0),
    chunk_norm  REAL NOT NULL CHECK(chunk_norm > 0.0)  -- pre-computed L2 norm
);

CREATE INDEX idx_embeddings_model_id ON chunk_embeddings(model_id);
```

**Notes**:
- Float32 byte ordering is platform-native (little-endian on x86_64, the reference hardware). Use `struct.pack('<%df' % dim, *vec)` for serialization and `struct.unpack('<%df' % dim, blob)` for deserialization.
- `chunk_norm` is pre-computed at ingest time so cosine similarity at query time only needs: `dot(query_vec, chunk_vec) / (query_norm × chunk_norm)`. Two fields can be pre-computed: query_norm (once per query) and chunk_norm (once per chunk at ingest).
- ON DELETE CASCADE ensures removing a chunk also removes its embedding.

---

### `rerank_validation`

Cached reranker benchmark results (FR-5).

```sql
CREATE TABLE rerank_validation (
    model_id              TEXT NOT NULL,       -- embedding model used
    document_type         TEXT NOT NULL,       -- e.g., "nda", "msa"
    precision_with        REAL CHECK(precision_with BETWEEN 0.0 AND 1.0),   -- P@5 with reranker
    precision_without     REAL CHECK(precision_without BETWEEN 0.0 AND 1.0), -- P@5 without reranker
    degradation_pp        REAL,                -- percentage points (negative = improvement)
    benchmark_timestamp   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (model_id, document_type)
);
```

**Notes**:
- Unique constraint on (model_id, document_type) means one cache entry per combination.
- `degradation_pp = precision_without - precision_with`. Positive = reranker degrades results.
- If `degradation_pp >= 0.0` for three consecutive runs (stored elsewhere; this table stores the latest), reranker is locked as disabled-by-default.
- The benchmark timestamp is updated each time the benchmark runs for this model/doc_type pair.

---

## Integrity Constraints Summary

| Constraint | Enforcement | Violation Handling |
|---|---|---|
| Document hash uniqueness | PRIMARY KEY on index_meta.document_id | N/A (one DB per doc) |
| Chunk ID uniqueness | PRIMARY KEY on chunks.chunk_id | DB constraint error → re-ingest |
| Parent chunk reference | FOREIGN KEY on chunks.parent_chunk_id | DB constraint error → check chunking pipeline |
| Document ID consistency | FOREIGN KEY on chunks.document_id | DB constraint error |
| Embedding model consistency | Application-level (check model_id match on ingest) | Detect and re-ingest with warning |
| Schema version compatibility | index_meta.index_version | Migration script or re-ingest prompt |
| Embedding dimension consistency | Application-level (all chunk_embeddings.dimension must match) | On mismatch: "Embedding model changed; re-indexing document." |

## Migration Strategy

When the schema version (`index_meta.index_version`) changes:

1. **Patch version bumps** (e.g., 1 → 2 for a non-breaking addition): Apply ALTER TABLE in a migration script.
2. **Minor/major changes** (column removal, type change): Print "Index schema version {N} is incompatible. Re-run `openreview ingest` to rebuild." and delete/recreate the database.

The initial schema version is `1`.
