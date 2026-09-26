"""Per-tab loading-state integration tests (T4).

Each list tab fetches its rows off the event loop while showing a visible
:class:`LoadingState`; the list stays hidden until the fetch lands. These tests
hold the tab's domain fetch open on a ``threading.Event`` to observe the loading
state, then release it and assert the list takes over.

The domain functions are patched where each tab imports/uses them. A companion
set of failure-path tests proves a failed fetch never takes the app down and
always clears the spinner.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager, suppress
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from textual.widgets import Label, ListItem, ListView, Static
from textual.worker import WorkerCancelled

from openreview_cli.tui.loading import LoadingState

# Patch targets — one per tab, at the module each tab resolves the symbol from.
_REVIEW_LIST = "openreview_cli.tui.domain.review.list_recent_reviews_via_tui"
_CLIENT_LIST = "openreview_cli.tui.domain.clients.list_clients_via_tui"
_PLAYBOOK_LIST = "openreview_cli.tui.domain.playbooks.list_playbooks_via_tui"
_PROMPT_LIST = "openreview_cli.tui.domain.prompts.list_prompts_via_tui"

# Tab name -> the domain fetch it drives.
_TARGETS = {
    "home": _REVIEW_LIST,
    "clients": _CLIENT_LIST,
    "playbooks": _PLAYBOOK_LIST,
    "prompts": _PROMPT_LIST,
}


def _frozen(value: Any, gate: threading.Event | None = None):
    """Build a domain-fn stub returning *value*, optionally gated on *gate*."""

    def _fn(*_args: Any, **_kwargs: Any) -> Any:
        if gate is not None:
            gate.wait(timeout=10)
        return value

    return _fn


@contextmanager
def _patched(
    under_test: str,
    rows: Any,
    gate: threading.Event | None = None,
) -> Iterator[dict[str, MagicMock]]:
    """Patch every tab's fetch; *under_test* returns *rows* (gated), others empty."""
    with ExitStack() as stack:
        mocks = {name: stack.enter_context(patch(target)) for name, target in _TARGETS.items()}
        for name, mock in mocks.items():
            if name == under_test:
                mock.side_effect = _frozen(rows, gate)
            else:
                mock.return_value = []
        yield mocks


@contextmanager
def _patched_failure(under_test: str, exc: Exception) -> Iterator[dict[str, MagicMock]]:
    """Patch every tab's fetch; *under_test* raises *exc*, the rest return empty."""
    with ExitStack() as stack:
        mocks = {name: stack.enter_context(patch(target)) for name, target in _TARGETS.items()}
        for name, mock in mocks.items():
            if name == under_test:
                mock.side_effect = exc
            else:
                mock.return_value = []
        yield mocks


