"""Build ``docs/cli-tui-parity-matrix.md`` from live source evidence.

Usage::

    uv run python scripts/parity/build_parity_matrix.py \
        --cli-json draft/parity/cli-inventory.json \
        --tui-json draft/parity/tui-inventory.json

The script does three things.

Part A resolves the shared call sites of ``run_review`` and
``run_comparison``. Every call site gets one row per target parameter, so an
omitted keyword argument is explicit (``value_kind`` ``absent``, effective
value ``NOT PASSED``). Keyword values are resolved with the rules from
``draft/parity/parity-plan.md``: ``literal``, ``name`` (enclosing parameter,
then enclosing function assignment, then module assignment), ``attribute``
(``self._x`` set in the class ``__init__``), ``conditional`` (``IfExp`` with a
bare ``Name`` guard, ``effective = body if guard_default else orelse``) and
``computed``. A ``name`` bound to more than one enclosing assignment with
disagreeing values is ``computed``, never a guessed value.

Part B joins CLI items with TUI items on normalized name tokens. A certain
match requires a shared significant root word in the names. Help text and label
overlaps that share a core noun are reported as needing human confirmation, not
asserted, because a prose overlap is weaker evidence than a name match.

Part C renders the markdown. Every echoed source string is sanitized to plain
ASCII, and the renderer refuses to emit a row without a source file or with a
line number below 1. Table C prints the shared name token that produced each
certain match, next to a note stating that a certain match is a name join and
not proof that the TUI implements the command.

Comparison statuses are ``MATCH``, ``MISMATCH``, ``MISMATCH-ABSENT`` (one side
present, one side absent, values differ), ``UNRESOLVED`` (a ``computed`` side)
and ``NO-COUNTERPART`` (the other lane has no call site at all). A row always
carries the six keys of the plan row schema; the extra keys (``owner``,
``help_text``, ``dynamic``, ``call_line``, ``call_expr_src``, ``callee_default``
plus the branch, guard and source keys of the comparison lane) are evidence
attached to that schema, never a replacement for it. A certain match requires a
shared significant root word in the names. Anything weaker goes to the human
list with the shared token recorded as the reason.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import importlib.util
import json
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = "scripts/parity/build_parity_matrix.py"
DEFAULT_OUT = REPO_ROOT / "docs" / "cli-tui-parity-matrix.md"
SRC_ROOT = REPO_ROOT / "src"

TARGETS: dict[str, str] = {
    "run_review": "src/openreview_cli/review/runner.py",
    "run_comparison": "src/openreview_cli/bilateral/__init__.py",
}
CLI_LANE_FILES = {
    "src/openreview_cli/app.py",
    "src/openreview_cli/benchmark/cli.py",
    "src/openreview_cli/prompts/cli.py",
}
TUI_LANE_PREFIX = "src/openreview_cli/tui/"
PRODUCT_MODE_LABEL = "product modes"

CLI_KINDS = {"command", "option", "argument"}
TUI_KINDS = {"app", "screen", "action", "binding"}

# "per", "if" and "md" are not core nouns.
_MIN_CORE_NOUN_LENGTH = 4
# A name token this short (a single letter such as a key binding) is not a word.
_MIN_NAME_TOKEN_LENGTH = 3
# Recursion guard for name and conditional resolution chains.
_MAX_RESOLVE_DEPTH = 4

# "prompt" is deliberately not generic: it is a product domain noun (the
# prompt library feature), not generic UI chrome, so "prompt history" matches
# "PromptHistoryScreen".
GENERIC_TOKENS = frozenset(
    {
        "get",
        "set",
        "list",
        "show",
        "add",
        "delete",
        "run",
        "new",
        "all",
        "the",
        "a",
        "an",
        "to",
        "of",
        "and",
        "or",
        "for",
        "in",
        "on",
        "with",
        "mode",
        "format",
        "output",
        "file",
        "path",
        "value",
        "name",
        "type",
        "id",
        "data",
        "item",
        "text",
        "flag",
        "option",
        "arg",
        "slot",
        "order",
        "open",
        "next",
        "prev",
        "previous",
        "page",
        "search",
        "form",
        "detail",
        "screen",
        "action",
        "app",
        "view",
        "edit",
        "force",
        "json",
        "dir",
        "url",
        "api",
        "key",
        "model",
        "history",
        "version",
        "check",
        "max",
        "min",
        "yes",
        "no",
        "per",
        "if",
        "md",
        "txt",
        "csv",
        "doc",
        "docs",
    }
)

# ASCII renderings for characters that appear in the repo source. The keys use
# escapes so that this module stays pure ASCII.
_ASCII_MAP = {
    "\u2014": "-",
    "\u2013": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2026": "...",
    "\u2022": "-",
    "\u2192": "->",
    "\u2190": "<-",
    "\u2713": "yes",
    "\u2717": "no",
    "\u26a0": "!",
    "\u2264": "<=",
    "\u2265": ">=",
    "\u00d7": "x",
    "\u00a2": "cents",
    "\u00b7": ".",
    "\u00b1": "+/-",
    "\u00a7": "S",
}


def _relative(path: str | Path) -> str:
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


def ascii_text(text: str) -> str:
    """Sanitize *text* down to plain ASCII, replacing known glyphs."""
    out = text
    for source, replacement in _ASCII_MAP.items():
        out = out.replace(source, replacement)
    out = unicodedata.normalize("NFKD", out)
    return "".join(char for char in out if ord(char) < 128)


def _display(value: object) -> str:
    """Normalize a Python literal into the row string form."""
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


def _module_name(path: Path) -> str:
    rel = path.resolve().relative_to(SRC_ROOT)
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _is_typer_call(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id == "typer" and func.attr in {"Option", "Argument"}
    return isinstance(func, ast.Name) and func.id in {"Option", "Argument"}


# --------------------------------------------------------------------------
# Targets and call sites (Part A)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _TargetParam:
    name: str
    default_display: str
    has_default: bool


@dataclass(frozen=True)
class _Target:
    name: str
    source_file: str
    line_number: int
    params: tuple[_TargetParam, ...]

    def param(self, name: str) -> _TargetParam | None:
        for item in self.params:
            if item.name == name:
                return item
        return None


@dataclass
class _CallSite:
    target: str
    caller: str
    module: str
    source_file: str
    line_number: int
    keywords: dict[str, ast.expr]
    positionals: list[ast.expr]
    chain: tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...]
    classes: tuple[ast.ClassDef, ...]
    index: _ModuleIndex | None = None
    entry_point: str = ""
    lane: str = "library"


@dataclass
class _Resolved:
    kind: str
    display: str
    raw: object = None
    expression: str = ""
    details: dict[str, str] = field(default_factory=dict)


def _parse_targets() -> dict[str, _Target]:
    targets: dict[str, _Target] = {}
    for name, rel in TARGETS.items():
        path = REPO_ROOT / rel
        tree = ast.parse(path.read_text(encoding="utf-8"))
        node = next(
            (
                item
                for item in ast.walk(tree)
                if isinstance(item, ast.FunctionDef) and item.name == name
            ),
            None,
        )
        if node is None:
            raise RuntimeError(f"{rel}: target function {name} not found")
        params: list[_TargetParam] = []
        for arg, default in _iter_params(node.args):
            params.append(
                _TargetParam(
                    name=arg.arg,
                    default_display=_display_node(default) if default is not None else "REQUIRED",
                    has_default=default is not None,
                )
            )
        targets[name] = _Target(
            name=name, source_file=rel, line_number=node.lineno, params=tuple(params)
        )
    return targets


def _iter_params(args: ast.arguments) -> list[tuple[ast.arg, ast.expr | None]]:
    positional = list(args.posonlyargs) + list(args.args)
    paired: list[tuple[ast.arg, ast.expr | None]] = list(
        zip(
            positional,
            [None] * (len(positional) - len(args.defaults)) + list(args.defaults),
            strict=False,
        )
    )
    paired.extend(zip(args.kwonlyargs, args.kw_defaults, strict=False))
    return paired


def _display_node(node: ast.expr | None) -> str:
    if node is None:
        return "REQUIRED"
    if isinstance(node, ast.Constant):
        return _display(node.value)
    return ascii_text(ast.unparse(node))


@dataclass
class _ParamDefault:
    found: bool
    default: ast.expr | None


class _ModuleIndex:
    """AST index for one source module: assignments, classes and call sites."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.source_file = _relative(path)
        self.module = _module_name(path)
        self.tree = ast.parse(path.read_text(encoding="utf-8"))
        self.module_assignments: dict[str, list[ast.expr]] = {}
        self.import_aliases: dict[str, str] = {}
        self.self_attributes: dict[str, dict[str, ast.Constant]] = {}
        self.call_sites: list[_CallSite] = []
        self.callers: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}
        self._build()

    def _build(self) -> None:
        for stmt in self.tree.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        self.module_assignments.setdefault(target.id, []).append(stmt.value)
            elif (
                isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Name)
                and stmt.value is not None
            ):
                self.module_assignments.setdefault(stmt.target.id, []).append(stmt.value)
            elif isinstance(stmt, ast.ImportFrom):
                for alias in stmt.names:
                    self.import_aliases[alias.asname or alias.name] = alias.name
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                self.self_attributes[node.name] = self._self_attributes(node)
        for stmt in self.tree.body:
            self._visit(stmt, (), ())
        for node in ast.walk(self.tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue
                callee = self._call_name(child)
                if callee and callee != node.name:
                    self.callers.setdefault(callee, []).append(node)

    @staticmethod
    def _self_attributes(cls_node: ast.ClassDef) -> dict[str, ast.Constant]:
        found: dict[str, ast.Constant] = {}
        for stmt in cls_node.body:
            if (
                isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
                and stmt.name == "__init__"
            ):
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
                        found.setdefault(target.attr, node.value)
        return found

    def _call_name(self, call: ast.Call) -> str | None:
        func = call.func
        if isinstance(func, ast.Name):
            return self.import_aliases.get(func.id, func.id)
        if isinstance(func, ast.Attribute):
            return func.attr
        return None

    def _visit(
        self,
        node: ast.AST,
        chain: tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...],
        classes: tuple[ast.ClassDef, ...],
    ) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            inner_chain = (*chain, node)
            for child in node.body:
                self._visit(child, inner_chain, classes)
            return
        if isinstance(node, ast.ClassDef):
            inner_classes = (*classes, node)
            for child in node.body:
                self._visit(child, chain, inner_classes)
            return
        if isinstance(node, ast.Call):
            name = self._call_name(node)
            if name in TARGETS:
                names = [item.name for item in chain]
                if classes:
                    names.insert(0, classes[-1].name)
                self.call_sites.append(
                    _CallSite(
                        target=name,
                        caller=f"{self.module}.{'.'.join(names)}",
                        module=self.module,
                        source_file=self.source_file,
                        line_number=node.lineno,
                        keywords={
                            keyword.arg: keyword.value
                            for keyword in node.keywords
                            if keyword.arg is not None
                        },
                        positionals=list(node.args),
                        chain=chain,
                        classes=classes,
                        index=self,
                    )
                )
        for child in ast.iter_child_nodes(node):
            self._visit(child, chain, classes)


