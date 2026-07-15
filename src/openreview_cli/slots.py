"""Slot definitions for AI gateway model roles.

Kept outside the ``gateway`` package so the TUI can import ``VALID_SLOTS``
without triggering ``gateway/__init__.py`` (which pulls in litellm via
``cost.py``). Importing this module has no heavyweight dependencies.
"""

VALID_SLOTS: frozenset[str] = frozenset(
    {"reasoning", "extraction", "embedding", "reranking", "graph", "grounding"}
)
