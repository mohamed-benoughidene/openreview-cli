"""Integration tests for the graph build screen.

These drive the real parse path through the real screen: the document is put on
disk, the screen is pushed, its worker task is awaited (never a fixed sleep), and
the assertions read the rendered text. The ``slow`` marker is applied by
``tests/integration/tui/conftest.py``.

The save path is pinned from both sides: the file the TUI writes must equal the
graph the tree rendered, and it must be the graph ``openreview graph build``
produces from the same document's parsed JSON -- the only difference being
``paragraph_count``, which the CLI's ``parse --format json`` output does not
carry (see ``_shape``).
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from docx import Document
from textual.widgets import Button, Input, Static, Tree

from openreview_cli.graph.models import ContractGraph
from openreview_cli.graph.view import render_tree
from openreview_cli.tui.app import OpenReviewApp
from openreview_cli.tui.screens.graph_build import GraphBuildScreen
from openreview_cli.tui.screens.retrieve import (
    GRAPH_NO_PATH_MESSAGE,
    GRAPH_NOT_FOUND_MESSAGE,
    RetrieveScreen,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
FLAT_PDF = FIXTURES / "nda_with_pii.pdf"

FLAT_STATUS = (
    "\u2713 Built 5 nodes, 0 edges. No clause hierarchy was detected in this document, "
    "so the clauses are shown as a flat list."
)
NOTHING_TO_SAVE = "\u2717 Nothing to save: no clause graph was built."


# ── fixtures and helpers ──────────────────────────────────────────────


def _hierarchical_docx(tmp_path: Path) -> Path:
    """A numbered .docx: two Article headings, each with nested Sections.

    ``Heading 1`` / ``Heading 2`` map to parser levels and drive
    ``link_parent_ids``, so the graph gets real ``parent_child`` edges. The body
    text carries a bracketed variable, which is the markup-survival case.
    """
    path = tmp_path / "hier.docx"
    doc = Document()
    doc.add_heading("Article 1: Definitions", level=1)
    doc.add_paragraph("This Agreement sets forth the definitions used below.")
    doc.add_heading("Section 1.1: Confidential Information", level=2)
    doc.add_paragraph('Confidential Information means all information marked "[Party A]".')
    doc.add_heading("Section 1.2: Exclusions", level=2)
    doc.add_paragraph("Confidential Information does not include public information.")
    doc.add_heading("Article 2: Obligations", level=1)
    doc.add_paragraph("The [Party A] shall comply with Section 1.1.")
    doc.save(str(path))
    return path


def _text(screen: GraphBuildScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


def _header(screen: GraphBuildScreen) -> str:
    return _text(screen, "#graph-build-header")


def _status(screen: GraphBuildScreen) -> str:
    return _text(screen, "#graph-build-status")


def _tree(screen: GraphBuildScreen) -> Tree[Any]:
    return screen.query_one("#graph-tree", Tree)


def _rows(screen: GraphBuildScreen) -> list[str]:
    """The tree rows the widget is actually drawing, in display order.

    ``Tree.get_node_at_line`` reads the same line cache the renderer uses, so a
    collapsed subtree removes its rows from this list.
    """
    tree = _tree(screen)
    return [str(tree.get_node_at_line(index).label) for index in range(tree.last_line + 1)]


async def _open(pilot: Any, app: OpenReviewApp, path: Path) -> GraphBuildScreen:
    screen = GraphBuildScreen(path)
    app.push_screen(screen)
    await pilot.pause()
    assert isinstance(app.screen, GraphBuildScreen)
    return screen


async def _await_load(pilot: Any, screen: GraphBuildScreen) -> None:
    task = screen._load_task
    if task is not None:
        await task
    await pilot.pause()


def _saved_files(tmp_path: Path) -> list[Path]:
    return sorted(tmp_path.glob("*.graph.json"))


def _shape(graph: ContractGraph) -> dict[str, Any]:
    """Node and edge content, minus the one field the parsed-JSON format drops.

    ``openreview parse --format json`` emits ``id``/``title``/``text``/``level``/
    ``parent_id``/``source_page``/``source_paragraph`` -- not ``paragraph_count``,
    so a graph rebuilt from it records ``paragraph_count: None`` where a direct
    parse records the real count. Everything else round-trips identically, and
    that is asserted separately in the CLI-comparison test.
    """
    return {
        "nodes": [
            (
                node.id,
                node.label,
                node.text,
                node.level,
                node.parent_id,
                {k: v for k, v in node.metadata.items() if k != "paragraph_count"},
            )
            for node in graph.nodes.values()
        ],
        "edges": [
            (edge.source_id, edge.target_id, edge.edge_type.value, edge.metadata)
            for edge in graph.edges
        ],
    }


# ── 1. structure, labels, annotations ─────────────────────────────────


async def test_hierarchical_document_renders_the_expected_tree(tmp_path: Path) -> None:
    path = _hierarchical_docx(tmp_path)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, path)
        await _await_load(pilot, screen)

        assert _header(screen) == "hier.docx \u00b7 4 nodes \u00b7 3 edges"
        assert _status(screen) == (
            "\u2713 Built 4 nodes, 3 edges. Press S to save, or Esc to go back."
        )

        rows = _rows(screen)
        assert rows[0] == "hier.docx"
        assert len(rows) == 5  # root + two Articles + two Sections
        assert "Article 1  Article 1: Definitions This Agreement sets forth" in rows[1]
        assert "Section 1.1  Section 1.1: Confidential Information" in rows[2]
        assert "Section 1.2  Section 1.2: Exclusions" in rows[3]
        # The cross-reference annotation the CLI's `graph view` prints, verbatim.
        assert rows[4].endswith("[1 refs out]")

        # The hierarchy is real: the Sections are children of Article 1, not roots.
        root = _tree(screen).root
        assert [str(child.label).split("  ")[0] for child in root.children] == [
            "Article 1",
            "Article 2",
        ]
        article_one = root.children[0]
        assert [str(child.label).split("  ")[0] for child in article_one.children] == [
            "Section 1.1",
            "Section 1.2",
        ]
        assert article_one.is_expanded is True

        # This screen carries no metrics: that stays GraphSummaryScreen's job.
        assert "Health score" not in _header(screen) + _status(screen)
        assert app._exception is None


async def test_folding_changes_the_displayed_rows(tmp_path: Path) -> None:
    path = _hierarchical_docx(tmp_path)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, path)
        await _await_load(pilot, screen)

        assert len(_rows(screen)) == 5

        article_one = _tree(screen).root.children[0]
        article_one.collapse()
        await pilot.pause()

        collapsed = _rows(screen)
        assert len(collapsed) == 3  # root + two Articles; the Sections are folded away
        assert not any("Section 1.1" in row for row in collapsed)

        article_one.expand()
        await pilot.pause()
        assert len(_rows(screen)) == 5


async def test_contract_brackets_survive_in_the_tree(tmp_path: Path) -> None:
    """Rich markup must not eat ``[Party A]`` -- labels are ``Text``, not markup."""
    from rich.text import Text

    path = _hierarchical_docx(tmp_path)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, path)
        await _await_load(pilot, screen)

        article_two = _tree(screen).root.children[1]
        assert isinstance(article_two.label, Text)
        assert "[Party A]" in str(article_two.label)

        # And the widget draws it: the eight characters reach the rendered row.
        matching = [row for row in _rows(screen) if "[Party A]" in row]
        assert matching, _rows(screen)


# ── 2. the flat and empty documents ───────────────────────────────────


async def test_flat_document_says_there_is_no_hierarchy(tmp_path: Path) -> None:
    """A flat document must say so plainly, not look broken."""
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, FLAT_PDF)
        await _await_load(pilot, screen)

        assert _header(screen) == "nda_with_pii.pdf \u00b7 5 nodes \u00b7 0 edges"
        assert _status(screen) == FLAT_STATUS

        # Still a usable tree: five clauses, shown as a flat list of roots.
        assert len(_tree(screen).root.children) == 5
        assert len(_rows(screen)) == 6
        assert app._exception is None


async def test_empty_document_says_no_clauses_were_detected(tmp_path: Path) -> None:
    path = tmp_path / "blank.docx"
    Document().save(str(path))

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, path)
        await _await_load(pilot, screen)

        assert _header(screen) == "blank.docx \u00b7 0 nodes \u00b7 0 edges"
        assert _status(screen) == "No clauses detected in this document."
        assert len(_tree(screen).root.children) == 0


# ── 3. save: the only writer ──────────────────────────────────────────


async def test_the_save_key_is_the_only_writer(tmp_path: Path) -> None:
    """Nothing is written on mount, on parse or on Escape -- only on the save key."""
    path = _hierarchical_docx(tmp_path)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, path)
        await _await_load(pilot, screen)

        assert _saved_files(tmp_path) == []

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, GraphBuildScreen)
        assert _saved_files(tmp_path) == []

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, path)
        await _await_load(pilot, screen)

        await pilot.press("s")
        await pilot.pause()

        saved = _saved_files(tmp_path)
        assert saved == [tmp_path / "hier.graph.json"]
        assert _status(screen) == f"\u2713 Saved the clause graph to {saved[0]}."
        assert app._exception is None


async def test_saved_json_is_the_graph_the_tree_rendered(tmp_path: Path) -> None:
    """The CLI's own serializer, fed the CLI's own graph -- nothing recomputed."""
    path = _hierarchical_docx(tmp_path)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, path)
        await _await_load(pilot, screen)

        await pilot.press("s")
        await pilot.pause()

        rendered = screen._summary
        assert rendered is not None

    saved = tmp_path / "hier.graph.json"
    saved_graph = ContractGraph.from_file(saved)
    assert saved_graph.to_json() == rendered.graph.to_json()

    # The consumer's side: the real CLI reads it and prints the same tree.
    from typer.testing import CliRunner

    from openreview_cli.app import app as cli_app

    view = CliRunner().invoke(cli_app, ["graph", "view", str(saved)])
    assert view.exit_code == 0
    assert view.stdout.rstrip("\n") == render_tree(rendered.graph)


async def test_saved_json_matches_what_the_cli_graph_build_produces(tmp_path: Path) -> None:
    """``openreview graph build`` on this document's parsed JSON yields the same graph.

    The one delta is ``paragraph_count``, which ``parse --format json`` does not
    emit; both graphs are compared with that field excluded, and the delta itself
    is pinned so it cannot silently grow.
    """
    from typer.testing import CliRunner

    from openreview_cli.app import app as cli_app

    path = _hierarchical_docx(tmp_path)
    runner = CliRunner()

    parsed = tmp_path / "parsed.json"
    parse_run = runner.invoke(cli_app, ["parse", str(path), "--format", "json"])
    assert parse_run.exit_code == 0
    parsed.write_text(parse_run.stdout)

    cli_output = tmp_path / "cli.graph.json"
    build_run = runner.invoke(cli_app, ["graph", "build", str(parsed), "-o", str(cli_output)])
    assert build_run.exit_code == 0
    assert "4 nodes, 3 edges" in build_run.stdout

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, path)
        await _await_load(pilot, screen)
        await pilot.press("s")
        await pilot.pause()

    saved = ContractGraph.from_file(tmp_path / "hier.graph.json")
    cli_graph = ContractGraph.from_file(cli_output)

    assert _shape(saved) == _shape(cli_graph)
    assert {node.metadata["paragraph_count"] for node in saved.nodes.values()} == {1}
    assert {node.metadata["paragraph_count"] for node in cli_graph.nodes.values()} == {None}


async def test_save_failure_writes_one_line(tmp_path: Path) -> None:
    """A write that cannot happen is reported, not raised."""
    path = _hierarchical_docx(tmp_path)
    # ``<stem>.graph.json`` is where the save lands; a directory there makes the
    # write fail with a real OSError, with no monkeypatching of the serializer.
    (tmp_path / "hier.graph.json").mkdir()

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, path)
        await _await_load(pilot, screen)

        await pilot.press("s")
        await pilot.pause()

        status = _status(screen)
        assert status.startswith("\u2717 Could not write ")
        assert str(tmp_path / "hier.graph.json") in status
        assert "Traceback" not in status
        assert isinstance(app.screen, GraphBuildScreen)
        assert app._exception is None


async def test_save_key_after_a_failed_parse_writes_nothing(tmp_path: Path) -> None:
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, tmp_path / "gone.pdf")
        await _await_load(pilot, screen)

        save_button = screen.query_one("#btn-graph-save", Button)
        assert save_button.disabled is True

        await pilot.press("s")
        await pilot.pause()

        assert _status(screen) == NOTHING_TO_SAVE
        assert _saved_files(tmp_path) == []


async def test_the_document_is_parsed_exactly_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G6: one parse, one build -- the tree reuses the domain summary's graph."""
    import openreview_cli.parsing.stream as stream_module

    calls: list[Path] = []
    real_parse = stream_module.parse_document

    def counting_parse(*args: Any, **kwargs: Any) -> Any:
        calls.append(Path(args[0]))
        return real_parse(*args, **kwargs)

    monkeypatch.setattr(stream_module, "parse_document", counting_parse)

    path = _hierarchical_docx(tmp_path)
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, path)
        await _await_load(pilot, screen)
        await pilot.press("s")
        await pilot.pause()

    assert calls == [path]


