# Memo Export

**Feature ID**: 021-memo-export
**Status**: Draft Specification
**Created**: 2026-07-05

---

## 1. Executive Summary

The single-party review pipeline (spec-011) produces a structured `ReviewReport` containing clause-level assessments, confidence scores, color codes (Green/Amber/Red), citation provenance, and playbook comparison results. Today, this report is only viewable in the terminal or writable as raw JSON. Users who need to share, archive, or file review results have no way to produce a formatted summary document.

This specification defines a **memo export** feature for the first three review modes: PreCheck, DealCheck, and HireCheck. Users can export the review results as a formatted memo in three output formats:

- **Markdown (.md)** — human-readable, zero-dependency format. Opens in any text editor, renders on GitHub, GitLab, and most review platforms. Default format.
- **JSON (.json)** — machine-readable. Reuses the existing `ReviewReport` JSON structure with additional memo-specific fields. Used for programmatic consumption, archival, and integration.
- **DOCX (.docx)** — editable document format. Suitable for sharing with stakeholders who expect a Word document. Uses the existing `python-docx` dependency already in the project.

PDF output is explicitly deferred (see §5 Non-Goals).

The memo includes everything a stakeholder needs to understand the review results without opening the CLI:

- **What was checked** — the document name, review mode, playbook used, and date of review
- **Matches** — clauses where the contract satisfies the playbook position, with the playbook text and the matching contract text shown side by side
- **Differences** — clauses where the contract deviates from the playbook, with a description of the deviation and its severity
- **Recommendation** — an overall recommendation (approve, revise, reject) based on the aggregate assessment
- **Green/Amber/Red color coding per clause** — each clause assessment is visually color-coded: Green (matches), Amber (minor difference, acceptable with caveats), Red (significant difference, action recommended)
- **Confidence scores per clause** — a numerical confidence score (0.0–1.0) with a visual bar representation showing how certain the extraction agent is about each assessment
- **Citation grounding provenance** — for each cited clause, the specific clause ID, paragraph index, and line range from the source contract that supports the assessment
- **Disclaimer** — a clearly visible statement that the review is AI-generated, is not legal advice, and should be reviewed by a qualified professional
- **Playbook version used** — the playbook name and semantic version number used for the review

The feature absorbs nine previously deferred enhancements that naturally fit within the memo export scope (see §3 Dependencies for the full list). Each is a presentation or annotation concern — none changes the review pipeline logic.

---

## 2. User Scenarios

### Scenario 1 — Export review results as Markdown memo (Priority: P1)

A lawyer runs a PreCheck on a standard NDA. After the review completes, they want to share the results with their client in a clean, readable format. They run:

```
openreview precheck contract.pdf --playbook nda-v1 --format md
```

The CLI runs the review normally, then writes a Markdown file to `review_results/precheck-nda-20260705-143022.md`. The file contains:

- A header with the document name, review mode, date, and playbook version
- A summary table with the total clauses checked, matched, differed, and the overall recommendation
- Per-clause sections, each with:
  - The clause title and number
  - A Green/Amber/Red badge
  - A confidence bar (`[████████░░] 0.82`)
  - The playbook requirement text
  - The contract clause text
  - Whether it matches or differs, and if it differs, what the issue is
  - Citation reference (clause ID, paragraph index) linked to the source
- A recommendation section with the overall verdict
- A disclaimer at the bottom

**Why this priority**: Markdown is the zero-dependency format that works for every user. Without it, users cannot share results without taking screenshots or copy-pasting terminal output.

**Independent Test**: A test that runs a review with `--format md` on a fixture document, then asserts that the output file exists, is valid Markdown (parses without error), and contains all required sections: header, per-clause assessments with G/A/R badges, recommendation, disclaimer, and playbook version.

**Acceptance Scenarios**:

1. **Given** a completed review, **When** the user specifies `--format md`, **Then** a Markdown file is written to the default output directory with a `.md` extension.
2. **Given** a Markdown memo file, **When** opened in any Markdown renderer, **Then** all sections are visible and properly formatted — no raw syntax errors.
3. **Given** a review with 0 matches, **When** exported to Markdown, **Then** the summary table shows "0 matched" and per-clause sections still render with their content (no empty sections omitted).
4. **Given** a review where every clause matches, **When** exported to Markdown, **Then** the differences section is present but states "No differences found" rather than being omitted.

---

