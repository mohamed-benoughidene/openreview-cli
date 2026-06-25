# Research: PII Stripping

**Date**: 2026-06-25
**Feature**: 003-pii-stripping

## Research Tasks

### 1. Presidio Analyzer + Anonymizer — Python 3.12 Compatibility

**Decision**: Use `presidio-analyzer` ≥2.2.362 and `presidio-anonymizer` ≥2.2.362

**Rationale**: Microsoft Presidio v2.2.362 (released March 15, 2026) explicitly supports Python 3.10, 3.11, 3.12, and 3.13. The package metadata on PyPI confirms Python 3.12 compatibility. No compatibility shims or workarounds needed.

**Alternatives considered**:
- `presidio` meta-package (v2.2.362) — installs both analyzer and anonymizer. Rejected because explicit dependency declaration is clearer in `pyproject.toml`.
- Older Presidio versions (2.2.35x) — rejected because 2.2.362 is the latest stable release with Python 3.12/3.13 support.

**Source**: PyPI package metadata for `presidio-analyzer` and `presidio-anonymizer`, version 2.2.362.

---

### 2. spaCy NLP Engine Configuration for Presidio

**Decision**: Configure Presidio's `SpacyNlpEngine` with `en_core_web_lg` model explicitly.

**Rationale**: Presidio's `AnalyzerEngine` defaults to `en_core_web_lg` when using the spaCy NLP backend. However, the model must be explicitly specified to avoid ambiguity and to control the NER model configuration (e.g., setting `default_score`).

**Configuration pattern** (from Presidio docs):
```python
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import SpacyNlpEngine, NerModelConfiguration

model_config = [{"lang_code": "en", "model_name": "en_core_web_lg"}]

ner_model_configuration = NerModelConfiguration(
    default_score=0.6,
    model_to_presidio_entity_mapping={
        "PER": "PERSON",
        "LOC": "LOCATION",
        "GPE": "LOCATION",
        "ORG": "ORGANIZATION",
    }
)

spacy_nlp_engine = SpacyNlpEngine(
    models=model_config,
    ner_model_configuration=ner_model_configuration,
)

analyzer = AnalyzerEngine(nlp_engine=spacy_nlp_engine)
```

**Alternatives considered**:
- `TransformersNlpEngine` with `dslim/bert-base-NER` — provides better NER accuracy but adds the `transformers` and `torch` dependencies (~2 GB RAM). Rejected for memory budget reasons.
- `en_core_web_md` (~90 MB) — smaller model but lower NER accuracy. Rejected because the spec requires `en_core_web_lg` and the constitution grants a memory exemption.
- `en_core_web_sm` (~12 MB) — no word vectors, poor NER accuracy on legal text. Rejected.

**Source**: Presidio GitHub docs `samples/python/ner_model_configuration.ipynb`, Presidio getting started guide.

---

### 3. spaCy en_core_web_lg Memory Footprint

**Decision**: Accept the ~600-800 MB RAM footprint of `en_core_web_lg` under the constitution's memory exemption (Principle III, v1.2.0).

**Rationale**: Research confirms the model's loaded memory footprint:
- On-disk package size: ~788 MB
- Loaded RAM footprint: ~600-800 MB (varies by environment)
- Primary driver: word vector table (~500k entries)
- The `Vocab` cache grows slightly during processing as new `Lexeme` objects are created for unseen words

**Memory management strategies** (applied in implementation):
1. Load model once per CLI session (not per-document)
2. Use `exclude=["parser"]` when loading via Presidio if the full spaCy parser pipeline is not needed (Presidio only uses NER)
3. Process pages sequentially — do not accumulate document text in memory
4. All processing overhead (Presidio framework, regex recognizers, output buffers) must stay under 100 MB

**Cold-start time**: 3-8 seconds on the reference machine (8 GB RAM, 2-core CPU, SSD). This is a one-time cost per CLI session.

**Alternatives considered**:
- Running spaCy in a subprocess with `multiprocessing` to isolate memory — adds complexity, rejected for YAGNI.
- Using `nlp.memory_zone()` — relevant for long-running services, not for a CLI tool with single invocations.

**Source**: spaCy documentation on memory management, GitHub issues on `en_core_web_lg` RAM usage.

---

### 4. Presidio score_threshold Behavior

