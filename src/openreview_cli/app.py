import logging
import sys
from datetime import UTC
from pathlib import Path

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

app = typer.Typer(
    name="openreview",
    help="Privacy-first contract review tool.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        _init()
        typer.echo(f"openreview {__version__}")
        raise typer.Exit()


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


@app.callback()
def _root(
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


@app.command()
def precheck(
    document_path: str = typer.Argument(..., help="Path to a PDF or DOCX contract file."),
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
) -> None:
    """Run a PreCheck review (NDA analysis) on a document.

    Automatically strips PII before processing unless --no-pii is specified.
    """

    from openreview_cli.pii.models import PartialProcessingError
    from openreview_cli.review.base import ReviewCommand

    if no_pii and pii_threshold is not None:
        typer.echo("Error: --no-pii and --pii-threshold are mutually exclusive", err=True)
        raise typer.Exit(code=3)

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
def gateway_providers() -> None:
    """List all supported providers."""
    from rich.console import Console
    from rich.table import Table

    from openreview_cli.gateway.registry import ModelRegistry

    registry = ModelRegistry(_GATEWAY_REGISTRY_PATH)
    registry.load()

    console = Console()
    table = Table(title="Supported Providers")
    table.add_column("Name", style="cyan")
    table.add_column("Auth", style="green")
    table.add_column("Models", style="white")

    for p in registry.list_providers():
        table.add_row(
            p["name"],
            "key required" if p["auth_required"] else "none",
            str(p["model_count"]),
        )
    console.print(table)


@gateway_app.command("models")
def gateway_models(provider: str) -> None:
    """List available models for a provider."""
    from rich.console import Console
    from rich.table import Table

    from openreview_cli.gateway.registry import ModelRegistry

    registry = ModelRegistry(_GATEWAY_REGISTRY_PATH)
    registry.load()

    models = registry.list_models(provider)
    if provider.lower() == "ollama":
        dynamic = registry.discover_ollama()
        seen = {m["model_id"] for m in models}
        for m in dynamic:
            if m["model_id"] not in seen:
                models.append(m)
                seen.add(m["model_id"])

    if not models:
        typer.echo(f"No models found for provider '{provider}'.")
        return

    console = Console()
    table = Table(title=f"Models for {provider}")
    table.add_column("Model ID", style="cyan")
    table.add_column("Slots", style="green")
    table.add_column("Context", style="white")
    table.add_column("Recommended", style="yellow")

    for m in models:
        table.add_row(
            m["model_id"],
            ", ".join(m.get("slots", [])),
            str(m.get("context", "-")),
            "✓" if m.get("recommended") else "",
        )
    console.print(table)


@gateway_app.command("set")
def gateway_set(slot: str, model: str) -> None:
    """Assign a model to a slot."""
    from openreview_cli.config.loader import set_config_value
    from openreview_cli.config.paths import get_config_dir
    from openreview_cli.gateway.router import VALID_SLOTS

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
    from openreview_cli.gateway.router import VALID_SLOTS, Gateway

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


app.add_typer(gateway_app)

if __name__ == "__main__":
    app()