def scan_call_sites() -> tuple[list[_CallSite], dict[tuple[str, str], list[Any]]]:
    """Scan every module under ``src/`` for calls to the target functions.

    Returns the call sites plus, per ``(source file, function name)``, the
    functions that call that name. The caller map lets a call site inside a
    shared helper be attributed to the commands whose callbacks use the helper.
    """
    sites: list[_CallSite] = []
    callers: dict[tuple[str, str], list[Any]] = {}
    for path in sorted(SRC_ROOT.rglob("*.py")):
        index = _ModuleIndex(path)
        sites.extend(index.call_sites)
        for name, nodes in index.callers.items():
            callers[(index.source_file, name)] = nodes
    return sites, callers


def _classify_lane(source_file: str) -> str:
    if source_file in CLI_LANE_FILES:
        return "cli"
    if source_file.startswith(TUI_LANE_PREFIX):
        return "tui"
    return "library"


def _anchor_lines(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[int]:
    lines = {node.lineno}
    if node.decorator_list:
        lines.add(node.decorator_list[0].lineno)
    return lines


def _cli_command_index(cli_inventory: dict[str, Any]) -> dict[tuple[str, int], set[str]]:
    index: dict[tuple[str, int], set[str]] = {}
    for row in cli_inventory.get("rows", []):
        if row.get("type") not in {"command", "group"}:
            continue
        key = (str(row.get("source_file", "")), int(row.get("line_number", 0)))
        index.setdefault(key, set()).add(str(row.get("name", "")))
    return index


def _commands_for_function(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    source_file: str,
    cli_index: dict[tuple[str, int], set[str]],
) -> set[str]:
    commands: set[str] = set()
    for line in _anchor_lines(func):
        commands |= cli_index.get((source_file, line), set())
    return commands


def _annotate_entry_points(
    sites: list[_CallSite],
    cli_index: dict[tuple[str, int], set[str]],
    callers: dict[tuple[str, str], list[Any]],
) -> None:
    for site in sites:
        site.lane = _classify_lane(site.source_file)
        commands: set[str] = set()
        if site.chain:
            owner = site.chain[-1]
            commands = _commands_for_function(owner, site.source_file, cli_index)
            if not commands:
                # A call site inside a shared helper belongs to the commands
                # whose callbacks call that helper, for example the product
                # mode commands that share one review implementation.
                for caller in callers.get((site.source_file, owner.name), []):
                    commands |= _commands_for_function(caller, site.source_file, cli_index)
        if len(commands) == 1:
            site.entry_point = commands.pop()
        elif len(commands) > 1:
            site.entry_point = PRODUCT_MODE_LABEL
        else:
            site.entry_point = site.caller


def _param_default(func: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> _ParamDefault:
    for arg, default in _iter_params(func.args):
        if arg.arg == name:
            return _ParamDefault(found=True, default=default)
    return _ParamDefault(found=False, default=None)


def _find_assignments(func: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> list[ast.expr]:
    values: list[ast.expr] = []
    for stmt in ast.walk(func):
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    values.append(stmt.value)
        elif (
            isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.target.id == name
            and stmt.value is not None
        ):
            values.append(stmt.value)
    return values


def _resolve(
    node: ast.expr | None,
    index: _ModuleIndex | None,
    chain: tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...],
    classes: tuple[ast.ClassDef, ...],
    depth: int = 0,
) -> _Resolved:
    """Resolve a call-site expression into a value kind and an effective value."""
    if node is None:
        return _Resolved(kind="absent", display="NOT PASSED")
    if depth <= _MAX_RESOLVE_DEPTH:
        if isinstance(node, ast.Constant):
            return _Resolved(
                kind="literal",
                display=_display(node.value),
                raw=node.value,
                expression=ast.unparse(node),
            )
        if isinstance(node, ast.IfExp):
            return _resolve_conditional(node, index, chain, classes, depth)
        if isinstance(node, ast.Name):
            return _resolve_name(node, index, chain, classes, depth)
        if isinstance(node, ast.Attribute):
            return _resolve_attribute(node, index, chain, classes)
    return _Resolved(
        kind="computed", display=ascii_text(ast.unparse(node)), expression=ast.unparse(node)
    )


def _resolve_conditional(
    node: ast.IfExp,
    index: _ModuleIndex | None,
    chain: tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...],
    classes: tuple[ast.ClassDef, ...],
    depth: int,
) -> _Resolved:
    expression = ast.unparse(node)
    if not isinstance(node.test, ast.Name):
        return _Resolved(kind="computed", display=ascii_text(expression), expression=expression)
    guard = _resolve_name(node.test, index, chain, classes, depth + 1)
    if not isinstance(guard.raw, (bool, int, float, str)) or guard.raw is None:
        return _Resolved(
            kind="computed",
            display=ascii_text(expression),
            expression=expression,
            details={"guard": node.test.id, "guard_default": guard.display},
        )
    body = _resolve(node.body, index, chain, classes, depth + 1)
    orelse = _resolve(node.orelse, index, chain, classes, depth + 1)
    selected = orelse if not guard.raw else body
    return _Resolved(
        kind="conditional",
        display=selected.display,
        raw=selected.raw,
        expression=expression,
        details={
            "guard": node.test.id,
            "guard_default": guard.display,
            "branch_true": body.display,
            "branch_false": orelse.display,
        },
    )


def _named(expression: str, resolved: _Resolved, origin: str) -> _Resolved:
    """Report a resolved value under the ``name`` value kind."""
    details = dict(resolved.details)
    details["resolved_by"] = origin
    return _Resolved(
        kind="name",
        display=resolved.display,
        raw=resolved.raw,
        expression=expression,
        details=details,
    )


def _resolve_enclosing_parameter(
    name: str,
    index: _ModuleIndex | None,
    chain: tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...],
    classes: tuple[ast.ClassDef, ...],
    depth: int,
) -> tuple[bool, _Resolved | None]:
    """Resolve *name* against an enclosing function parameter.

    Returns ``(found, resolved)``. ``found`` is true as soon as a parameter of
    that name exists, so that a parameter without a usable default stops the
    search instead of falling through to an unrelated outer scope.
    """
    for func in reversed(chain):
        found = _param_default(func, name)
        if not found.found:
            continue
        if found.default is None:
            return True, None
        if isinstance(found.default, ast.Call) and _is_typer_call(found.default):
            if not found.default.args:
                return True, _Resolved(kind="literal", display="None", raw=None)
            positional = _resolve(found.default.args[0], index, chain, classes, depth + 1)
            return True, None if positional.kind == "computed" else positional
        resolved_default = _resolve(found.default, index, chain, classes, depth + 1)
        return True, None if resolved_default.kind == "computed" else resolved_default
    return False, None


