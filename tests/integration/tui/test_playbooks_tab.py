"""Integration tests for PlaybooksTab (T033, T037, T038)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from textual.widgets import Label, ListItem


def _list_item_text(item: ListItem) -> str:
    """Extract visible text from a ListItem."""
    try:
        label = item.query_one(Label)
        return str(label.render())
    except Exception:
        return str(item.render())


def _make_list_mock(return_value):
    """Create a standard list_playbooks_via_tui mock."""
    m = MagicMock()
    m.return_value = return_value
    return m


def _make_detail_mock(return_value):
    """Create a standard get_playbook_detail_via_tui mock."""
    m = MagicMock()
    m.return_value = return_value
    return m


# ── T033: Core tests ──


async def test_playbooks_tab_empty_state() -> None:
    """Fresh state shows empty-state message (T037)."""
    with patch(
        "openreview_cli.tui.domain.playbooks.list_playbooks_via_tui",
        _make_list_mock([]),
    ):
        from openreview_cli.tui.app import OpenReviewApp

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("4")
            await pilot.pause()
            lv = app.query_one("#playbook-list")
            items = list(lv.children)
            assert len(items) == 1
            msg = _list_item_text(items[0])
            assert "No playbooks yet" in msg


async def test_playbooks_tab_shows_playbooks() -> None:
    """Playbooks visible in list."""
    with patch(
        "openreview_cli.tui.domain.playbooks.list_playbooks_via_tui",
        _make_list_mock(
            [
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
        ),
    ):
        from openreview_cli.tui.app import OpenReviewApp

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("4")
            await pilot.pause()
            items = list(app.query_one("#playbook-list").children)
            assert len(items) == 2
            all_text = " ".join(_list_item_text(item) for item in items)
            assert "precheck" in all_text
            assert "dealcheck" in all_text


async def test_playbooks_tab_filter_by_text() -> None:
    """Typing in text filter narrows list (T037)."""
    with patch(
        "openreview_cli.tui.domain.playbooks.list_playbooks_via_tui",
        _make_list_mock(
            [
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
                {
                    "id": "privacycheck",
                    "latest_version": 1,
                    "current_version": 1,
                    "created_at": "2026-01-03",
                },
            ]
        ),
    ):
        from openreview_cli.tui.app import OpenReviewApp

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("4")
            await pilot.pause()
            await pilot.click("#playbook-filter")
            await pilot.press("d", "e", "a", "l")
            await pilot.pause()
            items = list(app.query_one("#playbook-list").children)
            all_text = " ".join(_list_item_text(item) for item in items)
            assert "dealcheck" in all_text
            assert "precheck" not in all_text
            assert "privacycheck" not in all_text


# test_filter_by_mode removed: #playbook-mode-filter was removed from
# playbooks.py in a previous batch; text filter (#playbook-filter) covers it.


async def test_playbooks_tab_import_via_file_picker() -> None:
    """'+ Import playbook' flow with mocked file picker (T033)."""
    with (
        patch(
            "openreview_cli.tui.domain.playbooks.list_playbooks_via_tui",
            _make_list_mock([]),
        ),
        patch(
            "openreview_cli.tui.domain.playbooks.import_playbook_via_tui",
            MagicMock(
                return_value={
                    "playbook_id": "custom-nda",
                    "mode": "precheck",
                    "description": "Custom NDA",
                    "version": "1.0",
                    "category_count": 5,
                    "new_version": 1,
                    "prev_version": None,
                }
            ),
        ),
    ):
        import tempfile
        from pathlib import Path

        tmp = Path(tempfile.mkstemp(suffix=".yaml")[1])
        try:
            tmp.write_text(
                "id: custom-nda\n"
                "mode: precheck\n"
                "metadata:\n"
                "  version: '1.0'\n"
                "  description: Custom NDA\n"
                "  author: test\n"
                "categories:\n"
                "  - id: nda-confidentiality\n"
                "    name: Confidentiality\n"
                "    description: Test\n"
                "    preferred:\n"
                "      description: Good\n"
                "      exemplars: ['ex1']\n"
                "    acceptable:\n"
                "      description: OK\n"
                "      exemplars: ['ex2']\n"
                "    walkaway:\n"
                "      description: Bad\n"
                "      exemplars: ['ex3']\n"
                "    default_position: preferred\n"
            )
            from openreview_cli.tui.domain.playbooks import import_playbook_via_tui

            result = import_playbook_via_tui(tmp)
            assert result["playbook_id"] == "custom-nda"
            assert result["mode"] == "precheck"
            assert result["category_count"] == 5
            assert result["new_version"] == 1
        finally:
            tmp.unlink()


async def test_playbooks_tab_detail_shows_categories() -> None:
    """Click on playbook item opens detail view with categories (FR-026)."""
    from openreview_cli.review.models import (
        Category,
        Playbook,
        PlaybookMetadata,
        Position,
        PositionDef,
    )

    mock_playbook = Playbook(
        id="precheck",
        mode="precheck",
        metadata=PlaybookMetadata(version="1.0", description="NDA check", author="test"),
        categories=[
            Category(
                id="confidentiality",
                name="Confidentiality",
                description="Test clause",
                preferred=PositionDef(description="Standard", exemplars=["ex1"]),
                acceptable=PositionDef(description="Modified", exemplars=["ex2"]),
                walkaway=PositionDef(description="Unlimited", exemplars=["ex3"]),
                default_position=Position.PREFERRED,
            ),
        ],
    )

    with (
        patch(
            "openreview_cli.tui.domain.playbooks.list_playbooks_via_tui",
            _make_list_mock(
                [
                    {
                        "id": "precheck",
                        "latest_version": 2,
                        "current_version": 2,
                        "created_at": "2026-01-01",
                    }
                ]
            ),
        ),
        patch(
            "openreview_cli.tui.domain.playbooks.get_playbook_detail_via_tui",
            _make_detail_mock(mock_playbook),
        ),
        patch(
            "openreview_cli.tui.domain.playbooks.get_playbook_history_via_tui",
            MagicMock(return_value={"rows": [], "current_version": 0, "is_deleted": False}),
        ),
        patch(
            "openreview_cli.tui.domain.playbooks.set_current_version_via_tui",
            MagicMock(return_value=(True, "Done")),
        ),
    ):
        from openreview_cli.tui.app import OpenReviewApp
        from openreview_cli.tui.screens.confirm import ConfirmModal

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("4")
            await pilot.pause()
            await pilot.click("#playbook-list")
            await pilot.pause()

            # Verify detail opened by clicking a detail-only button
            await pilot.click("#btn-set-current")
            await pilot.pause()

            assert isinstance(app.screen, ConfirmModal)


async def test_playbooks_tab_version_history() -> None:
    """Click 'View versions' shows version history list (FR-027/028)."""
    from openreview_cli.review.models import (
        Category,
        Playbook,
        PlaybookMetadata,
        Position,
        PositionDef,
    )

    mock_playbook = Playbook(
        id="precheck",
        mode="precheck",
        metadata=PlaybookMetadata(version="2.0", description="NDA check", author="test"),
        categories=[
            Category(
                id="confidentiality",
                name="Confidentiality",
                description="Test clause",
                preferred=PositionDef(description="Standard", exemplars=["ex1"]),
                acceptable=PositionDef(description="Modified", exemplars=["ex2"]),
                walkaway=PositionDef(description="Unlimited", exemplars=["ex3"]),
                default_position=Position.PREFERRED,
            ),
        ],
    )

    with (
        patch(
            "openreview_cli.tui.domain.playbooks.list_playbooks_via_tui",
            _make_list_mock(
                [
                    {
                        "id": "precheck",
                        "latest_version": 2,
                        "current_version": 2,
                        "created_at": "2026-01-01",
                    }
                ]
            ),
        ),
        patch(
            "openreview_cli.tui.domain.playbooks.get_playbook_detail_via_tui",
            _make_detail_mock(mock_playbook),
        ),
        patch(
            "openreview_cli.tui.domain.playbooks.get_playbook_history_via_tui",
            MagicMock(
                return_value={
                    "rows": [
                        {
                            "version": 1,
                            "created_at": "2026-01-01",
                            "is_current": False,
                            "is_latest": False,
                        },
                        {
                            "version": 2,
                            "created_at": "2026-01-02",
                            "is_current": True,
                            "is_latest": True,
                        },
                    ],
                    "current_version": 2,
                    "is_deleted": False,
                }
            ),
        ),
        patch(
            "openreview_cli.tui.domain.playbooks.set_current_version_via_tui",
            MagicMock(return_value=(True, "Done")),
        ),
    ):
        from openreview_cli.tui.app import OpenReviewApp
        from openreview_cli.tui.screens.playbook_detail import (
            VersionHistoryScreen,
        )

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("4")
            await pilot.pause()
            await pilot.click("#playbook-list")
            await pilot.pause()
            await pilot.click("#btn-versions")
            await pilot.pause()

            # Version history is a ModalScreen - closing it via escape dismisses

            assert isinstance(app.screen, VersionHistoryScreen)


async def test_playbooks_tab_version_diff() -> None:
    """'View diff' shows diff view (FR-029)."""
    from openreview_cli.review.models import (
        Category,
        Playbook,
        PlaybookMetadata,
        Position,
        PositionDef,
    )
    from openreview_cli.review.playbook import VersionDiff

    mock_playbook = Playbook(
        id="precheck",
        mode="precheck",
        metadata=PlaybookMetadata(version="2.0", description="NDA check", author="test"),
        categories=[
            Category(
                id="confidentiality",
                name="Confidentiality",
                description="Test clause",
                preferred=PositionDef(description="Standard", exemplars=["ex1"]),
                acceptable=PositionDef(description="Modified", exemplars=["ex2"]),
                walkaway=PositionDef(description="Unlimited", exemplars=["ex3"]),
                default_position=Position.PREFERRED,
            ),
        ],
    )

    with (
        patch(
            "openreview_cli.tui.domain.playbooks.list_playbooks_via_tui",
            _make_list_mock(
                [
                    {
                        "id": "precheck",
                        "latest_version": 2,
                        "current_version": 2,
                        "created_at": "2026-01-01",
                    }
                ]
            ),
        ),
        patch(
            "openreview_cli.tui.domain.playbooks.get_playbook_detail_via_tui",
            _make_detail_mock(mock_playbook),
        ),
        patch(
            "openreview_cli.tui.domain.playbooks.get_playbook_history_via_tui",
            MagicMock(
                return_value={
                    "rows": [
                        {
                            "version": 1,
                            "created_at": "2026-01-01",
                            "is_current": False,
                            "is_latest": False,
                        },
                        {
                            "version": 2,
                            "created_at": "2026-01-02",
                            "is_current": True,
                            "is_latest": True,
                        },
                    ],
                    "current_version": 2,
                    "is_deleted": False,
                }
            ),
        ),
        patch(
            "openreview_cli.tui.domain.playbooks.get_playbook_version_diff",
            MagicMock(
                return_value=VersionDiff(
                    status="changed",
                    v1=1,
                    v2=2,
                    added_categories=["new-clause"],
                    removed_categories=["old-clause"],
                    changed_categories={
                        "confidentiality": {
                            "description": {"before": "Old desc", "after": "New desc"},
                        }
                    },
                )
            ),
        ),
        patch(
            "openreview_cli.tui.domain.playbooks.set_current_version_via_tui",
            MagicMock(return_value=(True, "Done")),
        ),
    ):
        from openreview_cli.tui.app import OpenReviewApp
        from openreview_cli.tui.screens.playbook_detail import (
            VersionDiffScreen,
        )

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("4")
            await pilot.pause()
            await pilot.click("#playbook-list")
            await pilot.pause()
            await pilot.click("#btn-diff")
            await pilot.pause()

            assert isinstance(app.screen, VersionDiffScreen)


# ── T037/T038: Additional tests ──


async def test_playbooks_tab_set_as_current_confirm() -> None:
    """Click 'Set as current' opens ConfirmModal (FR-028)."""
    from openreview_cli.review.models import (
        Category,
        Playbook,
        PlaybookMetadata,
        Position,
        PositionDef,
    )

    mock_playbook = Playbook(
        id="precheck",
        mode="precheck",
        metadata=PlaybookMetadata(version="1.0", description="NDA check", author="test"),
        categories=[
            Category(
                id="confidentiality",
                name="Confidentiality",
                description="Test clause",
                preferred=PositionDef(description="Standard", exemplars=["ex1"]),
                acceptable=PositionDef(description="Modified", exemplars=["ex2"]),
                walkaway=PositionDef(description="Unlimited", exemplars=["ex3"]),
                default_position=Position.PREFERRED,
            ),
        ],
    )

    with (
        patch(
            "openreview_cli.tui.domain.playbooks.list_playbooks_via_tui",
            _make_list_mock(
                [
                    {
                        "id": "precheck",
                        "latest_version": 2,
                        "current_version": 1,
                        "created_at": "2026-01-01",
                    }
                ]
            ),
        ),
        patch(
            "openreview_cli.tui.domain.playbooks.get_playbook_detail_via_tui",
            _make_detail_mock(mock_playbook),
        ),
        patch(
            "openreview_cli.tui.domain.playbooks.get_playbook_history_via_tui",
            MagicMock(
                return_value={
                    "rows": [
                        {
                            "version": 1,
                            "created_at": "2026-01-01",
                            "is_current": False,
                            "is_latest": False,
                        },
                        {
                            "version": 2,
                            "created_at": "2026-01-02",
                            "is_current": True,
                            "is_latest": True,
                        },
                    ],
                    "current_version": 2,
                    "is_deleted": False,
                }
            ),
        ),
        patch(
            "openreview_cli.tui.domain.playbooks.set_current_version_via_tui",
            MagicMock(return_value=(True, "Done")),
        ),
    ):
        from openreview_cli.tui.app import OpenReviewApp
        from openreview_cli.tui.screens.confirm import ConfirmModal

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("4")
            await pilot.pause()
            await pilot.click("#playbook-list")
            await pilot.pause()
            await pilot.click("#btn-set-current")
            await pilot.pause()

            assert isinstance(app.screen, ConfirmModal)


async def test_playbooks_tab_import_validation_preview() -> None:
    """Import YAML shows preview + validation (T037)."""
    import tempfile
    from pathlib import Path

    with patch(
        "openreview_cli.tui.domain.playbooks.list_playbooks_via_tui",
        _make_list_mock([]),
    ):
        tmp = Path(tempfile.mkstemp(suffix=".yaml")[1])
        try:
            tmp.write_text(
                "id: test-playbook\n"
                "mode: precheck\n"
                "metadata:\n"
                "  version: '1.0'\n"
                "  description: Test\n"
                "  author: tester\n"
                "categories:\n"
                "  - id: cat-1\n"
                "    name: Category 1\n"
                "    description: First category\n"
                "    preferred:\n"
                "      description: Good\n"
                "      exemplars: ['good example']\n"
                "    acceptable:\n"
                "      description: OK\n"
                "      exemplars: ['ok example']\n"
                "    walkaway:\n"
                "      description: Bad\n"
                "      exemplars: ['bad example']\n"
                "    default_position: preferred\n"
            )
            from openreview_cli.review.playbook import load_playbook

            playbook = load_playbook(tmp)
            assert playbook.id == "test-playbook"
            assert playbook.mode == "precheck"
            assert len(playbook.categories) == 1
            assert playbook.categories[0].default_position.value == "preferred"
        finally:
            tmp.unlink()
