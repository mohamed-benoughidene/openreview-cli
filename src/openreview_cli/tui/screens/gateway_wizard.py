"""4-step gateway setup wizard (FR-030 → FR-032a)."""

from __future__ import annotations

from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from openreview_cli.slots import VALID_SLOTS
from openreview_cli.tui.domain.gateway import (
    gateway_health_check,
    list_models,
    list_providers,
    provider_has_key,
    save_api_key,
    save_slot_config,
)


def _mount_list(body: Vertical, header: str, items: list[ListItem], list_id: str) -> None:
    body.mount(Static(header))
    body.mount(ListView(*items, id=list_id))


class GatewayWizard(Screen[bool]):
    """Four-step gateway configuration wizard (FR-030 → FR-032a)."""

    DEFAULT_CSS: ClassVar[str] = """
    #wizard-body { width: 56; height: auto; max-height: 80%; border: solid $primary; padding: 1 2; margin: 1 0; }
    #wizard-nav { width: 56; height: 3; align: center middle; }
    #wizard-nav Button { margin: 0 1; }
    ListView { height: 12; border: none; }
    Input { margin: 1 0; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._step: int = 1
        self._slot: str | None = None
        self._provider: str | None = None
        self._model: str | None = None
        self._key: str | None = None
        self._providers: list[dict[str, Any]] = []
        self._models: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Static("Gateway Setup Wizard", classes="wizard-title")
        yield Static(id="wizard-step")
        yield Vertical(id="wizard-body")
        yield Static(id="wizard-error")
        with Horizontal(id="wizard-nav"):
            yield Button("Cancel", id="wizard-cancel", variant="error")
            yield Button("Back", id="wizard-back", variant="default")
            yield Button("Next", id="wizard-next", variant="primary")

    def on_mount(self) -> None:
        self._providers = list_providers()
        self._show_step(1)

    def _show_step(self, step: int) -> None:
        self._step = step
        body = self.query_one("#wizard-body", Vertical)
        body.remove_children()
        self.query_one("#wizard-step", Static).update(f"Step {step} of 4")
        self.query_one("#wizard-error", Static).update("")

        if step == 1:
            self._render_slot_step(body)
        elif step == 2:
            self._render_provider_step(body)
        elif step == 3:
            self._render_model_step(body)
        elif step == 4:
            self._render_key_step(body)

        self._update_buttons()

    def _render_slot_step(self, body: Vertical) -> None:
        items = [ListItem(Label(s.capitalize()), name=s) for s in sorted(VALID_SLOTS)]
        _mount_list(body, "Select a model slot:", items, "slot-list")

    def _render_provider_step(self, body: Vertical) -> None:
        body.mount(Input(placeholder="Type to filter...", id="provider-filter"))
        items = [ListItem(Label(p["name"]), name=p["name"]) for p in self._providers]
        _mount_list(body, "Select a provider (type to filter):", items, "provider-list")

    def _render_model_step(self, body: Vertical) -> None:
        provider = self._provider or ""
        self._models = list_models(provider)
        items = []
        for m in self._models:
            mid = m.get("model_id", "")
            ctx = m.get("context", "")
            items.append(ListItem(Label(f"{mid}  ({ctx:,} ctx)" if ctx else mid), name=mid))
        _mount_list(body, f"Select a model for [bold]{provider}[/bold]:", items, "model-list")

    def _render_key_step(self, body: Vertical) -> None:
        provider = self._provider or ""
        if provider_has_key(provider):
            body.mount(Static(f"[green]Using saved key for {provider}.[/green]"))
            self._key = "<saved>"
        else:
            body.mount(Static(f"Enter API key for [bold]{provider}[/bold]:"))
            body.mount(
                Input(password=True, placeholder="Paste or type API key...", id="api-key-input")
            )

    # ── event handlers ──────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if self._step == 1 and event.list_view.id == "slot-list":
            self._slot = (event.item.name or "").lower()
            self._update_buttons()
        elif self._step == 2 and event.list_view.id == "provider-list":
            self._provider = event.item.name or ""
            self._update_buttons()
        elif self._step == 3 and event.list_view.id == "model-list":
            self._model = event.item.name or ""
            self._update_buttons()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "provider-filter" and self._step == 2:
            self._filter_providers(event.value)
        if event.input.id == "api-key-input" and self._step == 4:
            self._key = event.value
            self._update_buttons()

    def _filter_providers(self, text: str) -> None:
        provider_list = self.query_one("#provider-list", ListView)
        filter_lower = text.lower()
        for item in list(provider_list.children):
            child = item.children[0] if item.children else None
            label_text = (
                str(child.content).lower()
                if child is not None and hasattr(child, "content")
                else ""
            )
            item.display = not filter_lower or filter_lower in label_text

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "wizard-cancel":
            self.dismiss(False)
        elif btn_id == "wizard-back" and self._step > 1:
            self._show_step(self._step - 1)
        elif btn_id == "wizard-next":
            if self._step < 4:
                self._show_step(self._step + 1)
            else:
                self._do_save()

    # ── navigation helpers ──────────────────────────────────────

    def _update_buttons(self) -> None:
        back = self.query_one("#wizard-back", Button)
        next_btn = self.query_one("#wizard-next", Button)
        back.disabled = self._step == 1

        can_next = False
        if self._step == 1 and self._slot:
            can_next = True
        elif self._step == 2 and self._provider:
            can_next = True
        elif self._step == 3 and self._model:
            can_next = True
        elif self._step == 4:
            can_next = bool(self._key)
        next_btn.disabled = not can_next
        next_btn.label = "Save" if self._step == 4 else "Next"

    def _on_save_error(self, msg: str) -> None:
        self.query_one("#wizard-error", Static).update(msg)
        self.query_one("#wizard-next", Button).disabled = False
        self.query_one("#wizard-next", Button).label = "Retry Save"

    def _do_save(self) -> None:
        if not self._slot or not self._provider or not self._model:
            return
        if self._key and self._key != "<saved>":
            save_api_key(self._provider, self._key)
        save_slot_config(self._slot, self._provider, self._model)
        health = gateway_health_check()
        slot_status = health.get(self._slot, {}).get("status", "")
        if slot_status in ("configured", "missing_api_key"):
            self.dismiss(True)
        else:
            self._on_save_error(
                f"[red]Warning:[/red] Slot {self._slot} status: {slot_status}. "
                "Key was saved; you can retry or skip."
            )
