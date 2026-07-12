"""Playbook detail screen — categories, version history, diff (T037/T038)."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Label, ListItem, ListView, Static

from openreview_cli.review.models import Playbook
from openreview_cli.review.playbook import VersionDiff


class _CategoryItem(ListItem):
    """ListItem carrying category id and rendering inline summary."""

    def __init__(
        self,
        cat_id: str,
        name: str,
        default_position: str,
        description: str,
        exemplars: list[str],
    ) -> None:
        self.cat_id = cat_id
        ex_str = "; ".join(exemplars[:3])
        super().__init__(
            Label(f"{name} [{default_position}]\n  {description}\n  Exemplars: {ex_str}")
        )


class PlaybookDetailScreen(Screen[None]):
    """Playbook detail view: categories, positions, exemplars."""

    DEFAULT_CSS = """
    PlaybookDetailScreen { padding: 1; }
    PlaybookDetailScreen #detail-header { text-style: bold; padding: 0 0 1 0; }
    PlaybookDetailScreen #detail-meta { padding: 0 0 1 0; }
    PlaybookDetailScreen #detail-categories-label { text-style: bold; padding: 1 0 0 0; }
    PlaybookDetailScreen #detail-categories { height: 1fr; min-height: 3; }
    PlaybookDetailScreen #detail-toolbar { margin: 1 0 0 0; }
    PlaybookDetailScreen #detail-toolbar Button { margin: 0 1 0 0; }
    """

    def __init__(self, playbook: Playbook, current_version: int = 0) -> None:
        super().__init__()
        self._playbook_id = playbook.id
        self._mode = playbook.mode
        self._description = playbook.metadata.description
        self._version = playbook.metadata.version
        self._categories = playbook.categories
        self._current_version = current_version

    def compose(self) -> ComposeResult:
        yield Static(f"{self._playbook_id} — {self._mode} (v{self._version})", id="detail-header")
        yield Static(
            f"Description: {self._description}\nCategories: {len(self._categories)}",
            id="detail-meta",
        )
        yield Static("Categories (with default positions):", id="detail-categories-label")
        yield ListView(id="detail-categories")
        yield Horizontal(
            Button("View versions", id="btn-versions", variant="default"),
            Button("Set as current", id="btn-set-current", variant="primary"),
            Button("View diff", id="btn-diff", variant="default"),
            Button("Close", id="btn-close", variant="default"),
            id="detail-toolbar",
        )

    def on_mount(self) -> None:
        """Populate categories list from Playbook.categories."""
        lv = self.query_one("#detail-categories", ListView)
        for cat in self._categories:
            lv.append(
                _CategoryItem(
                    cat_id=cat.id,
                    name=cat.name,
                    default_position=cat.default_position.value,
                    description=cat.description,
                    exemplars=cat.preferred.exemplars
                    + cat.acceptable.exemplars
                    + cat.walkaway.exemplars,
                )
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-versions":
            self._show_versions()
        elif event.button.id == "btn-set-current":
            self._confirm_set_current()
        elif event.button.id == "btn-diff":
            self._show_diff()
        elif event.button.id == "btn-close":
            self.dismiss()

    def _show_versions(self) -> None:
        """Push version history screen."""
        from openreview_cli.tui.domain.playbooks import get_playbook_history_via_tui

        data = get_playbook_history_via_tui(self._playbook_id)
        self.app.push_screen(
            VersionHistoryScreen(
                playbook_id=self._playbook_id,
                rows=data["rows"],
                current_version=data["current_version"],
            )
        )

    def _confirm_set_current(self) -> None:
        """Open ConfirmModal for setting current version."""
        from openreview_cli.tui.screens.confirm import ConfirmModal

        def on_result(result: bool | None) -> None:
            if result:
                from openreview_cli.tui.domain.playbooks import set_current_version_via_tui

                was_changed, msg = set_current_version_via_tui(
                    self._playbook_id, self._current_version
                )
                self._show_notification(msg)

        self.app.push_screen(
            ConfirmModal(
                "Set as current",
                f"Set version {self._current_version} as the current version for "
                f"'{self._playbook_id}'?",
            ),
            on_result,
        )

    def _show_diff(self) -> None:
        """Push version picker then diff screen."""
        from openreview_cli.tui.domain.playbooks import get_playbook_history_via_tui

        data = get_playbook_history_via_tui(self._playbook_id)
        rows = data["rows"]
        if len(rows) < 2:
            self._show_notification("Need at least 2 versions to diff.")
            return
        v2 = max(r["version"] for r in rows)
        v1 = max(r["version"] for r in rows if r["version"] != v2)
        self._show_diff_for_versions(v1, v2)

    def _show_diff_for_versions(self, v1: int, v2: int) -> None:
        from openreview_cli.tui.domain.playbooks import get_playbook_version_diff

        try:
            diff = get_playbook_version_diff(self._playbook_id, v1, v2)
        except Exception as exc:
            self._show_notification(f"Diff error: {exc}")
            return
        self.app.push_screen(VersionDiffScreen(self._playbook_id, diff))

    def _show_notification(self, msg: str) -> None:
        self.notify(msg, timeout=3)


class VersionHistoryScreen(ModalScreen[None]):
    """Version history list for a playbook."""

    DEFAULT_CSS = """
    VersionHistoryScreen { align: center middle; }
    VersionHistoryScreen > Vertical { width: 60; height: 80%; padding: 1 2; background: $surface; border: thick $primary; }
    VersionHistoryScreen #vhistory-title { text-style: bold; margin: 0 0 1 0; }
    VersionHistoryScreen #vhistory-list { height: 1fr; min-height: 3; }
    VersionHistoryScreen #vhistory-actions { margin: 1 0 0 0; }
    """

    def __init__(
        self,
        playbook_id: str,
        rows: list[dict[str, Any]],
        current_version: int,
    ) -> None:
        super().__init__()
        self._playbook_id = playbook_id
        self._rows = rows
        self._current_version = current_version

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Version history: {self._playbook_id}", id="vhistory-title")
            yield ListView(id="vhistory-list")
            yield Horizontal(
                Button("View diff", id="btn-diff-v", variant="default"),
                Button("Close", id="btn-close-v", variant="default"),
                id="vhistory-actions",
            )

    def on_mount(self) -> None:
        """Populate version list — use plain ListItem, not _VersionItem."""
        lv = self.query_one("#vhistory-list", ListView)
        max_ver = max(r["version"] for r in self._rows) if self._rows else 0
        for r in self._rows:
            ver = r["version"]
            created = str(r.get("created_at", ""))
            markers = ""
            if ver == self._current_version:
                markers += " ← current"
            if ver == max_ver and ver != self._current_version:
                markers += " (latest)"
            lv.append(ListItem(Label(f"v{ver} — {created}{markers}")))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-diff-v":
            lv = self.query_one("#vhistory-list", ListView)
            if lv.index is not None and self._rows:
                selected_ver = self._rows[lv.index]["version"]
                other_ver = self._current_version
                if selected_ver == other_ver:
                    others = [r["version"] for r in self._rows if r["version"] != selected_ver]
                    if others:
                        other_ver = max(others)
                    else:
                        self.dismiss()
                        return
                v1, v2 = sorted([selected_ver, other_ver])
                self._open_diff(v1, v2)
            else:
                self.notify("Select a version first.", timeout=2)
        elif event.button.id == "btn-close-v":
            self.dismiss()

    def _open_diff(self, v1: int, v2: int) -> None:
        from openreview_cli.tui.domain.playbooks import get_playbook_version_diff

        try:
            diff = get_playbook_version_diff(self._playbook_id, v1, v2)
        except Exception as exc:
            self.notify(f"Diff error: {exc}", timeout=3)
            return
        self.app.push_screen(VersionDiffScreen(self._playbook_id, diff))


class VersionDiffScreen(ModalScreen[None]):
    """Full-screen version diff view (FR-029)."""

    DEFAULT_CSS = """
    VersionDiffScreen { align: center middle; }
    VersionDiffScreen > Vertical { width: 80; height: 90%; padding: 1 2; background: $surface; border: thick $primary; }
    VersionDiffScreen #diff-title { text-style: bold; margin: 0 0 1 0; }
    VersionDiffScreen #diff-content { height: 1fr; }
    VersionDiffScreen #diff-close { margin: 1 0 0 0; }
    """

    def __init__(self, playbook_id: str, diff: VersionDiff) -> None:
        super().__init__()
        self._playbook_id = playbook_id
        self._diff = diff

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(
                f"Version diff: {self._playbook_id} (v{self._diff.v1} → v{self._diff.v2})",
                id="diff-title",
            )
            with ScrollableContainer(id="diff-content"):
                yield Static(self._render_diff())
            yield Button("Close", id="diff-close", variant="default")

    def _render_diff(self) -> str:
        d = self._diff
        parts: list[str] = []
        if d.status == "unchanged":
            parts.append("No changes between these versions.")
        if d.added_categories:
            parts.append(f"[green]Added categories ({len(d.added_categories)}):[/]")
            parts += [f"  + {cid}" for cid in d.added_categories]
        if d.removed_categories:
            parts.append(f"[red]Removed categories ({len(d.removed_categories)}):[/]")
            parts += [f"  - {cid}" for cid in d.removed_categories]
        if d.changed_categories:
            parts.append(f"[yellow]Changed categories ({len(d.changed_categories)}):[/]")
            for cid, changes in d.changed_categories.items():
                parts.append(f"  ~ {cid}")
                for key in ("description", "default_position"):
                    if key in changes:
                        parts.append(
                            f"      {key}: {changes[key].get('before', '')} → {changes[key].get('after', '')}"
                        )
                for ex in changes.get("exemplars_added", []):
                    parts.append(f"      + exemplar: {ex}")
                for ex in changes.get("exemplars_removed", []):
                    parts.append(f"      - exemplar: {ex}")
        return "\n".join(parts) if parts else "No differences found."

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "diff-close":
            self.dismiss()

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss()
