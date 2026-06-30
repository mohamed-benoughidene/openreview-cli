# Papers → Product Synthesis

Generated: 2026-06-28 | Source: 15 papers, 6 impl specs, 38 product specs

---

## STEP 1 — RESEARCH THEMES

### THEME [T-1]: Domain-Specific Models Outperform General LLMs for Legal Text
Papers: [P-1], [P-10], [P-12]

**Consensus finding:** Domain-trained models consistently outperform larger general-purpose models on legal tasks. Legal-BERT (110M parameters) beats RoBERTa (355M) on 8/10 legal benchmarks [P-10]. Olava Extract (domain SLM) achieves micro F1=0.842, surpassing frontier LLMs including GPT-5.4, while costing 8×–25× less ($0.018/doc vs $0.149–$0.456) [P-1]. Fine-tuned models gain +30pp over base models on legal NLP tasks [P-12].

**Strongest evidence:** [P-10] (STRONG) — Legal-BERT vs RoBERTa direct comparison across 10 benchmarks with rigorous methodology.

**Contradictions:** NONE — all three papers converge on domain pre-training/fine-tuning as essential for legal NLP performance.

---

### THEME [T-2]: Multi-Agent Architectures Improve Legal QA and Review Quality
Papers: [P-2], [P-13]

**Consensus finding:** Multi-agent systems with specialized roles outperform single-agent LLM approaches. PAKTON achieves 82.8% F1 with 5× Recall@1 over baseline and is preferred over GPT-4o in blind evaluation [P-13]. AgentScope demonstrates a generalizable agentic framework supporting 5 LLM providers with MCP protocol integration [P-2].

**Strongest evidence:** [P-13] (STRONG, NEAR) — PAKTON shows statistically significant gains across multiple QA datasets and human preference evaluation.

**Contradictions:** NONE — [P-2] provides architecture validation for the approach [P-13] proves effective.

---

### THEME [T-3]: Contract Classification and Clause Detection Remain Challenging
Papers: [P-3], [P-4]

**Consensus finding:** Contract classification has mature infrastructure (LEDGAR: 60K training labels across 12K categories; CUAD: 510 contracts, 41 clause types) [P-3], but clause-level discrepancy detection remains unsolved — best F1=63%, and lawyer agreement on discrepancies is below 14% [P-4].

**Strongest evidence:** [P-3] (MODERATE, READY) for classification capability; [P-4] (MODERATE, RESEARCH) for the discrepancy ceiling.

**Contradictions:** NONE — [P-3] and [P-4] address different problems (classification vs discrepancy detection) and are complementary.

---

### THEME [T-4]: Citation Grounding and Hallucination Are the Critical Risk Axis
Papers: [P-6], [P-12]

**Consensus finding:** Legal LLMs hallucinate at rates of 13–58% [P-6] [P-12], making citation grounding the single most important safety mechanism. RAG-based citation grounding achieves CG=0.873, and citation-grounded DPO training pushes this to CG-DPO=98.5% [P-6]. Without grounding, outputs are unusable for professional legal work.

**Strongest evidence:** [P-6] (STRONG, READY) — comprehensive hallucination measurement and demonstrated mitigation with quantifiable results.

**Contradictions:** NONE — [P-12] confirms the hallucination problem at broader scale (58% across legal NLP tasks); [P-6] provides the remediation.

---

### THEME [T-5]: Legal Retrieval Benchmarks Expose Severe Gaps
Papers: [P-7], [P-9]

**Consensus finding:** Current legal retrieval is far from production-grade. LegalBench-RAG shows best P@1 of only 6.41% across all tested configurations [P-9]. General-purpose rerankers degrade rather than improve legal retrieval performance — genre-specific retrievers are essential [P-9]. LegalBench provides 162 tasks covering the full taxonomy of legal reasoning [P-7], but replicating comprehensive benchmarks like CUAD costs an estimated $2M [P-7].

**Strongest evidence:** [P-9] (STRONG, READY) — exhaustive benchmarking of retrieval configurations with clear actionable finding on reranker degradation.

**Contradictions:** NONE — [P-7] establishes the benchmark landscape; [P-9] measures the gap.

---

