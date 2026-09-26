# Quickstart — Adding a New Product Mode

**Spec 027 Pattern**: To add a new product mode to the openreview CLI, follow these four steps. This document captures the pattern validated by LicenseCheck, LeaseCheck, and PrivacyCheck.

## Step 1: Create a Playbook YAML

Create a playbook YAML file in `src/openreview_cli/review/playbooks/`. Follow the established 3-position, 3-question schema [S-024]:

```yaml
version: "1.0"
name: "Your Mode Review"
id: "your-mode-v1"
description: "Description of the domain"
mode: "yourmode"
positions:
  - id: "favorable"
    label: "Favorable to [Your Party]"
    questions:
      - id: "q1"
        text: "Is [domain-specific favorable clause] present?"
        threshold: 0.6
        weight: 1.0
      # ... 2 more questions
  - id: "neutral"
    label: "Neutral / Standard"
    questions:
      # ... 3 questions, threshold 0.5, weight 0.8
  - id: "adverse"
    label: "Adverse to [Your Party]"
    questions:
      # ... 3 questions, threshold 0.6, weight 1.0
```

Key rules:
- 3 positions, exactly 9 questions total
- Favorable/adverse questions: threshold 0.6, weight 1.0
- Neutral questions: threshold 0.5, weight 0.8
- Mode must match the CLI subcommand name

## Step 2: Register a Prompt Template

Add a prompt template entry in the prompt registry [S-009]. The template injects domain vocabulary and few-shot examples. Structure:

- **System message**: Sets the role as a contract review specialist for the domain
- **Example assessments**: 2-3 few-shot examples showing correct clause assessment
- **Glossary terms**: Domain-specific terms the LLM should recognize
- **Citation requirement**: Every assessment must cite the source clause

## Step 3: Wire the CLI Subcommand

Add a subcommand in `src/openreview_cli/app.py` that:

1. Creates a `ReviewCommand` subclass instance with the mode name and default playbook path
2. Registers a Typer subcommand matching the mode name
3. Reuses all existing flags (`--no-pii`, `--output`, `--playbook`)
4. Delegates to `run_review()` [S-011]

Pattern:

```python
@app.command()
def yourmode(
    path: Annotated[Path, typer.Argument(help="Document to review")],
    no_pii: Annotated[bool, typer.Option("--no-pii")] = False,
    output: Annotated[str, typer.Option("--output")] = "text",
    playbook: Annotated[Optional[Path], typer.Option("--playbook")] = None,
):
    """Review a document for [domain] compliance."""
    cmd = ReviewCommand(mode="yourmode", default_playbook="your-mode-v1.yaml")
    run_review(cmd, path, no_pii=no_pii, output=output, playbook=playbook)
```

## Step 4: Add Tests

- **Unit test**: Validate playbook YAML against the schema
- **Integration test**: E2E test with a fixture document
- **Accuracy benchmark**: Run against held-out test corpus using benchmark harness [S-010]

## Pattern Summary

| Step | What | Existing Pattern |
|------|------|------------------|
| 1 | Playbook YAML | [S-024] [S-011] |
| 2 | Prompt template | [S-009] |
| 3 | CLI subcommand | [S-015] [S-011] |
| 4 | Tests | [S-010] |

No changes to the pipeline, data models, or infrastructure. The architecture supports 22+ modes with linear growth only in playbook definitions [S-011].
