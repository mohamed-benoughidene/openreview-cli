# Research: Single-Party Review — PAKTON 3-Agent Pipeline

**Phase**: 0 (Research)
**Spec**: specs/011-single-party-review/spec.md
**Date**: 2026-07-02

## 1. PAKTON 3-Agent Architecture Patterns [P-13]

### Decision
Adopt the PAKTON pipeline as three sequential stages (not parallel agents): **Extraction → QA Verification → Comparison (no-op)**. Each stage is a function that receives the previous stage's output, routes through the AI Gateway (C-12–C-18), and produces structured output.

### Rationale
- The spec defines a strict sequential dependency: QA cannot run before extraction produces a result. Parallel execution would add complexity without benefit for single-party review.
- Each stage maps to a single prompt template + model routing call — no agentic loops, no tool-use, no multi-turn conversation. This keeps latency predictable and memory bounded.
- The three-stage pipeline is a core architectural pattern from the blueprint (§6.7). The structural comparison-agent placeholder ensures Phase 2 (bilateral comparison) can land without rewriting the pipeline.

### Alternatives Considered
- **Single monolithic prompt** (extraction + QA in one call): Rejected because it prevents independent model routing (SLM for extraction, larger model for QA per FR-7). Also violates the architectural pattern in §6.7.
- **Autonomous agent loop** (agent decides when to verify): Rejected — adds unnecessary complexity (tool-use, state management) for a deterministic two-step process. YAGNI.
- **Parallel extraction + QA**: Rejected — QA needs extraction output as input. Not feasible.

### Key Design Points
- Each stage receives its input as Pydantic models, not raw text.
- Stage output is validated (Pydantic) before passing to the next stage.
- If a stage fails (e.g., model returns unparseable output), the assessment is marked as `uncertain` with an error flag — the pipeline continues rather than aborting.
- The no-op comparison agent is a function that returns its input unchanged. This is not a stub — it's a deliberate pass-through that maintains the pipeline signature for Phase 2.

## 2. 3-Position Playbook Design (favorable/neutral/unfavorable)

### Decision
Playbooks are YAML files with a flat category list (no nested hierarchy). Each category defines exemplar language patterns per position and a default position.

### Rationale
- YAML is already a project dependency (pyyaml in pyproject.toml).
- Flat list is sufficient for NDA review where clauses have consistent headings (Confidentiality, Non-Solicitation, etc.). Nested hierarchy would add complexity without demonstrated need.
- The three-position taxonomy maps directly to the contract review domain: favorable, neutral, unfavorable. Uncertain is a pipeline-level status (set when QA disagrees or confidence is low), not a playbook position.

### Alternatives Considered
- **JSON playbooks**: Rejected — YAML is more human-readable for editing, and pyyaml is already a dependency. Users who override playbooks will appreciate YAML's lower ceremony.
- **Database-stored playbooks**: Rejected — bundling YAML files is simpler, works offline, and enables version control of playbook definitions. A playbook registry (DB-backed) could be added later when multiple playbooks need management.
- **Four-position taxonomy** (including "uncertain" as a playbook position): Rejected — uncertain is a pipeline verdict, not a playbook position. The playbook defines what the contract language *means*; the pipeline decides whether it's *confident* about that meaning.

### Format

```yaml
# specs/011-single-party-review/playbooks/precheck-nda-v1.yaml
id: "precheck-nda-v1"
mode: "precheck"
metadata:
  version: "1.0.0"
  description: "Bundled NDA playbook for PreCheck mode"
  author: "openreview"
categories:
  - id: "confidentiality-term"
    name: "Confidentiality Term"
    description: >
      Defines how long confidentiality obligations survive the NDA's termination.
    favorable:
      description: >
        Short, fixed confidentiality term (1-3 years). Obligation ends on a
        definite date, not tied to contract termination.
      exemplars:
        - "Confidentiality obligations shall survive for a period of three (3) years"
        - "The receiving party's obligations under this Agreement shall continue for two (2) years"
    neutral:
      description: >
        Standard 3-5 year term, mutual obligations, industry-standard exceptions.
      exemplars:
        - "The obligations set forth in this Section shall survive for a period of five (5) years"
    unfavorable:
      description: >
        Indefinite term, perpetual obligations, survival tied to indefinite period.
      exemplars:
        - "Confidentiality obligations shall survive the termination of this Agreement indefinitely"
        - "The obligations of confidentiality shall continue in perpetuity"
    default_position: "neutral"
```

## 3. Clause-to-Playbook Matching Approaches

