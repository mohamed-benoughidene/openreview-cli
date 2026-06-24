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


if __name__ == "__main__":
    app()
