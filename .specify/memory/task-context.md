## Verified Dependencies
VERIFIED DEP: rich | VERSION: 15.0.0 | SOURCE: https://pypi.org/project/rich/ · https://rich.readthedocs.io/en/stable/introduction.html
VERIFIED DEP: questionary | VERSION: 2.1.1 | SOURCE: https://pypi.org/project/questionary/ · https://questionary.readthedocs.io/
VERIFIED DEP: typer | VERSION: 0.26.8 | SOURCE: https://pypi.org/project/typer/ · https://typer.tiangolo.com/
VERIFIED DEP: gh | VERSION: v2.95.0 | SOURCE: https://cli.github.com/ · https://github.com/cli/cli/releases
VERIFIED DEP: gum | VERSION: v0.17.0 | SOURCE: https://github.com/charmbracelet/gum/releases
VERIFIED DEP: clig.dev | VERSION: N/A (guidelines) | SOURCE: https://clig.dev/
VERIFIED DEP: 200ms responsiveness threshold | VERSION: N/A (research) | SOURCE: Miller 1968; Nielsen Alertbox; Google Core Web Vitals
VERIFIED DEP: Python error message design | VERSION: N/A (stdlib) | SOURCE: https://docs.python.org/3/library/traceback.html
POTENTIALLY STALE: InquirerPy | VERSION: 0.3.4 | SOURCE: https://pypi.org/project/InquirerPy/ (4 years since last release; questionary is the actively maintained alternative)

## Project Structure (actual)
```
src/openreview_cli/:
app.py
cli/
  __init__.py
  review.py
  utils.py
config/
  auth.py
  __init__.py
  loader.py
  paths.py
errors.py
gateway/
  costs.py
  engine.py
  errors.py
  importer.py
  __init__.py
  logging.py
  models.py
  providers.py
  registry.py
  utils.py
  wizard.py
__init__.py
__main__.py
parsing/
  clause_detector.py
  docx_parser.py
  __init__.py
  models.py
  pdf_parser.py
  stream.py
pii/
  audit.py
  engine.py
  __init__.py
  mapping.py
  models.py
  placeholders.py
  recognizers.py
retrieval/  (only __pycache__ visible; .py files not in directory listing)
storage/
  database.py
  __init__.py
  migrations/
    001_initial.sql
```

```
tests/
conftest.py
fixtures/  (docx/, pdf/, pii/, test.txt, generate_fixtures.py)
integration/  (22 test files including test_review_cli.py, test_pii_*.py, test_gateway_*.py, test_retrieval/)
unit/  (27 test files including test_app.py, test_review_wizard.py, test_pii_*.py, test_retrieval/)
```

## Existing Files
EXISTS: src/openreview_cli/__init__.py (exports: __version__)
EXISTS: src/openreview_cli/__main__.py (exports: imports app, runs app())
EXISTS: src/openreview_cli/app.py (exports: typer.Typer app, _version_callback, _init; 986 lines)
EXISTS: src/openreview_cli/errors.py (exports: config_error, cost_limit_error, pii_error, gateway_error)
EXISTS: src/openreview_cli/cli/__init__.py (exports: empty)
EXISTS: src/openreview_cli/cli/review.py (exports: ReviewMode enum, OutputFormat enum, JURISDICTION_CODES, SUPPORTED_EXTENSIONS, ReviewConfiguration dataclass; 317 lines)
EXISTS: src/openreview_cli/cli/utils.py (exports: _is_interactive, _add_hint, _select, _checkbox, _autocomplete; uses questionary; 91 lines)