### Scenario 2 — Export review results as JSON memo (Priority: P1)

A compliance team ingests review results into their internal system. They need a machine-readable format that their data pipeline can parse. They run:

```
openreview dealcheck merger-agreement.pdf --playbook merger-v2 --format json
```

The CLI writes a JSON file to `review_results/dealcheck-merger-agreement-20260705-143022.json`. The structure extends the existing `ReviewReport` JSON:

```json
{
  "memo_version": "1.0",
  "mode": "dealcheck",
  "document": "merger-agreement.pdf",
  "playbook": {
    "name": "merger-agreement-v2",
    "version": "2.1.0"
  },
  "review_date": "2026-07-05T14:30:22Z",
  "overall": {
    "recommendation": "revise",
    "clauses_checked": 12,
    "matches": 8,
    "differences": 4,
    "confidence_avg": 0.87
  },
  "clauses": [
    {
      "id": "clause-003",
      "title": "Termination for Convenience",
      "playbook_requirement": "Party may terminate with 30 days written notice",
      "contract_text": "Party may terminate with 60 days written notice",
      "assessment": "difference",
      "color": "amber",
      "confidence": 0.82,
      "citation": {
        "clause_id": "§12.3",
        "paragraph_index": 2,
        "line_range": [45, 48]
      },
      "severity": "minor"
    }
  ],
  "disclaimer": "This review was generated by an AI system and is not legal advice. All results should be reviewed by a qualified legal professional.",
  "tier_info": {
    "privacy_tier": "balanced",
    "pii_stripped": true,
    "entities_redacted": 24
  }
}
```

**Why this priority**: JSON is the integration format. Downstream tools, dashboards, and archival systems consume JSON. Without it, the memo is only human-readable.

**Independent Test**: A test that runs a review with `--format json` on a fixture document, then asserts the output file is valid JSON, contains all required top-level keys (`memo_version`, `mode`, `playbook`, `clauses`, `disclaimer`), and each clause entry has the required fields (`id`, `assessment`, `color`, `confidence`, `citation`).

**Acceptance Scenarios**:

1. **Given** a completed review, **When** the user specifies `--format json`, **Then** a JSON file is written with all required memo fields.
2. **Given** a JSON memo file, **When** parsed by a JSON parser, **Then** the file is syntactically valid and contains no unexpected or missing keys per the schema.
3. **Given** a review with a single clause, **When** exported to JSON, **Then** the `clauses` array contains exactly one entry.
4. **Given** a review run on Performance tier, **When** exported to JSON, **Then** the `tier_info` block includes `"privacy_tier": "performance"`.

---

### Scenario 3 — Export review results as DOCX memo (Priority: P2)

An in-house counsel needs to submit review results to the board in Word format. They run:

```
openreview hirecheck employment-contract.docx --playbook employment-v1 --format docx
```

The CLI writes a DOCX file to `review_results/hirecheck-employment-contract-20260705-143022.docx`. The DOCX document mirrors the Markdown layout:

- Cover page with document name, review mode, date, playbook version
- Summary table
- Per-clause sections with G/A/R formatting (Green text fill for matches, Amber for minor, Red for significant)
- Confidence bars rendered as table cells with proportional width
- Recommendation section
- Disclaimer
- All text is editable — the recipient can modify, comment, and save

**Why this priority**: DOCX is the de facto standard for legal document exchange. Many stakeholders expect a Word document they can open and edit. Without it, the legal workflow is incomplete.

**Independent Test**: A test that runs a review with `--format docx`, opens the resulting file with `python-docx`, and asserts that the document contains at least one paragraph containing the disclaimer text and at least one table cell containing a confidence value.

**Acceptance Scenarios**:

1. **Given** a completed review, **When** the user specifies `--format docx`, **Then** a valid `.docx` file is written that can be opened by `python-docx` without errors.
2. **Given** a DOCX memo with color-coded clauses, **When** opened in Word or LibreOffice, **Then** Green/Amber/Red fill colors are applied to the appropriate cells.
3. **Given** a DOCX memo, **When** the document is saved and re-opened, **Then** all text content is preserved and editable.
4. **Given** a DOCX memo, **When** inspected with `python-docx`, **Then** the document contains at least one table (the summary) and at least one paragraph with the disclaimer text.

---

### Scenario 4 — Custom output directory (Priority: P3)

A team runs batch reviews and wants all memos in a shared directory. They specify:

