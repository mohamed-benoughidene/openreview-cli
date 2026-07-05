# CLI Interface Contract: Memo Export

**Spec**: 021 — Memo Export
**Date**: 2026-07-05

---

## `--format` Flag

### Specification

| Property | Value |
|----------|-------|
| **Name** | `--format` |
| **Type** | `str` (one of: `md`, `json`, `docx`) |
| **Default** | `md` |
| **Scope** | Per-command (review-producing subcommands for PreCheck, DealCheck, HireCheck) |
| **Required** | No |
| **Repeatable** | Yes — multiple `--format` flags produce multiple files |
| **Environment variable** | None (CLI-only) |
| **Deduplication** | Duplicate values are ignored — only one file per unique format |

### Validation

- Unsupported format values are rejected with:
  ```
  Error: Unsupported export format: <value>. Supported formats: md, json, docx.
  ```
- Values are case-sensitive (`md`, not `MD` or `Md`).
- Empty string is rejected by Typer.

### Help Text

```
--format TEXT  [default: md]
  Export format(s) for the review memo.
  Supported values: md (Markdown), json (JSON), docx (Word document).
  May be specified multiple times to produce multiple formats in one run.
```

---

## `--output-dir` Flag

### Specification

| Property | Value |
|----------|-------|
| **Name** | `--output-dir` |
| **Type** | `Path` (directory path) |
| **Default** | `review_results/` (relative to working directory) |
| **Scope** | Per-command |
| **Required** | No |
| **Repeatable** | No |
| **Environment variable** | `OPENREVIEW_OUTPUT_DIR` (optional override) |

### Validation

- If the specified directory does not exist, it is created automatically.
- If the directory cannot be created (permissions, read-only filesystem), error:
  ```
  Error: Cannot create output directory: /path/to/dir
  ```
- If the path points to an existing file (not a directory), error:
  ```
  Error: Output path exists and is not a directory: /path/to/file
  ```

### Help Text

```
--output-dir PATH  [default: review_results/]
  Directory where memo files are written.
  Created automatically if it does not exist.
  If not specified, defaults to review_results/ in the current working directory.
```

---

## CLI Invocation Examples

### Default Markdown export
```bash
openreview precheck document.pdf --playbook precheck-nda-v1
```
→ Runs review. Writes Markdown memo to `review_results/precheck-document-{timestamp}.md`.

### Explicit Markdown export
```bash
openreview precheck document.pdf --playbook precheck-nda-v1 --format md
```
→ Same as default. Explicit `--format md` produces Markdown.

### JSON export
```bash
openreview dealcheck agreement.pdf --playbook merger-v2 --format json
```
→ Writes JSON memo to `review_results/dealcheck-agreement-{timestamp}.json`.

### DOCX export
```bash
openreview hirecheck contract.docx --playbook employment-v1 --format docx
```
→ Writes DOCX memo to `review_results/hirecheck-contract-{timestamp}.docx`.

### Multiple formats
```bash
openreview precheck nda.pdf --playbook nda-v1 --format md --format json --format docx
```
→ Writes three files: `.md`, `.json`, `.docx` in `review_results/`.

### Custom output directory
```bash
openreview precheck nda.pdf --playbook nda-v1 --format md --output-dir /shared/reviews/
```
→ Writes Markdown memo to `/shared/reviews/precheck-nda-{timestamp}.md`.

### Deduplication (file exists)
```bash
openreview precheck nda.pdf --playbook nda-v1 --format md
# Run again:
openreview precheck nda.pdf --playbook nda-v1 --format md
```
→ First run: `precheck-nda-{ts}.md`
→ Second run: `precheck-nda-{ts}-1.md` (numeric suffix appended, never overwritten)

---

## Output Filename Convention

Pattern:
```
{review-mode}-{document-stem}-{timestamp}.{ext}
```

| Component | Source | Example |
|-----------|--------|---------|
| `review-mode` | Subcommand name | `precheck`, `dealcheck`, `hirecheck` |
| `document-stem` | Input filename sans path/extension, sanitized | `nda`, `merger-agreement` |
| `timestamp` | UTC compact: `YYYYMMDD-HHMMSS` | `20260705-143022` |
| `ext` | Format-specific | `md`, `json`, `docx` |

**Sanitization**: spaces → hyphens, special characters (non-alphanumeric except hyphen/underscore) removed, lowercased.

**Deduplication**: if exact filename exists, append `-N` (N = 1, 2, 3...) before extension.

---

## Error Handling

| Condition | Error Message | Exit Code |
|-----------|---------------|-----------|
| No review results | `No review results to export. The review did not complete.` | 1 |
| Unsupported format | `Unsupported export format: {fmt}. Supported formats: md, json, docx.` | 2 |
| Cannot create output dir | `Cannot create output directory: {path}` | 3 |
| Output path is file | `Output path exists and is not a directory: {path}` | 3 |
| DOCX write error | `Failed to write DOCX memo: {reason}` (stderr, other formats unaffected) | 0 (partial failure) |

Exit codes 1-3 are new; 0 means at least one format succeeded.

---

## Terminal Output During Export

When `--format` is specified, the terminal output includes export confirmation:

```
✓ Review complete. 12 clauses checked.
  Recommendation: revise
  Memo exported to: review_results/precheck-nda-20260705-143022.md
```

When multiple formats:
```
✓ Review complete. 12 clauses checked.
  Recommendation: revise
  Memo exported to:
    - review_results/precheck-nda-20260705-143022.md
    - review_results/precheck-nda-20260705-143022.json
    - review_results/precheck-nda-20260705-143022.docx
```

When no `--format` (default Markdown):
→ Same terminal output as before (memo export is an add-on, not a replacement for terminal output).

---

## Backward Compatibility

1. **No `--format` flag**: Behaves identically to current behavior — review runs, terminal output shown, no memo file written.
2. **Only `--format md`**: Terminal output unchanged, plus a `.md` file written.
3. **`--output-dir` is optional**: Omitting it uses default `review_results/`. No behavioral change for existing users.
4. **CLI exit codes**: Existing exit codes unchanged. New error codes (1-3) only fire when export is requested and fails.
5. **Existing terminal output**: Unchanged. Memo is an additional output channel, not a replacement.
