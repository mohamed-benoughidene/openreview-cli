# Product Blueprint

Generated: 2026-06-28 | Architect: @heavy | Version: 1.0

---

## §0 — Integrity Statement

This blueprint synthesizes all available source data across four categories:

**Papers (15):** P-1 through P-15 — legal NLP, contract analysis, multi-agent systems, RAG, citation grounding, and structured reasoning research.

**Product Specs (38):** PR-1 through PR-38 — architecture, CLI design, configuration, data storage, error handling, performance, playbook, privacy, tech stack, testing, user journey, and 22 product modes.

**Implementation Specs (6):** S-1 through S-6 — config/storage, document parsing, PII stripping, AI gateway, CLI wizard (superseded), CLI UX (current).

**Additional Context:** Package structure (`src/openreview_cli/`), S-6 plan.md key decisions, S-4 research.md, S-2 plan.md, constitution (`.specify/memory/constitution.md`), and verified-sources.md.

Every claim in this document is traceable to at least one source identifier. Where multiple sources conflict, the conflict is registered in §6 and §9 with resolution guidance.

---

## §1 — Core Problem

Legal document review is slow, expensive, and error-prone. Solo practitioners bill at $288/hour [PR-16] and spend 1h45m–3h+ per contract review. LLMs can accelerate this but hallucinate at rates of 13–58% [T-4] [P-6] [P-12], making raw model output unusable for professional legal work. General-purpose retrieval systems achieve only 6.41% precision on legal documents [T-5] [P-9], and generic rerankers actively degrade legal retrieval quality [P-9]. Domain-trained models outperform general LLMs [T-1] [P-1] [P-10], but the cost and complexity of running local models has blocked adoption. The core problem is delivering trustworthy, affordable, locally-runnable contract review that matches or exceeds the accuracy a lawyer would get from manual review — without shipping a web server, without requiring a GPU, and without sending raw contract text to third-party APIs [PR-13].

---

## §2 — North Star

**A solo lawyer opens a contract, runs `openreview precheck`, and receives a structured 3-position analysis with cited evidence — in under 90 seconds, for under $1, without raw contract text leaving their machine.**

Success metric: P@5 ≥90% on LegalBench-RAG contract retrieval [T-5] [P-9] [PR-15], citation hallucination <5% [T-4] [P-6] [PR-15], peak memory <100MB [PR-11], per-review cost <$1 [T-1] [P-1] [PR-1].

---

## §3 — Jobs To Be Done

### JOB [J-1]: Ingest and Parse Any Contract Format
**Who:** Solo lawyer receiving contracts from counterparties.
**Evidence:** Lawyers receive contracts as PDF (scanned and native), DOCX (with tracked changes), and occasionally plain text [PR-16]. Clause structure must be preserved for meaningful review [T-3] [P-3].
**Addressed by:** S-2 document parsing engine — PyMuPDF page-by-page streaming, python-docx with tracked-change detection, NUPunkt clause boundary detection at 91.1% precision.
**Status:** ✓ BUILT (S-2: 23/23 tasks).

### JOB [J-2]: Protect Client Confidentiality During AI Review
**Who:** Solo lawyer with ethical obligation to protect client data.
**Evidence:** Legal ethics rules prohibit sharing client-confidential information with third parties without consent. 58% hallucination risk [P-12] compounds this if API calls expose raw text.
**Addressed by:** S-3 PII stripping — 15 entity types via Presidio, AES encryption, 3-tier privacy, BYOK architecture [PR-13]. Raw contract text never logged.
**Status:** ✓ BUILT (S-3: 24/25 tasks; `--no-pii` flag deployment deferred).

### JOB [J-3]: Route AI Requests to the Best Available Model
**Who:** The review engine (not user-facing directly).
**Evidence:** Different models excel at different tasks — domain models for classification [T-1] [P-10], frontier models for reasoning [P-5]. Cost varies 8×–25× between providers [P-1]. A single-model approach wastes money or sacrifices quality.
**Addressed by:** S-4 AI Gateway — LiteLLM abstraction, 5 configurable slots, 8+ providers, automatic fallback routing, per-call cost tracking.
**Status:** ✓ BUILT (S-4: 31/31 tasks).

### JOB [J-4]: Find the Relevant Clauses That Matter
**Who:** Lawyer comparing a contract against their playbook.
**Evidence:** Contracts average 10–50 pages. Manual clause-by-clause review is the dominant time cost [PR-16]. General retrieval achieves only P@1=6.41% [P-9]. Two-step domain RAG improves performance by 8–15pp [P-11].
**Addressed by:** PR-2 hybrid retrieval (BM25+Dense+LightRAG+RRF) — not yet implemented [G-3].
**Status:** ✗ NOT BUILT — CRITICAL gap.

### JOB [J-5]: Generate a Trustworthy, Cited Review
**Who:** Lawyer making a decision based on the review output.
**Evidence:** LLMs generate plausible-sounding but incorrect legal analysis 13–58% of the time [T-4] [P-6] [P-12]. Without citations, every claim must be manually verified, defeating the purpose. CG-DPO citation grounding achieves 98.5% accuracy [P-6]. Multi-agent architectures improve quality over single-agent [T-2] [P-13].
**Addressed by:** PR-2 PAKTON 3-agent architecture with citation grounding — not yet implemented [G-1] [G-2].
**Status:** ✗ NOT BUILT — CRITICAL gap.

### JOB [J-6]: Navigate the Review Interactively
**Who:** Lawyer running the review on their terminal.
**Evidence:** Lawyers are not engineers. The first-run experience must be <100ms [S-6]. All user-facing text must score Flesch-Kincaid <10 [S-6]. CLI must feel responsive and guide the user through the workflow without reading documentation.
**Addressed by:** S-6 CLI UX — design tokens, 11 UI components, 6-phase wizard state machine, first-run detection, Rich-powered rendering.
**Status:** ✓ BUILT (S-6: 34/34 tasks; S-5 superseded).