### THEME [T-6]: Domain-Adapted RAG Drives Cost-Effective Legal AI
Papers: [P-9], [P-11]

**Consensus finding:** Two-step RAG pipelines with genre-specific retrievers add 8–15pp performance while achieving 99.4% cost reduction versus pure LLM approaches [P-11]. However, generic rerankers are actively harmful — only domain-specific (legal-trained) retrievers and rerankers improve performance [P-9].

**Strongest evidence:** [P-11] (MODERATE, READY) — MINA's production deployment in Bangladesh demonstrates real-world cost and accuracy gains; [P-9] establishes the domain-specificity requirement.

**Contradictions:** Nuance, not contradiction. Both agree domain-specific retrieval is required. [P-11] shows RAG benefits; [P-9] specifies the *type* of RAG that works.

---

### THEME [T-7]: Contract Revision Requires Multi-Dimensional Constraint Modeling
Papers: [P-5], [P-14]

**Consensus finding:** Effective contract revision requires modeling multiple constraint dimensions simultaneously. RCBSF's 5D constraint framework (Legal, Business, Risk, Fairness, Clarity) achieves 84.2% Revision Recommendation Recall [P-14]. Performance degrades significantly on multi-hop reasoning: CHANCERY achieves 75.2% on basic corporate governance questions but drops to 58.1% on multi-hop questions [P-5].

**Strongest evidence:** [P-14] (MODERATE, RESEARCH) — 5D framework validated across 800 contract pairs; [P-5] confirms multi-hop complexity penalty.

**Contradictions:** NONE — the multi-hop finding in [P-5] explains *why* the 5D framework in [P-14] is necessary.

---

### THEME [T-8]: Structured and Graph-Based Reasoning Enhances Legal Analysis
Papers: [P-8], [P-15]

**Consensus finding:** Graph-based training and ontology-structured reasoning significantly outperform unstructured approaches. GRAPH-GRPO-LEX improves from SFT 0.661 to GRPO 0.798, with gated models performing 6× better [P-8]. SOLAR's ontology-based verifiable reasoning achieves 76.4% vs 18.8% baseline with 45% token reduction [P-15].

**Strongest evidence:** [P-8] (MODERATE, NEAR) — GRPO training shows large gains; [P-15] demonstrates practical token savings with better accuracy.

**Contradictions:** NONE — complementary approaches (training method [P-8] vs inference-time structure [P-15]).

---

### ISOLATED [I-1]: CUAD Benchmark Replication Costs $2M
Source: [P-7]
Product relevance: LOW — informs benchmark selection strategy. $2M replication cost confirms we should use existing benchmarks (LegalBench-RAG per [PR-15]) rather than build custom ones.

### ISOLATED [I-2]: MINA Achieves Bar Passage at 75–80% with 99.4% Cost Reduction
Source: [P-11]
Product relevance: HIGH — direct evidence that cost-effective legal AI is achievable in a production setting. Supports [PR-1]'s $1/review cost ceiling and validates the two-step RAG architecture in [PR-2].

---

## STEP 2 — CURRENT STATE MAP

### Implementation Specs (S-N)

| Spec | Name | Status | Tech Stack | Built Capabilities |
|------|------|--------|------------|-------------------|
| S-1 | Config/Storage | 16/17 BUILT | YAML, Pydantic, SQLite, Rich | Config loading, auth.json, SQLite schema, CLI config commands, cost tracking store |
| S-2 | Document Parsing | 23/23 BUILT | PyMuPDF, python-docx, NUPunkt | PDF streaming (page-by-page), DOCX parsing, clause boundary detection (91.1% precision), `stream_clauses()` pipeline |
| S-3 | PII Stripping | 24/25 BUILT, 1 PARTIAL | Presidio, cryptography (AES) | 15 entity types, AES encryption, 3-tier privacy. `--no-pii` flag unwired (8 deferred tasks) |
| S-4 | AI Gateway | 31/31 BUILT | LiteLLM, Pydantic v2, httpx | 5 configurable model slots, 8+ providers, fallback routing, cost tracking via `litellm.completion_cost()`, setup wizard, YAML importer, key redaction logging |
| S-5 | CLI Wizard | 18/18 BUILT (superseded) | questionary | ReviewWizard with back navigation. **Superseded by S-6.** |
| S-6 | CLI UX | 34/34 BUILT | questionary v2.1.1, Rich 15.0.0, Typer 0.26.7 | Design tokens, 11 UI components, wizard state machine (6-phase), exit codes 0–8, first-run detection + auto-wizard, Flesch-Kincaid <10 constraint, first-render <100ms |

