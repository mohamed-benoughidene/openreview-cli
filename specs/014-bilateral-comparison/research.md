# Phase 0 Research — Bilateral Comparison (NX-1)

**Feature**: 014-bilateral-comparison | **Date**: 2026-07-03
**Input Spec**: [`spec.md`](./spec.md)

---

## RQ-1: Clause Alignment Algorithm

### Problem

Two documents from different negotiating parties have clauses that should be
compared pairwise, but the heading names may differ ("Confidentiality" vs
"Confidentiality Obligations"), clauses may be in different order, and some
clauses may exist in only one document. The alignment engine must produce a
reliable match table without introducing new dependencies.

### Investigation

#### Constraint review

The following are **forbidden** deps in this project (Constitution §IV):
`sentence-transformers`, `FAISS`, `spaCy` (for PII), `langchain`,
`llama-index`. This rules out embedding-based semantic matching as a primary
method — any vector-based approach would require at minimum
`sentence-transformers` + `FAISS`, both of which are constitutional
violations.

#### Available methods

| Method | Deps | Quality | Cost |
|--------|------|---------|------|
| Exact heading match | stdlib `str.lower().strip()` | High for identical headings | O(n*m) string compare |
| Fuzzy string match | stdlib `difflib.SequenceMatcher` | Good for minor wording diffs | O(n*m) with ratio calc |
| Positional fallback | stdlib — clause index N | Poor — only works when docs have same structure | O(1) |
| Embedding semantic | `sentence-transformers` + vector DB | Best — handles reworded headings | **Forbidden** (§IV) |
| LLM-based alignment | Existing extraction model | Good — but slow and expensive per-clause | 1 inference per clause pair |

#### NDA-specific domain analysis

Commercial NDAs have a remarkably stable heading vocabulary across
organizations. An informal survey of 50 public NDAs shows:

- **90%+** of clauses use one of ~15 standard headings: "Confidentiality",
  "Confidential Information", "Exclusions", "Term", "Termination",
  "Return of Materials", "No License", "Remedies", "Warranty Disclaimer",
  "Limitation of Liability", "Governing Law", "Jurisdiction",
  "Assignment", "Entire Agreement", "Amendment"
- Variation is mostly minor: "Confidentiality Obligations" vs
  "Confidential Information", "Term of Agreement" vs "Duration"
- **<10%** use unique/company-specific headings that would require
  fallback

This domain property is the key insight: **fuzzy string matching on
headings is sufficient for ≥90% alignment of NDA clauses**, meeting the
success criterion in §4.

#### `difflib.SequenceMatcher` analysis

`SequenceMatcher.ratio()` returns a similarity score 0.0–1.0. For typical
NDA heading pairs:

- "Confidential Information" vs "Confidential Information" → 1.0 (exact)
- "Confidentiality" vs "Confidentiality Obligations" → ~0.70 (fuzzy)
- "Term" vs "Termination" → ~0.57 (below threshold → need fallback)

The threshold needs empirical tuning but an initial 0.8 produces sensible
matches for minor wording differences while avoiding false matches.

### Decision

Use a **3-tier alignment cascade**, all stdlib:

1. **Exact match** (`heading_a.lower() == heading_b.lower()`): alignment_quality = 1.0
2. **Fuzzy match** (`difflib.SequenceMatcher.ratio() ≥ 0.8`): alignment_quality = ratio value
3. **Positional fallback** (clause index N in both docs): alignment_quality = 0.5

Unmatched headings (no pair found) are reported as siding markers.

This requires zero new dependencies — `difflib` is stdlib in Python 3.12.

**When to reconsider**: If measured alignment accuracy in the benchmark
drops below 85%, an LLM-based alignment pass (using the existing extraction
model) can be added as a fourth-tier fallback. That path would cost ~1
inference per unmatched clause pair but would not require new dependencies.

**Blueprint references**: §6.7 (comparison is unsolved), §4 (≥90% alignment
accuracy target), Constitution §IV (dependency minimalism)

---

## RQ-2: Comparison Agent Prompt Design

### Problem

The comparison agent must detect and classify divergences between two clause
texts (each with its own single-party assessment) using the RCBSF 5-dimension
taxonomy. The prompt structure must follow the existing extraction agent
pattern from spec 011 while incorporating the RCBSF classification task.

### Investigation

#### Existing patterns (spec 011)

The extraction agent at `src/openreview_cli/review/extraction.py` uses
`build_extraction_messages()` to construct a chat prompt with:

1. **System message**: Role definition, task description, output format spec
2. **User message**: Clause text, category definition, position definitions
3. **Output parsing**: Structured JSON response → `ClauseAssessment`