### Decision
Use a **two-phase matching** approach:
1. **Heading-based match** (fast path): Match clause by heading keyword (e.g., "Confidentiality") against playbook category descriptors using string/heuristic matching.
2. **Semantic fallback** (SLM-based): If heading match fails (confidence < threshold or no keyword overlap), route the clause text through a lightweight embedding comparison against category exemplars using the AI Gateway's embedding model.

If both phases fail to produce a confident match (>0.5 similarity), the clause is reported as `no-match` with no position guess.

### Rationale
- Heading-based matching covers ~80% of NDA clauses (per the benchmark corpus), making it the efficient fast path.
- The semantic fallback catches clauses with non-standard headings or embedded definitions.
- This avoids routing every clause through an embedding model — the fast path handles the common case with zero model inference.

### Alternatives Considered
- **Full semantic retrieval for every clause**: Rejected — unnecessary model calls for the majority of clauses where heading matching suffices.
- **Regex-only matching**: Rejected — too brittle for varied legal drafting styles.
- **Playbook as a single LLM prompt**: Rejected — the playbook is a data artifact that should be inspectable and editable independently of model behavior. Embedding the playbook in a prompt couples the two.

### Implementation Sketch

```python
def match_clause_to_playbook(
    clause: Clause,
    playbook: Playbook,
    embedder: EmbeddingFunction,
) -> MatchResult:
    # Phase 1: Heading match
    for cat in playbook.categories:
        score = heading_similarity(clause.heading, cat.name, cat.exemplars)
        if score > HEADING_THRESHOLD:
            return MatchResult(category=cat, confidence=score, method="heading")

    # Phase 2: Semantic fallback
    clause_emb = embedder(clause.text)
    best_cat = None
    best_score = 0.0
    for cat in playbook.categories:
        exemplar_embs = [embedder(ex) for ex in cat.exemplars]
        score = max(cosine_sim(clause_emb, e_emb) for e_emb in exemplar_embs)
        if score > best_score:
            best_score = score
            best_cat = cat

    if best_score > SEMANTIC_THRESHOLD:
        return MatchResult(category=best_cat, confidence=best_score, method="semantic")
    return MatchResult(category=None, confidence=0.0, method="no-match")
```

## 4. SLM-First Extraction Strategies [§6.1]

### Decision
The extraction agent defaults to SLM routing (local Ollama slot). QA agent independently configurable via `--qa-model`. Default: both agents use the gateway's default routing (typically the first available local SLM slot).

### Rationale
- SLM-first is a constitutional architecture requirement (§6.1). The default configuration must work on an air-gapped machine with no cloud credentials.
- Independent routing (FR-7) enables the accuracy-vs-speed trade-off: extraction runs fast on a 3B-parameter model, QA runs on a larger model (7B local or cloud GPT-4 class).
- The AI Gateway already supports per-task model routing (C-12–C-18). No new routing infrastructure needed.

### Prompt Design Principles
- **Extraction prompt**: Concise, few-shot with exemplars from the matched playbook category. Instructs the model to output JSON with position, confidence, and citation. The clause text is the primary input; the playbook exemplars provide category context.
- **QA prompt**: Receives the clause text, the extraction output, and the playbook entry. Instructs the model to verify the position assignment and flag disagreements. The QA prompt is more detailed — it enumerates specific checks (does the position match the text? is the category correct? is the confidence appropriate?).

### Token Budget
| Component | Extraction (est.) | QA (est.) |
|-----------|-------------------|-----------|
| System prompt | 200 tokens | 300 tokens |
| Playbook category context | 150 tokens | 150 tokens |
| Clause text (avg NDA clause) | 200 tokens | 200 tokens |
| Extraction output | — | 100 tokens |
| **Total per clause** | **~550 tokens** | **~750 tokens** |

At ~50 clauses per NDA: ~27K tokens for extraction + ~38K tokens for QA = ~65K total per document. On a local SLM at ~30 tok/s: ~36 minutes per document. This exceeds the 30-second target in the spec.

**Mitigation**: The spec's 30-second target assumes concurrent processing (Principle III: "API calls MUST be async and concurrent across playbook questions"). Clauses are processed concurrently, not sequentially. With 4 concurrent slots on a local Ollama instance, per-document wall time drops to ~9 minutes. With cloud models (higher throughput), the 30-second target is achievable.

Ponytail note: start with sequential processing for correctness, add concurrency when the perf target is proven to matter.

## 5. Citation Grounding Techniques

