import contextlib
import json
import logging
import re
import sys
import time
from datetime import UTC
from pathlib import Path
from typing import Any

import typer

from openreview_cli import __version__
from openreview_cli.config.auth import ensure_auth
from openreview_cli.config.loader import get_config_value, load_config, set_config_value
from openreview_cli.config.paths import get_config_dir, get_data_dir, get_log_dir
from openreview_cli.errors import config_error
from openreview_cli.storage.database import (
    add_client,
    client_has_reviews,
    delete_client,
    get_connection,
    init_database,
)

logger = logging.getLogger(__name__)

DEFAULT_CONFIDENCE_THRESHOLD: float = 0.7

# --no-tui: strip before Typer sees it (Typer/Click don't know about this flag)
_NO_TUI = "--no-tui" in sys.argv
if _NO_TUI:
    sys.argv = [a for a in sys.argv if a != "--no-tui"]

app = typer.Typer(
    name="openreview",
    help="Privacy-first contract review tool.",
    no_args_is_help=False,  # We handle no-args via TUI dispatch
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        _init()
        typer.echo(f"openreview {__version__}")
        raise typer.Exit()


def _validate_threshold(value: float | None) -> float | None:
    if value is not None and not 0.0 <= value <= 1.0:
        raise typer.BadParameter(f"confidence-threshold must be between 0.0 and 1.0, got {value}")
    return value


def _validate_enum(value: str, options: tuple[str, ...], name: str) -> None:
    """Validate a CLI option against an enum-like set of values."""
    if value not in options:
        joined = "', '".join(options)
        typer.echo(f"Error: --{name} must be '{joined}', got '{value}'", err=True)
        raise typer.Exit(code=2)


def _privacy_footer() -> str:
    """Build the privacy-tier footer for terminal reports."""
    from openreview_cli.config.loader import load_config
    from openreview_cli.config.paths import get_config_dir
    from openreview_cli.gateway.models import PrivacyTierReport
    from openreview_cli.gateway.tier_config import TierConfig
    from openreview_cli.gateway.tier_tracker import TierTracker

    _cfg = load_config(get_config_dir() / "config.yml")
    _tier_cfg = TierConfig.from_config(_cfg)

    _tracker = TierTracker()
    _msg = _tracker.check_and_record(_tier_cfg.tier)
    if _msg:
        logger.info(_msg)

    return PrivacyTierReport(tier=_tier_cfg.tier).report_footer()


def _export_memo_reports(
    reports: Any,
    memo_format: list[str],
    output_dir: str | None,
    mode: str = "precheck",
) -> None:
    """Export memo files for all reports in the requested formats.

    Args:
        reports: List of ReviewReport objects.
        memo_format: List of format strings (md, json, docx).
        output_dir: Optional output directory path.
        mode: Mode name used as filename prefix (e.g. "licensecheck").
    """
    from openreview_cli.review.memo.exporter import MemoExporter
    from openreview_cli.review.memo.models import MemoFormat

    # Validate formats
    fmt_set: set[MemoFormat] = set()
    for val in memo_format:
        try:
            fmt_set.add(MemoFormat(val))
        except ValueError:
            typer.echo(
                f"Error: Unsupported export format: {val}. Supported formats: md, json, docx.",
                err=True,
            )
            raise typer.Exit(code=2) from None

    if not fmt_set:
        return

    out = Path(output_dir) if output_dir else Path("review_results")

    exported_paths: list[str] = []
    for report in reports:
        try:
            exporter = MemoExporter(
                report=report,
                mode=mode,
                output_dir=out,
                formats=fmt_set,
            )
            result = exporter.export()
            for path in result.values():
                exported_paths.append(str(path))
        except ValueError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(code=1) from None
        except Exception as e:
            typer.echo(f"Warning: Memo export failed: {e}", err=True)

    if exported_paths:
        if len(exported_paths) == 1:
            typer.echo(f"  Memo exported to: {exported_paths[0]}")
        else:
            typer.echo("  Memo exported to:")
            for p in exported_paths:
                typer.echo(f"    - {p}")


def _emit_reviews(
    reports: list[Any],
    format: str,
    output: str | None,
    privacy_footer_ref: str | None,
    memo_format: list[str],
    output_dir: str | None,
    mode: str = "precheck",
) -> None:
    """Shared post-processing: format output, export memos, emit amber warning."""
    from openreview_cli.review import format_json, format_terminal

    if not reports:
        typer.echo("No documents processed.", err=True)
        raise typer.Exit(code=1)

    if format == "json":
        output_str = format_json(reports)
        if output:
            Path(output).write_text(output_str, encoding="utf-8")
        else:
            typer.echo(output_str)
    else:
        for report in reports:
            typer.echo(format_terminal(report, privacy_footer=privacy_footer_ref))

    if memo_format:
        _export_memo_reports(reports, memo_format, output_dir, mode=mode)

    if any(r.summary.amber_count > 0 for r in reports):
        typer.echo("⚠  Some clauses flagged Amber — review recommended.", err=True)


def _init(debug: bool = False) -> None:
    log_dir = get_log_dir()
    log_file = log_dir / "openreview.log"
    log_dir.mkdir(parents=True, exist_ok=True)
    _level = logging.DEBUG if debug else logging.INFO
    _fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    root = logging.getLogger()
    root.setLevel(_level)
    root.addHandler(logging.FileHandler(log_file, encoding="utf-8"))
    _sh = logging.StreamHandler(sys.stderr)
    _sh.setFormatter(_fmt)
    root.addHandler(_sh)

    config_dir = get_config_dir()
    config = load_config(config_dir / "config.yml")
    logger.info("config loaded")

    ensure_auth(config_dir)
    logger.info("auth configured")

    data_dir = get_data_dir()
    init_database(data_dir / "openreview.db")
    logger.info("database initialized")

    _cleanup_expired_pii(data_dir)
    _refresh_model_registry(config)


_GATEWAY_REGISTRY_PATH = Path(__file__).parent / "gateway" / "models.json"


def _refresh_model_registry(config: dict[str, object] | None) -> None:
    try:
        from openreview_cli.gateway.registry import ModelRegistry

        days = 0
        if config:
            days = config.get("gateway", {}).get("model_registry_refresh_days", 0)  # type: ignore[attr-defined]
        if not days:
            return
        reg_path = _GATEWAY_REGISTRY_PATH
        if not reg_path.exists():
            return
        registry = ModelRegistry(reg_path)
        registry.load()
        import time

        age_seconds = time.time() - reg_path.stat().st_mtime
        if age_seconds >= days * 86400:
            url = "https://raw.githubusercontent.com/mohamed-benoughidene/openreview/main/src/openreview_cli/gateway/models.json"
            count = registry.refresh(url)
            logger.info("model registry refreshed (%d models)", count)
    except Exception:
        logger.debug("model registry refresh skipped", exc_info=True)


def _cleanup_expired_pii(data_dir: Path) -> None:
    """Best-effort cleanup of expired PII mappings on CLI startup."""
    try:
        from openreview_cli.pii.retention import cleanup_expired

        deleted = cleanup_expired(data_dir / "openreview.db")
        if deleted:
            logger.info("cleaned up %d expired PII entries", deleted)
    except Exception:
        logger.debug("PII cleanup skipped", exc_info=True)


def _resolve_doc_id(file_path: Path) -> str:
    """Load a .ndax JSON file and extract the document_id (or SHA-256 fallback)."""
    import json

    with open(file_path) as f:
        chunks_data = json.load(f)
    doc_id = chunks_data[0].get("document_id", "") if chunks_data else ""
    if not doc_id:
        import hashlib

        doc_id = hashlib.sha256(file_path.read_bytes()).hexdigest()
    return doc_id


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the openreview version and exit.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug-level logging.",
    ),
) -> None:
    _init(debug=debug)

    # If a subcommand was invoked, let it proceed normally
    if ctx.invoked_subcommand is not None:
        return

    # No subcommand — TUI or friendly message
    if _NO_TUI:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)

    # Delegate to launcher: handles TTY check internally (stderr msg + sys.exit if non-TTY)
    from openreview_cli.tui.launcher import launch_tui

    launch_tui()
    raise typer.Exit(0)


client_app = typer.Typer(
    name="client",
    help="Manage clients.",
    no_args_is_help=True,
)


@client_app.command("add")
def client_add(id: str, name: str) -> None:
    db_path = get_data_dir() / "openreview.db"
    try:
        add_client(db_path, id, name)
        typer.echo(f"added client {id}")
    except Exception as e:
        config_error(str(e))


@client_app.command("list")
def client_list() -> None:
    from rich.console import Console
    from rich.table import Table

    db_path = get_data_dir() / "openreview.db"
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT id, name, created_at, updated_at FROM clients ORDER BY created_at"
        ).fetchall()
    finally:
        conn.close()

    console = Console()
    table = Table(title="Clients")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Created", style="white")
    table.add_column("Updated", style="white")
    for row in rows:
        table.add_row(row["id"], row["name"], row["created_at"], row["updated_at"])
    console.print(table)


@client_app.command("delete")
def client_delete(
    id: str,
    force: bool = typer.Option(False, "--force", help="Delete client and all associated reviews."),
) -> None:
    db_path = get_data_dir() / "openreview.db"
    if not force and client_has_reviews(db_path, id):
        config_error(f"client {id} has reviews; use --force to delete")
    if not delete_client(db_path, id, force=force):
        config_error(f"client {id} not found")
    typer.echo(f"deleted client {id}")


app.add_typer(client_app)

config_app = typer.Typer(
    name="config",
    help="View and modify configuration.",
    no_args_is_help=True,
)


@config_app.command("show")
def config_show() -> None:
    from rich.console import Console
    from rich.table import Table

    config_path = get_config_dir() / "config.yml"
    config = load_config(config_path)

    console = Console()
    table = Table(title="OpenReview Configuration")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")

    def _flatten(d: dict[str, object], prefix: str = "") -> None:
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                _flatten(v, key)
            else:
                table.add_row(key, str(v))

    _flatten(config)
    console.print(table)


@config_app.command("get")
def config_get(key: str) -> None:
    config_path = get_config_dir() / "config.yml"
    config = load_config(config_path)

    try:
        value = get_config_value(config, key)
        typer.echo(str(value))
    except KeyError:
        config_error(f"Unknown config key: {key}")


@config_app.command("set")
def config_set(key: str, value: str) -> None:
    from pydantic import ValidationError

    config_path = get_config_dir() / "config.yml"

    try:
        set_config_value(config_path, key, value)
        typer.echo(f"updated {key} = {value}")
    except (KeyError, ValidationError) as e:
        config_error(str(e))


app.add_typer(config_app)


pii_app = typer.Typer(
    name="pii",
    help="Manage PII data (encrypted mappings, audit trails, cache).",
    no_args_is_help=True,
)


@pii_app.command("list")
def pii_list(
    format: str = typer.Option("text", "--format", help="Output format: text, json"),
) -> None:
    import sqlite3

    from openreview_cli.config.paths import get_data_dir

    db_path = get_data_dir() / "openreview.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT pc.document_hash, pc.created_at, pc.expiry_at, "
            "COALESCE(pat.entity_count, 0) as entity_count, "
            "pc.mapping_path "
            "FROM pii_cache pc "
            "LEFT JOIN (SELECT document_hash, entity_count, MAX(timestamp) as max_ts "
            "FROM pii_audit_trail GROUP BY document_hash) pat "
            "ON pc.document_hash = pat.document_hash "
            "ORDER BY pc.created_at DESC"
        ).fetchall()
    finally:
        conn.close()

    if format == "json":
        import json

        typer.echo(json.dumps([dict(r) for r in rows], indent=2, default=str))
        return

    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Documents with PII data")
    table.add_column("Document Hash", style="cyan")
    table.add_column("Entities", style="green")
    table.add_column("Created", style="white")
    table.add_column("Expires", style="white")
    table.add_column("Mapping", style="dim")

    for row in rows:
        table.add_row(
            row["document_hash"][:12],
            str(row["entity_count"]),
            row["created_at"] or "",
            row["expiry_at"] or "",
            row["mapping_path"] or "",
        )
    console.print(table)