```
openreview precheck nda.pdf --playbook nda-v1 --format md --output-dir /shared/reviews/
```

The memo is written to `/shared/reviews/precheck-nda-20260705-143022.md` instead of the default `review_results/` directory.

**Why this priority**: Custom output directories support team workflows and CI integration. Without this, users must move files manually after each export.

**Independent Test**: A test that runs a review with `--format md --output-dir /tmp/test-memos/` and asserts the output file exists under the specified directory.

**Acceptance Scenarios**:

1. **Given** the `--output-dir` flag, **When** the review completes, **Then** the memo is written to the specified directory.
2. **Given** the `--output-dir` flag with a non-existent directory, **When** the review completes, **Then** the directory is created before writing (no "directory not found" error).
3. **Given** no `--output-dir` flag, **When** the review completes, **Then** the memo is written to the default `review_results/` directory.

---

### Scenario 5 — Multiple export formats in one run (Priority: P3)

A user needs both a human-readable memo and a machine-readable JSON for archival. They run:

```
openreview dealcheck agreement.pdf --playbook mnda-v1 --format md --format json
```

Two files are written to the output directory: one `.md` and one `.json`, both with the same base filename but different extensions.

**Why this priority**: Commonly, users want both formats. Requiring two separate runs wastes time.

**Independent Test**: A test that runs a review with `--format md --format json` and asserts that both a `.md` and a `.json` file exist in the output directory with matching base names.

**Acceptance Scenarios**:

1. **Given** two `--format` flags, **When** the review completes, **Then** one file per specified format is written.
2. **Given** duplicate `--format` flags (e.g., `--format md --format md`), **When** the review completes, **Then** only one `.md` file is written (deduplication).

---

### Scenario 6 — Memo contains all required sections regardless of output format (Priority: P1)

A user exports a review of a contract that has no differences (every clause matches the playbook). The memo must still include:
- The playbook version
- A summary showing 100% match rate
- Per-clause assessments (all Green)
- A positive recommendation
- The disclaimer

No section may be omitted because the data is "obvious" or "uninteresting." The memo is a standalone document — it must be complete.

**Independent Test**: A test that runs a review on a contract that matches the playbook perfectly, exports to Markdown, and asserts the output contains: playbook version, disclaimer text, at least one per-clause assessment, and the overall recommendation.

**Acceptance Scenarios**:

1. **Given** a perfect-match review, **When** exported, **Then** the disclaimer is present in all output formats.
2. **Given** a perfect-match review, **When** exported, **Then** the differences section states "No differences found" rather than being omitted entirely.
3. **Given** a review with color coding, **When** exported to Markdown, **Then** Green/Amber/Red are represented as text badges or emoji indicators (no dependency on CSS or rendering engine).
4. **Given** a review with confidence scores, **When** exported to any format, **Then** each clause assessment includes its confidence score and a visual indicator.

---

### Edge Cases

- **Empty review results** — If the review pipeline fails before producing clause assessments, the memo export produces an error: "No review results to export. The review did not complete."
- **Output file already exists** — If a file with the same name exists in the output directory, a numeric suffix is appended (e.g., `precheck-nda-20260705-143022-1.md`). The existing file is never overwritten without warning.
- **Unsupported format** — If the user specifies `--format pdf` (before PDF support lands), the CLI produces an error: "Unsupported export format: pdf. Supported formats: md, json, docx."
- **DOCX fails to generate** — If `python-docx` encounters an error (disk full, permissions), the error is surfaced to the user and the file is not written. Other formats are still written if requested.
- **Very long clause text** — Clauses with text longer than 10,000 characters are truncated with an ellipsis and a note: "Truncated to 10,000 characters. See the citation reference for the full text."
- **Missing citation provenance** — If the review pipeline did not produce citation data for a clause, the memo shows "Citation: not available" rather than omitting the field.
- **Multiple documents in a single review** — For multi-file document sets (exhibits), each clause assessment includes the source filename. The memo groups clauses by source document.

---

## 3. Dependencies & Related Specifications

The memo export feature is purely a presentation layer on top of existing infrastructure. It does not change the review pipeline, the extraction agent, or the QA agent.