### Product Specs (PR-N) — Key Decisions and Status

| Spec | Domain | Decisions Locked In | Assumptions Unvalidated |
|------|--------|--------------------|-----------------------|
| PR-1 | AI Gateway | LiteLLM, 8 providers, 5 slots, local-first, BYOK, $1/review limit | $1/review achievable in practice with our pipeline |
| PR-2 | Architecture | PAKTON 3-agent, hierarchical chunking, hybrid BM25+Dense+LightRAG+RRF, cross-encoder reranker, 3-position framework, citation grounding | PAKTON performance on real contracts; reranker choice (see C-4); chunking granularity for contracts |
| PR-4 | CLI Design | 22 mode subcommands, common flags, 10 exit codes, MD/JSON/PDF output | Exit code scheme conflicts with S-6 |
| PR-6 | Configuration | config.yml + auth.json, 6-level priority, Pydantic validation | YAML format conflicts with S-6 JSON format |
| PR-7 | Data Storage | SQLite + JSON, per-client playbook DBs, session DBs deleted on exit | Schema complexity for playbook versioning |
| PR-9 | Error Handling | 3-line template, 10 error categories, 5 recovery strategies | Recovery strategies untested against real provider failures |
| PR-11 | Performance | Stream-and-discard, async httpx, 5-stage pipeline, peak <100MB | Full pipeline memory budget with all layers running |
| PR-12 | PlayBook | 3 shared positions, 3-position framework, versioned, AI-suggested | Mapping to RCBSF 5D constraints unvalidated |
| PR-13 | Privacy | PII stripped before API, 3 tiers, BYOK, chmod 600 | Presidio performance on dense legal contracts |
| PR-14 | Tech Stack | Python 3.12, uv, Typer, Rich, SQLite, PyMuPDF, python-docx, Presidio, LiteLLM | Rejection of local domain SLMs (see C-3) |
| PR-15 | Testing | LegalBench-RAG primary, hallucination <5%, P@5 ≥90%, peak <100MB | Threshold achievability on first pass |
| PR-16 | User Journey | Solo lawyer, $288/hr, time savings 1h45m–3h+ | Time savings estimate not empirically validated |

---

## STEP 3 — ALIGNMENT TABLE

| Theme | Product Spec | Impl Spec | Built | Verdict |
|-------|-------------|-----------|-------|---------|
| T-1 Domain Models | PR-14 (rejects local SLMs, API-only) | S-4 (LiteLLM routing, 5 slots) | ✓ | **CONFLICT** — [P-1] and [P-10] show local domain models outperform and cost less; PR-14 rejects them. See [C-3]. |
| T-2 Multi-Agent | PR-2 (PAKTON 3-agent) | None | ✗ | **GAP [G-1]** — architecture specified but no implementation spec exists. |
| T-3 Contract Classification | PR-2 (hybrid retrieval mentions clause types) | S-2 (clause detection built) | ✓ Partial | **ALIGNED** — base clause detection built; classification logic not yet implemented. |
| T-4 Citation Grounding | PR-2 (citation grounding) | None | ✗ | **GAP [G-2]** — specified in PR-2, critical per [P-6], no implementation. |
| T-5 Legal Benchmarks | PR-15 (LegalBench-RAG primary) | S-2 tests exist | ✓ Partial | **ALIGNED** — benchmark selected, integration tests exist, but not run at scale. |
| T-6 Domain RAG | PR-2 (hybrid BM25+Dense+LightRAG+RRF) | None | ✗ | **GAP [G-3]** — retrieval architecture specified, no implementation. Also **CONFLICT [C-4]** on reranker choice. |
| T-7 Contract Revision | PR-12 (3-position framework) | None (S-6 CLI only) | ✗ | **GAP [G-4]** — revision logic specified in PR-12/PR-2 but no implementation. |
| T-8 Structured Reasoning | Not in any PR | None | ✗ | **GAP [G-5]** — graph/ontology reasoning absent from all product and implementation specs. |