@pii_app.command("delete")
def pii_delete(
    document_hash: str = typer.Argument(..., help="Document hash (or prefix, min 8 chars)"),
) -> None:
    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.pii.retention import delete_pii_data

    db_path = get_data_dir() / "openreview.db"
    result = delete_pii_data(db_path, document_hash)
    if result["mapping_removed"]:
        typer.echo(f"Deleted PII data for document hash: {document_hash}")
        typer.echo("  - Encrypted mapping: removed")
        typer.echo(f"  - Audit trail: removed ({result['audit_records']} records)")
        typer.echo("  - Cache entry: removed")
    else:
        typer.echo(f"No PII data found for document hash: {document_hash}")


@pii_app.command("cleanup")
def pii_cleanup(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deleted"),
) -> None:
    import sqlite3

    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.pii.retention import cleanup_expired

    db_path = get_data_dir() / "openreview.db"
    if dry_run:
        from datetime import datetime

        now = datetime.now(UTC).isoformat()
        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute(
                "SELECT document_hash, mapping_path FROM pii_cache WHERE expiry_at < ?",
                (now,),
            ).fetchall()
        finally:
            conn.close()
        typer.echo(f"Dry run: {len(rows)} expired entries would be deleted")
        return

    deleted = cleanup_expired(db_path)
    typer.echo(f"Cleanup complete: {deleted} expired entries deleted")


app.add_typer(pii_app)

playbook_app = typer.Typer(
    name="playbook",
    help="Manage versioned playbooks in the local database.",
    no_args_is_help=True,
)


@playbook_app.command("import")
def playbook_import(
    yaml_path: str = typer.Argument(..., help="Path to YAML playbook file"),
) -> None:
    """Import a YAML playbook into the local database.

    Parses the YAML playbook, validates it, and saves it as a new append-only version.
    Returns the playbook ID and version number.
    """
    import json
    from dataclasses import asdict

    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.review.playbook import load_playbook
    from openreview_cli.storage.database import import_playbook_yaml

    path = Path(yaml_path)
    if not path.exists():
        typer.echo(f"Error: File not found: {yaml_path}", err=True)
        raise typer.Exit(code=2)

    try:
        playbook = load_playbook(path)
    except Exception as e:
        typer.echo(f"Error: Invalid playbook: {e}", err=True)
        raise typer.Exit(code=2) from None

    db_path = get_data_dir() / "openreview.db"
    content = json.dumps(asdict(playbook))
    try:
        next_ver, prev_version = import_playbook_yaml(db_path, playbook.id, content)
    except Exception as e:
        typer.echo(f"Error: Failed to save playbook: {e}", err=True)
        raise typer.Exit(code=1) from None

    msg = f"Imported playbook '{playbook.id}' as version {next_ver}."
    if prev_version is not None:
        msg += f" (previous version: {prev_version})."
    typer.echo(msg)