| Dependency | Description | Relationship |
|---|---|---|
| Single-Party Review (spec-011) | 3-agent pipeline: extraction, QA, report. Produces `ReviewReport` with clause assessments, confidence, color codes | Memo export reads the `ReviewReport` produced by this pipeline. No pipeline changes needed. |
| G/A/R Color Coding (spec-013) | Green/Amber/Red color assignment per clause assessment, with defined mapping from assessment type to color | Memo export renders the color assigned by this system. Colors are read from the report, not computed in the exporter. |
| Citation Grounding (spec-012) | Clause-level citation provenance: clause ID, paragraph index, line range from source contract | Memo export displays citation data from the report. Citation is read-only — the exporter does not validate or compute citations. |
| Prompt Management (spec-009) | Versioned prompt storage with semantic version numbers | Memo export reads the playbook name and version from the report metadata. |
| Benchmark Harness (spec-010) | Performance and accuracy measurement framework | Memo export quality is validated by benchmark tests that assert output content and structure. |
| Privacy Tier Routing (spec-020) | Reports privacy tier used and number of PII entities redacted | Memo export includes tier information in the JSON format output. |

**Absorbed deferred enhancements:** The following items from the project's deferred list naturally belong in the memo export scope. Each is a presentation or annotation concern — none changes review pipeline logic:

| Deferred ID | Description | How it is absorbed |
|---|---|---|
| D-6 | Three-color rendering per clause | Rendered as colored badges (Markdown), cell fill colors (DOCX), or string values (JSON) |
| D-7 | Grounding explanation + per-clause confidence bar | Each clause shows citation reference with provenance. Confidence shown as bar and numeric value |
| D-4 | Semantic citation relevance display | Citation includes clause ID, paragraph index, and line range for provenance |
| D-5 | Paragraph-range validation for citations | Citation data includes `line_range` validated by the grounding system; memo displays it as provided |
| D-8 | Exhibit-aware citation for multi-file document sets | When review spans multiple files, each clause assessment includes source filename. Memo groups by document |
| D-16 | Output formatting for generated answers | Memo export IS the output formatting solution. Three formats supported |
| D-20 | AI-suggested playbook changes presentation | When the extraction agent suggests playbook updates, these appear in the differences section as "Suggested playbook update" |
| D-30 | Data preservation tracking in output | Memo header includes review date, playbook version, and privacy tier — enabling traceability |
| D-34 | Per-clause/per-page tier selection annotation | Privacy tier is recorded per operation in JSON output. Tier is uniform per review, not per clause |

---

## 4. Functional Requirements

Each requirement is testable and described in plain English. No internal codes are used.

### FR-01 — Memo Export for PreCheck, DealCheck, HireCheck

The system **must** support exporting review results as a formatted memo for three review modes: PreCheck, DealCheck, and HireCheck. Each mode produces the same memo structure. The mode name appears in the memo header and in the filename. The exporter does not change behavior based on mode — the content differences come from the review pipeline, not the export layer.

### FR-02 — Three Output Formats

The system **must** support exactly three output formats:
- **Markdown (.md)** — default format. No additional dependencies. Must render correctly in any standard Markdown renderer (GitHub-Flavored Markdown preferred).
- **JSON (.json)** — machine-readable format. Structure extends the existing `ReviewReport` with a `memo_version` field, `playbook` metadata block, `disclaimer` string, and `tier_info` block.
- **DOCX (.docx)** — editable Word document format. Uses the existing `python-docx` library. Must be openable in Microsoft Word, LibreOffice, and Google Docs without errors.

Format is specified via a `--format` CLI flag. Multiple `--format` flags may be specified. If no `--format` flag is given, the default is Markdown.

### FR-03 — Required Memo Sections

Every memo, regardless of output format, **must** include all of the following sections:

1. **Header** — document name, review mode, review date, playbook name and version
2. **Summary** — total clauses checked, count of matches, count of differences, average confidence, overall recommendation
3. **Per-Clause Assessments** — for each clause in the review report:
   - Clause title and identifier
   - Green/Amber/Red color indicator
   - Confidence score (0.0–1.0) with a visual representation
   - Playbook requirement text
   - Contract clause text
   - Assessment type (match or difference)
   - Citation provenance: clause ID, paragraph index, line range
4. **Overall Recommendation** — based on the aggregate assessment, one of: approve, revise, or reject
5. **Disclaimer** — clearly visible statement that the review is AI-generated and not legal advice
6. **Playbook Version** — the playbook name and semantic version used

### FR-04 — Color Coding Per Clause

