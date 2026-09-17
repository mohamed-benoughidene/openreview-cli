# Fix P0/P1 Design & Rendering Defects — Implementation Plan

> **For agentic workers:** Use tasks as checkboxes (`- [ ]`) for tracking. Steps use the
> checkbox syntax — mark `- [x]` as you complete each one.

**Goal:** Fix six rendering/UX defects (bracketed legal text deleted by Rich markup, lost
ANSI colors in the terminal report, the invalid `[amber]` tag, inert progress bars, INFO
log spam on every command, and hardcoded `/tmp` export paths) so the TUI and CLI render
contract data faithfully and quietly.

**Architecture:** Six independent, surgical fixes. Each is driven by a failing test first
(TDD). The TUI fixes use `rich.markup.escape()` / `markup=False` for untrusted text and a
single status-colour mapping for the amber badge; the progress fixes thread the existing
`ProgressCallback`/`ProgressEvent` plumbing from the review/negotiation pipelines into the
Textual screens, which run their blocking work via `asyncio.to_thread` and marshal widget
updates back with `App.call_from_thread`. The logging and report fixes are confined to
`app.py` and `report.py`.

**Tech Stack:** Python ≥ 3.12, Typer/Click, Rich ≥ 15, Textual ≥ 8.2.8, pytest 9 +
pytest-asyncio (auto mode). No new runtime dependencies.

## Global Constraints

- **No new runtime dependencies.** `rich>=15.0.0`, `textual>=8.2.8`, `typer>=0.26.7` are
  already declared in `pyproject.toml`.
- **Test speed markers are mandatory.** `tests/unit/**` tests are auto-marked `fast`;
  `tests/integration/tui/**` are auto-marked `slow` (each `app.run_test()` pays a ~30 s
  startup cost and a 120 s per-test timeout). Never add a test without falling into one of
  those trees.
- **Run tests with the project venv:** `.venv/bin/pytest ...` (or `uv run pytest ...`).
  The configured `addopts` include `--disable-socket`; do not add tests that perform real
  network I/O.
- **Privacy:** never log clause text, memo text, or PII. The exported files must stay under
  the current working directory (`review_results/`), never `/tmp`.
- **Do not change public CLI flags or exit codes** except adding the root `-v/--verbose`
  flag (Task 6) and the additive `progress_callback`/`color` keyword arguments.
- **Preserve existing test coverage:** changing `format_terminal` must not alter the plain
  text it already returns (only add ANSI when colour is enabled).

## File Structure

| File | Change | Responsibility |
| --- | --- | --- |
| `src/openreview_cli/tui/screens/result.py` | Modify | Escape clause/reasoning text; valid status-colour tag; `review_results` export dir |
| `src/openreview_cli/tui/screens/negotiation_result.py` | Modify | Non-markup memo label; `review_results` export dir |
| `src/openreview_cli/tui/screens/playbook_detail.py` | Modify | Non-markup category item labels |
| `src/openreview_cli/tui/tabs/playbooks.py` | Modify | Escape data lines in YAML import preview |
| `src/openreview_cli/review/report.py` | Modify | Terminal colour detection + `color` kwarg |
| `src/openreview_cli/app.py` | Modify | `_log_level()` helper, root `-v/--verbose`, quiet default |
| `src/openreview_cli/review/runner.py` | Modify | Forward `progress_callback` to the pipeline |
| `src/openreview_cli/tui/domain/review.py` | Modify | Forward `progress_callback` to `run_review` |
| `src/openreview_cli/tui/screens/progress.py` | Modify | Drive bar/steps from `ProgressEvent`s off-thread |
| `src/openreview_cli/tui/domain/negotiation.py` | Modify | Emit phase `ProgressEvent`s |
| `src/openreview_cli/tui/screens/negotiation_progress.py` | Modify | Drive bar/steps from phase events off-thread |

> **Note on the defect list:** the review references `src/openreview_cli/tui/screens/playbook_preview.py`,
> which does not exist in this repository. The equivalent playbook preview/detail surfaces are
> `src/openreview_cli/tui/screens/playbook_detail.py` and `src/openreview_cli/tui/tabs/playbooks.py`
> (the `_ImportModal` preview); both are covered in Task 4.

---

### Task 1: Preserve bracketed legal text in `ResultScreen` (P0 / T2)

**Files:**
- Modify: `src/openreview_cli/tui/screens/result.py` (lines 122–163; imports at top)
- Test: `tests/integration/tui/test_result_screen.py`

**Interfaces:**
- Consumes: `rich.markup.escape` (Rich ≥ 15).
- Produces: no new public symbols; `ResultScreen.__init__(reports, mode="precheck", error=None)` unchanged.

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/tui/test_result_screen.py` (reuses the module-level
`_make_mock_assessment` and `_make_mock_report` helpers already in that file):

```python
# ── Markup safety (P0/T2) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_result_screen_preserves_bracketed_clause_text() -> None:
    """Legal bracket text (e.g. [intentionally omitted]) must render literally."""
    from textual.widgets import Label

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    assessments = [
        _make_mock_assessment(text="Confidentiality [intentionally omitted] term."),
        _make_mock_assessment(text="Notice must be sent to [Party A] only."),
    ]
    report = _make_mock_report(assessments)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[report], mode="precheck"))
        await pilot.pause()

        joined = "\n".join(str(w.render()) for w in app.screen.query(Label))
        assert "[intentionally omitted]" in joined, joined
        assert "[Party A]" in joined, joined
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/integration/tui/test_result_screen.py::test_result_screen_preserves_bracketed_clause_text -q`

Expected: FAIL — `AssertionError`, rendered text is
`"1.  Confidentiality  term."` (brackets and their contents consumed by Textual markup).

- [ ] **Step 3: Write minimal implementation**

At the top of `src/openreview_cli/tui/screens/result.py`, add the import:

```python
from rich.markup import escape
```

In `_build_split_view` (lines 122–151), escape the clause text in the list item and set
`markup=False` on the two labels that carry arbitrary text:

```python
    def _build_split_view(self, assessments: list[ClauseAssessment]) -> Horizontal:
        """Build split view with clause list (left) and detail (right)."""
        items = [
            ListItem(
                Label(
                    f"{i + 1}. [{a.color}] "
                    f"{escape((a.clause_text or getattr(a, 'clause_ref', None) or f'Clause {i}')[:50])}",
                )
            )
            for i, a in enumerate(assessments)
        ]
        first = assessments[0]
        labels: dict[str, Label] = {
            "status": Label(f"Status: {first.color}"),
            "confidence": Label(
                f"Confidence: {first.effective_confidence or first.confidence:.2f}"
            ),
            "clause": Label(f"Clause: {first.clause_text or '\u2014'}", markup=False),
            "position": Label(f"Position: {first.position.value}"),
        }
        reasoning = getattr(first, "reasoning", None) or getattr(
            first, "qa_revised_rationale", None
        )
        labels["reasoning"] = Label(
            f"Reasoning: {str(reasoning)[:200]}" if reasoning else "", markup=False
        )
        self._right_labels = labels
        return Horizontal(
            ListView(*items, id="clause-list-pane"),
            Vertical(*labels.values(), id="clause-detail-pane"),
            id="split-view",
        )
