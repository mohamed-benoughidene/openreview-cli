# Data Model: CLI Wizard UX Redesign

**Phase 1 output** | **Date**: 2026-06-27

## Entities

### ReviewConfiguration

The bundle returned by `ReviewWizard.run()` to the caller in `app.py`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_path` | `str` | yes | Path to the contract file |
| `mode` | `Literal["full", "clause-by-clause", "risk-scan"]` | yes | Review mode selected by user |
| `jurisdiction` | `str \| None` | no | Jurisdiction code (e.g. "us-de", "us-ca", "eu-gdpr"). None when mode is "risk-scan". |
| `output_format` | `Literal["json", "text", "html"] \| None` | no | Desired output format. None when mode is "risk-scan". |
| `clauses` | `list[str] \| None` | no | Selected clause IDs. None = all clauses. Only populated when mode is "clause-by-clause". |

**Validation rules**:
- `file_path` must exist and be a supported file type (PDF, DOCX)
- If `mode` is "full" or "clause-by-clause": `jurisdiction` and `output_format` are required
- If `mode` is "clause-by-clause": `clauses` must have at least one entry (unless empty list = all clauses)
- In non-interactive mode, missing required fields raise a validation error

### WizardStep (internal/shared)

Describes a single prompt in a wizard flow. Not persisted; used to define step sequences.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | yes | Key in the answers dictionary |
| `prompt_type` | `Literal["select", "checkbox", "autocomplete", "confirm", "password", "text"]` | yes | Maps to a questionary function |
| `message` | `str` | yes | Prompt text shown to user |
| `choices` | `list[str] \| None` | no | Options for select/checkbox/autocomplete |
| `when` | `Callable[[dict], bool] \| None` | no | Conditional skip function, receives prior answers |
| `validate` | `Callable \| None` | no | Validation function for text/password inputs |
| `default` | `Any \| None` | no | Default selection or value |

### ReviewMode

```python
class ReviewMode(str, enum.Enum):
    FULL = "full"
    CLAUSE_BY_CLAUSE = "clause-by-clause"
    RISK_SCAN = "risk-scan"
```

### OutputFormat

```python
class OutputFormat(str, enum.Enum):
    JSON = "json"
    TEXT = "text"
    HTML = "html"
```

## State: ReviewWizard Flow

```
[Start] → [Pre-flight check (gateway ready?)]
  if not ready → [Warn user] → [Offer gateway setup]
    → [Accept: run gateway setup] → [Retry check]
    → [Decline: continue with defaults]
  if ready (or declined) → [Select mode]
    if risk-scan → [Show summary] → [Confirm?]
      → [Yes: return ReviewConfiguration]
      → [No/Ctrl+C: exit]
    if full or clause-by-clause → [Select jurisdiction] → [Select output format]
      if clause-by-clause → [Select clauses (multi-select)]
    → [Show summary] → [Confirm?]
      → [Yes: return ReviewConfiguration]
      → [No/Ctrl+C: exit]
```

## State: SetupWizard Flow (refactored)

```
[Start] → [Loop over 5 slots: reasoning, extraction, embedding, reranking, graph]
  Per slot:
    [Select provider (arrow keys)] → [Select model (arrow keys, fuzzy filter)]
    If cloud provider → [Enter API key (password mask, inline validation)]
    If reasoning → [Apply to extraction & graph? (confirm)]
      → Yes: copy model, skip those slots
  [After all slots → Show summary table]
  [Confirm?]
    → Yes: [Save config.yml + auth.json] → [Exit]
    → No: [Exit without saving]
```

## Relationships

- `ReviewWizard` produces a single `ReviewConfiguration` per invocation
- `SetupWizard` produces two files: `config.yml` (GatewayConfiguration) and `auth.json` (API keys)
- `SetupWizard` and `ReviewWizard` share prompt helper functions from `cli/utils.py` but are independent classes
