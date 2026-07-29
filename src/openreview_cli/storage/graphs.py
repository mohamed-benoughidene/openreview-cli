"""Graph storage — persist and load contract graphs."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from openreview_cli.storage.database import transaction


def _ensure_graph_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS graph_meta ("
        "  contract_id TEXT PRIMARY KEY,"
        "  metadata_json TEXT DEFAULT '{}'"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS graph_nodes ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  contract_id TEXT NOT NULL,"
        "  node_id TEXT NOT NULL,"
        "  label TEXT NOT NULL,"
        "  position TEXT,"
        "  metadata_json TEXT DEFAULT '{}',"
        "  UNIQUE(contract_id, node_id)"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS graph_edges ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  contract_id TEXT NOT NULL,"
        "  source_node_id TEXT NOT NULL,"
        "  target_node_id TEXT NOT NULL,"
        "  edge_type TEXT NOT NULL,"
        "  UNIQUE(contract_id, source_node_id, target_node_id)"
        ")"
    )


def save_graph(db_path: Path, contract_id: str, graph: Any) -> None:
    """Persist a ContractGraph to SQLite.

    Replaces any existing graph with the same contract_id.
    """
    with transaction(db_path) as conn:
        _ensure_graph_tables(conn)
        # Clear existing data for this contract
        conn.execute("DELETE FROM graph_nodes WHERE contract_id = ?", (contract_id,))
        conn.execute("DELETE FROM graph_edges WHERE contract_id = ?", (contract_id,))
        conn.execute("DELETE FROM graph_meta WHERE contract_id = ?", (contract_id,))

        # Insert nodes
        for node in graph.nodes.values():
            conn.execute(
                "INSERT INTO graph_nodes (contract_id, node_id, label, position, metadata_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    contract_id,
                    node.id,
                    node.label,
                    str(node.level),
                    json.dumps(node.metadata, default=str),
                ),
            )

        # Insert metadata
        conn.execute(
            "INSERT INTO graph_meta (contract_id, metadata_json) VALUES (?, ?)",
            (contract_id, json.dumps(graph.metadata, default=str)),
        )

        # Insert edges
        for edge in graph.edges:
            conn.execute(
                "INSERT OR IGNORE INTO graph_edges (contract_id, source_node_id, target_node_id, edge_type) "
                "VALUES (?, ?, ?, ?)",
                (contract_id, edge.source_id, edge.target_id, edge.edge_type.value),
            )


def load_graph(db_path: Path, contract_id: str) -> Any | None:
    """Load a ContractGraph from SQLite.

    Returns None if contract_id not found.
    """
    from openreview_cli.graph.models import ContractGraph, GraphEdge, GraphNode

    with transaction(db_path) as conn:
        _ensure_graph_tables(conn)
        meta_row = conn.execute(
            "SELECT metadata_json FROM graph_meta WHERE contract_id = ?",
            (contract_id,),
        ).fetchone()
        node_rows = conn.execute(
            "SELECT node_id, label, position, metadata_json FROM graph_nodes "
            "WHERE contract_id = ? ORDER BY node_id",
            (contract_id,),
        ).fetchall()
        if not node_rows:
            return None

        nodes: dict[str, GraphNode] = {}
        for r in node_rows:
            metadata: dict[str, Any] = {}
            if r["metadata_json"]:
                try:
                    metadata = json.loads(r["metadata_json"])
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            nodes[str(r["node_id"])] = GraphNode(
                id=str(r["node_id"]),
                label=str(r["label"]),
                text="",
                level=int(r["position"]) if r["position"] else 0,
                metadata=metadata,
            )

        edge_rows = conn.execute(
            "SELECT source_node_id, target_node_id, edge_type FROM graph_edges "
            "WHERE contract_id = ?",
            (contract_id,),
        ).fetchall()

    from openreview_cli.graph.models import EdgeType

    edges = [
        GraphEdge(
            source_id=str(r["source_node_id"]),
            target_id=str(r["target_node_id"]),
            edge_type=EdgeType(str(r["edge_type"])),
        )
        for r in edge_rows
    ]

    graph_metadata: dict[str, Any] = {}
    if meta_row and meta_row["metadata_json"]:
        try:
            graph_metadata = json.loads(meta_row["metadata_json"])
        except (json.JSONDecodeError, TypeError):
            graph_metadata = {}

    return ContractGraph(nodes=nodes, edges=edges, metadata=graph_metadata)
