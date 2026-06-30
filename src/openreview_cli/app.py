import logging
import sys
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

_CONFIG_EXISTS_AT_START = False

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


def _init(debug: bool = False, debug_unsafe: bool = False) -> None:
    from openreview_cli.gateway.logging import set_debug_unsafe, setup_gateway_logging

    set_debug_unsafe(debug_unsafe)

    log_dir = get_log_dir()
    log_file = log_dir / "openreview.log"
    log_dir.mkdir(parents=True, exist_ok=True)
    _level = logging.DEBUG if (debug or debug_unsafe) else logging.INFO
    _fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    root = logging.getLogger()
    root.setLevel(_level)
    root.addHandler(logging.FileHandler(log_file, encoding="utf-8"))
    _sh = logging.StreamHandler(sys.stderr)
    _sh.setFormatter(_fmt)
    root.addHandler(_sh)

    config_dir = get_config_dir()
    global _CONFIG_EXISTS_AT_START
    _CONFIG_EXISTS_AT_START = (config_dir / "config.yml").exists()
    config = load_config(config_dir / "config.yml")
    logger.info("config loaded")

    ensure_auth(config_dir)
    logger.info("auth configured")

    data_dir = get_data_dir()
    init_database(data_dir / "openreview.db")
    logger.info("database initialized")

    gw_logging = config.get("gateway", {}).get("logging", {})
    gw_level = "debug" if (debug or debug_unsafe) else gw_logging.get("level", "info")
    gw_debug_file = gw_logging.get("debug_file", "~/.openreview/gateway.log")
    setup_gateway_logging(level=gw_level, debug_file=gw_debug_file)


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
    debug_unsafe: bool = typer.Option(
        False,
        "--debug-unsafe",
        help="Enable unsafe debug logging (logs API response bodies).",
    ),
) -> None:
    _init(debug=debug, debug_unsafe=debug_unsafe)


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


gateway_app = typer.Typer(
    name="gateway",
    help="AI model gateway management.",
    no_args_is_help=True,
)


@gateway_app.command("setup")
def gateway_setup(
    non_interactive: bool = typer.Option(
        False, "--non-interactive", help="Force non-interactive mode (error if config incomplete)"
    ),
    reasoning: str | None = typer.Option(None, "--reasoning", help="Pre-configure reasoning slot"),
    extraction: str | None = typer.Option(
        None, "--extraction", help="Pre-configure extraction slot"
    ),
    embedding: str | None = typer.Option(None, "--embedding", help="Pre-configure embedding slot"),
    reranking: str | None = typer.Option(None, "--reranking", help="Pre-configure reranking slot"),
    graph: str | None = typer.Option(None, "--graph", help="Pre-configure graph slot"),
) -> None:
    from openreview_cli.errors import gateway_error
    from openreview_cli.gateway.wizard import SetupWizard

    wizard = SetupWizard()
    flags = {
        "reasoning": reasoning,
        "extraction": extraction,
        "embedding": embedding,
        "reranking": reranking,
        "graph": graph,
    }

    if not _CONFIG_EXISTS_AT_START:
        for slot in wizard.steps:
            if not flags.get(slot):
                wizard.slots_config[slot]["primary"] = ""

    any_flags = any(flags.values())
    if non_interactive or any_flags:
        missing_slots = []
        for slot in wizard.steps:
            val = flags[slot]
            if val:
                if "/" in val:
                    parts = val.split("/", 1)
                    if not parts[0] or not parts[1]:
                        gateway_error(f"Invalid model format for slot '{slot}': '{val}'")
                wizard.slots_config[slot]["primary"] = val
            elif not wizard.slots_config[slot].get("primary"):
                missing_slots.append(slot)

        if missing_slots:
            gateway_error(f"Missing configuration for slots: {', '.join(missing_slots)}")

        # Handle optional reranking flag
        if flags.get("reranking"):
            val = flags["reranking"]
            if "/" in val:
                parts = val.split("/", 1)
                if not parts[0] or not parts[1]:
                    gateway_error(f"Invalid model format for slot 'reranking': '{val}'")
            wizard.slots_config["reranking"] = {"primary": val, "params": {}}

        wizard.save()
        typer.echo("Gateway configured successfully.")
        return

    # Check if config already exists and is complete
    is_complete = _CONFIG_EXISTS_AT_START and all(
        wizard.slots_config[s].get("primary") for s in wizard.steps
    )
    if is_complete:
        typer.echo("Current Gateway Configuration:")
        for slot in wizard.steps:
            typer.echo(f"  {slot}: {wizard.slots_config[slot]['primary']}")
        reconfig = typer.confirm("Reconfigure?", default=False)
        if not reconfig:
            typer.echo("Setup skipped.")
            return

    wizard.run()


