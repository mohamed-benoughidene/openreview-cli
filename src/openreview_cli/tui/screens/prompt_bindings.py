"""Prompt bindings — the bind, unbind and bindings surfaces (Task 6).

``PromptBindingsScreen`` lists **every** slot binding (CLI parity with
``openreview prompt bindings``), marks the row that belongs to the prompt it was
opened for, and offers a per-row unbind plus a "bind this prompt" entry point.
``PromptBindModal`` binds one prompt to a slot.

The overwrite confirmation runs *inside* the modal, before it dismisses.  The
store's ``bind`` silently replaces an existing binding (``INSERT OR REPLACE``,
``store.py:176``), and the write itself happens in the *caller*
(``tabs/prompts.py:242-260``), so a modal that dismissed first and confirmed
later would hand the caller a payload it would then write unconditionally.  A
slot already bound to a *different* ``(prompt_name, prompt_version)`` therefore
pushes ``ConfirmModal(danger=True)`` and only dismisses with the payload on Yes.

``VALID_SLOTS`` is imported from ``openreview_cli.slots`` (dependency-free by
design) rather than the gateway package, which would pull in litellm.
"""

from __future__ import annotations

from typing import Any, ClassVar, cast

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Label, ListItem, ListView, Select, Static

from openreview_cli.slots import VALID_SLOTS
from openreview_cli.tui.domain import prompts as _prompts
from openreview_cli.tui.screens.confirm import ConfirmModal

_EMPTY_MESSAGE = "No slot bindings yet. Use [Bind this prompt\u2026] to create one."


class _BindingRow(ListItem):
    """One slot binding: the slot, its prompt/version and an Unbind button."""

    def __init__(self, binding: dict[str, Any], is_this_prompt: bool) -> None:
        slot = str(binding["slot"])
        self.slot = slot
        marker = "  \u2190 this prompt" if is_this_prompt else ""
        # markup=False: the prompt name is user-authored and may contain
        # bracketed text the Rich markup parser would otherwise consume.
        label = f"{slot}: {binding['prompt_name']} v{binding['prompt_version']}{marker}"
        super().__init__(
            Horizontal(
                Label(label, markup=False),
                Button("Unbind", id=f"btn-unbind-{slot}", variant="error"),
                classes="binding-row",
            )
        )


class PromptBindingsScreen(Screen[None]):
    """List every slot binding and unbind one, with confirmation."""

    DEFAULT_CSS: ClassVar[str] = """
    PromptBindingsScreen { padding: 1; }
    #bindings-title { text-style: bold; background: $primary; color: $text; padding: 1 2; margin: 0 0 1 0; }
    #bindings-subtitle { padding: 0 0 0 1; margin: 0 0 1 0; color: $text-muted; }
    #bindings-list { height: 1fr; min-height: 3; }
    .binding-row { height: auto; }
    .binding-row Label { width: 1fr; }
    #bindings-empty { padding: 1 2; color: $text-muted; }
    #bindings-actions { dock: bottom; height: 3; padding: 0 1; align: center middle; }
    #bindings-actions Button { margin: 0 1; min-width: 12; }
    """

    BINDINGS: ClassVar = [("escape", "close", "Back")]

    def __init__(self, prompt_name: str) -> None:
        super().__init__()
        self._prompt_name = prompt_name
        self._rows: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Bindings", id="bindings-title")
            # markup=False: the prompt name is user-authored content.
            yield Static(
                f"Opened for prompt '{self._prompt_name}'. Showing every slot binding.",
                id="bindings-subtitle",
                markup=False,
            )
            yield ListView(id="bindings-list")
            yield Static(_EMPTY_MESSAGE, id="bindings-empty", markup=False)
            with Horizontal(id="bindings-actions"):
                yield Button("Bind this prompt\u2026", id="btn-bind-new", variant="primary")
                yield Button("Close (Esc)", id="btn-bindings-close", variant="default")

    def on_mount(self) -> None:
        self._load()

    def _load(self) -> None:
        """Reload every binding and re-render the rows.

        ``list_bindings_via_tui`` is the store boundary: it re-raises any store
        failure as ``ValueError``, which is caught here so no exception can
        reach a Textual handler.
        """
        try:
            self._rows = _prompts.list_bindings_via_tui()
        except Exception as exc:
            self._rows = []
            self.notify(f"Load bindings failed: {exc}", severity="error", markup=False)

        list_view = self.query_one("#bindings-list", ListView)
        empty = self.query_one("#bindings-empty", Static)
        list_view.clear()

        if not self._rows:
            list_view.display = False
            empty.display = True
            return

        list_view.display = True
        empty.display = False
        for binding in self._rows:
            list_view.append(_BindingRow(binding, str(binding["prompt_name"]) == self._prompt_name))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "btn-bindings-close":
            self.dismiss(None)
        elif button_id == "btn-bind-new":
            self._open_bind()
        elif button_id.startswith("btn-unbind-"):
            self._confirm_unbind(button_id.removeprefix("btn-unbind-"))

    def action_close(self) -> None:
        self.dismiss(None)

    def _open_bind(self) -> None:
        """Bind *this* prompt to a slot; this screen is the caller that writes."""

        def on_result(result: dict[str, Any] | None) -> None:
            if not result:
                return
            try:
                _prompts.bind_prompt_via_tui(
                    result["slot"], self._prompt_name, int(result["version"])
                )
            except Exception as exc:
                self.notify(f"Bind failed: {exc}", severity="error", markup=False)
                return
            self._load()

        self.app.push_screen(PromptBindModal(prompt_name=self._prompt_name), on_result)

    def _confirm_unbind(self, slot: str) -> None:
        binding = next((b for b in self._rows if str(b["slot"]) == slot), None)
        if binding is None:
            return

        message = (
            f"Unbind slot '{slot}' from prompt '{binding['prompt_name']}' "
            f"v{binding['prompt_version']}?"
        )

        def on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                _prompts.unbind_prompt_via_tui(slot)
            except Exception as exc:
                # The binding may have vanished between load and confirm; the
                # store's message is surfaced and the screen stays up.
                self.notify(f"Unbind failed: {exc}", severity="error", markup=False)
                return
            self._load()

        self.app.push_screen(ConfirmModal("Unbind slot", message, danger=True), on_confirm)