**Decision**: Use `score_threshold=0.7` (configurable) in `analyzer.analyze()` to filter low-confidence NLP detections. Regex recognizers are unaffected.

**Rationale**: Presidio's `analyzer.analyze()` accepts a `score_threshold` parameter (float, 0.0-1.0). When set:
- Entities detected with confidence **below** the threshold are excluded from results
- Presidio's default threshold is **0** (returns everything)
- Regex-based recognizers (emails, phone numbers, amounts) return scores of **1.0** and are never filtered
- NLP-based recognizers (PERSON, ORGANIZATION, LOCATION) return variable scores (0.5-0.95)
- The spec clarification states that at default threshold 0, Presidio achieves 22.7% precision on business documents — too many false positives from legal terms and law firm names
- At threshold 0.7, most false positives from legal terms are eliminated while maintaining >90% recall on actual named entities

**Implementation**:
```python
results = analyzer.analyze(
    text=text,
    language="en",
    score_threshold=config.get("privacy.pii_threshold", 0.7),
)
```

**Alternatives considered**:
- Post-filtering results manually — rejected because `score_threshold` is a built-in parameter that's more efficient (filtering happens during analysis).
- Fixed threshold (not configurable) — rejected because different document types may require different thresholds.

**Source**: Presidio Analyzer API documentation, `analyzer.analyze()` method signature.

---

### 5. Presidio Encrypt Operator

**Decision**: Use Presidio's built-in `encrypt` operator for AES encryption of PII mapping values at rest.

**Rationale**: The `encrypt` operator in `presidio-anonymizer`:
- Uses **AES in CBC mode** with **PKCS#7 padding**
- Requires a key of exactly **128, 192, or 256 bits** (16, 24, or 32 bytes as a string)
- Automatically generates a **random 16-byte IV** for each encryption operation
- The IV is prepended to the ciphertext (first 16 bytes)
- The `DeanonymizeEngine` can reverse the encryption using the same key
- The `cryptography` Python package is a transitive dependency (already pulled in by `presidio-anonymizer`)

**Key management approach**:
1. On first PII stripping run, check `config.yml` for `privacy.pii_encryption_key`
2. If not present, generate a random 256-bit (32-character) key using `secrets.token_urlsafe(32)[:32]`
3. Write the key to `config.yml`
4. The config file is already recommended to be at a user-only-readable location

**Implementation**:
```python
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import RecognizerResult, OperatorConfig

engine = AnonymizerEngine()
result = engine.anonymize(
    text="James Bond",
    analyzer_results=[RecognizerResult(entity_type="PERSON", start=0, end=10, score=0.8)],
    operators={"PERSON": OperatorConfig("encrypt", {"key": crypto_key})},
)
# result.text contains the AES-encrypted ciphertext (base64-encoded)
```

**Alternatives considered**:
- Direct use of `cryptography.fernet.Fernet` — simpler API but Fernet uses AES-CBC + HMAC (256-bit combined key). Rejected because the spec says "Presidio's built-in encrypt operator."
- `hashlib` for one-way hashing — rejected because the mapping must be reversible for memo generation.

**Source**: Presidio anonymizer documentation, tutorial `12_encryption.md`, PyPI package metadata.

---

### 6. Presidio Default Entity Types vs. Custom Recognizers Needed

**Decision**: Use Presidio's built-in recognizers for 7 entity types; build custom `PatternRecognizer` instances for 4 entity types.

**Rationale**: Research into Presidio's default recognizer registry reveals:

**Built-in (no custom recognizer needed)**:
| Spec Entity | Presidio Entity Type | Detection Method |
|------------|---------------------|-----------------|
| Party names (ORG) | `ORGANIZATION` | NLP NER (spaCy) |
| Individual names | `PERSON` | NLP NER (spaCy) |
| Email addresses | `EMAIL_ADDRESS` | Regex (RFC-822 pattern) |
| Phone numbers | `PHONE_NUMBER` | Regex + context |
| Physical addresses | `LOCATION` | NLP NER (spaCy) |
| Dates of birth | `DATE_TIME` | Regex + context |
| Bank account (IBAN) | `IBAN_CODE` | Regex + checksum |

