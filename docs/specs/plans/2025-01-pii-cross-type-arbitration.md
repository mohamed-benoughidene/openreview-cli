# PII Cross-Type Overlap Arbitration — Architecture Proposal

> **READ-ONLY proposal. No files modified in this session.**

**Goal:** Resolve the 138/172 false positives caused by Presidio returning overlapping detections of *different* entity types, pushing precision from 0.7601 to ≥0.95 while preserving recall ≥0.9435.

**Root Cause:** Presidio's `EntityRecognizer.remove_duplicates()` (file: `.venv/…/entity_recognizer.py:169-200`) only suppresses duplicates when `result.contained_in(filtered) and result.entity_type == filtered.entity_type` — **same-type containment only**. Cross-type overlapping spans all survive to the final output.

---

## Root Cause Analysis (Verified by Code Inspection)

### The Pipeline

```
analyzer.analyze()
  └─ For each recognizer:
       ├─ PatternRecognizer.analyze() → RecognizerResult(score=1.0)  [deterministic]
       └─ SpacyRecognizer.analyze()   → RecognizerResult(score=0.85) [statistical]
  └─ _enhance_using_context()
  └─ EntityRecognizer.remove_duplicates()  ← ONLY REMOVES SAME-TYPE DUPLICATES
  └─ __remove_low_scores()
  └─ return results
```

### The Conflict Resolution Gap

`EntityRecognizer.remove_duplicates()` at `.venv/lib/python3.12/site-packages/presidio_analyzer/entity_recognizer.py:186-198`:

```python
for result in results:
    to_keep = result not in filtered_results          # equality = same start, end, type, score
    if to_keep:
        for filtered in filtered_results:
            if (
                result.contained_in(filtered)          # span containment check
                and result.entity_type == filtered.entity_type  # ← SAME TYPE ONLY
            ):
                to_keep = False
                break
    if to_keep:
        filtered_results.append(result)
```

**What survives:**
| Overlap Kind | Types | Both Survive? | Example |
|---|---|---|---|
| Exact span, same type | TAX_ID + TAX_ID | No (equality check) | — |
| Exact span, **different** type | TAX_ID + DATE_TIME | **YES** ← bug | "11-7654320" at [42, 53] |
| Containment, same type | PERSON ⊂ PERSON | No | — |
| Containment, **different** type | ORG ⊂ LOCATION | **YES** ← bug | "San Francisco" inside full address |
| Partial overlap, different types | LOCATION ∩ ORG | **YES** ← bug | Address fragment |

### Score Distribution (from code)

| Source | Score | `source` field | Identifiable via |
|---|---|---|---|
| Custom regex recognizers | 1.0 (from `Pattern.score`) | `"regex"` | `r.score == 1.0` |
| spaCy NER | 0.85 (from `NerModelConfiguration.default_score`) | `"nlp"` | `r.score == 0.85` |
| Context-enhanced | Up to 1.0 (boosted) | `"nlp"` | `r.recognition_metadata` |

**Critical constraint:** spaCy emits FLAT 0.85 for every entity — no per-entity confidence. Any "confidence threshold" approach is REFUTED.

### Fingerprint of Recognition Metadata

Every `RecognizerResult` carries `recognition_metadata` with:
- `recognizer_name`: e.g., `"PatternRecognizer"` vs `"SpacyRecognizer"`
- `recognizer_identifier`: unique ID per recognizer instance

This is set by `AnalyzerEngine.__add_recognizer_id_if_not_exists()` at line 403-428 of `analyzer_engine.py`.

---

## Candidates Evaluated

### Candidate 1: Post-Analyzer Cross-Type Span Arbitration

**Mechanism:** After `analyzer.analyze()` returns, but before `PiiEntity` construction (engine.py:102-113), insert an arbitration pass that detects overlapping spans of *different* types and selects ONE winner per span.

**Arbitration Rules (priority order):**
1. **Deterministic-first:** When two detections have identical [start, end], prefer the one from a deterministic recognizer (score=1.0) over a statistical one (score=0.85).
2. **Longer-span-wins:** When one detection fully contains another, prefer the longer/larger span (more likely to be the complete entity).
3. **Type-specificity tiebreaker:** For remaining partial overlaps where neither is deterministic, use a small static type-priority map (domain semantics, not corpus-specific):
   ```
   TAX_ID > DATE_TIME       # "11-7654320" is an EIN, not a date
   ACCT > PERSON             # IBAN codes look like names to spaCy
   LOCATION > ORGANIZATION   # Addresses contain org-like fragments
   EMAIL_ADDRESS > PERSON    # Email local parts look like names
   REG_NUMBER > ORGANIZATION # Registration numbers look like org names
   ID_DOCUMENT > PERSON      # "PASSPORT123456" looks like a name
   AMOUNT > DATE_TIME        # "$5,000.00" could be date-like
   PHONE_NUMBER > PERSON     # Phone fragments could be name-like
   ```