Each clause assessment **must** display a Green, Amber, or Red indicator based on the color assigned by the review pipeline:

- **Green** — clause matches the playbook requirement. No action needed.
- **Amber** — clause differs from the playbook in a minor way. Acceptable with caveats or requires minor revision.
- **Red** — clause significantly differs from the playbook. Action recommended (renegotiate, reject, or seek legal advice).

Color is read from the `ReviewReport` — the exporter does not compute or override colors.

**Rendering by format:**

| Format | Green | Amber | Red |
|---|---|---|---|
| Markdown | `🟢` or `✅` badge with green text | `🟡` or `⚠️` badge with amber text | `🔴` or `❌` badge with red text |
| JSON | `"color": "green"` string value | `"color": "amber"` string value | `"color": "red"` string value |
| DOCX | Green cell fill (RGB 198,239,206) | Amber cell fill (RGB 255,235,156) | Red cell fill (RGB 255,199,206) |

### FR-05 — Confidence Scores Per Clause

Each clause assessment **must** display its confidence score, both as a numeric value (0.0–1.0) and as a visual indicator (progress bar or proportional representation).

**Rendering by format:**

| Format | Visual representation |
|---|---|
| Markdown | ASCII bar: `[████████░░] 0.82` |
| JSON | Numeric value: `"confidence": 0.82` |
| DOCX | Table cell with inner table or merged cell whose width is proportional to the confidence value |

### FR-06 — Citation Grounding Provenance

Each clause assessment **must** display the citation provenance data produced by the citation grounding system:

- Clause identifier from the source contract (e.g., `§12.3`)
- Paragraph index within the clause
- Line range (start line, end line) in the source document

If citation data is unavailable for a clause, the memo displays "Citation: not available" rather than omitting the field. The exporter does not validate or compute citation data — it displays what the review pipeline produced.

### FR-07 — Disclaimer

Every memo **must** include the following disclaimer text at the bottom:

> **Disclaimer**: This review was generated by an AI system and is not legal advice. The analysis is based on automated comparison of the provided document against the selected playbook. Results may contain errors, omissions, or inaccuracies. All review results should be independently verified by a qualified legal professional before taking any action based on them.

This text must be visually distinct from the body content (e.g., italic, bordered block, or separated by a horizontal rule). It must be present in all output formats and cannot be suppressed or modified by any CLI flag.

### FR-08 — Playbook Version in Output

Every memo **must** include the playbook name and semantic version (e.g., `nda-v1`, version `1.2.0`) used for the review. This appears in the header section and in the JSON metadata block.

### FR-09 — Output File Naming

The system **must** generate output filenames using the following convention:

```
{review-mode}-{document-stem}-{timestamp}.{format-extension}
```

- `review-mode`: one of `precheck`, `dealcheck`, `hirecheck`
- `document-stem`: the input filename without directory and without extension, sanitized (spaces replaced with hyphens, special characters removed)
- `timestamp`: compact UTC timestamp: `YYYYMMDD-HHMMSS`
- `format-extension`: `md`, `json`, or `docx`

Example: `precheck-nda-20260705-143022.md`

If a file with the same path already exists, a numeric suffix is appended: `precheck-nda-20260705-143022-1.md`. Existing files are never silently overwritten.

### FR-10 — Output Directory

The system **must** write memo files to a configurable output directory. Default: `review_results/` relative to the working directory. The user may override with `--output-dir <path>`. If the specified directory does not exist, it **must** be created automatically. If the directory cannot be created (permissions, read-only filesystem), an error is returned and no file is written.

### FR-11 — Multiple Formats in Single Export

The system **must** accept multiple `--format` flags in a single CLI invocation. Each specified format produces an output file. All files share the same base filename but have different extensions. Duplicate format flags are ignored (no duplicate files).

### FR-12 — All Required Sections in All Formats

Every output format **must** include all required memo sections (FR-03). No section may be omitted based on the data being empty or uniform. The "differences" section must still appear when there are no differences (stating "No differences found"). The disclaimer must appear in every memo regardless of content.

### FR-13 — Error Handling for Export

If the review pipeline did not complete or produced no clause assessments, the export **must** fail with a clear error message: "No review results to export. The review did not complete." If an output format generation fails (e.g., DOCX write error), the error for that format is reported but does not prevent other formats from being written.

---

## 5. Non-Goals / Out of Scope

The following are explicitly out of scope for this specification:

