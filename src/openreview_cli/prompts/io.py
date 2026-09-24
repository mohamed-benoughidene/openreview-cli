from __future__ import annotations

from typing import Any

import yaml


def parse_prompts_yaml(text: str) -> list[dict[str, Any]]:
    """Parse a prompt-import YAML document into a list of prompt mappings.

    Validates **structure only** - never content size, which is the store's rule
    (``PromptStore.import_prompt`` accepts up to 16384 characters). Raises
    ``ValueError`` naming the offending prompt or entry.
    """
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML: {exc}") from exc

    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError(  # noqa: TRY004 - callers catch ValueError, not TypeError
            f"Prompt import document must be a mapping or a list, got {type(data).__name__}"
        )

    return [_validate_item(index, item) for index, item in enumerate(data)]


def _validate_item(index: int, item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(  # noqa: TRY004 - callers catch ValueError, not TypeError
            f"Prompt import entry {index} is not a mapping, got {type(item).__name__}"
        )
    if "name" not in item:
        raise ValueError(f"Prompt import entry {index} is missing 'name'")
    name = item["name"]
    if "versions" not in item:
        raise ValueError(f"Prompt '{name}' is missing 'versions'")
    versions = item["versions"]
    if versions is None:
        raise ValueError(f"Prompt '{name}' has null 'versions'")
    if not isinstance(versions, list):
        raise ValueError(  # noqa: TRY004 - callers catch ValueError, not TypeError
            f"Prompt '{name}' has a non-list 'versions' value, got {type(versions).__name__}"
        )
    if not versions:
        raise ValueError(f"Prompt '{name}' has an empty 'versions' list")

    seen_versions: set[Any] = set()
    for version_index, version in enumerate(versions):
        _validate_version(name, version_index, version, seen_versions)
    return item


def _validate_version(name: str, index: int, version: Any, seen_versions: set[Any]) -> None:
    if not isinstance(version, dict):
        raise ValueError(  # noqa: TRY004 - callers catch ValueError, not TypeError
            f"Prompt '{name}' version entry {index} is not a mapping, got {type(version).__name__}"
        )
    if "content" not in version:
        raise ValueError(f"Prompt '{name}' version entry {index} is missing 'content'")
    if "created_at" not in version:
        raise ValueError(f"Prompt '{name}' version entry {index} is missing 'created_at'")
    version_number = version.get("version", 1)
    if version_number in seen_versions:
        raise ValueError(f"Prompt '{name}' has a duplicate version {version_number}")
    seen_versions.add(version_number)
