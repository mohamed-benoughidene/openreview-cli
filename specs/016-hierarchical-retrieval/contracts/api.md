# Python API Contracts — Hierarchical Retrieval

**Spec**: specs/016-hierarchical-retrieval/spec.md

---

## Module: `openreview_cli.retrieval.models`

### `class RetrievalQuery`
```python
@dataclass
class RetrievalQuery:
    query_text: str
    method: str = "hybrid"         # "sparse" | "dense" | "hybrid"
    top_k: int = 5                 # 1–50
    rerank: bool = False
    rerank_depth: int = 20         # ≥ top_k
    force_rerank: bool = False
```

Validation:
- `method` must be one of `{"sparse", "dense", "hybrid"}`
- `top_k` must be ≥ 1 and ≤ 50
- `rerank_depth` must be ≥ `top_k`
- `query_text` must be non-empty

### `class RetrievalResult`
```python
@dataclass
class RetrievalResult:
    chunk_id: str
    text: str
    clause_heading: str
    clause_level: int
    hierarchy_chain: list[str]
    parent_chunk_id: str | None
    score: float                   # 0.0–1.0
    method: str                    # "sparse" | "dense" | "hybrid" | "hybrid+rerank"
    rank_sparse: int | None
    rank_dense: int | None
    rrf_score: float | None
    rerank_score: float | None
    char_start: int
    char_end: int
```

### `class IndexMeta`
```python
@dataclass
class IndexMeta:
    document_id: str               # SHA-256 hex
    document_path: str             # Original file path
    chunk_count: int
    method: str                    # "sparse" | "hybrid"
    embedding_model: str | None
    embedding_dimension: int | None
    index_timestamp: str           # ISO 8601
    index_status: str              # "empty" | "ingesting" | "indexed" | "corrupt"
    db_size_bytes: int
```

---

## Module: `openreview_cli.retrieval.engine`

### `class RetrievalEngine`
```python
class RetrievalEngine:
    """Orchestrates hybrid retrieval across BM25 + Dense + RRF fusion."""
    
    def __init__(self, db_path: str | Path, gateway: "Gateway"):
        """
        Initialize the retrieval engine.
        
        Args:
            db_path: Path to the SQLite index database.
            gateway: AI Gateway instance for embedding/reranker calls.
        """
        ...
    
    def retrieve(self, query: RetrievalQuery) -> list[RetrievalResult]:
        """
        Execute a retrieval query.
        
        Args:
            query: The retrieval query parameters.
        
        Returns:
            Ranked list of RetrievalResult (length = top_k).
        
        Raises:
            IndexCorruptError: If the index database is corrupted.
            ModelUnavailableError: If embedding model is not available for dense/hybrid.
        """
        ...
    
    def get_index_meta(self) -> IndexMeta:
        """Return metadata about the current index."""
        ...
```

---

## Module: `openreview_cli.retrieval.ingest`

### `async def ingest_document()`
```python
async def ingest_document(
    chunks: Iterator[Chunk],
    db_path: str | Path,
    gateway: Gateway,
    method: str = "hybrid",
    model_id: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> IndexMeta:
    """
    Ingest parsed chunks into a retrieval index.
    
    Args:
        chunks: Iterator of Chunk objects from the chunking pipeline (spec 007).
        db_path: Path to the SQLite database file.
        gateway: AI Gateway instance for embedding computation.
        method: "sparse" (BM25 only) or "hybrid" (BM25 + dense embeddings).
        model_id: Embedding model to use (None = gateway default).
        progress_callback: Called with (current, total) after each chunk.
    
    Returns:
        IndexMeta with the completed index metadata.
    
    Raises:
        EmbeddingError: If embedding computation fails for a chunk.
    
    Notes:
        - Idempotent: If db_path exists, it is replaced (not appended).
        - Stream-and-discard: Each chunk is written individually.
        - Incomplete marker is written at start, cleared on success.
    """
    ...

    # Internally calls:
    # 1. _create_schema(db_path) — creates tables, FTS5 virtual table, WAL mode
    # 2. _write_chunks(db_path, chunks) — stores chunk data
    # 3. _build_fts_index(db_path) — populates FTS5 virtual table
    # 4. _compute_and_store_embeddings(db_path, chunks, gateway, model_id) — dense mode only
```

### `def index_exists()`
```python
def index_exists(db_path: str | Path) -> bool:
    """Check if an index database exists and is complete (not ingesting/corrupt)."""
    ...

def clear_index(db_path: str | Path) -> None:
    """Delete an index database file."""
    ...

def get_index_for_document(
    doc_hash: str,
    db_dir: str | Path | None = None,
) -> str | Path | None:
    """
    Resolve the SQLite database path for a document hash.
    
    Returns None if no index exists for this document.
    """
    ...
```

---

## Module: `openreview_cli.retrieval.storage`

