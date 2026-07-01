from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


@pytest.mark.integration
@pytest.mark.memory
def test_peak_memory_500_page_pdf() -> None:
    import tracemalloc

    from openreview_cli.parsing.stream import stream_clauses

    # Warm the lazy-loaded nupunkt model (~320 MB) before starting the
    # memory measurement so the test captures per-document parse memory,
    # not the one-time NLP model load.
    list(stream_clauses(FIXTURES / "simple_contract.pdf"))

    tracemalloc.start()
    clauses = list(stream_clauses(FIXTURES / "500_page.pdf"))
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert peak < 110 * 1024 * 1024, f"Peak memory {peak / 1024 / 1024:.1f} MB exceeds 110 MB"
    assert len(clauses) > 0


@pytest.mark.integration
@pytest.mark.memory
def test_gateway_peak_memory(tmp_path: Path) -> None:
    import tracemalloc

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "version: 1\ngateway:\n  models:\n    reasoning:\n      primary: ollama/qwen3:8b\n"
    )
    auth_path = tmp_path / "auth.json"
    auth_path.write_text("{}")

    from openreview_cli.gateway.router import Gateway

    tracemalloc.start()
    gw = Gateway(config_path, auth_path, tmp_path / "data.db")
    _ = gw.health_check()
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert peak < 110 * 1024 * 1024, (
        f"Gateway peak memory {peak / 1024 / 1024:.1f} MB exceeds 110 MB"
    )