```

In `_build_full_screen` (lines 153–163), escape the heading text and set `markup=False`
on the reasoning label:

```python
    def _build_full_screen(self, assessments: list[ClauseAssessment]) -> Vertical:
        """Build full-screen scroll view."""
        children: list[Label] = []
        for i, a in enumerate(assessments):
            text = a.clause_text or getattr(a, "clause_ref", None) or f"Clause {i}"
            children.append(Label(f"{i + 1}. [{a.color}] {escape(text)}"))
            children.append(Label(f"   Confidence: {a.effective_confidence or a.confidence:.2f}"))
            reasoning = getattr(a, "reasoning", None) or getattr(a, "qa_revised_rationale", None)
            if reasoning:
                children.append(Label(f"   Reasoning: {str(reasoning)[:100]}", markup=False))
        return Vertical(*children, id="full-screen-scroll")
```

> **Why this works:** `escape()` turns `[` into Rich's literal `\[`, and `markup=False`
> disables Textual's markup parser for a widget entirely. `_update_focus` (lines 200–226)
> calls `.update(...)` on the `clause`/`reasoning` labels; because those widgets were
> constructed with `markup=False`, the setting persists across updates.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/integration/tui/test_result_screen.py -q`
Expected: PASS (all pre-existing `ResultScreen` tests plus the new one).

- [ ] **Step 5: Commit**

```bash
git add src/openreview_cli/tui/screens/result.py tests/integration/tui/test_result_screen.py
git commit -m "fix(tui): preserve bracketed legal text in ResultScreen"
```

---

### Task 2: Map `amber` to a valid Rich colour tag (P1 / T3)

**Files:**
- Modify: `src/openreview_cli/tui/screens/result.py` (module level + lines 126–129 and 158)
- Test: `tests/unit/test_tui_status_color.py` (create), `tests/integration/tui/test_result_screen.py` (append)

**Interfaces:**
- Produces: `status_color_tag(color: object) -> str` — module-level function in
  `openreview_cli.tui.screens.result`; returns a Rich-parseable colour name
  (`"green"`, `"dark_orange"`, `"red"`, fallback `"white"`).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tui_status_color.py`:

```python
"""Unit tests for the TUI three-colour status tag mapping (P1/T3)."""

from __future__ import annotations

import pytest
from rich.errors import StyleSyntaxError
from rich.style import Style


def test_status_color_tag_maps_amber_to_valid_rich_color() -> None:
    from openreview_cli.tui.screens.result import status_color_tag

    assert status_color_tag("amber") == "dark_orange"
    # Every mapped value must be a colour Rich can actually parse.
    for color in ("green", "amber", "red"):
        Style.parse(status_color_tag(color))


def test_raw_amber_is_not_a_valid_rich_color() -> None:
    """Guard: this fails if someone regresses to emitting the raw value."""
    with pytest.raises(StyleSyntaxError):
        Style.parse("amber")
```

Append to `tests/integration/tui/test_result_screen.py`:

```python
@pytest.mark.asyncio
async def test_result_screen_amber_clause_gets_valid_style() -> None:
    """An amber clause must render with a real colour, not a stripped tag."""
    from textual.widgets import Label, ListView

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    assessments = [_make_mock_assessment(color="amber", confidence=0.4, text="Amber clause")]
    report = _make_mock_report(assessments)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[report], mode="precheck"))
        await pilot.pause()

        label = app.screen.query_one("#clause-list-pane", ListView).query_one(Label)
        content = label.render()
        styles = [str(span.style) for span in content.spans]
        assert any("orange" in style for style in styles), styles
        assert "Amber clause" in str(content)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/test_tui_status_color.py -q`

Expected: FAIL — `ImportError: cannot import name 'status_color_tag'`.

Run: `.venv/bin/pytest tests/integration/tui/test_result_screen.py::test_result_screen_amber_clause_gets_valid_style -q`

Expected: FAIL — `styles` contains no `"orange"` entry (`[amber]` is stripped as an
unknown style and produces no span; `rich.style.Style.parse("amber")` raises
`StyleSyntaxError: 'amber' is not a valid color`).

- [ ] **Step 3: Write minimal implementation**

In `src/openreview_cli/tui/screens/result.py`, add after `CLAUSES_PER_PAGE = 100`
(around line 16):

```python
# Rich colour names; "amber" is not a valid Rich colour, so it maps to dark_orange.
_STATUS_COLOR_TAG: dict[str, str] = {
    "green": "green",
    "amber": "dark_orange",
    "red": "red",
}


def status_color_tag(color: object) -> str:
    """Map an assessment colour value to a valid Rich colour tag."""
    return _STATUS_COLOR_TAG.get(str(color), "white")
```

Replace `[{a.color}]` with `[{status_color_tag(a.color)}]` in both places from Task 1
(the `_build_split_view` list item and the `_build_full_screen` heading). The list item
becomes:

```python
                Label(
                    f"{i + 1}. [{status_color_tag(a.color)}] "
                    f"{escape((a.clause_text or getattr(a, 'clause_ref', None) or f'Clause {i}')[:50])}",
                )