### `class RetrievalStorage`
```python
class RetrievalStorage:
    """Low-level SQLite operations for the retrieval index."""
    
    def __init__(self, db_path: str | Path):
        self.db_path = db_path
    
    def create_schema(self) -> None:
        """
        Create all tables, FTS5 virtual table, and indexes.
        Sets PRAGMA journal_mode=WAL.
        """
        ...
    
    def insert_chunk(self, chunk: Chunk) -> None:
        """Insert a single chunk row."""
        ...
    
    def insert_embedding(self, chunk_id: str, embedding: bytes, 
                         model_id: str, dimension: int, norm: float) -> None:
        """Insert a single embedding row."""
        ...
    
    def insert_fts(self, chunk_id: str, text: str, clause_heading: str) -> None:
        """Insert a row into the FTS5 virtual table."""
        ...
    
    def search_fts(self, query_text: str, top_k: int) -> list[tuple[str, float]]:
        """
        BM25 search via FTS5.
        
        Returns list of (chunk_id, bm25_score).
        bm25_score is from SQLite's bm25() ranking function (negative = better).
        """
        ...
    
    def load_embeddings(self) -> Iterator[tuple[str, bytes, float]]:
        """
        Stream all (chunk_id, embedding_blob, chunk_norm) tuples.
        
        Used by dense retrieval to compute cosine similarity against query.
        Does not load all embeddings into memory at once — yields one at a time.
        """
        ...
    
    def load_chunk(self, chunk_id: str) -> Chunk | None:
        """Load a single chunk by ID."""
        ...
    
    def load_embedding(self, chunk_id: str) -> tuple[bytes, float] | None:
        """Load a single embedding by chunk ID."""
        ...
    
    def set_index_status(self, status: str) -> None:
        """Set the index status in index_meta table."""
        ...
    
    def get_index_meta(self) -> dict | None:
        """Read index metadata."""
        ...
```

---

## Module: `openreview_cli.retrieval.bm25`

```python
def normalize_bm25_scores(
    raw_scores: list[tuple[str, float]]
) -> list[tuple[str, float]]:
    """
    Normalize FTS5 bm25() scores for RRF fusion input.
    
    FTS5 bm25() returns negative scores where lower (more negative) = better.
    This function converts to rank positions (1 = best) for RRF.
    """
    # Sort by bm25 score ascending (best = most negative)
    # Return list of (chunk_id, rank)
    ...

def preprocess_query(query_text: str) -> str:
    """
    Normalize query text for FTS5.
    
    Steps:
    1. Lowercase
    2. Strip punctuation (except hyphens in legal terms like "data-processing")
    3. Split on whitespace
    4. Rejoin with spaces
    """
    ...
```

---

## Module: `openreview_cli.retrieval.dense`

```python
def compute_embedding(
    text: str,
    gateway: "Gateway",
    model_id: str = "nomic-embed-text",
) -> tuple[list[float], int]:
    """
    Compute embedding vector for text via AI Gateway.
    
    Returns:
        (vector_as_list, dimension)
    """
    ...

def serialize_embedding(vector: list[float]) -> bytes:
    """Convert float list to raw float32 bytes (little-endian)."""
    ...

def deserialize_embedding(blob: bytes, dimension: int) -> list[float]:
    """Convert raw float32 bytes back to float list."""
    ...

def cosine_similarity(
    query_vec: list[float],
    chunk_vec: list[float],
    query_norm: float | None = None,
    chunk_norm: float | None = None,
) -> float:
    """
    Compute cosine similarity between query and chunk vectors.
    
    If pre-computed norms are provided, skips the sqrt for each vector.
    Returns value in [-1.0, 1.0].
    """
    ...

def compute_l2_norm(vec: list[float]) -> float:
    """Compute L2 norm of a vector."""
    ...
```

---

## Module: `openreview_cli.retrieval.rrf`

```python
def rrf_fuse(
    sparse_ranks: dict[str, int],
    dense_ranks: dict[str, int],
    k: int = 60,
) -> list[tuple[str, float]]:
    """
    Fuse sparse and dense ranked results via Reciprocal Rank Fusion.
    
    Args:
        sparse_ranks: dict[chunk_id, rank] from BM25 (1 = best).
        dense_ranks: dict[chunk_id, rank] from cosine similarity (1 = best).
        k: RRF constant (default 60).
    
    Returns:
        List of (chunk_id, rrf_score) sorted by descending score.
    
    Formula:
        score(c) = 1/(k + rank_sparse(c)) + 1/(k + rank_dense(c))
    
    A chunk that appears in only one set gets contribution only from that set.
    """
    ...
```

---

## Module: `openreview_cli.retrieval.rerank`

```python
class Reranker:
    """Cross-encoder reranker wrapper via AI Gateway."""
    
    def __init__(self, gateway: "Gateway", model_id: str = "lightrag-cross-encoder"):
        self.gateway = gateway
        self.model_id = model_id
    
    async def rerank(
        self,
        query: str,
        candidates: list[tuple[str, Chunk]],
        top_k: int,
    ) -> list[tuple[str, float]]:
        """
        Rerank candidate chunks using cross-encoder.
        
        Args:
            query: The original query text.
            candidates: List of (chunk_id, Chunk) pairs to rerank.
            top_k: Number of results to return after reranking.
        
        Returns:
            List of (chunk_id, reranker_score) sorted by descending score.
        """
        ...

    async def validate(
        self,
        storage: RetrievalStorage,
    ) -> dict:
        """
        Run the reranker validation benchmark.
        
        Compares Precision@5 with and without reranker on the document.
        Updates the rerank_validation table.
        
        Returns:
            {"with_reranker": float, "without_reranker": float, "degradation_pp": float}
        """
        ...
```

---

## Module: `openreview_cli.retrieval`

### Public Exports

```python
# __init__.py exports
__all__ = [
    "RetrievalEngine",
    "RetrievalQuery",
    "RetrievalResult",
    "ingest_document",
    "index_exists",
    "clear_index",
    "get_index_for_document",
    "IndexMeta",
    "RetrievalStorage",
]
```

---

## Exceptions

```python
class RetrievalError(Exception):
    """Base error for retrieval pipeline."""

class IndexCorruptError(RetrievalError):
    """Index database is missing, corrupt, or from incompatible schema."""

class IndexNotFoundError(RetrievalError):
    """Document has not been indexed."""

class ModelUnavailableError(RetrievalError):
    """Embedding or reranker model is not available."""

class EmbeddingError(RetrievalError):
    """Embedding computation failed for a chunk."""

class QueryValidationError(RetrievalError):
    """Query parameters failed validation."""
```