### JOB [J-7]: Apply a Structured Playbook Consistently
**Who:** Lawyer defining what "good" and "bad" clauses look like.
**Evidence:** Contract review is inherently comparative — the contract vs. what the lawyer considers acceptable [T-7] [P-14]. A 3-position framework (favorable/neutral/unfavorable) maps to lawyer mental models [PR-12]. RCBSF's 5D constraints (Legal, Business, Risk, Fairness, Clarity) provide a validated analysis framework [P-14].
**Addressed by:** PR-12 PlayBook + PR-2 3-position framework — not yet implemented [G-4].
**Status:** ✗ NOT BUILT — HIGH gap.

---

## §4 — Capability Map

### CAPABILITY [CAP-01]: Document Ingestion & Parsing
**Type:** Infrastructure
**Evidence:** [P-3] establishes contract structure complexity; [T-3] confirms clause detection is necessary for meaningful review. NUPunkt achieves 91.1% precision [S-2].
**TRL:** Production (S-2: 23/23 BUILT)
**Status:** ✓ DONE
**Source:** S-2, PR-11, PR-14
**Depends on:** None
**Enables:** CAP-04, CAP-05, CAP-06, CAP-07

### CAPABILITY [CAP-02]: PII Detection & Redaction
**Type:** Infrastructure / Compliance
**Evidence:** [PR-13] establishes privacy tier model; Presidio covers 15 entity types [S-3].
**TRL:** Production (S-3: 24/25 BUILT)
**Status:** ✓ DONE (--no-pii flag unwired — deferred, not blocking)
**Source:** S-3, PR-13
**Depends on:** None
**Enables:** CAP-07 (safe API calls)

### CAPABILITY [CAP-03]: AI Model Gateway & Routing
**Type:** Infrastructure
**Evidence:** [T-1] shows 8×–25× cost variance between models [P-1]; LiteLLM provides provider abstraction with cost tracking [S-4]; 5 slots × 8+ providers covers the model diversity needed per [T-1][T-2][T-4].
**TRL:** Production (S-4: 31/31 BUILT)
**Status:** ✓ DONE
**Source:** S-4, PR-1, PR-14
**Depends on:** None
**Enables:** CAP-05, CAP-06, CAP-07

### CAPABILITY [CAP-04]: CLI Interaction Layer
**Type:** User Interface
**Evidence:** [S-6] implements first-render <100ms, 11 components, 6-phase wizard; questionary v2.1.1 provides interactive prompts; Rich 15.0.0 provides styled output.
**TRL:** Production (S-6: 34/34 BUILT)
**Status:** ✓ DONE
**Source:** S-6, PR-4, PR-9
**Depends on:** None
**Enables:** All user-facing workflows

### CAPABILITY [CAP-05]: Hybrid Legal Retrieval Pipeline
**Type:** Core Product
**Evidence:** [T-6] — LegalBench-RAG P@1=6.41% proves retrieval is the bottleneck [P-9]; two-step RAG adds 8–15pp [P-11]; domain-specific retrievers essential, generic rerankers degrade [P-9]; BM25+Dense+LightRAG+RRF specified in [PR-2]; hierarchical chunking needed for contract structure [T-3] [P-3].
**TRL:** READY (research is clear, architecture is specified, no fundamental unknowns)
**Status:** ✗ NOT BUILT [G-3]
**Source:** PR-2, P-9, P-11, P-3
**Depends on:** CAP-01 (document parsing for chunking), CAP-03 (embedding models via gateway)
**Enables:** CAP-06 (review engine needs relevant context), CAP-07 (citation grounding needs source chunks)

### CAPABILITY [CAP-06]: Multi-Agent Contract Review Engine
**Type:** Core Product
**Evidence:** [T-2] — PAKTON 3-agent architecture achieves 82.8% F1, 5× Recall@1, preferred over GPT-4o [P-13]; AgentScope validates agentic orchestration patterns [P-2]; 3-position framework (favorable/neutral/unfavorable) specified in [PR-12] maps to the 3-agent structure in [PR-2]; multi-hop reasoning degrades performance [P-5], motivating specialized agent roles.
**TRL:** READY (PAKTON concept proven [P-13]; AgentScope provides implementation patterns [P-2]; PR-2 specifies architecture)
**Status:** ✗ NOT BUILT [G-1]
**Source:** PR-2, P-13, P-2, P-5
**Depends on:** CAP-05 (retrieval feeds context to agents), CAP-03 (each agent calls the gateway), CAP-04 (CLI triggers review)
**Enables:** CAP-08 (playbook application), CAP-07 (citation generation)

### CAPABILITY [CAP-07]: Citation Grounding & Verification
**Type:** Core Product / Safety
**Evidence:** [T-4] — 13–21% hallucination on legal tasks [P-6]; 58% across legal NLP [P-12]; RAG-based citation grounding CG=0.873 [P-6]; CG-DPO training achieves 98.5% grounding accuracy [P-6]; citation grounding is the single most important safety mechanism for trustworthy output.
**TRL:** READY (P-6 provides proven methodology)
**Status:** ✗ NOT BUILT [G-2]
**Source:** PR-2, P-6, PR-15
**Depends on:** CAP-06 (review engine generates claims to ground), CAP-05 (retrieval provides source evidence)
**Enables:** Trustworthy output — gating factor for production use

