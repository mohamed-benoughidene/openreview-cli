# Phase 1 — Foundation

**Date:** 2026-06-23
**Commit:** `018c4ba` (reports folder) | `742a8dc` (Phase 1 foundation)
**Audience:** non-technical stakeholder learning Python through this project
**Teaching method:** Pain → Recipe → Practice

## Part 1 — Status

### What this phase was

We turned a single `Hello world` file into a properly installed, properly tested, properly checked Python package. The house is still empty — no product features shipped — but the foundation is in place.

### What changed

- The project now lives in a real Python package at `src/openreview_cli/`. The old `main.py` Hello-world is gone.
- `uv run openreview --version` works. So does `python -m openreview_cli`. A `uv tool install .` from a fresh checkout now installs a working `openreview` command.
- A test suite exists. It runs four tests and proves the package stays under 110 MB of RAM.
- A linter, a type checker, and a code formatter are now configured. They run automatically before every commit and on every push to GitHub.
- GitHub Actions (the CI pipeline) now runs four checks in parallel: lint, type-check, tests, memory budget. Green CI is required to merge.
- `AGENTS.md` (the developer-only instruction file) was updated to reflect the new state.

### What was verified

- ruff (linter) — clean
- ruff format — 9 files formatted correctly
- mypy (type checker, strict) — no issues
- pytest — 4 of 4 tests pass
- memory budget test — passes (peak under 110 MB)
- `openreview --version` — prints `openreview 0.1.0`

---

## Part 2 — Concepts

### 1. Variable

**The Pain.** The version `0.1.0` shows up in 5 places: help text, package metadata, error messages, tests, docs. If we wrote `"0.1.0"` directly in all 5 places, upgrading to `"0.2.0"` means find-and-replace in 5 files. Easy to miss one — and now the project claims to be 0.1.0 in some places and 0.2.0 in others.

**The Recipe.** A variable is a labeled box. The label is the name; the contents are the value. In `_version.py`:
```python
__version__ = "0.1.0"
```
- `__version__` = the name on the box
- `=` = "put this inside" (not "is equal to" like in math)
- `"0.1.0"` = the text stored inside

**In Practice.** When we ship a new version: open `_version.py`, find `__version__ = "0.1.0"`, change `"0.1.0"` to `"0.2.0"`, save. That's it. One line, one file, and the new version appears everywhere — help text, error messages, tests, docs. The name is the handle; the value is what's in your hand.

---

### 2. Import

**The Pain.** The version string lives in `_version.py`. But `app.py` needs it (for the `--version` flag), `__init__.py` needs it (to expose it to the rest of the project), and `__main__.py` needs it (to wire up the CLI). Without a way to borrow code between files, you'd have to copy-paste the version into every file — and now you have 3 copies to keep in sync.

**The Recipe.** Importing is borrowing tools from another file. You write the code once in one file, and other files borrow it. In `__init__.py`:
```python
from openreview_cli._version import __version__
```
- `from` = "go to the file"
- `openreview_cli._version` = "the file named `_version.py` inside the `openreview_cli` package"
- `import __version__` = "borrow the box labeled `__version__`"

**In Practice.** When `app.py` needs the version, it writes one line: `from openreview_cli._version import __version__`. Python goes to `_version.py`, finds the box labeled `__version__`, and gives `app.py` a copy of whatever's inside. Change the value in `_version.py` once, and every file that imported it sees the new value.

---

### 3. Function

**The Pain.** Suppose the `--version` output should print the version in 3 places: CLI help, error messages, test output. We'd write `typer.echo(f"openreview {__version__}")` 3 times. If we want to change the format (add a date, change the prefix), we have to find and update 3 places. Easy to miss one.

**The Recipe.** A function is a recipe card. You write it once, and use it many times with different ingredients. In `app.py`:
```python
def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"openreview {__version__}")
        raise typer.Exit()
```
- `def` = "define a recipe"
- `_version_callback` = the recipe's name
- `value: bool` = the input (a yes/no flag)
- The indented lines = the steps
- Calling `_version_callback(True)` follows the recipe with `value=True`

**In Practice.** When a user types `openreview --version`, here's what happens: Typer sees the `--version` flag, finds the recipe we registered for it (`_version_callback`), and runs the recipe with `value=True`. The recipe prints `openreview 0.1.0` and exits. You define the recipe once (`def _version_callback...`), register it with Typer (`@app.callback()`), and Typer calls it whenever the flag is present.

---

### 4. The double underscores `__` (Python's built-in labels)

**The Pain.** You see `__init__.py`, `__main__.py`, `__version__`, `__name__`, `__all__` everywhere. Without knowing the rule, each one looks like a different thing. You have to memorize them one by one.