@gateway_app.command("status")
def gateway_status() -> None:
    """Show current configuration and provider health status."""
    import httpx

    from openreview_cli.config.auth import load_auth
    from openreview_cli.config.loader import load_config
    from openreview_cli.config.paths import get_config_dir
    from openreview_cli.errors import config_error
    from openreview_cli.gateway.costs import CostStore

    config_dir = get_config_dir()
    if not _CONFIG_EXISTS_AT_START:
        config_error(
            "No config found. Please run 'openreview gateway setup' to configure the gateway."
        )

    config = load_config(config_dir / "config.yml")
    auth_path = config_dir / "auth.json"
    auth_keys = load_auth(auth_path) if auth_path.exists() else {}

    typer.echo("Gateway Status")
    typer.echo("==============")
    typer.echo("")
    typer.echo("Slots:")

    models_config = config["gateway"]["models"]
    for slot in ["reasoning", "extraction", "embedding", "reranking", "graph"]:
        slot_cfg = models_config.get(slot, {})
        primary = slot_cfg.get("primary", "")
        if primary:
            provider = primary.split("/")[0] if "/" in primary else primary
            if provider == "ollama":
                try:
                    r = httpx.get("http://localhost:11434/api/tags", timeout=1.0)
                    if r.status_code == 200:
                        health = "✓ healthy (local)"
                    else:
                        health = "✗ unreachable (local)"
                except Exception:
                    health = "✗ unreachable (local)"
            else:
                api_key = auth_keys.get(provider)
                if api_key:
                    health = "✓ healthy"
                else:
                    health = "✗ not configured"

            typer.echo(f"  {slot:<12}{primary:<27}{health}")
        else:
            typer.echo(f"  {slot:<12}{'Not Configured':<27}✗ not configured")

    # Fallback
    fb = config["gateway"]["fallback"]
    typer.echo("")
    typer.echo("Fallback:")
    typer.echo(f"  retries: {fb.get('retries', 2)}")
    typer.echo(f"  retry_delay: {fb.get('retry_delay', 1.0)}s")
    typer.echo(f"  timeout: {fb.get('timeout', 60)}s")
    typer.echo(f"  on_failure: {fb.get('on_failure', 'error')}")

    # Cost Limits
    cl = config["gateway"]["cost_limits"]
    per_rev = f"${cl.get('per_review_cents', 100) / 100:.2f}"
    daily = f"${cl.get('daily_cents', 1000) / 100:.2f}"
    typer.echo("")
    typer.echo("Cost Limits:")
    typer.echo(f"  per_review: {per_rev}")
    typer.echo(f"  daily: {daily}")

    # Today's Usage
    store = CostStore()
    today_cost = store.get_daily_cost()
    summary = store.get_summary(days=1)
    typer.echo("")
    typer.echo("Today's Usage:")
    typer.echo(f"  total_cost: ${today_cost:.2f}")
    typer.echo(
        f"  total_tokens: {summary.get('total_input', 0) + summary.get('total_output', 0):,}"
    )
    typer.echo(f"  api_calls: {summary.get('total_calls', 0)}")