def _agree_on_one_value(
    values: list[ast.expr],
    index: _ModuleIndex | None,
    chain: tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...],
    classes: tuple[ast.ClassDef, ...],
    depth: int,
    *,
    literals_only: bool,
) -> _Resolved | None:
    """Resolve *values* only when every assignment agrees on one literal."""
    resolved = [_resolve(value, index, chain, classes, depth + 1) for value in values]
    displays = {item.display for item in resolved}
    kinds_ok = all(item.kind == "literal" for item in resolved) if literals_only else True
    if len(displays) != 1 or not kinds_ok or any(item.kind == "computed" for item in resolved):
        return None
    return resolved[0]


def _resolve_function_assignment(
    name: str,
    index: _ModuleIndex | None,
    chain: tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...],
    classes: tuple[ast.ClassDef, ...],
    depth: int,
) -> _Resolved | None:
    """Resolve *name* against an assignment inside an enclosing function."""
    for func in reversed(chain):
        assignments = _find_assignments(func, name)
        if not assignments:
            continue
        return _agree_on_one_value(assignments, index, chain, classes, depth, literals_only=False)
    return None


def _resolve_module_constant(
    name: str,
    index: _ModuleIndex | None,
    chain: tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...],
    classes: tuple[ast.ClassDef, ...],
    depth: int,
) -> _Resolved | None:
    """Resolve *name* against a module level assignment."""
    if index is None:
        return None
    values = index.module_assignments.get(name, [])
    if not values:
        return None
    return _agree_on_one_value(values, index, chain, classes, depth, literals_only=True)


def _resolve_name(
    node: ast.Name,
    index: _ModuleIndex | None,
    chain: tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...],
    classes: tuple[ast.ClassDef, ...],
    depth: int,
) -> _Resolved:
    expression = node.id
    found, parameter = _resolve_enclosing_parameter(node.id, index, chain, classes, depth)
    if not found:
        assigned = _resolve_function_assignment(node.id, index, chain, classes, depth)
        if assigned is not None:
            return _named(expression, assigned, "function_assignment")
        constant = _resolve_module_constant(node.id, index, chain, classes, depth)
        if constant is not None:
            return _named(expression, constant, "module_constant")
    elif parameter is not None:
        return _named(expression, parameter, "parameter_default")
    return _Resolved(kind="computed", display=ascii_text(expression), expression=expression)


def _resolve_attribute(
    node: ast.Attribute,
    index: _ModuleIndex | None,
    chain: tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...],
    classes: tuple[ast.ClassDef, ...],
) -> _Resolved:
    expression = ast.unparse(node)
    _ = chain
    if isinstance(node.value, ast.Name) and node.value.id == "self" and classes:
        attributes = index.self_attributes.get(classes[-1].name, {}) if index is not None else {}
        value = attributes.get(node.attr)
        if value is not None:
            return _Resolved(
                kind="attribute",
                display=_display(value.value),
                raw=value.value,
                expression=expression,
                details={"resolved_by": "self_attribute"},
            )
    return _Resolved(kind="computed", display=ascii_text(expression), expression=expression)


@dataclass
class _ArgRecord:
    """One ``(call site, target parameter)`` pair with its comparison value."""

    row: dict[str, Any]
    site: _CallSite
    param: str
    kind: str
    display: str
    comparison: str
    callee_default: str

    @property
    def source(self) -> str:
        """Where the argument is written, or the call line when it is absent."""
        return f"{self.row['source_file']}:{self.row['line_number']}"


