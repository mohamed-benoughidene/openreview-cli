"""Prompts domain wrapper — every TUI-facing prompt operation.

Resolves the data directory at call time (never at import) so per-test
``XDG_*`` overrides in the ``isolated_xdg`` fixture are honored.

This is the only layer that touches ``PromptStore``.  The boundary is
**total**: every wrapper catches ``Exception`` and re-raises ``ValueError``
naming the operation — the read path (``list_prompts_via_tui``,
``get_prompt_history_via_tui``) as well as the mutating one — so no store,
filesystem or YAML error can reach a Textual handler.
``get_prompt_detail_via_tui`` and ``get_prompt_history_via_tui`` return
``found=False`` for a *missing* name instead of raising;
``get_prompt_version_diff`` propagates the store's ``ValueError`` for a
missing version (its screen handler catches it); and
``import_prompts_via_tui`` reports per-item failures in its result rather
than raising.  ``export_prompts_via_tui`` writes one prompt or the whole
library (its ``name`` is optional, mirroring the CLI) and returns how many
prompts were written; ``count_prompts_via_tui`` reports the uncapped total.
"""

from __future__ import annotations

from difflib import unified_diff
from pathlib import Path
from typing import Any

import yaml

from openreview_cli.config.paths import get_data_dir
from openreview_cli.prompts.io import parse_prompts_yaml
from openreview_cli.prompts.store import PromptStore


def _store() -> PromptStore:
    """Build a ``PromptStore`` against the *current* data directory.

    ``get_data_dir()`` is called here, at call time, rather than cached at
    module import, because ``isolated_xdg`` patches the environment per test.
    """
    store = PromptStore(get_data_dir() / "openreview.db")
    store.init()
    return store


def _normalize_created_at(value: Any) -> str:
    """Coerce a SQL NULL coerced to the literal string ``"None"`` to ``""``."""
    text = str(value)
    return "" if text == "None" else text


def list_prompts_via_tui() -> list[dict[str, Any]]:
    """List prompts as dicts shaped ``{name, latest_version, created_at}``.

    Requests an explicit ``per_page=100``, so it returns up to 100 prompts.
    Prompts beyond the first 100 are not included (the store's default 25-item
    cap is not the limiting factor here, but a cap of 100 still applies).
    Any failure is translated to ``ValueError`` naming the operation.
    """
    try:
        prompts = _store().list(per_page=100)
    except Exception as exc:
        raise ValueError(f"list prompts failed: {exc}") from exc
    return [
        {
            "name": p.name,
            "latest_version": p.latest_version,
            "created_at": p.created_at,
        }
        for p in prompts
    ]


def get_prompt_history_via_tui(name: str) -> dict[str, Any]:
    """Return ``{rows, current_version, found}`` for prompt ``name``.

    Each row is ``{version, created_at}``, sorted by version.  Versions are
    enumerated through ``PromptStore.export`` (ordered by version) rather than
    ``range(1, latest + 1)``, so imported prompts with gaps or non-1-based
    numbering are handled without raising.  A missing prompt yields
    ``{"rows": [], "current_version": 0, "found": False}``; any other failure
    is translated to ``ValueError`` naming the operation.
    """
    try:
        data = _store().export(name)
    except ValueError:
        return {"rows": [], "current_version": 0, "found": False}
    except Exception as exc:
        raise ValueError(f"get prompt history for '{name}' failed: {exc}") from exc

    # ``export(name)`` returns a single dict when a name is supplied.
    assert isinstance(data, dict)
    rows: list[dict[str, Any]] = [
        {
            "version": int(version["version"]),
            "created_at": _normalize_created_at(version.get("created_at")),
        }
        for version in data["versions"]
    ]
    rows.sort(key=lambda row: row["version"])
    current_version = max((row["version"] for row in rows), default=0)
    return {"rows": rows, "current_version": current_version, "found": True}


def get_prompt_version_diff(name: str, v1: int, v2: int) -> str:
    """Return a unified diff between versions ``v1`` and ``v2`` of ``name``.

    Mirrors the CLI ``prompt diff`` command.  Raises ``ValueError`` (propagated
    from the store) when either version is missing.
    """
    store = _store()
    pv_from = store.get(name, v1)
    pv_to = store.get(name, v2)
    diff = unified_diff(
        pv_from.content.splitlines(keepends=True),
        pv_to.content.splitlines(keepends=True),
        fromfile=f"v{v1}",
        tofile=f"v{v2}",
    )
    return "".join(diff)


