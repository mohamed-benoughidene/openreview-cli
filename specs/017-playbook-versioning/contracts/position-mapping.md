# Contract: Position Name Mapping

**Phase**: 1 — Contracts
**Date**: 2026-07-03

## Purpose

Define the bi-directional position name mapping that happens at playbook load time. This contract governs how YAML position names are mapped to the internal `Position3` enum.

## Load-Time Mapping Function

Signature (Python):
```python
def map_position_name(key: str) -> str:
    """Map YAML position key to internal Position3 value.
    
    Args:
        key: One of 'favorable', 'neutral', 'unfavorable', 
             'preferred', 'acceptable', 'walkaway'
    
    Returns:
        One of 'preferred', 'acceptable', 'walkaway'
    
    Raises:
        ValueError: If key is not a recognized position name
    """
```

## Mapping Table

| YAML input (key) | Internal Position3 | Category |
|------------------|-------------------|----------|
| `favorable` | `preferred` | Old → new |
| `neutral` | `acceptable` | Old → new |
| `unfavorable` | `walkaway` | Old → new |
| `preferred` | `preferred` | New (passthrough) |
| `acceptable` | `acceptable` | New (passthrough) |
| `walkaway` | `walkaway` | New (passthrough) |
| `default_position: favorable` | `default_position: acceptable` | Old default → new |
| `default_position: neutral` | `default_position: acceptable` | Old default → new |
| `default_position: unfavorable` | `default_position: walkaway` | Old default → new |
| `default_position: preferred` | `default_position: preferred` | New (passthrough) |
| `default_position: acceptable` | `default_position: acceptable` | New (passthrough) |
| `default_position: walkaway` | `default_position: walkaway` | New (passthrough) |

## YAML Schema Validation

### Accepted YAML (old naming — backward compatible)
```yaml
categories:
  - name: "confidentiality"
    description: "Confidentiality obligations"
    favorable:
      description: "..."
      exemplars:
        - "mutual confidentiality"
    neutral:
      description: "..."
      exemplars: []
    unfavorable:
      description: "..."
      exemplars:
        - "unilateral confidentiality"
    default_position: "favorable"
```

### Accepted YAML (new naming)
```yaml
categories:
  - name: "confidentiality"
    description: "Confidentiality obligations"
    preferred:
      description: "..."
      exemplars:
        - "mutual confidentiality"
    acceptable:
      description: "..."
      exemplars: []
    walkaway:
      description: "..."
      exemplars:
        - "unilateral confidentiality"
    default_position: "preferred"
```

### Rejected YAML (invalid position names)
```yaml
categories:
  - name: "confidentiality"
    good:        # INVALID — not a recognized position name
      exemplars: []
    bad:         # INVALID — not a recognized position name
      exemplars: []
```

## Implementation Notes

- The mapping is applied at parse time in `playbook.py`, **before** `Playbook` dataclass construction
- The internal `Position3` enum has only four values: `preferred`, `acceptable`, `walkaway`, `uncertain`
- The `uncertain` value is never produced by YAML parsing — it is assigned by the pipeline
- The mapping is pure (no IO, no DB access) — a simple dict lookup
- No validation errors for old names — they are valid input that maps to new values

## Citations

- **§6.4**: 3-position framework — Preferred/Acceptable/Walkaway + Amber (uncertain)
- **FR-8**: Position naming backward compatibility
- **Assumption 2**: Position naming is a vocabulary change, not a semantic change