def _build_arg_rows(
    targets: dict[str, _Target],
    sites: list[_CallSite],
) -> list[_ArgRecord]:
    records: list[_ArgRecord] = []
    for site in sites:
        target = targets[site.target]
        positional_names = [item.name for item in target.params][: len(site.positionals)]
        keywords = dict(site.keywords)
        for index, value in enumerate(site.positionals):
            keywords.setdefault(positional_names[index], value)
        for param in target.params:
            node = keywords.get(param.name)
            if node is None:
                resolved = _Resolved(kind="absent", display="NOT PASSED")
                comparison = param.default_display if param.has_default else "REQUIRED"
            else:
                resolved = _resolve(node, site.index, site.chain, site.classes)
                comparison = resolved.display
            # An argument that is present is cited at the argument itself: that
            # line carries the expression the row reports.
            line_number = node.lineno if node is not None else site.line_number
            row: dict[str, Any] = {
                "name": param.name,
                "type": "shared-call-arg",
                "flags_or_actions": [param.name],
                "default_value": resolved.display,
                "source_file": site.source_file,
                "line_number": line_number,
                "call_line": site.line_number,
                "caller": site.caller,
                "target": site.target,
                "entry_point": site.entry_point,
                "lane": site.lane,
                "value_kind": resolved.kind,
                "effective_value": resolved.display,
                "call_expr_src": resolved.expression,
                "callee_default": param.default_display if param.has_default else "REQUIRED",
            }
            if resolved.kind == "absent":
                row["value_kind_detail"] = "not_passed"
            row.update(
                {key: value for key, value in resolved.details.items() if key.startswith("branch_")}
            )
            if "guard" in resolved.details:
                row["guard"] = resolved.details["guard"]
                row["guard_default"] = resolved.details["guard_default"]
            records.append(
                _ArgRecord(
                    row=row,
                    site=site,
                    param=param.name,
                    kind=resolved.kind,
                    display=resolved.display,
                    comparison=comparison,
                    callee_default=row["callee_default"],
                )
            )
    return records


def _classify(cli: _ArgRecord, tui: _ArgRecord) -> str:
    if cli.kind == "computed" or tui.kind == "computed":
        return "UNRESOLVED"
    if cli.comparison == tui.comparison:
        return "MATCH"
    if cli.kind == "absent" or tui.kind == "absent":
        return "MISMATCH-ABSENT"
    return "MISMATCH"


@dataclass
class _Comparison:
    target: str
    param: str
    status: str
    cli: _ArgRecord | None = None
    tui: _ArgRecord | None = None
    note: str = ""


def _compare(records: list[_ArgRecord]) -> list[_Comparison]:
    grouped: dict[tuple[str, str], list[_ArgRecord]] = {}
    for record in records:
        grouped.setdefault((record.site.target, record.param), []).append(record)

    comparisons: list[_Comparison] = []
    for (target, param), items in grouped.items():
        cli_items = [item for item in items if item.site.lane == "cli"]
        tui_items = [item for item in items if item.site.lane == "tui"]
        if not tui_items:
            comparisons.append(
                _Comparison(
                    target=target,
                    param=param,
                    status="NO-COUNTERPART",
                    cli=cli_items[0] if cli_items else None,
                    note="no TUI call site" if cli_items else "no call site in the TUI or CLI lane",
                )
            )
            continue
        if not cli_items:
            comparisons.append(
                _Comparison(
                    target=target,
                    param=param,
                    status="NO-COUNTERPART",
                    tui=tui_items[0],
                    note="no CLI call site",
                )
            )
            continue
        for cli_item in cli_items:
            for tui_item in tui_items:
                comparisons.append(
                    _Comparison(
                        target=target,
                        param=param,
                        status=_classify(cli_item, tui_item),
                        cli=cli_item,
                        tui=tui_item,
                    )
                )
    return comparisons


