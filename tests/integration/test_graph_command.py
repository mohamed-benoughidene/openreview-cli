from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

SAMPLE_CLAUSES = [
    {
        "id": "c1",
        "title": "Article 1",
        "text": "Article 1 text. See Section 1.1.",
        "level": 0,
        "parent_id": None,
        "source_page": None,
        "source_paragraph": None,
        "source_span": None,
        "paragraph_count": None,
    },
    {
        "id": "c2",
        "title": "Section 1.1",
        "text": '"Confidential Information" means non-public data.',
        "level": 1,
        "parent_id": "c1",
        "source_page": None,
        "source_paragraph": None,
        "source_span": None,
        "paragraph_count": None,
    },
]


def test_graph_build_smoke(tmp_path: Path) -> None:
    """graph build creates a valid graph JSON file."""
    parsed_path = tmp_path / "parsed.json"
    parsed_path.write_text(json.dumps(SAMPLE_CLAUSES))
    output_path = tmp_path / "output.json"

    result = runner.invoke(app, ["graph", "build", str(parsed_path), "--output", str(output_path)])
    assert result.exit_code == 0, result.stdout
    assert output_path.exists()
    data = json.loads(output_path.read_text())
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) == 2


def test_graph_build_nonexistent_file() -> None:
    result = runner.invoke(app, ["graph", "build", "/nonexistent/file.json"])
    assert result.exit_code == 1


def test_graph_build_malformed_json(tmp_path: Path) -> None:
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("not json")
    result = runner.invoke(app, ["graph", "build", str(bad_path)])
    assert result.exit_code == 2


def test_graph_metrics_smoke(tmp_path: Path) -> None:
    parsed_path = tmp_path / "parsed.json"
    parsed_path.write_text(json.dumps(SAMPLE_CLAUSES))
    graph_path = tmp_path / "graph.json"
    runner.invoke(app, ["graph", "build", str(parsed_path), "--output", str(graph_path)])

    result = runner.invoke(app, ["graph", "metrics", str(graph_path)])
    assert result.exit_code == 0
    assert "Density" in result.stdout
    assert "Max Depth" in result.stdout


def test_graph_metrics_nonexistent() -> None:
    result = runner.invoke(app, ["graph", "metrics", "/nonexistent.json"])
    assert result.exit_code == 1


def test_graph_health_smoke(tmp_path: Path) -> None:
    parsed_path = tmp_path / "parsed.json"
    parsed_path.write_text(json.dumps(SAMPLE_CLAUSES))
    graph_path = tmp_path / "graph.json"
    runner.invoke(app, ["graph", "build", str(parsed_path), "--output", str(graph_path)])

    result = runner.invoke(app, ["graph", "health", str(graph_path)])
    assert result.exit_code == 0
    assert "Health Score:" in result.stdout


def test_graph_health_custom_weights(tmp_path: Path) -> None:
    parsed_path = tmp_path / "parsed.json"
    parsed_path.write_text(json.dumps(SAMPLE_CLAUSES))
    graph_path = tmp_path / "graph.json"
    runner.invoke(app, ["graph", "build", str(parsed_path), "--output", str(graph_path)])

    result = runner.invoke(
        app,
        [
            "graph",
            "health",
            str(graph_path),
            "--weights",
            "0.1 0.1 0.1 0.5 0.2",
        ],
    )
    assert result.exit_code == 0


def test_graph_health_non_normalised_weights_warning(tmp_path: Path) -> None:
    parsed_path = tmp_path / "parsed.json"
    parsed_path.write_text(json.dumps(SAMPLE_CLAUSES))
    graph_path = tmp_path / "graph.json"
    runner.invoke(app, ["graph", "build", str(parsed_path), "--output", str(graph_path)])

    result = runner.invoke(
        app,
        [
            "graph",
            "health",
            str(graph_path),
            "--weights",
            "0.2 0.2 0.2 0.3 0.3",
        ],
    )
    assert result.exit_code == 0
    assert "Warning" in result.stderr


def test_graph_health_nonexistent() -> None:
    result = runner.invoke(app, ["graph", "health", "/nonexistent.json"])
    assert result.exit_code == 1


def test_graph_view_smoke(tmp_path: Path) -> None:
    parsed_path = tmp_path / "parsed.json"
    parsed_path.write_text(json.dumps(SAMPLE_CLAUSES))
    graph_path = tmp_path / "graph.json"
    runner.invoke(app, ["graph", "build", str(parsed_path), "--output", str(graph_path)])

    result = runner.invoke(app, ["graph", "view", str(graph_path)])
    assert result.exit_code == 0
    assert "Article 1" in result.stdout


def test_graph_view_nonexistent() -> None:
    result = runner.invoke(app, ["graph", "view", "/nonexistent.json"])
    assert result.exit_code == 1


def test_graph_help_shows_all_subcommands() -> None:
    result = runner.invoke(app, ["graph", "--help"])
    assert result.exit_code == 0
    assert "build" in result.stdout
    assert "metrics" in result.stdout
    assert "health" in result.stdout
    assert "view" in result.stdout
