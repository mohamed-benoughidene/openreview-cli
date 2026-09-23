"""Inventory the openreview Typer command tree with source citations.

Usage::

    uv run python scripts/parity/inventory_cli.py --out draft/parity/cli-inventory.json

Every row carries the six keys mandated by ``draft/parity/parity-plan.md``:
``name``, ``type``, ``flags_or_actions``, ``default_value``, ``source_file``
and ``line_number``. Extra evidence keys: ``owner`` (the command path the row
belongs to), ``help_text``, ``dynamic`` and, for parameter rows,
``default_line`` (the line of the first positional argument of the
``typer.Option`` / ``typer.Argument`` call, which is where the declared
default literal lives). The row ``line_number`` for a parameter points at the
flag token of the declaration, so the cited line always supports the row name.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import inspect
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = "scripts/parity/inventory_cli.py"
_LIBRARY_MARKERS = ("/typer/", "/click/", "site-packages")

_TREES: dict[Path, ast.Module] = {}


def _relative(path: str | Path) -> str:
    """Return *path* relative to the repository root, with forward slashes."""
    resolved = Path(path).resolve()
    with contextlib.suppress(ValueError):
        return resolved.relative_to(REPO_ROOT).as_posix()
    return resolved.as_posix()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _commit() -> str:
    with contextlib.suppress(OSError, subprocess.SubprocessError):
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
    """Parse and cache the module at *path*."""
    tree = _TREES.get(path)
    if tree is None:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        _TREES[path] = tree
    return tree


def _display(value: object) -> str:
    """Normalize a Python default value into the row string form."""
    if value is None:
        return "None"
    if value is Ellipsis:
        return "REQUIRED"
    if isinstance(value, str):
        return value or '""'
    if isinstance(value, (list, tuple, dict, set)):
        return json.dumps(value, default=str, sort_keys=True)
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


@dataclass(frozen=True)
class _ParamLine:
    """Source lines for one Typer parameter declaration."""

    line: int
    default_line: int


def _function_for_line(
    tree: ast.Module, lineno: int
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Find the function whose ``def`` or first decorator sits on *lineno*.

    ``inspect`` reports the line of the first decorator for a decorated
    function, so both anchors are checked.
    """
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.lineno == lineno:
            return node
        if node.decorator_list and node.decorator_list[0].lineno == lineno:
            return node
    return None


def _is_typer_call(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id == "typer" and func.attr in {"Option", "Argument"}
    return isinstance(func, ast.Name) and func.id in {"Option", "Argument"}


def _default_node(args: ast.arguments, name: str) -> ast.expr | None:
    """Return the default expression bound to parameter *name*, if any."""
    positional = list(args.posonlyargs) + list(args.args)
    for arg, default in zip(positional[-len(args.defaults) :], args.defaults, strict=False):
        if arg.arg == name:
            return default
    for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=False):
        if arg.arg == name:
            return default
    return None


def _param_line(tree: ast.Module, func_lineno: int, name: str) -> _ParamLine | None:
    """Resolve the cited source lines for parameter *name*."""
    func = _function_for_line(tree, func_lineno)
    if func is None:
        return None
    all_args = [*func.args.posonlyargs, *func.args.args, *func.args.kwonlyargs]
    arg = next((item for item in all_args if item.arg == name), None)
    if arg is None:
        return None

    default = _default_node(func.args, name)
    if isinstance(default, ast.Call) and _is_typer_call(default):
        flag = next(
            (
                item
                for item in default.args[1:]
                if isinstance(item, ast.Constant)
                and isinstance(item.value, str)
                and item.value.startswith("-")
            ),
            None,
        )
        first_positional = default.args[0] if default.args else None
        default_line = (first_positional or arg).lineno
        return _ParamLine((flag or first_positional or arg).lineno, default_line)
    default_line = default.lineno if default is not None else arg.lineno
    return _ParamLine(default_line, default_line)


def _param_kind(param: Any) -> str:
    """Classify a Typer parameter as an option or an argument.

    Typer vendors Click as ``typer._click``, so ``isinstance`` checks against
    the ``click`` package never match. The class name carries the answer.
    """
    names = {klass.__name__ for klass in type(param).__mro__}
    return "option" if any("Option" in name for name in names) else "argument"


def _callback_function(node: Any) -> Any:
    """Return the real Python function behind a Click command callback."""
    callback = node.callback
    if callback is None:
        return None
    return getattr(callback, "__wrapped__", None) or callback


def _is_library_path(path: str) -> bool:
    return any(marker in path for marker in _LIBRARY_MARKERS)


def _typer_group_locations() -> dict[str, tuple[str, int]]:
    """Map ``typer.Typer()`` variable names to their source location."""
    locations: dict[str, tuple[str, int]] = {}
    cli_modules = [
        *(REPO_ROOT / "src" / "openreview_cli").glob("**/cli.py"),
        REPO_ROOT / "src" / "openreview_cli" / "app.py",
    ]
    for path in sorted(cli_modules):
        for node in ast.walk(_module_tree(path)):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                continue
            func = node.value.func
            is_typer = (isinstance(func, ast.Attribute) and func.attr == "Typer") or (
                isinstance(func, ast.Name) and func.id == "Typer"
            )
            if not is_typer:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    locations.setdefault(target.id, (_relative(path), node.value.lineno))
    return locations


