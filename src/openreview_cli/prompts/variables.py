from __future__ import annotations

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


def substitute(content: str, slot: str, variables: dict[str, str]) -> str:
    class _DefaultDict(defaultdict[str, str]):
        def __missing__(self, key: str) -> str:
            logger.warning("Unknown variable '%s' in slot '%s'", key, slot)
            return "{" + key + "}"

    mapping = _DefaultDict(str, variables)
    return content.format_map(mapping)
