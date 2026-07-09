-- D-59: Persistent graph storage tables
CREATE TABLE IF NOT EXISTS graph_meta (
    contract_id TEXT PRIMARY KEY,
    metadata_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS graph_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    label TEXT NOT NULL,
    position TEXT,
    metadata_json TEXT DEFAULT '{}',
    UNIQUE(contract_id, node_id)
);

CREATE TABLE IF NOT EXISTS graph_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id TEXT NOT NULL,
    source_node_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    UNIQUE(contract_id, source_node_id, target_node_id)
);

PRAGMA user_version = 8;