class _Notifications:
    """Record ``app.notify`` calls instead of running the real toast machinery."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, message: str, **kwargs: Any) -> None:
        self.calls.append((message, kwargs))

    def load_failures(self) -> list[dict[str, Any]]:
        return [kwargs for message, kwargs in self.calls if "Load failed" in message]


async def _wait_for_workers(app: Any) -> None:
    """Wait for tab workers, tolerating a worker cancelled by ``exclusive=True``.

    ``WorkerManager.wait_for_complete()`` re-raises ``WorkerCancelled`` when any
    worker was cancelled (an ``exclusive=True`` worker cancels its predecessor),
    so it must be wrapped rather than allowed to escape the test.
    """
    with suppress(WorkerCancelled):
        await app.workers.wait_for_complete()


def _list_item_text(item: ListItem) -> str:
    """Extract visible text from a ListItem."""
    try:
        return str(item.query_one(Label).render())
    except Exception:
        return str(item.render())


def _spinner_width(app: Any, loading_id: str) -> int:
    """Width of the *visible* spinner inside ``loading_id`` (0 when not painted)."""
    from textual.widgets import LoadingIndicator

    loading = app.query_one(loading_id, LoadingState)
    return loading.query_one(LoadingIndicator).region.width


_REVIEW_ROWS = [
    {
        "id": "r-001",
        "filename": "nda.pdf",
        "mode": "precheck",
        "green_count": 2,
        "amber_count": 1,
        "red_count": 0,
        "created_at": "2026-07-11T10:00:00",
    },
    {
        "id": "r-002",
        "filename": "lease.pdf",
        "mode": "leasecheck",
        "green_count": 1,
        "amber_count": 0,
        "red_count": 1,
        "created_at": "2026-07-10T10:00:00",
    },
]

_CLIENT_ROWS = [
    {"id": "acme", "name": "Acme Corp"},
    {"id": "beta", "name": "Beta Inc"},
]

_PLAYBOOK_ROWS = [
    {
        "id": "precheck",
        "latest_version": 2,
        "current_version": 2,
        "created_at": "2026-01-01",
    },
    {
        "id": "dealcheck",
        "latest_version": 1,
        "current_version": 1,
        "created_at": "2026-01-02",
    },
]

_PROMPT_ROWS = [
    {"name": "greeting", "latest_version": 2},
    {"name": "summary", "latest_version": 1},
]


# ── Home ──


async def test_home_tab_shows_loading_state_until_reviews_arrive(
    isolated_xdg: dict[str, Path],
) -> None:
    from openreview_cli.tui.app import OpenReviewApp

    gate = threading.Event()
    with _patched("home", _REVIEW_ROWS, gate):
        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            loading = app.query_one("#home-loading", LoadingState)
            recent_list = app.query_one("#recent-list", ListView)

            assert loading.display is True
            assert recent_list.display is False
            assert _spinner_width(app, "#home-loading") > 0

            gate.set()
            await _wait_for_workers(app)
            await pilot.pause()

            assert loading.display is False
            assert recent_list.display is True
            assert len(recent_list.children) == 2
            joined = " ".join(_list_item_text(i) for i in recent_list.children)
            assert "nda.pdf" in joined
            assert "lease.pdf" in joined


async def test_home_load_failure_notifies_and_recovers(
    isolated_xdg: dict[str, Path],
) -> None:
    """A failed recent-reviews fetch is reported, never fatal, and unblocks the UI."""
    from openreview_cli.tui.app import OpenReviewApp

    recorder = _Notifications()
    with _patched_failure("home", sqlite_error()):
        app = OpenReviewApp()
        app.notify = recorder  # type: ignore[method-assign]
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await _wait_for_workers(app)
            await pilot.pause()

            assert app.is_running
            failures = recorder.load_failures()
            assert failures
            assert failures[-1].get("severity") == "error"
            assert failures[-1].get("markup") is False

            loading = app.query_one("#home-loading", LoadingState)
            recent_list = app.query_one("#recent-list", ListView)
            assert loading.display is False
            assert recent_list.display is True


# ── Clients ──


async def test_clients_tab_shows_loading_state_until_clients_arrive(
    isolated_xdg: dict[str, Path],
) -> None:
    from openreview_cli.tui.app import OpenReviewApp

    gate = threading.Event()
    with _patched("clients", _CLIENT_ROWS, gate):
        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("3")
            await pilot.pause()

            loading = app.query_one("#clients-loading", LoadingState)
            client_list = app.query_one("#client-list", ListView)

            assert loading.display is True
            assert client_list.display is False
            assert _spinner_width(app, "#clients-loading") > 0

            gate.set()
            await _wait_for_workers(app)
            await pilot.pause()

            assert loading.display is False
            assert client_list.display is True
            assert len(client_list.children) == 2
            joined = " ".join(_list_item_text(i) for i in client_list.children)
            assert "acme" in joined
            assert "beta" in joined


async def test_clients_filter_does_not_requery_the_database(
    isolated_xdg: dict[str, Path],
) -> None:
    """A filter keystroke re-filters the cache instead of re-querying."""
    from openreview_cli.tui.app import OpenReviewApp

    with _patched("clients", _CLIENT_ROWS) as mocks:
        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("3")
            await pilot.pause()
            assert mocks["clients"].call_count == 1

            await pilot.click("#client-filter")
            await pilot.press("a", "c", "m", "e")
            await pilot.pause()

            assert mocks["clients"].call_count == 1
            joined = " ".join(_list_item_text(i) for i in app.query_one("#client-list").children)
            assert "acme" in joined
            assert "beta" not in joined


async def test_clients_load_failure_notifies_and_recovers(
    isolated_xdg: dict[str, Path],
) -> None:
    """A failed clients fetch is reported, never fatal, and reveals the list."""
    from openreview_cli.tui.app import OpenReviewApp

    recorder = _Notifications()
    with _patched_failure("clients", sqlite_error()):
        app = OpenReviewApp()
        app.notify = recorder  # type: ignore[method-assign]
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("3")
            await pilot.pause()
            await _wait_for_workers(app)
            await pilot.pause()

            assert app.is_running
            failures = recorder.load_failures()
            assert failures
            assert failures[-1].get("severity") == "error"
            assert failures[-1].get("markup") is False

            loading = app.query_one("#clients-loading", LoadingState)
            client_list = app.query_one("#client-list", ListView)
            assert loading.display is False
            assert client_list.display is True


# ── Playbooks ──


async def test_playbooks_tab_shows_loading_state_until_playbooks_arrive(
    isolated_xdg: dict[str, Path],
) -> None:
    from openreview_cli.tui.app import OpenReviewApp

    gate = threading.Event()
    with _patched("playbooks", _PLAYBOOK_ROWS, gate):
        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("4")
            await pilot.pause()

            loading = app.query_one("#playbooks-loading", LoadingState)
            playbook_list = app.query_one("#playbook-list", ListView)

            assert loading.display is True
            assert playbook_list.display is False
            assert _spinner_width(app, "#playbooks-loading") > 0

            gate.set()
            await _wait_for_workers(app)
            await pilot.pause()

            assert loading.display is False
            assert playbook_list.display is True
            assert len(playbook_list.children) == 2
            joined = " ".join(_list_item_text(i) for i in playbook_list.children)
            assert "precheck" in joined
            assert "dealcheck" in joined


async def test_playbooks_filter_does_not_requery_the_database(
    isolated_xdg: dict[str, Path],
) -> None:
    """A filter keystroke re-filters the cache instead of re-querying."""
    from openreview_cli.tui.app import OpenReviewApp

    with _patched("playbooks", _PLAYBOOK_ROWS) as mocks:
        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("4")
            await pilot.pause()
            assert mocks["playbooks"].call_count == 1

            await pilot.click("#playbook-filter")
            await pilot.press("d", "e", "a", "l")
            await pilot.pause()

            assert mocks["playbooks"].call_count == 1
            joined = " ".join(_list_item_text(i) for i in app.query_one("#playbook-list").children)
            assert "dealcheck" in joined
            assert "precheck" not in joined


async def test_playbooks_load_failure_notifies_and_recovers(
    isolated_xdg: dict[str, Path],
) -> None:
    """A failed playbooks fetch is reported, never fatal, and reveals the list."""
    from openreview_cli.tui.app import OpenReviewApp

    recorder = _Notifications()
    with _patched_failure("playbooks", sqlite_error()):
        app = OpenReviewApp()
        app.notify = recorder  # type: ignore[method-assign]
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("4")
            await pilot.pause()
            await _wait_for_workers(app)
            await pilot.pause()

            assert app.is_running
            failures = recorder.load_failures()
            assert failures
            assert failures[-1].get("severity") == "error"
            assert failures[-1].get("markup") is False

            loading = app.query_one("#playbooks-loading", LoadingState)
            playbook_list = app.query_one("#playbook-list", ListView)
            assert loading.display is False
            assert playbook_list.display is True


# ── Prompts ──


async def test_prompts_tab_shows_loading_state_until_prompts_arrive(
    isolated_xdg: dict[str, Path],
) -> None:
    from openreview_cli.tui.app import OpenReviewApp

    gate = threading.Event()
    with _patched("prompts", _PROMPT_ROWS, gate):
        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("6")
            await pilot.pause()

            loading = app.query_one("#prompts-loading", LoadingState)
            prompt_list = app.query_one("#prompt-list", ListView)

            assert loading.display is True
            assert prompt_list.display is False
            assert _spinner_width(app, "#prompts-loading") > 0

            gate.set()
            await _wait_for_workers(app)
            await pilot.pause()

            assert loading.display is False
            assert prompt_list.display is True
            assert len(prompt_list.children) == 2
            joined = " ".join(_list_item_text(i) for i in prompt_list.children)
            assert "greeting" in joined
            assert "summary" in joined


async def test_prompts_filter_does_not_requery_the_database(
    isolated_xdg: dict[str, Path],
) -> None:
    """A filter keystroke re-filters the cache instead of re-querying."""
    from openreview_cli.tui.app import OpenReviewApp

    with _patched("prompts", _PROMPT_ROWS) as mocks:
        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("6")
            await pilot.pause()
            assert mocks["prompts"].call_count == 1

            await pilot.click("#prompt-filter")
            await pilot.press("g", "r", "e", "e", "t")
            await pilot.pause()

            assert mocks["prompts"].call_count == 1
            joined = " ".join(_list_item_text(i) for i in app.query_one("#prompt-list").children)
            assert "greeting" in joined
            assert "summary" not in joined


async def test_prompts_load_failure_notifies_and_recovers(
    isolated_xdg: dict[str, Path],
) -> None:
    """A failed prompts fetch is reported, never fatal, and reveals the list."""
    from openreview_cli.tui.app import OpenReviewApp

    recorder = _Notifications()
    with _patched_failure("prompts", sqlite_error()):
        app = OpenReviewApp()
        app.notify = recorder  # type: ignore[method-assign]
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("6")
            await pilot.pause()
            await _wait_for_workers(app)
            await pilot.pause()

            assert app.is_running
            failures = recorder.load_failures()
            assert failures
            assert failures[-1].get("severity") == "error"
            assert failures[-1].get("markup") is False

            loading = app.query_one("#prompts-loading", LoadingState)
            prompt_list = app.query_one("#prompt-list", ListView)
            assert loading.display is False
            assert prompt_list.display is True
            # The list is not blank: the empty-state row renders.
            assert len(prompt_list.children) == 1


# ── Settings ──


def _gated_text_for(block_on: str, gate: threading.Event):
    """Wrap ``SettingsTab._text_for`` so *block_on* waits on *gate* before rendering.

    Every other section renders immediately, so only the section under test
    holds the worker (and therefore the loading state) open.
    """
    from openreview_cli.tui.tabs.settings import SettingsTab

    real = SettingsTab._text_for

    def _fn(self: Any, section: str) -> str:
        if section == block_on:
            gate.wait(timeout=10)
        return real(self, section)

    return _fn


async def test_settings_tab_shows_loading_state_until_section_renders(
    isolated_xdg: dict[str, Path],
) -> None:
    """The section body stays hidden behind #settings-loading until it renders."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.tabs.settings import SettingsTab

    gate = threading.Event()
    with (
        patch("openreview_cli.tui.tabs.settings.get_slot_configs", return_value={}),
        patch.object(SettingsTab, "_text_for", _gated_text_for("gateway", gate)),
    ):
        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("5")
            await pilot.pause()

            loading = app.query_one("#settings-loading", LoadingState)
            display = app.query_one("#section-content-display", Static)

            assert loading.display is True
            assert display.display is False
            assert _spinner_width(app, "#settings-loading") > 0

            gate.set()
            await _wait_for_workers(app)
            await pilot.pause()

            assert loading.display is False
            assert display.display is True
            assert "No providers configured yet" in display.content