**The Recipe.** The double underscores are Python's "this is special" stamp. If you name a file `app.py`, Python treats it as a normal file. If you name a file `__init__.py` or `__main__.py`, Python sees the double underscores and immediately thinks: "Aha! This is a special system file. I have specific rules on how to handle this." Same with variables: `version` is just a regular variable, but `__version__` is a variable that Python recognizes as the package's version string.

**In Practice.** In this project, Python uses three dunder files:
- `__init__.py` — tells Python "this folder is a toolbox (a package)". It borrows `__version__` from `_version.py` and exports it via `__all__`.
- `__main__.py` — tells Python "if the user runs this folder as a program, run me first." It borrows `app` from `app.py` and calls `app()` if the file is run directly.
- The dunder *variables* (`__version__`, `__name__`, `__all__`) are Python's built-in labels that have specific meaning.

---

### 5. `__name__ == "__main__"` (boss vs. sub-assistant)

**The Pain.** `__main__.py` borrows the `app` function from `app.py`. But it should only call `app()` when the user runs the file directly (like `python -m openreview_cli`). If another file just borrows something from `__main__.py`, it shouldn't trigger `app()`.

**The Recipe.** Python uses a built-in box called `__name__` to keep track of who's running the script. If a file is run directly, Python puts `"__main__"` inside the `__name__` box. If a file is just imported by another file, Python puts the file's actual name inside the `__name__` box. So:
```python
if __name__ == "__main__":
    app()
```
means: "Only run `app()` if the user ran this specific file directly. If another file is just borrowing something from here, don't run the tool."

**In Practice.** In `__main__.py`, we have:
```python
from openreview_cli.app import app

if __name__ == "__main__":
    app()
```
When you type `python -m openreview_cli` in the terminal, Python sets `__name__` to `"__main__"`, the condition is true, and `app()` runs. If another file just imports something from `__main__.py`, the condition is false, and `app()` does NOT run.

---

### 6. The CLI (vending machine with buttons)

**The Pain.** Without a CLI framework, you'd write your own argument parser: check `sys.argv` for `--version`, handle `--help`, deal with errors, format the output. It's 50+ lines of boilerplate before you've done anything useful.

**The Recipe.** A CLI (Command-Line Interface) is a vending machine. The user pushes buttons (types flags like `--version`, `--help`), and the machine delivers products (prints output, runs actions). Typer is the vending machine framework. You register buttons and their recipes, and Typer handles the rest. In `app.py`:
```python
app = typer.Typer(name="openreview", help="...", no_args_is_help=True)

@app.callback()
def _version_callback(value: bool) -> None:
    ...
```
- `typer.Typer(...)` = create a vending machine with a name and help text
- `@app.callback()` = register a button (`--version`) that runs a recipe (`_version_callback`)
- `no_args_is_help=True` = "if the user types `openreview` with no arguments, show the help text"

**In Practice.** When you type `openreview --version`, Typer (the vending machine) sees the `--version` button, finds the recipe we registered (`_version_callback`), runs it with `value=True`, and the recipe prints `openreview 0.1.0` and exits. When you type `openreview --help`, Typer shows the help text we configured. You never have to parse `sys.argv` yourself.

---

### 7. Tests (quality inspector with a checklist)

**The Pain.** You write code, it works on your machine, you push it, and it breaks on someone else's machine. Or you change one file and accidentally break another file. Without tests, you find out about bugs when users complain.

**The Recipe.** A test is a quality inspector with a checklist. Each test is a small script that says: "Given this input, I expect this output. If the output doesn't match, fail." Tests run automatically — you don't have to remember to run them. In `tests/unit/test_app.py`:
```python
def test_app_imports():
    from openreview_cli.app import app
    assert app is not None
```
This test says: "Import the `app` from `openreview_cli.app`. Assert that it exists (is not `None`). If the import fails or `app` is `None`, fail."

**In Practice.** Every time you run `uv run pytest`, Python goes through every `test_*.py` file, finds every `test_*` function, runs each one, and reports pass/fail. If all 4 tests pass, you know the package is healthy. If one fails, you know exactly which test broke and why. Tests run on every push to GitHub (via CI) and can run locally before you push.

---

### 8. Fixtures (the inspector's setup crew)

**The Pain.** Tests need temporary resources — a folder for sample PDFs, a peak-memory counter, a clean slate for each test. Without a way to share setup code, each test would have to create its own resources. If 10 tests need the same folder, you'd write the same setup code 10 times.