def _unwrap_location(node: Any, group_locations: dict[str, tuple[str, int]]) -> tuple[str, int]:
    """Locate the source of a command or group node."""
    func = _callback_function(node)
    if func is not None:
        with contextlib.suppress(TypeError, OSError):
            path = inspect.getsourcefile(func)
            if path and not _is_library_path(path):
                return _relative(path), int(func.__code__.co_firstlineno)
        return "", 0
    for candidate in (f"{node.name}_app", str(node.name).replace("-", "_")):
        location = group_locations.get(candidate)
        if location is not None:
            return location
    print(f"warning: cannot locate source for command {node.name!r}", file=sys.stderr)
    return "", 0


def _normalize_default(param: Any) -> str:
    if _param_kind(param) == "argument" and param.required:
        return "REQUIRED"
    return _display(param.default)


def _command_row(
    node: Any,
    path: str,
    owner: str,
    location: tuple[str, int],
    dynamic: bool,
) -> dict[str, Any]:
    source_file, line_number = location
    doc = (getattr(_callback_function(node), "__doc__", None) or "").strip()
    help_text = (node.help or "").strip()
    if not help_text and doc:
        help_text = doc.splitlines()[0].strip()
    return {
        "name": path,
        "type": "group" if getattr(node, "commands", None) else "command",
        "flags_or_actions": [],
        "default_value": "",
        "source_file": source_file,
        "line_number": line_number,
        "owner": owner,
        "help_text": help_text,
        "dynamic": dynamic,
    }


def _param_rows(
    node: Any,
    path: str,
    location: tuple[str, int],
    dynamic: bool,
) -> list[dict[str, Any]]:
    source_file, func_lineno = location
    tree: ast.Module | None = None
    module_path = REPO_ROOT / source_file if source_file else None
    if module_path is not None and func_lineno and module_path.is_file():
        tree = _module_tree(module_path)

    rows: list[dict[str, Any]] = []
    for param in node.params:
        line_info: _ParamLine | None = None
        if tree is not None:
            line_info = _param_line(tree, func_lineno, param.name)
        opts = list(getattr(param, "opts", []) or []) + list(
            getattr(param, "secondary_opts", []) or []
        )
        kind = _param_kind(param)
        name = opts[0] if (kind == "option" and opts) else str(param.name)
        row: dict[str, Any] = {
            "name": name,
            "type": kind,
            "flags_or_actions": opts,
            "default_value": _normalize_default(param),
            "source_file": source_file,
            "line_number": line_info.line if line_info else 0,
            "owner": path,
            "help_text": (param.help or "").strip(),
            "dynamic": dynamic,
        }
        if line_info is not None:
            row["default_line"] = line_info.default_line
        rows.append(row)
    return rows


def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["type"]] = counts.get(row["type"], 0) + 1
    return counts


def collect() -> dict[str, Any]:
    """Walk the Typer tree and return ``{"meta": ..., "rows": ...}``."""
    import typer
    import typer.main

    from openreview_cli.app import app

    root = typer.main.get_command(app)
    group_locations = _typer_group_locations()

    nodes: list[tuple[Any, str, str]] = []

    def _gather(node: Any, parent_names: tuple[str, ...]) -> None:
        name = " ".join((*parent_names, str(node.name)))
        nodes.append((node, name, parent_names[-1] if parent_names else ""))
        for child in (getattr(node, "commands", None) or {}).values():
            _gather(child, (*parent_names, str(node.name)))

    # The root app contributes its name only: every other node is addressed by
    # the path the user types, for example ``precheck review``.
    nodes.append((root, str(root.name), ""))
    for child in (getattr(root, "commands", None) or {}).values():
        _gather(child, ())

    shared: dict[tuple[str, int, str], int] = {}
    for node, _path, _owner in nodes:
        func = _callback_function(node)
        if func is None:
            continue
        key = (
            str(inspect.getsourcefile(func) or ""),
            int(func.__code__.co_firstlineno),
            str(func.__name__),
        )
        shared[key] = shared.get(key, 0) + 1

    rows: list[dict[str, Any]] = []
    for node, path, owner in nodes:
        location = _unwrap_location(node, group_locations)
        func = _callback_function(node)
        dynamic = False
        if func is not None:
            key = (
                str(inspect.getsourcefile(func) or ""),
                int(func.__code__.co_firstlineno),
                str(func.__name__),
            )
            dynamic = shared[key] > 1
        rows.append(_command_row(node, path, owner, location, dynamic))
        rows.extend(_param_rows(node, path, location, dynamic))

    meta = {
        "generator": GENERATOR,
        "generated_at": _now(),
        "commit": _commit(),
        "framework": "Typer",
        "framework_version": getattr(typer, "__version__", "unknown"),
        "root_command": str(root.name),
        "row_count": len(rows),
        "counts": _counts(rows),
    }
    return {"meta": meta, "rows": rows}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inventory the openreview Typer command tree.")
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