- **PDF output** — PDF generation via WeasyPrint is deferred pending user demand. Users who need PDF can convert from Markdown using any Markdown-to-PDF tool. (Reference: D-4 resolution in the project deferred list.)
- **Memo export for other modes** — This feature covers PreCheck, DealCheck, and HireCheck only. Other modes (BilateralComparison, etc.) are deferred until their review pipelines produce compatible `ReviewReport` output.
- **Custom memo templates** — The memo structure and layout are fixed. Custom branding, logo insertion, or field reordering are not supported in this version. Users can customize the Markdown output after generation.
- **Report-to-memo comparison** — No diffing or comparison between multiple memos. Each memo is a snapshot of a single review.
- **Batch export** — No batch processing of multiple review results into a single memo or zip archive. Each review produces its own memo file.
- **Memo summarization** — The memo does not include an AI-generated executive summary beyond the summary table. The review pipeline's own recommendation is used as-is.
- **E-mail or direct sharing** — No integration with e-mail, Slack, or other sharing channels. The memo is written to a local file only.
- **Memo version history** — No tracking of memo revisions or comparisons with previous versions of the same document.
- **Real-time memo generation** — The memo is generated after the review completes. No streaming or incremental output.

---

## 6. Success Criteria

Each criterion is measurable, technology-agnostic, and verifiable without implementation knowledge.

### SC-01 — Review results can be exported as a Markdown document

When a user runs a review with `--format md`, a valid Markdown file is written containing all required memo sections. The file renders correctly in at least one standard Markdown renderer (verified programmatically by parsing the output).

*Verification*: A test runs a review on a fixture document with `--format md`, reads the output file, and asserts that it contains: a `#` or `##` heading for each required section, the disclaimer text as a distinct block, at least one per-clause assessment with a color badge (`🟢`/`🟡`/`🔴` or `✅`/`⚠️`/`❌`), a confidence bar pattern, and the playbook version string.

### SC-02 — Review results can be exported as a JSON document

When a user runs a review with `--format json`, a valid JSON file is written. Every required top-level key exists, and every clause entry contains all required fields.

*Verification*: A test runs a review on a fixture document with `--format json`, parses the output with `json.loads()`, and asserts the presence of keys: `memo_version`, `mode`, `document`, `playbook` (with `name` and `version`), `review_date`, `overall` (with `recommendation`, `clauses_checked`, `matches`, `differences`), `clauses` (each with `id`, `assessment`, `color`, `confidence`, `citation`), and `disclaimer`.

### SC-03 — Review results can be exported as a DOCX document

When a user runs a review with `--format docx`, a valid `.docx` file is written. The file can be opened by `python-docx` without errors. It contains at least one table and a paragraph containing the disclaimer text.

*Verification*: A test runs a review on a fixture document with `--format docx`, opens the resulting file with `python-docx`, and asserts that `doc.tables` is non-empty and at least one paragraph contains the disclaimer text.

### SC-04 — Color coding matches the review pipeline's assessment

For every clause, the color displayed in the memo matches the color assigned by the review pipeline. Green means match, Amber means minor difference, Red means significant difference.

*Verification*: A test runs a review on a document with known matches and differences, exports to all three formats, and asserts that the color value in each format matches the expected value from the pipeline output.

### SC-05 — Confidence scores are preserved and displayed

For every clause, the confidence score in the memo matches the score from the review pipeline. The score is displayed both as a number (0.0–1.0) and as a visual indicator.

*Verification*: A test exports a review to JSON, parses the output, and asserts that every clause entry has a `confidence` field with a float value between 0.0 and 1.0. For Markdown, a test asserts the presence of a bar pattern (`[#+#]`) and numeric value.

### SC-06 — Citation provenance is present for every clause

For every clause that has citation data, the memo includes the clause ID, paragraph index, and line range. For clauses without citation data, the memo shows "not available" rather than omitting the field.

*Verification*: A test exports a review to JSON and asserts that every clause entry has a `citation` field. If citation data exists, the field contains `clause_id`, `paragraph_index`, and `line_range`. If not, the value is `null` or an empty object.

### SC-07 — Disclaimer is present in every memo

Every exported memo, regardless of format, contains the AI-generated disclaimer text. The disclaimer cannot be suppressed or modified by any CLI flag.

*Verification*: A test exports to each format and asserts that the disclaimer text (or a close semantic match) appears in the output. For JSON, the `disclaimer` key exists. For Markdown and DOCX, the text string appears in the content.