def _mismatch_rows(comparisons: list[_Comparison]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for comparison in comparisons:
        if comparison.status not in {"MISMATCH", "MISMATCH-ABSENT"}:
            continue
        cli = comparison.cli
        tui = comparison.tui
        if cli is None or tui is None:
            continue
        rows.append(
            {
                "name": f"{comparison.target}.{comparison.param}",
                "type": "mismatch",
                "flags_or_actions": [comparison.status],
                "default_value": f"{cli.display} vs {tui.display}",
                "source_file": cli.row["source_file"],
                "line_number": cli.row["line_number"],
                "target": comparison.target,
                "param": comparison.param,
                "status": comparison.status,
                "cli_value": cli.display,
                "cli_entry_point": cli.site.entry_point,
                "cli_source": cli.source,
                "tui_value": tui.display,
                "tui_entry_point": tui.site.entry_point,
                "tui_source": tui.source,
                "callee_default": cli.callee_default,
            }
        )
    return rows


# --------------------------------------------------------------------------
# Name join (Part B)
# --------------------------------------------------------------------------


def _words(text: str) -> list[str]:
    spaced = ""
    for index, char in enumerate(text):
        if index and char.isupper() and (text[index - 1].islower() or text[index - 1].isdigit()):
            spaced += " "
        spaced += char
    chunks: list[str] = []
    for chunk in spaced.replace("_", " ").replace("-", " ").replace(".", " ").split():
        cleaned = "".join(char for char in chunk if char.isalnum())
        if cleaned:
            chunks.append(cleaned.lower())
    return chunks


def _root(word: str) -> str:
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _roots(text: str) -> set[str]:
    return {_root(word) for word in _words(text)}


def _tokens(text: str) -> set[str]:
    return {
        word
        for word in _roots(text)
        if word not in GENERIC_TOKENS and len(word) >= _MIN_NAME_TOKEN_LENGTH and not word.isdigit()
    }


def _normalized(text: str) -> str:
    return " ".join(_words(text))


@dataclass
class _JoinItem:
    side: str
    name: str
    kind: str
    owners: list[str]
    flags: list[str]
    help_text: str
    source_file: str
    line_number: int

    @property
    def source(self) -> str:
        return f"{self.source_file}:{self.line_number}"

    @property
    def owner(self) -> str:
        """Human readable owner list, short enough for one table cell."""
        unique: list[str] = []
        for owner in self.owners:
            if owner and owner not in unique:
                unique.append(owner)
        return _summarize(unique, limit=2)


def _join_items(rows: list[dict[str, Any]], side: str, kinds: set[str]) -> list[_JoinItem]:
    """Group inventory rows into join items, keyed by kind, name and help text.

    A flag declared by several commands (for example ``--playbook`` in the
    product modes) is one item with several owners, not one item per command.
    """
    grouped: dict[tuple[str, str, str], _JoinItem] = {}
    for row in rows:
        if row.get("type") not in kinds:
            continue
        key = (str(row.get("type", "")), str(row.get("name", "")), str(row.get("help_text", "")))
        if key not in grouped:
            grouped[key] = _JoinItem(
                side=side,
                name=str(row.get("name", "")),
                kind=str(row.get("type", "")),
                owners=[],
                flags=[str(flag) for flag in row.get("flags_or_actions", [])],
                help_text=str(row.get("help_text", "")),
                source_file=str(row.get("source_file", "")),
                line_number=int(row.get("line_number", 0) or 0),
            )
        grouped[key].owners.append(str(row.get("owner", "")))
    return list(grouped.values())


def _pair(
    cli: _JoinItem, tui: _JoinItem, match: str, reason: str, shared: list[str]
) -> dict[str, Any]:
    return {
        "match": match,
        "reason": reason,
        "shared_tokens": sorted(shared),
        "cli_item": cli.name,
        "cli_kind": cli.kind,
        "cli_owner": cli.owner,
        "cli_flags": cli.flags,
        "cli_source": cli.source,
        "tui_item": tui.name,
        "tui_kind": tui.kind,
        "tui_owner": tui.owner,
        "tui_source": tui.source,
    }


def _prose_tokens(cli: _JoinItem, tui: _JoinItem) -> set[str]:
    """Core nouns shared between the CLI help text and the TUI label.

    Only a binding carries a real label, its description. A screen or action
    ``help_text`` is the class or method docstring, which is documentation, not
    a label, so those rows never take part in a prose match.
    """
    if tui.kind != "binding":
        return set()
    return {
        token
        for token in _tokens(cli.help_text) & _tokens(tui.help_text)
        if len(token) >= _MIN_CORE_NOUN_LENGTH
    }


def _is_short_key_binding(pair: dict[str, Any]) -> bool:
    """A one or two character binding key is a shortcut, not a reviewable feature."""
    return pair.get("tui_kind") == "binding" and len(str(pair.get("tui_item", ""))) <= 2


def _human_group_key(pair: dict[str, Any]) -> str:
    """The TUI screen a human-confirmation pair points at."""
    kind = str(pair.get("tui_kind", ""))
    if kind in {"screen", "app"}:
        return str(pair.get("tui_item", ""))
    return str(pair.get("tui_owner", "")) or str(pair.get("tui_item", ""))


def _merge_human_rows(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse rows for the same CLI item and TUI item, merging their sources."""
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for pair in pairs:
        key = (
            str(pair["cli_item"]),
            str(pair["cli_kind"]),
            str(pair["tui_item"]),
            str(pair["tui_kind"]),
        )
        entry = merged.setdefault(
            key,
            {
                "cli_item": str(pair["cli_item"]),
                "cli_kind": str(pair["cli_kind"]),
                "cli_sources": set(),
                "tui_item": str(pair["tui_item"]),
                "tui_kind": str(pair["tui_kind"]),
                "tui_sources": set(),
                "shared_tokens": set(),
                "reason": str(pair["reason"]),
            },
        )
        entry["cli_sources"].add(str(pair.get("cli_source", "")))
        entry["tui_sources"].add(str(pair.get("tui_source", "")))
        entry["shared_tokens"].update(str(token) for token in pair.get("shared_tokens", []))
    rows: list[dict[str, Any]] = []
    for entry in merged.values():
        entry["cli_source"] = "; ".join(sorted(entry["cli_sources"]))
        entry["tui_source"] = "; ".join(sorted(entry["tui_sources"]))
        entry["shared_tokens"] = sorted(entry["shared_tokens"])
        rows.append(entry)
    return rows


def build_join(cli_rows: list[dict[str, Any]], tui_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Join CLI items with TUI items and report matched, human and unmatched items."""
    cli_items = _join_items(cli_rows, "cli", CLI_KINDS)
    tui_items = _join_items(tui_rows, "tui", TUI_KINDS)
    certain: list[dict[str, Any]] = []
    human: list[dict[str, Any]] = []
    matched_cli: set[tuple[str, str, str]] = set()
    matched_tui: set[tuple[str, str, str]] = set()

    def _key(item: _JoinItem) -> tuple[str, str, str]:
        return (item.kind, item.name, item.help_text)

    for cli in cli_items:
        for tui in tui_items:
            shared_all = _roots(cli.name) & _roots(tui.name)
            shared_significant = _tokens(cli.name) & _tokens(tui.name)
            shared_prose = _prose_tokens(cli, tui)
            if _normalized(cli.name) == _normalized(tui.name):
                pair = _pair(cli, tui, "CERTAIN", "identical normalized name", sorted(shared_all))
            elif shared_significant:
                pair = _pair(
                    cli, tui, "CERTAIN", "shared significant name token", sorted(shared_significant)
                )
            elif shared_prose:
                pair = _pair(
                    cli,
                    tui,
                    "NEEDS-HUMAN",
                    f"shared core noun in help text and label: {', '.join(sorted(shared_prose))}",
                    sorted(shared_prose),
                )
                human.append(pair)
                continue
            elif shared_all:
                pair = _pair(
                    cli,
                    tui,
                    "NEEDS-HUMAN",
                    f"generic token only: {', '.join(sorted(shared_all))}",
                    sorted(shared_all),
                )
                human.append(pair)
                continue
            else:
                continue
            certain.append(pair)
            matched_cli.add(_key(cli))
            matched_tui.add(_key(tui))

    for pair in human:
        for cli_item in cli_items:
            if cli_item.name == pair["cli_item"] and cli_item.kind == pair["cli_kind"]:
                matched_cli.add(_key(cli_item))
        for tui_item in tui_items:
            if tui_item.name == pair["tui_item"] and tui_item.kind == pair["tui_kind"]:
                matched_tui.add(_key(tui_item))

    unmatched_cli = [item for item in cli_items if _key(item) not in matched_cli]
    unmatched_tui = [item for item in tui_items if _key(item) not in matched_tui]

    # Report the strongest classification per CLI item: a certain match does not
    # also generate a generic-overlap human row. A generic-token-only pair is
    # only noise once the same CLI item is already matched with certainty
    # elsewhere in this join. The unmatched computation above still sees every
    # human pair, so this only trims the reported human list.
    certain_cli = {(pair["cli_kind"], pair["cli_item"]) for pair in certain}
    visible = [pair for pair in human if not _is_short_key_binding(pair)]
    kept = [
        pair
        for pair in visible
        if not (
            str(pair["reason"]).startswith("generic token only")
            and (pair["cli_kind"], pair["cli_item"]) in certain_cli
        )
    ]
    hidden = sum(1 for pair in human if _is_short_key_binding(pair))
    return {
        "certain": certain,
        "human": kept,
        "human_hidden": hidden,
        "unmatched_cli": unmatched_cli,
        "unmatched_tui": unmatched_tui,
    }


def detect_semantic_collisions(cli_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Report CLI flags that carry more than one meaning."""
    groups: dict[str, dict[str, dict[str, Any]]] = {}
    for row in cli_rows:
        if row.get("type") != "option":
            continue
        flags = [str(flag) for flag in row.get("flags_or_actions", [])]
        if not flags:
            continue
        flag = flags[0]
        help_text = str(row.get("help_text", ""))
        entry = groups.setdefault(flag, {}).setdefault(
            help_text, {"help": help_text, "owners": [], "sources": []}
        )
        owner = str(row.get("owner", ""))
        if owner and owner not in entry["owners"]:
            entry["owners"].append(owner)
        source = f"{row.get('source_file', '')}:{row.get('line_number', 0)}"
        if source not in entry["sources"]:
            entry["sources"].append(source)

    collisions: list[dict[str, Any]] = []
    for flag, meanings in groups.items():
        if len(meanings) < 2:
            continue
        collisions.append({"flag": flag, "meanings": [meanings[key] for key in sorted(meanings)]})
    return sorted(collisions, key=lambda item: item["flag"])


def _summarize(values: list[str], limit: int = 4) -> str:
    if len(values) <= limit:
        return ", ".join(values)
    return ", ".join(values[:limit]) + f", +{len(values) - limit} more"


# --------------------------------------------------------------------------
# Rendering (Part C)
# --------------------------------------------------------------------------

# The reader meets Table C here. The note qualifies the CERTAIN claim before the
# rows are read, so a name join is not mistaken for a functional proof.
TABLE_C_NOTE = (
    "Note: `CERTAIN` in this table means only that the CLI item and the TUI item share a "
    "significant name token, printed in the `Shared token` column. It is a name join, not "
    "evidence that the TUI implements the command: a row that matched on the bare domain "
    "token `prompt` records a shared noun, not a functional correspondence. The only "
    "functional comparison in this document is the shared-call comparison for the two "
    "targeted functions `run_review` and `run_comparison`, where each CLI and TUI call site "
    "is compared argument by argument."
)


def check_rows(rows: list[dict[str, Any]]) -> list[str]:
    """Return a problem description for every row without usable provenance."""
    problems: list[str] = []
    for row in rows:
        source_file = str(row.get("source_file", ""))
        try:
            line_number = int(row.get("line_number", 0) or 0)
        except (TypeError, ValueError):
            line_number = 0
        if not source_file:
            problems.append(f"row without a source file: {row.get('name', '<unnamed>')}")
        elif not (REPO_ROOT / source_file).is_file():
            problems.append(f"row points at a missing source file: {source_file}")
        if line_number < 1:
            problems.append(f"row with line number below 1: {row.get('name', '<unnamed>')}")
    return problems


def _cell(text: str) -> str:
    return ascii_text(text).replace("|", "\\|").replace("\n", " ").strip()


def _mismatch_by_site(data: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Index mismatch rows by target, parameter and CLI call site."""
    found: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in data.get("rows", []):
        if row.get("type") == "mismatch":
            key = (
                str(row.get("target", "")),
                str(row.get("param", "")),
                str(row.get("cli_source", "")),
            )
            found[key] = row
    return found


def _mismatch_cell(row: dict[str, Any]) -> str:
    return (
        f"{row['cli_value']} (CLI {row['cli_source']}) vs "
        f"{row['tui_value']} (TUI {row['tui_source']})"
    )


def _shared_call_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in data.get("rows", []) if row.get("type") == "shared-call-arg"]


def _cli_item_for_param(data: dict[str, Any], entry_point: str, param: str) -> str:
    """Find the CLI option or argument row that exposes *param*.

    The match must be exact on the name tokens, so ``no_pii`` picks ``--no-pii``
    and not ``--allow-partial-pii``. A parameter with no exact option of its own,
    for example ``mode_threshold_overrides``, is labelled by its own name rather
    than borrowing an unrelated flag.
    """
    wanted = _tokens(param)
    if not wanted:
        return f"{entry_point} ({param})"
    wanted_name = _normalized(param)
    token_matches: list[str] = []
    for row in data.get("cli_inventory", {}).get("rows", []):
        if (
            row.get("type") not in {"option", "argument"}
            or str(row.get("owner", "")) != entry_point
        ):
            continue
        flags = [str(flag) for flag in row.get("flags_or_actions", [])]
        label = flags[0] if flags else str(row.get("name", ""))
        if _tokens(label) != wanted:
            continue
        if _normalized(label) == wanted_name:
            return f"{label} ({entry_point})"
        token_matches.append(label)
    unique = sorted(set(token_matches))
    if len(unique) == 1:
        return f"{unique[0]} ({entry_point})"
    return f"{entry_point} ({param})"


def _build_table_c(data: dict[str, Any]) -> list[dict[str, str]]:
    """Build the parity join table, including the default comparison lane."""
    mismatches = _mismatch_by_site(data)
    arg_rows = _shared_call_rows(data)
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for arg in arg_rows:
        target = str(arg.get("target", ""))
        param = str(arg.get("name", ""))
        lane = str(arg.get("lane", ""))
        if lane == "cli":
            cli_item = _cli_item_for_param(data, str(arg.get("entry_point", "")), param)
            tui_item = ""
            tui_source = "(none)"
            for peer in arg_rows:
                if (
                    peer.get("target") == target
                    and peer.get("name") == param
                    and peer.get("lane") == "tui"
                ):
                    tui_item = str(peer.get("entry_point", ""))
                    tui_source = f"{peer.get('source_file', '')}:{peer.get('line_number', 0)}"
                    break
            key = (target, param, cli_item, tui_item)
            if key in seen:
                continue
            seen.add(key)
            cli_source = f"{arg.get('source_file', '')}:{arg.get('line_number', 0)}"
            mismatch = mismatches.get((target, param, cli_source))
            if mismatch is not None:
                cell = _mismatch_cell(mismatch)
                match = mismatch["status"]
            else:
                cell = "none"
                match = "SHARED-CALL"
            if not tui_item:
                tui_item = f"no TUI control for {param}"
            rows.append(
                {
                    "match": match,
                    "shared_token": "n/a",
                    "cli_item": cli_item,
                    "cli_source": cli_source,
                    "tui_item": tui_item,
                    "tui_source": tui_source,
                    "default_mismatch": cell,
                }
            )

    for pair in data.get("join", []):
        if pair.get("match") != "CERTAIN":
            continue
        rows.append(
            {
                "match": "CERTAIN",
                "shared_token": ", ".join(str(token) for token in pair.get("shared_tokens", [])),
                "cli_item": f"{pair['cli_item']} ({pair['cli_kind']})",
                "cli_source": str(pair["cli_source"]),
                "tui_item": f"{pair['tui_item']} ({pair['tui_kind']})",
                "tui_source": str(pair["tui_source"]),
                "default_mismatch": "none",
            }
        )

    order = {"MISMATCH": 0, "MISMATCH-ABSENT": 0, "UNRESOLVED": 1, "SHARED-CALL": 2, "CERTAIN": 3}
    return sorted(
        rows, key=lambda row: (order.get(row["match"], 9), row["cli_item"], row["tui_item"])
    )


def _inventory_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Name | Type | Owner | Flags or actions | Default | Source |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        flags = ", ".join(str(flag) for flag in row.get("flags_or_actions", []))
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(str(row.get("name", ""))),
                    _cell(str(row.get("type", ""))),
                    _cell(str(row.get("owner", ""))),
                    _cell(flags),
                    _cell(str(row.get("default_value", ""))),
                    _cell(f"{row.get('source_file', '')}:{row.get('line_number', 0)}"),
                ]
            )
            + " |"
        )
    return lines


