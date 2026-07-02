"""Shared AI Gateway helper — single ``_call_gateway_chat`` for extraction + QA.

Kept minimal: one function, no extra imports, no runtime deps beyond Gateway.
Monkeypatched by tests when they need to stub the model call.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def call_gateway_chat(slot: str, messages: list[dict[str, str]]) -> str:
    """Call the AI Gateway's chat method.

    Separated into its own function for testability (monkeypatching).
    """
    from openreview_cli.gateway.router import Gateway

    gw = Gateway()
    return gw.chat(slot, messages)
