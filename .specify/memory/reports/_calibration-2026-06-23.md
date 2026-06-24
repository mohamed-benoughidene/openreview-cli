# Teaching Method Calibration Record

**Date:** 2026-06-23
**Method name:** Pain → Recipe → Practice

## Why this method

We tested 5 teaching methods against 2 concepts (variable and function) using dunder-named examples from the project. The stakeholder (non-technical) rated each method. Methods 2, 3, and 4 won for both concepts:

- **Method 2 (Analogy + code side-by-side):** a tangible analogy, then the real code, then "what each part means"
- **Method 3 (Problem-first):** show the pain of NOT having the concept, then introduce the concept as the fix
- **Method 4 (Real-world workflow):** show the actual steps the reader will take in the project

The three methods were combined into a single three-beat structure: **Pain → Recipe → Practice**.

## Sample: Variable

**The Pain.** The version `0.1.0` shows up in 5 places: help text, package metadata, error messages, tests, docs. If we wrote `"0.1.0"` directly in all 5 places, upgrading to `"0.2.0"` means find-and-replace in 5 files. Easy to miss one — and now the project claims to be 0.1.0 in some places and 0.2.0 in others.

**The Recipe.** A variable is a labeled box. The label is the name; the contents are the value. In `_version.py`:
```python
__version__ = "0.1.0"
```
- `__version__` = the name on the box
- `=` = "put this inside" (not "is equal to" like in math)
- `"0.1.0"` = the text stored inside

**In Practice.** When we ship a new version: open `_version.py`, find `__version__ = "0.1.0"`, change `"0.1.0"` to `"0.2.0"`, save. That's it. One line, one file, and the new version appears everywhere — help text, error messages, tests, docs. The name is the handle; the value is what's in your hand.

## Sample: Function

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

## Re-calibration trigger

Re-test this method only when a new domain concept is introduced (LLM, embedding, vector DB, PII detection, etc.). Not on a cadence.
