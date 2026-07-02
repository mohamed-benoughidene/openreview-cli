from __future__ import annotations

from difflib import unified_diff
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from openreview_cli.config.paths import get_data_dir
from openreview_cli.prompts.store import PromptStore

console = Console()

prompt_app = typer.Typer(
    name="prompt",
    help="Manage versioned prompts.",
    no_args_is_help=True,
)


def _get_store() -> PromptStore:
    db_path = get_data_dir() / "openreview.db"
    store = PromptStore(db_path)
    store.init()
    return store


def _exit(code: int, message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(code=code)


@prompt_app.command("create")
def prompt_create(
    name: str = typer.Option(..., "--name", help="Unique prompt identifier"),
    content: str = typer.Option(..., "--content", help="Prompt instruction text (max 16 KB)"),
    tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags"),
    description: str | None = typer.Option(
        None, "--description", help="Human-readable description"
    ),
) -> None:
    store = _get_store()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    try:
        pv = store.create(name, content, tags=tag_list, description=description)
        typer.echo(f"Created prompt '{name}' version {pv.version}")
    except ValueError as e:
        if "already exists" in str(e):
            _exit(1, str(e))
        if "16384" in str(e):
            _exit(2, str(e))
        _exit(1, str(e))


@prompt_app.command("update")
def prompt_update(
    name: str = typer.Argument(..., help="Prompt name"),
    content: str = typer.Option(..., "--content", help="New prompt content"),
    tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags"),
    description: str | None = typer.Option(None, "--description", help="Updated description"),
) -> None:
    store = _get_store()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    try:
        pv = store.update(name, content, tags=tag_list, description=description)
        typer.echo(f"Updated prompt '{name}' to version {pv.version}")
    except ValueError as e:
        _exit(1, str(e))


@prompt_app.command("list")
def prompt_list(
    page: int = typer.Option(1, "--page", help="Page number"),
    per_page: int = typer.Option(25, "--per-page", help="Items per page"),
) -> None:
    store = _get_store()
    prompts = store.list(page=page, per_page=per_page)
    table = Table(title="Prompts")
    table.add_column("Name", style="cyan")
    table.add_column("Latest Version", style="green")
    table.add_column("Created", style="white")
    for p in prompts:
        table.add_row(p.name, str(p.latest_version), p.created_at)
    console.print(table)


@prompt_app.command("show")
def prompt_show(
    name: str = typer.Argument(..., help="Prompt name"),
    version: int | None = typer.Option(
        None, "--version", help="Specific version (default: latest)"
    ),
) -> None:
    store = _get_store()
    try:
        pv = store.get(name, version) if version else store.get_latest(name)
    except ValueError as e:
        _exit(1, str(e))
        return
    typer.echo(f"Name: {pv.name}")
    typer.echo(f"Version: {pv.version}")
    typer.echo(f"Created: {pv.created_at}")
    if pv.description:
        typer.echo(f"Description: {pv.description}")
    if pv.tags:
        typer.echo(f"Tags: {', '.join(pv.tags)}")
    typer.echo("---")
    typer.echo(pv.content)


@prompt_app.command("delete")
def prompt_delete(
    name: str = typer.Argument(..., help="Prompt name"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
) -> None:
    if not force:
        typer.confirm(f"Delete prompt '{name}' and all versions?", abort=True)
    store = _get_store()
    try:
        store.delete(name)
        typer.echo(f"Deleted prompt '{name}'")
    except ValueError as e:
        _exit(1, str(e))


@prompt_app.command("diff")
def prompt_diff(
    name: str = typer.Argument(..., help="Prompt name"),
    from_version: int = typer.Option(..., "--from", help="Source version"),
    to_version: int = typer.Option(..., "--to", help="Target version"),
) -> None:
    store = _get_store()
    try:
        pv_from = store.get(name, from_version)
        pv_to = store.get(name, to_version)
    except ValueError as e:
        msg = str(e)
        _exit(2 if "version" in msg else 1, msg)
        return
    diff = unified_diff(
        pv_from.content.splitlines(keepends=True),
        pv_to.content.splitlines(keepends=True),
        fromfile=f"v{from_version}",
        tofile=f"v{to_version}",
    )
    typer.echo("".join(diff))


@prompt_app.command("bind")
def prompt_bind(
    slot: str = typer.Option(..., "--slot", help="Gateway slot name"),
    prompt: str = typer.Option(..., "--prompt", help="Prompt name"),
    version: int = typer.Option(..., "--version", help="Prompt version"),
) -> None:
    store = _get_store()
    try:
        pb = store.bind(slot, prompt, version)
        typer.echo(f"Bound {slot} → {prompt}:v{pb.prompt_version}")
    except ValueError as e:
        _exit(1, str(e))


@prompt_app.command("unbind")
def prompt_unbind(
    slot: str = typer.Option(..., "--slot", help="Gateway slot name"),
) -> None:
    store = _get_store()
    try:
        store.unbind(slot)
        typer.echo(f"Unbound slot '{slot}'")
    except ValueError as e:
        _exit(1, str(e))


@prompt_app.command("bindings")
def prompt_bindings() -> None:
    store = _get_store()
    bs = store.bindings()
    table = Table(title="Active Bindings")
    table.add_column("Slot", style="cyan")
    table.add_column("Prompt", style="green")
    table.add_column("Version", style="white")
    for b in bs:
        table.add_row(b.slot, b.prompt_name, str(b.prompt_version))
    console.print(table)


@prompt_app.command("history")
def prompt_history(
    name: str = typer.Argument(..., help="Prompt name"),
) -> None:
    store = _get_store()
    try:
        latest = store.get_latest(name)
    except ValueError as e:
        _exit(1, str(e))
        return
    table = Table(title=f"History: {name}")
    table.add_column("Version", style="cyan")
    table.add_column("Content", style="white")
    table.add_column("Created", style="green")
    table.add_column("Tags", style="yellow")
    for v in range(1, latest.version + 1):
        pv = store.get(name, v)
        content_preview = pv.content[:60] + "..." if len(pv.content) > 60 else pv.content
        tags_str = ", ".join(pv.tags) if pv.tags else ""
        table.add_row(str(pv.version), content_preview, pv.created_at, tags_str)
    console.print(table)


@prompt_app.command("test")
def prompt_test(
    prompt: str = typer.Option(..., "--prompt", help="Prompt name"),
    versions: str = typer.Option(
        ..., "--versions", help="Comma-separated version numbers (e.g., 1,2)"
    ),
    benchmark: str = typer.Option("standard", "--benchmark", help="Benchmark dataset name"),
) -> None:
    store = _get_store()
    try:
        store.get_latest(prompt)
    except ValueError:
        _exit(1, f"Prompt '{prompt}' not found")
        return
    version_nums = [int(v.strip()) for v in versions.split(",")]
    for v in version_nums:
        try:
            store.get(prompt, v)
        except ValueError:
            _exit(2, f"Version {v} not found")
            return
    _exit(
        3,
        "A/B testing requires the benchmark harness (roadmap N-3). Configure a benchmark to proceed.",
    )


@prompt_app.command("export")
def prompt_export(
    name: str | None = typer.Argument(None, help="Prompt name (default: export all)"),
    output: str | None = typer.Option(None, "--output", help="Output file path (default: stdout)"),
) -> None:
    import yaml

    store = _get_store()
    try:
        data = store.export(name)
    except ValueError as e:
        _exit(1, str(e))
        return
    yaml_str = yaml.dump(data, default_flow_style=False)
    if output:
        Path(output).write_text(yaml_str)
        typer.echo(f"Exported to {output}")
    else:
        typer.echo(yaml_str)


@prompt_app.command("import")
def prompt_import(
    path: str = typer.Argument(..., help="YAML file path"),
) -> None:
    import yaml

    file_path = Path(path)
    if not file_path.exists():
        _exit(1, f"File not found: {path}")
        return
    try:
        data = yaml.safe_load(file_path.read_text())
    except Exception:
        _exit(2, "Invalid YAML format")
        return
    if isinstance(data, dict):
        data = [data]
    store = _get_store()
    for item in data:
        try:
            store.import_prompt(item)
            typer.echo(f"Imported prompt '{item['name']}'")
        except ValueError as e:
            _exit(1, str(e))
            return


@prompt_app.command("optimize")
def prompt_optimize(
    prompt: str = typer.Option(..., "--prompt", help="Prompt name"),
    benchmark: str = typer.Option("standard", "--benchmark", help="Benchmark dataset name"),
    iterations: int = typer.Option(5, "--iterations", help="Number of optimization iterations"),
) -> None:
    store = _get_store()
    if iterations < 1:
        _exit(3, "Iterations must be >= 1")
        return
    try:
        store.get_latest(prompt)
    except ValueError:
        _exit(1, f"Prompt '{prompt}' not found")
        return
    _exit(
        2,
        "GRPO optimization requires the benchmark harness (roadmap N-3). Configure a benchmark to proceed.",
    )
