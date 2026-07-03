# Research Findings: Citation Grounding Discriminator (N-5)

**Date**: 2026-07-03 | **Spec**: `specs/012-citation-grounding/spec.md`

---

## R1: CG-DPO adaptation from court citations to contract clauses

**Decision**: Adapt P-6's four corruption strategies from court citations to contract clauses.

**Rationale**: P-6 (DPO-based discriminator) achieves 98.5% discrimination accuracy in the legal citation domain. Contract clauses share structural properties with court citations: hierarchical ID numbering (e.g., `4.3` vs. `(a)(1)`), text content, and document-relative references. The adaptation requires only surface-level mapping of corruption strategy mechanics, not a fundamentally different approach.

**Corruption strategies adapted from P-6**:

| P-6 Strategy | Contract Adaptation | Description |
|---|---|---|
| `citation_swap` | `clause_swap` | Replace clause ID in a claim with a different clause ID from the same document |
| `category_swap` | `category_swap` | Replace the playbook category label while keeping clause text unchanged |
| `hallucination` | `hallucination` | Generate a claim with no support in any clause of the source document |
| `anachronism` | `anachronism` | Cite a non-existent clause ID (e.g., v99.99) or a clause from a different document version |

**Alternatives considered**:
- Building a custom BERT-based classifier for binary grounded/ungrounded classification — rejected. Would require training pipeline, labeled dataset, and a new model loaded locally (~500 MB), exceeding the 100 MB memory budget and introducing a new dependency (transformers).
- Pure lexical overlap (TF-IDF + Jaccard similarity) — rejected. Cannot reach 98.5% accuracy; contracts use variable phrasing where same meaning maps to different surface forms.
- Custom ONNX classifier — rejected. Same dependency problem as BERT; ONNX runtime is a new dep and still requires a model file.

**Reference**: P-6 discrimination methodology, Section 3.2 (Corruption Strategies). CONFIRMED — documented in `.specify/memory/verified-sources.md`.

---

## R2: LLM-based grounding via Gateway

**Decision**: Use the existing AI Gateway chat endpoint for grounding discrimination.

**Rationale**: Zero new runtime dependencies. Reuses existing cost tracking (per-token pricing), model routing, and retry/error handling. Fits the 100 MB memory budget because no local model is loaded — the LLM runs on the provider side.

**Prompt design**: The discriminator sends a batch of 5-10 claims per LLM call with a structured prompt:

```
Given the following source document clauses and assessment claims, determine for each claim whether the cited clause supports the claim.

Source clause text: [...]
Claims:
  1. "Claim text..." (cites clause 4.3)
  2. "Claim text..." (cites clause 7.1)
  ...

For each claim, respond with: GROUNDED | UNGROUNDED | UNCERTAIN, plus confidence (0.0-1.0), and matching clause_id(s).
```

**Batching strategy**: Group 5-10 claims per prompt to amortize per-call latency. Total processing time for 100 claims: ~10-20 gateway calls × ~2-3s per call = ~20-60s, within the 60s target.

**Alternatives considered**:
- ONNX classifier — rejected (new dependency, no training data for contract-specific grounding).
- Local embedding similarity (sentence-transformers) — rejected. `sentence-transformers` is on the forbidden dependencies list (Constitution §IV).
- Pure regex-based matching — rejected. Cannot handle paraphrased or semantically equivalent claims (98.5% target impossible with regex).

**Reference**: AI Gateway architecture, `src/openreview_cli/gateway/router.py`. CONFIRMED — existing, tested, used in spec 011 extraction/QA pipeline.

---

## R3: Structural CG metrics for contracts

**Decision**: Compute CP (Citation Precision), CR (Citation Relevance), and CL (Citation Locality) via deterministic string and index operations.

**Metric definitions**:

- **CP (Citation Precision)**: `count(claims where cited clause_id exists in Document) / total_grounded_claims`. Pure existence check against parsed document clause list. O(1) per claim via hash lookup.
- **CR (Citation Relevance)**: `count(claims where claim text substring appears in cited clause text) / total_grounded_claims`. Substring match (case-insensitive) against the full text of the cited clause. Ponytail: simple `in` operator; semantic relevance deferred.
- **CL (Citation Locality)**: `avg(paragraph_index_exists(claim) for all grounded claims)`. Each claim's `paragraph_index` is checked against the cited clause's paragraph count. Returns 1.0 if all paragraph indices are valid, <1.0 if any exceed the clause length.

**Rationale**: All three metrics are O(n) deterministic operations — no LLM calls, no embeddings. Latency <1ms per claim. Sufficient for v1 baseline. The spec explicitly notes these are "structural" metrics (not semantic).

**Alternatives considered**:
- Embedding cosine similarity for CR — rejected. Requires `sentence-transformers` (forbidden dep) or a Gateway embedding call per claim (prohibitive cost).
- BERTScore for CR — rejected. Requires `transformers` (new dep, local model load).

**Reference**: Spec §FR-005, blueprints P-6, T-7. CONFIRMED — deterministic metrics explicitly specified.

---

## R4: Integration with existing hallucination detection

**Decision**: Create `HallucinationDetector` ABC and implement `CGDPODetector` and `LexicalOverlapDetector` classes in `benchmark/hallu_detect.py`.

**Rationale**: The spec 010 benchmark harness transition plan (AGENTS.md) references a swappable `HallucinationDetector` interface with CLI flag `--hallucination-method=lexical|cg-dpo`, but this interface does not yet exist in code — `hallu_detect.py` currently only exports standalone functions (`detect_lexical()`, `detect_hallucinations()`). This spec creates the ABC and refactors the existing logic into two concrete implementations:

```python
from abc import ABC, abstractmethod

class HallucinationDetector(ABC):
    @abstractmethod
    def detect(self, claims: list[str], sources: list[str]) -> list[bool]: ...
```

The existing `LexicalOverlapDetector` wraps the current lexical overlap logic as the placeholder default. The new `CGDPODetector` fills the second slot, using the grounding discriminator's verdicts instead of lexical overlap.

**Interface alignment**:
- `detect()` returns `list[bool]` — `True` if grounded (no hallucination), `False` if ungrounded (hallucination detected).
- `CGDPODetector` wraps `CitationGroundingDiscriminator.ground_report()` and maps verdicts: GROUNDED → `True`, UNGROUNDED → `False`, UNCERTAIN → `False` (conservative, default ungrounded per R-9).
- No changes to the `HallucinationDetector` interface. No breaking changes to the benchmark harness.

**Transition plan** (from AGENTS.md):
- Default stays `lexical` until C-21 (CG-DPO) reaches TRL 7+
- Once CG-DPO is stable, default flips to `cg-dpo`, `lexical` becomes legacy
- Reports show which method was used; historical baselines remain comparable

**Reference**: AGENTS.md (Hallucination Detection — Transition Plan), `src/openreview_cli/benchmark/hallu_detect.py`. **NOTE**: Interface does NOT exist yet — `hallu_detect.py` has only standalone functions. Creating the ABC and refactoring existing functions into `LexicalOverlapDetector` and `CGDPODetector` is part of this spec (T019b). The transition plan in AGENTS.md documents the intended interface and CLI wiring.

---

## UNVERIFIED Claims

No unverified claims. All research findings reference CONFIRMED sources from `.specify/memory/verified-sources.md`.