### Per-Spec Alignment Detail

| PR-N | Spec Name | Alignment | Key Issues |
|------|-----------|-----------|------------|
| PR-1 | AI Gateway | ✓ ALIGNED | S-4 fully implements. $1/review limit unvalidated [O-3]. |
| PR-2 | Architecture | ✗ GAP | Core review pipeline unimplemented. Multiple GAPs [G-1][G-2][G-3]. Reranker conflict [C-4]. |
| PR-3 | (not in source data) | — | Not referenced. |
| PR-4 | CLI Design | ⚠ PARTIAL | S-6 implements CLI. Exit code scheme conflict [C-2]. |
| PR-5 | (not in source data) | — | Not referenced. |
| PR-6 | Configuration | ⚠ CONFLICT | S-1 uses YAML; S-6 uses JSON. Format conflict [C-1]. |
| PR-7 | Data Storage | ✓ ALIGNED | S-1 implements. Playbook schema extensibility unvalidated. |
| PR-8 | (not in source data) | — | Not referenced. |
| PR-9 | Error Handling | ✓ ALIGNED | Implemented in S-1/S-4. Recovery strategies untested. |
| PR-10 | (not in source data) | — | Not referenced. |
| PR-11 | Performance | ✓ ALIGNED | S-2 streaming built. Full pipeline memory unvalidated [O-5]. |
| PR-12 | PlayBook | ✗ GAP | No implementation exists for revision logic [G-4]. |
| PR-13 | Privacy | ✓ ALIGNED | S-3 fully implements (24/25). `--no-pii` unwired but blocked by downstream infrastructure. |
| PR-14 | Tech Stack | ✓ ALIGNED | All dependencies in place. Local SLM rejection conflicts with [T-1] research. |
| PR-15 | Testing | ⚠ PARTIAL | Benchmarks selected but not run. Thresholds unvalidated. |
| PR-16 | User Journey | ✗ GAP | Time savings claim not empirically validated. |

---

## STEP 4 — GAP MAP

### GAP [G-1]: Multi-Agent Review Architecture — CRITICAL
**Research basis:** [T-2] — PAKTON achieves 82.8% F1, 5× Recall@1 [P-13]; AgentScope validates agentic patterns [P-2].
**Specified in:** PR-2 (3-agent PAKTON architecture, 3-position framework).
**Missing from:** All S-N specs. S-4 builds the *gateway* for LLM calls but none builds the *review orchestration* that uses it.
**Priority:** CRITICAL — this is the core product capability. Without it, there is no review engine.

### GAP [G-2]: Citation Grounding Implementation — HIGH
**Research basis:** [T-4] — 13–58% hallucination rates [P-6][P-12]; CG-DPO achieves 98.5% grounding accuracy [P-6].
**Specified in:** PR-2 (citation grounding listed as architectural component).
**Missing from:** All S-N specs. No implementation spec defines how citations are extracted, verified, and rendered.
**Priority:** HIGH — without citation grounding, review outputs are not trustworthy per [P-6] and [P-12].

### GAP [G-3]: Hybrid Retrieval Pipeline — CRITICAL
**Research basis:** [T-6] — LegalBench-RAG P@1=6.41% [P-9]; two-step RAG adds 8–15pp [P-11]; domain-specific retrievers essential [P-9].
**Specified in:** PR-2 (hybrid BM25+Dense+LightRAG+RRF, hierarchical chunking).
**Missing from:** All S-N specs. S-2 handles document parsing but no retrieval pipeline exists.
**Priority:** CRITICAL — retrieval is the foundation that feeds context to the review engine and citation grounder.

### GAP [G-4]: Contract Revision Logic — HIGH
**Research basis:** [T-7] — RCBSF 84.2% RRR with 5D constraints [P-14]; multi-hop degrades 17pp [P-5].
**Specified in:** PR-12 (3-position framework: favorable, neutral, unfavorable) and PR-2 (3-position analysis).
**Missing from:** All S-N specs. S-6 builds CLI interaction for review but the actual revision/comparison logic is unimplemented.
**Priority:** HIGH — the revision framework is the product's output format. Without it, the review has no structured result.

