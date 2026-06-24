import logging

import typer

from openreview_cli._version import __version__

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
    from openreview_cli.config.auth import ensure_auth
    from openreview_cli.config.loader import load_config
    from openreview_cli.config.paths import get_config_dir, get_data_dir, get_log_dir
    from openreview_cli.logging_config import setup_logging
    from openreview_cli.storage.database import init_database

    log_dir = get_log_dir()
    setup_logging(log_dir, debug=debug)

    config_dir = get_config_dir()
    load_config(config_dir / "config.yml")
    logger.info("config loaded")

    ensure_auth(config_dir)
    logger.info("auth configured")

    data_dir = get_data_dir()
    init_database(data_dir / "openreview.db")
    logger.info("database initialized")


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
    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.errors import config_error
    from openreview_cli.storage.database import add_client

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

    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.storage.database import get_connection

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
    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.errors import config_error
    from openreview_cli.storage.database import client_has_reviews, delete_client

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

    from openreview_cli.config.loader import load_config
    from openreview_cli.config.paths import get_config_dir

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
    from openreview_cli.config.loader import get_config_value, load_config
    from openreview_cli.config.paths import get_config_dir
    from openreview_cli.errors import config_error

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

    from openreview_cli.config.loader import set_config_value
    from openreview_cli.config.paths import get_config_dir
    from openreview_cli.errors import config_error

    config_path = get_config_dir() / "config.yml"

    try:
        set_config_value(config_path, key, value)
        typer.echo(f"updated {key} = {value}")
    except (KeyError, ValidationError) as e:
        config_error(str(e))


app.add_typer(config_app)

if __name__ == "__main__":
    app()
