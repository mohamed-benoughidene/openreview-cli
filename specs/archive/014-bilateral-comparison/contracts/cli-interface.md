# CLI Interface Contract — Bilateral Comparison

**Feature**: 014-bilateral-comparison | **Date**: 2026-07-03
**Spec Reference**: [`spec.md`](./spec.md) §2–§3
**Existing Pattern**: [`src/openreview_cli/app.py`](../../src/openreview_cli/app.py) — `review` command

---

## Command

```bash
openreview precheck compare <doc_a> <doc_b> [OPTIONS]
```

### Positional Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `doc_a` | `str` | Yes | Path to Party A's document (PDF or DOCX) |
| `doc_b` | `str` | Yes | Path to Party B's document (PDF or DOCX) |

Both arguments are required. The first document is "Party A" and the second
is "Party B" — the comparison is symmetric (neither side is "standard").
See spec §6 assumption 8.

### Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--playbook` | `str \| None` | `None` | Path to custom YAML playbook override. Default uses bundled NDA playbook. |
| `--extraction-model` | `str \| None` | `None` | Model slot for the extraction agent. Also used for the comparison agent (FR-3). |
| `--qa-model` | `str \| None` | `None` | Model slot for the QA verification agent. `None` = use extraction model. |
| `--confidence-threshold` | `float` | `0.7` | Amber boundary for divergence detection confidence (0.0–1.0). Independent of single-party threshold. Note: accuracy ceiling ~64% F1 — set generously. |
| `--format` | `str` | `text` | Output format: `text` (terminal report) or `json` (structured JSON). |
| `--output` | `str \| None` | `None` | Write output to file path instead of stdout. |
| `--align-only` | `bool` | `False` | Only run parsing and alignment, skip inference pipeline. Output alignment table. |
| `--verbose` | `bool` | `False` | Show full RCBSF classification, alignment_quality, and comparison agent rationale in terminal output. |
| `--no-pii` | `bool` | `False` | Disable PII stripping on both documents. |
| `--conservative` | `bool` | `False` | Shortcut for `--confidence-threshold 0.8`. Maximum sensitivity — favors recall over precision. |
| `--grounding-mode` | `str` | `strict` | Citation grounding mode: `strict` (ungrounded excluded) or `lenient` (flagged). |
| `--no-grounding` | `bool` | `False` | Skip citation grounding entirely. |
| ~~`--share-data`~~ | ~~`bool`~~ | ~~`False`~~ | **DEFERRED** — opt-in data collection deferred to future spec pending constitutional amendment. Not in NX-1 scope. |

### Mutual Exclusions

- `--no-pii` and any PII-related config flag: if a PII threshold flag is
  added in future, `--no-pii` SHALL override it.
- `--align-only` and `--output`: alignment-only output goes to stdout
  regardless. Users who want machine-readable alignment output use
  `--align-only --format json` (also stdout).
- `--conservative` and `--confidence-threshold`: mutually exclusive.
  `--conservative` is a convenience shortcut only.

---

## Exit Codes

| Code | Condition |
|------|-----------|
| 0 | Success — comparison completed, output written |
| 1 | Error — document missing, corrupt, password-protected, or unsupported format |
| 2 | Partial processing — one document had partial PII processing issues |
| 3 | Configuration error — mutually exclusive flags used |
| 8 | Parse error — one or both documents failed to parse (reusing parsing exit code) |

---

## Output Format — Terminal (default `--format text`)

```text
╔══════════════════════════════════════════════════════════════╗
║  NX-1 BILATERAL COMPARISON — EXPERIMENTAL FEATURE           ║
║  Comparison accuracy has known limitations (best ≤64% F1).  ║
║  Do not rely on this tool for legal advice.                 ║
╚══════════════════════════════════════════════════════════════╝

Documents:
  Party A: my-nda.pdf (12 pages, 28 clauses)
  Party B: their-nda.pdf (15 pages, 30 clauses)
  Confidence threshold: 0.7

─────────────────────────────────────────────────────────────
 Clause Pair      A Position     B Position     Divergence   Conf.   Status
─────────────────────────────────────────────────────────────
 Confidentiality  unfavorable    favorable      evidence      0.82    🔴 Red
 Exclusions      favorable      favorable      —             0.95    🟢 Green
 Term            neutral        unfavorable    suggestion    0.76    🟠 Amber
 Return of       favorable      favorable      —             0.91    🟢 Green
 Materials
 ...

 Unmatched (Party A only): clause-014 (Indemnification)
 Unmatched (Party B only): clause-017, clause-023

─────────────────────────────────────────────────────────────
 Summary
─────────────────────────────────────────────────────────────
  Matched pairs:   25
  Unmatched:       1 (A: 1, B: 2)
  Divergences:     3 (evidence: 1, suggestion: 2)
  Agreement rate:  88%
  Amber rate:      8% (2/25)
  Avg alignment:   0.94

══════════════════════════════════════════════════════════════
  EXPERIMENTAL — Review all results manually.
══════════════════════════════════════════════════════════════
```