def _regenerate_commands() -> list[str]:
    return [
        "uv run python scripts/parity/inventory_cli.py --out draft/parity/cli-inventory.json",
        "uv run python scripts/parity/inventory_tui.py --out draft/parity/tui-inventory.json",
        "uv run python scripts/parity/build_parity_matrix.py"
        " --cli-json draft/parity/cli-inventory.json --tui-json draft/parity/tui-inventory.json",
    ]


def render_markdown(data: dict[str, Any]) -> str:
    """Render the parity matrix markdown, or exit non zero on bad provenance."""
    problems = check_rows(list(data.get("rows", [])))
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        raise SystemExit(2)

    meta = dict(data.get("meta", {}))
    cli_rows = list(data.get("cli_inventory", {}).get("rows", []))
    tui_rows = list(data.get("tui_inventory", {}).get("rows", []))
    table_c = _build_table_c(data)
    mismatches = [row for row in data.get("rows", []) if row.get("type") == "mismatch"]
    comparisons = list(data.get("comparisons", []))
    no_counterpart = [item for item in comparisons if item.get("status") == "NO-COUNTERPART"]
    unresolved = [item for item in comparisons if item.get("status") == "UNRESOLVED"]

    lines: list[str] = []
    lines.append("# CLI and TUI parity matrix")
    lines.append("")
    lines.append(
        "Generated from live source by `scripts/parity/build_parity_matrix.py`. Every row cites a "
        "source file and a line number."
    )
    lines.append("")
    lines.append(f"- Commit: `{ascii_text(str(meta.get('commit', 'unknown')))}`")
    lines.append(f"- Generated at: {ascii_text(str(meta.get('generated_at', '')))}")
    lines.append(f"- CLI framework: Typer {ascii_text(str(meta.get('typer_version', 'unknown')))}")
    lines.append(
        f"- TUI framework: Textual {ascii_text(str(meta.get('textual_version', 'unknown')))}"
    )
    lines.append(f"- Python: {ascii_text(str(meta.get('python_version', '')))}")
    lines.append("")
    lines.append("Regenerate with:")
    lines.append("")
    lines.append("```bash")
    lines.extend(_regenerate_commands())
    lines.append("```")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Item | Count |")
    lines.append("|---|---|")
    lines.append(f"| CLI inventory rows | {len(cli_rows)} |")
    lines.append(f"| TUI inventory rows | {len(tui_rows)} |")
    lines.append(f"| Shared call argument rows | {len(_shared_call_rows(data))} |")
    lines.append(f"| Compared shared call argument pairs | {len(comparisons)} |")
    lines.append(f"| Default-value mismatches | {len(mismatches)} |")
    lines.append(f"| Parity join rows | {len(table_c)} |")
    lines.append(f"| Needs human confirmation | {len(data.get('needs_human_confirmation', []))} |")
    lines.append(f"| Hidden single-key bindings | {data.get('needs_human_hidden', 0)} |")
    lines.append(f"| Unmatched CLI items | {len(data.get('unmatched_cli', []))} |")
    lines.append(f"| Unmatched TUI items | {len(data.get('unmatched_tui', []))} |")
    lines.append(f"| Semantic collisions | {len(data.get('semantic_collisions', []))} |")
    lines.append("")

    lines.append("## Table A: CLI inventory")
    lines.append("")
    lines.extend(_inventory_table(cli_rows))
    lines.append("")

    lines.append("## Table B: TUI inventory")
    lines.append("")
    lines.extend(_inventory_table(tui_rows))
    lines.append("")

    lines.append("## Table C: parity join")
    lines.append("")
    lines.append(TABLE_C_NOTE)
    lines.append("")
    lines.append(
        "| Match | Shared token | CLI item | CLI source | TUI item | TUI source | Default mismatch |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for row in table_c:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(row["match"]),
                    _cell(row["shared_token"]),
                    _cell(row["cli_item"]),
                    _cell(row["cli_source"]),
                    _cell(row["tui_item"]),
                    _cell(row["tui_source"]),
                    _cell(row["default_mismatch"]),
                ]
            )
            + " |"
        )
    lines.append("")

    lines.append("## Default-value mismatches")
    lines.append("")
    if mismatches:
        for row in mismatches:
            lines.append(
                f"- `{_cell(str(row['target']))}.{_cell(str(row['param']))}` ({_cell(str(row['status']))}): "
                f"CLI `{_cell(str(row['cli_value']))}` at {_cell(str(row['cli_source']))} "
                f"({_cell(str(row['cli_entry_point']))}) against TUI "
                f"`{_cell(str(row['tui_value']))}` at {_cell(str(row['tui_source']))} "
                f"({_cell(str(row['tui_entry_point']))}). Callee default: "
                f"`{_cell(str(row['callee_default']))}`."
            )
    else:
        lines.append("No default-value mismatch was detected.")
    lines.append("")

    lines.append("## Shared call sites without a counterpart")
    lines.append("")
    if no_counterpart:
        for item in no_counterpart:
            lines.append(
                f"- `{_cell(str(item['target']))}.{_cell(str(item['param']))}`: {_cell(str(item['note']))}"
            )
    else:
        lines.append("Every shared call argument has a counterpart in the other entry point lane.")
    lines.append("")

    lines.append("## Unresolved shared call arguments")
    lines.append("")
    if unresolved:
        for item in unresolved:
            lines.append(
                f"- `{_cell(str(item['target']))}.{_cell(str(item['param']))}`: "
                f"CLI `{_cell(str(item.get('cli_value', '')))}` ({_cell(str(item.get('cli_source', '')))}) "
                f"against TUI `{_cell(str(item.get('tui_value', '')))}` "
                f"({_cell(str(item.get('tui_source', '')))})."
            )
    else:
        lines.append("Every compared shared call argument resolved to a value.")
    lines.append("")

    lines.append("## Needs human confirmation")
    lines.append("")
    human = list(data.get("needs_human_confirmation", []))
    hidden = int(data.get("needs_human_hidden", 0) or 0)
    if human:
        lines.append(
            "Grouped by the TUI screen each CLI item points at. "
            f"{hidden} single and double character keybinding rows are omitted."
        )
        lines.append("")
        groups: dict[str, list[dict[str, Any]]] = {}
        for pair in human:
            groups.setdefault(_human_group_key(pair), []).append(pair)
        for screen in sorted(groups):
            lines.append(f"### {_cell(screen)}")
            lines.append("")
            lines.append(
                "| CLI item | CLI source | TUI item | TUI source | Shared token | Reason |"
            )
            lines.append("|---|---|---|---|---|---|")
            for row in _merge_human_rows(groups[screen]):
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            _cell(f"{row['cli_item']} ({row['cli_kind']})"),
                            _cell(row["cli_source"]),
                            _cell(f"{row['tui_item']} ({row['tui_kind']})"),
                            _cell(row["tui_source"]),
                            _cell(", ".join(row["shared_tokens"])),
                            _cell(row["reason"]),
                        ]
                    )
                    + " |"
                )
            lines.append("")
    else:
        lines.append("No pair needs human confirmation.")
    lines.append("")

    lines.append("## Unmatched CLI items")
    lines.append("")
    unmatched_cli = list(data.get("unmatched_cli", []))
    if unmatched_cli:
        lines.append("| Item | Type | Owner | Source |")
        lines.append("|---|---|---|---|")
        for item in unmatched_cli:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(str(item["name"])),
                        _cell(str(item["kind"])),
                        _cell(str(item["owner"])),
                        _cell(str(item["source"])),
                    ]
                )
                + " |"
            )
    else:
        lines.append("Every CLI item has at least one candidate TUI counterpart.")
    lines.append("")

    lines.append("## Unmatched TUI items")
    lines.append("")
    unmatched_tui = list(data.get("unmatched_tui", []))
    if unmatched_tui:
        lines.append("| Item | Type | Owner | Source |")
        lines.append("|---|---|---|---|")
        for item in unmatched_tui:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(str(item["name"])),
                        _cell(str(item["kind"])),
                        _cell(str(item["owner"])),
                        _cell(str(item["source"])),
                    ]
                )
                + " |"
            )
    else:
        lines.append("Every TUI item has at least one candidate CLI counterpart.")
    lines.append("")

    lines.append("## Semantic collisions")
    lines.append("")
    collisions = list(data.get("semantic_collisions", []))
    if collisions:
        for collision in collisions:
            lines.append(f"### `{_cell(str(collision['flag']))}`")
            lines.append("")
            for meaning in collision["meanings"]:
                lines.append(
                    f"- {_cell(str(meaning['help']))} (owners: {_cell(_summarize(list(meaning['owners'])))}; "
                    f"sources: {_cell(_summarize(list(meaning['sources'])))})."
                )
            lines.append("")
    else:
        lines.append("No CLI flag carries more than one meaning.")
        lines.append("")

    lines.append("## Row counts")
    lines.append("")
    lines.append("| Row type | Count |")
    lines.append("|---|---|")
    counts: dict[str, int] = {}
    for row in data.get("rows", []):
        key = str(row.get("type", ""))
        counts[key] = counts.get(key, 0) + 1
    for key in sorted(counts):
        lines.append(f"| {_cell(key)} | {counts[key]} |")
    lines.append(f"| total | {len(list(data.get('rows', [])))} |")
    lines.append("")
    lines.append("Regenerate with:")
    lines.append("")
    lines.append("```bash")
    lines.extend(_regenerate_commands())
    lines.append("```")
    lines.append("")
    return ascii_text("\n".join(lines))