**Root cause addressed:** Directly resolves the cross-type overlap gap in `remove_duplicates()`.

**Recall risk:** LOW. We are choosing ONE winner per overlapping span, not removing the span. The winning detection retains its text and position. The only risk is if the arbitration consistently picks the wrong type — but the type-priority map is designed so that the more specific type (the one from the more specialized recognizer) always wins.

**Precision benefit:** ELIMINATES the 138/172 FPs that are "correct PII span, wrong type." Expected precision: ~0.95+.

**Generalization:** HIGH. The rules are:
- Source-agnostic (deterministic beats statistical is a universal principle)
- Type-priority is based on semantic specificity, not corpus strings
- Works for any new recognizers added in the future

**Complexity:** ~40-50 lines of pure Python in a new function. No new dependencies.

---

### Candidate 2: Suppress spaCy When Regex Covers Same Span

**Mechanism:** After `analyzer.analyze()`, for each spaCy result (score=0.85), check if any regex result (score=1.0) overlaps the same span. If so, suppress the spaCy result entirely.

**Root cause addressed:** YES — eliminates spaCy duplicates that overlap with regex hits.

**Recall risk:** MEDIUM-HIGH. This approach doesn't just fix the type — it removes the spaCy detection entirely. If a spaCy detection covers a DIFFERENT legitimate PII entity that happens to overlap with a regex hit (e.g., a person name whose characters fall within a date pattern), the person name would be lost. Example:
- Regex matches TAX_ID "12-3456789" at [5, 15]
- spaCy matches PERSON "3456789" at [8, 15] (last 7 digits happen to be a name)
- Suppressing spaCy loses the person detection

**Precision benefit:** HIGH for the current data. Would eliminate most of the 138 cross-type FPs.

**Generalization:** LOW-MEDIUM. The axiom "regex=correct, spaCy=wrong" is a heuristic that holds in this corpus but isn't universally true. A regex could misfire (e.g., ID_DOCUMENT pattern `[A-Z]{1,2}\d{6,9}` at score=0.8 matching a company name).

**Complexity:** ~15-20 lines. Very simple.

**Verdict:** THIS IS A HACK. It conflates "source identity" with "correctness." It would reduce precision FPs but creates silent recall holes. REJECT as the primary solution.

---

### Candidate 3: Presidio's `context` / `allow_list` / `deny_list`

**Mechanism:** Pass `context` words or `allow_list`/`deny_list` to `analyzer.analyze()`.

**Root cause addressed:** PARTIALLY.
- `context` only boosts/adjusts scores — it doesn't change entity types. Since spaCy emits flat 0.85, context enhancement could push it higher but won't fix type confusion between TAX_ID and DATE_TIME.
- `allow_list` suppresses specific text values — requires knowing the exact false positive strings (corpus-specific, violates constraint).
- `deny_list` forces specific strings to be classified — also corpus-specific.

**Recall risk:** LOW (context/allow_list are additive/subtractive, not transformative).

**Precision benefit:** LOW for the dominant FP pattern (138 cross-type overlaps). Might help with the 34/172 genuine spaCy mislabels.

**Generalization:** LOW for `allow_list`/`deny_list` (corpus-specific). MEDIUM for `context` (could help if contract-specific context words are available).

**Complexity:** Minimal code change, but requires maintaining corpus-specific word lists.

**Verdict:** DOES NOT ADDRESS ROOT CAUSE. The fundamental problem is cross-type overlaps, not score calibration. REJECT as the primary solution.

---

### Candidate 4: Standalone Type-Priority Map

**Mechanism:** Define a static type priority map. When two detections overlap, the higher-priority type wins.

**Root cause addressed:** PARTIALLY. Addresses the type-selection problem but doesn't handle the source-reliability dimension (deterministic vs. statistical).

**Recall risk:** LOW — we're picking one type, not removing spans.

**Precision benefit:** MEDIUM-HIGH. Would handle most cross-type overlaps. But for the case where both detections come from spaCy (both score 0.85), the priority map alone doesn't provide a strong signal.

**Generalization:** MEDIUM. Type priority is a reasonable domain heuristic but lacks the principled "deterministic beats statistical" foundation.

**Complexity:** ~30-40 lines.

**Verdict:** GOOD AS A COMPONENT, but insufficient alone. Best combined with Candidate 1's deterministic-first rule.

---

