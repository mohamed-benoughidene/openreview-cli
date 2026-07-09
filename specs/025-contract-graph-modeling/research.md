# Contract Graph Modeling — Research and Design Decisions

**Spec**: `specs/025-contract-graph-modeling/spec.md`
**Created**: 2026-07-06
**Status**: Resolved

---

## Resolved Decisions

### 0. Use Existing `Clause.parent_id` Instead of Adding a `numbering` Field

**Decision**: Use the existing `Clause.parent_id` field (already populated by `clause_detector.build_hierarchy()`) for hierarchy edge construction. Do not add a separate `numbering` field to the `Clause` model.

**Rationale**:
- The `Clause` model already has `parent_id` populated during parsing. Adding a `numbering` field would duplicate information already derivable from the clause hierarchy.
- GraphNode IDs are derived from text-extracted section numbering (regex on clause text), not from `Clause.id` or a separate numbering field. This keeps the graph builder independent of the parsing module's internal ID scheme.
- Using `parent_id` directly simplifies the hierarchy builder: it's a direct pointer rather than needing to infer parentage by sorting and comparing numbering strings.
- The parsing engine is the authoritative source of hierarchy; the graph builder should consume it, not re-derive it.

**Risk**: Very low. `parent_id` is already present and populated. The graph builder becomes simpler (no numbering parsing logic) and more robust (no numbering-format assumptions).

### 1. Why Heuristic Metrics over GRPO / ML

**Decision**: Use heuristic rule-based metrics exclusively. No ML training, no GRPO, no GPU.

**Rationale**:
- The P-8 paper [1] demonstrates that GRPO achieves 72.3% F1 on CUAD clause classification using 43 annotated contracts. While impressive, this approach requires:
  - 43+ annotated contracts (labelled training data)
  - GPU hours for training
  - Ongoing model maintenance and re-training
  - Runtime ML inference pipeline with model loading overhead (~600-800 MB for spaCy alone)
- The spec's five heuristic metrics (density, max depth, orphan ratio, broken cross-refs, definition coverage) can be computed from the graph alone using arithmetic and graph traversal — no training data, no GPU, no model loading.
- Research finding: **no published contract health score benchmark exists** (see Section 5 below). Without a ground-truth dataset, supervised ML cannot be validated. Heuristic metrics provide a meaningful baseline that is interpretable, auditable, and deterministic.
- Hardware constraint: target machine is 8 GB RAM, no GPU. Adding an ML pipeline would blow the 100 MB memory budget (the spaCy model alone is 600-800 MB).
- Heuristic metrics have the advantage of being fully explainable: each metric maps directly to a structural property that a lawyer or contract manager can verify.

**Risk**: Heuristic metrics may not capture semantic quality (e.g., poorly worded but structurally well-formed clauses). This is an accepted limitation documented in the spec. Future specs may add semantic metrics via the AI Gateway.

**References**:
- [1] P-8 paper: "GRPO for Contract Understanding" — demonstrates GRPO on 43 CUAD contracts, achieving 72.3% F1 on clause classification. The paper's key finding is that GRPO reduces annotation cost but still requires labelled data and GPU compute. Neither is available for this phase.
- [2] CUAD (Contract Understanding Atticus Dataset): 510+ annotated contract clause types. Used as the benchmark in P-8. Our heuristic approach does not attempt clause classification, only structural graph properties.

---

### 2. Why Stdlib Graph over NetworkX

**Decision**: Use plain Python stdlib data structures (`dict`, `list`, `dataclasses`) for the graph. No NetworkX or other external graph library.

**Rationale**:
- The spec's maximum graph size is 5000 nodes, 20000 edges. This fits easily in memory with stdlib structures (~5-10 MB).
- Operations needed are simple: adjacency list traversal (DFS/BFS), edge counting, node iteration. No need for NetworkX's advanced algorithms (eigenvector centrality, community detection, etc.).
- NetworkX is not currently a project dependency. Adding it would conflict with the "no new deps" constraint and add ~12 MB to the venv.
- Stdlib `dict` adjacency list is sufficient for:
  - Density: `len(edges) / (n * (n-1))`
  - Max depth: DFS recursion with visited set
  - Orphan detection: inbound-edge check
  - Broken cross-ref: target-in-nodes check
- JSON serialisation is trivial: `nodes` list + `edges` list.

**Trade-off**: No advanced graph algorithms available. Not a concern — the spec explicitly requires only heuristic metrics.

---

### 3. Why Regex over spaCy for Cross-Reference Detection

**Decision**: Use regex-based detectors with configurable pattern lists. No spaCy, no NLP pipeline.