```

and the full-screen heading becomes:

```python
            children.append(Label(f"{i + 1}. [{status_color_tag(a.color)}] {escape(text)}"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_tui_status_color.py tests/integration/tui/test_result_screen.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/openreview_cli/tui/screens/result.py \
        tests/unit/test_tui_status_color.py \
        tests/integration/tui/test_result_screen.py
git commit -m "fix(tui): map amber status to valid Rich dark_orange tag"
```

---

### Task 3: Preserve bracketed memo text in `NegotiationResultScreen` (P0 / T2)

**Files:**
- Modify: `src/openreview_cli/tui/screens/negotiation_result.py` (line 62)
- Test: `tests/integration/tui/test_negotiation_result_screen.py` (create)

**Interfaces:**
- Consumes: `openreview_cli.tui.screens.negotiation_result.NegotiationResultScreen(report=None, error=None)`.
- Produces: none.

- [ ] **Step 1: Write the failing test**

Create `tests/integration/tui/test_negotiation_result_screen.py`:

```python
"""Integration tests for NegotiationResultScreen markup safety (P0/T2)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_negotiation_result_preserves_bracketed_memo_text() -> None:
    """Rendered memo text must keep literal brackets such as [intentionally omitted]."""
    from textual.widgets import Label

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.negotiation_result import NegotiationResultScreen

    report = MagicMock()
    report.disclaimer = "Advisory only."
    memo = "Clause 3 [intentionally omitted] remains binding."

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch("openreview_cli.negotiation.report.format_memo", return_value=memo):
            app.push_screen(NegotiationResultScreen(report=report))
            await pilot.pause()

            labels = [str(w.render()) for w in app.screen.query(Label)]
            assert any("[intentionally omitted]" in text for text in labels), labels
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/integration/tui/test_negotiation_result_screen.py -q`

Expected: FAIL — the memo label renders
`"Clause 3  remains binding."` (brackets stripped).

- [ ] **Step 3: Write minimal implementation**

In `src/openreview_cli/tui/screens/negotiation_result.py`, line 62, disable markup on the
memo label:

```python
                    Label(memo_text, id="memo-text", markup=False),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/integration/tui/test_negotiation_result_screen.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/openreview_cli/tui/screens/negotiation_result.py \
        tests/integration/tui/test_negotiation_result_screen.py
git commit -m "fix(tui): preserve bracketed memo text in NegotiationResultScreen"
```

---

### Task 4: Preserve bracketed text in playbook preview/detail (P0 / T2)

**Files:**
- Modify: `src/openreview_cli/tui/screens/playbook_detail.py` (line 30; imports at top)
- Modify: `src/openreview_cli/tui/tabs/playbooks.py` (lines 190–211; imports at top)
- Test: `tests/integration/tui/test_playbook_markup.py` (create)

**Interfaces:**
- Consumes: `openreview_cli.tui.screens.playbook_detail._CategoryItem(cat_id, name, default_position, description, exemplars)`.
- Consumes: `openreview_cli.tui.tabs.playbooks._ImportModal`.
- Produces: none.

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/tui/test_playbook_markup.py`:

```python
"""Markup-safety tests for playbook detail/preview widgets (P0/T2)."""

from __future__ import annotations

from pathlib import Path

import pytest

_BRACKETED_YAML = """id: bracket-pb
mode: precheck
metadata:
  version: "1.0"
  description: Brackets [test]
  author: Test
categories:
  - id: confidentiality
    name: "Confidentiality [scope]"
    description: Handles [bracketed] terms
    preferred:
      description: Broad
      exemplars: ["mutual [NDA]"]
    acceptable:
      description: Standard
      exemplars: ["standard"]
    walkaway:
      description: None
      exemplars: ["none"]
    default_position: preferred
"""


@pytest.mark.asyncio
async def test_playbook_category_item_preserves_brackets() -> None:
    from textual.widgets import Label

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.playbook_detail import _CategoryItem

    item = _CategoryItem(
        cat_id="confidentiality",
        name="Confidentiality",
        default_position="preferred",
        description="Handles [intentionally omitted] terms",
        exemplars=["mutual NDA [standard]"],
    )

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.screen.mount(item)
        await pilot.pause()
        text = str(item.query_one(Label).render())
        assert "[preferred]" in text, text
        assert "[intentionally omitted]" in text, text
        assert "[standard]" in text, text


@pytest.mark.asyncio
async def test_import_preview_preserves_brackets(tmp_path: Path) -> None:
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.tabs.playbooks import _ImportModal

    pb_path = tmp_path / "bracket-pb.yaml"
    pb_path.write_text(_BRACKETED_YAML, encoding="utf-8")

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        modal = _ImportModal()
        app.push_screen(modal)
        await pilot.pause()

        modal._show_preview(pb_path)
        await pilot.pause()

        text = str(modal.query_one("#preview-content").render())
        assert "[scope]" in text, text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/integration/tui/test_playbook_markup.py -q`

Expected: FAIL on `test_playbook_category_item_preserves_brackets` — `[preferred]`,
`[intentionally omitted]`, and `[standard]` are all stripped. The preview test fails on
`"[scope]"` (the preview data is parsed as markup and the bracket text is stripped).

- [ ] **Step 3: Write minimal implementation**

In `src/openreview_cli/tui/screens/playbook_detail.py`, line 30, disable markup for the
category item (all of name/description/exemplars are user-authored YAML):

```python
        super().__init__(
            Label(
                f"{name} [{default_position}]\n  {description}\n  Exemplars: {ex_str}",
                markup=False,
            )
        )
```

In `src/openreview_cli/tui/tabs/playbooks.py`, add the import at the top:

```python
from rich.markup import escape
```

Then escape the data-derived lines and the exception text in `_show_preview`
(lines 190–211). Replace the three `update` calls:

```python
            self.query_one("#preview-content", Static).update(escape("\n".join(lines)))
            self.query_one("#preview-validation", Label).update("[green]\u2713 Valid playbook[/]")
            self._path = path
        except Exception as exc:
            self.query_one("#preview-content", Static).update(
                f"[red]Validation error:[/]\n{escape(str(exc))}"
            )
            self.query_one("#preview-validation", Label).update(f"[red]\u2717 {escape(str(exc))}[/]")
            self._path = None
```

> **Note:** only the *data* line is escaped; the intentional `[green]`/`[red]` validation
> markup on the separate label is preserved.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/integration/tui/test_playbook_markup.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/openreview_cli/tui/screens/playbook_detail.py \
        src/openreview_cli/tui/tabs/playbooks.py \
        tests/integration/tui/test_playbook_markup.py
git commit -m "fix(tui): preserve bracketed text in playbook preview and detail"
```

---

### Task 5: Emit ANSI colours in the terminal report (P1 / C1)

**Files:**
- Modify: `src/openreview_cli/review/report.py` (imports at top; `format_terminal` signature and Console creation, lines 21–48)
- Test: `tests/unit/test_report_color.py` (create)

**Interfaces:**
- Produces: `format_terminal(report, privacy_footer=None, *, color: bool | None = None) -> str`
  — `color=None` auto-detects terminal capability; `color=True` forces ANSI; `color=False`
  forces plain text.
- Produces: `_terminal_supports_color() -> bool` (module-level, monkeypatchable in tests).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_report_color.py`:

```python
"""Unit tests for terminal report colour output (P1/C1)."""

from __future__ import annotations

from datetime import UTC, datetime

from openreview_cli.review.models import (
    ClauseAssessment,
    DocMeta,
    Position,
    QAVerdict,
    ReviewReport,
    ReviewSummary,
)
from openreview_cli.review.report import format_terminal


def _make_report() -> ReviewReport:
    ca = ClauseAssessment(
        clause_id="c1",
        clause_text="Confidentiality term.",
        playbook_category="confidentiality-term",
        position=Position.PREFERRED,
        confidence=0.92,
        citation="clause c1",
        qa_verdict=QAVerdict.agree,
        extraction_model="m1",
        qa_model="m1",
    )
    dm = DocMeta(filename="nda.docx", page_count=1, clause_count=1, pii_stripped=True)
    return ReviewReport(
        document=dm,
        assessments=[ca],
        summary=ReviewSummary(preferred_count=1, avg_confidence=0.92),
        playbook_id="precheck-nda-v1",
        generated_at=datetime.now(UTC),
    )


def test_format_terminal_color_true_emits_ansi() -> None:
    assert "\x1b[" in format_terminal(_make_report(), color=True)


def test_format_terminal_color_false_has_no_ansi() -> None:
    assert "\x1b[" not in format_terminal(_make_report(), color=False)


def test_format_terminal_default_respects_terminal(monkeypatch) -> None:
    monkeypatch.setattr("openreview_cli.review.report._terminal_supports_color", lambda: True)
    assert "\x1b[" in format_terminal(_make_report())

    monkeypatch.setattr("openreview_cli.review.report._terminal_supports_color", lambda: False)
    assert "\x1b[" not in format_terminal(_make_report())


def test_plain_text_content_is_unchanged() -> None:
    """Enabling colour must not alter the visible text."""
    colored = format_terminal(_make_report(), color=True)
    plain = format_terminal(_make_report(), color=False)
    assert "NDA Review Report" in plain
    assert "● OK" in plain
    assert "● OK" in colored  # substring survives the ANSI wrappers
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_report_color.py -q`

Expected: FAIL — `TypeError: format_terminal() got an unexpected keyword argument 'color'`
(and `AttributeError` for the missing `_terminal_supports_color`).

- [ ] **Step 3: Write minimal implementation**

In `src/openreview_cli/review/report.py`, add imports near the top (after `import json`):

```python
import os
import sys
```

Add the detector just below `logger = logging.getLogger(__name__)` (line 18):

```python
def _terminal_supports_color() -> bool:
    """Return True when stdout is an interactive terminal that supports colour."""
    if os.environ.get("NO_COLOR"):
        return False
    return bool(getattr(sys.stdout, "isatty", lambda: False)())
```

Change the signature and Console construction in `format_terminal` (lines 21–48):

```python
def format_terminal(  # noqa: PLR0912, PLR0915  # ponytail: function extraction would add more complexity
    report: ReviewReport,
    privacy_footer: str | None = None,
    *,
    color: bool | None = None,
) -> str:
    """Format a ``ReviewReport`` as a human-readable terminal string.

    ...
    color : bool | None
        ``None`` (default) auto-detects whether ``sys.stdout`` supports colour.
        ``True`` forces ANSI output, ``False`` forces plain text.
    """
    # ponytail: safety net — ensure colors are assigned for directly-constructed reports
    if report.assessments and report.assessments[0].color is None:
        from openreview_cli.review.colors import assign_colors

        assign_colors(report.assessments, threshold=report.confidence_threshold)
    from rich.console import Console
    from rich.table import Table

    use_color = _terminal_supports_color() if color is None else color
    buf = io.StringIO()
    console = Console(
        width=100,
        file=buf,
        force_terminal=use_color,
        color_system="truecolor" if use_color else None,
        no_color=not use_color,
    )
```

The rest of the function is unchanged. No caller changes are required: `_emit_reviews`
(lines 155–186 of `app.py`) already calls
`format_terminal(report, privacy_footer=privacy_footer_ref)` and will now colourise in an
interactive terminal while remaining plain under pipes/`CliRunner`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_report_color.py tests/unit/test_review_report.py tests/unit/test_three_color_report.py -q`
Expected: PASS (new tests pass; existing plain-text assertions still pass because pytest's
captured stdout is not a TTY).

- [ ] **Step 5: Commit**

```bash
git add src/openreview_cli/review/report.py tests/unit/test_report_color.py
git commit -m "fix(review): emit ANSI colors in terminal report"
```

---

### Task 6: Quiet CLI logging by default (P1 / C2)

**Files:**
- Modify: `src/openreview_cli/app.py` (add `_log_level` near `_validate_enum`, ~line 55; `_init` lines 188–192; `_root` lines 300–315)
- Test: `tests/unit/test_cli_logging.py` (create)

**Interfaces:**
- Produces: `_log_level(debug: bool, verbose: bool) -> int` — module-level in
  `openreview_cli.app`.
- Changes: `_init(debug: bool = False, verbose: bool = False) -> None`; root CLI gains
  `-v/--verbose`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_cli_logging.py`:

```python
"""Unit/integration tests for CLI logging verbosity (P1/C2)."""

from __future__ import annotations

import logging


def test_log_level_default_is_warning() -> None:
    from openreview_cli.app import _log_level

    assert _log_level(debug=False, verbose=False) == logging.WARNING


def test_log_level_verbose_is_info() -> None:
    from openreview_cli.app import _log_level

    assert _log_level(debug=False, verbose=True) == logging.INFO


def test_log_level_debug_is_debug() -> None:
    from openreview_cli.app import _log_level

    assert _log_level(debug=True, verbose=False) == logging.DEBUG


def test_cli_emits_no_info_lines_by_default() -> None:
    """A normal command must not print INFO startup lines to stderr."""
    from typer.testing import CliRunner

    from openreview_cli.app import app

    result = CliRunner().invoke(app, ["gateway", "costs"])
    assert result.exit_code == 0, result.output
    assert "config loaded" not in result.stderr
    assert "auth configured" not in result.stderr
    assert "database initialized" not in result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_cli_logging.py -q`

Expected: FAIL — `ImportError: cannot import name '_log_level'`, and
`test_cli_emits_no_info_lines_by_default` fails with stderr containing
`[INFO] config loaded`, `[INFO] auth configured`, `[INFO] database initialized`.

- [ ] **Step 3: Write minimal implementation**

In `src/openreview_cli/app.py`, add the helper after `_validate_enum` (~line 55):

```python
def _log_level(debug: bool, verbose: bool) -> int:
    """Resolve the root log level from CLI flags (default: quiet)."""
    if debug:
        return logging.DEBUG
    if verbose:
        return logging.INFO
    return logging.WARNING
```

Edit `_init` (line 188) to accept and use `verbose`:

```python
def _init(debug: bool = False, verbose: bool = False) -> None:
    log_dir = get_log_dir()
    log_file = log_dir / "openreview.log"
    log_dir.mkdir(parents=True, exist_ok=True)
    _level = _log_level(debug=debug, verbose=verbose)
```

Edit the root callback (lines 300–315) to add the option and pass it through:

```python
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug-level logging.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable info-level logging (startup diagnostics).",
    ),
) -> None:
    _init(debug=debug, verbose=verbose)
```

> `-v/--verbose` on the root group does not collide with the per-subcommand `--verbose`
> flags (`precheck review`, `negotiate`): Click parses the group flag before the
> subcommand name and the subcommand flag after it. No subcommand uses `-v` (verified).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_cli_logging.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/openreview_cli/app.py tests/unit/test_cli_logging.py
git commit -m "fix(cli): default logging to WARNING unless --verbose or --debug"
```

---

### Task 7: Replace hardcoded `/tmp` export paths with `./review_results` (P2 / T6)

**Files:**
- Modify: `src/openreview_cli/tui/screens/result.py` (lines 100, 243, 270)
- Modify: `src/openreview_cli/tui/screens/negotiation_result.py` (lines 81, 89)
- Test: `tests/integration/tui/test_result_screen.py` (append), `tests/integration/tui/test_negotiation_result_screen.py` (append)

**Interfaces:**
- Consumes: `openreview_cli.review.memo.filename.DEFAULT_OUTPUT_DIR` (`Path("review_results")`).
- Produces: none.

- [ ] **Step 1: Write the failing tests**

Append to `tests/integration/tui/test_result_screen.py`:

```python
@pytest.mark.asyncio
async def test_save_uses_relative_review_results_dir(tmp_path, monkeypatch) -> None:
    """TUI export must default to ./review_results, not /tmp (T6)."""
    from pathlib import Path

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    monkeypatch.chdir(tmp_path)
    report = _make_mock_report([_make_mock_assessment()])

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch("openreview_cli.review.memo.exporter.MemoExporter") as mock_exporter_cls:
            mock_exporter = MagicMock()
            mock_exporter.export.return_value = {
                MagicMock(): Path("review_results") / "review-result.md"
            }
            mock_exporter_cls.return_value = mock_exporter

            app.push_screen(ResultScreen(reports=[report], mode="precheck"))
            await pilot.pause()

            await pilot.click("#btn-export")
            await pilot.pause()
            await pilot.click("#btn-fmt-md")
            await pilot.pause()

            label = str(app.screen.query_one("#save-file-path").render())
            assert "review_results" in label, label
            assert "/tmp" not in label, label

            await pilot.click("#btn-save")
            await pilot.pause()

            assert mock_exporter_cls.call_args.kwargs["output_dir"] == Path("review_results")
```

Append to `tests/integration/tui/test_negotiation_result_screen.py`:

```python
@pytest.mark.asyncio
async def test_negotiation_export_writes_to_review_results(tmp_path, monkeypatch) -> None:
    """Negotiation export must land in ./review_results, not /tmp (T6)."""
    from unittest.mock import MagicMock, patch

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.negotiation_result import NegotiationResultScreen

    monkeypatch.chdir(tmp_path)
    report = MagicMock()
    report.disclaimer = "Advisory only."

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch("openreview_cli.negotiation.report.format_memo", return_value="memo [x]"):
            app.push_screen(NegotiationResultScreen(report=report))
            await pilot.pause()
            await pilot.click("#btn-export")
            await pilot.pause()

    out = tmp_path / "review_results" / "negotiation-result.md"
    assert out.exists(), out
    assert out.read_text(encoding="utf-8") == "memo [x]"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/integration/tui/test_result_screen.py::test_save_uses_relative_review_results_dir tests/integration/tui/test_negotiation_result_screen.py::test_negotiation_export_writes_to_review_results -q`

Expected: FAIL — the result test sees `/tmp/review-result.md` in the label and
`Path("/tmp")` as `output_dir`; the negotiation test finds no file under the tmp cwd.

- [ ] **Step 3: Write minimal implementation**

In `src/openreview_cli/tui/screens/result.py`, add the import near the existing
`from openreview_cli.review.models import ...`:

```python
from openreview_cli.review.memo.filename import DEFAULT_OUTPUT_DIR
```

Line 100 — the informational label:

```python
                    yield Label(f"The file will be saved to {DEFAULT_OUTPUT_DIR}/")
```

Line 243 — the file-path label:

```python
            self.query_one("#save-file-path", Label).update(
                f"File: {DEFAULT_OUTPUT_DIR}/review-result{ext}"
            )
```

Line 270 — the exporter call:

```python
            exporter = MemoExporter(
                report=self._reports[0],
                mode=self._mode,
                output_dir=DEFAULT_OUTPUT_DIR,
                formats={memo_fmt},
            )
```

In `src/openreview_cli/tui/screens/negotiation_result.py`, add the import near the
`from pathlib import Path` line:

```python
from openreview_cli.review.memo.filename import DEFAULT_OUTPUT_DIR
```

Replace the `_do_export` tail (lines 80–91); also update the docstring on line 81:

```python
    async def _do_export(self) -> None:
        """Write memo to a .md file under ./review_results/."""
        if self._report is None:
            self.notify("No report to export.", severity="error")
            return
        from openreview_cli.negotiation.report import format_memo

        try:
            memo_text = format_memo(self._report)
            out_dir = DEFAULT_OUTPUT_DIR
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / "negotiation-result.md"
            out_path.write_text(memo_text, encoding="utf-8")
            self.notify(f"Exported to {out_path}", severity="information", timeout=5)
        except Exception as exc:
            self.notify(f"Export error: {exc}", severity="error")
```

> `MemoExporter.export()` already calls `resolve_output_dir(self.output_dir)`, which creates
> `review_results/` on demand, so `result.py` needs no `mkdir`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/integration/tui/test_result_screen.py tests/integration/tui/test_negotiation_result_screen.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/openreview_cli/tui/screens/result.py \
        src/openreview_cli/tui/screens/negotiation_result.py \
        tests/integration/tui/test_result_screen.py \
        tests/integration/tui/test_negotiation_result_screen.py
git commit -m "fix(tui): default memo exports to ./review_results instead of /tmp"
```

---

### Task 8: Drive the review progress bar from pipeline events (P1 / T5)

**Files:**
- Modify: `src/openreview_cli/review/runner.py` (TYPE_CHECKING import ~line 12; `run_review` signature lines 26–40; call site lines 128–141; `_run_review_doc_pipeline` signature lines 207–221 and `_progress` lines 307–321)
- Modify: `src/openreview_cli/tui/domain/review.py` (lines 26–55)
- Modify: `src/openreview_cli/tui/screens/progress.py` (lines 1–120)
- Test: `tests/unit/test_review_runner_progress.py` (create), `tests/integration/tui/test_progress_screen.py` (append)

**Interfaces:**
- Produces: `run_review(..., progress_callback: ProgressCallback | None = None)`.
- Produces: `run_review_via_tui(..., progress_callback: ProgressCallback | None = None)`.
- Consumes: `openreview_cli.pipeline.progress.ProgressEvent`, `ProgressCallback`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_review_runner_progress.py`:

```python
"""Unit test for progress_callback forwarding in run_review (P1/T5)."""

from __future__ import annotations


def test_run_review_forwards_progress_callback(monkeypatch, tmp_path) -> None:
    from openreview_cli.review import runner

    doc = tmp_path / "doc.pdf"
    doc.write_bytes(b"%PDF-1.4")

    seen: dict[str, object] = {}

    def fake_pipeline(**kwargs):
        seen.update(kwargs)
        return None  # no report produced; run_review skips the document

    monkeypatch.setattr(runner, "load_bundled", lambda: object())
    monkeypatch.setattr(runner, "_run_review_doc_pipeline", fake_pipeline)

    sentinel = lambda event: None  # noqa: E731
    runner.run_review([str(doc)], progress_callback=sentinel)

    assert seen.get("progress_callback") is sentinel
```

Append to `tests/integration/tui/test_progress_screen.py` (the test imports `asyncio`
locally, matching the file's existing style of function-local imports):

```python
@pytest.mark.asyncio
async def test_progress_screen_advances_on_pipeline_events() -> None:
    """ProgressBar and step labels must reflect emitted pipeline events (P1/T5)."""
    import asyncio

    from textual.widgets import ProgressBar

    from openreview_cli.pipeline.progress import ProgressEvent
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.progress import ProgressScreen

    def fake_run_via_tui(**kwargs):  # noqa: ANN003, ANN201
        cb = kwargs["progress_callback"]
        cb(ProgressEvent(0, 3, "parse", "running"))
        cb(ProgressEvent(0, 3, "parse", "completed"))
        cb(ProgressEvent(1, 3, "strip", "running"))
        cb(ProgressEvent(1, 3, "strip", "completed"))
        cb(ProgressEvent(2, 3, "review", "running"))
        cb(ProgressEvent(2, 3, "review", "completed"))
        return []

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch(
            "openreview_cli.tui.domain.review.run_review_via_tui",
            side_effect=fake_run_via_tui,
        ):
            app.call_later = lambda _cb: None  # type: ignore[method-assign]
            app.push_screen(ProgressScreen(paths=[], mode="precheck"))
            await asyncio.sleep(0.4)  # let the 12 yield-points + worker thread finish
            await pilot.pause()

            screen = _get_progress_screen_checked(app)
            bar = screen.query_one("#progress-bar", ProgressBar)
            assert bar.progress == 5

            for sid in ("step-parse", "step-pii", "step-extract", "step-qa", "step-report"):
                text = str(screen.query_one(f"#{sid}").render())
                assert "\u2713" in text, (sid, text)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/test_review_runner_progress.py -q`

Expected: FAIL — `TypeError: run_review() got an unexpected keyword argument 'progress_callback'`.

Run: `.venv/bin/pytest tests/integration/tui/test_progress_screen.py::test_progress_screen_advances_on_pipeline_events -q`

Expected: FAIL — `KeyError: 'progress_callback'` in `fake_run_via_tui` (the screen never
forwards one), so no step advances.

- [ ] **Step 3: Write minimal implementation**

**3a. `src/openreview_cli/review/runner.py`**

Extend the TYPE_CHECKING import block (lines 12–15):

```python
if TYPE_CHECKING:
    from collections.abc import Sequence

    from openreview_cli.pipeline.progress import ProgressCallback, ProgressEvent
```

Add the parameter to `run_review` (after `allow_partial_pii: bool = False,`, line 39):

```python
    progress_callback: ProgressCallback | None = None,
```

Pass it through at the call site (lines 128–141):

```python
            result = _run_review_doc_pipeline(
                doc_path=doc_path,
                playbook=playbook,
                playbook_version=playbook_version,
                extraction_model=extraction_model,
                qa_model=qa_model,
                no_pii=no_pii,
                verbose=verbose,
                confidence_threshold=confidence_threshold,
                mode_threshold_overrides=mode_threshold_overrides,
                mode=mode,
                session_id=doc_session_id,
                allow_partial_pii=allow_partial_pii,
                progress_callback=progress_callback,
            )
```

Add the parameter to `_run_review_doc_pipeline` (after `allow_partial_pii: bool = False,`,
line 219):

```python
    progress_callback: ProgressCallback | None = None,
```

Extend the internal `_progress` callback (lines 307–315) to forward to the caller:

```python
    def _progress(event: ProgressEvent) -> None:
        if verbose:
            print(
                f"[{event.stage_index + 1}/{event.total_stages}] {event.stage_name}..."
                if event.status == "running"
                else f"[{event.stage_index + 1}/{event.total_stages}] "
                f"{event.stage_name} {event.status}",
                file=sys.stderr,
            )
        if progress_callback is not None:
            progress_callback(event)
```

**3b. `src/openreview_cli/tui/domain/review.py`**

Add `from typing import TYPE_CHECKING` to the import block, add the TYPE_CHECKING import,
add the parameter, and forward it:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openreview_cli.pipeline.progress import ProgressCallback
```

```python
def run_review_via_tui(
    paths: list[str],
    mode: str = "precheck",
    playbook_path: str | None = None,
    playbook_id: str | None = None,
    disable_pii: bool = False,
    extraction_model: str = "extraction",
    qa_model: str | None = None,
    confidence_threshold: float = 0.7,
    verbose: bool = False,
    client_id: str | None = None,
    cancel_requested: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> list[ReviewReport]:
    """Run a review from the TUI with PII stripping enabled by default."""
    if cancel_requested or _tui_cancel_requested:
        return []

    reports = run_review(
        paths=paths,
        playbook_path=playbook_path,
        playbook_id=playbook_id,
        extraction_model=extraction_model,
        qa_model=qa_model,
        no_pii=disable_pii,
        verbose=verbose,
        confidence_threshold=confidence_threshold,
        mode=mode,
        progress_callback=progress_callback,
    )
```

(Keep the rest of the function — DB persistence — unchanged.)

**3c. `src/openreview_cli/tui/screens/progress.py`**

Replace the imports and add module constants:

```python
import asyncio
import contextlib
import time
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, ProgressBar, Static

from openreview_cli.pipeline.progress import ProgressEvent

_STEP_IDS: tuple[str, ...] = (
    "step-parse",
    "step-pii",
    "step-extract",
    "step-qa",
    "step-report",
)
_STEP_LABELS: tuple[str, ...] = (
    "Parsing document",
    "Stripping PII",
    "Extracting clauses",
    "QA verification",
    "Building report",
)
_STAGE_START: dict[str, int] = {"parse": 0, "strip": 1, "review": 2}
_MARKERS: dict[str, str] = {"pending": "\u25cb", "active": "\u25cf", "done": "\u2713", "failed": "\u2717"}
```

Replace `compose` (lines 52–63) so the step rows come from the constants:

```python
    def compose(self) -> ComposeResult:
        with Vertical(id="progress-container"):
            yield Static("Review in progress...", id="title")
            for step_id, text in zip(_STEP_IDS, _STEP_LABELS, strict=True):
                yield Static(f"{_MARKERS['pending']} {text}", id=step_id)
            yield ProgressBar(id="progress-bar", total=len(_STEP_IDS))
            yield Label("Elapsed: 0s", id="elapsed-time")
        with Horizontal(id="nav-buttons"):
            yield Button("Cancel review", id="btn-cancel", variant="error")
```

In `_run_review` (lines 77–120), run the blocking call off the event loop and pass the
callback. Replace the `try:` body start:

```python
        try:
            reports = await asyncio.to_thread(
                run_review_via_tui,
                paths=self._paths,
                mode=self._mode,
                disable_pii=self._disable_pii,
                playbook_id=self._playbook_id,
                playbook_path=self._playbook_path,
                extraction_model=self._extraction_model,
                qa_model=self._qa_model,
                confidence_threshold=self._confidence_threshold,
                client_id=self._client_id,
                cancel_requested=self._cancelled,
                progress_callback=self._on_progress_event,
            )
```

Add the three methods after `_update_elapsed` (before `_run_review`):

```python
    def _on_progress_event(self, event: ProgressEvent) -> None:
        """Forward a pipeline event from the worker thread to the UI thread."""
        try:
            self.app.call_from_thread(self._apply_progress_event, event)
        except Exception:
            # App not mounted / shutting down — progress is best-effort.
            pass

    def _apply_progress_event(self, event: ProgressEvent) -> None:
        index = _STAGE_START.get(event.stage_name)
        if index is None:
            return
        if event.status == "running":
            self._set_step(index, "active")
            self._set_bar(index)
        elif event.status in ("completed", "skipped"):
            self._set_step(index, "done")
            if event.stage_name == "review":
                for i in range(index, len(_STEP_IDS)):
                    self._set_step(i, "done")
                self._set_bar(len(_STEP_IDS))
            else:
                self._set_bar(index + 1)
        elif event.status == "failed":
            self._set_step(index, "failed")

    def _set_step(self, index: int, state: str) -> None:
        with contextlib.suppress(Exception):
            label = self.query_one(f"#{_STEP_IDS[index]}", Static)
            label.update(f"{_MARKERS[state]} {_STEP_LABELS[index]}")

    def _set_bar(self, progress: int) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#progress-bar", ProgressBar).update(progress=progress)
```

> The `for _ in range(12): await asyncio.sleep(0.01)` yield loop stays; `asyncio.to_thread`
> then runs `run_review_via_tui` on a worker thread, so the bar and step labels can update
> while the pipeline runs. `ReviewStage` is preceded by `ParseStage` and `StripStage`
> (`runner.py:302-305`), so the `parse`/`strip`/`review` stage names map 1:1 onto the five
> UI steps (the `review` stage covers extract + QA + report). When `--no-pii` is used the
> strip stage is absent and `step-pii` simply stays pending.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_review_runner_progress.py tests/integration/tui/test_progress_screen.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/openreview_cli/review/runner.py \
        src/openreview_cli/tui/domain/review.py \
        src/openreview_cli/tui/screens/progress.py \
        tests/unit/test_review_runner_progress.py \
        tests/integration/tui/test_progress_screen.py
git commit -m "feat(tui): drive review progress bar from pipeline events"
```

---

### Task 9: Drive the negotiation progress bar from phase events (P1 / T5)

**Files:**
- Modify: `src/openreview_cli/tui/domain/negotiation.py` (lines 22–108)
- Modify: `src/openreview_cli/tui/screens/negotiation_progress.py` (lines 1–113)
- Test: `tests/unit/tui/test_negotiation_domain_wrapper.py` (append), `tests/integration/tui/test_negotiation_progress_screen.py` (create)

**Interfaces:**
- Produces: `run_negotiation_via_tui(..., progress_callback: ProgressCallback | None = None)`.
  Emits eight `ProgressEvent`s (running/completed for stage names `parse`, `assess`,
  `solve`, `report`; `total_stages=4`).
- Consumes: `openreview_cli.pipeline.progress.ProgressEvent`, `ProgressCallback`.

- [ ] **Step 1: Write the failing tests**

Append this method to `TestNegotiationDomainWrapper` in
`tests/unit/tui/test_negotiation_domain_wrapper.py`:

```python
    def test_emits_progress_events(self, tmp_path: Path) -> None:
        """The wrapper emits running/completed events for each phase (P1/T5)."""
        from openreview_cli.negotiation.models import NegotiationReport
        from openreview_cli.parsing.models import Clause, Document

        doc = tmp_path / "test.pdf"
        doc.write_text("dummy pdf content")
        events: list = []

        with (
            patch("openreview_cli.parsing.stream.parse_document") as mock_parse,
            patch("openreview_cli.review.playbook.load_bundled") as mock_playbook,
            patch("openreview_cli.negotiation.run_negotiation") as mock_run,
        ):
            mock_parse.return_value = (
                Document(
                    source_path=Path("test.pdf"),
                    format="pdf",
                    page_count=1,
                    clause_count=1,
                    parse_duration_seconds=0.1,
                    warnings=[],
                ),
                [
                    Clause(
                        id="c1",
                        title="Clause 1",
                        text="Some clause text.",
                        level=1,
                        parent_id=None,
                        source_page=None,
                        source_paragraph=1,
                        source_span=None,
                    )
                ],
            )

            class MockPB:
                id = "bundled"
                categories: list = []

            mock_playbook.return_value = MockPB()
            mock_run.return_value = NegotiationReport()

            result = _neg_mod.run_negotiation_via_tui(
                str(doc), progress_callback=events.append
            )

        assert result is not None
        assert [(e.stage_name, e.status) for e in events] == [
            ("parse", "running"),
            ("parse", "completed"),
            ("assess", "running"),
            ("assess", "completed"),
            ("solve", "running"),
            ("solve", "completed"),
            ("report", "running"),
            ("report", "completed"),
        ]
```

Create `tests/integration/tui/test_negotiation_progress_screen.py`:

```python
"""Integration test: negotiation progress bar advances from phase events (P1/T5)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_negotiation_progress_advances_on_phase_events() -> None:
    from textual.widgets import ProgressBar

    from openreview_cli.pipeline.progress import ProgressEvent
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.negotiation_progress import NegotiationProgressScreen

    names = ("parse", "assess", "solve", "report")

    def fake_run_via_tui(**kwargs):  # noqa: ANN003, ANN201
        cb = kwargs["progress_callback"]
        for i, name in enumerate(names):
            cb(ProgressEvent(i, 4, name, "running"))
            cb(ProgressEvent(i, 4, name, "completed"))
        return None

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch(
            "openreview_cli.tui.domain.negotiation.run_negotiation_via_tui",
            side_effect=fake_run_via_tui,
        ):
            app.call_later = lambda _cb: None  # type: ignore[method-assign]
            screen = NegotiationProgressScreen(doc_path="test.pdf")
            app.push_screen(screen)
            await asyncio.sleep(0.4)
            await pilot.pause()

            bar = screen.query_one("#progress-bar", ProgressBar)
            assert bar.progress == 4
            for sid in ("step-parse", "step-assess", "step-solve", "step-report"):
                text = str(screen.query_one(f"#{sid}").render())
                assert "\u2713" in text, (sid, text)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/tui/test_negotiation_domain_wrapper.py::TestNegotiationDomainWrapper::test_emits_progress_events -q`

Expected: FAIL — `TypeError: run_negotiation_via_tui() got an unexpected keyword argument 'progress_callback'`.

Run: `.venv/bin/pytest tests/integration/tui/test_negotiation_progress_screen.py -q`

Expected: FAIL — `KeyError: 'progress_callback'` in `fake_run_via_tui`.

- [ ] **Step 3: Write minimal implementation**

**3a. `src/openreview_cli/tui/domain/negotiation.py`**

Add the imports and a small emit helper:

```python
if TYPE_CHECKING:
    from openreview_cli.negotiation.models import NegotiationReport
    from openreview_cli.pipeline.progress import ProgressCallback

from openreview_cli.pipeline.progress import ProgressEvent

_TOTAL_STAGES = 4


def _emit(
    callback: ProgressCallback | None,
    index: int,
    stage_name: str,
    status: str,
) -> None:
    if callback is not None:
        callback(
            ProgressEvent(
                stage_index=index,
                total_stages=_TOTAL_STAGES,
                stage_name=stage_name,
                status=status,  # type: ignore[arg-type]
            )
        )
```

Change the signature and wrap each phase (lines 22–108):

```python
def run_negotiation_via_tui(
    doc_path: str,
    *,
    solver: str = "qre",
    rationality: float = 1.0,
    depth: int = 2,
    weights: dict[str, float] | None = None,
    confidence_threshold: float = 0.7,
    playbook_path: str | None = None,
    cancel_requested: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> NegotiationReport | None:
    """Run negotiation from the TUI — all local, no external API calls."""
    if cancel_requested or _tui_cancel_requested:
        return None

    path = Path(doc_path)

    # ── lazy imports: never pull gateway/litellm at module level ──
    from openreview_cli.negotiation import run_negotiation
    from openreview_cli.parsing.stream import parse_document
    from openreview_cli.review.extraction import match_category as _match_category
    from openreview_cli.review.models import ClauseAssessment, Position, QAVerdict
    from openreview_cli.review.playbook import load_bundled, load_playbook

    if playbook_path:
        pb_path = Path(playbook_path)
        if not pb_path.exists():
            raise FileNotFoundError(f"Playbook not found: {playbook_path}")
        playbook = load_playbook(pb_path)
    else:
        playbook = load_bundled()

    _emit(progress_callback, 0, "parse", "running")
    _doc, clauses = parse_document(str(path))
    _emit(progress_callback, 0, "parse", "completed")

    _emit(progress_callback, 1, "assess", "running")
    assessments: list[ClauseAssessment] = []
    for clause in clauses:
        # ... unchanged body ...
        assessments.append(assessment)
    _emit(progress_callback, 1, "assess", "completed")

    if _tui_cancel_requested:
        return None

    if not assessments:
        return None

    _emit(progress_callback, 2, "solve", "running")
    report = run_negotiation(
        assessments=assessments,
        solver=solver,
        weights=weights,
        rationality=rationality,
        depth=depth,
        confidence_threshold=confidence_threshold,
        playbook_id=playbook.id if hasattr(playbook, "id") else "bundled",
    )
    _emit(progress_callback, 2, "solve", "completed")

    if cancel_requested or _tui_cancel_requested:
        return None

    _emit(progress_callback, 3, "report", "running")
    _emit(progress_callback, 3, "report", "completed")
    return report
```

> Keep the existing assessment-building loop body verbatim between the `assess` events;
> only the surrounding `_emit` calls are added.

**3b. `src/openreview_cli/tui/screens/negotiation_progress.py`**

Apply the same constants/methods pattern as Task 8:

```python
import asyncio
import contextlib
import time
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, ProgressBar, Static

from openreview_cli.pipeline.progress import ProgressEvent

_STEP_IDS: tuple[str, ...] = ("step-parse", "step-assess", "step-solve", "step-report")
_STEP_LABELS: tuple[str, ...] = (
    "Parsing document",
    "Building assessments",
    "Computing equilibria",
    "Generating report",
)
_STAGE_START: dict[str, int] = {"parse": 0, "assess": 1, "solve": 2, "report": 3}
_MARKERS: dict[str, str] = {"pending": "\u25cb", "active": "\u25cf", "done": "\u2713", "failed": "\u2717"}
```

`compose` becomes:

```python
    def compose(self) -> ComposeResult:
        with Vertical(id="progress-container"):
            yield Static("Negotiation in progress...", id="title")
            for step_id, text in zip(_STEP_IDS, _STEP_LABELS, strict=True):
                yield Static(f"{_MARKERS['pending']} {text}", id=step_id)
            yield ProgressBar(id="progress-bar", total=len(_STEP_IDS))
            yield Label("Elapsed: 0s", id="elapsed-time")
        with Horizontal(id="nav-buttons"):
            yield Button("Cancel negotiation", id="btn-cancel", variant="error")
```

`_run_negotiation` (lines 72–113) uses `asyncio.to_thread`:

```python
        try:
            report = await asyncio.to_thread(
                run_negotiation_via_tui,
                doc_path=self._doc_path,
                solver=self._solver,
                rationality=self._rationality,
                depth=self._depth,
                weights=self._weights,
                confidence_threshold=self._confidence_threshold,
                playbook_path=self._playbook_path,
                cancel_requested=self._cancelled,
                progress_callback=self._on_progress_event,
            )
```

Add the same `_on_progress_event`, `_apply_progress_event`, `_set_step`, `_set_bar` methods
as Task 8 (identical bodies; `_STAGE_START`/`_STEP_IDS`/`_STEP_LABELS`/`_MARKERS` resolve to
the negotiation constants in this module):

```python
    def _on_progress_event(self, event: ProgressEvent) -> None:
        """Forward a phase event from the worker thread to the UI thread."""
        try:
            self.app.call_from_thread(self._apply_progress_event, event)
        except Exception:
            pass

    def _apply_progress_event(self, event: ProgressEvent) -> None:
        index = _STAGE_START.get(event.stage_name)
        if index is None:
            return
        if event.status == "running":
            self._set_step(index, "active")
            self._set_bar(index)
        elif event.status in ("completed", "skipped"):
            self._set_step(index, "done")
            self._set_bar(index + 1)
        elif event.status == "failed":
            self._set_step(index, "failed")

    def _set_step(self, index: int, state: str) -> None:
        with contextlib.suppress(Exception):
            label = self.query_one(f"#{_STEP_IDS[index]}", Static)
            label.update(f"{_MARKERS[state]} {_STEP_LABELS[index]}")

    def _set_bar(self, progress: int) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#progress-bar", ProgressBar).update(progress=progress)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/tui/test_negotiation_domain_wrapper.py tests/integration/tui/test_negotiation_progress_screen.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/openreview_cli/tui/domain/negotiation.py \
        src/openreview_cli/tui/screens/negotiation_progress.py \
        tests/unit/tui/test_negotiation_domain_wrapper.py \
        tests/integration/tui/test_negotiation_progress_screen.py
git commit -m "feat(tui): drive negotiation progress bar from phase events"
```

---

## Full verification

After all nine tasks are committed, run the complete affected suites from a clean
working tree:

```bash
# Fast unit suites (no TUI startup cost)
.venv/bin/pytest tests/unit/test_tui_status_color.py \
                 tests/unit/test_report_color.py \
                 tests/unit/test_cli_logging.py \
                 tests/unit/test_review_runner_progress.py \
                 tests/unit/tui/test_negotiation_domain_wrapper.py \
                 tests/unit/test_review_report.py \
                 tests/unit/test_three_color_report.py -q

# TUI integration suites (slow: ~30s startup each)
.venv/bin/pytest tests/integration/tui/test_result_screen.py \
                 tests/integration/tui/test_negotiation_result_screen.py \
                 tests/integration/tui/test_playbook_markup.py \
                 tests/integration/tui/test_progress_screen.py \
                 tests/integration/tui/test_negotiation_progress_screen.py -m slow -q

# Lint the touched modules
.venv/bin/ruff check src/openreview_cli/app.py \
    src/openreview_cli/review/report.py \
    src/openreview_cli/review/runner.py \
    src/openreview_cli/tui/screens/result.py \
    src/openreview_cli/tui/screens/negotiation_result.py \
    src/openreview_cli/tui/screens/progress.py \
    src/openreview_cli/tui/screens/negotiation_progress.py \
    src/openreview_cli/tui/screens/playbook_detail.py \
    src/openreview_cli/tui/tabs/playbooks.py \
    src/openreview_cli/tui/domain/review.py \
    src/openreview_cli/tui/domain/negotiation.py
```

Expected: all suites PASS; `ruff` reports no new findings. Verify no escaped
`\[` sequences leak into rendered output and no `\x1b[` appears in
`format_terminal(..., color=False)` output.

## Self-Review

**Spec/defect coverage**

| Defect | Task(s) | Test |
| --- | --- | --- |
| 1. [P0] T2 bracketed text deleted | 1, 3, 4 | `test_result_screen_preserves_bracketed_clause_text`, `test_negotiation_result_preserves_bracketed_memo_text`, `test_playbook_category_item_preserves_brackets`, `test_import_preview_preserves_brackets` |
| 2. [P1] C1 ANSI colours stripped | 5 | `test_format_terminal_color_true_emits_ansi`, `test_format_terminal_color_false_has_no_ansi`, `test_format_terminal_default_respects_terminal` |
| 3. [P1] T3 invalid `[amber]` | 2 | `test_status_color_tag_maps_amber_to_valid_rich_color`, `test_raw_amber_is_not_a_valid_rich_color`, `test_result_screen_amber_clause_gets_valid_style` |
| 4. [P1] T5 fake progress bar | 8, 9 | `test_run_review_forwards_progress_callback`, `test_progress_screen_advances_on_pipeline_events`, `test_emits_progress_events`, `test_negotiation_progress_advances_on_phase_events` |
| 5. [P1] C2 INFO log spam | 6 | `test_log_level_*`, `test_cli_emits_no_info_lines_by_default` |
| 6. [P2] T6 hardcoded `/tmp` | 7 | `test_save_uses_relative_review_results_dir`, `test_negotiation_export_writes_to_review_results` |

**Placeholder scan:** none — every step contains runnable code/commands and exact paths.

**Type consistency:** `progress_callback: ProgressCallback | None` is the same type across
`run_review`, `run_review_via_tui`, and `run_negotiation_via_tui`. `status_color_tag(color: object) -> str`
and `_log_level(debug: bool, verbose: bool) -> int` are used with the exact signatures
defined in Tasks 2 and 6. `DEFAULT_OUTPUT_DIR: Path` is imported from
`openreview_cli.review.memo.filename` in both TUI files.
