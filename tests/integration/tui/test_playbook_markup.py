"""Markup-safety tests for playbook detail/preview widgets (P0/T2)."""

from __future__ import annotations

from pathlib import Path

import pytest

_BRACKETED_YAML = """id: bracket-pb
mode: precheck
metadata:
  version: "1.0"
  description: Brackets [test]
  author: Test
categories:
  - id: confidentiality
    name: "Confidentiality [Scope]"
    description: Handles [bracketed] terms
    preferred:
      description: Broad
      exemplars: ["mutual [NDA]"]
    acceptable:
      description: Standard
      exemplars: ["standard"]
    walkaway:
      description: None
      exemplars: ["none"]
    default_position: preferred
"""


@pytest.mark.asyncio
async def test_playbook_category_item_preserves_brackets() -> None:
    from textual.widgets import Label

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.playbook_detail import _CategoryItem

    item = _CategoryItem(
        cat_id="confidentiality",
        name="Confidentiality",
        default_position="preferred",
        description="Handles [Party A] terms",
        exemplars=["mutual NDA [standard]"],
    )

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.screen.mount(item)
        await pilot.pause()
        text = str(item.query_one(Label).render())
        assert "[preferred]" in text, text
        assert "[Party A]" in text, text
        assert "[standard]" in text, text


@pytest.mark.asyncio
async def test_import_preview_preserves_brackets(tmp_path: Path) -> None:
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.tabs.playbooks import _ImportModal

    pb_path = tmp_path / "bracket-pb.yaml"
    pb_path.write_text(_BRACKETED_YAML, encoding="utf-8")

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        modal = _ImportModal()
        app.push_screen(modal)
        await pilot.pause()

        modal._show_preview(pb_path)
        await pilot.pause()

        text = str(modal.query_one("#preview-content").render())
        assert "[Scope]" in text, text
        assert "[preferred]" in text, text