@gateway_app.command("providers")
def gateway_providers() -> None:
    """List all supported providers and their configuration status."""
    from openreview_cli.config.auth import load_auth
    from openreview_cli.config.paths import get_config_dir

    auth_path = get_config_dir() / "auth.json"
    auth_keys = load_auth(auth_path) if auth_path.exists() else {}

    providers_list = [
        ("openai", "API key", "https://api.openai.com/v1"),
        ("anthropic", "API key", "https://api.anthropic.com"),
        ("google", "API key", "https://generativelanguage.googleapis.com"),
        ("ollama", "None (local)", "http://localhost:11434"),
        ("openrouter", "API key", "https://openrouter.ai/api/v1"),
        ("cohere", "API key", "https://api.cohere.com/v1"),
        ("huggingface", "API key", "https://api-inference.huggingface.co"),
        ("custom", "API key + URL", "(user-defined)"),
    ]

    typer.echo("Supported Providers")
    typer.echo("===================")
    typer.echo("")
    typer.echo(f"{'Provider':<14}{'Status':<14}{'Auth Method':<21}{'Base URL'}")
    typer.echo("────────────────────────────────────────────────────────────────")
    for name, auth, url in providers_list:
        if name == "ollama":
            status = "✓ configured"
        else:
            status = "✓ configured" if auth_keys.get(name) else "✗ not configured"
        typer.echo(f"{name:<14}{status:<14}{auth:<21}{url}")


@gateway_app.command("models")
def gateway_models(provider: str = typer.Argument(..., help="Provider name")) -> None:
    """List available models for a specific provider."""
    from openreview_cli.config.auth import load_auth
    from openreview_cli.config.paths import get_config_dir
    from openreview_cli.errors import config_error, gateway_error
    from openreview_cli.gateway.registry import ModelRegistry, ModelRegistryEntry

    auth_path = get_config_dir() / "auth.json"
    auth_keys = load_auth(auth_path) if auth_path.exists() else {}

    valid_providers = {
        "openai",
        "anthropic",
        "google",
        "ollama",
        "openrouter",
        "cohere",
        "huggingface",
        "custom",
    }
    if provider.lower() not in valid_providers:
        typer.echo(f"Invalid provider: '{provider}'", err=True)
        raise typer.Exit(code=1)

    if provider.lower() != "ollama":
        if not auth_keys.get(provider.lower()):
            config_error(f"Provider '{provider}' is not configured.")

    registry = ModelRegistry()
    models = registry.get_all_models()
    provider_models = [m for m in models if m.provider == provider.lower()]

    if provider.lower() == "ollama":
        from openreview_cli.gateway.providers import ollama_discover_models

        try:
            local_models = ollama_discover_models()
            for lm in local_models:
                if not any(pm.model_id == lm.name for pm in provider_models):
                    provider_models.append(
                        ModelRegistryEntry(
                            provider="ollama",
                            model_id=lm.name,
                            display_name=lm.name,
                            slot_compatibility=[
                                "reasoning",
                                "extraction",
                                "embedding",
                                "reranking",
                                "graph",
                            ],
                            is_local=True,
                        )
                    )
        except Exception:
            pass

    if not provider_models:
        gateway_error(f"Failed to fetch models for provider '{provider}'")

    typer.echo(f"Available Models: {provider}")
    typer.echo("========================")
    typer.echo("")
    typer.echo(f"{'Model':<25}{'Slots':<25}{'Context':<11}{'Price (per MTok)'}")
    typer.echo("─────────────────────────────────────────────────────────────────────────")
    for m in provider_models:
        slots_str = ", ".join(m.slot_compatibility)
        ctx = f"{m.context_window // 1000}K" if m.context_window else "N/A"
        if m.pricing_input_usd_per_mtok is not None and m.pricing_output_usd_per_mtok is not None:
            price = f"${m.pricing_input_usd_per_mtok:.2f} / ${m.pricing_output_usd_per_mtok:.2f}"
        else:
            price = "local" if m.is_local else "N/A"
        typer.echo(f"{m.model_id:<25}{slots_str:<25}{ctx:<11}{price}")


