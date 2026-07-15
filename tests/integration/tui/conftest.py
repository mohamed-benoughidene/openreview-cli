import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every test under this directory as slow.

    Textual ``app.run_test()`` pays a fixed startup cost (~30s) per test, so
    the whole TUI suite is opt-out for fast dev feedback:
    ``pytest -m "not slow"`` skips it; ``pytest -m slow`` runs only it.
    """
    for item in items:
        if "tests/integration/tui/" in item.path.as_posix():
            item.add_marker(pytest.mark.slow)
