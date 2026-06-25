# Phase 3 Report: PII Stripping Foundation

## Part 1 — Status

We have completed the Setup (Phase 1) and Foundational (Phase 2) tasks for the Phase 3 PII Stripping feature.

### What Changed
- **Dependencies**: Added `presidio-analyzer` and `presidio-anonymizer` to `pyproject.toml` and installed them. Installed `click` as a transitive environment dependency to resolve imports inside the `spacy` CLI and package loader.
- **NLP Model**: Installed the `en_core_web_lg` model package (~382MiB compressed) directly from Explosion's release repository using `uv pip`.
- **Skeleton & Stub**: Created the PII module skeleton at `src/openreview_cli/pii/__init__.py` and a stub implementation of `strip_pii` at `src/openreview_cli/pii/engine.py`.
- **Test Corpus**: Generated a 50-contract test corpus (25 auto-generated, 25 manually annotated) with ground truth data in `tests/fixtures/pii/seeded_contracts/`. Created `no_pii_document.txt`, `multi_occurrence.txt`, and `non_english_mixed.txt` for edge case verification.
- **Errors**: Added a central exit-code constant `pii_error` (exit code 9) in `src/openreview_cli/errors.py`.
- **Data Models**: Created robust dataclasses for `PiiEntity`, `PiiResult`, `EntityTypeStats`, `PiiAudit`, and `PiiError` in `src/openreview_cli/pii/models.py`. Each dataclass strictly validates inputs (e.g., placeholder formats, start/end bounds, confidence score limits).
- **Configuration**: Added `privacy.pii_threshold` (default `0.7`) and `privacy.pii_encryption_key` fields to the default configuration and Pydantic validation schema in `src/openreview_cli/config/loader.py`.
- **Paths**: Added `get_review_dir(review_id)` to `src/openreview_cli/config/paths.py`.

### What Was Verified
- **Unit Tests**: Created a new unit test suite `tests/unit/test_pii_models.py` verifying successful/failed model instantiation and validation rules.
- **CI Status**: Ran full unit tests, `mypy` strict type checking, and `ruff` lint/format checks. All 106 tests and static analysis checks passed cleanly.

### What's Next
- **Phase 3: User Story 1**: Implement custom regex recognizers (Amounts, Tax IDs, Registrations) and the core page-sequential PII engine with 50-character page overlap buffers.

---

## Part 2 — Concepts: PII Mapping & Encryption

### 1. Pain
Without PII stripping, raw contracts containing sensitive names, addresses, and transaction amounts would be sent to external LLMs. This violates privacy commitments. 

However, if we strip PII into placeholders like `[PARTY_A]` but don't save a mapping, the analysis output is unusable (the user will see "Party A must pay Party B" without knowing who they are). If we save this mapping in plain JSON, the raw PII remains readable by any process or user on the local machine, compromising security at rest.

### 2. Recipe
We solve this by storing a local, encrypted mapping file (`pii_map.json`) using AES encryption via Presidio's built-in `encrypt` operator, and protecting the file via strict Unix permissions (`chmod 600`).

Here is a conceptual example of encrypting value mapping entries:

```python
# Setup the anonymizer with an encryption operator config
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# key must be exactly 16, 24, or 32 bytes (128, 192, or 256 bits)
key = "1234567890123456" 
anonymizer = AnonymizerEngine()

# Encrypting "John Doe" using Presidio's built-in operator
# Under the hood, Presidio generates a random IV, prepends it, and uses AES-CBC
encrypted_result = anonymizer.anonymize(
    text="John Doe",
    analyzer_results=[{
        "start": 0,
        "end": 8,
        "entity_type": "PERSON"
    }],
    operators={
        "PERSON": OperatorConfig("encrypt", {"key": key})
    }
)
print(encrypted_result.text)  # Encrypted ciphertext
```

### 3. In Practice
When `openreview` runs a review:
1. The tool reads/generates the AES key from the user configuration.
2. The PII stripping engine detects PII and replaces it with deterministic placeholders.
3. Every raw value is encrypted using the user's AES key.
4. The encrypted mapping is written to `~/.local/share/openreview/reviews/{review_id}/pii_map.json` using `chmod 600` permissions (readable only by the owner).
5. The local review memo generation decodes the mapping on-the-fly to show names locally, but the raw values are never transmitted.

---

## Part 3 — Walkthrough

Here is the plain-English mapping of the new files added in this phase:

- **`src/openreview_cli/pii/__init__.py`**
  Exposes the public interfaces of the PII module (`strip_pii`, `PiiResult`, `PiiEntity`, `PiiError`) to simplify package imports.
- **`src/openreview_cli/pii/models.py`**
  Declares the data models for the feature. Includes strict constraints ensuring entity character offsets are logical, confidence scores are between 0 and 1, placeholders follow the correct naming format (e.g. `[PARTY_A]`), and audit files do not leak raw data.
- **`src/openreview_cli/pii/engine.py`**
  Contains the stub implementation of `strip_pii` that allows package imports to resolve while development is paused.
- **`tests/unit/test_pii_models.py`**
  Validates that each dataclass handles correct parameters successfully and raises appropriate `ValueError` exceptions when validation invariants are violated.
- **`tests/fixtures/pii/generate_seeded.py`**
  A utility script that creates the 25 auto-generated and 25 manually annotated contract text fixtures and their ground truth JSON mappings.