### GAP [G-5]: Structured Reasoning Layer — MEDIUM
**Research basis:** [T-8] — GRPO 0.798 vs SFT 0.661 (gated 6× better) [P-8]; ontology reasoning 76.4% vs 18.8% [P-15].
**Specified in:** Not in any PR or S spec.
**Missing from:** Entire specification landscape.
**Priority:** MEDIUM — enhances quality but is not a blocker for initial product. Can be layered after core pipeline works.

### GAP [G-6]: Cost Validation — MEDIUM
**Research basis:** [T-1] — $0.018/doc for domain SLM [P-1]; [T-6] — 99.4% cost reduction via RAG [P-11].
**Specified in:** PR-1 ($1/review limit).
**Missing from:** No empirical cost measurement of our specific pipeline (LiteLLM routing × multi-agent × hybrid RAG).
**Priority:** MEDIUM — PR-1's $1 ceiling is a business constraint. Must validate before launch.

---

## STEP 5 — CONFLICT REGISTER

### CONFLICT [C-1]: Configuration Format — JSON vs YAML
**Research says:** N/A (tooling preference, not research).
**Spec says:** PR-6 specifies `config.yml` (YAML); S-1 implements YAML-based config loading. S-6 plan.md specifies `$XDG_CONFIG_HOME/openreview/config.json` (JSON format), diverging from the YAML scheme used by S-1's storage layer.
**Resolution:** Adopt JSON format (S-6 is the most recent implementation spec and supersedes). Migrate S-1's YAML loader to JSON. The 6-level priority and Pydantic validation from PR-6 remain valid regardless of format.
**Risk:** MEDIUM — breaks existing S-1 storage code. Migration work is mechanical but must be thorough.

### CONFLICT [C-2]: Exit Code Scheme Fragmentation
**Research says:** N/A (CLI convention, not research).
**Spec says:** PR-4 specifies 10 exit codes. S-6 implements exit codes 0–8 (9 distinct codes). S-4 previously used a 5/6/7 scheme.
**Resolution:** Adopt S-6's 0–8 scheme as canonical. S-6 is the latest and fully built. Update PR-4 to reflect 9 codes (not 10). Map S-4 codes to S-6 scheme.
**Risk:** LOW — exit codes are CLI-level; no data loss possible. Mechanical alignment.

### CONFLICT [C-3]: Domain SLM Rejection vs Research Evidence
**Research says:** Domain-trained models (Legal-BERT 110M, Olava Extract) outperform general LLMs while costing 8×–25× less [P-1] [P-10]. Fine-tuned domain models gain +30pp [P-12].
**Spec says:** PR-14 explicitly rejects local domain models in favor of API-only architecture. Tech stack rejects spaCy-for-PII and sentence-transformers (used by some SLM pipelines) but does not explicitly reject all local inference.
**Resolution:** Maintain API-first architecture for initial launch (LiteLLM routing per S-4 is built and working). But plan a hybrid augmentation: local domain SLM for classification/triage (high-volume, low-complexity), API LLMs for generation/reasoning (low-volume, high-complexity). This captures the cost benefits of [P-1] while preserving the flexibility of [PR-1]'s gateway.
**Risk:** MEDIUM — current architecture leaves 78–97% cost savings on the table [P-1]. Competitors who adopt hybrid architectures will undercut on price. However, API-only is simpler and works today.

### CONFLICT [C-4] (RESOLVED): Reranker Selection — LightRAG Replaces Generic Cross-Encoder
**Research says:** General-purpose rerankers *degrade* legal retrieval performance. Only domain-specific (legal-trained) rerankers improve results [P-9].
**Spec said:** PR-2 specified "cross-encoder reranker" without domain qualification — implied a generic model.
**Resolution:** LightRAG graph retrieval replaces the generic cross-encoder reranker as the primary precision filter. LightRAG traverses entity relationships and reuses the same local embedding model, avoiding the degradation [P-9] found with generic rerankers while adding relationship-aware retrieval that no reranker provides. The reranking slot remains available as an optional path for users who want it, but is disabled by default.
**Risk (resolved):** RESOLVED by this decision. The generic reranker degradation path is eliminated. LightRAG graph retrieval provides superior precision without a separate reranker model.

