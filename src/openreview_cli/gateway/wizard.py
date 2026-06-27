import json
from pathlib import Path
from typing import Any

import httpx
import yaml
from rich.console import Console
from rich.table import Table

from openreview_cli.cli.utils import _confirm, _is_interactive, _password, _select, _text
from openreview_cli.config.auth import get_api_base, get_api_key
from openreview_cli.config.loader import load_config
from openreview_cli.config.paths import get_config_dir
from openreview_cli.gateway.providers import (
    OllamaNotRunningError,
    OllamaTimeoutError,
    ollama_discover_models,
)
from openreview_cli.gateway.registry import get_models_for_slot
from openreview_cli.gateway.utils import atomic_write


def validate_api_key(provider: str, api_key: str, timeout_seconds: float = 10.0) -> bool:
    url = ""
    headers = {}
    params = {}

    prov = provider.lower()
    if prov == "openai":
        url = "https://api.openai.com/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
    elif prov == "anthropic":
        url = "https://api.anthropic.com/v1/models"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    elif prov == "cohere":
        url = "https://api.cohere.com/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
    elif prov == "openrouter":
        url = "https://openrouter.ai/api/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
    elif prov == "google":
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        params = {"key": api_key}
    elif prov == "huggingface":
        url = "https://api-inference.huggingface.co/models/gpt2"
        headers = {"Authorization": f"Bearer {api_key}"}
    elif prov == "custom":
        base_url = get_api_base("custom")
        if base_url:
            url = f"{base_url.rstrip('/')}/models"
        else:
            url = "http://localhost:8000/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
    else:
        return True

    try:
        timeout = httpx.Timeout(timeout=timeout_seconds, connect=5.0)
        response = httpx.get(url, headers=headers, params=params, timeout=timeout)
        if response.status_code in (200, 201):
            return True
        if response.status_code in (401, 403):
            return False
        return response.status_code not in {401, 403}
    except Exception:
        return False