class PromptBindModal(ModalScreen[dict[str, Any] | None]):
    """Choose a slot and a version for one prompt, confirming an overwrite.

    Dismisses ``{"slot": str, "version": int}`` or ``None``.  The *caller*
    performs ``bind_prompt_via_tui``; the overwrite confirmation therefore runs
    here, before the dismiss, so a decline never reaches the caller.
    """

    DEFAULT_CSS: ClassVar[str] = """
    PromptBindModal { align: center middle; }
    PromptBindModal > Vertical { width: 60; padding: 1 2; background: $surface; border: thick $primary; }
    PromptBindModal #bind-title { text-style: bold; margin: 0 0 1 0; }
    PromptBindModal Select { margin: 0 0 1 0; }
    PromptBindModal #bind-error { color: $error; margin: 0 0 1 0; }
    PromptBindModal Horizontal { align: center middle; }
    PromptBindModal Button { margin: 0 1; min-width: 10; }
    """

    _slot_select: Select[str]
    _version_select: Select[int]

    def __init__(self, prompt_name: str) -> None:
        super().__init__()
        self._prompt_name = prompt_name

    def compose(self) -> ComposeResult:
        # allow_blank=False: the slot Select holds exactly the six real slots and
        # auto-selects the first, so it can never report the NULL sentinel.
        self._slot_select = Select.from_values(
            sorted(VALID_SLOTS),
            allow_blank=False,
            prompt="Choose a slot",
            id="bind-slot",
        )
        # allow_blank=True: the version starts blank and is populated on mount.
        self._version_select = Select[int](
            [],
            allow_blank=True,
            prompt="Choose a version",
            id="bind-version",
        )
        with Vertical():
            # markup=False: the prompt name is user-authored content.
            yield Label(f"Bind prompt '{self._prompt_name}'", id="bind-title", markup=False)
            yield Label("Slot")
            yield self._slot_select
            yield Label("Version")
            yield self._version_select
            yield Label("", id="bind-error", markup=False)
            with Horizontal():
                yield Button("Bind", id="bind-confirm", variant="primary")
                yield Button("Cancel", id="bind-cancel")

    def on_mount(self) -> None:
        """Resolve the prompt before offering a bind.

        ``store.bind`` misdiagnoses a missing prompt as a missing version
        (``store.py:173``), so the prompt is resolved here first and its absence
        reported honestly.  A prompt with no versions disables Bind outright.
        """
        try:
            detail = _prompts.get_prompt_detail_via_tui(self._prompt_name)
        except Exception as exc:
            self._fail(f"Bind failed: {exc}")
            return

        if not detail["found"]:
            self._fail(f"Prompt '{self._prompt_name}' no longer exists")
            return

        versions = [int(version) for version in detail["versions"]]
        if not versions:
            self._fail("This prompt has no versions")
            return

        self._version_select.set_options([(str(version), version) for version in versions])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "bind-confirm":
            self._bind()
        elif event.button.id == "bind-cancel":
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss(None)

    def _fail(self, message: str) -> None:
        self.query_one("#bind-error", Label).update(message)
        self.query_one("#bind-confirm", Button).disabled = True

    def _bind(self) -> None:
        # Guard before any store call: an untouched modal must not bind.
        if self._slot_select.is_blank() or self._version_select.is_blank():
            self.query_one("#bind-error", Label).update("Choose a slot and a version")
            return

        slot = cast("str", self._slot_select.value)
        version = cast("int", self._version_select.value)

        try:
            bindings = _prompts.list_bindings_via_tui()
        except Exception as exc:
            self.query_one("#bind-error", Label).update(f"Bind failed: {exc}")
            return

        existing = next((b for b in bindings if str(b["slot"]) == slot), None)
        if existing is not None:
            same_binding = (
                str(existing["prompt_name"]),
                int(existing["prompt_version"]),
            ) == (self._prompt_name, version)
            if not same_binding:
                message = (
                    f"Slot '{slot}' is currently bound to "
                    f"{existing['prompt_name']}:v{existing['prompt_version']}. Replace it?"
                )

                def on_confirm(confirmed: bool | None) -> None:
                    if confirmed:
                        self.dismiss({"slot": slot, "version": version})

                self.app.push_screen(
                    ConfirmModal("Replace binding", message, danger=True), on_confirm
                )
                return

        self.dismiss({"slot": slot, "version": version})
