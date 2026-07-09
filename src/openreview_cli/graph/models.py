from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class EdgeType(StrEnum):
    parent_child = "parent_child"
    cross_ref = "cross_ref"
    def_ref = "def_ref"


@dataclass
class GraphNode:
    id: str
    label: str
    text: str
    level: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    edge_type: EdgeType
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContractGraph:
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def adjacency(self) -> dict[str, list[GraphEdge]]:
        result: dict[str, list[GraphEdge]] = {}
        for edge in self.edges:
            result.setdefault(edge.source_id, []).append(edge)
        return result

    @property
    def roots(self) -> list[str]:
        parent_child_targets = {
            e.target_id for e in self.edges if e.edge_type == EdgeType.parent_child
        }
        return [nid for nid in self.nodes if nid not in parent_child_targets]

    @property
    def orphan_ids(self) -> list[str]:
        parent_child_targets = {
            e.target_id for e in self.edges if e.edge_type == EdgeType.parent_child
        }
        parent_child_sources = {
            e.source_id for e in self.edges if e.edge_type == EdgeType.parent_child
        }
        return [
            nid
            for nid in self.nodes
            if nid not in parent_child_targets and nid in parent_child_sources
        ]

    def to_json(self) -> str:
        data = {
            "metadata": self.metadata,
            "nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "text": n.text,
                    "level": n.level,
                    "metadata": n.metadata,
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "edge_type": e.edge_type.value,
                    "metadata": e.metadata,
                }
                for e in self.edges
            ],
        }
        return json.dumps(data, indent=2, default=str)

    @classmethod
    def from_json(cls, data: str | dict[str, Any]) -> ContractGraph:
        parsed = json.loads(data) if isinstance(data, str) else data

        nodes: dict[str, GraphNode] = {}
        for nd in parsed.get("nodes", []):
            node = GraphNode(
                id=nd["id"],
                label=nd.get("label", nd["id"]),
                text=nd.get("text", ""),
                level=nd.get("level", 0),
                metadata=nd.get("metadata", {}),
            )
            nodes[node.id] = node

        edges: list[GraphEdge] = []
        for ed in parsed.get("edges", []):
            edges.append(
                GraphEdge(
                    source_id=ed["source_id"],
                    target_id=ed["target_id"],
                    edge_type=EdgeType(ed["edge_type"]),
                    metadata=ed.get("metadata", {}),
                )
            )

        return cls(nodes=nodes, edges=edges, metadata=parsed.get("metadata", {}))

    @classmethod
    def from_file(cls, path: str | Path) -> ContractGraph:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return cls.from_json(p.read_text(encoding="utf-8"))

    def to_file(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")

    def save_to_db(self, db_path: str | Path, contract_id: str) -> None:
        """Persist this graph to SQLite."""
        from openreview_cli.storage.database import save_graph as _save_graph

        _save_graph(Path(db_path), contract_id, self)

    @classmethod
    def load_from_db(cls, db_path: str | Path, contract_id: str) -> ContractGraph | None:
        """Load a graph from SQLite. Returns None if contract_id not found."""
        from openreview_cli.storage.database import load_graph as _load_graph

        return _load_graph(Path(db_path), contract_id)


__all__ = [
    "ContractGraph",
    "EdgeType",
    "GraphEdge",
    "GraphNode",
]