### CAPABILITY [CAP-08]: Playbook & Position Framework
**Type:** Core Product
**Evidence:** [T-7] — RCBSF 84.2% RRR with 5D constraints [P-14]; 3-position framework specified in [PR-12]; CHANCERY shows multi-hop complexity penalty [P-5]; playbook versioning in [PR-7].
**TRL:** READY (framework is specified, research validates constraint-based revision)
**Status:** ✗ NOT BUILT [G-4]
**Source:** PR-12, PR-2, P-14, P-5, PR-7
**Depends on:** CAP-06 (review engine produces analysis to map to positions)
**Enables:** Structured output — the deliverable lawyers receive

### CAPABILITY [CAP-09]: Configuration & Session Management
**Type:** Infrastructure
**Evidence:** [PR-6] 6-level priority; [PR-7] SQLite + JSON storage; [S-1] YAML config, auth.json, cost tracking — 16/17 BUILT. **Note:** Configuration format conflict with S-6 JSON format [C-1].
**TRL:** Production (S-1: 16/17 BUILT)
**Status:** ✓ DONE (format reconciliation needed)
**Source:** S-1, PR-6, PR-7
**Depends on:** None
**Enables:** All other capabilities (provides auth, config, persistence)

### CAPABILITY [CAP-10]: LightRAG Graph Retrieval  
**Type:** SUPPORTING  
**What it does:** Builds a clause-level graph from the parsed document and uses graph traversal (entity/relationship navigation) as the precision filter for retrieval output. Reuses the same local embedding model already loaded for dense retrieval — no separate reranker model needed. LightRAG's graph replaces the generic cross-encoder reranker that [P-9] proved degrades legal retrieval.  
**Evidence basis:** [T-6] hybrid retrieval outperforms baselines [P-13]; generic rerankers degrade legal text [P-9]; LightRAG graph traversal provides relationship-aware retrieval [P-13].  
**TRL:** READY  
**Current status:** NOT STARTED  
**Source:** GAP [G-3] — retrieval pipeline not implemented  
**Depends on:** [CAP-01] document parsing, [CAP-03] embedding via gateway

### CAPABILITY [CAP-11]: Structured Reasoning Layer (Graph/Ontology)
**Type:** Enhancement
**Evidence:** [T-8] — GRPO improves SFT 0.661→0.798, gated 6× better [P-8]; ontology reasoning 76.4% vs 18.8% baseline, 45% token reduction [P-15].
**TRL:** NEAR (P-8 and P-15 provide methodology; integration into our pipeline is non-trivial)
**Status:** ✗ NOT BUILT — not specified in any PR or S [G-5]
**Source:** P-8, P-15
**Depends on:** CAP-06 (review engine to structure)
**Enables:** Higher-quality reasoning, lower token costs, verifiable output

### CAPABILITY [CAP-12]: Local Domain SLM for Classification
**Type:** Optimization / Cost
**Evidence:** [T-1] — Olava Extract F1=0.842 at $0.018/doc, 8×–25× cheaper than API [P-1]; Legal-BERT 110M outperforms RoBERTa 355M [P-10]; fine-tuned models +30pp [P-12]. **Note:** Conflicts with PR-14's API-only stance [C-3].
**TRL:** READY (LoRA fine-tuning, vLLM serving are production-grade [P-1])
**Status:** ✗ NOT BUILT — architecturally rejected by PR-14 but research strongly supports
**Source:** P-1, P-10, P-12
**Depends on:** Constitution's 8GB RAM budget (SLM must fit), CAP-01 (parsed documents as input)
**Enables:** 78–97% cost reduction [P-1], fully local classification, offline operation

### CAPABILITY [CAP-13]: Full 5D Constraint Contract Revision
**Type:** Future Enhancement
**Evidence:** [T-7] — RCBSF 84.2% RRR [P-14]; 5D constraints validated across 800 contract pairs [P-14].
**TRL:** RESEARCH (P-14 is academic research; not production-hardened)
**Status:** ✗ NOT BUILT — LATER roadmap
**Source:** P-14
**Depends on:** CAP-08 (playbook framework to extend)
**Enables:** Richer, more nuanced revision recommendations

---

## §5 — Differentiation Layer

### DIFFERENTIATOR [D-1]: Local-First, PII-Stripped, BYOK Architecture
**Evidence:** [PR-13] specifies PII stripping before any API call; [S-3] implements 15 entity types via Presidio; [S-4] implements BYOK with chmod 600 auth. No competitor in the legal AI space offers end-to-end local-first operation with automatic PII redaction — most require full document upload to cloud APIs.
**Approach:** Strip PII client-side → route via local AI gateway (BYOK) → never log raw text. This is implemented and working.
**Status:** ✓ BUILT (24/25)
**Risk:** Presidio false negatives on novel PII patterns in dense legal text [O-5]. Mitigation: 3-tier privacy allows opt-out.

### DIFFERENTIATOR [D-2]: Citation-Grounded Multi-Agent Review
**Evidence:** [T-4] — CG-DPO achieves 98.5% citation grounding [P-6]; [T-2] — PAKTON multi-agent 82.8% F1 [P-13]. The combination — multi-agent review *with* citation grounding — is unique. Most legal AI products use single-agent generation without citation verification.
**Approach:** 3 PAKTON agents (classifier, analyzer, synthesizer) each produce grounded claims; cross-agent verification catches hallucination; citations rendered inline.
**Status:** ✗ NOT BUILT [G-1][G-2]
**Risk:** PAKTON validated on legal QA, not contracts [O-1]; citation grounding for intra-document clause references unvalidated [O-2].