@playbook_app.command("list")
def playbook_list(
    include_deleted: bool = typer.Option(
        False, "--include-deleted", help="Include soft-deleted playbooks."
    ),
) -> None:
    """List all playbooks in the local database.

    Displays a table with playbook ID, description, latest version, current version, and import date.
    """
    import json as _json

    from rich.console import Console
    from rich.table import Table

    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.storage.database import (
        get_current_version,
        get_playbook_version,
        list_playbooks_with_meta,
    )

    db_path = get_data_dir() / "openreview.db"
    try:
        playbooks = list_playbooks_with_meta(db_path, include_deleted=include_deleted)
    except Exception as e:
        typer.echo(f"Error: Database error: {e}", err=True)
        raise typer.Exit(code=1) from None

    if not playbooks:
        typer.echo("No playbooks saved yet.")
        return

    console = Console()
    table = Table(title="Playbooks")
    table.add_column("ID", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Latest", style="yellow", justify="right")
    table.add_column("Current", style="blue", justify="right")
    table.add_column("Imported", style="white")

    for pb_id, version, created_at, is_deleted in playbooks:
        # Try to extract description from the latest version's content
        desc = ""
        try:
            content = get_playbook_version(db_path, pb_id, version)
            if content:
                parsed = _json.loads(content)
                desc = parsed.get("metadata", {}).get("description", "")
        except Exception:
            pass

        # Get current version
        cur_ver = ""
        with contextlib.suppress(Exception):
            cur_ver = str(get_current_version(db_path, pb_id))

        cur_display = f"[green]{cur_ver} ←[/green]" if cur_ver == str(version) else cur_ver

        label = ""
        if is_deleted:
            label = " [red](deleted)[/red]"

        # Format date as YYYY-MM-DD
        date_str = created_at[:10] if created_at else ""
        table.add_row(f"{pb_id}{label}", desc, str(version), cur_display, date_str)

    console.print(table)


@playbook_app.command("show")
def playbook_show(
    playbook_id: str = typer.Argument(..., help="Playbook ID"),
    version: int = typer.Argument(..., help="Version number"),
) -> None:
    """Show a specific playbook version from the database.

    Displays full playbook contents including all categories and their
    position definitions.
    """
    import json as _json

    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.storage.database import get_playbook_version

    if version < 1:
        typer.echo("Error: Version must be a positive integer.", err=True)
        raise typer.Exit(code=2)

    db_path = get_data_dir() / "openreview.db"
    try:
        content = get_playbook_version(db_path, playbook_id, version)
    except Exception as e:
        typer.echo(f"Error: Database error: {e}", err=True)
        raise typer.Exit(code=1) from None

    if content is None:
        # Check if playbook_id exists at all
        from openreview_cli.storage.database import list_playbooks

        all_pbs = list_playbooks(db_path)
        ids = {pb[0] for pb in all_pbs}
        if playbook_id not in ids:
            typer.echo(f"Error: Playbook '{playbook_id}' not found.", err=True)
        else:
            typer.echo(
                f"Error: Version {version} not found for playbook '{playbook_id}'.",
                err=True,
            )
        raise typer.Exit(code=2)

    # Parse and display
    try:
        parsed = _json.loads(content)
    except _json.JSONDecodeError as e:
        typer.echo(f"Error: Corrupt playbook data: {e}", err=True)
        raise typer.Exit(code=1) from None

    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    meta = parsed.get("metadata", {})
    header = f"Playbook: {playbook_id} (version {version})"
    lines = [f"Mode: {parsed.get('mode', '?')}"]
    lines.append(f"Description: {meta.get('description', '')}")
    lines.append(f"Author: {meta.get('author', '')}")
    lines.append(f"Created: {meta.get('version', '')}")

    console.print()
    console.print(Panel.fit("\n".join(lines), title=header))
    console.print()

    categories = parsed.get("categories", [])
    if categories:
        console.print("[bold]Categories:[/bold]")
        console.print()
        for i, cat in enumerate(categories, 1):
            cat_id = cat.get("id", "?")
            cat_name = cat.get("name", "")
            default_pos = cat.get("default_position", "preferred")
            console.print(f"  [cyan]{i}.[/cyan] [bold]{cat_id}[/bold] — {cat_name}")
            console.print(f"     Default: {default_pos}")

            for pos_name in ("preferred", "acceptable", "walkaway"):
                pos = cat.get(pos_name, {})
                desc = pos.get("description", "")
                exemplars = pos.get("exemplars", [])
                console.print(f"     [green]{pos_name.title()}[/green]: {desc}")
                if exemplars:
                    for ex in exemplars:
                        console.print(f"       • {ex}")
            console.print()


@playbook_app.command("export")
def playbook_export(
    playbook_id: str = typer.Argument(None, help="Saved playbook identifier (omit with --all)"),
    version: int | None = typer.Option(
        None, "--version", help="Version to export (default: current/latest)"
    ),
    output: str | None = typer.Option(
        None, "--output", help="Destination file path (or directory with --all)"
    ),
    force: bool = typer.Option(False, "--force", help="Suppress overwrite warning"),
    all_flag: bool = typer.Option(False, "--all", help="Export all playbooks"),
) -> None:
    """Export a playbook version from the database to a YAML file."""
    import json

    import yaml

    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.storage.database import export_playbook_version, list_playbooks

    db_path = get_data_dir() / "openreview.db"

    # Bulk export all playbooks
    if all_flag:
        out_dir = Path(output) if output else Path.cwd()
        out_dir.mkdir(parents=True, exist_ok=True)

        playbooks = list_playbooks(db_path)
        if not playbooks:
            typer.echo("No playbooks to export.")
            return

        count = 0
        for pb_id, _ver, _created in playbooks:
            content = export_playbook_version(db_path, pb_id)
            if content is None:
                continue
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                continue
            yaml_str = yaml.safe_dump(
                data, sort_keys=False, allow_unicode=True, default_flow_style=False
            )
            out_path = out_dir / f"{pb_id}.yaml"
            out_path.write_text(yaml_str, encoding="utf-8")
            count += 1

        typer.echo(f"Exported {count} playbook(s) to '{out_dir}'.")
        return

    # Single-playbook export
    if not playbook_id:
        typer.echo("Error: Either PLAYBOOK_ID or --all is required.", err=True)
        raise typer.Exit(code=2)

    if not output:
        typer.echo("Error: --output is required for single export.", err=True)
        raise typer.Exit(code=2)

    out_path = Path(output)

    # Validate output parent directory exists
    if not out_path.parent.exists():
        typer.echo(
            f"Error: Cannot write to '{output}': parent directory does not exist.",
            err=True,
        )
        raise typer.Exit(code=1)

    # Fetch version data
    try:
        content = export_playbook_version(db_path, playbook_id, version)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None

    if content is None:
        resolved_ver = version if version else 0
        typer.echo(
            f"Error: Version {resolved_ver} not found for playbook '{playbook_id}'.",
            err=True,
        )
        raise typer.Exit(code=1)

    # Parse JSON content to dict
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        typer.echo(f"Error: Corrupt playbook data: {e}", err=True)
        raise typer.Exit(code=1) from None

    # Serialize to YAML
    try:
        yaml_str = yaml.safe_dump(
            data, sort_keys=False, allow_unicode=True, default_flow_style=False
        )
    except Exception as e:
        typer.echo(f"Error: YAML serialisation failed: {e}", err=True)
        raise typer.Exit(code=1) from None

    # Write with overwrite warning
    if out_path.exists() and not force:
        typer.echo(f"Warning: Overwriting existing file '{output}'.", err=True)

    out_path.write_text(yaml_str, encoding="utf-8")
    typer.echo(f"Exported playbook '{playbook_id}' to '{output}'.")


@playbook_app.command("diff")
def playbook_diff(
    playbook_id: str = typer.Argument(..., help="Saved playbook identifier"),
    v1: int = typer.Argument(..., help="First version to compare"),
    v2: int = typer.Argument(..., help="Second version to compare"),
    json_output: bool = typer.Option(False, "--json", help="Output diff as JSON"),
) -> None:
    """Compare two versions of a saved playbook structurally."""
    import dataclasses
    import json as stdlib_json

    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.review.playbook import compute_playbook_diff
    from openreview_cli.storage.database import diff_playbook_versions

    if v1 < 1 or v2 < 1:
        typer.echo("Error: Versions must be positive integers.", err=True)
        raise typer.Exit(code=2)

    db_path = get_data_dir() / "openreview.db"

    # Fetch version data (handles normalisation v1 > v2)
    try:
        data1, data2, norm_v1, norm_v2 = diff_playbook_versions(db_path, playbook_id, v1, v2)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None

    # Compute diff
    diff = compute_playbook_diff(data1, data2)
    diff.v1 = norm_v1
    diff.v2 = norm_v2

    # JSON output
    if json_output:
        d = dataclasses.asdict(diff)
        typer.echo(stdlib_json.dumps(d, indent=2))
        return

    # Format and display (inline format_playbook_diff)
    lines: list[str] = []
    lines.append(f"Changes between version {diff.v1} and {diff.v2} of {playbook_id}:")
    lines.append("")

    if diff.added_categories:
        lines.append("New categories:")
        for cid in diff.added_categories:
            lines.append(f"  - {cid}")
        lines.append("")

    if diff.removed_categories:
        lines.append("Removed categories:")
        for cid in diff.removed_categories:
            lines.append(f"  - {cid}")
        lines.append("")

    if diff.changed_categories:
        lines.append("Changed categories:")
        for cid, changes in diff.changed_categories.items():
            lines.append(f"  {cid}:")
            desc = changes.get("description")
            if isinstance(desc, dict):
                lines.append(
                    f'    description: "{desc.get("before", "")}" \u2192 "{desc.get("after", "")}"'
                )
            dp = changes.get("default_position")
            if isinstance(dp, dict):
                lines.append(
                    f'    default_position: "{dp.get("before", "")}" \u2192 "{dp.get("after", "")}"'
                )
            for ex in changes.get("exemplars_added", []):
                lines.append(f'    exemplar added: "{ex}"')
            for ex in changes.get("exemplars_removed", []):
                lines.append(f'    exemplar removed: "{ex}"')
        lines.append("")

    if not diff.added_categories and not diff.removed_categories and not diff.changed_categories:
        lines.append(f"No changes between version {diff.v1} and version {diff.v2}.")
        lines.append("")

    typer.echo("\n".join(lines))


@playbook_app.command("set-current")
def playbook_set_current(
    playbook_id: str = typer.Argument(..., help="Saved playbook identifier"),
    version: int = typer.Argument(..., help="Version number to set as current"),
) -> None:
    """Set the effective current version for a playbook.

    Re-activates a deleted playbook if it was soft-deleted.
    """
    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.storage.database import set_current_version

    if version < 1:
        typer.echo("Error: Version must be a positive integer.", err=True)
        raise typer.Exit(code=2)

    db_path = get_data_dir() / "openreview.db"
    try:
        _, msg = set_current_version(db_path, playbook_id, version)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(msg)


@playbook_app.command("delete")
def playbook_delete(
    playbook_id: str = typer.Argument(None, help="Saved playbook identifier (omit with --all)"),
    all_flag: bool = typer.Option(False, "--all", help="Delete ALL playbooks"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompt"),
) -> None:
    """Soft-delete a playbook (tombstone, never hard-delete).

    Removes from default list view. Restorable via set-current or undelete.
    """
    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.storage.database import delete_playbook, list_playbooks

    db_path = get_data_dir() / "openreview.db"

    # Bulk delete all playbooks
    if all_flag:
        playbooks = list_playbooks(db_path)

        if not force:
            from rich.prompt import Confirm

            confirmed = Confirm.ask(
                f"Delete all {len(playbooks)} playbook(s)? This cannot be undone."
            )
            if not confirmed:
                typer.echo("Cancelled.")
                raise typer.Exit(code=0)

        count = 0
        for pb_id, _ver, _created in playbooks:
            try:
                delete_playbook(db_path, pb_id)
                count += 1
            except ValueError:
                continue

        typer.echo(f"Deleted {count} playbook(s).")
        return

    # Single-playbook delete
    if not playbook_id:
        typer.echo("Error: Either PLAYBOOK_ID or --all is required.", err=True)
        raise typer.Exit(code=2)

    try:
        _, msg = delete_playbook(db_path, playbook_id)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(msg)


@playbook_app.command("undelete")
def playbook_undelete(
    playbook_id: str = typer.Argument(..., help="Saved playbook identifier to restore"),
) -> None:
    """Restore a soft-deleted playbook.

    Clears the deleted_at tombstone so the playbook reappears in listings.
    """
    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.storage.database import (
        get_current_version,
        list_playbooks_with_meta,
        set_current_version,
    )

    db_path = get_data_dir() / "openreview.db"

    # Find the soft-deleted playbook
    playbooks = list_playbooks_with_meta(db_path, include_deleted=True)
    matching = [
        (pid, ver) for pid, ver, _ca, deleted in playbooks if pid == playbook_id and deleted
    ]
    if not matching:
        typer.echo(
            f"Error: Playbook '{playbook_id}' not found or is not deleted.",
            err=True,
        )
        raise typer.Exit(code=1)

    current_ver = get_current_version(db_path, playbook_id)
    try:
        set_current_version(db_path, playbook_id, current_ver)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(f"Undeleted playbook '{playbook_id}' (version {current_ver}).")


@playbook_app.command("history")
def playbook_history(
    playbook_id: str = typer.Argument(..., help="Saved playbook identifier"),
) -> None:
    """Show version timeline of a playbook.

    Displays a Rich table with Version, Created, and Status columns.
    """
    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.storage.database import get_playbook_history

    db_path = get_data_dir() / "openreview.db"
    try:
        rows, _current_version, is_deleted = get_playbook_history(db_path, playbook_id)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None

    if not rows:
        typer.echo(f"No versions found for playbook '{playbook_id}'.")
        return

    from rich.console import Console
    from rich.table import Table

    console = Console()
    title = f"Version History: {playbook_id}"
    header = "(deleted)" if is_deleted else ""
    if header:
        title += f" [red]{header}[/red]"
    table = Table(title=title)
    table.add_column("Version", style="cyan", justify="right")
    table.add_column("Created", style="white")
    table.add_column("Status", style="yellow")

    for r in rows:
        ver = r["version"]
        created = str(r["created_at"])
        status_parts = []
        if r["is_current"]:
            status_parts.append("[green]Current[/green]")
        if r["is_latest"]:
            status_parts.append("[blue]Latest[/blue]")
        table.add_row(str(ver), created, "  ".join(status_parts))

    console.print(table)


app.add_typer(playbook_app)


precheck_app = typer.Typer(
    name="precheck",
    help="PreCheck contract review commands.",
    no_args_is_help=True,
)


@precheck_app.callback(invoke_without_command=True)
def precheck(
    ctx: typer.Context,
    document_path: str | None = typer.Option(
        None, "--document", "-d", help="Path to a PDF or DOCX contract file."
    ),
    no_pii: bool = typer.Option(
        False, "--no-pii", help="Disable PII stripping. Processes raw text."
    ),
    pii_threshold: float | None = typer.Option(
        None, "--pii-threshold", help="PII detection confidence threshold (0.0 to 1.0)."
    ),
    output: str | None = typer.Option(
        None, "--output", help="Output directory for review results."
    ),
    format: str = typer.Option("text", "--format", help="Output format: text, json."),
    force_reprocess: bool = typer.Option(
        False, "--force-reprocess", help="Force re-processing even if cached."
    ),
    dual_path: bool = typer.Option(
        False,
        "--dual-path",
        help="Enable dual-path: call providers in parallel, pick first success.",
    ),
) -> None:
    """Run a PreCheck review (NDA analysis) on a document.

    Automatically strips PII before processing unless --no-pii is specified.
    Use 'openreview precheck review' for the full 3-agent review pipeline.
    """
    if ctx.invoked_subcommand is not None:
        return

    from openreview_cli.pii.models import PartialProcessingError
    from openreview_cli.review.base import ReviewCommand

    if no_pii and pii_threshold is not None:
        typer.echo("Error: --no-pii and --pii-threshold are mutually exclusive", err=True)
        raise typer.Exit(code=3)

    if not document_path:
        typer.echo("Error: missing document path argument.", err=True)
        raise typer.Exit(code=1)

    cmd = ReviewCommand(
        document_path=document_path,
        pii_enabled=not no_pii,
        threshold=pii_threshold,
        output_dir=output,
        force_reprocess=force_reprocess,
    )

    try:
        result = cmd.run()
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None
    except PartialProcessingError as e:
        typer.echo(f"Partial PII processing: {e}", err=True)
        raise typer.Exit(code=2) from None
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None

    if no_pii:
        typer.echo("Warning: PII stripping disabled. Raw text processed.", err=True)

    typer.echo(f"Review memo generated: {result['result_path']}")
    typer.echo(f"Document hash: {result['document_hash'][:12]}")
    if result["failed_pages"]:
        typer.echo(f"Failed pages: {result['failed_pages']}", err=True)
        raise typer.Exit(code=2)


@precheck_app.command()
def review(
    paths: list[str] = typer.Argument(
        ..., help="One or more document paths (PDF, DOCX). Shell glob supported."
    ),
    playbook_path: str | None = typer.Option(
        None, "--playbook-path", help="Path to a custom YAML playbook override."
    ),
    playbook: str | None = typer.Option(
        None, "--playbook", help="Playbook ID to load from database."
    ),
    format: str = typer.Option("text", "--format", help="Output format: text or json."),
    output: str | None = typer.Option(
        None, "--output", help="Write output to file instead of stdout."
    ),
    memo_format: list[str] = typer.Option(
        [],
        "--memo-format",
        help="Export format(s) for the review memo. "
        "Supported values: md (Markdown), json (JSON), docx (Word document). "
        "May be specified multiple times to produce multiple formats in one run.",
    ),
    output_dir: str | None = typer.Option(
        None,
        "--output-dir",
        help="Directory where memo files are written. "
        "Created automatically if it does not exist. "
        "Defaults to review_results/ in the current working directory.",
        envvar="OPENREVIEW_OUTPUT_DIR",
    ),
    extraction_model: str | None = typer.Option(
        None, "--extraction-model", help="Model slot for the extraction agent."
    ),
    qa_model: str | None = typer.Option(
        None, "--qa-model", help="Model slot for the QA verification agent."
    ),
    no_pii: bool = typer.Option(False, "--no-pii", help="Skip PII stripping."),
    verbose: bool = typer.Option(False, "--verbose", help="Show per-clause progress."),
    grounding_mode: str | None = typer.Option(
        "strict",
        "--grounding-mode",
        help="Citation grounding mode: strict (ungrounded excluded) or lenient (flagged).",
    ),
    no_grounding: bool = typer.Option(
        False, "--no-grounding", help="Skip citation grounding entirely."
    ),
    confidence_threshold: float = typer.Option(
        DEFAULT_CONFIDENCE_THRESHOLD,
        "--confidence-threshold",
        "-ct",
        help="Confidence threshold for Green/Amber/Red assignment (0.0-1.0). "
        "Clauses with effective confidence below this threshold are marked Amber. "
        "Note: The comparison accuracy of automated review is bounded by "
        "approximately 64% F1. Three-color output (Green/Amber/Red) is "
        "designed to mitigate this — set the threshold generously to push "
        "uncertain comparisons to Amber rather than risking false Green or Red.",
        callback=_validate_threshold,
    ),
    dual_path: bool = typer.Option(
        False,
        "--dual-path",
        help="Enable dual-path: call providers in parallel, pick first success.",
    ),
) -> None:
    """Review one or more contract documents against a 3-position playbook.

    Runs the PAKTON 3-agent pipeline: extraction, QA verification, and
    comparison (no-op). Produces a per-clause structured report with
    position assessments, confidence scores, and citation grounding.
    """
    # Validate grounding mode
    if grounding_mode not in ("strict", "lenient"):
        typer.echo(
            f"Error: --grounding-mode must be 'strict' or 'lenient', got '{grounding_mode}'",
            err=True,
        )
        raise typer.Exit(code=1)

    from openreview_cli.review import run_review

    try:
        reports = run_review(
            paths=paths,
            playbook_path=playbook_path,
            playbook_id=playbook,
            extraction_model=extraction_model or "extraction",
            qa_model=qa_model,
            no_pii=no_pii,
            verbose=verbose,
            grounding_mode=None if no_grounding else grounding_mode,
            confidence_threshold=confidence_threshold,
            mode="precheck",
            dual_path=dual_path,
        )
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2) from None

    _emit_reviews(reports, format, output, _privacy_footer(), memo_format, output_dir)
    typer.echo("Costs: see `openreview gateway costs --today`")


app.add_typer(precheck_app)


@app.command()
def parse(
    path: str = typer.Argument(..., help="Path to a PDF or DOCX contract file."),
    format: str = typer.Option("text", "--format", help="Output format: text, json"),
    summary: bool = typer.Option(False, "--summary", help="Show one-line summary only"),
) -> None:
    from openreview_cli.parsing.models import ParseError
    from openreview_cli.parsing.stream import (
        format_json,
        format_summary,
        format_text,
        parse_document,
    )

    try:
        doc, clauses = parse_document(path)
    except ParseError as e:
        typer.echo(f"Error: {e.message}", err=True)
        typer.echo(f"What to do: {e.action}", err=True)
        raise typer.Exit(code=8) from None

    if summary:
        typer.echo(format_summary(doc))
    elif format == "json":
        typer.echo(format_json(clauses))
    else:
        typer.echo(format_text(clauses, doc))


gateway_app = typer.Typer(
    name="gateway",
    help="Configure and manage AI provider gateways.",
    no_args_is_help=True,
)

provider_app = typer.Typer(
    name="provider",
    help="Manage custom providers.",
    no_args_is_help=True,
)


@gateway_app.command("setup")
def gateway_setup() -> None:
    """Interactive setup wizard for provider and model configuration."""
    from openreview_cli.gateway.wizard import gateway_setup as _wizard

    _wizard()


@gateway_app.command("status")
def gateway_status() -> None:
    """Show configured slots and provider reachability."""
    from rich.console import Console
    from rich.table import Table

    from openreview_cli.gateway.router import Gateway

    gw = Gateway()
    status = gw.health_check()

    console = Console()
    table = Table(title="Gateway Status")
    table.add_column("Slot", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Provider", style="yellow")

    for slot, info in status.items():
        table.add_row(slot, info.get("status", "unknown"), info.get("provider", "-"))
    console.print(table)


@gateway_app.command("providers")
def gateway_providers(json_mode: bool = typer.Option(False, "--json")) -> None:
    """List all supported providers (bundled + custom)."""
    from openreview_cli.config.auth import load_auth
    from openreview_cli.config.paths import get_config_dir
    from openreview_cli.gateway.registry import load_registry, provider_credential_status

    registry = load_registry()
    auth = load_auth(get_config_dir() / "auth.json")

    if json_mode:
        data = {
            "providers": [
                {
                    "name": p.name,
                    "base_url": p.base_url,
                    "api_key_env": p.env_key,
                    "capabilities": p.capabilities.model_dump(),
                    "is_local": p.is_local,
                    "source": p.source,
                    "configured": status["configured"],
                    "credentials": status["credentials"],
                }
                for p in registry.values()
                if (status := provider_credential_status(p, auth))
            ]
        }
        typer.echo(json.dumps(data, indent=2))
        return

    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Supported Providers")
    table.add_column("Name", style="cyan")
    table.add_column("Auth", style="green")
    table.add_column("Models", style="white")

    for p in registry.values():
        table.add_row(
            p.name,
            "key required" if p.auth_required else "none",
            str(len(p.models)),
        )
    console.print(table)


@gateway_app.command("models")
def gateway_models(
    provider: str,
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """List available models for a provider."""
    from openreview_cli.gateway.registry import load_registry

    registry = load_registry()
    p = registry.get(provider)
    if p is None:
        typer.echo(f"No provider '{provider}' found.", err=True)
        raise typer.Exit(code=1)

    if json_mode:
        data = {
            provider: [
                {
                    "id": mid,
                    "capabilities": (
                        m.capabilities.model_dump() if hasattr(m, "capabilities") else {}
                    ),
                    "slots": m.slots,
                    "context": m.context,
                    "dimensions": m.dimensions,
                    "recommended": m.recommended,
                    "status": m.status,
                    "note": m.note,
                }
                for mid, m in p.models.items()
            ]
        }
        typer.echo(json.dumps(data, indent=2))
        return

    from rich.console import Console
    from rich.table import Table

    if not p.models:
        typer.echo(f"No models found for provider '{provider}'.")
        return

    console = Console()
    table = Table(title=f"Models for {provider}")
    table.add_column("Model ID", style="cyan")
    table.add_column("Slots", style="green")
    table.add_column("Context", style="white")
    table.add_column("Recommended", style="yellow")

    for mid, m in p.models.items():
        table.add_row(
            mid,
            ", ".join(m.slots),
            str(m.context if m.context is not None else "-"),
            "✓" if m.recommended else "",
        )
    console.print(table)


@gateway_app.command("set")
def gateway_set(slot: str, model: str) -> None:
    """Assign a model to a slot."""
    from openreview_cli.config.loader import set_config_value
    from openreview_cli.config.paths import get_config_dir
    from openreview_cli.slots import VALID_SLOTS

    if slot not in VALID_SLOTS:
        typer.echo(
            f"Invalid slot '{slot}'. Valid slots: {', '.join(sorted(VALID_SLOTS))}",
            err=True,
        )
        raise typer.Exit(code=1)

    config_path = get_config_dir() / "config.yml"
    try:
        set_config_value(config_path, f"gateway.models.{slot}.primary", model)
        typer.echo(f"Set {slot} → {model}")
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None


@gateway_app.command("refresh")
def gateway_refresh() -> None:
    """Refresh model registry from remote."""
    from openreview_cli.gateway.registry import ModelRegistry

    registry = ModelRegistry(_GATEWAY_REGISTRY_PATH)
    url = "https://raw.githubusercontent.com/mohamed-benoughidene/openreview/main/src/openreview_cli/gateway/models.json"
    count = registry.refresh(url)
    typer.echo(f"Registry refreshed: {count} models loaded.")


@gateway_app.command("test")
def gateway_test(slot: str) -> None:
    """Send a test request to a slot's model."""
    from openreview_cli.gateway.router import Gateway
    from openreview_cli.slots import VALID_SLOTS

    if slot not in VALID_SLOTS:
        typer.echo(f"Invalid slot '{slot}'. Valid slots: {', '.join(sorted(VALID_SLOTS))}")
        raise typer.Exit(code=1)

    gw = Gateway()
    try:
        if slot in ("reasoning", "extraction", "graph"):
            response = gw.chat(slot, [{"role": "user", "content": "Hello — respond with 'OK'."}])
            typer.echo(f"Response: {response}")
        elif slot == "embedding":
            emb = gw.embed(slot, ["Hello world"])
            typer.echo(f"Embedding: {len(emb[0])} dimensions")
        elif slot == "reranking":
            rnk = gw.rerank(slot, "test", ["doc1", "doc2"], top_n=2)
            typer.echo(f"Reranked: {len(rnk)} results")
        elif slot == "grounding":
            from openreview_cli.gateway.models import CapabilityRequirement

            response = gw.chat(
                "grounding",
                [{"role": "user", "content": "Does clause 1 require confidentiality? Answer OK."}],
                requirement=CapabilityRequirement(capability="reasoning"),
            )
            typer.echo(f"Response: {response}")
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None


@gateway_app.command("costs")
def gateway_costs(
    today: bool = typer.Option(False, "--today", help="Show today's costs"),
    session: str | None = typer.Option(None, "--session", help="Session ID to query"),
) -> None:
    """Show cost summary."""
    from openreview_cli.gateway.router import Gateway

    gw = Gateway()
    if session:
        cost = gw.get_cost(session)
        typer.echo(
            f"Session {session}: {cost['prompt_tokens']} prompt tokens, "
            f"{cost['completion_tokens']} completion tokens, "
            f"{cost['cost_cents']}¢"
        )
    elif today:
        from openreview_cli.config.paths import get_data_dir
        from openreview_cli.storage.database import check_daily_limit

        db_path = get_data_dir() / "openreview.db"
        under = check_daily_limit(db_path, 999999)
        typer.echo(f"Daily cost limit: {'under' if under else 'exceeded'}")
    else:
        typer.echo("Use --today or --session <id> to query costs.")


@provider_app.command("add")
def provider_add(
    name: str = typer.Argument(..., help="Custom provider name."),
    base_url: str = typer.Option(..., "--base-url", help="OpenAI-compatible base URL."),
    env_key: str | None = typer.Option(
        None, "--env-key", help="API key env var (derived if omitted)."
    ),
    creds: list[str] | None = typer.Option(
        None, "--cred", help="key=value credential, repeatable (multi-field providers)."
    ),
    cap_embedding: bool = typer.Option(False, "--cap-embedding", help="Supports embeddings."),
    cap_reasoning: bool = typer.Option(False, "--cap-reasoning", help="Supports reasoning/chat."),
    cap_tool_call: bool = typer.Option(False, "--cap-tool-call", help="Supports tool calls."),
    context_window: int | None = typer.Option(
        None, "--context-window", help="Context window in tokens."
    ),
) -> None:
    """Add a custom OpenAI-compatible provider (non-interactive)."""
    from openreview_cli.config.auth import save_provider_credentials
    from openreview_cli.config.paths import get_config_dir
    from openreview_cli.gateway.errors import (
        EnvKeyCollisionError,
        ProviderNameCollisionError,
    )
    from openreview_cli.gateway.registry import add_custom_provider

    if env_key is None:
        env_key = re.sub(r"[^A-Z0-9]", "_", name.upper()) + "_API_KEY"

    capabilities = {
        "embedding": cap_embedding,
        "reasoning": cap_reasoning,
        "tool_call": cap_tool_call,
        "context_window": context_window,
    }

    try:
        add_custom_provider(name, base_url, capabilities, api_key_env=env_key)
    except (ProviderNameCollisionError, EnvKeyCollisionError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None

    if creds:
        parsed: dict[str, str] = {}
        for item in creds:
            if "=" not in item:
                typer.echo(f"Error: --cred must be key=value, got {item!r}", err=True)
                raise typer.Exit(code=2)
            key, value = item.split("=", 1)
            if value == "":
                typer.echo(f"Error: --cred {key} has empty value", err=True)
                raise typer.Exit(code=2)
            parsed[key] = value
        save_provider_credentials(get_config_dir() / "auth.json", name, parsed)

    typer.echo(
        f"Added provider '{name}' (source: custom). "
        f"Set a slot with: openreview gateway set <slot> {name}/<model>"
    )


gateway_app.add_typer(provider_app, name="provider")


app.add_typer(gateway_app)


@app.command()
def chunk(
    path: str = typer.Argument(..., help="Path to a parsed contract JSON file."),
    format: str = typer.Option("text", "--format", help="Output format: text, json"),
    summary: bool = typer.Option(False, "--summary", help="Show one-line summary only"),
) -> None:
    from openreview_cli.chunking.models import ChunkConfig
    from openreview_cli.chunking.stream import (
        format_chunks_json,
        format_chunks_summary,
        format_chunks_text,
        stream_chunks,
    )
    from openreview_cli.parsing.stream import parse_document

    try:
        _, clauses = parse_document(path)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None

    import time

    start = time.time()
    chunks = list(stream_chunks(clauses, ChunkConfig()))
    elapsed = time.time() - start

    if summary:
        typer.echo(format_chunks_summary(len(clauses), len(chunks), elapsed))
    elif format == "json":
        typer.echo(format_chunks_json(chunks))
    else:
        typer.echo(format_chunks_text(chunks))


# ── compare subcommand ──


@precheck_app.command("compare")
def compare(
    doc_a: str | None = typer.Argument(None, help="Path to Party A's document (PDF or DOCX)."),
    doc_b: str | None = typer.Argument(None, help="Path to Party B's document (PDF or DOCX)."),
    playbook: str | None = typer.Option(
        None, "--playbook", help="Path to custom YAML playbook override."
    ),
    extraction_model: str | None = typer.Option(
        None, "--extraction-model", help="Model slot for the extraction agent."
    ),
    qa_model: str | None = typer.Option(
        None, "--qa-model", help="Model slot for the QA verification agent."
    ),
    comparison_model: str | None = typer.Option(
        None, "--comparison-model", help="Override model slot for the comparison agent (D-13)."
    ),
    confidence_threshold: float | None = typer.Option(
        None,
        "--confidence-threshold",
        "-ct",
        help="Amber boundary for divergence detection confidence (0.0-1.0). "
        "Independent of single-party threshold. "
        "Note: accuracy ceiling ~64% F1 — set generously.",
        callback=_validate_threshold,
    ),
    show_redlines: bool = typer.Option(
        False, "--show-redlines", help="Show per-clause redline (tracked changes) summary (D-10)."
    ),
    version_label_a: str | None = typer.Option(
        None, "--version-label-a", help="Version label for Party A's document (D-11)."
    ),
    version_label_b: str | None = typer.Option(
        None, "--version-label-b", help="Version label for Party B's document (D-11)."
    ),
    history: bool = typer.Option(
        False, "--history", help="Show comparison history and exit (D-11)."
    ),
    format: str = typer.Option("text", "--format", help="Output format: text (terminal) or json."),
    output: str | None = typer.Option(
        None, "--output", help="Write output to file instead of stdout."
    ),
    align_only: bool = typer.Option(
        False, "--align-only", help="Only run parsing and alignment, skip inference."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Show full RCBSF classification and rationale."
    ),
    no_pii: bool = typer.Option(False, "--no-pii", help="Skip PII stripping on both documents."),
    conservative: bool = typer.Option(
        False,
        "--conservative",
        help="Shortcut for --confidence-threshold 0.8. Mutually exclusive with --confidence-threshold.",
    ),
    grounding_mode: str = typer.Option(
        "strict",
        "--grounding-mode",
        help="Citation grounding mode: strict (ungrounded excluded) or lenient (flagged).",
    ),
    no_grounding: bool = typer.Option(
        False, "--no-grounding", help="Skip citation grounding entirely."
    ),
) -> None:
    """Compare two documents clause-by-clause and detect divergences.

    Runs the NX-1 bilateral comparison pipeline: parses both documents,
    aligns clauses by heading, runs the comparison agent on each pair,
    and produces a paired side-by-side assessment with three-color status.

    This is an EXPERIMENTAL feature with known accuracy limitations (≤64% F1).
    """
    # ── Handle --history (mutually exclusive with doc paths) ──
    if history:
        _show_comparison_history()
        return

    # Validate mutually exclusive flags
    if conservative and confidence_threshold is not None:
        typer.echo(
            "Error: --conservative and --confidence-threshold are mutually exclusive",
            err=True,
        )
        raise typer.Exit(code=3)

    # Validate output format
    if format not in ("text", "json"):
        typer.echo(
            f"Error: --format must be 'text' or 'json', got '{format}'",
            err=True,
        )
        raise typer.Exit(code=1)

    # Validate grounding mode
    if grounding_mode not in ("strict", "lenient"):
        typer.echo(
            f"Error: --grounding-mode must be 'strict' or 'lenient', got '{grounding_mode}'",
            err=True,
        )
        raise typer.Exit(code=1)

    # Resolve confidence threshold
    if conservative:
        resolved_threshold: float = 0.8
        # Also enable verbose for conservative mode
        verbose = True
    else:
        resolved_threshold = confidence_threshold if confidence_threshold is not None else 0.7

    # Check required args when not in history mode
    if doc_a is None or doc_b is None:
        typer.echo("Error: Both doc_a and doc_b are required (use --history to skip).", err=True)
        raise typer.Exit(code=2)

    # Check both files exist
    for path, _label in [(doc_a, "Party A"), (doc_b, "Party B")]:
        if not Path(path).exists():
            typer.echo(f"Error: File not found: {path}", err=True)
            raise typer.Exit(code=1)

    from openreview_cli.bilateral import run_comparison

    try:
        report = run_comparison(
            doc_a_path=doc_a,
            doc_b_path=doc_b,
            playbook=None,  # Use bundled playbook
            extraction_model=extraction_model or "extraction",
            qa_model=qa_model or extraction_model,
            no_pii=no_pii,
            verbose=verbose,
            confidence_threshold=resolved_threshold,
            align_only=align_only,
            grounding_mode=None if no_grounding else grounding_mode,
            comparison_model=comparison_model,
            version_label_a=version_label_a,
            version_label_b=version_label_b,
        )
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2) from None

    from openreview_cli.bilateral.report import (
        format_comparison_json,
        format_comparison_terminal,
    )

    if format == "json":
        output_str = format_comparison_json(report)
        if output:
            Path(output).write_text(output_str, encoding="utf-8")
        else:
            typer.echo(output_str)
    else:
        output_str = format_comparison_terminal(report, verbose=verbose)
        typer.echo(output_str)

    # ── D-10: Show redlines per clause ──
    if show_redlines:
        _show_clause_redlines(doc_a, doc_b, report)

    # Print Amber warning to stderr
    if report.summary.amber_count > 0:
        typer.echo(
            f"⚠  {report.summary.amber_count} clause(s) flagged Amber — review recommended.",
            err=True,
        )


# ── D-10 / D-11 Helpers ──


def _show_comparison_history() -> None:
    """Print comparison history table and exit."""
    from rich.console import Console
    from rich.table import Table

    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.storage.database import list_comparison_history

    db_path = get_data_dir() / "openreview.db"
    entries = list_comparison_history(db_path)

    console = Console()
    if not entries:
        console.print("No comparison history found.")
        return

    table = Table(title="Comparison History")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Doc A", style="green")
    table.add_column("Label A", style="white")
    table.add_column("Doc B", style="green")
    table.add_column("Label B", style="white")
    table.add_column("Run At", style="yellow")

    for e in entries:
        table.add_row(
            str(e["id"]),
            e["contract_a_path"],
            e["contract_a_version_label"] or "",
            e["contract_b_path"],
            e["contract_b_version_label"] or "",
            e["run_at"],
        )
    console.print(table)


def _show_clause_redlines(
    doc_a: str,
    doc_b: str,
    report: Any,
) -> None:
    """Extract tracked changes from DOCX documents and show per-clause summary."""
    from rich.console import Console

    from openreview_cli.parsing.docx_parser import DocxParser

    _c = Console()

    for doc_path, label in [(doc_a, "A"), (doc_b, "B")]:
        if not doc_path.lower().endswith(".docx"):
            continue
        try:
            parser = DocxParser(Path(doc_path))
            clauses = list(parser.parse())
            redlines = parser.tracked_changes
            if not redlines:
                _c.print(f"  Party {label}: No tracked changes found.")
                continue

            from openreview_cli.bilateral.comparison import map_redlines_to_clauses

            mapping = map_redlines_to_clauses(redlines, clauses)

            _c.print(f"\n  Party {label} — Tracked Changes per Clause:")
            for clause in clauses:
                changes = mapping.get(clause.id, [])
                if not changes:
                    continue
                for c in changes:
                    marker = "[green]+[/green]" if c.change_type == "ins" else "[red]-[/red]"
                    _c.print(f'    {marker} [{clause.id}] {c.author}: "{c.text[:80]}"')
        except Exception as exc:
            _c.print(
                f"  Party {label}: Could not extract redlines: {exc}",
                style="red",
            )


# ── retrieval subcommands ──


@app.command()
def ingest(
    file: str = typer.Argument(..., help="Path to a .ndax file with pre-chunked data."),
    method: str = typer.Option("hybrid", "--method", help="Retrieval method: sparse, hybrid"),
    model: str | None = typer.Option(None, "--model", help="Embedding model override"),
    db_dir: str | None = typer.Option(None, "--db-dir", help="Index database directory"),
) -> None:
    """Parse, chunk, and index a document for retrieval."""
    from openreview_cli.gateway.router import Gateway
    from openreview_cli.retrieval.errors import EmbeddingError
    from openreview_cli.retrieval.ingest import (
        _ensure_db_dir,
        get_index_for_document,
        ingest_from_file,
    )

    file_path = Path(file)
    if not file_path.exists():
        typer.echo(f"Error: File not found: {file}", err=True)
        raise typer.Exit(code=1)

    import json

    with open(file_path) as f:
        chunks_data = json.load(f)

    if not chunks_data:
        typer.echo("Error: No chunks found in file.", err=True)
        raise typer.Exit(code=1)

    doc_id = _resolve_doc_id(file_path)

    db_dir_resolved = _ensure_db_dir(db_dir)
    db_path = db_dir_resolved / f"{doc_id[:32]}.db"

    # Check if already indexed
    existing = get_index_for_document(doc_id[:32], db_dir_resolved)
    if existing is not None:
        typer.echo("Document already indexed (up to date). Use --force to re-index.")
        return

    gateway: Gateway | None = None
    with contextlib.suppress(Exception):
        gateway = Gateway()

    try:
        start = time.time()

        def _progress(current: int, total: int) -> None:
            if total > 0 and current % max(1, total // 10) == 0:
                typer.echo(f"  Progress: {current}/{total} chunks", err=True)

        meta = ingest_from_file(
            file_path,
            db_path,
            gateway=gateway,
            method=method,
            model_id=model,
            progress_callback=_progress,
        )
        elapsed = time.time() - start

        chunk_count = meta.get("chunk_count", len(chunks_data))
        final_method = meta.get("method", method)
        embed_info = ""
        if meta.get("embedding_model"):
            embed_info = f" ({meta['embedding_model']}, {meta.get('embedding_dimension', '?')}d)"

        typer.echo(f"Indexed {chunk_count} chunks in {elapsed:.1f}s")
        typer.echo(f"  Method: {final_method}{embed_info}")
        typer.echo(f"  DB: {db_path}")
    except EmbeddingError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None


@app.command()
def retrieve(
    query: str = typer.Argument(..., help="Natural-language query (wrap in quotes)."),
    file: str | None = typer.Argument(
        None, help="Document file (.ndax). Omit to use most recently indexed document."
    ),
    method: str = typer.Option(
        "hybrid", "--method", help="Retrieval method: sparse, dense, hybrid"
    ),
    top_k: int = typer.Option(5, "--top-k", help="Number of results (1-50)"),
    rerank: bool = typer.Option(
        False, "--rerank", help="Enable cross-encoder reranker (experimental, opt-in)."
    ),
    rerank_depth: int = typer.Option(
        20, "--rerank-depth", help="Number of hybrid results to rerank."
    ),
    force_rerank: bool = typer.Option(
        False, "--force-rerank", help="Override reranker validation warning."
    ),
    format: str = typer.Option("terminal", "--format", help="Output format: terminal, json"),
    db_dir: str | None = typer.Option(None, "--db-dir", help="Index database directory"),
    no_header: bool = typer.Option(
        False, "--no-header", help="Omit header row from terminal output."
    ),
) -> None:
    """Retrieve relevant clause chunks from an indexed document."""
    import json as json_lib

    from openreview_cli.gateway.router import Gateway
    from openreview_cli.retrieval.engine import RetrievalEngine
    from openreview_cli.retrieval.errors import IndexCorruptError, IndexNotFoundError
    from openreview_cli.retrieval.ingest import _ensure_db_dir, get_last_indexed_doc
    from openreview_cli.retrieval.models import RetrievalQuery

    db_dir_resolved = _ensure_db_dir(db_dir)

    # Resolve db_path
    doc_id = ""
    if file:
        file_path = Path(file)
        if not file_path.exists():
            typer.echo(f"Error: File not found: {file}", err=True)
            raise typer.Exit(code=1)
        doc_id = _resolve_doc_id(file_path)
    else:
        # T062: Fallback to most recently indexed document
        last_doc = get_last_indexed_doc(db_dir_resolved)
        if last_doc is None:
            typer.echo(
                "Error: No document specified and no previously indexed document found.\n"
                'Run `openreview retrieve "<query>" <file>` with a document, '
                "or `openreview ingest <file>` to index one first.",
                err=True,
            )
            raise typer.Exit(code=2)
        doc_id = _resolve_doc_id(Path(last_doc))

    if not doc_id:
        typer.echo("Error: Could not determine document ID.", err=True)
        raise typer.Exit(code=1)

    db_path = db_dir_resolved / f"{doc_id[:32]}.db"

    if not db_path.exists():
        typer.echo(
            "Document not indexed. Run `openreview ingest <file>` first.",
            err=True,
        )
        raise typer.Exit(code=2)

    # Build query
    try:
        rq = RetrievalQuery(
            query_text=query,
            method=method,
            top_k=top_k,
            rerank=rerank,
            rerank_depth=rerank_depth,
            force_rerank=force_rerank,
        )
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None

    # Get gateway for dense/hybrid mode
    gateway: Gateway | None = None
    if method in ("dense", "hybrid") or rerank:
        try:
            gateway = Gateway()
        except Exception:
            gateway = None

    engine = RetrievalEngine(db_path, gateway=gateway)

    try:
        results = engine.retrieve(rq)
    except IndexNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2) from None
    except IndexCorruptError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=3) from None

    # ── Offline/dense-fallback notices (T047) ──
    for notice in engine.notices:
        typer.echo(f"⚠  {notice}", err=True)

    # ── Reranker integration (T031) ──
    if rerank and results:
        from openreview_cli.retrieval.rerank import Reranker
        from openreview_cli.retrieval.storage import RetrievalStorage

        try:
            reranker = Reranker(gateway)
            candidates = results[:rerank_depth] if rerank_depth < len(results) else results
            results = reranker.rerank(query, candidates, top_k)

            # Check reranker validation warning
            if not force_rerank:
                with RetrievalStorage(db_path) as store:
                    val = store.get_rerank_validation(
                        model_id=reranker.model_id,
                        document_type="legal-nda",
                    )
                if val and val.get("degradation_pp", 0) is not None:
                    deg = val["degradation_pp"]
                    if isinstance(deg, (int, float)) and deg >= 0:
                        warning = (
                            "⚠ Reranker validation shows reranker does not improve "
                            f"retrieval quality (degradation: {deg:.1f}pp). "
                            "Use --force-rerank to override."
                        )
                        typer.echo(warning, err=True)

        except Exception as exc:
            logger.warning("Reranker integration failed (%s); returning raw results.", exc)

    if not results:
        typer.echo(
            "No relevant clauses found for this query. "
            "Try a different query or use --method sparse for broader matching."
        )
        return

    if format == "json":
        output = []
        for r in results:
            output.append(
                {
                    "chunk_id": r.chunk_id,
                    "text": r.text,
                    "clause_heading": r.clause_heading,
                    "clause_level": r.clause_level,
                    "hierarchy_chain": r.hierarchy_chain,
                    "score": round(r.score, 4),
                    "method": r.method,
                    "rank_sparse": r.rank_sparse,
                    "rank_dense": r.rank_dense,
                    "rrf_score": round(r.rrf_score, 6) if r.rrf_score is not None else None,
                    "rerank_score": round(r.rerank_score, 6)
                    if r.rerank_score is not None
                    else None,
                }
            )
        typer.echo(
            json_lib.dumps(
                {"query": query, "method": method, "top_k": top_k, "results": output}, indent=2
            )
        )
    else:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        show_header = not no_header
        table = Table(title=f'Retrieval Results — "{query}"', show_header=show_header)
        table.add_column("Rank", style="cyan", justify="right")
        table.add_column("Clause Heading", style="green")
        table.add_column("Score", style="yellow", justify="right")
        table.add_column("Method", style="blue")

        for rank, r in enumerate(results, start=1):
            heading = r.clause_heading
            # Show hierarchy chain as indented tree
            if r.hierarchy_chain and len(r.hierarchy_chain) > 1:
                lines = [r.hierarchy_chain[0]]
                for h in r.hierarchy_chain[1:]:
                    lines.append(f"  {h}")
                heading = "\n".join(lines)

            table.add_row(
                str(rank),
                heading,
                f"{r.score:.4f}",
                r.method,
            )
        console.print(table)


@app.command(name="index-status")
def index_status(
    file: str | None = typer.Argument(None, help="Document file (.ndax)."),
    db_dir: str | None = typer.Option(None, "--db-dir", help="Index database directory"),
) -> None:
    """Show indexing status for a document."""

    from openreview_cli.retrieval.engine import RetrievalEngine
    from openreview_cli.retrieval.ingest import _ensure_db_dir

    if not file:
        typer.echo("Error: FILE argument required.", err=True)
        raise typer.Exit(code=1)

    file_path = Path(file)
    if not file_path.exists():
        typer.echo(f"Error: File not found: {file}", err=True)
        raise typer.Exit(code=1)

    doc_id = _resolve_doc_id(file_path)

    db_dir_resolved = _ensure_db_dir(db_dir)
    db_path = db_dir_resolved / f"{doc_id[:32]}.db"

    if not db_path.exists():
        typer.echo(f"Document not indexed. Run `openreview ingest {file}` first.")
        raise typer.Exit(code=2)

    engine = RetrievalEngine(db_path)
    meta = engine.get_index_meta()
    if meta is None:
        size = db_path.stat().st_size if db_path.exists() else 0
        typer.echo(f"Index file exists but metadata not found ({size} bytes).")
        return

    typer.echo(f"Document: {file_path.name}")
    status = meta.get("index_status", "unknown")
    ts = meta.get("index_timestamp", "")
    typer.echo(f"Status:   {status}" + (f" ({ts})" if ts else ""))
    typer.echo(f"Chunks:   {meta.get('chunk_count', 0)}")
    typer.echo(f"Method:   {meta.get('method', '?')}")
    model = meta.get("embedding_model")
    dim = meta.get("embedding_dim")
    if model:
        typer.echo(f"Model:    {model}" + (f" ({dim}d)" if dim else ""))
    else:
        typer.echo("Model:    (none — sparse only)")
    size_bytes = meta.get("db_size_bytes", 0)
    if size_bytes > 1024 * 1024:
        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
    elif size_bytes > 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes} bytes"
    typer.echo(f"DB size:  {size_str}")


@app.command(name="index-clear")
def index_clear(
    file: str | None = typer.Argument(None, help="Document file (.ndax)."),
    all_flag: bool = typer.Option(
        False, "--all", help="Clear ALL indexes (requires confirmation)."
    ),
    db_dir: str | None = typer.Option(None, "--db-dir", help="Index database directory"),
) -> None:
    """Remove indexed data for a document."""

    from openreview_cli.retrieval.ingest import _ensure_db_dir
    from openreview_cli.retrieval.ingest import clear_index as _clear_index

    if all_flag:
        typer.echo("Clearing ALL indexes...")
        db_dir_resolved = _ensure_db_dir(db_dir)
        count = 0
        for db_file in db_dir_resolved.glob("*.db"):
            _clear_index(db_file)
            count += 1
        typer.echo(f"Cleared {count} index database(s).")
        return

    if not file:
        typer.echo("Error: FILE argument required.", err=True)
        raise typer.Exit(code=1)

    file_path = Path(file)
    if not file_path.exists():
        typer.echo(f"Error: File not found: {file}", err=True)
        raise typer.Exit(code=1)

    doc_id = _resolve_doc_id(file_path)

    db_dir_resolved = _ensure_db_dir(db_dir)
    db_path = db_dir_resolved / f"{doc_id[:32]}.db"

    if not db_path.exists():
        typer.echo("Document not indexed.")
        raise typer.Exit(code=2)

    db_size = db_path.stat().st_size
    _clear_index(db_path)
    typer.echo(f"Index for {file_path.name} cleared ({db_size} bytes).")


# ── graph subcommand group ──


def _run_clause_clustering(
    graph: Any,  # ANN401: ContractGraph, lazy import
    parsed_path: Path,
) -> None:
    """Embed clause text, cluster with HDBSCAN, attach to graph metadata.

    Fails gracefully if model can't load (offline/error) — graph build
    succeeds without clustering.
    """
    try:
        # Load clauses from parsed JSON (same as graph builder did)
        import json

        from openreview_cli.parsing.clause_clusterer import ClauseClusterer

        clause_dicts: list[dict[str, Any]] = json.loads(parsed_path.read_text(encoding="utf-8"))
        from openreview_cli.parsing.models import Clause

        clauses: list[Clause] = []
        for cd in clause_dicts:
            clauses.append(
                Clause(
                    id=cd["id"],
                    title=cd.get("title"),
                    text=cd["text"],
                    level=cd.get("level", 0),
                    parent_id=cd.get("parent_id"),
                    source_page=cd.get("source_page"),
                    source_paragraph=cd.get("source_paragraph"),
                    source_span=cd.get("source_span"),
                    paragraph_count=cd.get("paragraph_count"),
                )
            )

        ClauseClusterer.load()
        try:
            embeddings = ClauseClusterer.embed_clauses(clauses)
            labels = ClauseClusterer.cluster_clauses(embeddings)
        finally:
            ClauseClusterer.cleanup()

        # Build cluster summaries
        cluster_labels_list = labels.tolist()
        unique_labels = sorted(set(cluster_labels_list))
        clusters: list[dict[str, Any]] = []
        for lab in unique_labels:
            indices = [i for i, li in enumerate(cluster_labels_list) if li == lab]
            # ponytail: simple excerpt-based summary
            excerpts = [clauses[i].text[:120] for i in indices[:3]]
            clusters.append(
                {
                    "label": int(lab),
                    "count": len(indices),
                    "clause_ids": [clauses[i].id for i in indices],
                    "excerpts": excerpts,
                }
            )

        graph.metadata["clustering"] = {
            "method": "legal-bert + HDBSCAN cosine",
            "model": "nlpaueb/legal-bert-base-uncased",
            "cluster_count": len(unique_labels) - (1 if -1 in unique_labels else 0),
            "noise_count": cluster_labels_list.count(-1),
            "clusters": clusters,
        }
        n_clusters = graph.metadata["clustering"]["cluster_count"]
        typer.echo(
            f"Clustering: {n_clusters} cluster(s), "
            f"{graph.metadata['clustering']['noise_count']} noise clause(s)"
        )

    except Exception as exc:
        # ponytail: cluster failure doesn't break graph build
        typer.echo(f"Clustering skipped (model not available?): {exc}", err=True)


graph_app = typer.Typer(
    name="graph",
    help="Build and analyse contract clause graphs.",
    no_args_is_help=True,
)


@graph_app.command("build")
def graph_build(
    input_path: str = typer.Argument(
        ...,
        help="Path to a parsed contract JSON file (output of 'openreview parse --format json').",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Path for the output graph JSON file (default: {input_stem}.graph.json).",
    ),
    store: bool = typer.Option(False, "--store", help="Save graph to SQLite database."),
    contract_id: str | None = typer.Option(
        None, "--contract-id", help="Contract ID for SQLite storage (default: input file stem)."
    ),
    db_path: str | None = typer.Option(
        None,
        "--db-path",
        help="Path to SQLite database (default: .openreview/openreview.db in config dir).",
    ),
    cluster_clauses: bool = typer.Option(
        False,
        "--cluster-clauses",
        help="Run legal-bert clause embedding + HDBSCAN clustering on parsed clauses.",
    ),
) -> None:
    """Build a directed clause graph from a parsed contract JSON file."""
    from pathlib import Path

    path = Path(input_path)
    if not path.exists():
        typer.echo(f"Error: File not found: {input_path}", err=True)
        raise typer.Exit(code=1)

    try:
        from openreview_cli.graph.builder import build_from_parsed

        graph = build_from_parsed(str(path))
    except Exception as e:
        typer.echo(f"Error: Invalid graph file: {e}", err=True)
        raise typer.Exit(code=2) from None

    if output is None:
        output = str(path.with_suffix(".graph.json"))
    graph.to_file(output)
    typer.echo(f"Graph built: {len(graph.nodes)} nodes, {len(graph.edges)} edges \u2192 {output}")

    # --cluster-clauses: embed + cluster and attach to graph metadata
    if cluster_clauses:
        _run_clause_clustering(graph, path)
        graph.to_file(output)

    if store:
        from openreview_cli.config.paths import get_config_dir
        from openreview_cli.storage.database import init_database, save_graph

        cid = contract_id if contract_id else path.stem
        db = Path(db_path) if db_path else get_config_dir() / "openreview.db"
        db.parent.mkdir(parents=True, exist_ok=True)
        init_database(db)
        save_graph(db, cid, graph)
        typer.echo(f"Graph stored in database: contract_id={cid}")


@graph_app.command("metrics")
def graph_metrics(
    graph_path: str = typer.Argument(
        None, help="Path to a graph JSON file (output of 'graph build')."
    ),
    from_db: bool = typer.Option(False, "--from-db", help="Load graph from SQLite."),
    contract_id: str | None = typer.Option(
        None, "--contract-id", help="Contract ID in SQLite (required with --from-db)."
    ),
    db_path: str | None = typer.Option(
        None,
        "--db-path",
        help="Path to SQLite database (default: .openreview/openreview.db in config dir).",
    ),
) -> None:
    """Compute heuristic structural metrics from a graph JSON file."""
    from pathlib import Path

    if from_db:
        from openreview_cli.config.paths import get_config_dir
        from openreview_cli.graph.models import ContractGraph

        if not contract_id:
            typer.echo("Error: --contract-id required with --from-db", err=True)
            raise typer.Exit(code=2)
        db = Path(db_path) if db_path else get_config_dir() / "openreview.db"
        graph = ContractGraph.load_from_db(db, contract_id)
        if graph is None:
            typer.echo(f"Error: Contract '{contract_id}' not found in database.", err=True)
            raise typer.Exit(code=2)
    else:
        if not graph_path:
            typer.echo("Error: GRAPH_PATH argument or --from-db required.", err=True)
            raise typer.Exit(code=2)
        path = Path(graph_path)
        if not path.exists():
            typer.echo(f"Error: File not found: {graph_path}", err=True)
            raise typer.Exit(code=1)

        try:
            from openreview_cli.graph.models import ContractGraph

            graph = ContractGraph.from_file(str(path))
        except Exception as e:
            typer.echo(f"Error: Invalid graph file: {e}", err=True)
            raise typer.Exit(code=2) from None

    from openreview_cli.graph.metrics import compute_metrics

    metrics = compute_metrics(graph)

    typer.echo("Contract Graph Metrics")
    typer.echo("\u2500" * 22)
    typer.echo(f"Density:              {metrics.density:.3f}")
    typer.echo(f"Max Depth:            {metrics.max_depth}")
    typer.echo(f"Orphan Ratio:         {metrics.orphan_ratio:.3f}")
    typer.echo(f"Broken Cross-Refs:    {metrics.broken_ref_count}")
    typer.echo(f"Definition Coverage:  {metrics.definition_coverage:.3f}")


@graph_app.command("diff")
def graph_diff(
    file_a: str = typer.Argument(..., help="Path to first graph JSON file."),
    file_b: str = typer.Argument(..., help="Path to second graph JSON file."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Compare two contract graphs and show differences."""
    from pathlib import Path

    path_a = Path(file_a)
    path_b = Path(file_b)
    if not path_a.exists():
        typer.echo(f"Error: File not found: {file_a}", err=True)
        raise typer.Exit(code=1)
    if not path_b.exists():
        typer.echo(f"Error: File not found: {file_b}", err=True)
        raise typer.Exit(code=1)

    try:
        from openreview_cli.graph.diff import compute_graph_diff
        from openreview_cli.graph.models import ContractGraph

        g1 = ContractGraph.from_file(str(path_a))
        g2 = ContractGraph.from_file(str(path_b))
        diff = compute_graph_diff(g1, g2)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2) from None

    if json_output:
        import json as _json

        data = {
            "added_nodes": [n.id for n in diff.added_nodes],
            "removed_nodes": [n.id for n in diff.removed_nodes],
            "relabeled_nodes": [
                {"old": old.label, "new": new.label, "id": old.id}
                for old, new in diff.relabeled_nodes
            ],
            "added_edges": [
                {"source": edge.source_id, "target": edge.target_id, "type": edge.edge_type.value}
                for edge in diff.added_edges
            ],
            "removed_edges": [
                {"source": edge.source_id, "target": edge.target_id, "type": edge.edge_type.value}
                for edge in diff.removed_edges
            ],
        }
        typer.echo(_json.dumps(data, indent=2))
        return

    if (
        not diff.added_nodes
        and not diff.removed_nodes
        and not diff.added_edges
        and not diff.removed_edges
        and not diff.relabeled_nodes
    ):
        typer.echo("No differences found between graphs.")
        return

    if diff.added_nodes:
        typer.echo("Added nodes:")
        for n in diff.added_nodes:
            typer.echo(f"  + {n.id}: {n.label}")
    if diff.removed_nodes:
        typer.echo("Removed nodes:")
        for n in diff.removed_nodes:
            typer.echo(f"  - {n.id}: {n.label}")
    if diff.relabeled_nodes:
        typer.echo("Relabeled nodes:")
        for old, new in diff.relabeled_nodes:
            typer.echo(f"  ~ {old.id}: '{old.label}' -> '{new.label}'")
    if diff.added_edges:
        typer.echo("Added edges:")
        for edge in diff.added_edges:
            typer.echo(f"  + {edge.source_id} -> {edge.target_id} ({edge.edge_type.value})")
    if diff.removed_edges:
        typer.echo("Removed edges:")
        for edge in diff.removed_edges:
            typer.echo(f"  - {edge.source_id} -> {edge.target_id} ({edge.edge_type.value})")


@graph_app.command("health")
def graph_health(
    graph_path: str = typer.Argument(
        None, help="Path to a graph JSON file (output of 'graph build')."
    ),
    weights: str | None = typer.Option(
        None,
        "--weights",
        "-w",
        help="Five custom weights: density depth orphans broken-refs coverage. "
        "Space-separated, e.g. --weights '0.15 0.20 0.20 0.25 0.20'. "
        "Auto-normalised to sum 1.0.",
    ),
    from_db: bool = typer.Option(False, "--from-db", help="Load graph from SQLite."),
    contract_id: str | None = typer.Option(
        None, "--contract-id", help="Contract ID in SQLite (required with --from-db)."
    ),
    db_path: str | None = typer.Option(
        None,
        "--db-path",
        help="Path to SQLite database (default: .openreview/openreview.db in config dir).",
    ),
) -> None:
    """Compute a 0-100 health score from a graph JSON file."""
    from pathlib import Path

    if from_db:
        from openreview_cli.config.paths import get_config_dir
        from openreview_cli.graph.models import ContractGraph

        if not contract_id:
            typer.echo("Error: --contract-id required with --from-db", err=True)
            raise typer.Exit(code=2)
        db = Path(db_path) if db_path else get_config_dir() / "openreview.db"
        graph = ContractGraph.load_from_db(db, contract_id)
        if graph is None:
            typer.echo(f"Error: Contract '{contract_id}' not found in database.", err=True)
            raise typer.Exit(code=2)
    else:
        if not graph_path:
            typer.echo("Error: GRAPH_PATH argument or --from-db required.", err=True)
            raise typer.Exit(code=2)
        path = Path(graph_path)
        if not path.exists():
            typer.echo(f"Error: File not found: {graph_path}", err=True)
            raise typer.Exit(code=1)

        try:
            from openreview_cli.graph.models import ContractGraph

            graph = ContractGraph.from_file(str(path))
        except Exception as e:
            typer.echo(f"Error: Invalid graph file: {e}", err=True)
            raise typer.Exit(code=2) from None

    from openreview_cli.graph.health import compute_health
    from openreview_cli.graph.metrics import compute_metrics

    metrics = compute_metrics(graph)

    parsed_weights: list[float] | None = None
    if weights is not None:
        parts = weights.split()
        if len(parts) != 5:
            typer.echo("Error: --weights must contain exactly 5 values", err=True)
            raise typer.Exit(code=2)
        try:
            parsed_weights = [float(w) for w in parts]
        except ValueError:
            typer.echo("Error: --weights values must be valid floats", err=True)
            raise typer.Exit(code=2) from None
        if any(w < 0 for w in parsed_weights):
            typer.echo("Error: --weights values must be non-negative", err=True)
            raise typer.Exit(code=2)

    try:
        health = compute_health(metrics, parsed_weights)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2) from None

    typer.echo(f"Health Score: {health.score}/100")


@graph_app.command("view")
def graph_view(
    graph_path: str = typer.Argument(
        None, help="Path to a graph JSON file (output of 'graph build')."
    ),
    from_db: bool = typer.Option(False, "--from-db", help="Load graph from SQLite."),
    contract_id: str | None = typer.Option(
        None, "--contract-id", help="Contract ID in SQLite (required with --from-db)."
    ),
    db_path: str | None = typer.Option(
        None,
        "--db-path",
        help="Path to SQLite database (default: .openreview/openreview.db in config dir).",
    ),
) -> None:
    """Render the clause hierarchy as an indented ASCII text tree."""
    from pathlib import Path

    if from_db:
        from openreview_cli.config.paths import get_config_dir
        from openreview_cli.graph.models import ContractGraph

        if not contract_id:
            typer.echo("Error: --contract-id required with --from-db", err=True)
            raise typer.Exit(code=2)
        db = Path(db_path) if db_path else get_config_dir() / "openreview.db"
        graph = ContractGraph.load_from_db(db, contract_id)
        if graph is None:
            typer.echo(f"Error: Contract '{contract_id}' not found in database.", err=True)
            raise typer.Exit(code=2)
    else:
        if not graph_path:
            typer.echo("Error: GRAPH_PATH argument or --from-db required.", err=True)
            raise typer.Exit(code=2)
        path = Path(graph_path)
        if not path.exists():
            typer.echo(f"Error: File not found: {graph_path}", err=True)
            raise typer.Exit(code=1)

        try:
            from openreview_cli.graph.models import ContractGraph

            graph = ContractGraph.from_file(str(path))
        except Exception as e:
            typer.echo(f"Error: Invalid graph file: {e}", err=True)
            raise typer.Exit(code=2) from None

    from openreview_cli.graph.view import render_tree

    typer.echo(render_tree(graph))


app.add_typer(graph_app)


# ── negotiate command ──


@app.command()
def negotiate(
    doc_path: str = typer.Argument(..., help="Path to a PDF or DOCX contract document."),
    playbook_path: str | None = typer.Option(
        None, "--playbook-path", help="Path to a custom YAML playbook."
    ),
    solver: str = typer.Option(
        "qre",
        "--solver",
        help="Equilibrium solver: nash, qre, or level_k.",
    ),
    rationality: float = typer.Option(
        1.0,
        "--rationality",
        help="Rationality parameter for QRE solver (λ). Higher = more rational.",
    ),
    depth: int = typer.Option(
        2,
        "--depth",
        help="Depth of reasoning for level-k solver (k).",
    ),
    weights: str | None = typer.Option(
        None,
        "--weights",
        help="Payoff component weights as comma-separated values: "
        "risk,financial,obligation (e.g. 0.7,0.15,0.15). "
        "Must sum to ~1.0.",
    ),
    confidence_threshold: float = typer.Option(
        0.7,
        "--confidence-threshold",
        "-ct",
        help="Confidence threshold for Amber flagging (0.0-1.0).",
    ),
    no_pii: bool = typer.Option(False, "--no-pii", help="Skip PII stripping."),
    verbose: bool = typer.Option(False, "--verbose", help="Show per-clause progress."),
    output: str | None = typer.Option(
        None, "--output", help="Write output to file instead of stdout."
    ),
    format: str = typer.Option("table", "--format", help="Output format: table, json, memo."),
) -> None:
    """Run a game-theoretic negotiation analysis on a contract document.

    Builds clause-level payoff matrices from playbook positions and
    computes equilibrium strategies using the selected solver (default:
    bounded-rationality QRE). Produces per-clause recommendations with
    confidence annotations.

    This is an EXPERIMENTAL feature. All output is advisory only.
    """
    _validate_enum(solver, ("nash", "qre", "level_k"), "solver")
    _validate_enum(format, ("table", "json", "memo"), "format")

    if not 0.0 <= confidence_threshold <= 1.0:
        typer.echo(
            "Error: --confidence-threshold must be between 0.0 and 1.0",
            err=True,
        )
        raise typer.Exit(code=2)

    path = Path(doc_path)
    if not path.exists():
        typer.echo(f"Error: File not found: {doc_path}", err=True)
        raise typer.Exit(code=1)

    # Build assessments from document + playbook
    from openreview_cli.parsing.stream import parse_document
    from openreview_cli.review.extraction import match_category as _match_category
    from openreview_cli.review.models import ClauseAssessment, Position, QAVerdict
    from openreview_cli.review.playbook import load_bundled, load_playbook

    if playbook_path:
        pb_path = Path(playbook_path)
        if not pb_path.exists():
            typer.echo(f"Error: Playbook not found: {playbook_path}", err=True)
            raise typer.Exit(code=1)
        playbook = load_playbook(pb_path)
    else:
        playbook = load_bundled()

    # Parse document
    doc, clauses = parse_document(str(path))

    # Build ClauseAssessment objects for each clause
    assessments: list[ClauseAssessment] = []
    for clause in clauses:
        clause_text = getattr(clause, "text", str(clause)) or str(clause)
        clause_id_str = getattr(
            clause, "heading", getattr(clause, "id", f"clause_{len(assessments) + 1}")
        )

        # Match clause heading to playbook category for position extraction
        heading = str(clause_id_str)
        cat = _match_category(heading, playbook)

        if cat is not None:
            playbook_cat_id = cat.id
            position = cat.default_position
            # ponytail: confidence from playbook, default 0.7
            pb_confidence = 0.7
            if hasattr(cat, "preferred") and hasattr(cat.preferred, "description"):
                pb_confidence = 0.75  # Slight bump when playbook has position details
        else:
            playbook_cat_id = "no-match"
            position = Position.PREFERRED
            pb_confidence = 0.5  # Lower confidence when no playbook match

        assessment = ClauseAssessment(
            clause_id=clause_id_str,
            clause_text=str(clause_text)[:200],
            playbook_category=playbook_cat_id,
            position=position,
            confidence=pb_confidence,
            citation="",
            qa_verdict=QAVerdict.agree,
            extraction_model="bundled",
            qa_model="bundled",
        )
        assessments.append(assessment)

    if not assessments:
        typer.echo("Error: No clauses found in document.", err=True)
        raise typer.Exit(code=2)

    if verbose:
        doc_filename = doc.filename if hasattr(doc, "filename") else str(path)
        typer.echo(f"Loaded {len(assessments)} clauses from {doc_filename}", err=True)

    # Parse weights string
    weights_dict: dict[str, float] | None = None
    if weights:
        parts = [float(x) for x in weights.split(",")]
        if len(parts) == 3:
            weights_dict = {"risk": parts[0], "financial": parts[1], "obligation": parts[2]}

    from openreview_cli.negotiation import (
        format_json,
        format_memo,
        format_terminal,
        run_negotiation,
    )

    try:
        report = run_negotiation(
            assessments=assessments,
            solver=solver,
            weights=weights_dict,
            rationality=rationality,
            depth=depth,
            confidence_threshold=confidence_threshold,
            playbook_id=playbook.id if hasattr(playbook, "id") else "bundled",
        )
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2) from None
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=3) from None

    if format == "json":
        output_str = format_json(report)
        if output:
            Path(output).write_text(output_str, encoding="utf-8")
        else:
            typer.echo(output_str)
    elif format == "memo":
        output_str = format_memo(report)
        if output:
            Path(output).write_text(output_str, encoding="utf-8")
        else:
            typer.echo(output_str)
    else:
        output_str = format_terminal(report)
        typer.echo(output_str)

    # Amber warning
    if report.summary.amber_count > 0:
        typer.echo(
            f"⚠  {report.summary.amber_count} clause(s) flagged Amber — review recommended.",
            err=True,
        )


# ── batch export subcommand ──


@app.command()
def export(
    batch_dir: str = typer.Option(
        ...,
        "--batch-dir",
        help="Directory containing ReviewReport JSON files to re-export.",
    ),
    format: str = typer.Option("md", "--format", help="Export format: md, json, docx."),
    output_dir: str = typer.Option(
        "review_results", "--output-dir", help="Directory for exported files."
    ),
    mode: str = typer.Option("precheck", "--mode", help="Mode name used as the filename prefix."),
    template: str | None = typer.Option(
        None,
        "--template",
        help="Path to a custom Jinja2 template for Markdown export (D-42). "
        "When set, overrides the built-in Markdown renderer. "
        "Has no effect on JSON or DOCX formats.",
    ),
) -> None:
    """Batch-export one or more saved review reports (D-41).

    Loads all JSON report files from BATCH_DIR, re-exports each in the
    requested format, and writes the results to OUTPUT_DIR.
    """
    _validate_enum(format, ("md", "json", "docx"), "format")

    src = Path(batch_dir)
    if not src.is_dir():
        typer.echo(
            f"Error: --batch-dir '{batch_dir}' is not a directory or does not exist.",
            err=True,
        )
        raise typer.Exit(code=2)

    report_paths = sorted(src.glob("*.json"))
    if not report_paths:
        typer.echo(f"No JSON report files found in '{batch_dir}'.", err=True)
        raise typer.Exit(code=1)

    # Validate --template path if provided
    template_path: Path | None = None
    if template is not None:
        template_path = Path(template)
        if not template_path.exists():
            typer.echo(
                f"Error: Template file not found: {template_path}",
                err=True,
            )
            raise typer.Exit(code=2)

    from openreview_cli.review.report import batch_export_reports

    out = Path(output_dir)
    written = batch_export_reports(
        report_paths, format, out, mode=mode, template_path=template_path
    )

    if written:
        typer.echo(f"Exported {len(written)} memo(s) to '{output_dir}'.")
        for p in written:
            typer.echo(f"  - {p}")
    else:
        typer.echo("No memos were exported.")


from openreview_cli.benchmark.cli import benchmark_app  # noqa: E402

app.add_typer(benchmark_app)

from openreview_cli.prompts.cli import prompt_app  # noqa: E402

app.add_typer(prompt_app)

# ── Product mode CLI registration ─────────────────────────────────────────


def _register_product_mode(
    app: typer.Typer,
    name: str,
    help_text: str,
    path_help: str,
) -> None:
    """Register a product-mode CLI command on *app*."""

    @app.command(name=name, help=help_text)
    def _cmd(
        path: str = typer.Argument(..., help=path_help),
        no_pii: bool = typer.Option(False, "--no-pii", help="Skip PII stripping."),
        playbook_path: str | None = typer.Option(
            None, "--playbook", help="Path to a custom YAML playbook override."
        ),
        format: str = typer.Option("text", "--format", help="Output format: text or json."),
        output: str | None = typer.Option(
            None, "--output", help="Write output to file instead of stdout."
        ),
        memo_format: list[str] = typer.Option(
            [],
            "--memo-format",
            help="Export format(s) for the review memo. Supported: md, json, docx.",
        ),
        output_dir: str | None = typer.Option(
            None,
            "--output-dir",
            help="Directory for memo files. Defaults to review_results/.",
        ),
        verbose: bool = typer.Option(False, "--verbose", help="Show per-clause progress."),
        confidence_threshold: float = typer.Option(
            DEFAULT_CONFIDENCE_THRESHOLD,
            "--confidence-threshold",
            "-ct",
            help="Confidence threshold for Green/Amber/Red (0.0-1.0).",
            callback=_validate_threshold,
        ),
        mode_threshold: list[str] = typer.Option(
            [],
            "--mode-threshold",
            help="Per-mode confidence threshold override, e.g. "
            "--mode-threshold leasecheck=0.85. Repeatable.",
        ),
    ) -> None:
        _run_product_review(
            mode=name,
            path=path,
            no_pii=no_pii,
            playbook_path=playbook_path,
            format=format,
            output=output,
            memo_format=memo_format,
            output_dir=output_dir,
            verbose=verbose,
            confidence_threshold=confidence_threshold,
            mode_threshold=mode_threshold,
        )


_register_product_mode(
    app,
    name="licensecheck",
    help_text="Review a SaaS/software license agreement with LicenseCheck.",
    path_help="Path to a SaaS/software license agreement (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="leasecheck",
    help_text="Review a commercial lease agreement with LeaseCheck.",
    path_help="Path to a commercial lease agreement (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="privacycheck",
    help_text="Review a Data Processing Agreement with PrivacyCheck.",
    path_help="Path to a Data Processing Agreement (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="dealcheck",
    help_text="Review a vendor/service agreement with DealCheck.",
    path_help="Path to a vendor or service agreement (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="hirecheck",
    help_text="Review an employment agreement with HireCheck.",
    path_help="Path to an employment agreement (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="indemnitycheck",
    help_text="Review an indemnification agreement with IndemnityCheck.",
    path_help="Path to an indemnification agreement (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="consultcheck",
    help_text="Review a consulting services agreement with ConsultCheck.",
    path_help="Path to a consulting services agreement (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="workcheck",
    help_text="Review an independent contractor/work-for-hire agreement with WorkCheck.",
    path_help="Path to an independent contractor agreement (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="loicheck",
    help_text="Review a letter of intent or MOU with LOICheck.",
    path_help="Path to a letter of intent or MOU (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="subcheck",
    help_text="Review a subcontractor agreement with SubCheck.",
    path_help="Path to a subcontractor agreement (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="settlementcheck",
    help_text="Review a settlement/release agreement with SettlementCheck.",
    path_help="Path to a settlement or release agreement (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="settlementcheck_v2",
    help_text="Review a complex settlement/release agreement (v2) with SettlementCheck.",
    path_help="Path to a complex settlement or release agreement (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="assetcheck",
    help_text="Review an asset transfer/assignment agreement with AssetCheck.",
    path_help="Path to an asset transfer or assignment agreement (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="buycheck",
    help_text="Review an asset purchase/business acquisition agreement with BuyCheck.",
    path_help="Path to an asset purchase or acquisition agreement (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="engagecheck",
    help_text="Review a professional services engagement letter with EngageCheck.",
    path_help="Path to an engagement letter (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="guaranteecheck",
    help_text="Review a personal guarantee/suretyship agreement with GuaranteeCheck.",
    path_help="Path to a personal guarantee or suretyship agreement (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="loancheck",
    help_text="Review a loan agreement/promissory note with LoanCheck.",
    path_help="Path to a loan agreement or promissory note (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="franchisecheck",
    help_text="Review a franchise agreement or franchise disclosure document.",
    path_help="Path to a franchise agreement or FDD (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="opcheck",
    help_text="Review an Operating Agreement (LLC governance document).",
    path_help="Path to an operating agreement (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="partnercheck",
    help_text="Review a general or limited partnership agreement.",
    path_help="Path to a partnership agreement (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="sponsorcheck",
    help_text="Review a sponsorship agreement.",
    path_help="Path to a sponsorship agreement (PDF or DOCX).",
)
_register_product_mode(
    app,
    name="distrocheck",
    help_text="Review a distribution or reseller agreement.",
    path_help="Path to a distribution agreement (PDF or DOCX).",
)


# ── Shared product review logic ─────────────────────────────────────────────


def _run_product_review(
    mode: str,
    path: str,
    no_pii: bool,
    playbook_path: str | None,
    format: str,
    output: str | None,
    memo_format: list[str],
    output_dir: str | None,
    verbose: bool,
    confidence_threshold: float,
    mode_threshold: list[str] | None = None,
) -> None:
    """Run a review using a mode-specific bundled playbook.

    Shared implementation for licensecheck, leasecheck, and privacycheck.
    """
    from openreview_cli.review.playbook import BUNDLED_PLAYBOOKS

    # Resolve playbook path
    resolved_playbook_path = playbook_path or str(BUNDLED_PLAYBOOKS[mode])

    from openreview_cli.review import run_review

    # Parse --mode-threshold MODE=VALUE pairs into dict
    mode_threshold_overrides: dict[str, float] | None = None
    if mode_threshold:
        mode_threshold_overrides = {}
        for item in mode_threshold:
            if "=" not in item:
                typer.echo(f"Error: --mode-threshold must be MODE=VALUE, got '{item}'", err=True)
                raise typer.Exit(code=2)
            m, v = item.split("=", 1)
            try:
                mode_threshold_overrides[m] = float(v)
            except ValueError:
                typer.echo(f"Error: --mode-threshold VALUE must be a float, got '{v}'", err=True)
                raise typer.Exit(code=2) from None

    # Merge with config-level mode thresholds (CLI takes precedence)
    try:
        from openreview_cli.config.loader import load_config
        from openreview_cli.config.paths import get_config_dir

        _cfg = load_config(get_config_dir() / "config.yml")
        config_thresholds = _cfg.get("modes", {}).get("thresholds")
        if isinstance(config_thresholds, dict):
            mode_threshold_overrides = mode_threshold_overrides or {}
            for ck, cv in config_thresholds.items():
                if ck not in mode_threshold_overrides:
                    mode_threshold_overrides[ck] = float(cv)
    except Exception:
        pass  # config not available, use CLI values only

    try:
        reports = run_review(
            paths=[path],
            playbook_path=resolved_playbook_path,
            extraction_model="extraction",
            qa_model=None,
            no_pii=no_pii,
            verbose=verbose,
            confidence_threshold=confidence_threshold,
            mode_threshold_overrides=mode_threshold_overrides,
            mode=mode,
        )
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2) from None

    _emit_reviews(
        reports,
        format,
        output,
        _privacy_footer() if not no_pii else None,
        memo_format,
        output_dir,
        mode=mode,
    )


if __name__ == "__main__":
    app()
