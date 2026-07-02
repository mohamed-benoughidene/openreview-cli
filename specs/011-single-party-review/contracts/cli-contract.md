# CLI Contract: `openreview precheck review`

**Spec**: specs/011-single-party-review/spec.md
**Date**: 2026-07-02

## Command

```
openreview precheck review [OPTIONS] PATHS...
```

Reviews one or more contract documents against a 3-position playbook. Produces a per-clause structured report with position assessments, confidence scores, and citations.

## Arguments

### `PATHS...` (positional, required)

One or more document file paths. Glob expansion is supported by the shell.

- Accepts: `.pdf`, `.docx`
- Each path is parsed via `stream_clauses()`, run through the extraction + QA pipeline, and appended to the batch report.
- Mixed document types in a single invocation are supported.

## Options

### `--playbook PATH`

Path to a custom YAML playbook file.

- **Type**: `Path | None`
- **Default**: `None` (use bundled playbook for the mode)
- **Effect**: Overrides the bundled playbook. The playbook is loaded, validated, and used for all documents in the invocation.
- **Error**: If the file does not exist or is not valid YAML matching the Playbook schema, exit with code `PLAYBOOK_ERROR`.

### `--format {text|json}`

Output format.

- **Type**: `Literal["text", "json"]`
- **Default**: `"text"`
- **`text`**: Terminal-formatted report with per-clause table, Amber highlights, and roll-up summary.
- **`json`**: Machine-readable JSON output (see data-model.md for JSON schema). Writes to stdout unless `--output` is specified.

### `--output FILE`

Write output to a file instead of stdout.

- **Type**: `Path | None`
- **Default**: `None` (write to stdout)
- **Effect**: When specified, no output is written to stdout (unless `--verbose` is set).
- **Note**: Progress/status output (stderr) is unaffected.

### `--extraction-model SLOT`

Model slot name for the extraction agent.

- **Type**: `str | None`
- **Default**: `None` (use gateway default routing)
- **Effect**: Routes all extraction calls to the specified model slot. The slot must be configured in the AI Gateway registry.
- **Error**: If the slot does not exist, exit with code `MODEL_NOT_FOUND`.

### `--qa-model SLOT`

Model slot name for the QA verification agent.

- **Type**: `str | None`
- **Default**: `None` (same slot as extraction model, or gateway default if neither specified)
- **Effect**: Routes all QA verification calls to the specified model slot. Enables the SLM-first accuracy-vs-speed trade-off (fast SLM for extraction, larger model for QA).

### `--no-pii`

Skip PII stripping. (Existing flag on the `precheck` command group — inherited by the `review` subcommand.)

- **Type**: `bool` (flag)
- **Default**: `False` (PII stripping is active)
- **Effect**: When set, PII stripping is disabled for the review run. Raw PII may reach the extraction and QA agents.

### `--verbose`

Verbose output.

- **Type**: `bool` (flag)
- **Default**: `False`
- **Effect**: When set, per-clause progress and model response timing are printed to stderr.

## Exit Codes

| Code | Constant | Condition |
|------|----------|-----------|
| 0 | `SUCCESS` | All documents processed successfully |
| 1 | `PARSE_ERROR` | One or more documents could not be parsed |
| 2 | `PLAYBOOK_ERROR` | Custom playbook not found or invalid |
| 3 | `MODEL_NOT_FOUND` | Specified model slot does not exist |
| 4 | `GATEWAY_ERROR` | AI Gateway call failed (network, auth, rate limit) |
| 5 | `INTERNAL_ERROR` | Unexpected error (bug) |

## Examples

### Basic NDA review

```bash
openreview precheck review nda.docx
```

### Custom playbook + JSON output

```bash
openreview precheck review nda.docx \
  --playbook my-terms.yaml \
  --format json \
  --output report.json
```

### Separate model slots for extraction and QA

```bash
openreview precheck review nda.docx \
  --extraction-model ollama/llama3.2:3b \
  --qa-model openai/gpt-4o-mini
```

### Batch review

```bash
openreview precheck review *.docx
```

### Offline mode (all-local, no cloud call)

```bash
openreview precheck review nda.docx
# Both agents use the default local SLM slot (Ollama)
```

## Output Formats

### Text (terminal) format

```
┌──────────────────────────────────────────────────────────────┐
│                    NDA Review Report                         │
│                    precheck-nda-v1                           │
├──────────────────────────────────────────────────────────────┤
│ Document: nda.docx (12 pages, 28 clauses)                    │
│ PII stripped: Yes                                            │
├──────────────────────────────────────────────────────────────┤
│ #   Clause                    Position    Confidence  Amber │
│ ─── ───────────────────────── ─────────── ─────────── ───── │
│ 1   Confidentiality Term      Favorable   0.92             │
│ 2   Permitted Disclosures     Neutral     0.85             │
│ 3   Non-Solicitation          Unfavorable 0.72        ⚠    │
│ 4   Term and Termination      Uncertain   0.45        ⚠    │
│ ...                                                         │
├──────────────────────────────────────────────────────────────┤
│ Summary                                                     │
│ ───────                                                     │
│ Favorable:   12                                             │
│ Neutral:     10                                             │
│ Unfavorable:  4                                             │
│ Uncertain:    2                                             │
│ No-match:     0                                             │
│ Amber flags:  3                                             │
│ Avg confidence: 0.85                                        │
└──────────────────────────────────────────────────────────────┘
```

### JSON format

See `data-model.md` for the full JSON schema. The JSON output is a single `ReviewReport` object serialized with `json.dumps()`.

## Error Behaviour

- **Parse errors**: If a document cannot be parsed, it is skipped with a warning to stderr. Other documents in the batch continue processing. Exit code is `PARSE_ERROR` if any document fails.
- **Model errors**: If a model call fails (timeout, auth, rate limit), the clause assessment is marked as uncertain with the error message. Processing continues.
- **Playbook errors**: If the custom playbook is invalid, the command exits immediately with `PLAYBOOK_ERROR`. No documents are processed.
- **Graceful shutdown**: On `SIGINT` (Ctrl+C), the current clause completes and the partial report is printed before exit.