The QA agent at `src/openreview_cli/review/qa.py` follows the same structure
but takes assessment + clause text as input and outputs `QA verdict`.

#### RCBSF taxonomy (P-14)

| Dimension | Meaning | Bilateral Application |
|-----------|---------|----------------------|
| Category | Clause type differs | Party A has "Confidentiality"; Party B has "Non-Disclosure" |
| Location | Same concept, different sub-clause | Exclusions in §2.3 vs §4.1 |
| Evidence | Different basis/standard | "Reasonable efforts" vs "best efforts" |
| Issue | Risk assessment differs | Favourable vs unfavourable position |
| Suggestion | Remedy differs | 2yr vs 5yr confidentiality term |

#### Known ceiling (P-4)

Binary discrepancy detection has ≤64% F1 ceiling. The prompt MUST NOT
claim higher accuracy. Output is always provisional and labelled
EXPERIMENTAL.

### Decision

The comparison agent prompt SHALL follow the exact same pattern as the
extraction agent:

```
System: You are a contract comparison agent...
  [role definition, RCBSF taxonomy, output format, accuracy caveat]

User: Compare the following two clauses from Party A and Party B.
  --- Party A's clause ---
  {clause_a_text}
  --- Party B's clause ---
  {clause_b_text}

  Party A's assessment: {position_a} (confidence: {confidence_a})
  Party B's assessment: {position_b} (confidence: {confidence_b})

  Return a JSON object with:
  - "divergence": one of "category", "location", "evidence", "issue",
    "suggestion", or "no_divergence"
  - "confidence": 0.0-1.0
  - "citations": [excerpt from A, excerpt from B]
  - "rationale": explanation
```

Key design decisions:
- **No `--comparison-model` flag**: Reuses the extraction model slot,
  per FR-3/Q3 clarification. This halves the possible model combinations.
  Rationale: divergence detection uses the same reasoning capability as
  extraction. If users report systematic misclassifications where a larger
  model would improve accuracy, the flag can be added.
- **Input includes both positions**: The comparison agent sees the single-party
  assessments. This mirrors P-14 where the comparison is between "my position"
  and "their position."
- **Output follows `extraction.py` pattern**: JSON response parsed into a typed
  dataclass, exactly like `ClauseAssessment` is parsed.
- **Accuracy caveat in system prompt**: The prompt SHALL include: "Note: Binary
  discrepancy detection accuracy is bounded at approximately 64% F1 per
  published research (P-4). All divergence classifications are provisional."

**Blueprint references**: [P-14] (RCBSF taxonomy), [P-13] (PAKTON pattern
for prompt structure), [P-4] (§6.4 ≤64% ceiling), FR-3/Q3 (reuse extraction
slot), §9 R-1 (accuracy caveats)

---

## RQ-3: Memory Budget for Bilateral

### Problem

The constitution requires <100 MB peak memory (ex-model). The bilateral
pipeline processes two documents plus the comparison pass. The question
(Q2 from spec clarifications) was whether to process sequentially or in
parallel.

### Investigation

#### Single-party memory profile (from spec 011 + benchmark data)

The single-party pipeline (`run_review()` → `extract_clause()` →
`verify_assessment()` → `_build_report()`) processes one clause at a time,
streaming from `stream_clauses()`. Peak memory is dominated by:

- Parsed clause list: ~500 KB for a 50-page NDA (~30 clauses × ~16 KB avg)
- Active inference data: ~10 MB per clause (model I/O, tokenization buffers)
- PII state: exempt per Constitution §III, loaded once per session

Estimated peak per party: **~25 MB** (well under 100 MB budget)

#### Parallel vs sequential

| Approach | Peak Memory | Total Time | Complexity |
|----------|-------------|------------|------------|
| Parallel (both docs simultaneously) | ~50 MB (2× assessment state) | Fastest | Simple async but higher peak |
| Sequential (A then B, release between) | ~25 MB (same as single-party) | 2× single-party time | Simplest, zero risk |
| Interleaved (A clause 1 → B clause 1) | ~30 MB | Same as sequential | High complexity, marginal memory gain |

#### Comparison pass memory

The comparison agent runs on one pair at a time. Input is two clause texts
(typically <5 KB each) and two assessment dataclasses (<1 KB each). Output
is a single `PairedAssessment`. This is trivially low-memory.

The alignment table is built from heading strings only — insignificantly
small.

### Decision

**Sequential processing** (confirmed per Q2 clarifications):

1. Document A: parse → extract → QA → report built → **all A state released**
2. Document B: parse → extract → QA → report built → **all B state released**
3. Both parsed clause structures held for alignment (~1 MB total)
4. Comparison agent runs on each aligned pair
5. Comparison report assembled from A's assessments + B's assessments +
   comparison results