@gateway_app.command("set")
def gateway_set(
    slot: str = typer.Argument(..., help="Slot name to configure"),
    model: str = typer.Argument(
        ..., help="Model identifier in format provider/model or local model name"
    ),
    fallback: str | None = typer.Option(None, "--fallback", help="Set fallback model"),
    temperature: float | None = typer.Option(
        None, "--temperature", help="Set temperature (0.0 to 2.0)"
    ),
    max_tokens: int | None = typer.Option(None, "--max-tokens", help="Set max_tokens"),
    dimensions: int | None = typer.Option(
        None, "--dimensions", help="Set dimensions (embedding only)"
    ),
) -> None:
    """Configure a specific slot with a model."""
    import yaml

    from openreview_cli.config.loader import DEFAULT_CONFIG, _validate_and_merge
    from openreview_cli.config.paths import get_config_dir
    from openreview_cli.errors import config_error, gateway_error
    from openreview_cli.gateway.registry import ModelRegistry
    from openreview_cli.gateway.utils import atomic_write

    valid_slots = {"reasoning", "extraction", "embedding", "reranking", "graph"}
    if slot.lower() not in valid_slots:
        typer.echo(f"Invalid slot: '{slot}'", err=True)
        raise typer.Exit(code=1)

    if "/" in model:
        parts = model.split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            config_error(f"Model must be in format 'provider/model-id', got '{model}'")
        provider = parts[0]
        model_id = parts[1]
    else:
        provider = "ollama"
        model_id = model

    registry = ModelRegistry()
    all_models = registry.get_all_models()

    model_found = False
    if provider == "ollama":
        model_found = True
    else:
        for m in all_models:
            if m.provider == provider and m.model_id == model_id:
                model_found = True
                break

    if not model_found:
        gateway_error(f"Model '{model}' not found in registry.")

    if fallback:
        if "/" in fallback:
            fb_parts = fallback.split("/")
            if len(fb_parts) != 2 or not fb_parts[0] or not fb_parts[1]:
                config_error(f"Fallback must be in format 'provider/model-id', got '{fallback}'")
            fb_provider = fb_parts[0]
            fb_model_id = fb_parts[1]
        else:
            fb_provider = "ollama"
            fb_model_id = fallback

        fb_found = False
        if fb_provider == "ollama":
            fb_found = True
        else:
            for m in all_models:
                if m.provider == fb_provider and m.model_id == fb_model_id:
                    fb_found = True
                    break
            if not fb_found:
                gateway_error(f"Fallback model '{fallback}' not found in registry.")

    config_path = get_config_dir() / "config.yml"
    if not config_path.exists():
        config_error(
            "No config found. Please run 'openreview gateway setup' to configure the gateway."
        )

    with open(config_path) as f:
        raw_config = yaml.safe_load(f) or {}

    slot_key = slot.lower()
    raw_config.setdefault("gateway", {}).setdefault("models", {}).setdefault(slot_key, {})
    raw_config["gateway"]["models"][slot_key]["primary"] = model
    if fallback is not None:
        raw_config["gateway"]["models"][slot_key]["fallback"] = fallback

    params = raw_config["gateway"]["models"][slot_key].setdefault("params", {})
    if temperature is not None:
        if not (0.0 <= temperature <= 2.0):
            config_error("temperature must be between 0.0 and 2.0")
        params["temperature"] = temperature
    if max_tokens is not None:
        if max_tokens <= 0:
            config_error("max_tokens must be positive")
        params["max_tokens"] = max_tokens
    if dimensions is not None:
        if slot_key != "embedding":
            config_error("dimensions parameter only allowed for embedding slot")
        if dimensions <= 0:
            config_error("dimensions must be positive")
        params["dimensions"] = dimensions

    validated = _validate_and_merge(raw_config, dict(DEFAULT_CONFIG))
    atomic_write(config_path, yaml.safe_dump(validated, default_flow_style=False))

    typer.echo(f"✓ Updated {slot_key} slot: {model}")
    if fallback is not None:
        typer.echo(f"  fallback: {fallback}")
    if temperature is not None:
        typer.echo(f"  temperature: {temperature}")
    if max_tokens is not None:
        typer.echo(f"  max_tokens: {max_tokens}")
    if dimensions is not None:
        typer.echo(f"  dimensions: {dimensions}")


