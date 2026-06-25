"""Deterministic placeholder assignment for PII entities."""

import string
from collections import defaultdict
from typing import Any

PRESIDIO_TO_PREFIX = {
    "ORGANIZATION": "PARTY",
    "PERSON": "NAME",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "LOCATION": "ADDRESS",
    "DATE_TIME": "DATE",
    "AMOUNT": "AMOUNT",
    "TAX_ID": "TAX_ID",
    "IBAN_CODE": "ACCT",
    "ACCT": "ACCT",
    "ID_DOCUMENT": "ID",
    "REG_NUMBER": "REG",
    "CREDIT_CARD": "CC",
    "IP_ADDRESS": "IP",
}

PARTY_PREFIXES = {"PARTY"}


def assign_placeholders(
    entities: list[Any], metadata_entities: list[Any] | None = None
) -> tuple[dict[str, str], list[Any]]:
    """Assign deterministic placeholders to entities.

    Args:
        entities: list of PiiEntity-like objects (dict or obj with entity_type, original_value attrs)
        metadata_entities: optional list of metadata PiiEntity objects

    Returns:
        mapping: dict[str, str] of {placeholder_key: original_value}
        entities: list with placeholder field set
    """
    all_entities = list(entities) + list(metadata_entities or [])
    if not all_entities:
        return {}, []

    # Group by prefix
    groups = defaultdict(list)
    for entity in all_entities:
        prefix = _get_prefix(entity)
        groups[prefix].append(entity)

    mapping = {}
    for prefix, group in sorted(groups.items()):
        # Unique values sorted alphabetically
        unique = sorted({e.original_value for e in group}, key=str.lower)

        if prefix in PARTY_PREFIXES:
            labels = string.ascii_uppercase[: len(unique)]
            for val, lbl in zip(unique, labels, strict=True):
                placeholder = f"[{prefix}_{lbl}]"
                mapping[placeholder.replace("[", "").replace("]", "")] = val
                for entity in group:
                    if entity.original_value == val:
                        entity.placeholder = placeholder
        else:
            for i, val in enumerate(unique, 1):
                placeholder = f"[{prefix}_{i}]"
                mapping[placeholder.replace("[", "").replace("]", "")] = val
                for entity in group:
                    if entity.original_value == val:
                        entity.placeholder = placeholder

    return mapping, all_entities


def _get_prefix(entity: Any) -> str:
    """Map Presidio entity type to placeholder prefix."""
    return PRESIDIO_TO_PREFIX.get(entity.entity_type, entity.entity_type)  # type: ignore[no-any-return]


__all__ = ["PRESIDIO_TO_PREFIX", "assign_placeholders"]