**The Recipe.** A fixture is the inspector's setup crew. It runs BEFORE each test and hands the test whatever it needs. Fixtures live in `conftest.py` and are available to every test in the same folder. In `tests/conftest.py`:
```python
@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures"

@pytest.fixture
def memory_tracker():
    tracemalloc.start()
    yield
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 110 * 1024 * 1024, f"Peak memory {peak / 1024 / 1024:.1f} MB exceeded 110 MB"
```
- `@pytest.fixture` = "this is a setup crew, not a test"
- `fixtures_dir` hands the test a path to the `tests/fixtures/` folder
- `memory_tracker` starts tracking memory, runs the test, then checks that peak memory stayed under 110 MB

**In Practice.** When a test needs the fixtures directory, it just asks for it: `def test_something(fixtures_dir):`. Pytest sees the parameter name, finds the matching fixture, runs the setup code, and hands the result to the test. When a test needs the memory budget checked, it asks for `memory_tracker`: `def test_memory(memory_tracker):`. The fixture starts tracking, the test runs, and the fixture checks the budget after the test finishes.

---

### 9. CI (automated inspection line)

**The Pain.** You can run tests locally, but you have to remember to do it. You can run the linter, but you might forget. Different developers on the same project might have different versions of Python or different tools installed. Without automation, quality depends on discipline.

**The Recipe.** CI (Continuous Integration) is an automated inspection line that runs in the cloud. Every time you push code to GitHub, CI runs the same checks you'd run locally — lint, type-check, tests, memory budget — on a clean, standardized machine. If any check fails, CI blocks the merge. In `.github/workflows/ci.yml`:
```yaml
jobs:
  lint:
    steps: [ruff check, ruff format --check]
  types:
    steps: [mypy --strict]
  test:
    steps: [pytest tests/unit/]
  memory:
    steps: [pytest -m memory]
```
- Four jobs run in parallel (lint, types, test, memory)
- Each job runs on a fresh Ubuntu machine with Python 3.12 and uv installed
- All four must pass for the code to be merged

**In Practice.** When you push to `main` or open a PR, GitHub Actions spins up four clean machines in parallel. Each runs one check. If all four pass, you see a green checkmark and the code can be merged. If one fails, you see a red X and know exactly which check broke. You fix it locally, push again, and the cycle repeats.

---

## Part 3 — Walkthrough

### `_version.py` — the storage room with one box

This file contains one line: `__version__ = "0.1.0"`. It's the single source of truth for the project's version. Every other file that needs the version imports it from here. Concept 1 (Variable) explains why this exists.

### `__init__.py` — the front door of the toolbox

This file tells Python: "This folder (`openreview_cli/`) is a package — a unified toolbox." It borrows `__version__` from `_version.py` and exports it via `__all__ = ["__version__"]`. Concepts 2 (Import) and 4 (Double underscores) explain how this works.

### `__main__.py` — the on-switch

This file is what Python runs when you type `python -m openreview_cli`. It borrows `app` from `app.py`, checks if it's being run directly (`if __name__ == "__main__":`), and calls `app()`. Concepts 5 (`__name__ == "__main__"`) and 2 (Import) explain this.

### `app.py` — the vending machine with buttons

This file builds the CLI: it creates a Typer app, registers the `--version` flag with a callback function, and sets up the help text. Concepts 6 (CLI), 3 (Function), and 4 (Double underscores) explain this file.

### `tests/conftest.py` — the inspector's toolbelt

This file provides fixtures (setup code) for every test: a `fixtures_dir` path and a `memory_tracker` that enforces the 110 MB budget. Concept 8 (Fixtures) explains this.

### `tests/unit/test_app.py` — the four checks the inspector runs

This file contains 4 tests: import check, `--version` check, `--help` check, and memory budget check. Concept 7 (Tests) explains this.

### `pyproject.toml` — the instruction manual

This file tells Python (and uv, and PyPI, and mypy, and ruff, and pytest) how the project is structured: its name, version, dependencies, entry point, and tool configurations. It's not a concept we teach separately — it's the configuration that ties everything together.

### `.pre-commit-config.yaml` — the spell-check before saving

This file configures pre-commit hooks: tools that run automatically before every commit. They check formatting (ruff-format), linting (ruff), type safety (mypy), and a quick test run (pytest-fast). If any check fails, the commit is blocked until you fix it.

### `.github/workflows/ci.yml` — the cloud inspection line

This file configures GitHub Actions: four parallel jobs (lint, types, test, memory) that run on every push and PR. Concept 9 (CI) explains this.

---

## What's next

Phase 2 — the first product mode, end-to-end. Most likely `precheck` (NDA review). This is the phase that pulls in the big dependencies (`litellm`, `PyMuPDF`, `presidio-*`, `docling`, `python-docx`, `sqlite-vss`, `PyYAML`, `ijson`) one at a time, each justified by the feature that needs it.

## Questions for the stakeholder

- (placeholder — write here when you have a question or a decision for me to track)