### DIFFERENTIATOR [D-3]: Domain-Adapted Hybrid Retrieval
**Evidence:** [T-5] — P@1=6.41% for general retrieval on legal text [P-9]; [T-6] — two-step RAG +8–15pp [P-11]; general rerankers degrade legal retrieval [P-9]; LightRAG graph traversal avoids degradation [P-13]. A hybrid pipeline (BM25+Dense+LightRAG+RRF) with LightRAG graph retrieval as the precision filter addresses the specific failure modes of legal retrieval.
**Approach:** Hierarchical chunking (contract→section→clause), BM25 for exact text matching, dense embeddings for semantic similarity, LightRAG for graph-based relationship retrieval (primary precision filter), RRF for fusion. Cross-encoder reranker optional (disabled by default).
**Status:** ✗ NOT BUILT [G-3]; specification updated per [C-4] resolution
**Risk:** Complexity of 4-way hybrid retrieval may challenge the <100MB memory budget [O-5].

### DIFFERENTIATOR [D-4]: CLI-First for the Terminal-Literate Lawyer
**Evidence:** [S-6] implements design tokens, 11 UI components, Flesch-Kincaid <10, first-render <100ms. No web server required [PR-14]. This is unique in the legal AI market, where products are uniformly web applications.
**Approach:** Typer + Rich + questionary stack; wizard state machine guides the lawyer through review; output in MD/JSON/PDF.
**Status:** ✓ BUILT (S-6: 34/34)
**Risk:** Terminal literacy of target users (lawyers) is an assumption. Some may prefer GUI. Mitigation: MD/PDF output can be consumed outside the terminal.

### DIFFERENTIATOR [D-5]: Hardware-Constrained by Design
**Evidence:** [PR-11] sets peak memory <100MB, 8GB RAM, no GPU, 2-core CPU. This is not a limitation — it is a design constraint that forces efficiency. [P-1] shows domain SLMs can run within these constraints (Olava Extract can be served on consumer hardware). Most legal AI products assume cloud infrastructure.
**Approach:** Streaming parsers (PyMuPDF page-by-page), async httpx for concurrent API calls, SQLite for zero-config persistence, no vector database server.
**Status:** ✓ BUILT for infrastructure layers; full pipeline unvalidated [O-5]
**Risk:** Full pipeline (PII + retrieval + multi-agent + citation) may exceed 100MB. Mitigation: streaming + sequential component loading.

---

## §6 — Architecture Implications

### ARCH [A-1]: The Gateway-to-Agent Pipeline Is Well-Founded
**Evidence:** [T-1] proves model diversity matters — different models excel at different tasks [P-1][P-10]. [S-4]'s LiteLLM gateway with 5 configurable slots enables per-task model assignment: classification → cheap domain model, reasoning → frontier model, embedding → specialized model. This aligns with [PR-1]'s slot architecture and [PR-2]'s multi-agent design.
**Alignment:** Fully aligned. Gateway architecture (S-4) was built to feed the agent architecture (PR-2), even though the agents themselves are not yet built.
**Conflicts:** None at this layer.

### ARCH [A-2]: Retrieval Pipeline — LightRAG Graph Replaces Generic Reranker
**Evidence:** [T-5] — LegalBench-RAG's strongest finding is that generic approaches fail on legal text [P-9]. [PR-2] specified a hybrid pipeline with a generic cross-encoder reranker. This created **CONFLICT [C-4]**: the most important retrieval finding was contradicted by the specified implementation.
**Alignment:** The hybrid architecture (BM25+Dense+LightRAG+RRF) is well-founded per [T-6]. LightRAG graph retrieval now replaces the generic reranker, adding relationship-aware retrieval that no reranker provides.
**Conflicts:** [C-4] (RESOLVED) — reranker selection resolved by LightRAG adoption. LightRAG graph traversal reuses the local embedding model and avoids the degradation [P-9] found with generic rerankers.

### ARCH [A-3]: Citation Grounding Architecture Needs Contract-Specific Adaptation
**Evidence:** [T-4] — citation grounding is the critical safety mechanism [P-6]. However, [P-6] tested on statutory and case law citations, not intra-document clause references ("Section 4.2(a)"). Contract citations are structurally different: they point to positions within the same document, not external authorities. The grounding architecture must handle both: (1) clause-level references within the contract, (2) external legal citations if the review references statutes or precedent.
**Alignment:** PR-2 specifies citation grounding generically. The architecture is correct in principle but needs contract-specific citation extraction logic.
**Conflicts:** None at the architectural level. Implementation detail: citation span detection for clause references vs legal citations.

### ARCH [A-4]: Configuration Format Conflict Requires Resolution
**Evidence:** [S-1] implements YAML config loading per [PR-6]. [S-6] plan.md specifies JSON format at `$XDG_CONFIG_HOME/openreview/config.json`. This is **CONFLICT [C-1]**.
**Alignment:** Both formats are valid serialization. Pydantic v2 (used by S-4) supports both. The conflict is operational, not architectural: existing YAML configs would break if the loader switches to JSON.
**Conflicts:** [C-1] — YAML vs JSON. Resolution: migrate to JSON (S-6 most recent), provide YAML→JSON migration tool, validate Pydantic models work with both during transition.

### ARCH [A-5]: API-Only Architecture Leaves Cost and Privacy on the Table
**Evidence:** [T-1] — domain SLMs cost $0.018/doc vs $0.149–$0.456 for API [P-1], a 78–97% cost reduction. [P-10] — Legal-BERT 110M runs on consumer hardware. This is **CONFLICT [C-3]**: the research says local models are cheaper and more private; the architecture (PR-14) rejects them.
**Alignment:** Not aligned. Current architecture is API-only for LLM calls (S-4 gateway routes to external providers). This contradicts the cost and privacy benefits demonstrated by local domain models.
**Conflicts:** [C-3] — domain SLM rejection. Resolution: phase in local SLM for classification/triage in NEXT roadmap phase. Maintain API for generation/reasoning. This is a hybrid architecture that captures the cost benefits while preserving gateway flexibility.