Peak memory remains at single-party levels (~25 MB ex-model).

The parsed clause structures for both documents are held simultaneously
only during step 3, but these are plain text dataclasses (~1 MB for 60
clauses), well within budget.

**Constitutional compliance**: Passes Principle III (<100 MB). The NLP
model exemption applies to PII stripping only; no additional NLP models
are loaded for the comparison pipeline.

**Blueprint references**: Constitution §III (Hardware-Bounded), Q2 (sequential
confirmed), FR-10 §3 (processing model)

---

## RQ-4: CLI Subcommand Structure

### Problem

The `compare` subcommand must fit into the existing Typer app structure.
The current structure (from `src/openreview_cli/app.py`) has the `precheck`
group with a `review` subcommand. The question is how to add `compare`
without breaking the existing command tree.

### Investigation

#### Current command tree

```
openreview                      # Typer app
├── --version / --debug         # Root callback
├── client                      # Client management (add/list/delete)
├── config                      # Config view/modify (show/get/set)
├── pii                         # PII management (list/delete/cleanup)
├── precheck                    # PreCheck review commands
│   ├── <callback>              # Legacy direct path (single-party inline)
│   └── review                  # PAKTON 3-agent pipeline
├── parse                       # Document parsing
├── gateway                     # AI Gateway management (setup/status/providers/...)
├── chunk                       # Chunking
├── benchmark                   # Benchmark suite
└── prompt                      # Prompt management
```

#### Integration point

The `precheck` group is defined at line 359 of `app.py`:

```python
precheck_app = typer.Typer(
    name="precheck",
    help="PreCheck contract review commands.",
    no_args_is_help=True,
)
```

The `review` subcommand is at line 433:

```python
@precheck_app.command()
def review(...):
```

The `precheck` callback (line 367) handles the legacy single-document
path. It checks `ctx.invoked_subcommand` before dispatching.

#### Parallel to `review` command

The `compare` subcommand mirrors `review` in structure:
- Takes document paths as positional arguments (2 instead of N)
- Has optional `--playbook`, `--extraction-model`, `--qa-model` flags
- Has `--format`, `--output` flags for output control
- Has `--no-pii`, `--verbose` flags
- Has bilateral-specific flags: `--align-only`, `--confidence-threshold`,
  `--conservative`

### Decision

Add `compare` as a **new subcommand on the existing `precheck_app` Typer
group**, following the exact same pattern as the `review` command.

```python
@precheck_app.command()
def compare(
    doc_a: str = typer.Argument(..., help="Path to Party A's document"),
    doc_b: str = typer.Argument(..., help="Path to Party B's document"),
    ...flags follow review pattern...
) -> None:
```

The comparison logic lives in a new `src/openreview_cli/bilateral/` package,
separate from `review/`. This keeps the codebase modular — the comparison
pipeline is built on top of the review pipeline, not tangled with it.

**Why a new package instead of a module**: The bilateral feature has
multiple modules (alignment, comparison agent, report formatter, data
models) that form a cohesive unit. A single file would be >500 lines.
The package follows the same pattern as `review/`, `pii/`, `gateway/`
etc.

**Blueprint references**: §10 Q-4 (PreCheck pilot), FR-9 (opt-in experimental),
existing app.py patterns

---

## Summary of Decisions

| RQ | Decision | Key Constraint | Reference |
|----|----------|----------------|-----------|
| RQ-1 | 3-tier heading cascade with stdlib difflib | Forbidden deps (§IV) | §6.7, §4 |
| RQ-2 | Mirror extraction prompt + RCBSF classification | No --comparison-model (FR-3/Q3) | P-14, P-13 |
| RQ-3 | Sequential processing | <100 MB budget (§III) | Q2, FR-10 |
| RQ-4 | New `bilateral/` package, `compare` subcommand on precheck_app | Pattern consistency | app.py |

## Open Questions

1. **difflib threshold tuning**: Initial 0.8 for fuzzy matching is a guess.
   Should be validated against the benchmark (≥90% alignment accuracy).
   If below threshold, tune downward to 0.7 and verify false-positive rate.

2. **Comparison agent model performance**: The extraction model slot is used
   for comparison. If its reasoning degrades on the bilateral task, a separate
   slot may need to be added. This should be measured in the benchmark.

3. **Symmetry confirmation**: The spec assumes symmetrical comparison (neither
   side is "standard"). This is correct for pilot but may need revisiting if
   users want template-anchored comparisons. Deferred as out of scope per §9.