def get_prompt_detail_via_tui(name: str) -> dict[str, Any]:
    """Return ``{found, name, latest_version, versions, content, tags, description}``.

    Built from a **single** ``PromptStore.export(name)`` call, which already
    carries each version's content and ``metadata``; ``versions`` therefore
    reflects the stored numbering and imported gaps (e.g. ``[1, 3]``) without
    raising.  A missing prompt returns ``found=False`` with empty fields; any
    other failure is translated to ``ValueError``.
    """
    try:
        data = _store().export(name)
    except ValueError:
        return {
            "found": False,
            "name": name,
            "latest_version": 0,
            "versions": [],
            "content": "",
            "tags": None,
            "description": None,
        }
    except Exception as exc:
        raise ValueError(f"get prompt detail for '{name}' failed: {exc}") from exc

    # ``export(name)`` returns a single dict when a name is supplied.
    assert isinstance(data, dict)
    versions = sorted(int(version["version"]) for version in data["versions"])
    latest = max(data["versions"], key=lambda version: int(version["version"]))
    metadata = latest.get("metadata") or {}
    tags = metadata.get("tags")
    description = metadata.get("description")
    detail: dict[str, Any] = {
        "found": True,
        "name": str(data["name"]),
        "latest_version": versions[-1],
        "versions": versions,
        "content": str(latest["content"]),
        "tags": tags,
        "description": description,
    }
    return detail


def create_prompt_via_tui(
    name: str,
    content: str,
    tags: list[str] | None = None,
    description: str | None = None,
) -> int:
    """Create prompt ``name`` (version 1) and return the new version number.

    Thin delegate to ``PromptStore.create``, which owns the 16384-**byte**
    limit.  Any failure is translated to ``ValueError`` naming the operation.
    """
    try:
        pv = _store().create(name, content, tags=tags, description=description)
    except Exception as exc:
        raise ValueError(f"create prompt '{name}' failed: {exc}") from exc
    return pv.version


def update_prompt_via_tui(
    name: str,
    content: str,
    tags: list[str] | None = None,
    description: str | None = None,
) -> int:
    """Append a new version of ``name`` and return its version number.

    Thin delegate to ``PromptStore.update``, which owns the 16384-**character**
    SQL limit.  Any failure is translated to ``ValueError`` naming the
    operation.
    """
    try:
        pv = _store().update(name, content, tags=tags, description=description)
    except Exception as exc:
        raise ValueError(f"update prompt '{name}' failed: {exc}") from exc
    return pv.version


def delete_prompt_via_tui(name: str) -> None:
    """Delete ``name`` and all of its versions (and its bindings).

    Thin delegate to ``PromptStore.delete``.  Any failure is translated to
    ``ValueError`` naming the operation.
    """
    try:
        _store().delete(name)
    except Exception as exc:
        raise ValueError(f"delete prompt '{name}' failed: {exc}") from exc


def list_bindings_via_tui() -> list[dict[str, Any]]:
    """List every binding as ``{slot, prompt_name, prompt_version, created_at}``.

    Any failure is translated to ``ValueError`` naming the operation.
    """
    try:
        bindings = _store().bindings()
    except Exception as exc:
        raise ValueError(f"list bindings failed: {exc}") from exc
    return [
        {
            "slot": binding.slot,
            "prompt_name": binding.prompt_name,
            "prompt_version": binding.prompt_version,
            "created_at": binding.created_at,
        }
        for binding in bindings
    ]


def bind_prompt_via_tui(slot: str, name: str, version: int) -> None:
    """Bind ``slot`` to ``name`` at ``version``.

    Thin delegate to ``PromptStore.bind``, which validates the slot and the
    exact (name, version) and silently overwrites an existing binding.  Any
    failure is translated to ``ValueError`` naming the operation.
    """
    try:
        _store().bind(slot, name, version)
    except Exception as exc:
        raise ValueError(f"bind slot '{slot}' to prompt '{name}' v{version} failed: {exc}") from exc