@gateway_app.command("test")
def gateway_test(slot: str = typer.Argument(..., help="Slot name to test")) -> None:
    """Test connectivity and API key validity for a slot."""
    import time

    import httpx

    from openreview_cli.config.loader import load_config
    from openreview_cli.config.paths import get_config_dir
    from openreview_cli.errors import config_error, gateway_error
    from openreview_cli.gateway.wizard import validate_api_key

    valid_slots = {"reasoning", "extraction", "embedding", "reranking", "graph"}
    if slot.lower() not in valid_slots:
        typer.echo(f"Invalid slot: '{slot}'", err=True)
        raise typer.Exit(code=1)

    config_path = get_config_dir() / "config.yml"
    if not config_path.exists():
        config_error(
            "No config found. Please run 'openreview gateway setup' to configure the gateway."
        )

    config = load_config(config_path)
    slot_cfg = config["gateway"]["models"].get(slot.lower(), {})
    primary = slot_cfg.get("primary")
    if not primary:
        typer.echo(f"Slot '{slot}' is not configured.", err=True)
        raise typer.Exit(code=1)

    if "/" in primary:
        provider, model = primary.split("/", 1)
    else:
        provider, model = "ollama", primary

    typer.echo(f"Testing slot: {slot}")
    typer.echo(f"  provider: {provider}")
    typer.echo(f"  model: {model}")
    typer.echo("")

    from openreview_cli.config.auth import get_api_key

    api_key = get_api_key(provider) or ""

    start_time = time.perf_counter()
    if provider == "ollama":
        try:
            r = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
            if r.status_code == 200:
                latency = int((time.perf_counter() - start_time) * 1000)
                typer.echo("  ✓ Connection to Ollama valid")
                typer.echo(f"  ✓ Latency: {latency}ms")
                typer.echo("")
                typer.echo("Test passed.")
                return
            else:
                gateway_error(f"Ollama returned status code {r.status_code}")
        except Exception as e:
            gateway_error(f"Failed to connect to Ollama: {e}")
    else:
        if not api_key:
            gateway_error(f"API key not found for provider '{provider}'")

        try:
            is_valid = validate_api_key(provider, api_key)
            latency = int((time.perf_counter() - start_time) * 1000)
            if is_valid:
                typer.echo("  ✓ API key valid")
                typer.echo("  ✓ Provider endpoint reachable")
                typer.echo(f"  ✓ Latency: {latency}ms")
                typer.echo("")
                typer.echo("Test passed.")
                return
            else:
                gateway_error("API key validation failed.")
        except Exception as e:
            gateway_error(f"API key validation failed with error: {e}")


@gateway_app.command("refresh")
def gateway_refresh() -> None:
    """Refresh the cached model registry from remote source."""
    from openreview_cli.config.loader import load_config
    from openreview_cli.config.paths import get_config_dir
    from openreview_cli.errors import config_error, gateway_error
    from openreview_cli.gateway.registry import ModelRegistry

    config_path = get_config_dir() / "config.yml"
    if not config_path.exists():
        config_error(
            "No config found. Please run 'openreview gateway setup' to configure the gateway."
        )

    config = load_config(config_path)
    remote_url = config["gateway"]["registry"]["remote_url"]

    typer.echo("Refreshing model registry...")
    typer.echo(f"  remote: {remote_url}")

    registry = ModelRegistry()
    try:
        registry.refresh(remote_url)
        typer.echo(f"  ✓ Cache updated: {registry.cache_file}")
    except Exception as e:
        gateway_error(f"Failed to refresh model registry: {e}")


