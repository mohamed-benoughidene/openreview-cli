import time
from pathlib import Path

from openreview_cli.storage.database import (
    check_daily_limit,
    check_session_limit,
    get_connection,
    init_database,
    log_cost,
    transaction,
)


def test_init_database_creates_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "openreview.db"
    init_database(db_path)
    assert db_path.exists()


def test_init_database_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "openreview.db"
    init_database(db_path)
    init_database(db_path)


def test_init_database_latency(tmp_path: Path) -> None:
    db_path = tmp_path / "openreview.db"
    start = time.perf_counter()
    init_database(db_path)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"DB init took {elapsed:.3f}s, expected <2.0s"


def _seed_session(db_path: Path, session_id: str) -> None:
    """Insert a session row so cost_logs FK constraint is satisfied."""
    with transaction(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id) VALUES (?)",
            (session_id,),
        )


def _seed_review(db_path: Path, review_id: str = "test-review") -> None:
    with transaction(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO clients (id, name) VALUES (?, ?)", ("seed", "Seed Client")
        )
        conn.execute(
            "INSERT OR IGNORE INTO reviews (id, client_id, contract_path, contract_hash, mode) VALUES (?, ?, ?, ?, ?)",
            (review_id, "seed", "/dev/null", "0000", "precheck"),
        )


def test_log_cost_inserts_row(tmp_path: Path) -> None:
    db_path = tmp_path / "openreview.db"
    init_database(db_path)
    _seed_review(db_path)
    _seed_session(db_path, "test-review")
    log_cost(db_path, "test-review", "ollama/qwen3:8b", "ollama", 100, 50, 5)
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM cost_logs").fetchone()
    assert row is not None
    assert row["session_id"] == "test-review"
    assert row["model"] == "ollama/qwen3:8b"
    assert row["provider"] == "ollama"
    assert row["prompt_tokens"] == 100
    assert row["completion_tokens"] == 50
    assert row["cost_cents"] == 5
    assert row["id"] is not None
    conn.close()


def test_check_daily_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "openreview.db"
    init_database(db_path)
    for i in range(3):
        _seed_review(db_path, f"review-{i}")
        _seed_session(db_path, f"review-{i}")
        log_cost(db_path, f"review-{i}", "gpt4", "openai", 0, 0, 100)
    assert not check_daily_limit(db_path, 200)
    assert check_daily_limit(db_path, 400)


def test_check_session_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "openreview.db"
    init_database(db_path)
    _seed_review(db_path, "session-1")
    _seed_session(db_path, "session-1")
    log_cost(db_path, "session-1", "gpt4", "openai", 0, 0, 100)
    log_cost(db_path, "session-1", "gpt4", "openai", 0, 0, 50)
    assert not check_session_limit(db_path, "session-1", 100)
    assert check_session_limit(db_path, "session-1", 200)


def test_log_cost_latency(tmp_path: Path) -> None:
    db_path = tmp_path / "openreview.db"
    init_database(db_path)
    _seed_review(db_path, "latency-test")
    _seed_session(db_path, "latency-test")
    start = time.perf_counter()
    log_cost(db_path, "latency-test", "gpt4", "openai", 0, 0, 1)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1, f"log_cost took {elapsed:.3f}s, expected <0.1s"


# ── D-11: Comparison History ──


def test_record_comparison_creates_table(tmp_path: Path) -> None:
    from openreview_cli.storage.database import record_comparison

    db_path = tmp_path / "test.db"
    entry = {
        "contract_a_path": "/tmp/a.docx",
        "contract_a_hash": "aaa",
        "contract_a_version_label": "v1",
        "contract_b_path": "/tmp/b.docx",
        "contract_b_hash": "bbb",
        "contract_b_version_label": "v2",
        "result_json": '{"ok": true}',
    }
    row_id = record_comparison(db_path, entry)
    assert row_id > 0


def test_list_comparison_history(tmp_path: Path) -> None:
    from openreview_cli.storage.database import list_comparison_history, record_comparison

    db_path = tmp_path / "test.db"
    record_comparison(
        db_path,
        {
            "contract_a_path": "/tmp/a.docx",
            "contract_a_hash": "aaa",
            "contract_a_version_label": None,
            "contract_b_path": "/tmp/b.docx",
            "contract_b_hash": "bbb",
            "contract_b_version_label": None,
            "result_json": '{"ok": true}',
        },
    )
    record_comparison(
        db_path,
        {
            "contract_a_path": "/tmp/c.docx",
            "contract_a_hash": "ccc",
            "contract_a_version_label": "v2",
            "contract_b_path": "/tmp/d.docx",
            "contract_b_hash": "ddd",
            "contract_b_version_label": "v1",
            "result_json": '{"ok": false}',
        },
    )
    entries = list_comparison_history(db_path)
    assert len(entries) == 2
    paths = {e["contract_a_path"] for e in entries}
    assert "/tmp/a.docx" in paths
    assert "/tmp/c.docx" in paths


def test_list_comparison_history_limit(tmp_path: Path) -> None:
    from openreview_cli.storage.database import list_comparison_history, record_comparison

    db_path = tmp_path / "test.db"
    for i in range(5):
        record_comparison(
            db_path,
            {
                "contract_a_path": f"/tmp/{i}.docx",
                "contract_a_hash": f"{i:03x}",
                "contract_a_version_label": None,
                "contract_b_path": "/tmp/b.docx",
                "contract_b_hash": "bbb",
                "contract_b_version_label": None,
                "result_json": "{}",
            },
        )
    entries = list_comparison_history(db_path, limit=3)
    assert len(entries) == 3