def unbind_prompt_via_tui(slot: str) -> None:
    """Unbind ``slot``; raises ``ValueError`` when no binding exists.

    Thin delegate to ``PromptStore.unbind``.  Any failure is translated to
    ``ValueError`` naming the operation.
    """
    try:
        _store().unbind(slot)
    except Exception as exc:
        raise ValueError(f"unbind slot '{slot}' failed: {exc}") from exc


def validate_prompt_test_via_tui(name: str, versions: list[int]) -> None:
    """Validate that ``name`` exists and every version in ``versions`` exists.

    Returns ``None`` when valid; raises ``ValueError`` naming the operation for
    an unknown prompt or any unknown version.  Never dispatches a model call.
    """
    try:
        store = _store()
        store.get_latest(name)
        for version in versions:
            store.get(name, version)
    except Exception as exc:
        raise ValueError(f"validate prompt test for '{name}' failed: {exc}") from exc


def export_prompts_via_tui(dest: Path, name: str | None = None) -> int:
    """Write prompt export data as YAML to ``dest``; return the prompts written.

    Mirrors the CLI's ``prompt export``, whose NAME argument is optional: with
    ``name`` given it writes that one prompt and returns ``1``; with
    ``name=None`` it writes **every** prompt in the library and returns the
    number written.  ``PromptStore.export(None)`` walks every distinct prompt
    name with no cap, so neither the file nor the count is truncated - unlike
    ``list_prompts_via_tui``, which asks for ``per_page=100``.  The caller owns
    overwrite confirmation and parent-directory creation.  Any failure (store
    or filesystem) is translated to ``ValueError`` naming the operation.
    """
    operation = "export all prompts" if name is None else f"export prompt '{name}'"
    try:
        data = _store().export(name)
        dest.write_text(yaml.dump(data, default_flow_style=False))
    except Exception as exc:
        raise ValueError(f"{operation} failed: {exc}") from exc
    return len(data) if name is None else 1


def count_prompts_via_tui() -> int:
    """Return the true number of prompts in the library, uncapped.

    ``list_prompts_via_tui`` requests ``per_page=100``, so its length stops at
    100 once the library is larger.  ``PromptStore.export(None)`` enumerates
    every distinct prompt name with no cap, so its length is the real total.
    Any failure is translated to ``ValueError`` naming the operation.
    """
    try:
        data = _store().export(None)
    except Exception as exc:
        raise ValueError(f"count prompts failed: {exc}") from exc
    assert isinstance(data, list)
    return len(data)


def export_prompt_via_tui(dest: Path, name: str) -> None:
    """Write ``name``'s export data as YAML to ``dest``.

    Kept for the per-prompt call sites: a thin delegate to
    :func:`export_prompts_via_tui` with a single name, discarding the count.
    The caller owns overwrite confirmation and parent-directory creation.  Any
    failure (store or filesystem) is translated to ``ValueError`` naming the
    operation.
    """
    export_prompts_via_tui(dest, name)


def import_prompts_via_tui(path: Path) -> dict[str, Any]:
    """Import prompts from a YAML file at ``path``.

    Returns ``{"imported": list[str], "failed": dict[str, str]}``.  The file is
    read and then validated by ``parse_prompts_yaml`` - the same structural
    validator the CLI's ``prompt import`` runs - so the TUI preview, the TUI
    import and the CLI cannot disagree about what a document means.

    An unreadable file, a parse/structural failure, or a store-init failure
    raises ``ValueError`` naming the operation; a per-item store failure (for
    example a duplicate name) is reported in ``failed`` under the item's name
    and never raised, because import commits per item and is not atomic.
    """
    try:
        data = parse_prompts_yaml(Path(path).read_text())
    except Exception as exc:
        raise ValueError(f"import prompts from '{path}' failed: {exc}") from exc

    try:
        store = _store()
    except Exception as exc:
        raise ValueError(f"import prompts from '{path}' failed: {exc}") from exc

    imported: list[str] = []
    failed: dict[str, str] = {}
    for index, item in enumerate(data):
        name = item.get("name")
        key = str(name) if name is not None else f"item {index}"
        try:
            store.import_prompt(item)
        except Exception as exc:
            failed[key] = str(exc)
        else:
            imported.append(key)
    return {"imported": imported, "failed": failed}