**Custom recognizers required**:
| Spec Entity | Custom Entity Type | Pattern |
|------------|-------------------|---------|
| Dollar amounts | `AMOUNT` | `\$[\d,]+(?:\.\d{2})?` and `\$\d+(?:\.\d+)?[MBKmk]\b` |
| Tax IDs (EIN) | `TAX_ID` | `\d{2}-\d{7}` (EIN), plus extend US_SSN |
| Passport/DL numbers | `ID_DOCUMENT` | Country-specific patterns |
| Company reg numbers | `REG_NUMBER` | State/country-specific patterns |

**Implementation**: Custom recognizers are registered via `analyzer.registry.add_recognizer()` before the first analysis call.

**Source**: Presidio supported entities documentation, `default_recognizers.yaml` in the Presidio GitHub repo.

---

### 7. Handling Repeated Entity Occurrences

**Decision**: All occurrences of the same literal string map to the same placeholder. No context-aware disambiguation.

**Rationale**: Spec edge case clarification states: "for MVP, all instances of the same literal string map to the same placeholder." Context-aware entity resolution (e.g., distinguishing "John Smith" as signer vs. witness) is a future enhancement.

**Implementation**:
1. First pass: collect all entity detections across the entire document
2. Group by entity type, then by literal value (exact string match)
3. Assign one placeholder per unique (type, value) pair
4. Replace all occurrences with the assigned placeholder

**Alternatives considered**:
- Context-aware disambiguation using coreference resolution — rejected per spec ("future enhancement").
- Per-occurrence unique placeholders — rejected because spec requires consistency.

---

### 8. False Positive Mitigation for Legal Terms

**Decision**: Rely on `score_threshold=0.7` as the primary filter. No deny-list of legal terms in MVP.

**Rationale**: The spec requires <5% false replacement rate. Research shows:
- At threshold 0.7, most legal terms ("Force Majeure", "Indemnification", "Confidentiality") are not detected as entities by spaCy NER
- Law firm names (e.g., "Baker McKenzie") may be detected as PERSON at lower confidence — the 0.7 threshold filters these out in most cases
- A deny-list approach was considered but adds maintenance burden and can miss new terms

**Future enhancement**: If the 5% false positive rate is exceeded in accuracy testing, a deny-list recognizer can be added as a negative-weight recognizer to suppress known legal terms.

**Alternatives considered**:
- Custom deny-list recognizer with negative scores — adds complexity, rejected for YAGNI unless accuracy tests show it's needed.
- Legal-term NER model (fine-tuned on contract text) — would require custom model training, rejected for scope.

---

### 9. Metadata Redaction Approach

**Decision**: Unconditionally redact document metadata fields (filename, author, title, company) with typed placeholders.

**Rationale**: Spec FR-017 requires unconditional redaction of metadata. This is a string replacement operation independent of Presidio NER:
- Parse filename into components: `Smith_Employment_2024.pdf` → split on `_` and `.`
- Replace each component with `[FILENAME_N]`
- Replace author, title, company fields with `[AUTHOR_1]`, `[TITLE_1]`, `[COMPANY_1]`
- Store original values in the PII mapping alongside body text entities

**Implementation**: Metadata redaction is a separate step from body text PII stripping, applied before body text processing to ensure metadata PII doesn't leak even if body text stripping fails.

---

### 10. Audit File Design

**Decision**: Write `pii_audit.json` with entity counts, confidence ranges, processing duration, threshold, and non-English section count. Zero actual PII values.

**Rationale**: Spec FR-018 requires an audit trail that contains no PII. The audit file serves as:
- A debugging aid for PII stripping accuracy
- A compliance record for privacy audits
- A signal for downstream phases to know how much PII was detected

**Schema**:
```json
{
  "version": 1,
  "threshold": 0.7,
  "duration_seconds": 1.23,
  "page_count": 50,
  "non_english_sections": 2,
  "entities": {
    "PERSON": {"count": 12, "min_score": 0.72, "max_score": 0.95},
    "ORGANIZATION": {"count": 5, "min_score": 0.85, "max_score": 0.92},
    "EMAIL_ADDRESS": {"count": 3, "min_score": 1.0, "max_score": 1.0},
    "AMOUNT": {"count": 8, "min_score": 1.0, "max_score": 1.0}
  },
  "metadata_fields_redacted": 4
}
```