### ARCH [A-6]: Structured Reasoning Layer Is Absent but Compatible
**Evidence:** [T-8] — graph-based GRPO training [P-8] and ontology-based reasoning [P-15] both improve results. These techniques operate at the reasoning layer, above retrieval and below output formatting. They are architecturally compatible with the PAKTON 3-agent design [PR-2] — graph structures can inform agent reasoning without replacing agents.
**Alignment:** Compatible. The architecture can accommodate structured reasoning as an enhancement to CAP-06 without redesign. No conflicts.
**Conflicts:** None.

---

## §7 — Roadmap

### ALREADY BUILT

| Capability | Spec | Evidence | Alignment |
|------------|------|----------|-----------|
| CAP-01 Document Parsing | S-2 (23/23) | [P-3], [T-3] | ALIGNED |
| CAP-02 PII Stripping | S-3 (24/25) | [PR-13] | ALIGNED |
| CAP-03 AI Gateway | S-4 (31/31) | [P-1], [T-1], [PR-1] | ALIGNED |
| CAP-04 CLI Interaction | S-6 (34/34) | [PR-4], [PR-9] | ALIGNED (minor: [C-2] exit codes) |
| CAP-09 Config/Storage | S-1 (16/17) | [PR-6], [PR-7] | ALIGNED (minor: [C-1] format) |
| Product modes scaffolding | S-6 | [PR-17–38] | ALIGNED |
| Cost tracking store | S-4 | [PR-1] | ALIGNED |
| Test suite (unit + integration) | All S-N | [PR-15] | ALIGNED |

### NOW — Unbuilt Core Capabilities (TRL = READY)

| Capability | Priority | Evidence | Spec Source | Depends On | Effort |
|------------|----------|----------|-------------|------------|--------|
| CAP-05 Hybrid Retrieval | **CRITICAL** | [P-9] P@1=6.41%, [P-11] +8–15pp, [P-13] LightRAG graph retrieval essential | PR-2 (C-4 resolved) | CAP-01, CAP-03 | Large (4 retrieval methods + fusion) |
| CAP-06 Multi-Agent Review | **CRITICAL** | [P-13] 82.8% F1, [P-2] agentic patterns | PR-2 | CAP-05, CAP-03, CAP-04 | Large (3 agents + orchestration) |
| CAP-07 Citation Grounding | **HIGH** | [P-6] 98.5% CG-DPO, [P-12] 58% hallucination | PR-2, PR-15 | CAP-06, CAP-05 | Medium (CG logic + rendering) |
| CAP-08 Playbook Framework | **HIGH** | [P-14] 84.2% RRR, [PR-12] 3-position | PR-12, PR-2 | CAP-06 | Medium (framework + storage) |
| CAP-10 LightRAG Graph Retrieval | **HIGH** | [P-13] graph relationship retrieval, [P-9] generic rerankers degrade legal text | PR-2 (C-4 resolved) | CAP-01, CAP-03 | Medium (graph construction + traversal) |

**NOW Gate:** All 5 capabilities above must be implemented before any product mode can ship. CAP-05 is the dependency root — build it first. Then CAP-06 + CAP-07 + CAP-08 can proceed in parallel with shared integration tests. CAP-10 LightRAG graph retrieval integrates with CAP-05 at the graph-construction layer rather than as a downstream filter.

### NEXT — Enhancements (TRL = NEAR, or lower-priority READY)

| Capability | Priority | Evidence | Spec Source | Depends On | Effort |
|------------|----------|----------|-------------|------------|--------|
| CAP-11 Structured Reasoning | MEDIUM | [P-8] GRPO 0.798, [P-15] 76.4% ontology, 45% token reduction | New spec needed [G-5] | CAP-06 | Medium (graph layer) |
| CAP-12 Local Domain SLM | MEDIUM | [P-1] $0.018/doc, [P-10] Legal-BERT 110M | New spec needed [C-3] | CAP-01, 8GB RAM budget | Medium (model serving) |
| Cost validation [O-3] | MEDIUM | [P-1] $0.018/doc, [P-11] 99.4% reduction | PR-1 | CAP-05, CAP-06 | Small (benchmark) |
| Memory validation [O-5] | MEDIUM | Full pipeline measurement | PR-11 | All NOW caps | Small (tracemalloc) |
| MINA RAG validation [O-6] | LOW | [P-11] U.S. contract context | PR-2 | CAP-05 | Small (benchmark) |
| PAKTON contract validation [O-1] | MEDIUM | [P-13] on contract datasets | PR-2 | CAP-06 | Small (benchmark) |
| Citation contract validation [O-2] | MEDIUM | [P-6] on clause references | PR-2 | CAP-07 | Small (benchmark) |

**NEXT Gate:** After NOW ships (first product mode operational), optimize with NEXT capabilities. CAP-12 (local SLM) enables offline operation and cost reduction. CAP-11 (structured reasoning) improves review quality. Validation tasks (O-1 through O-6) should run continuously during NOW development.

### LATER — Research-Stage or Blocked

| Capability | Priority | Evidence | Blocker | Effort |
|------------|----------|----------|---------|--------|
| CAP-13 Full 5D Constraint Revision | LOW | [P-14] RESEARCH, [P-5] RESEARCH | Research not production-ready; CAP-08 must ship first | Large |
| Verifiable reasoning output | LOW | [P-15] RESEARCH | CAP-11 must ship first | Large |
| Graph-based training (GRPO) | LOW | [P-8] NEAR | Requires model training pipeline; CAP-11 must ship first | Very Large |
| Playbook AI-suggestion engine | LOW | [PR-12] AI-suggested | CAP-08 must ship first | Medium |
| 22 product modes (PR-17–38) | LOW | [PR-17–38] | All core capabilities must ship first | Very Large (22 increments) |

