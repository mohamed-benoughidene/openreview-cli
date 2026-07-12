from __future__ import annotations

import contextlib
from pathlib import Path

import yaml

from openreview_cli.prompts.store import PromptStore

DEFAULTS_DIR = Path(__file__).parent / "defaults"


def load_defaults(store: PromptStore) -> None:
    if store.list():
        return
    for yaml_path in sorted(DEFAULTS_DIR.glob("*.yaml")):
        data = yaml.safe_load(yaml_path.read_text())
        for v in data.get("versions", []):
            with contextlib.suppress(ValueError):
                store.create(
                    data["name"],
                    v["content"],
                    tags=v.get("metadata", {}).get("tags"),
                    description=v.get("metadata", {}).get("description"),
                )
