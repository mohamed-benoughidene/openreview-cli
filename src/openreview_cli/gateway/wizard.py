import json
from pathlib import Path
from typing import Any

import httpx
import yaml
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

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
    """Validate API key via model list endpoint or simple request."""
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
        # If any other code (e.g. 404 models endpoint not supported), assume key is acceptable
        return response.status_code not in {401, 403}
    except Exception:
        return False


class SetupWizard:
    """Interactive first-time setup wizard for the AI Gateway."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = config_dir or get_config_dir()
        self.console = Console()
        self.steps = ["reasoning", "extraction", "embedding", "graph"]
        self.slots_config: dict[str, dict[str, Any]] = {
            s: {"primary": "", "params": {}} for s in self.steps
        }
        self.api_keys: dict[str, str] = {}

        # Load existing config if available
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
        """Helper to apply reasoning slot provider/model to extraction and graph slots too."""
        model_str = f"{provider}/{model}"
        self.slots_config[slot]["primary"] = model_str
        if slot == "reasoning":
            self.slots_config["extraction"]["primary"] = model_str
            self.slots_config["graph"]["primary"] = model_str

    def run(self) -> None:
        """Run the interactive setup wizard."""
        self.console.print("\n[bold green]Welcome to OpenReview Gateway Setup![/bold green]")
        self.console.print(
            "Configure task-specific model slots. Type 'back' to go to the previous step, or 'cancel' to exit.\n"
        )

        step_idx = 0
        skipped_slots: set[str] = set()

        while step_idx < len(self.steps):
            slot = self.steps[step_idx]

            # If slot was configured via grouping, we can skip it
            if slot in skipped_slots:
                # Still allow user to confirm or override if going back/forward
                # but by default skip to next
                step_idx += 1
                continue

            self.console.print(
                f"\n[bold blue]Step {step_idx + 1} of {len(self.steps)}: Configuring '{slot}' slot[/bold blue]"
            )

            # 1. Ask for Provider
            providers = ["ollama", "openai", "anthropic", "cohere", "google", "custom"]
            provider_choices = list(providers)
            if step_idx > 0:
                provider_choices.append("back")
            provider_choices.append("cancel")

            current_primary = self.slots_config[slot].get("primary", "")
            default_provider = "ollama"
            if current_primary and "/" in current_primary:
                default_provider = current_primary.split("/")[0]

            provider_prompt = f"Select provider for {slot} slot"
            provider = (
                Prompt.ask(provider_prompt, choices=provider_choices, default=default_provider)
                .strip()
                .lower()
            )

            if provider == "cancel":
                if Confirm.ask(
                    "Cancel setup? Configured slots so far will be saved.", default=True
                ):
                    self.save()
                    self.console.print("[yellow]Setup cancelled. Progress saved.[/yellow]")
                    return
                continue
            elif provider == "back":
                # Go back, clearing any skipped slots if we go back past reasoning
                step_idx -= 1
                if step_idx == 0:
                    skipped_slots.clear()
                continue

            # 2. Ask for Model
            model = ""
            while not model:
                if provider == "ollama":
                    try:
                        self.console.print("[dim]Checking local Ollama models...[/dim]")
                        models = ollama_discover_models()
                        if not models:
                            self.console.print(
                                "[yellow]Ollama is running, but no models were found.[/yellow]"
                            )
                            self.console.print("Hint: Pull a model with 'ollama pull <model>'.")
                            choice = Prompt.ask(
                                "Enter model name manually, or go back?",
                                choices=["manual", "back"],
                                default="manual",
                            )
                            if choice == "back":
                                break
                            model = Prompt.ask("Enter Ollama model name (e.g. qwen3:8b)")
                        else:
                            model_names = [m.name for m in models]
                            model_choices = list(model_names)
                            model_choices.append("manual")
                            model_choices.append("back")

                            self.console.print("\nAvailable Ollama models:")
                            for m in models:
                                size_mb = (
                                    f"{m.size / (1024 * 1024):.0f} MB" if m.size else "unknown"
                                )
                                self.console.print(
                                    f" - [cyan]{m.name}[/cyan] ({size_mb}, parameter size: {m.parameter_size or 'unknown'})"
                                )

                            choice = Prompt.ask(
                                "Select a model", choices=model_choices, default=model_names[0]
                            )
                            if choice == "back":
                                break
                            elif choice == "manual":
                                model = Prompt.ask("Enter Ollama model name")
                            else:
                                model = choice
                    except OllamaNotRunningError:
                        self.console.print(
                            "[red]Ollama is not running.[/red] Hint: Start Ollama with 'ollama serve'."
                        )
                        choice = Prompt.ask(
                            "Retry discovery, enter model name manually, or go back?",
                            choices=["retry", "manual", "back"],
                            default="manual",
                        )
                        if choice == "back":
                            break
                        elif choice == "manual":
                            model = Prompt.ask("Enter Ollama model name")
                        else:
                            continue
                    except OllamaTimeoutError:
                        self.console.print("[red]Ollama connection timed out.[/red]")
                        choice = Prompt.ask(
                            "Retry discovery, enter model name manually, or go back?",
                            choices=["retry", "manual", "back"],
                            default="manual",
                        )
                        if choice == "back":
                            break
                        elif choice == "manual":
                            model = Prompt.ask("Enter Ollama model name")
                        else:
                            continue
                else:
                    # Slot-aware model list from registry
                    choices = get_models_for_slot(provider, slot)
                    model_choices = list(choices)
                    model_choices.append("manual")
                    model_choices.append("back")

                    if choices:
                        choice = Prompt.ask(
                            f"Select model for {provider}",
                            choices=model_choices,
                            default=choices[0],
                        )
                        if choice == "back":
                            break
                        elif choice == "manual":
                            model = Prompt.ask("Enter model ID")
                        else:
                            model = choice
                    else:
                        model = Prompt.ask(
                            f"Enter model ID for {provider} (or type 'back' to go back)"
                        )
                        if model == "back":
                            break

            if model == "back" or not model:
                # Re-loop this step/provider selection
                continue

            # 3. API Key Entry (if non-local)
            if provider != "ollama":
                # Check if API key is already configured
                existing_key = get_api_key(provider)
                if existing_key:
                    if Confirm.ask(
                        f"API key for '{provider}' is already configured. Reuse it?", default=True
                    ):
                        self.api_keys[provider] = existing_key
                    else:
                        self.api_keys[provider] = self._prompt_and_validate_key(provider)
                else:
                    self.api_keys[provider] = self._prompt_and_validate_key(provider)

            # Update slot primary
            self.slots_config[slot]["primary"] = f"{provider}/{model}"

            # 4. Slot Grouping
            if slot == "reasoning":
                if Confirm.ask(
                    "Apply this provider and model to extraction and graph slots too?", default=True
                ):
                    self.apply_grouping(provider, model, slot)
                    skipped_slots.add("extraction")
                    skipped_slots.add("graph")

            step_idx += 1

        # Ask about optional reranking slot
        if Confirm.ask(
            "Configure reranking slot? (optional, disabled by default — LightRAG graph retrieval is the precision filter)",
            default=False,
        ):
            self.steps.append("reranking")
            self.slots_config["reranking"] = {"primary": "", "params": {}}
            slot = "reranking"
            self.console.print(
                f"\n[bold blue]Step {len(self.steps)} of {len(self.steps)}: Configuring 'reranking' slot[/bold blue]"
            )
            providers = ["ollama", "openai", "anthropic", "cohere", "google", "custom"]
            provider = Prompt.ask(f"Select provider for reranking slot", choices=providers, default="ollama").strip().lower()
            model = ""
            while not model:
                if provider == "ollama":
                    try:
                        self.console.print("[dim]Checking local Ollama models...[/dim]")
                        models = ollama_discover_models()
                        if not models:
                            self.console.print("[yellow]No models found.[/yellow]")
                            model = Prompt.ask("Enter Ollama model name (e.g. qwen3-reranker)")
                        else:
                            model_names = [m.name for m in models]
                            self.console.print("\nAvailable Ollama models:")
                            for m in models:
                                size_mb = f"{m.size / (1024 * 1024):.0f} MB" if m.size else "unknown"
                                self.console.print(f" - [cyan]{m.name}[/cyan] ({size_mb})")
                            choice = Prompt.ask("Select a model", choices=model_names + ["manual"], default=model_names[0])
                            model = Prompt.ask("Enter Ollama model name") if choice == "manual" else choice
                    except (OllamaNotRunningError, OllamaTimeoutError):
                        self.console.print("[red]Ollama not reachable.[/red] Enter model name manually or skip.")
                        model = Prompt.ask("Enter Ollama model name (or leave empty to skip)")
                        if not model:
                            break
                else:
                    choices = get_models_for_slot(provider, slot)
                    if choices:
                        choice = Prompt.ask(f"Select model for {provider}", choices=choices + ["manual"], default=choices[0])
                        model = Prompt.ask("Enter model ID") if choice == "manual" else choice
                    else:
                        model = Prompt.ask(f"Enter model ID for {provider}")
                if model:
                    if provider != "ollama":
                        existing_key = get_api_key(provider)
                        if existing_key and Confirm.ask(f"Reuse existing API key for '{provider}'?", default=True):
                            self.api_keys[provider] = existing_key
                        else:
                            self.api_keys[provider] = self._prompt_and_validate_key(provider)
                    self.slots_config["reranking"]["primary"] = f"{provider}/{model}"

        self.save()
        self.show_summary()
        self.console.print(
            "\n[bold green]Gateway configuration completed successfully![/bold green]"
        )

    def _prompt_and_validate_key(self, provider: str) -> str:
        """Prompt user for API key and validate with retries and skip options."""
        while True:
            key = Prompt.ask(f"Enter API key for {provider}", password=True)
            self.console.print("[dim]Validating API key...[/dim]")

            # Try validating
            if validate_api_key(provider, key):
                self.console.print("[green]API key is valid![/green]")
                return key

            self.console.print("[red]API key validation failed or timed out.[/red]")
            if Confirm.ask("Retry validation?"):
                continue
            if Confirm.ask("Skip validation and save anyway?"):
                return key

    def save(self) -> None:
        """Save slot configuration to config.yml and keys to auth.json."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Save config.yml
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

        # Save auth.json
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
        """Display a summary table of the slot configuration."""
        self.console.print("\n[bold]Gateway Slot Assignment Summary:[/bold]")
        table = Table()
        table.add_column("Slot", style="cyan")
        table.add_column("Assigned Model", style="green")

        for slot in self.steps:
            model = self.slots_config[slot].get("primary", "unconfigured")
            table.add_row(slot, model)

        self.console.print(table)