### SC-08 — Playbook version is recorded in every memo

Every exported memo contains the playbook name and semantic version used for the review.

*Verification*: A test exports to each format and asserts the presence of the playbook name and version string. For JSON, the `playbook.name` and `playbook.version` keys exist.

### SC-09 — Multiple export formats in one run produce all requested files

When a user specifies multiple `--format` flags, one file per distinct format is written. All files share the same base filename with different extensions.

*Verification*: A test runs `--format md --format json` and asserts that both a `.md` and a `.json` file exist with the same base name in the output directory. A third format (`.docx`) produces three files.

### SC-10 — Custom output directory is respected

When a user specifies `--output-dir <path>`, the memo file(s) are written to the specified path. If the path does not exist, it is created.

*Verification*: A test runs with `--output-dir /tmp/test-memos/` and asserts the output file exists under that directory. A second test uses a non-existent path and asserts the directory is created.

### SC-11 — Memo export does not modify the review pipeline

The memo export feature loads the `ReviewReport` produced by the review pipeline but makes no changes to it. Pipeline behavior is identical regardless of whether export is requested.

*Verification*: A test runs a review twice with identical inputs, once with `--format md` and once without. The resulting `ReviewReport` objects are identical in structure and content.

---

## 7. Assumptions

- The `ReviewReport` produced by the review pipeline (spec-011) includes all fields needed for the memo: clause assessments, colors, confidence scores, citation provenance, playbook metadata (name and version), and overall recommendation. If the report lacks a required field, the exporter uses a sensible default (e.g., "unknown" for missing playbook version, "not available" for missing citation data).
- The review pipeline runs to completion before any export occurs. The exporter receives the completed `ReviewReport` object as input — it does not stream or assemble the report incrementally.
- `python-docx` is already a project dependency and is available for DOCX generation. No additional DOCX-related dependencies are needed.
- Markdown rendering follows GitHub-Flavored Markdown (GFM) conventions, which is the most widely supported standard. Memo files render correctly on GitHub, GitLab, Bitbucket, and common Markdown tools (Pandoc, Markdown Preview Enhanced).
- The `--format` CLI flag is already wired in the Typer CLI framework. Adding new values (`md`, `json`, `docx`) follows the same pattern as existing flags.
- The `review_results/` directory exists or can be created. If it does not exist and cannot be created, the error is surfaced to the user.
- Users of DOCX format have access to Microsoft Word, LibreOffice, or Google Docs. The exporter generates a standard `.docx` file compatible with all three.
- All nine absorbed deferred items (D-4, D-5, D-6, D-7, D-8, D-16, D-20, D-30, D-34) are pure presentation concerns that do not require changes to the review pipeline, citation grounding, or color assignment systems. If any of these assumptions is incorrect, the item is unabsorbed and returned to the deferred list.

---

## 8. Key Entities

### MemoFormat

An enumeration with three values: `markdown`, `json`, `docx`. Each value maps to a file extension and a rendering implementation. Additional values can be added later without changing the export interface.

### MemoExporter

The central class that converts a `ReviewReport` into a formatted memo. For each requested `MemoFormat`, it:

1. Reads the `ReviewReport` (clause assessments, colors, confidence scores, citations, playbook metadata, recommendation)
2. Constructs the memo sections (header, summary, per-clause, recommendation, disclaimer)
3. Renders the sections in the target format (Markdown text, JSON structure, DOCX document)
4. Writes the output to the specified directory with the correct filename and extension

The exporter receives the report at construction time. It does not call any review pipeline components.

### CitationProvenance

A data object containing the citation data for a single clause assessment:
- `clause_id`: the clause identifier from the source contract (e.g., `§12.3`)
- `paragraph_index`: the paragraph index within the clause
- `line_range`: the start and end line numbers in the source document

This data is read from the `ReviewReport` and displayed as-is. No validation or computation is performed by the exporter.

### MemoReport

The JSON-specific output structure. Extends the `ReviewReport` JSON with:
- `memo_version`: a semantic version string for the memo schema (starts at `1.0`)
- `playbook`: a metadata block with `name` and `version`
- `disclaimer`: the disclaimer text string
- `tier_info`: privacy tier information (if available from spec-020)

---

## 9. Quality Checklist

See `checklists/requirements.md` for the spec quality validation checklist.