# --------------------------------------------------------------------------
# Collection and entry point
# --------------------------------------------------------------------------


def _load_sibling(name: str) -> ModuleType:
    """Import a sibling script from ``scripts/parity`` by file path."""
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"parity_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _read_inventory(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "rows" not in data:
        raise RuntimeError(f"{path}: expected an inventory JSON object with a rows key")
    return data


def collect(cli_json: Path | None = None, tui_json: Path | None = None) -> dict[str, Any]:
    """Build the parity matrix data structure without rendering it."""
    import textual
    import typer

    if cli_json is not None:
        cli_inventory = _read_inventory(cli_json)
    else:
        cli_inventory = _load_sibling("inventory_cli").collect()
    if tui_json is not None:
        tui_inventory = _read_inventory(tui_json)
    else:
        tui_inventory = _load_sibling("inventory_tui").collect()

    targets = _parse_targets()
    sites, callers = scan_call_sites()
    _annotate_entry_points(sites, _cli_command_index(cli_inventory), callers)

    arg_records = _build_arg_rows(targets, sites)
    comparisons = _compare(arg_records)
    mismatch_rows = _mismatch_rows(comparisons)

    cli_rows = list(cli_inventory.get("rows", []))
    tui_rows = list(tui_inventory.get("rows", []))
    join = build_join(cli_rows, tui_rows)

    comparisons_data = []
    for comparison in comparisons:
        comparisons_data.append(
            {
                "target": comparison.target,
                "param": comparison.param,
                "status": comparison.status,
                "note": comparison.note,
                "cli_value": comparison.cli.display if comparison.cli else "",
                "cli_source": comparison.cli.source if comparison.cli else "",
                "cli_entry_point": comparison.cli.site.entry_point if comparison.cli else "",
                "tui_value": comparison.tui.display if comparison.tui else "",
                "tui_source": comparison.tui.source if comparison.tui else "",
                "tui_entry_point": comparison.tui.site.entry_point if comparison.tui else "",
            }
        )

    rows: list[dict[str, Any]] = [
        *arg_records_rows(arg_records),
        *mismatch_rows,
        *cli_rows,
        *tui_rows,
    ]
    meta = {
        "generator": GENERATOR,
        "generated_at": _now(),
        "commit": _commit(),
        "typer_version": str(getattr(typer, "__version__", "unknown")),
        "textual_version": str(getattr(textual, "__version__", "unknown")),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "row_count": len(rows),
        "cli_rows": len(cli_rows),
        "tui_rows": len(tui_rows),
        "shared_call_rows": len(arg_records),
        "comparison_count": len(comparisons),
        "mismatch_count": len(mismatch_rows),
        "join_count": len(join["certain"]),
        "needs_human_count": len(join["human"]),
        "targets": {
            name: {
                "source": target.source_file,
                "line_number": target.line_number,
                "params": len(target.params),
            }
            for name, target in targets.items()
        },
    }
    return {
        "meta": meta,
        "rows": rows,
        "comparisons": comparisons_data,
        "join": join["certain"],
        "needs_human_confirmation": join["human"],
        "needs_human_hidden": join.get("human_hidden", 0),
        "unmatched_cli": [_join_item_dict(item) for item in join["unmatched_cli"]],
        "unmatched_tui": [_join_item_dict(item) for item in join["unmatched_tui"]],
        "semantic_collisions": detect_semantic_collisions(cli_rows),
        "cli_inventory": cli_inventory,
        "tui_inventory": tui_inventory,
    }


def arg_records_rows(records: list[_ArgRecord]) -> list[dict[str, Any]]:
    """Return the emitted rows for the resolved shared call arguments."""
    return [record.row for record in records]


def _join_item_dict(item: _JoinItem) -> dict[str, Any]:
    return {
        "name": item.name,
        "kind": item.kind,
        "owner": item.owner,
        "owners": _summarize([owner for owner in item.owners if owner], limit=6),
        "source": item.source,
        "help_text": item.help_text,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the CLI and TUI parity matrix.")
    parser.add_argument(
        "--cli-json", type=Path, default=None, help="Pre-generated CLI inventory JSON."
    )
    parser.add_argument(
        "--tui-json", type=Path, default=None, help="Pre-generated TUI inventory JSON."
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Markdown output path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Print the matrix data as JSON and write the markdown to ``--out``."""
    args = _build_parser().parse_args(argv)
    data = collect(cli_json=args.cli_json, tui_json=args.tui_json)
    markdown = render_markdown(data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")
    print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
