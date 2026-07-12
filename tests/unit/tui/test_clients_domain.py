"""Unit tests for domain/clients.py wrappers (T023)."""

from __future__ import annotations

from unittest.mock import patch


class TestClientsDomain:
    """Domain wrappers delegate to storage correctly."""

    @patch("openreview_cli.tui.domain.clients.add_client")
    @patch("openreview_cli.tui.domain.clients.get_db_path")
    def test_add_client_via_tui_calls_storage(self, mock_get_db_path, mock_add_client) -> None:
        """add_client_via_tui delegates to storage.add_client."""
        from openreview_cli.tui.domain.clients import add_client_via_tui

        mock_get_db_path.return_value = "/fake/db.sqlite"
        add_client_via_tui("acme", "Acme Corp")
        mock_add_client.assert_called_once_with("/fake/db.sqlite", "acme", "Acme Corp")

    @patch("openreview_cli.tui.domain.clients.list_clients")
    @patch("openreview_cli.tui.domain.clients.get_db_path")
    def test_list_clients_via_tui_returns_data(self, mock_get_db_path, mock_list_clients) -> None:
        """list_clients_via_tui returns what storage returns."""
        from openreview_cli.tui.domain.clients import list_clients_via_tui

        mock_get_db_path.return_value = "/fake/db.sqlite"
        expected = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]
        mock_list_clients.return_value = expected
        result = list_clients_via_tui()
        assert result == expected
        mock_list_clients.assert_called_once_with("/fake/db.sqlite")

    @patch("openreview_cli.tui.domain.clients.get_client")
    @patch("openreview_cli.tui.domain.clients.get_db_path")
    def test_get_client_via_tui_returns_client(self, mock_get_db_path, mock_get_client) -> None:
        """get_client_via_tui returns a client dict."""
        from openreview_cli.tui.domain.clients import get_client_via_tui

        mock_get_db_path.return_value = "/fake/db.sqlite"
        expected = {"id": "acme", "name": "Acme Corp"}
        mock_get_client.return_value = expected
        result = get_client_via_tui("acme")
        assert result == expected
        mock_get_client.assert_called_once_with("/fake/db.sqlite", "acme")

    @patch("openreview_cli.tui.domain.clients.get_client")
    @patch("openreview_cli.tui.domain.clients.get_db_path")
    def test_get_client_via_tui_returns_none(self, mock_get_db_path, mock_get_client) -> None:
        """get_client_via_tui returns None for missing client."""
        from openreview_cli.tui.domain.clients import get_client_via_tui

        mock_get_db_path.return_value = "/fake/db.sqlite"
        mock_get_client.return_value = None
        result = get_client_via_tui("nonexistent")
        assert result is None

    @patch("openreview_cli.tui.domain.clients.client_has_reviews")
    @patch("openreview_cli.tui.domain.clients.delete_client")
    @patch("openreview_cli.tui.domain.clients.get_db_path")
    def test_delete_client_via_tui_returns_ok_when_no_reviews(
        self, mock_get_db_path, mock_delete_client, mock_client_has_reviews
    ) -> None:
        """delete_client_via_tui returns 'ok' when client has no reviews."""
        from openreview_cli.tui.domain.clients import delete_client_via_tui

        mock_get_db_path.return_value = "/fake/db.sqlite"
        mock_client_has_reviews.return_value = False
        result = delete_client_via_tui("acme")
        assert result == "ok"
        mock_delete_client.assert_called_once_with("/fake/db.sqlite", "acme", force=False)

    @patch("openreview_cli.tui.domain.clients.client_has_reviews")
    @patch("openreview_cli.tui.domain.clients.delete_client")
    @patch("openreview_cli.tui.domain.clients.get_db_path")
    def test_delete_client_via_tui_returns_has_reviews(
        self, mock_get_db_path, mock_delete_client, mock_client_has_reviews
    ) -> None:
        """delete_client_via_tui returns 'has_reviews' when cascade=False and client has reviews."""
        from openreview_cli.tui.domain.clients import delete_client_via_tui

        mock_get_db_path.return_value = "/fake/db.sqlite"
        mock_client_has_reviews.return_value = True
        result = delete_client_via_tui("acme")
        assert result == "has_reviews"
        mock_delete_client.assert_not_called()

    @patch("openreview_cli.tui.domain.clients.client_has_reviews")
    @patch("openreview_cli.tui.domain.clients.delete_client")
    @patch("openreview_cli.tui.domain.clients.get_db_path")
    def test_delete_client_via_tui_cascade_ignores_reviews(
        self, mock_get_db_path, mock_delete_client, mock_client_has_reviews
    ) -> None:
        """delete_client_via_tui cascade=True bypasses review check."""
        from openreview_cli.tui.domain.clients import delete_client_via_tui

        mock_get_db_path.return_value = "/fake/db.sqlite"
        mock_client_has_reviews.return_value = True
        result = delete_client_via_tui("acme", cascade=True)
        assert result == "ok"
        mock_delete_client.assert_called_once_with("/fake/db.sqlite", "acme", force=True)
