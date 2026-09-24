import asyncio
import functools
import logging
import threading
import tracemalloc
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from openreview_cli.pii.engine import PiiEngine
from openreview_cli.pipeline.base import Stage


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-mark speed category, enforce taxonomy, auto-timeout.

    Root hook runs before child conftest hooks (e.g. TUI's).  The
    path-based logic below correctly identifies TUI tests and marks them
    ``slow``, so the TUI conftest's own ``slow`` marking is a no-op
    overlay — no race.  ``-m`` expression filtering runs after this hook
    returns, so auto-assigned markers are visible to marker expressions.
    """
    for item in items:
        markers = {m.name for m in item.iter_markers()}

        # Auto-enable socket for network/live-marked tests
        if ("network" in markers or "live" in markers) and "enable_socket" not in markers:
            item.add_marker(pytest.mark.enable_socket)

        # Auto-assign speed marker if missing
        if not (markers & {"fast", "slow", "memory", "live"}):
            path = item.path.as_posix()
            if "network" in markers:
                item.add_marker(pytest.mark.live)
            elif "memory" in markers:
                pass
            elif "tests/unit/" in path:
                item.add_marker(pytest.mark.fast)
            elif "tests/integration/tui/" in path:
                item.add_marker(pytest.mark.slow)
            else:
                item.add_marker(pytest.mark.fast)

    # Enforce: every test MUST have a speed marker
    for item in items:
        if not ({m.name for m in item.iter_markers()} & {"fast", "slow", "memory", "live"}):
            pytest.fail(
                f"Test {item.nodeid} has no speed/resource marker. "
                f"Add one of: @pytest.mark.fast, @pytest.mark.slow, @pytest.mark.memory, @pytest.mark.live"
            )

    # Auto-timeout based on speed marker
    for item in items:
        markers = {m.name for m in item.iter_markers()}
        if any(m.name == "timeout" for m in item.iter_markers()):
            continue
        if "memory" in markers or "live" in markers:
            item.add_marker(pytest.mark.timeout(300))
        elif "slow" in markers:
            item.add_marker(pytest.mark.timeout(120))


# Silence transformers advisory/info warnings during pytest runs.
# Avoids "I/O operation on closed file" from warnings emitted while
# pytest has already closed the capture output.
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("transformers.modeling_utils").setLevel(logging.ERROR)
logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.ERROR)
logging.getLogger("transformers.configuration_utils").setLevel(logging.ERROR)
logging.getLogger("transformers.integrations.tensor_parallel").setLevel(logging.ERROR)
logging.getLogger("transformers.integrations.tensor_parallel").setLevel(logging.ERROR)

# Presidio logs into pytest-captured streams that close during teardown.
logging.getLogger("presidio_analyzer").addHandler(logging.NullHandler())
logging.getLogger("presidio_analyzer").propagate = False

PEAK_MEMORY_FLOOR_BYTES = 110 * 1024 * 1024
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ── Shared PII engine (ponytail: one spaCy model load per session, not per test) ──

_shared_pii_engine: dict[str, "PiiEngine"] = {}
_shared_pii_engine_lock = threading.Lock()


def _get_shared_pii_engine() -> "PiiEngine":
    """Return one warmed PiiEngine for the whole session.

    Loads spaCy (en_core_web_lg) once; every PII test reuses the instance
    instead of reloading the ~600 MB model on each test.
    """
    if "engine" not in _shared_pii_engine:
        with _shared_pii_engine_lock:
            if "engine" not in _shared_pii_engine:
                engine = PiiEngine(threshold=0.7)
                engine._ensure_analyzer()
                _shared_pii_engine["engine"] = engine
    return _shared_pii_engine["engine"]


# ── Shared pipeline mock stages ─────────────────────────────────────────────


class MockStage(Stage):
    """Stage that returns a configurable dict and counts calls."""

    def __init__(
        self,
        name: str,
        return_value: dict[str, Any] | None = None,
        sleep: float = 0,
        critical: bool = False,
    ) -> None:
        self.name = name
        self.critical = critical
        self._return = return_value if return_value is not None else {name: f"{name}_out"}
        self._sleep = sleep
        self.call_count = 0

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        self.call_count += 1
        if self._sleep:
            await asyncio.sleep(self._sleep)
        return dict(self._return)


class TrackingStage(Stage):
    """Stage that records the context it received."""

    def __init__(self, name: str, return_value: dict[str, Any] | None = None) -> None:
        self.name = name
        self._return = return_value or {name: f"{name}_out"}
        self.received_ctx: dict[str, Any] | None = None

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        self.received_ctx = dict(ctx)
        return dict(self._return)


class ErrorStage(Stage):
    """Stage that raises a configurable error on run."""

    def __init__(
        self,
        name: str,
        critical: bool = False,
        error_cls: type[Exception] | None = None,
    ) -> None:
        self.name = name
        self.critical = critical
        from openreview_cli.pipeline.errors import StageError

        self._error_cls = error_cls or StageError
        self.call_count = 0

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        self.call_count += 1
        raise self._error_cls(f"{self.name} failed")


class SlowStage(Stage):
    """Stage that sleeps to simulate long work (for cancellation tests)."""

    def __init__(self, name: str, sleep: float = 10) -> None:
        self.name = name
        self._sleep = sleep
        self.started = asyncio.Event()
        self.completed = False

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        self.started.set()
        await asyncio.sleep(self._sleep)
        self.completed = True
        return {self.name: "done"}


@pytest.fixture
def memory_tracker() -> Generator[None, None, None]:
    """Enforce the constitutional peak-memory floor of 110 MB."""
    tracemalloc.start()
    try:
        yield
    finally:
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert peak < PEAK_MEMORY_FLOOR_BYTES, (
            f"Peak memory {peak / 1024 / 1024:.1f} MB exceeds "
            f"{PEAK_MEMORY_FLOOR_BYTES / 1024 / 1024:.0f} MB floor"
        )


@pytest.fixture(autouse=True)
def _tracemalloc_state_isolation(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """Restore tracemalloc on/off state after memory-marked tests.

    Tests carrying ``pytest.mark.memory`` often call ``tracemalloc.start()``
    and ``.stop()`` inside their body.  Leaving tracemalloc in a different
    running state than the per-test ``memory_tracker`` fixture expects
    interacts badly with pytest-socket under heavy memory pressure
    (en_core_web_lg's tok2vec triggers ``SocketBlockedError`` through an
    unexplained CPython/thinc interop).  This sandbox unconditionally resets
    tracemalloc to ``was_tracing`` after any memory-marked test.

    See https://docs.pytest.org/en/stable/how-to/fixtures.html#autouse-fixtures
    """
    if not any(m.name == "memory" for m in request.node.iter_markers()):
        yield
        return
    was_tracing = tracemalloc.is_tracing()
    yield
    if was_tracing:
        if not tracemalloc.is_tracing():
            tracemalloc.start()
    elif tracemalloc.is_tracing():
        tracemalloc.stop()


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def isolated_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Redirect XDG config/data/cache dirs at a per-test ``tmp_path``.

    platformdirs appends the app name, so ``get_config_dir()`` resolves to
    ``XDG_CONFIG_HOME/openreview`` and ``get_data_dir()`` to
    ``XDG_DATA_HOME/openreview``. The fixture materializes a ``config.yml``
    and initializes the SQLite schema so commands exercise the real data
    path without writing into the developer's directories.
    """
    from openreview_cli.storage import init_database

    config_base = tmp_path / "config"
    data_base = tmp_path / "data"
    for base in (config_base, data_base):
        base.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_base))
    monkeypatch.setenv("XDG_DATA_HOME", str(data_base))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    openreview_config_dir = config_base / "openreview"
    openreview_config_dir.mkdir(parents=True, exist_ok=True)
    config_path = openreview_config_dir / "config.yml"
    config_path.write_text(
        "privacy:\n  tier: balanced\ngateway:\n  models: {}\n",
        encoding="utf-8",
    )

    openreview_data_dir = data_base / "openreview"
    openreview_data_dir.mkdir(parents=True, exist_ok=True)
    db_path = openreview_data_dir / "openreview.db"
    init_database(db_path)

    return {
        "config_path": config_path,
        "data_dir": openreview_data_dir,
        "db_path": db_path,
    }


