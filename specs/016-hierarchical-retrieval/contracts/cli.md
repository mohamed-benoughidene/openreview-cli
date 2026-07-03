# CLI Command Contracts — Hierarchical Retrieval

**Spec**: specs/016-hierarchical-retrieval/spec.md (§FR-8)

---

## `openreview ingest <file>`

Parse, chunk, and index a document for retrieval.

### Signature
```
openreview ingest [OPTIONS] <FILE>
```

### Arguments
| Argument | Type | Required | Description |
|---|---|---|---|
| `FILE` | `Path` | Yes | Path to a parsed contract file (`.ndax` or raw `.pdf`/`.docx`) |

### Options
| Option | Type | Default | Description |
|---|---|---|---|
| `--method` | `str` | `"hybrid"` | Retrieval mode to prepare for: `sparse` (BM25 only), `hybrid` (BM25 + dense embeddings) |
| `--model` | `str` | Gateway default | Embedding model override for this ingest |
| `--force` | `bool` | `False` | Force re-ingest even if index is up-to-date |
| `--no-progress` | `bool` | `False` | Suppress progress indicator |
| `--db-dir` | `Path` | Platform default | Directory for the SQLite index database (testing use) |

### Output
```
✓ Indexed 47 chunks in 3.2s
  Method: hybrid (nomic-embed-text, 1024d)
  DB: /home/user/.local/share/openreview/indexes/a1b2c3d4...ef.db
```

### Exit Codes
| Code | Meaning |
|---|---|
| `0` | Success — ingestion complete |
| `1` | Error — invalid file, parsing failure, embedding model unavailable |
| `2` | Error — document not parsed (run `openreview parse <file>` first) |

### Edge Cases
- **Already indexed**: If the document is already indexed with the same config, print "Document already indexed (up to date). Use --force to re-index."
- **Embedding model not found**: Print "Embedding model '{model}' not available. Run `openreview gateway status` to check available models."
- **Ingestion interrupted**: Leave incomplete marker in DB. Next ingest cleans it up.

---

## `openreview retrieve "<query>" [<file>]`

Retrieve relevant clause chunks from an indexed document.

### Signature
```
openreview retrieve [OPTIONS] <QUERY> [FILE]
```

### Arguments
| Argument | Type | Required | Description |
|---|---|---|---|
| `QUERY` | `str` | Yes | Natural-language query (wrap in quotes) |
| `FILE` | `Path` | No | Document file. If omitted, use most recently indexed. |

### Options
| Option | Type | Default | Description |
|---|---|---|---|
| `--method` | `str` | `"hybrid"` | Retrieval method: `sparse`, `dense`, `hybrid` |
| `--top-k` | `int` | `5` | Number of results (1–50) |
| `--rerank` | `flag` | — | Enable cross-encoder reranker (experimental) |
| `--rerank-depth` | `int` | `20` | Number of hybrid results to rerank |
| `--force-rerank` | `flag` | — | Override reranker validation warning |
| `--format` | `str` | `"terminal"` | Output format: `terminal` (Rich table) or `json` |
| `--no-header` | `flag` | — | Omit headings from output (JSON mode only) |
| `--db-dir` | `Path` | Platform default | SQLite index directory override |

### Output (terminal mode — Rich table)
```
┌──────┬──────────────────────────────────────┬────────┬────────┬──────────┐
│ Rank │ Clause Heading                       │ Score  │ Method │ Location │
├──────┼──────────────────────────────────────┼────────┼────────┼──────────┤
│ 1    │ Article 7 — Limitation of Liability  │ 0.89   │ hybrid │ §7.3     │
│      │   Section 7.3 — Data Breach          │        │        │          │
│ 2    │ Article 3 — Confidentiality          │ 0.72   │ hybrid │ §3.1     │
│ ...  │                                      │        │        │          │
└──────┴──────────────────────────────────────┴────────┴────────┴──────────┘
```

### Output (JSON mode)
```json
{
  "query": "limitation of liability for data breach",
  "method": "hybrid",
  "top_k": 5,
  "results": [
    {
      "chunk_id": "abc123",
      "text": "The Licensor's aggregate liability...",
      "clause_heading": "Section 7.3 — Data Breach",
      "clause_level": 1,
      "hierarchy_chain": [
        "Article 7 — Limitation of Liability",
        "Section 7.3 — Data Breach"
      ],
      "score": 0.89,
      "method": "hybrid",
      "rank_sparse": 2,
      "rank_dense": 1,
      "rrf_score": 0.0164,
      "rerank_score": null,
      "char_start": 14500,
      "char_end": 14980
    }
  ],
  "timing": {
    "bm25_ms": 12,
    "dense_ms": 245,
    "fusion_ms": 0.4,
    "rerank_ms": null,
    "total_ms": 258
  }
}
```

### Exit Codes
| Code | Meaning |
|---|---|
| `0` | Success — results returned (even if empty) |
| `2` | Error — document not indexed |
| `3` | Error — index database missing/corrupt |
| `4` | Error — embedding model not available for dense/hybrid mode |

### Edge Cases
- **No results**: Print "No relevant clauses found for this query. Try a different query or use --method sparse for broader matching."
- **No embedding model (dense/hybrid)**: Fall back to BM25 with notice. Exit code 0.
- **Reranker validation warning**: If `--rerank` is used and validation says it degrades results, print warning in terminal mode or `"warning"` field in JSON mode.

---

## `openreview index-status [<file>]`

Show indexing status for a document.

### Signature
```
openreview index-status [OPTIONS] [FILE]
```

### Options
| Option | Type | Default | Description |
|---|---|---|---|
| `--db-dir` | `Path` | Platform default | SQLite index directory override |
| `--json` | `flag` | — | Output as JSON |

### Output (terminal)
```
Document: contract-123.ndax
Status:   Indexed (2026-07-03T14:30:00Z)
Chunks:   47
Method:   hybrid
Model:    nomic-embed-text (1024d)
DB size:  3.2 MB
Reranker validation: Not yet benchmarked
```

### Exit Codes
| Code | Meaning |
|---|---|
| `0` | Success |
| `2` | Error — document not indexed |

---

## `openreview index-clear [<file>]`

Remove indexed data for a document.

### Signature
```
openreview index-clear [OPTIONS] [FILE]
```

### Options
| Option | Type | Default | Description |
|---|---|---|---|
| `--all` | `flag` | — | Clear ALL indexes (prompt required) |
| `--db-dir` | `Path` | Platform default | SQLite index directory override |

### Output
```
✓ Index for contract-123.ndax cleared (47 chunks, 1 embedding model)
```

### Exit Codes
| Code | Meaning |
|---|---|
| `0` | Success |
| `2` | Error — document not indexed |

---

## Config Keys (config.yml)

```yaml
retrieval:
  method: hybrid           # default retrieval method (sparse|dense|hybrid)
  top_k: 5                 # default result count
  rrf_k: 60                # RRF fusion constant
  rerank_enabled: false    # reranker default state
  rerank_depth: 20         # candidates for reranking
  embedding_model: nomic-embed-text  # default embedding model (gateway model name)
  db_dir: null             # override database directory (null = platform default)
```