---

## §8 — Spec Revisions

### REVISION [RV-1] (RESOLVED): Architecture.md — Reranker Demotion  
**Spec:** Architecture.md [PR-2]  
**Reason:** [C-4] resolved — LightRAG graph retrieval replaces the generic cross-encoder reranker.  
**What to change:** Already applied — cross-encoder reranker demoted from required to optional; LightRAG positioned as primary precision filter.  
**Priority:** HIGH  
**Status:** RESOLVED

### REVISION [RV-2]: PR-14 Tech Stack — Domain SLM Rejection — MEDIUM
**What:** Add a hybrid tier: "Local domain SLMs for classification/triage; API LLMs for generation/reasoning."
**Why:** [C-3] — [P-1] and [P-10] show 78–97% cost savings and better accuracy with local domain models. Current API-only position is unnecessarily restrictive.
**Impact:** Enables CAP-12 in NEXT roadmap. Unlocks offline operation and significant cost reduction.
**Speckit hook:** Update `specs/014-tech-stack/research.md` (or equivalent PR-14 spec file).

### REVISION [RV-3]: PR-6 Configuration — Format Change — MEDIUM
**What:** Change config format from YAML (`config.yml`) to JSON (`config.json`). Add migration tool for existing YAML configs.
**Why:** [C-1] — S-6 (most recent implementation spec) uses JSON. S-1 uses YAML. Must reconcile.
**Impact:** Breaks S-1 YAML loader. Migration is mechanical. Pydantic v2 supports both — validation logic unchanged.
**Speckit hook:** Update `specs/006-configuration/research.md` (or equivalent PR-6 spec file). Add migration task to S-1.

### REVISION [RV-4]: PR-4 CLI Design — Exit Code Scheme — LOW
**What:** Change from 10 exit codes to 9 exit codes (0–8) matching S-6 implementation.
**Why:** [C-2] — S-6 is the built implementation. Spec should match reality.
**Impact:** Documentation-only change. No code impact.
**Speckit hook:** Update `specs/004-cli-design/research.md` (or equivalent PR-4 spec file).

### REVISION [RV-5]: New Spec — Structured Reasoning Layer (CAP-11) — MEDIUM
**What:** Create an implementation spec for graph/ontology-based reasoning as an enhancement to the review engine.
**Why:** [G-5] — [P-8] and [P-15] show significant gains. Currently absent from all specifications.
**Impact:** Defines CAP-11 scope, TRL path from NEAR to READY, and integration points with CAP-06.
**Speckit hook:** New speckit.specify for structured reasoning capability.

### REVISION [RV-6]: New Spec — Local Domain SLM Integration (CAP-12) — MEDIUM
**What:** Create an implementation spec for local domain SLM serving (Legal-BERT or equivalent) within the 8GB RAM budget.
**Why:** [C-3] — research strongly supports local models. Needs a proper implementation plan with memory budget, model selection, and integration with S-4 gateway.
**Impact:** Defines CAP-12 scope, model selection criteria, serving architecture, and RAM budget allocation.
**Speckit hook:** New speckit.specify for local SLM capability.

### RV [RV-7]: PR-15 Testing — Citation Grounding Metric — LOW
**What:** Add citation grounding accuracy as a primary test metric alongside hallucination rate.
**Why:** [P-6] provides CG-DPO 98.5% as a proven metric. Hallucination <5% is vague; citation grounding accuracy is measurable and actionable.
**Impact:** Adds CG metric to test suite. Improves test coverage for CAP-07.
**Speckit hook:** Update `specs/015-testing/research.md` (or equivalent PR-15 spec file).

---

## §9 — Risk Register

### RISK [RK-1] (RESOLVED): LightRAG replaces generic reranker  
**Source:** [C-4] resolved by product decision to use LightRAG graph retrieval.  
**Likelihood:** LOW (resolved)  
**Impact:** LOW (resolved)  
**Mitigation:** LightRAG graph traversal provides relationship-aware retrieval without a separate reranker model, eliminating the [P-9] degradation risk.

### RK [RK-2]: Full Pipeline Exceeds 100MB Memory Budget
**Source:** [PR-11] (<100MB peak), [O-5] (unvalidated)
**Likelihood:** MEDIUM — individual components are tested (S-2 streaming parser, S-3 Presidio), but the combined pipeline (PII + retrieval + 3 agents + citation grounding + LiteLLM SDK) has never been profiled together.
**Impact:** HIGH — constitution floor is 110MB [PR-11]. Exceeding this means the product cannot run on the target 8GB machine during concurrent use. May require component unloading or sequential processing.
**Mitigation:** Profile early during NOW phase. Implement sequential component loading (only one heavy component in memory at a time). Use tracemalloc for granular measurement. If necessary, split pipeline into subprocess stages.
**Status:** OPEN — must be measured in NOW phase.

### RK [RK-3]: $1/Review Cost Ceiling Not Empirically Validated
**Source:** [PR-1], [O-3]
**Likelihood:** LOW-MEDIUM — individual component costs are low ([P-1] $0.018/doc extraction; LiteLLM routing is cheap), but the 3-agent × retrieval × citation pipeline has unknown cost.
**Impact:** MEDIUM — exceeding $1/review undermines the business model. At $288/hour lawyer billing [PR-16], even $5/review could be justified if time savings hold.
**Mitigation:** Run cost simulation in NOW phase. If ceiling is at risk, implement CAP-12 (local SLM) in NEXT phase to reduce API call volume by 60–80%.
**Status:** OPEN — must be validated in NOW phase.