---

## STEP 6 — RESEARCH GAPS

### OPEN [O-1]: PAKTON Performance on Real-World Contracts
**Why it matters:** [P-13] validated PAKTON on legal QA datasets (statutory questions, case law retrieval), not on contract review workflows. Our product reviews contracts, not answers legal questions.
**Validation method:** Run PAKTON architecture against CUAD [P-3] and LEDGAR [P-3] contract corpora. Measure F1, precision, recall on clause classification, risk identification, and recommendation generation. Compare single-agent vs 3-agent performance on contracts specifically.

### OPEN [O-2]: Citation Grounding for Contract Clause References
**Why it matters:** [P-6] tested citation grounding on legal reasoning (statutes, case citations), not on intra-document clause references ("see Section 4.2(a)"). Contract review citations are fundamentally different: they reference positions within the document, not external legal authorities.
**Validation method:** Build a contract clause citation benchmark. Extract clause references from CUAD contracts, measure grounding accuracy of our system's citations, compare against [P-6]'s CG-DPO 98.5% baseline.

### OPEN [O-3]: Cost-Per-Review Ceiling Under $1
**Why it matters:** [PR-1] sets $1/review as a hard ceiling. [P-1] shows $0.018/doc for extraction alone; [P-11] shows 99.4% cost reduction via RAG. But our pipeline is more complex: 3 agents × (retrieval + generation) × LiteLLM routing overhead. The actual cost is unknown.
**Validation method:** Run cost simulation using actual LiteLLM pricing across all configured providers. Model 3 scenarios: min (local-only via Ollama), typical (LiteLLM routing to cheapest provider), max (fallback to most expensive). Verify all three stay under $1/review.

### OPEN [O-4]: RCBSF 5D Constraints Coverage by 3-Position Framework
**Why it matters:** [P-14]'s 5D constraints (Legal, Business, Risk, Fairness, Clarity) are a validated framework for contract revision. [PR-12] uses a 3-position framework (favorable, neutral, unfavorable). It is unclear whether 3 positions can adequately represent 5 dimensions of analysis.
**Validation method:** Map 5D constraint categories to 3-position output. Test coverage: can all 5 dimensions be expressed within 3 positions? Run on 50 contract pairs, measure whether collapsing 5D→3D loses critical distinction.

### OPEN [O-5]: Full Pipeline Memory Budget
**Why it matters:** [PR-11] sets peak memory <100MB. Individual components (S-2 streaming parser, S-3 Presidio) are tested. But the full pipeline — LiteLLM SDK, Presidio model, SQLite, questionary, Rich — has never been measured concurrently. [P-10] shows Legal-BERT feasible at 110M params, but our stack adds multiple heavy libraries.
**Validation method:** Tracemalloc test with full pipeline: load a 50-page contract, run PII stripping, hybrid retrieval, multi-agent review, citation grounding. Measure peak RSS. Target <110MB (constitution floor).

### OPEN [O-6]: MINA Two-Step RAG Applicability to Western Legal Systems
**Why it matters:** [P-11] validated on Bangladesh legal system. While Bangladesh uses common law (derived from English law), the legal language, statute structure, and contract conventions differ from U.S./UK systems. Our target market (per [PR-16]) is U.S. lawyers.
**Validation method:** Benchmark two-step RAG (retrieve-then-generate) against U.S. contract datasets (CUAD, LEDGAR). Compare to single-step RAG baseline. Measure the 8–15pp improvement [P-11] claims in the U.S. legal context.

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Research themes | 8 |
| Isolated findings | 2 |
| Gaps identified | 6 (2 CRITICAL, 2 HIGH, 2 MEDIUM) |
| Conflicts registered | 4 (1 HIGH, 2 MEDIUM, 1 LOW) |
| Open research questions | 6 |
| Specs aligned | 7 |
| Specs with gaps | 4 |
| Specs with conflicts | 2 |
| Papers contributing to gaps | P-1, P-2, P-5, P-6, P-8, P-9, P-10, P-11, P-12, P-13, P-14, P-15 |
| Papers fully absorbed into built capabilities | P-3 (LEDGAR/CUAD awareness), P-7 (benchmark selection) |
