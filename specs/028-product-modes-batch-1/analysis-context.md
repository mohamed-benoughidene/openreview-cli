# Analysis Context — Spec 028 Product Modes Batch 1

**Date**: 2026-07-08
**Author**: OpenCode remediation agent
**Status**: Green — implementable after remediation edits

---

## 1. Plan Claims vs. Reality

| Claim | Reality | Status |
|-------|---------|--------|
| Six new modes deploy via playbook + prompt + CLI wiring | True — established pattern from 4 wired modes | **Matches** |
| No new runtime dependencies | True — all deps already in `pyproject.toml` | **Matches** |
| Each mode follows same pipeline (`run_review()`) | True — single-party review pipeline unchanged | **Matches** |
| 6 existing product modes before this batch | **False** — only 4 wired in `app.py`. `dealcheck` and `hirecheck` referenced in data-model.md but un-wired. Scope expansion B closes this gap. | **Mismatch — resolved** |
| FR1 flags match `_register_product_mode` helper | Original spec listed only `--no-pii`, `--output`, `--playbook`, verbosity. Actual helper exposes 8 flags incl. `--format`, `--memo-format`, `--output-dir`, `--confidence-threshold`/`-ct`. | **Mismatch — resolved** |
| Memory budget "<110 MB" | Constitution says "<100 MB peak (110 MB hard floor)". Plan used wrong value. | **Mismatch — resolved** |
| Accuracy baseline "within 5pp of existing" | Unverifiable — no held-out corpus for 6 new domains. Replaced with measurable criterion. | **Mismatch — resolved** |

---

## 2. Dependencies

### Runtime (all pre-existing, no new additions)

`httpx`, `pydantic`, `rich`, `typer` (foundation), `PyMuPDF`, `python-docx`, `nupunkt` (parsing), `presidio-analyzer`, `presidio-anonymizer`, `cryptography` (PII), `litellm`, `questionary`, `platformdirs`, `pyyaml` (AI Gateway).

### Development (all pre-existing)

`pytest`, `ruff`, `mypy`, `pre-commit`, `pytest-cov`, `pytest-mock`, `responses`.

### Constraint check

- ✅ No langchain, llama-index, FAISS, spaCy (for PII), sentence-transformers, Click, loguru, structlog, FastAPI, Flask
- ✅ AGPL-3.0 compatible
- ✅ All deps already installed via `uv sync`

---

## 3. File Paths

### Existing files (modified)

| File | Changes |
|------|---------|
| `src/openreview_cli/app.py` | Add 8 new subcommands (6 batch-1 + 2 remediation). Already has `_register_product_mode` helper. |
| `src/openreview_cli/review/prompts.py` | Add 8 new entries to `MODE_VOCABULARY` dict. Already has dict structure. |
| `src/openreview_cli/review/playbook.py` | Register new playbook names in `BUNDLED_PLAYBOOKS` dict. |
| `tests/unit/test_playbook_schema.py` | Add playbook validation tests for 8 new playbooks. |
| `tests/integration/test_{mode}.py` | Add 8 new E2E integration test files. |

### New files (created)

| File | Purpose |
|------|---------|
| `src/openreview_cli/review/playbooks/indemnification-v1.yaml` | IndemnityCheck playbook |
| `src/openreview_cli/review/playbooks/consulting-agreement-v1.yaml` | ConsultCheck playbook |
| `src/openreview_cli/review/playbooks/work-for-hire-v1.yaml` | WorkCheck playbook |
| `src/openreview_cli/review/playbooks/letter-of-intent-v1.yaml` | LOICheck playbook |
| `src/openreview_cli/review/playbooks/subcontractor-agreement-v1.yaml` | SubCheck playbook |
| `src/openreview_cli/review/playbooks/settlement-agreement-v1.yaml` | SettlementCheck playbook |
| `src/openreview_cli/review/playbooks/dealcheck-v1.yaml` | DealCheck playbook (remediation — may already exist) |
| `src/openreview_cli/review/playbooks/hirecheck-v1.yaml` | HireCheck playbook (remediation — may already exist) |
| `tests/fixtures/{indemnification,consulting,...}-agreement.pdf` | 8 fixture PDFs |
| `tests/unit/review/playbooks/test_dealcheck.py` | DealCheck unit tests (remediation) |
| `tests/unit/review/playbooks/test_hirecheck.py` | HireCheck unit tests (remediation) |
| `tests/integration/test_dealcheck_command.py` | DealCheck integration test (remediation) |
| `tests/integration/test_hirecheck_command.py` | HireCheck integration test (remediation) |
| `tests/integration/test_indemnitycheck.py` | IndemnityCheck integration test |
| `tests/integration/test_consultcheck.py` | ConsultCheck integration test |
| `tests/integration/test_workcheck.py` | WorkCheck integration test |
| `tests/integration/test_loicheck.py` | LOICheck integration test |
| `tests/integration/test_subcheck.py` | SubCheck integration test |
| `tests/integration/test_settlementcheck.py` | SettlementCheck integration test |

