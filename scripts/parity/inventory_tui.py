"""Inventory the openreview Textual TUI with source citations.

Usage::

    uv run python scripts/parity/inventory_tui.py --out draft/parity/tui-inventory.json

The script first proves the TUI framework (``OpenReviewApp`` must subclass
``textual.app.App``) and then walks ``openreview_cli.tui`` for every class the
package defines that is an app or a screen. Rows carry the six keys mandated
by ``draft/parity/parity-plan.md`` (``name``, ``type``, ``flags_or_actions``,
``default_value``, ``source_file``, ``line_number``) plus the extra evidence
keys ``owner``, ``help_text`` and ``dynamic``. ``default-state`` rows are
inventory only: the parity join never consumes them.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import pkgutil
import subprocess
import sys
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from textual.binding import Binding

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = "scripts/parity/inventory_tui.py"

_TREES: dict[Path, ast.Module] = {}


def _relative(path: str | Path) -> str:
    resolved = Path(path).resolve()
    with suppress(ValueError):
        return resolved.relative_to(REPO_ROOT).as_posix()
    return resolved.as_posix()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _commit() -> str:
    with suppress(OSError, subprocess.SubprocessError):
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    return "unknown"


def _module_tree(path: Path) -> ast.Module:
    tree = _TREES.get(path)
    if tree is None:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        _TREES[path] = tree
    return tree


def _constant_text(node: ast.expr | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Constant):
        return "" if node.value is None else str(node.value)
    return ast.unparse(node)


def _first_line(text: str | None) -> str:
    if not text:
        return ""
    for line in text.strip().splitlines():
        if line.strip():
            return line.strip()
    return ""


def _display(value: object) -> str:
    """Normalize a Python literal into the row string form."""
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, str):
        return value or '""'
    return str(value)


def detect_framework() -> dict[str, str]:
    """Confirm the TUI framework and return its metadata.

    Exits non zero with a clear message when ``OpenReviewApp`` is not a
    Textual app, because every other row depends on that fact.
    """
    import textual
    from textual.app import App

    from openreview_cli.tui.app import OpenReviewApp

    if not issubclass(OpenReviewApp, App):
        print(
            "error: OpenReviewApp does not subclass textual.app.App; the TUI framework is not Textual.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return {
        "framework": "Textual",
        "framework_version": str(textual.__version__),
        "detection": "ok",
        "app": OpenReviewApp.__name__,
    }


def _iter_modules() -> list[tuple[str, Path, ast.Module, Any]]:
    """Import every module in ``openreview_cli.tui`` and return their trees."""
    import openreview_cli.tui as tui_package

    discovered: list[tuple[str, Path, ast.Module, Any]] = []
    for info in pkgutil.walk_packages(tui_package.__path__, prefix=tui_package.__name__ + "."):
        module = importlib.import_module(info.name)
        path = Path(module.__file__)
        discovered.append((info.name, path, _module_tree(path), module))
    return discovered


def _class_node(tree: ast.Module, name: str) -> ast.ClassDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def _bindings_list_node(cls_node: ast.ClassDef) -> ast.List | None:
    for stmt in cls_node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            target_name, value = stmt.target.id, stmt.value
        elif (
            isinstance(stmt, ast.Assign) and stmt.targets and isinstance(stmt.targets[0], ast.Name)
        ):
            target_name, value = stmt.targets[0].id, stmt.value
        else:
            continue
        if target_name == "BINDINGS" and isinstance(value, ast.List):
            return value
    return None


def _binding_fields(entry: object, element: ast.expr) -> tuple[str, str, str]:
    """Return ``(key, action, description)`` for one binding entry."""
    if isinstance(entry, Binding):
        return str(entry.key), str(entry.action), str(entry.description or "")
    if isinstance(entry, (tuple, list)):
        parts = [str(part) for part in entry]
        while len(parts) < 3:
            parts.append("")
        return parts[0], parts[1], parts[2]
    if isinstance(element, ast.Tuple):
        parts = [_constant_text(item) for item in element.elts]
        while len(parts) < 3:
            parts.append("")
        return parts[0], parts[1], parts[2]
    return "", "", ""


def _action_name(action: str) -> str:
    return action.split("(", maxsplit=1)[0].strip().split(".")[-1]


def _binding_rows(
    cls: Any,
    cls_node: ast.ClassDef,
    source_file: str,
) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """Return binding rows and the ``(action, key)`` pairs they carry."""
    list_node = _bindings_list_node(cls_node)
    if list_node is None:
        return [], []
    runtime = list(getattr(cls, "BINDINGS", []) or [])
    rows: list[dict[str, Any]] = []
    pairs: list[tuple[str, str]] = []
    for index, element in enumerate(list_node.elts):
        entry = runtime[index] if index < len(runtime) else element
        key, action, description = _binding_fields(entry, element)
        rows.append(
            {
                "name": key,
                "type": "binding",
                "flags_or_actions": [key, action, description],
                "default_value": "",
                "source_file": source_file,
                "line_number": element.lineno,
                "owner": cls.__name__,
                "help_text": description,
                "dynamic": False,
            }
        )
        pairs.append((action, key))
    return rows, pairs


def _action_rows(
    cls: Any,
    cls_node: ast.ClassDef,
    source_file: str,
    binding_pairs: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stmt in cls_node.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not stmt.name.startswith("action_"):
            continue
        bare = stmt.name[len("action_") :]
        keys = [key for action, key in binding_pairs if _action_name(action) == bare]
        rows.append(
            {
                "name": stmt.name,
                "type": "action",
                "flags_or_actions": keys,
                "default_value": "",
                "source_file": source_file,
                "line_number": stmt.lineno,
                "owner": cls.__name__,
                "help_text": _first_line(ast.get_docstring(stmt)),
                "dynamic": False,
            }
        )
    return rows


def _init_self_assignments(cls_node: ast.ClassDef) -> list[tuple[str, ast.Constant, int]]:
    found: list[tuple[str, ast.Constant, int]] = []
    for stmt in cls_node.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) or stmt.name != "__init__":
            continue
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and isinstance(node.value, ast.Constant)
            ):
                found.append((target.attr, node.value, target.lineno))
    return found


def _widget_literal_calls(cls_node: ast.ClassDef) -> list[tuple[str, int, str]]:
    found: list[tuple[str, int, str]] = []
    for node in ast.walk(cls_node):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "value" or not isinstance(keyword.value, ast.Constant):
                continue
            func = node.func
            widget = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "widget")
            found.append((str(widget), keyword.value.lineno, ast.unparse(keyword.value)))
            break
    return found


def _default_state_rows(cls: Any, cls_node: ast.ClassDef, source_file: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for attr, value, lineno in _init_self_assignments(cls_node):
        rows.append(
            {
                "name": attr,
                "type": "default-state",
                "flags_or_actions": [attr],
                "default_value": _display(value.value),
                "source_file": source_file,
                "line_number": lineno,
                "owner": cls.__name__,
                "help_text": "__init__ assignment",
                "dynamic": False,
            }
        )
    for widget, lineno, expression in _widget_literal_calls(cls_node):
        rows.append(
            {
                "name": f"{widget}.value",
                "type": "default-state",
                "flags_or_actions": ["value"],
                "default_value": expression,
                "source_file": source_file,
                "line_number": lineno,
                "owner": cls.__name__,
                "help_text": f"{widget}(value=...)",
                "dynamic": False,
            }
        )
    return rows


def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["type"]] = counts.get(row["type"], 0) + 1
    return counts


def collect() -> dict[str, Any]:
    """Walk the Textual package and return ``{"meta": ..., "rows": ...}``."""
    from textual.app import App
    from textual.screen import Screen

    meta = detect_framework()
    rows: list[dict[str, Any]] = []
    module_count = 0

    for module_name, path, tree, module in _iter_modules():
        module_count += 1
        source_file = _relative(path)
        for name, obj in vars(module).items():
            if not isinstance(obj, type) or obj.__module__ != module_name:
                continue
            if issubclass(obj, App):
                kind = "app"
            elif issubclass(obj, Screen):
                kind = "screen"
            else:
                continue
            cls_node = _class_node(tree, name)
            if cls_node is None:
                continue
            rows.append(
                {
                    "name": name,
                    "type": kind,
                    "flags_or_actions": [],
                    "default_value": "",
                    "source_file": source_file,
                    "line_number": cls_node.lineno,
                    "owner": module_name,
                    "help_text": _first_line(ast.get_docstring(cls_node)),
                    "dynamic": False,
                }
            )
            binding_rows, binding_pairs = _binding_rows(obj, cls_node, source_file)
            rows.extend(binding_rows)
            rows.extend(_action_rows(obj, cls_node, source_file, binding_pairs))
            rows.extend(_default_state_rows(obj, cls_node, source_file))

    meta.update(
        {
            "generator": GENERATOR,
            "generated_at": _now(),
            "commit": _commit(),
            "module_count": module_count,
            "row_count": len(rows),
            "counts": _counts(rows),
        }
    )
    return {"meta": meta, "rows": rows}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inventory the openreview Textual TUI.")
    parser.add_argument(
        "--out", type=Path, default=None, help="Write the JSON inventory to this path."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Print the inventory as JSON and write it to ``--out`` when given."""
    args = _build_parser().parse_args(argv)
    data = collect()
    text = json.dumps(data, indent=2)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