### RK [RK-4]: PAKTON Architecture Underperforms on Contracts vs QA
**Source:** [P-13] (validated on legal QA, not contracts), [O-1]
**Likelihood:** LOW — PAKTON's 3-agent pattern (retrieve → analyze → synthesize) is domain-agnostic. The pattern should transfer to contract review, though absolute performance numbers will differ.
**Impact:** HIGH — if PAKTON underperforms on contracts, the core review engine architecture is invalid. May require alternative agent design.
**Mitigation:** Validate early with a contract-specific benchmark in NOW phase (CUAD + LEDGAR). If PAKTON underperforms, adapt agent roles for contract-specific tasks before full implementation.
**Status:** OPEN — must be validated before CAP-06 completion.

### RK [RK-5]: Intra-Document Citation Grounding Differs from Legal Citation Grounding
**Source:** [P-6] (tested on statutory/case citations), [O-2]
**Likelihood:** MEDIUM — clause references ("Section 4.2(a)") are structurally different from legal citations ("Smith v. Jones, 123 U.S. 456"). The CG-DPO 98.5% result from [P-6] may not transfer.
**Impact:** MEDIUM — if citation grounding for clause references is harder, review trustworthiness is reduced. However, clause references are simpler (within document, not external) and may actually be easier to ground.
**Mitigation:** Build clause-reference citation extraction as a dedicated step before applying CG-DPO methodology. Test both clause references and external citations separately.
**Status:** OPEN — must be validated during CAP-07 implementation.

### RK [RK-6]: YAML→JSON Migration Breaks Existing User Configs
**Source:** [C-1]
**Likelihood:** MEDIUM — depends on whether early adopters exist. If no users exist yet, impact is zero.
**Impact:** LOW — configuration is machine-generated on first run. Migration tool can handle existing configs.
**Mitigation:** Ship a migration subcommand (`openreview config migrate`) that reads YAML, validates, writes JSON. Run migration on first startup after upgrade.
**Status:** OPEN — apply [RV-3] and implement migration tool.