# ── 4. parse failure: one line, no traceback ──────────────────────────


@pytest.mark.parametrize(
    ("name", "contents"),
    [
        ("gone.pdf", None),
        ("empty.docx", b""),
    ],
)
async def test_parse_failure_is_one_line_without_a_traceback(
    tmp_path: Path, name: str, contents: bytes | None
) -> None:
    path = tmp_path / name
    if contents is not None:
        path.write_bytes(contents)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, path)
        await _await_load(pilot, screen)

        status = _status(screen)
        assert status.startswith("\u2717 Could not read ")
        assert len(status.splitlines()) == 1
        assert "Traceback" not in status
        assert _header(screen) == name
        # Still mounted and interactive: nothing escaped into Textual's handler.
        assert isinstance(app.screen, GraphBuildScreen)
        assert app._exception is None
        assert _saved_files(tmp_path) == []


# ── 5. the busy guard ─────────────────────────────────────────────────


async def test_escape_and_save_are_blocked_while_the_worker_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An uncancellable worker must not be unmounted under, and writes nothing."""
    import openreview_cli.tui.screens.graph_build as graph_build_module

    started = threading.Event()
    release = threading.Event()
    real_summary = graph_build_module.graph_summary_via_tui

    def blocked_summary(document_path: Path) -> Any:
        started.set()
        assert release.wait(timeout=15)
        return real_summary(document_path)

    monkeypatch.setattr(graph_build_module, "graph_summary_via_tui", blocked_summary)

    path = _hierarchical_docx(tmp_path)
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, path)

        await asyncio.to_thread(started.wait, 10)
        assert screen._load_task is not None and not screen._load_task.done()

        assert screen._busy is True
        assert screen.check_action("go_back", ()) is False
        assert screen.check_action("save_graph", ()) is False
        assert screen.query_one("#btn-graph-save", Button).disabled is True
        assert screen.query_one("#btn-graph-back", Button).disabled is True

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, GraphBuildScreen)  # not popped while busy

        # Popping the screen cancels the in-flight build.
        app.pop_screen()
        await pilot.pause()
        assert screen._load_task.cancelled()

        release.set()
        await pilot.pause(0.5)

        assert _saved_files(tmp_path) == []
        assert app._exception is None


# ── 6. reach: the result screen and the retrieve screen ───────────────


def _report(filename: str) -> Any:
    """Minimal ReviewReport double: only the fields ResultScreen reads."""
    report = MagicMock()
    report.assessments = []
    report.document.filename = filename
    report.summary.green_count = 0
    report.summary.amber_count = 0
    report.summary.red_count = 0
    return report


async def test_b_on_the_result_screen_opens_the_build_screen(tmp_path: Path) -> None:
    from openreview_cli.tui.screens.result import ResultScreen

    path = _hierarchical_docx(tmp_path)
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[_report(path.name)], document_paths=[path]))
        await pilot.pause()
        result = app.screen
        assert isinstance(result, ResultScreen)
        assert result.query("#btn-graph-build")

        await pilot.click("#btn-graph-build")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, GraphBuildScreen)
        assert screen._document_path == path
        await _await_load(pilot, screen)
        assert _header(screen).startswith("hier.docx")


async def test_b_is_unavailable_on_the_result_screen_without_a_document_path() -> None:
    from openreview_cli.tui.screens.result import ResultScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[_report("reviewed.pdf")]))
        await pilot.pause()
        result = app.screen
        assert isinstance(result, ResultScreen)

        assert result.check_action("build_clause_graph", ()) is False
        assert not result.query("#btn-graph-build")

        await pilot.press("b")
        await pilot.pause()
        assert isinstance(app.screen, ResultScreen)


async def test_graph_button_on_the_retrieve_screen_opens_the_build_screen(
    tmp_path: Path,
) -> None:
    path = _hierarchical_docx(tmp_path)
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = RetrieveScreen(db_dir=tmp_path / "indexes")
        app.push_screen(screen)
        await pilot.pause()
        assert isinstance(app.screen, RetrieveScreen)

        screen.query_one("#retrieve-path", Input).value = str(path)
        await pilot.click("#btn-graph")
        await pilot.pause()

        built = app.screen
        assert isinstance(built, GraphBuildScreen)
        assert built._document_path == path
        await _await_load(pilot, built)
        assert _header(built).startswith("hier.docx")


@pytest.mark.parametrize(
    ("raw_path", "expected"),
    [
        ("", GRAPH_NO_PATH_MESSAGE),
        ("/nowhere/at/all/gone.pdf", GRAPH_NOT_FOUND_MESSAGE),
    ],
)
async def test_graph_button_on_the_retrieve_screen_refuses_a_bad_path(
    tmp_path: Path, raw_path: str, expected: str
) -> None:
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = RetrieveScreen(db_dir=tmp_path / "indexes")
        app.push_screen(screen)
        await pilot.pause()

        screen.query_one("#retrieve-path", Input).value = raw_path
        await pilot.click("#btn-graph")
        await pilot.pause()

        assert isinstance(app.screen, RetrieveScreen)
        assert str(screen.query_one("#retrieve-status", Static).render()) == expected
        assert app._exception is None


async def test_the_graph_button_is_disabled_while_the_retrieve_screen_is_busy(
    tmp_path: Path,
) -> None:
    """``_BUTTON_IDS`` must carry the new control, or a worker could unmount under it."""
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = RetrieveScreen(db_dir=tmp_path / "indexes")
        app.push_screen(screen)
        await pilot.pause()

        screen._set_busy(True)
        try:
            assert screen.query_one("#btn-graph", Button).disabled is True
        finally:
            screen._set_busy(False)

        assert screen.query_one("#btn-graph", Button).disabled is False