### Unchanged

`src/openreview_cli/parsing/`, `src/openreview_cli/pii/`, `src/openreview_cli/gateway/`, `src/openreview_cli/errors.py`, `src/openreview_cli/config/`, `src/openreview_cli/storage/`.

---

## 4. Module Interfaces

### `_register_product_mode` (app.py, ~line 2255)

```python
def _register_product_mode(
    app: typer.Typer,
    mode_name: str,
    display_name: str,
    playbook_id: str,
    prompt_key: str,
    help_text: str,
) -> None:
```
Registers a CLI subcommand on the provided `typer.Typer` app. Flags:
`--no-pii`, `--playbook`, `--format` (default `text`), `--output`, `--memo-format`, `--output-dir`, `--verbose`, `--confidence-threshold`/`-ct` (default `0.7`).

### `BUNDLED_PLAYBOOKS` (playbook.py, ~line 20)

```python
BUNDLED_PLAYBOOKS: dict[str, Path] = {
    "precheck": ..., "licensecheck": ..., "leasecheck": ..., "privacycheck": ...,
    "dealcheck": ..., "hirecheck": ...,  # after remediation
}
```
Dict mapping mode name → `Path` to YAML file. New playbooks must add an entry.

### `run_review()` (review/__init__.py)

```python
async def run_review(
    path: Path,
    mode: str,
    playbook: Playbook,
    no_pii: bool = False,
    output_dir: Optional[Path] = None,
    ...
) -> ReviewReport:
```
Entry point for all product-mode review. Accepts mode string, playbook, PII flag, output path.

### `ReviewReport` (review/models.py)

```python
@dataclass
class ReviewReport:
    mode: str
    assessments: list[Assessment]
    document: Document
    overall_confidence: float  # 0.0–1.0
    memo_path: Optional[Path]
```
Primary output structure. Serialises to JSON envelope (see data-model.md §5).

### `MODE_VOCABULARY` (review/prompts.py)

```python
MODE_VOCABULARY: dict[str, dict[str, str]] = {
    "precheck": {"specialization": "...", "domain": "...", "vocabulary": "..."},
    ...
}
```
Dict mapping mode name → prompt template overrides. One entry per mode.

---

## 5. Mismatches Found & Resolved

| # | Finding | Resolution |
|---|---------|------------|
| U1 | JSON output schema undefined in data-model.md | Added §5 JSON Output Envelope with fields, types, and example |
| U2 | Accuracy baseline "within 5pp" unverifiable | Replaced with measurable criterion: each mode's integration test yields non-empty ReviewReport with Green/Amber/Red assessments and exits 0 |
| U3 | FR1 flags mismatch actual `_register_product_mode` | Updated FR1 to list exact 8 flags: `--no-pii`, `--playbook`, `--format`, `--output`, `--memo-format`, `--output-dir`, `--verbose`, `--confidence-threshold`/`-ct` |
| I1 | Spec claims 6 existing modes; only 4 wired | Updated Overview + Dependencies to state 4 wired + 2 being wired in this batch. Added Remediation phase in tasks.md |
| C1 | Plan memory wording: "<110 MB" vs constitution | Fixed to: "<100 MB peak memory budget (110 MB hard floor)" |
| G1 | Missing analysis-context.md | This file created |

### Verdict

**GREEN** — all mismatches resolved in artifact edits. Implementation may proceed. No blocker remains in spec, data-model, plan, tasks, or analysis-context.