@pytest.fixture(scope="session", autouse=True)
def _tldextract_resolves_suffixes_offline() -> None:
    """Resolve public suffixes from tldextract's bundled snapshot, never the network.

    Presidio's built-in ``EmailRecognizer.validate_result()`` calls
    ``tldextract.extract()``, which obtains the public suffix list from (1) its
    on-disk cache, (2) an HTTPS fetch of ``publicsuffix.org``, or (3) the
    snapshot bundled inside the tldextract wheel.

    Under this suite's ``--disable-socket`` addopt (2) cannot succeed, and
    tldextract only tolerates a failed fetch when it raises
    ``requests.exceptions.RequestException``.  ``pytest_socket`` raises
    ``SocketBlockedError``, a ``RuntimeError``, which escapes tldextract
    uncaught — so the designed snapshot fallback in (3) never runs and the
    PiiEngine reports an engine crash.  Any environment whose tldextract cache
    is cold therefore fails every PII test whose clause text contains an email
    address: a fresh CI runner, a fresh checkout, or ``isolated_xdg``
    redirecting ``XDG_CACHE_HOME`` (tldextract pins its cache directory when the
    module is first imported).

    Pinning the default extractor to the bundled snapshot removes that
    environment dependency.  Detection results are unaffected: the bundled
    snapshot and the downloaded list agree on ``extract(...).fqdn`` — the only
    value Presidio consults — for every address in the fixtures.
    """
    import tldextract
    import tldextract.tldextract as tldextract_impl

    # ``extract()`` and ``update()`` look TLD_EXTRACTOR up in the implementation
    # module's globals; the package re-exports those functions, not the instance.
    tldextract_impl.TLD_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=())


@pytest.fixture(scope="session")
def pii_engine() -> "PiiEngine":
    """Session-scoped shared PiiEngine for tests that build their own engine."""
    return _get_shared_pii_engine()


@pytest.fixture(autouse=True)
def _inject_shared_pii_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feed the shared PiiEngine into strip_pii/strip_pii_clauses when none passed.

    Non-PII tests never load the model; it loads lazily on the first real PII
    call and is reused for the rest of the session.
    """
    from openreview_cli.pii.engine import strip_pii, strip_pii_clauses

    real_strip_pii = strip_pii
    real_strip_clauses = strip_pii_clauses

    @functools.wraps(real_strip_pii)
    def _patched_strip_pii(*args: Any, engine: "PiiEngine | None" = None, **kwargs: Any) -> Any:
        return real_strip_pii(*args, engine=engine or _get_shared_pii_engine(), **kwargs)

    @functools.wraps(real_strip_clauses)
    def _patched_strip_clauses(*args: Any, engine: "PiiEngine | None" = None, **kwargs: Any) -> Any:
        return real_strip_clauses(*args, engine=engine or _get_shared_pii_engine(), **kwargs)

    monkeypatch.setattr("openreview_cli.pii.engine.strip_pii", _patched_strip_pii)
    monkeypatch.setattr("openreview_cli.pii.engine.strip_pii_clauses", _patched_strip_clauses)