**Rationale**:
- Legal cross-references in English follow a small set of predictable patterns: "Section X.Y", "as defined in Section X.Y", "pursuant to Section X.Y". These are amenable to regex.
- spaCy's dependency parsing could detect more complex references ("the provisions of Section 3.2 shall apply"), but:
  - spaCy is a **forbidden dependency** for PII processing (per the spec's forbidden list).
  - The spaCy model is 600-800 MB, exceeding the memory budget.
  - spaCy loading adds 2-5 seconds cold-start time.
- The regex approach is deterministic, testable, and ~1000x faster than NLP.
- The pattern list is extensible — users can add patterns for domain-specific phrasing.

**Risk**: Some cross-references will be missed (false negatives). Examples: "as per clause 3.2", "under section 7.1", "per the terms of Section 5". These can be addressed by expanding the default pattern list. The initial patterns cover the most common phrasing observed in 54-sample contract corpus from Phase 3.

---

### 4. Graph Storage: JSON Default, SQLite Optional (D-59)

**Decision**: JSON files remain the default for graph persistence (portable, human-readable, zero migration cost). SQLite storage is available as an opt-in via `--store` flag on `graph build`, for users who need cross-contract queries, versioning, or integration with the existing SQLite layer (PII mapping, playbook versioning, gateway cost tracking).

**Rationale**:
- **JSON default unchanged**: Graphs are still serialised to JSON by default — portable, human-readable, no schema migrations, cheap to regenerate (<1s for 500 nodes).
- **SQLite as opt-in**: New tables `graph_meta` (contract-level metadata), `graph_nodes` (per-row + position + metadata_json), `graph_edges` (per-row + type) added in migration 008. Enables cross-contract queries and versioned storage.
- **Use cases**: SQLite storage is for users who build many graphs and want to query across them, or want versioned graph history. JSON files remain for one-off graph inspection and external tool consumption.
- **Trade-off**: Two storage backends. The default JSON path is unchanged; SQLite adds complexity (schema migration, query interface) only for users who opt in.

**Migration**: Migration `008_graph_tables.sql` uses `CREATE TABLE IF NOT EXISTS` — fully additive, no existing schema changes.

---

### 5. No Published Contract Health Score Benchmark

**Research finding**: A thorough search of legal AI literature (P-8, CUAD, Legal-BERT, CaseHOLD, LexGLUE) found no published benchmark or standard for a single "contract health score." Existing work focuses on:
- Clause classification (CUAD, P-8)
- Legal judgment prediction (CaseHOLD, LexGLUE)
- Text summarisation (Legal-BERT)
- Contract element extraction (LinkSoul, Atticus)

**Implications**:
- The health score formula and default weights in this spec are novel heuristic proposals. They cannot be calibrated against external ground truth.
- Validation must rely on: (a) sanity checks (perfect graph → score 100, pathological graph → score 0), (b) user feedback, (c) internal consistency testing.
- The formula is intentionally simple (weighted linear combination) and fully customisable via `--weights`. This allows users to adjust for their domain.
- A formal validation study would require a labelled dataset of contracts with expert-assigned quality scores. This is out of scope for v1.

**Future work**: If a benchmark dataset emerges, the health score formula can be calibrated via linear regression against expert scores. The architecture supports plugging in different formulae.

---

### 6. Cross-Jurisdiction Validation Gap

**Research finding**: Contract drafting conventions vary significantly across jurisdictions:
- **US**: Detailed cross-references ("as defined in Section 3.2(b)"), numbered sections, defined terms in quotation marks
- **UK/EU**: More narrative style, fewer explicit cross-references, definitions in separate schedules
- **Civil law** (France, Germany): Article numbering, more hierarchical, fewer explicit definitions in the text body

**Decision**: v1 targets English-language contracts following US convention (most common in the training corpus of 54 documents). The regex patterns are designed for this convention.

**Mitigation**:
- Documentation states this limitation explicitly
- Pattern lists are extensible — a UK variant can be added by providing alternative regex patterns
- The ClauseHierarchyBuilder uses `Clause.parent_id` for hierarchy, so it is independent of numbering format
- Cross-jurisdiction support is deferred; a future spec may add jurisdiction-specific detector profiles

---

### 7. Why TDD with Separate Test Files per Module

**Decision**: Each graph module gets a dedicated unit test file (`test_graph_models.py`, `test_graph_builder.py`, etc.). Integration test in a single file.

**Rationale**:
- Matches existing project convention (test files mirror `src/` structure)
- Ensures each module is testable in isolation
- TDD workflow: write failing test → write minimal code to pass → refactor
- Integration test validates end-to-end flow (parse → build → metrics → health → view)

---

## References

| # | Reference | Used For |
|---|-----------|----------|
| [1] | P-8: "GRPO for Contract Understanding" (2025) — GRPO on 43 CUAD contracts, 72.3% F1 | Decision 1 (heuristics over GRPO) |
| [2] | CUAD Dataset (510+ clause types, Hendrycks et al., 2021) | Decision 1, Section 5 |
| [3] | CaseHOLD (Zheng et al., 2021) — legal holding identification | Section 5 (no health score benchmark) |
| [4] | LexGLUE (Chalkidis et al., 2022) — legal NLP benchmark suite | Section 5 (no health score benchmark) |
| [5] | Legal-BERT (Chalkidis et al., 2020) — legal domain language model | Section 5 (no health score benchmark) |
| [6] | 54-contract corpus from Phase 3 PII benchmarking | Decision 3 (regex pattern coverage validation) |
| [7] | Python stdlib `re` module documentation | Decision 3 (regex approach) |
| [8] | NetworkX documentation — graph algorithms | Decision 2 (rejected in favour of stdlib) |