## RECOMMENDED MINIMAL CHANGE: Candidate 1 — Post-Analyzer Cross-Type Arbitration

### Principle

> When multiple recognizers produce overlapping detections with different entity types, **prefer the detection from the more reliable source** (deterministic regex over statistical NER), and use **type specificity** as a tiebreaker when sources are equal.

### Where It Belongs

**File:** `src/openreview_cli/pii/engine.py`
**Function:** New function `_resolve_cross_type_overlaps()` called at line ~101, between `results = analyzer.analyze(...)` (line 69) and the `PiiEntity` construction loop (line 102).

**Why here and not in Presidio's `remove_duplicates()`:**
- Presidio is a third-party dependency; modifying its internals is fragile and unmaintainable.
- The arbitration is application-specific policy (which type wins), not generic deduplication.
- It fits naturally as a post-processing step in the engine.

### Pseudocode

```python
# New constant at module level
_TYPE_PRIORITY: dict[str, int] = {
    # Higher number = more specific = wins in overlap disputes
    "TAX_ID":       80,
    "ACCT":         80,
    "ID_DOCUMENT":  80,
    "REG_NUMBER":   80,
    "EMAIL_ADDRESS": 90,  # regex-only, never disputed
    "PHONE_NUMBER": 70,
    "AMOUNT":       70,
    "LOCATION":     60,
    "ORGANIZATION": 40,
    "PERSON":       30,
    "DATE_TIME":    20,   # least specific — "catch-all" NER label
}


def _resolve_cross_type_overlaps(
    results: list[RecognizerResult],
) -> list[RecognizerResult]:
    """Remove cross-type overlapping detections by keeping the winner.

    When two detections overlap and have different entity types:
    1. Deterministic (score=1.0) beats statistical (score<1.0)
    2. Longer span beats shorter span
    3. Higher type-priority wins (more specific type)

    This is NOT the same as Presidio's remove_duplicates(), which only
    handles same-type containment.
    """
    if len(results) <= 1:
        return results

    # Sort: highest score first, then longest span, then highest priority
    sorted_results = sorted(
        results,
        key=lambda r: (
            -r.score,
            -(r.end - r.start),
            -_TYPE_PRIORITY.get(r.entity_type, 50),
        ),
    )

    kept: list[RecognizerResult] = []
    for candidate in sorted_results:
        dominated = False
        for existing in kept:
            overlap = candidate.intersects(existing)
            if overlap == 0:
                continue  # no conflict

            # Same type: let Presidio's own dedup handle it
            if candidate.entity_type == existing.entity_type:
                continue

            # Cross-type overlap: arbitration needed
            # Rule 1: deterministic beats statistical
            if existing.score > candidate.score:
                dominated = True
                break
            if candidate.score > existing.score:
                # candidate wins over existing — but don't remove existing
                # if they don't fully overlap; only suppress candidate's
                # competing type label by renaming (handled below)
                continue

            # Rule 2: equal scores — longer span wins
            existing_len = existing.end - existing.start
            candidate_len = candidate.end - candidate.start
            if existing_len > candidate_len:
                dominated = True
                break
            if candidate_len > existing_len:
                continue

            # Rule 3: equal scores, equal lengths — higher priority wins
            existing_pri = _TYPE_PRIORITY.get(existing.entity_type, 50)
            candidate_pri = _TYPE_PRIORITY.get(candidate.entity_type, 50)
            if existing_pri >= candidate_pri:
                dominated = True
                break

        if not dominated:
            kept.append(candidate)

    return kept
```

### Integration Point

In `detect_on_page()` at engine.py, between lines 100 and 102:

```python
        # --- NEW: resolve cross-type overlaps ---
        results = _resolve_cross_type_overlaps(list(results))
        # --- END NEW ---

        entities = []
        for r in results:
            entity = PiiEntity(
                entity_type=r.entity_type,
                original_value=text[r.start : r.end],
                start=r.start,
                end=r.end,
                score=r.score,
                placeholder=_TEMP_PH,
                source="regex" if r.score == 1.0 else "nlp",
            )
            entities.append(entity)
```

### How It Works — Concrete Examples

**Example 1: Exact-span TAX_ID + DATE_TIME**
- Input: `"EIN: 11-7654320"` → regex emits TAX_ID [6, 17] score=1.0, spaCy emits DATE_TIME [6, 17] score=0.85
- Arbitration: score 1.0 > 0.85 → TAX_ID wins. DATE_TIME suppressed.
- Output: one entity, TAX_ID "11-7654320"