class SetupWizard:
    """Interactive first-time setup wizard for the AI Gateway."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = config_dir or get_config_dir()
        self.console = Console()
        self.steps = ["reasoning", "extraction", "embedding", "reranking", "graph"]
        self.slots_config: dict[str, dict[str, Any]] = {
            s: {"primary": "", "params": {}} for s in self.steps
        }
        self.api_keys: dict[str, str] = {}

        self.config_path = self.config_dir / "config.yml"
        if self.config_path.exists():
            try:
                config_data = load_config(self.config_path)
                models_data = config_data.get("gateway", {}).get("models", {})
                for slot in self.steps:
                    if slot in models_data:
                        self.slots_config[slot]["primary"] = models_data[slot].get("primary", "")
                        self.slots_config[slot]["params"] = models_data[slot].get("params", {})
            except Exception:
                pass

    def apply_grouping(self, provider: str, model: str, slot: str) -> None:
        model_str = f"{provider}/{model}"
        self.slots_config[slot]["primary"] = model_str
        if slot == "reasoning":
            self.slots_config["extraction"]["primary"] = model_str
            self.slots_config["graph"]["primary"] = model_str

    def run(self) -> None:
        if not _is_interactive():
            self.console.print(
                "[yellow]Non-interactive terminal detected. Use --non-interactive flag or run in a terminal.[/yellow]"
            )
            return

        self.console.print("\n[bold green]Welcome to OpenReview Gateway Setup![/bold green]")

        step_idx = 0
        skipped_slots: set[str] = set()

        while step_idx < len(self.steps):
            slot = self.steps[step_idx]

            if slot in skipped_slots:
                step_idx += 1
                continue

            self.console.print(
                f"\n[bold blue]Step {step_idx + 1} of 5: Configuring '{slot}' slot[/bold blue]"
            )

            provider = self._select_provider(slot, step_idx)
            if provider is None:
                if step_idx > 0:
                    step_idx -= 1
                    if step_idx == 0:
                        skipped_slots.clear()
                    continue
                return

            model = self._select_model(slot, provider)
            if model is None:
                continue

            if provider != "ollama":
                existing_key = get_api_key(provider)
                if existing_key:
                    reuse = _confirm(f"API key for '{provider}' is already configured. Reuse it?")
                    if reuse:
                        self.api_keys[provider] = existing_key
                    else:
                        self.api_keys[provider] = self._prompt_and_validate_key(provider)
                else:
                    self.api_keys[provider] = self._prompt_and_validate_key(provider)

            self.slots_config[slot]["primary"] = f"{provider}/{model}"

            if slot == "reasoning":
                group = _confirm("Apply this provider and model to extraction and graph slots too?")
                if group:
                    self.apply_grouping(provider, model, slot)
                    skipped_slots.add("extraction")
                    skipped_slots.add("graph")

            step_idx += 1

        self.show_summary()
        confirm = _confirm("Save this configuration?")
        if confirm:
            self.save()
            self.console.print(
                "\n[bold green]Gateway configuration completed successfully![/bold green]"
            )
        else:
            self.console.print("\n[yellow]Setup cancelled. No changes saved.[/yellow]")

    def _select_provider(self, slot: str, step_idx: int) -> str | None:
        providers = ["ollama", "openai", "anthropic", "cohere", "google", "custom"]
        choices = list(providers)
        if step_idx > 0:
            choices.append("← Back")

        current_primary = self.slots_config[slot].get("primary", "")
        default_provider = "ollama"
        if current_primary and "/" in current_primary:
            default_provider = current_primary.split("/")[0]

        result = _select(
            f"Select provider for {slot} slot",
            choices=choices,
            default=default_provider,
        )
        if result == "← Back":
            return None
        return result

    def _select_model(self, slot: str, provider: str) -> str | None:
        if provider == "ollama":
            return self._select_ollama_model()
        # Slot-aware model list from registry
        choices = list(get_models_for_slot(provider, slot))
        model_choices = [*list(choices), "manual"]
        if choices:
            choice = _select(
                f"Select model for {provider}",
                choices=model_choices,
                default=choices[0],
            )
            if choice == "manual":
                return _text("Enter model ID")
            return choice
        return _text(f"Enter model ID for {provider}")

    def _select_ollama_model(self) -> str | None:
        try:
            self.console.print("[dim]Checking local Ollama models...[/dim]")
            models = ollama_discover_models()
            if not models:
                self.console.print("[yellow]Ollama is running, but no models were found.[/yellow]")
                self.console.print("Hint: Pull a model with 'ollama pull <model>'.")
                return _text("Enter Ollama model name (e.g. qwen3:8b)")
            model_names = [m.name for m in models]
            self.console.print("\nAvailable Ollama models:")
            for m in models:
                size_mb = f"{m.size / (1024 * 1024):.0f} MB" if m.size else "unknown"
                self.console.print(
                    f" - [cyan]{m.name}[/cyan] ({size_mb}, parameter size: {m.parameter_size or 'unknown'})"
                )
            choices = [*model_names, "manual"]
            choice = _select("Select a model", choices=choices, default=model_names[0])
            if choice == "manual":
                return _text("Enter Ollama model name")
            return choice
        except OllamaNotRunningError:
            self.console.print(
                "[red]Ollama is not running.[/red] Hint: Start Ollama with 'ollama serve'."
            )
            return _text("Enter Ollama model name")
        except OllamaTimeoutError:
            self.console.print("[red]Ollama connection timed out.[/red]")
            return _text("Enter Ollama model name")

    def _prompt_and_validate_key(self, provider: str) -> str:
        while True:
            key = _password(f"Enter API key for {provider}")
            if key is None:
                return ""
            self.console.print("[dim]Validating API key...[/dim]")
            if validate_api_key(provider, key):
                self.console.print("[green]API key is valid![/green]")
                return key
            self.console.print("[red]API key validation failed or timed out.[/red]")
            retry = _confirm("Retry validation?")
            if retry:
                continue
            skip = _confirm("Skip validation and save anyway?")
            if skip:
                return key

    def save(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)

        config_data = {}
        if self.config_path.exists():
            try:
                config_data = load_config(self.config_path)
            except Exception:
                pass

        if "gateway" not in config_data:
            config_data["gateway"] = {}
        if "models" not in config_data["gateway"]:
            config_data["gateway"]["models"] = {}

        for slot, conf in self.slots_config.items():
            if conf["primary"]:
                config_data["gateway"]["models"][slot] = conf

        yaml_str = yaml.safe_dump(config_data, default_flow_style=False)
        atomic_write(self.config_path, yaml_str)

        auth_path = self.config_dir / "auth.json"
        auth_data = {}
        if auth_path.exists():
            try:
                auth_data = json.loads(auth_path.read_text())
            except Exception:
                pass

        for provider, key in self.api_keys.items():
            auth_data[provider] = key

        auth_str = json.dumps(auth_data, indent=2)
        atomic_write(auth_path, auth_str)
        try:
            auth_path.chmod(0o600)
        except Exception:
            pass

    def show_summary(self) -> None:
        self.console.print("\n[bold]Gateway Slot Assignment Summary:[/bold]")
        table = Table()
        table.add_column("Slot", style="cyan")
        table.add_column("Assigned Model", style="green")

        for slot in self.steps:
            model = self.slots_config[slot].get("primary", "unconfigured")
            table.add_row(slot, model)

        self.console.print(table)