async def test_settings_second_section_click_wins_over_slow_first_render(
    isolated_xdg: dict[str, Path],
) -> None:
    """A newer section click must win; the stale render must not clobber it."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.tabs.settings import SettingsTab

    config_gate = threading.Event()
    with (
        patch("openreview_cli.tui.tabs.settings.get_slot_configs", return_value={}),
        patch.object(SettingsTab, "_text_for", _gated_text_for("configuration", config_gate)),
    ):
        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            settings = app.query_one(SettingsTab)

            # First click selects a section whose render is held open.
            settings.select_section("configuration")
            await pilot.pause()

            loading = app.query_one("#settings-loading", LoadingState)
            display = app.query_one("#section-content-display", Static)
            assert loading.display is True

            # Second click selects a section that renders immediately.
            settings.select_section("about")
            await pilot.pause()
            await _wait_for_workers(app)
            await pilot.pause()

            assert loading.display is False
            assert display.display is True
            assert "Accessibility" in display.content
            assert "Configuration" not in display.content

            # Releasing the stale render must leave the newer section in place.
            config_gate.set()
            await _wait_for_workers(app)
            await pilot.pause()

            assert "Accessibility" in display.content
            assert "Configuration" not in display.content


async def test_settings_load_failure_notifies_and_recovers(
    isolated_xdg: dict[str, Path],
) -> None:
    """A failed section render is reported, never fatal, and reveals the pane."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.tabs.settings import SettingsTab

    def _boom(self: Any, section: str) -> str:
        raise sqlite_error()

    recorder = _Notifications()
    with patch.object(SettingsTab, "_text_for", _boom):
        app = OpenReviewApp()
        app.notify = recorder  # type: ignore[method-assign]
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await _wait_for_workers(app)
            await pilot.pause()

            assert app.is_running
            failures = recorder.load_failures()
            assert failures
            assert failures[-1].get("severity") == "error"
            assert failures[-1].get("markup") is False

            loading = app.query_one("#settings-loading", LoadingState)
            display = app.query_one("#section-content-display", Static)
            assert loading.display is False
            assert display.display is True


def sqlite_error() -> Exception:
    """A realistic store-style failure (the shape domain reads translate)."""
    import sqlite3

    return sqlite3.OperationalError("database is locked")
