# Pipeline API Contracts

**Date**: 2026-07-04 | **Spec Reference**: spec.md §3 (FR-001 through FR-012)

## Pipeline Runner Contract

### `Pipeline.__init__(stages, max_memory_mb, cancellation_token, progress_callback)`

```python
class Pipeline:
    def __init__(
        self,
        stages: list[Stage],
        max_memory_mb: int | None = None,
        cancellation_token: asyncio.Event | None = None,
        progress_callback: Callable[[ProgressEvent], None] | None = None,
    ) -> None: ...
```

**Parameters**:
- `stages`: Ordered list of stage objects. Must not be empty (empty list returns empty report immediately).
- `max_memory_mb`: If set, emit a warning when a stage's allocated memory delta exceeds this threshold (measured via tracemalloc).
- `cancellation_token`: An `asyncio.Event` that, when set, signals the pipeline to cancel gracefully after the current stage completes.
- `progress_callback`: Called with `ProgressEvent` on each stage transition.

### `Pipeline.run(ctx) → PipelineReport`

```python
async def run(
    self,
    ctx: dict[str, Any] | None = None,
) -> PipelineReport: ...
```

**Parameters**:
- `ctx`: Initial shared context. If `None`, starts with an empty dict.

**Returns**: `PipelineReport` with per-stage results, total duration, cancellation flag, peak memory.

**Effects**:
- Iterates stages in order, calling `await stage.run(ctx)` for each
- Merges each stage's results into ctx via `ctx.update(result)`
- Invokes `stage.cleanup()` if defined, after merge
- Emits `ProgressEvent` via callback on each stage transition
- On non-critical error: captures error in `StageResult`, appends to `ctx["errors"]`, continues
- On critical error: halts immediately, returns partial report with error
- On cancellation: completes current stage, returns report with `cancelled=True`

## Stage Contract

### `Stage` (abstract base class)

```python
class Stage(ABC):
    name: str
    critical: bool = False

    @abstractmethod
    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Execute this stage.

        Args:
            ctx: Shared pipeline context. Read prior stage outputs from this.

        Returns:
            Dict of keys to merge into the shared context.
        """
        ...

    def cleanup(self) -> None:
        """Optional: release stage-local resources after run() completes."""
        ...
```

### Stage Adapter Contracts

#### `ParseStage`

```python
class ParseStage(Stage):
    name = "parse"
    critical = True  # No clauses → nothing to process downstream

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Parse document at ctx['document_path'].

        Reads:  ctx['document_path'] (str)
        Writes: ctx['document'] (Document), ctx['clauses'] (list[Clause])
        """
```

#### `StripStage`

```python
class StripStage(Stage):
    name = "strip"
    critical = False  # PII stripping can be skipped (no_pii flag)

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Strip PII from clauses.

        Reads:  ctx['clauses'] (list[Clause])
        Writes: ctx['stripped_clauses'] (list[Clause])
        """
```

#### `ChunkStage`

```python
class ChunkStage(Stage):
    name = "chunk"
    critical = False

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Chunk clauses into retrieval-ready chunks.

        Reads:  ctx['stripped_clauses'] or ctx['clauses'] (list[Clause])
        Writes: ctx['chunks'] (list[Chunk])
        """
```

#### `RetrieveStage`

```python
class RetrieveStage(Stage):
    name = "retrieve"
    critical = False

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Retrieve relevant passages for each chunk.

        Reads:  ctx['chunks'] (list[Chunk])
        Writes: ctx['retrieved'] (list[SearchResult])
        """
```

#### `GenerateStage`

```python
class GenerateStage(Stage):
    name = "generate"
    critical = False

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Generate AI response from retrieved context.

        Reads:  ctx['retrieved'] (list[SearchResult]), ctx['playbook'] (Playbook)
        Writes: ctx['generated'] (str)
        """
```

## CLI Contract (run_review refactor)

The existing `run_review()` function signature remains unchanged:

```python
def run_review(
    paths: Sequence[str],
    playbook_path: str | None = None,
    playbook_id: str | None = None,
    extraction_model: str = "extraction",
    qa_model: str | None = None,
    no_pii: bool = False,
    verbose: bool = False,
    grounding_mode: str | None = None,
    confidence_threshold: float = 0.7,
) -> list[ReviewReport]: ...
```

**Internal change only**: The body is rewritten to compose a `Pipeline` with the five stage adapters and call `asyncio.run(pipeline.run(...))`. Output format is preserved exactly. Zero behavioural change for callers.

## Progress Callback Contract

```python
def progress_handler(event: ProgressEvent) -> None:
    """Handle a progress event from the pipeline runner.

    The handler is called on every stage transition. May be synchronous
    (called from the async event loop). Output to stderr recommended
    to avoid interfering with stdout-based output.
    """
```

## Error Contract

| Error Type | Raised By | Behaviour |
|-----------|-----------|-----------|
| `StageError` | Non-critical stage | Captured in StageResult, pipeline continues |
| `CriticalStageError(StageError)` | Critical stage | Pipeline halts, error propagated |
| `pipeline.CancelledError` | Runner (via cancellation token) | Current stage completes, cancelled report returned |
| `KeyboardInterrupt` | CLI (OS signal) | Sets cancellation token, graceful shutdown |