### Verbose Output (`--verbose`)

Shows per-pair:
- Full RCBSF dimension classification
- `alignment_quality` value
- Comparison agent rationale and citations
- Both clause texts (truncated to 200 chars)

---

## Output Format — JSON (`--format json`)

```json
{
  "schema_version": "1.0.0",
  "experimental": true,
  "disclaimer": "Comparison accuracy has known limitations...",
  "document_a": {
    "filename": "my-nda.pdf",
    "page_count": 12,
    "clause_count": 28,
    "pii_stripped": true,
    "parsed_at": "2026-07-03T12:00:00Z"
  },
  "document_b": { "...": "..." },
  "alignment": {
    "pairs": [
      {
        "heading": "Confidentiality",
        "clause_id_a": "clause-001",
        "clause_id_b": "clause-002",
        "alignment_quality": 1.0,
        "match_method": "exact_heading",
        "index_a": 0,
        "index_b": 1
      }
    ],
    "unmatched_a_ids": ["clause-014"],
    "unmatched_b_ids": ["clause-017", "clause-023"],
    "total_a": 28,
    "total_b": 30,
    "alignment_rate": 0.93
  },
  "assessments": [
    {
      "pair_id": "pair-001",
      "clause_heading": "Confidentiality",
      "party_a_assessment": { "...": "..." },
      "party_b_assessment": { "...": "..." },
      "divergence": "evidence",
      "confidence": 0.82,
      "alignment_quality": 1.0,
      "color": "red",
      "citations": ["excerpt from A", "excerpt from B"],
      "rationale": "The evidentiary standard differs..."
    }
  ],
  "summary": {
    "total_pairs": 25,
    "divergences": 3,
    "divergences_by_dimension": {
      "evidence": 1,
      "suggestion": 2
    },
    "unmatched_a": 1,
    "unmatched_b": 2,
    "agreement_rate": 0.88,
    "green_count": 20,
    "amber_count": 2,
    "red_count": 3,
    "avg_alignment_quality": 0.94,
    "confidence_threshold": 0.7
  }
}
```

---

## Error Messages

### Document not found
```
Error: File not found: path/to/document.pdf
```

### Parse failure
```
Error: Failed to parse 'their-nda.pdf': [specific error from parser]
       The file may be corrupt, password-protected, or in an unsupported format.
       Exit code: 1
```

### Both documents fail
First failure exits immediately — no partial output per spec §8.

### Mutually exclusive flags
```
Error: --conservative and --confidence-threshold are mutually exclusive
       Exit code: 3
```

### Confidence threshold out of range
```
Error: --confidence-threshold must be between 0.0 and 1.0, got 1.5
```

---

## Stderr Behavior

| Condition | Output |
|-----------|--------|
| First `compare` invocation on machine | Non-suppressible one-time experimental warning |
| Every `compare` invocation | Disclaimer to stderr |
| `--verbose` | Per-clause progress: "Processing Party A: clause-001...", "Aligning clause pairs..." |
| Error | Error message to stderr, exit code, no partial output |
| ~~`--share-data` not set~~ | ~~Reminder (once per session, to stderr)~~ — DEFERRED |

---

## Consistency with `review` Command

| Aspect | `review` | `compare` |
|--------|----------|-----------|
| Document args | list of paths | exactly 2 paths |
| Playbook | `--playbook` | `--playbook` |
| Extraction model | `--extraction-model` | `--extraction-model` |
| QA model | `--qa-model` | `--qa-model` |
| Confidence threshold | `--confidence-threshold` (default 0.7) | `--confidence-threshold` (default 0.7) |
| Format | `--format text\|json` | `--format text\|json` |
| Output file | `--output` | `--output` |
| PII | `--no-pii` | `--no-pii` |
| Verbose | `--verbose` | `--verbose` |
| Grounding | `--grounding-mode`, `--no-grounding` | `--grounding-mode`, `--no-grounding` |
| Bilateral-only | — | `--align-only`, `--conservative` ~~`, --share-data`~~ (DEFERRED) |

The `compare` command is intentionally a superset of `review`'s flags,
extended with bilateral-specific options. Flag names and types are
identical where they serve the same purpose.

**Blueprint references**: spec §2 (user scenarios), §3 FR-5–FR-9, spec 011
CLI pattern, §10 Q-4, Q-6