### Decision
Citations are generated by the extraction agent as part of its structured output. The prompt instructs the model to quote the exact clause text that supports the position assignment. The citation is a direct quote (or paraphrase with `[...]` for truncation) from the input clause text.

### Rationale
- Spec requirement Q-6: "Every claim cites its source clause."
- The extraction model receives the clause text as input and the playbook exemplars as context. It can directly quote the relevant portion of the clause text.
- No RAG or retrieval needed — the clause text is already in the model's context window.
- The citation is validated by the QA agent: if QA cannot find the cited text in the original clause, it flags the assessment as uncertain.

### Alternatives Considered
- **Retrieval-augmented citation** (extract spans via an embedding retriever): Rejected — the clause text is short enough to fit in the model's context. RAG adds infrastructure for a problem that doesn't exist at the clause level.
- **Span-level citation** (character offsets into the clause text): Rejected — fragile across model tokenization. A natural language quote is more robust and human-readable.

### Validation by QA Agent
The QA agent receives: (a) the clause text, (b) the extraction output (position, confidence, citations), (c) the playbook entry. Its verification includes:

1. **Citation check**: Does the cited text appear in the original clause? (substring match)
2. **Position check**: Does the clause text support the assigned position, given the playbook entry's exemplars?
3. **Category check**: Does the clause belong to the matched playbook category?
4. **Confidence check**: Is the confidence score appropriate for the clause's ambiguity?

If any check fails, the QA agent outputs a revised position and the assessment is flagged as Amber.

## 6. Memory-Efficient Agent Pipelines

### Decision
Process one clause at a time in the pipeline. Each stage's output is a Pydantic model that is validated, passed to the next stage, and then freed. No in-memory accumulation of all clause assessments before formatting.

### Rationale
- Constitution Principle III: <100 MB peak memory. Processing all clauses in memory before output would violate this for batch review.
- Streaming pattern: `stream_clauses()` yields one clause at a time (C-08). The review pipeline consumes the stream: for each clause → extraction → QA → comparison → append to assessments list (bounded).
- The assessments list is the only accumulated structure. For a 50-clause NDA, each assessment is ~500 bytes → ~25 KB total. Well within budget.
- Heavy imports (litellm, prompt-templating) are already loaded by the AI Gateway at session start. The review package adds no new heavy imports.

### Memory Profile (Estimated)

| Component | Memory | Notes |
|-----------|--------|-------|
| AI Gateway (loaded) | ~15 MB | Already resident |
| stream_clauses() | ~2 MB | Page-by-page, clause-by-clause |
| Extraction per clause | ~200 KB | Prompt + response (transient) |
| QA per clause | ~300 KB | Prompt + response (transient) |
| Report accumulator | ~50 KB | 50 clauses × ~1 KB each |
| Python runtime overhead | ~30 MB | Interpreter + stdlib |
| **Total (ex-SLM model)** | **~48 MB** | Within 100 MB budget |

### Async Concurrency
- Clause processing is async: each clause fires extraction → QA → comparison as a coroutine.
- For concurrent processing: a `asyncio.Semaphore` bounds the number of in-flight clauses (default: 4 for local SLMs, higher for cloud).
- Progress display (rich progress bar) updates per-clause completion.

## 7. Research Grounding — Verified Sources

The following sources inform the above decisions. Sources marked CONFIRMED are from the project's own codebase, which is the primary reference for architectural compatibility.

| Item | Source | Status |
|------|--------|--------|
| AI Gateway routing (C-12–C-18) | `src/openreview_cli/gateway/router.py` | CONFIRMED |
| stream_clauses() (C-08) | `src/openreview_cli/parsing/stream.py` | CONFIRMED |
| pyyaml dependency | `pyproject.toml` | CONFIRMED |
| PII stripping pipeline | `src/openreview_cli/pii/` | CONFIRMED |
| Prompt registry (N-1 / spec 009) | `specs/009-prompt-registry/` | CONFIRMED |
| RCTS chunking (C-32) | `specs/007-hierarchical-chunking/` | CONFIRMED |
| PAKTON architecture (P-13, §6.7) | Product design — `products/openreview/` | CONFIRMED (from spec references) |
| 3-position playbook design (C-22, §6.5) | Product design — `products/openreview/` | CONFIRMED (from spec references) |
| SLM-first architecture (§6.1) | Product design — `products/openreview/` | CONFIRMED (from spec references) |
| Local Ollama model performance (~30 tok/s on 3B) | Common knowledge — Ollama benchmarks | UNVERIFIED — perf testing planned; use as rough estimate only |