def test_list_comparison_history_empty(tmp_path: Path) -> None:
    from openreview_cli.storage.database import list_comparison_history

    entries = list_comparison_history(tmp_path / "empty.db")
    assert entries == []


# ── D-59: Graph Storage ──


def test_save_graph_creates_tables(tmp_path: Path) -> None:
    from openreview_cli.graph.models import ContractGraph, GraphNode
    from openreview_cli.storage.database import save_graph

    db_path = tmp_path / "test.db"
    graph = ContractGraph(nodes={"n1": GraphNode(id="n1", label="Test", text="...", level=0)})
    save_graph(db_path, "c1", graph)
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM graph_nodes").fetchall()
    conn.close()
    assert len(rows) == 1


def test_save_graph_idempotent(tmp_path: Path) -> None:
    from openreview_cli.graph.models import ContractGraph, GraphNode
    from openreview_cli.storage.database import save_graph

    db_path = tmp_path / "test.db"
    graph = ContractGraph(nodes={"n1": GraphNode(id="n1", label="Test", text="...", level=0)})
    save_graph(db_path, "c1", graph)
    save_graph(db_path, "c1", graph)
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM graph_nodes WHERE contract_id = 'c1'").fetchall()
    conn.close()
    assert len(rows) == 1


def test_load_graph_returns_none_for_missing(tmp_path: Path) -> None:
    from openreview_cli.storage.database import load_graph

    db_path = tmp_path / "test.db"
    init_database(db_path)
    result = load_graph(db_path, "nonexistent")
    assert result is None


def test_save_load_graph_round_trip(tmp_path: Path) -> None:
    from openreview_cli.graph.models import ContractGraph, EdgeType, GraphEdge, GraphNode
    from openreview_cli.storage.database import load_graph, save_graph

    db_path = tmp_path / "test.db"
    nodes: dict[str, GraphNode] = {
        "1": GraphNode(id="1", label="Root", text="...", level=0, metadata={"source": "test"}),
        "2": GraphNode(id="2", label="Child", text="...", level=1),
    }
    edges = [GraphEdge(source_id="1", target_id="2", edge_type=EdgeType.parent_child)]
    graph = ContractGraph(nodes=nodes, edges=edges, metadata={"key": "val"})
    save_graph(db_path, "c1", graph)
    loaded = load_graph(db_path, "c1")
    assert loaded is not None
    assert len(loaded.nodes) == 2
    assert loaded.nodes["1"].label == "Root"
    assert loaded.nodes["1"].metadata.get("source") == "test"
    assert len(loaded.edges) == 1
    assert loaded.edges[0].source_id == "1"
    assert loaded.edges[0].target_id == "2"


# ── D-31: Recovery State ──


def test_save_load_recovery_state_round_trip(tmp_path: Path) -> None:
    from openreview_cli.recovery.models import RecoveryContext, RecoveryEvent, RecoveryOutcome
    from openreview_cli.storage.database import (
        load_recovery_state,
        save_recovery_state,
    )

    db_path = tmp_path / "test.db"
    ctx = RecoveryContext(
        provider_list=["openai/gpt-4", "ollama/llama3.1"],
        attempted_strategies=["auto_retry"],
        current_provider_index=1,
        retry_counts={"generate": 2},
        failed_stages=["chunk"],
        completed_stages=["parse"],
        partial_data={"chunk": {"progress": 0.5}},
        events=[
            RecoveryEvent(
                strategy_name="auto_retry",
                stage_name="generate",
                outcome=RecoveryOutcome.RESOLVED,
                message="Retry succeeded",
            )
        ],
    )
    save_recovery_state(db_path, "pipeline-1", "parse", ctx)
    loaded = load_recovery_state(db_path, "pipeline-1")
    assert loaded is not None
    assert loaded.provider_list == ["openai/gpt-4", "ollama/llama3.1"]
    assert loaded.attempted_strategies == ["auto_retry"]
    assert loaded.current_provider_index == 1
    assert loaded.retry_counts == {"generate": 2}
    assert loaded.failed_stages == ["chunk"]
    assert loaded.completed_stages == ["parse"]
    assert loaded.partial_data == {"chunk": {"progress": 0.5}}
    assert len(loaded.events) == 1
    assert loaded.events[0].strategy_name == "auto_retry"
    assert loaded.events[0].outcome == RecoveryOutcome.RESOLVED


def test_load_recovery_state_missing(tmp_path: Path) -> None:
    from openreview_cli.storage.database import load_recovery_state

    result = load_recovery_state(tmp_path / "nonexistent.db", "no-such-pipeline")
    assert result is None


def test_delete_recovery_state(tmp_path: Path) -> None:
    from openreview_cli.recovery.models import RecoveryContext
    from openreview_cli.storage.database import (
        delete_recovery_state,
        load_recovery_state,
        save_recovery_state,
    )

    db_path = tmp_path / "test.db"
    ctx = RecoveryContext()
    save_recovery_state(db_path, "pipeline-1", "parse", ctx)
    assert load_recovery_state(db_path, "pipeline-1") is not None
    deleted = delete_recovery_state(db_path, "pipeline-1")
    assert deleted is True
    assert load_recovery_state(db_path, "pipeline-1") is None


def test_delete_recovery_state_missing(tmp_path: Path) -> None:
    from openreview_cli.storage.database import delete_recovery_state

    result = delete_recovery_state(tmp_path / "test.db", "no-such-pipeline")
    assert result is False


def test_graph_tables_exist_after_init(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_database(db_path)
    conn = get_connection(db_path)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('graph_meta', 'graph_nodes', 'graph_edges')"
    ).fetchall()
    conn.close()
    names = {r[0] for r in tables}
    assert "graph_meta" in names
    assert "graph_nodes" in names
    assert "graph_edges" in names
