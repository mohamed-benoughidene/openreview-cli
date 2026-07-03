# CLI Contract: Citation Grounding Discriminator (N-5)

**Date**: 2026-07-03 | **Spec**: `specs/012-citation-grounding/spec.md`

---

## CLI Contract — `openreview precheck` with grounding

The existing `precheck` command gains grounding integration:

- **Grounding runs automatically** after QA in the review pipeline. No separate command needed.
- **New flag**: `--grounding-mode=strict|lenient` (default: `strict`)
- **New flag**: `--no-grounding` to skip grounding entirely
- **Terminal output**: Grounding verdict column (G/U/?) alongside existing position/confidence table
- **JSON output**: `grounding_verdict`, `grounding_provenances`, `grounding_confidence` per assessment
- **Audit log**: Written to `{output_dir}/grounding-audit.jsonl`

### Usage examples

```bash
# Default — strict mode grounding
openreview precheck contract.pdf --playbook playbooks/precheck-nda-v1.yaml

# Lenient mode — all claims retained, ungrounded flagged
openreview precheck contract.pdf --playbook playbooks/precheck-nda-v1.yaml --grounding-mode=lenient

# Skip grounding entirely
openreview precheck contract.pdf --playbook playbooks/precheck-nda-v1.yaml --no-grounding
```

### Output behavior by mode

| Behavior | Strict (default) | Lenient | No grounding |
|---|---|---|---|
| Ungrounded claims excluded from output | Yes | No | N/A |
| Ungrounded claims visibly flagged | N/A (excluded) | Yes | No |
| Grounding verdict column in table | Yes | Yes | No |
| Grounding fields in JSON | Populated | Populated | null |
| Audit log | Written | Written | Not written |
| Warning for excluded claims | Printed to stderr | None | None |

---

## Public API Contract — `grounding` module

```python
# src/openreview_cli/grounding/__init__.py

def run_grounding(
    report: ReviewReport,
    source_document: Document,
    mode: Literal["strict", "lenient"] = "strict",
    gateway: Gateway | None = None,
    model: str | None = None,
) -> CGReport:
    """Run citation grounding on a ReviewReport.

    Args:
        report: The ReviewReport from single-party review.
        source_document: The parsed source document (for clause text lookup).
        mode: Grounding mode — 'strict' excludes ungrounded, 'lenient' flags only.
        gateway: Optional Gateway instance (defaults to global singleton).
        model: Optional model override (defaults to gateway default).

    Returns:
        CGReport with per-claim verdicts, provenances, and metrics.

    Skips claims where QA already set citation_valid=False.
    """
    ...
```

### CGReport (return type)

```python
@dataclass
class CGReport:
    verdicts: list[GroundingResult]                  # Per-claim results
    mode: Literal["strict", "lenient"]               # Mode used
    metrics: CGMetrics                               # CP, CR, CL scores
    total_claims: int                                # Total claims received
    grounded_count: int                              # Count of GROUNDED verdicts
    ungrounded_count: int                            # Count of UNGROUNDED verdicts
    uncertain_count: int                             # Count of UNCERTAIN verdicts

    def merge_into(self, report: ReviewReport) -> ReviewReport:
        """Merge grounding results into a ReviewReport, populating ClauseAssessment fields.
        In strict mode, removes UNGROUNDED and UNCERTAIN claims from the report.
        """
        ...
```

### CitationGroundingDiscriminator (internal class)

```python
class CitationGroundingDiscriminator:
    """LLM-based post-hoc discriminator for contract-clause grounding."""

    def __init__(self, mode: str = "strict", gateway: Gateway | None = None, model: str | None = None):
        ...

    def ground_claim(
        self,
        claim_text: str,
        cited_clause_id: str,
        clause_text: str,
    ) -> tuple[GroundingVerdict, list[CitationProvenance], float]:
        """Ground a single claim against a single clause.
        Returns (verdict, provenances, confidence).
        """
        ...

    def ground_report(
        self,
        report: ReviewReport,
        document: Document,
    ) -> CGReport:
        """Ground all claims in a ReviewReport against the source document.
        Skips claims where citation_valid=False.
        """
        ...
```

### GroundingVerdict (enum)

```python
class GroundingVerdict(str, Enum):
    GROUNDED = "grounded"
    UNGROUNDED = "ungrounded"
    UNCERTAIN = "uncertain"
```

---

## HallucinationDetector interface — CGDPODetector

```python
# In src/openreview_cli/benchmark/hallu_detect.py

class CGDPODetector(HallucinationDetector):
    """CG-DPO based hallucination detector using citation grounding discriminator."""

    def __init__(self, mode: str = "strict", ...):
        ...

    def detect(self, claims: list[str], sources: list[str]) -> list[bool]:
        """Returns True (grounded/no-hallucination) or False (ungrounded/hallucination).
        UNCERTAIN verdicts are mapped to False (conservative).
        """
        ...
```