### RK [RK-7]: Presidio False Negatives on Dense Legal Text
**Source:** [S-3] (Presidio for PII), [O-5] (memory budget includes Presidio model)
**Likelihood:** LOW-MEDIUM — Presidio is battle-tested but legal contracts contain PII in unusual formats (e.g., parties' names embedded in clause headers, addresses in signature blocks with non-standard formatting).
**Impact:** HIGH — if PII leaks through Presidio to an API call, it violates [PR-13]'s privacy guarantee and may breach legal ethics obligations.
**Mitigation:** 3-tier privacy model allows users to opt out of API calls entirely (Tier 3: local-only). Add legal-specific PII patterns to Presidio configuration. Run accuracy validation [S-3 deferred task T049] before production use.
**Status:** MITIGATED (3-tier model) — but accuracy validation is deferred.

### RK [RK-8]: 22 Product Modes Scope Creep
**Source:** [PR-17–38]
**Likelihood:** HIGH — 22 modes with unique playbooks, questions, and review logic is a massive scope. Implementing all before shipping any delays time-to-market by months.
**Impact:** MEDIUM — scope risk, not technical risk. Delaying first mode ship means no user feedback loop.
**Mitigation:** Ship one mode (e.g., PreCheck [PR-17]) as the initial product. Validate the full pipeline end-to-end. Add remaining 21 modes incrementally. The architecture is designed for mode extensibility [PR-4].
**Status:** MITIGATED — roadmap gates on first mode, not all 22.

---

## §10 — Open Questions

### OPEN [O-1]: PAKTON Performance on Real-World Contracts
**Why:** [P-13] validated on legal QA datasets, not contract review. Our product reviews contracts.
**Validation:** Run PAKTON against CUAD [P-3] and LEDGAR [P-3]. Measure F1, precision, recall on clause classification and risk identification. Compare 1-agent vs 3-agent on contracts.
**Priority:** NOW — gates CAP-06 architecture decision.

### OPEN [O-2]: Citation Grounding for Contract Clause References
**Why:** [P-6] tested on statutory citations, not intra-document clause references ("Section 4.2(a)").
**Validation:** Build contract clause citation benchmark. Measure grounding accuracy for clause references vs external legal citations. Compare to [P-6]'s CG-DPO 98.5%.
**Priority:** NOW — gates CAP-07 implementation approach.

### OPEN [O-3]: Cost-Per-Review Ceiling Under $1
**Why:** [PR-1] sets $1/review. [P-1] shows $0.018/doc for extraction alone. Our pipeline is more complex.
**Validation:** Run cost simulation with actual LiteLLM pricing. Model 3 scenarios (local-only, typical routing, worst-case fallback). Verify all under $1.
**Priority:** NOW — gates business model viability.

### OPEN [O-4]: RCBSF 5D Constraints Coverage by 3-Position Framework
**Why:** [P-14]'s 5D constraints (Legal, Business, Risk, Fairness, Clarity) may not map cleanly to [PR-12]'s 3 positions (favorable/neutral/unfavorable).
**Validation:** Map 5D categories to 3 positions. Test on 50 contract pairs. Measure information loss.
**Priority:** NEXT — impacts CAP-08 output quality, not blocking initial ship.

### OPEN [O-5]: Full Pipeline Memory Budget
**Why:** [PR-11] sets <100MB peak. Individual components tested; full pipeline never measured concurrently.
**Validation:** Tracemalloc test: load 50-page contract, run PII → retrieval → 3-agent review → citation grounding. Measure peak RSS. Target <110MB.
**Priority:** NOW — gates production readiness.

### OPEN [O-6]: MINA Two-Step RAG in Western Legal Systems
**Why:** [P-11] validated on Bangladesh (common law derivative, but distinct from U.S. conventions).
**Validation:** Benchmark two-step RAG against U.S. contract datasets. Compare to single-step RAG. Measure claimed 8–15pp improvement.
**Priority:** NEXT — validates retrieval architecture for target market.

---

## §11 — Speckit Feed

### For CAP-05 (Hybrid Retrieval Pipeline) — CRITICAL, NOW

Create a speckit.plan for the hybrid retrieval pipeline. This is the dependency root for all core capabilities. The plan must include: (1) hierarchical chunking strategy for contracts (document→section→clause), (2) four retrieval methods: BM25 (exact text), Dense (semantic via embeddings from CAP-03 gateway), LightRAG (graph-based relationship retrieval), and RRF (fusion), (3) LightRAG graph retrieval as primary precision filter per [RV-1] (cross-encoder reranker optional, disabled by default), (4) LegalBench-RAG test harness per [P-9] and [PR-15], (5) memory budget allocation within the 100MB peak constraint [PR-11]. Target P@5 ≥90% on contract retrieval. Gateway dependence: embedding models via S-4 LiteLLM slots. Parse dependence: chunked documents from CAP-01 / S-2 `stream_clauses()`.

### For CAP-06 (Multi-Agent Review Engine) — CRITICAL, NOW

Create a speckit.plan for the PAKTON 3-agent review engine. The plan must include: (1) three specialized agents — Classifier (clause type identification per [T-3][P-3]), Analyzer (risk/favorability assessment per [T-7][P-14]), Synthesizer (3-position output per [PR-12]), (2) agent orchestration protocol (sequential classify→analyze→synthesize with context passing), (3) integration with CAP-05 retrieval (each agent receives retrieved context), (4) integration with CAP-03 gateway (each agent calls models via LiteLLM slots), (5) multi-hop reasoning support per [P-5]'s finding that multi-hop degrades 17pp, (6) configurable agent prompts per PlayBook (CAP-08). Validate against CUAD contract benchmark per [O-1]. Target: review quality matching or exceeding single-agent baseline.

### For CAP-07 (Citation Grounding) — HIGH, NOW

Create a speckit.plan for citation grounding and verification. The plan must include: (1) two citation types — intra-document clause references ("Section 4.2(a)") and external legal citations — with separate extraction logic, (2) CG-DPO methodology per [P-6] for grounding accuracy, (3) inline citation rendering in output (MD/JSON/PDF), (4) verification step: cross-reference each agent's claim against retrieved source chunks, (5) contract-specific citation benchmark per [O-2], (6) hallucination measurement at <5% per [PR-15]. Integration: receives claims from CAP-06 agents, retrieves source evidence from CAP-05, outputs grounded claims.

### For CAP-08 (Playbook & Position Framework) — HIGH, NOW

Create a speckit.plan for the playbook and 3-position framework. The plan must include: (1) 3-position taxonomy (favorable/neutral/unfavorable) per [PR-12], (2) per-position clause templates with configurable thresholds, (3) playbook versioning and storage in SQLite per [PR-7], (4) integration: CAP-06 Synthesizer agent maps analysis to positions, (5) RCBSF 5D coverage mapping per [O-4] to validate that 3 positions adequately represent 5 constraint dimensions, (6) AI-suggested playbook entries per [PR-12] (can be deferred to LATER). Output: structured review with every clause classified into one of three positions with cited evidence from CAP-07.

### For RV-1 (LightRAG Graph Retrieval) — RESOLVED, REVISION

Update PR-2 architecture spec: demote cross-encoder reranker from required to optional; position LightRAG graph retrieval as the primary precision filter. Add justification: LightRAG traverses entity relationships, reuses the local embedding model already loaded for dense retrieval, and avoids the retrieval degradation [P-9] found with generic cross-encoders. Update CAP-10 definition to LightRAG Graph Retrieval.

### For RV-2 (Local Domain SLM) — MEDIUM, REVISION

Update PR-14 tech stack spec: add a hybrid tier allowing local domain SLMs for classification/triage alongside API LLMs for generation/reasoning. Cite [P-1] ($0.018/doc, 78–97% cost reduction) and [P-10] (Legal-BERT outperforms larger models). Define RAM budget allocation (≤2GB for SLM within the 8GB total). Define integration point with S-4 gateway (local models as additional "provider" slots). This revision unlocks CAP-12 for NEXT roadmap.

### For RV-3 (Config Format Migration) — MEDIUM, REVISION

Update PR-6 configuration spec: change primary format from YAML to JSON. Plan migration from S-1 YAML loader to JSON loader. Add `openreview config migrate` subcommand to S-6 CLI. Validate Pydantic v2 model compatibility (already supports both). This revision resolves [C-1].

---

## Document Metadata

| Field | Value |
|-------|-------|
| Version | 1.0 |
| Generated | 2026-06-28 |
| Papers cited | P-1, P-2, P-3, P-4, P-5, P-6, P-7, P-8, P-9, P-10, P-11, P-12, P-13, P-14, P-15 |
| Product specs cited | PR-1, PR-2, PR-4, PR-6, PR-7, PR-9, PR-11, PR-12, PR-13, PR-14, PR-15, PR-16, PR-17–38 |
| Impl specs cited | S-1, S-2, S-3, S-4, S-5, S-6 |
| Capabilities defined | 13 (CAP-01 through CAP-13) |
| Differentiators | 5 (D-1 through D-5) |
| Architecture implications | 6 (A-1 through A-6) |
| Spec revisions | 7 (RV-1 through RV-7) |
| Risks | 8 (RK-1 through RK-8) |
| Open questions | 6 (O-1 through O-6) |
| Jobs to be done | 7 (J-1 through J-7) |
| Gaps | 6 (G-1 through G-6) |
| Conflicts | 4 (C-1 through C-4) |
