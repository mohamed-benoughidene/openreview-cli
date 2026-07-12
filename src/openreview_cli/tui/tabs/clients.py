"""Clients tab — client CRUD with filterable list."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from openreview_cli.tui.domain import clients as _dc
from openreview_cli.tui.screens.client_form import ClientForm
from openreview_cli.tui.screens.confirm import ConfirmModal


class ClientsTab(Static):
    """Clients tab with filterable list, add, and delete."""

    DEFAULT_CSS = """
    ClientsTab { padding: 1; }
    #client-filter { width: 1fr; margin: 0 1 0 0; }
    #client-list { height: 1fr; min-height: 3; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._selected_client_id: str | None = None
        self._clients: list[dict[str, str]] = []

    def compose(self) -> ComposeResult:
        yield Static("Clients", id="clients-header")
        yield Horizontal(
            Input(placeholder="Type to filter clients...", id="client-filter"),
            Button("+ New client", id="btn-new-client", variant="primary"),
            id="clients-toolbar",
        )
        yield ListView(id="client-list")
        yield Horizontal(
            Button("Delete selected", id="btn-delete", variant="error", disabled=True),
            id="clients-actions",
        )

    def on_mount(self) -> None:
        self._load()

    def _on_input_changed(self, event: Input.Changed) -> None:
        self._load(event.value)

    def _load(self, filter_text: str = "") -> None:
        """Fetch and display clients, optionally filtered."""
        self._clients = _dc.list_clients_via_tui()

        if filter_text:
            lowered = filter_text.lower()
            self._clients = [
                c
                for c in self._clients
                if lowered in c["id"].lower() or lowered in c["name"].lower()
            ]

        list_view = self.query_one("#client-list", ListView)
        list_view.clear()

        if not self._clients:
            list_view.append(ListItem(Label("No clients yet. Add one with [+ New client].")))
            self._selected_client_id = None
            self.query_one("#btn-delete", Button).disabled = True
            return

        for c in self._clients:
            list_view.append(ListItem(Label(f"{c['id']} \u2014 {c['name']}")))

        self._selected_client_id = None
        self.query_one("#btn-delete", Button).disabled = True

    def _on_list_view_selected(self, event: ListView.Selected) -> None:
        """Track selected client for delete action."""
        lv = event.list_view
        if lv.index is not None and lv.index < len(self._clients):
            self._selected_client_id = self._clients[lv.index]["id"]
            self.query_one("#btn-delete", Button).disabled = False
        else:
            self._selected_client_id = None
            self.query_one("#btn-delete", Button).disabled = True

    def _on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-new-client":
            self._open_add_form()
        elif btn_id == "btn-delete":
            self._confirm_delete()

    def _open_add_form(self) -> None:
        def on_result(result: dict[str, str] | None) -> None:
            if result:
                _dc.add_client_via_tui(result["client_id"], result["name"], result.get("notes"))
                self._load()
                lv = self.query_one("#client-list", ListView)
                new_id = result["client_id"]
                for i, c in enumerate(self._clients):
                    if c["id"] == new_id:
                        lv.index = i
                        break

        self.app.push_screen(ClientForm(), on_result)

    def _confirm_delete(self) -> None:
        client_id = self._selected_client_id
        if not client_id:
            return
        if _dc.client_has_reviews(_dc.get_db_path(), client_id):  # type: ignore[attr-defined]

            def on_confirm(result: bool | None) -> None:
                if result:
                    _dc.delete_client_via_tui(client_id, cascade=True)
                    self._load()

            self.app.push_screen(
                ConfirmModal(
                    "Delete client",
                    f"Client '{client_id}' has reviews. Delete all reviews too?",
                    danger=True,
                ),
                on_confirm,
            )
        else:
            _dc.delete_client_via_tui(client_id)
            self._load()
