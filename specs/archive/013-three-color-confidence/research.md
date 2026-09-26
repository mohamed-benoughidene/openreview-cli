# Research: Three-Color Output with Confidence Scores

**Spec**: 013 — Three-Color Output with Confidence Scores
**Date**: 2026-07-03

---

## R1: Three-Color Output Patterns in Legal Tech

**Question**: What is the established UX pattern for displaying assessment confidence in legal document review tools?

### Findings

The traffic-light model (Green/Amber/Red) is the de facto standard across legal technology:

- **Kira Systems, Luminance, eBrevia, LawGeex**: All use Green-Amber-Red (or equivalent checkmark-warning-cross) to indicate clause risk. The pattern matches the mental model of "stoplight" that legal professionals use in manual review.
- **Amber as escape hatch**: In every major platform, Amber ("requires human review") is the most important signal — it is where the system concedes uncertainty rather than making a false high-confidence prediction.
- **Binary (pass/fail) limitations**: Binary output forces the user into a false dichotomy. Legal review requires a middle state because automated comparison accuracy has a known ceiling (cite §6.4: ~64% F1). Amber is the mitigation for that ceiling.

### Decision

Use a three-state `AssessmentColor` enum (Green/Amber/Red). Do not extend to four states — §6.4 explicitly calls for three-color output and neutral + high confidence maps to Green (FR-011). This matches the legal-tech industry standard and the project's own §6.4 requirements.

---

## R2: Confidence Threshold Design

**Question**: Single global threshold vs. per-stage thresholds? What value should the default be?

### Findings

- **Single global threshold**: Simplest UX. One knob the user turns. No cognitive overhead of tuning per-stage thresholds. §6.4 mandates a single `--confidence-threshold` flag.
- **Per-stage thresholds**: More flexible but harder to explain and test. Not warranted until users explicitly ask for it. (YAGNI — Principle V.)
- **Default value**: §6.4 says "set Amber threshold generously." Industry benchmarks for clause classification (LexNLP, LawGeex benchmarks) show optimal F1 at thresholds around 0.6-0.8. 0.7 is generous — meaning it will err on the side of "human review needed" (Amber) rather than false Green/Red. The spec confirms this in FR-012.
- **Range validation**: Any float in [0.0, 1.0] is valid. 0.0 means "all non-erroneous assessments pass" (essentially Amber only on error/QA-disagree). 1.0 means "only assessments with perfect confidence pass" — virtually everything Amber.

### Decision

Single global threshold, float in [0.0, 1.0], default 0.7. CLI accepts via `--confidence-threshold` flag. Typer callback validates the range and rejects out-of-range values with a clear error message.

---

## R3: Confidence Aggregation Strategy

**Question**: How to combine extraction confidence, QA confidence, and grounding confidence into a single "effective confidence"?

### Options Considered

| Strategy | Formula | Behavior |
|----------|---------|----------|
| **Min** (selected) | `min(extraction, qa, grounding)` | Most conservative. Any low-confidence stage → low effective confidence → Amber. |
| Weighted average | `w1*ext + w2*qa + w3*gnd` | Requires tuning weights. Can mask a single failed stage if other stages are high. |
| Product | `ext * qa * gnd` | Punishes multiple moderate confidences very hard (0.8 * 0.8 * 0.8 = 0.51). Too aggressive. |
| Max | `max(extraction, qa, grounding)` | Too permissive. Hides failures. |

### Decision

Use **min()** across available stages. Missing stages default to 1.0 (no penalty). The rule:
```
effective_confidence = min(
    extraction_confidence or 1.0,
    qa_confidence or 1.0,
    grounding_confidence or 1.0
)
```

This matches the §6.4 "generous Amber" philosophy — any single stage expressing doubt drives the assessment to Amber. It is trivially correct (a chain is only as strong as its weakest link) and requires no tuning.

---

## R4: CLI Flag Design for Typer

**Question**: How to expose `--confidence-threshold` on review-producing subcommands in a Typer app?

### Findings

- **Typer Option pattern**: `typer.Option(default, help=..., min=..., max=..., clamp=...)` — built-in validation.
- **Per-command flag**: Each review subcommand (`precheck`, `hirecheck`, etc.) gets its own `--confidence-threshold` flag. The flag is on the command, not the app — this matches FR-013 ("per-command with shared default").
- **Shared default constant**: Define `DEFAULT_CONFIDENCE_THRESHOLD = 0.7` in one place (e.g., `review/__init__.py` or `app.py` — ponytail: put it where it's first used, `app.py`). Each command imports and uses it.
- **Help text**: Must include the accuracy ceiling disclosure (FR-008) — that text belongs in the `help=` parameter of `typer.Option()`.
- **Backward compat**: Commands that don't accept the flag (non-review commands) remain unchanged.

### Typer Code Pattern

```python
import typer
from openreview_cli.app import DEFAULT_CONFIDENCE_THRESHOLD

def _validate_threshold(value: float) -> float:
    if not 0.0 <= value <= 1.0:
        raise typer.BadParameter(f"confidence-threshold must be between 0.0 and 1.0, got {value}")
    return value

@review_app.command("precheck")
def precheck_review(
    ...,
    confidence_threshold: float = typer.Option(
        DEFAULT_CONFIDENCE_THRESHOLD,
        "--confidence-threshold",
        help="Confidence threshold for Green/Amber/Red assignment "
             "(0.0-1.0). Note: The comparison accuracy of automated review "
             "is bounded by approximately 64% F1. Three-color output "
             "(Green/Amber/Red) is designed to mitigate this — set the "
             "threshold generously to push uncertain comparisons to Amber "
             "rather than risking false Green or Red.",
        min=0.0,
        max=1.0,
        callback=_validate_threshold,
    ),
):
    ...
```

### Decision

Per-command flag using standard Typer `Option` with `min`/`max` constraint and a callback for custom validation. Default value from a shared constant. Help text includes the §6.4/CON-1 accuracy ceiling disclosure.