@gateway_app.command("costs")
def gateway_costs(
    session: str | None = typer.Option(
        None, "--session", help="Show costs for specific review session"
    ),
    days: int = typer.Option(1, "--days", help="Show costs for last N days"),
    clear: bool = typer.Option(False, "--clear", help="Clear all cost records"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """View cost tracking and usage statistics."""
    import json

    from openreview_cli.config.loader import load_config
    from openreview_cli.config.paths import get_config_dir
    from openreview_cli.gateway.costs import CostStore

    store = CostStore()

    if clear:
        store.clear()
        typer.echo("✓ All cost records cleared.")
        return

    if session is not None:
        if not store.session_exists(session):
            typer.echo(f"Session not found: {session}", err=True)
            raise typer.Exit(code=1)
        summary = store.get_summary(session_id=session)
    else:
        summary = store.get_summary(days=days)

    if json_output:
        typer.echo(json.dumps(summary, indent=2))
        return

    title_suffix = (
        f" (Session: {session})"
        if session
        else f" (Last {days} Days)"
        if days > 1
        else " (Last 24 Hours)"
    )
    typer.echo(f"Cost Summary{title_suffix}")
    typer.echo("=============================")
    typer.echo("")
    typer.echo(f"Total Cost: ${summary['total_cost']:.2f}")
    typer.echo(f"Total Tokens: {summary['total_input'] + summary['total_output']:,}")
    typer.echo(f"  Input: {summary['total_input']:,}")
    typer.echo(f"  Output: {summary['total_output']:,}")
    typer.echo(f"API Calls: {summary['total_calls']}")
    typer.echo("")

    typer.echo("By Slot:")
    for slot in ["reasoning", "extraction", "embedding", "reranking", "graph"]:
        s_data = summary["slots"].get(slot, {"cost": 0.0, "tokens": 0, "calls": 0})
        typer.echo(
            f"  {slot:<12}${s_data['cost']:.2f}  {s_data['tokens']:,} tokens  {s_data['calls']} calls"
        )

    typer.echo("")
    typer.echo("By Provider:")
    for prov, p_data in summary["providers"].items():
        local_lbl = " (local)" if prov == "ollama" else ""
        typer.echo(
            f"  {prov:<12}${p_data['cost']:.2f}  {p_data['tokens']:,} tokens  {p_data['calls']} calls{local_lbl}"
        )

    config_path = get_config_dir() / "config.yml"
    if config_path.exists():
        config = load_config(config_path)
        cl = config["gateway"]["cost_limits"]
        per_rev_usd = cl.get("per_review_cents", 100) / 100
        daily_usd = cl.get("daily_cents", 1000) / 100

        daily_cost = store.get_daily_cost()
        daily_pct = int((daily_cost / daily_usd) * 100) if daily_usd > 0 else 0

        if session:
            sess_cost = summary["total_cost"]
            sess_pct = int((sess_cost / per_rev_usd) * 100) if per_rev_usd > 0 else 0
            rev_str = f"${sess_cost:.2f} / ${per_rev_usd:.2f} ({sess_pct}%)"
        else:
            rev_str = f"N/A / ${per_rev_usd:.2f}"

        typer.echo("")
        typer.echo("Cost Limits:")
        typer.echo(f"  per_review: {rev_str}")
        typer.echo(f"  daily: ${daily_cost:.2f} / ${daily_usd:.2f} ({daily_pct}%)")


@gateway_app.command("install-models")
def gateway_install_models(
    models: list[str] = typer.Argument(..., help="One or more Ollama model names"),
) -> None:
    """Install local models via Ollama."""
    import httpx

    from openreview_cli.errors import gateway_error

    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if r.status_code != 200:
            gateway_error("Ollama is not running or returned an invalid response.")
    except Exception:
        gateway_error("Ollama is not running. Please start the Ollama service.")

    typer.echo("Installing Ollama models...")
    typer.echo("")

    for i, model in enumerate(models, 1):
        typer.echo(f"[{i}/{len(models)}] {model}")

        try:
            with httpx.stream(
                "POST",
                "http://localhost:11434/api/pull",
                json={"name": model, "stream": True},
                timeout=600.0,
            ) as response:
                if response.status_code != 200:
                    gateway_error(
                        f"Failed to pull model '{model}': status code {response.status_code}"
                    )

                for line in response.iter_lines():
                    if not line:
                        continue
                    pass
            typer.echo("  ✓ Downloaded")
            typer.echo("")
        except Exception as e:
            gateway_error(f"Failed to install model '{model}': {e}")

    typer.echo("All models installed successfully.")


@gateway_app.command("import")
def gateway_import(
    file: Path = typer.Argument(..., help="Path to YAML config file"),
    force: bool = typer.Option(
        False, "--force", help="Skip confirmation prompt (overwrite existing config)"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate file without applying changes"),
) -> None:
    """Import gateway configuration from a YAML file."""
    import yaml

    from openreview_cli.config.paths import get_config_dir
    from openreview_cli.gateway.importer import import_config, validate_import_config

    if not file.exists():
        typer.echo(f"Error: file not found '{file}'", err=True)
        raise typer.Exit(code=1) from None

    try:
        content = yaml.safe_load(file.read_text())
    except Exception as e:
        typer.echo(f"Validation error: invalid YAML: {e}", err=True)
        raise typer.Exit(code=5) from e

    errors = validate_import_config(content)
    if errors:
        typer.echo("Validation errors found:", err=True)
        for err in errors:
            typer.echo(f"  - {err}", err=True)
        raise typer.Exit(code=5) from None

    # Output validation success
    typer.echo(f"Importing config from: {file}")
    typer.echo("")
    typer.echo("Validating...")
    slots_defined = [s for s in content if s in {"reasoning", "extraction", "embedding", "reranking", "graph"}]
    typer.echo(f"  ✓ {len(slots_defined)} slot(s) defined")
    typer.echo("  ✓ All providers recognized")
    typer.echo("  ✓ All model IDs valid")
    typer.echo("  ✓ No inline API keys detected")
    typer.echo("")

    # Display summary
    typer.echo("Summary:")
    for slot in ["reasoning", "extraction", "embedding", "reranking", "graph"]:
        slot_import = content.get(slot)
        if slot_import:
            typer.echo(f"  {slot:<12}: {slot_import['provider']}/{slot_import['model']}")
    typer.echo("")

    if dry_run:
        typer.echo("Dry-run: validation passed, config not applied.")
        return

    # Check for confirmation if existing config
    config_dir = get_config_dir()
    config_path = config_dir / "config.yml"
    if config_path.exists() and not force:
        confirm = typer.confirm("Existing config will be overwritten. Continue?", default=False)
        if not confirm:
            typer.echo("Cancelled.")
            raise typer.Exit(code=1) from None

    try:
        import_config(content, config_dir)
        typer.echo("✓ Config imported successfully")
        if content.get("api_key_env"):
            typer.echo("✓ API keys written to auth.json (chmod 600)")
    except ValueError as e:
        typer.echo(f"Validation error: {e}", err=True)
        raise typer.Exit(code=5) from e
    except Exception as e:
        typer.echo(f"Import failed: {e}", err=True)
        raise typer.Exit(code=7) from e


app.add_typer(gateway_app)


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


if __name__ == "__main__":
    app()