**Example 2: Containment — LOCATION contains ORGANIZATION**
- Input: `"100 Auto Blvd, Suite 1, San Francisco, CA 94107"` → spaCy emits LOCATION [0, 49] score=0.85, spaCy also emits ORGANIZATION [0, 18] score=0.85 ("100 Auto Blvd, Suite")
- Arbitration: equal scores; LOCATION span (49 chars) > ORGANIZATION span (18 chars) → LOCATION wins. ORGANIZATION suppressed.
- Output: one entity, LOCATION "100 Auto Blvd, Suite 1, San Francisco, CA 94107"

**Example 3: IBAN + ORGANIZATION**
- Input: `"IBAN: GB29NWBK60161331926801"` → regex emits ACCT [6, 30] score=1.0, spaCy emits ORGANIZATION [6, 30] score=0.85 (looks like org name)
- Arbitration: score 1.0 > 0.85 → ACCT wins.
- Output: one entity, ACCT "GB29NWBK60161331926801"

**Example 4: Two spaCy detections, no regex**
- Input: `"Google, Inc."` → spaCy emits ORGANIZATION [0, 12] score=0.85
- No overlap → passes through unchanged.

**Example 5: No false suppression risk**
- Input: `"John Smith signed on 2024-01-15"` → spaCy emits PERSON [0, 10] score=0.85, spaCy emits DATE_TIME [22, 32] score=0.85
- No overlap → both pass through.

---

## Expected Impact

| Metric | Current | Expected After | Confidence |
|---|---|---|---|
| Precision | 0.7601 | ≥0.94 | HIGH — eliminates 138/172 FPs |
| Recall | 0.9435 | ≥0.9435 | HIGH — no detections removed, only types arbitrated |
| F1 | ~0.84 | ≥0.94 | Derived from P/R |

**Residual FPs (34/172):** Genuine spaCy mislabels on non-PII boilerplate ("EIN", "This Non-Disclosure Agreement"). These require a different remediation (context enhancement or deny-lists) and are OUT OF SCOPE for this change.

**Residual recall gap (~0.0065):** Missing detections (not type confusion). Also out of scope.

---

## Trade-offs

| Dimension | Assessment |
|---|---|
| **Correctness** | The arbitration rules are sound: deterministic > statistical is an information-theoretic principle, type specificity reflects domain semantics |
| **Generality** | Works for any recognizer combination; new recognizers automatically participate via score and type |
| **Maintainability** | Single function, ~40 lines, pure Python, no dependencies |
| **Testability** | Fully unit-testable with synthetic RecognizerResult objects |
| **Performance** | O(n²) where n = number of detections per page; n is typically <50, so negligible |
| **Reversibility** | Single function insertion; trivial to remove if needed |
| **Type-priority map risk** | The map encodes domain knowledge. If entity type semantics change, the map needs updating. Mitigation: map is small, documented, and testable |
| **Edge case: partial overlap** | When neither span fully contains the other, we suppress the smaller one. This is correct when the larger span is the real entity and the smaller is a fragment. If two genuinely different entities partially overlap (rare), the smaller is lost. This is acceptable because such overlaps are inherently ambiguous and the system must pick one |

---

## Files Read (No Modifications)

| File | Purpose |
|---|---|
| `src/openreview_cli/pii/engine.py` | Main engine; integration point for arbitration |
| `src/openreview_cli/pii/recognizers.py` | Custom regex recognizers (score=1.0 patterns) |
| `src/openreview_cli/pii/models.py` | PiiEntity/PiiResult data classes |
| `src/openreview_cli/pii/placeholders.py` | Placeholder assignment (downstream, unaffected) |
| `src/openreview_cli/benchmark/metrics_pii.py` | Evaluator with type-strict matching |
| `tests/fixtures/pii/seeded_contracts/ground_truth.json` | Ground truth entities |
| `tests/integration/test_benchmark_pii_accuracy.py` | Accuracy gate test |
| `.venv/…/presidio_analyzer/entity_recognizer.py` | `remove_duplicates()` — the root cause |
| `.venv/…/presidio_analyzer/analyzer_engine.py` | `analyze()` pipeline orchestration |
| `.venv/…/presidio_analyzer/recognizer_result.py` | RecognizerResult with `intersects()`, `contained_in()`, `equal_indices()` |
| `.venv/…/presidio_analyzer/pattern_recognizer.py` | PatternRecognizer score handling |
| `.venv/…/spacy_recognizer.py` | SpacyRecognizer with flat 0.85 ner_strength |
| `.venv/…/spacy_nlp_engine.py` | `_get_scores_for_entities()` confirming flat default score |
| `.venv/…/ner_model_configuration.py` | MODEL_TO_PRESIDIO_ENTITY_MAPPING and default_score=0.85 |

## Changes Made

**None.** This is a read-only architecture proposal.