NOTE: Cap reached at 8 read-only calls. Remaining source files not scanned:
- config/auth.py, config/loader.py, config/paths.py
- gateway/*.py (11 files)
- parsing/*.py (6 files)
- pii/*.py (7 files)
- storage/database.py, storage/__init__.py
- retrieval/ (files not visible in ls output)

## Plan vs Filesystem

### Plan.md Source Code Paths (from specs/006-cli-ux-specification/plan.md)

**Existing files referenced by plan:**
EXISTS: src/openreview_cli/__init__.py — plan says "Exposes __version__" ✓ matches
EXISTS: src/openreview_cli/app.py — plan says "Typer app (extended with output flags, wizard callback)" ✓ matches
EXISTS: src/openreview_cli/errors.py — plan says "Exit code constants (extended: 8 codes from spec §5.3)" ✓ matches
EXISTS: src/openreview_cli/config/ — plan says "Existing config package (extended)" ✓ matches

**NEW files defined by plan (not yet on filesystem):**
NEW: src/openreview_cli/types.py — "type aliases (OutputFormat, WizardStep, ColorRole)"
NEW: src/openreview_cli/ui/__init__.py — "Public exports"
NEW: src/openreview_cli/ui/console.py — "SGRenderer (Rich Console singleton, capability detection)"
NEW: src/openreview_cli/ui/colors.py — "Design tokens (semantic palette, Role → Hex mapping)"
NEW: src/openreview_cli/ui/components/panel.py — "Info/Warning/Error/Success panels"
NEW: src/openreview_cli/ui/components/table.py — "SGTable (auto-width, plain/table output)"
NEW: src/openreview_cli/ui/components/spinner.py — "Spinner wrapper (live + fallback)"
NEW: src/openreview_cli/ui/components/progress.py — "Progress wrapper (streaming, cancellation)"
NEW: src/openreview_cli/ui/components/prompt.py — "Select/checkbox/confirm/text/password (questionary)"
NEW: src/openreview_cli/ui/components/wizard.py — "Wizard state machine (Entry → Results)"
NEW: src/openreview_cli/ui/components/key_bindings.py — "Keyboard shortcut map (Ctrl-C, Escape, Tab, etc.)"
NEW: src/openreview_cli/ui/components/status_line.py — "Status display (LLM streaming, mode context)"
NEW: src/openreview_cli/ui/components/header.py — "Separator/breadcrumb headers"
NEW: src/openreview_cli/ui/components/markdown.py — "Minimal MD renderer (headers, bullets, bold)"
NEW: src/openreview_cli/ui/components/validation.py — "Input validation (paths, config keys, ranges)"
NEW: src/openreview_cli/ui/feedback.py — "Structured feedback format (3-part error, exit mapping)"
NEW: src/openreview_cli/config/first_run.py — "first-run detection + auto-wizard trigger"

**NEW test files defined by plan:**
NEW: tests/unit/test_ui_console.py
NEW: tests/unit/test_ui_colors.py
NEW: tests/unit/test_ui_panel.py
NEW: tests/unit/test_ui_table.py
NEW: tests/unit/test_ui_spinner.py
NEW: tests/unit/test_ui_progress.py
NEW: tests/unit/test_ui_prompt.py
NEW: tests/unit/test_ui_wizard.py
NEW: tests/unit/test_ui_feedback.py
NEW: tests/unit/test_ui_validation.py
NEW: tests/unit/test_first_run.py
NEW: tests/integration/test_cli_output.py
NEW: tests/integration/test_cli_wizard.py
NEW: tests/integration/test_cli_config.py

**Existing files NOT in plan.md (filesystem has, plan doesn't mention):**
EXISTS BUT UNMENTIONED: src/openreview_cli/cli/ (review.py, utils.py) — interactive review wizard
EXISTS BUT UNMENTIONED: src/openreview_cli/pii/ (7 files) — PII stripping engine
EXISTS BUT UNMENTIONED: src/openreview_cli/retrieval/ — retrieval/search module
EXISTS BUT UNMENTIONED: src/openreview_cli/storage/ — SQLite storage layer
EXISTS BUT UNMENTIONED: src/openreview_cli/gateway/ — AI gateway
EXISTS BUT UNMENTIONED: src/openreview_cli/parsing/ — document parsing engine

**Mismatches:** None. Plan.md paths are consistent with existing structure. Plan defines 17 NEW source files and 14 NEW test files.
