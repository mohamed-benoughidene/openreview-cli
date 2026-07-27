"""Shared helpers for parsing LLM JSON responses.

LLM providers (e.g. Claude via OpenRouter) frequently wrap JSON payloads in
markdown code fences (```json ... ```). ``json.loads`` fails on the leading
backticks, and parsers that swallow ``JSONDecodeError`` then return silent
fallback values. Every gateway-response parser must strip fences via
``strip_fences`` before calling ``json.loads``.

See specs/retro-markdown-fence-bug.md.
"""

from __future__ import annotations


def fence_safe(text: str) -> str:
    """Break triple-backtick runs so embedded text cannot escape prompt code fences."""
    return text.replace("```", "` ` `")


def strip_fences(text: str) -> str:
    """Strip a markdown code fence wrapping the whole payload.

    Handles `````json\\n{...}\\n````` and `````\\n{...}\\n`````. Returns the
    input whitespace-stripped when no fence is present. Semantics identical
    to the inline stripping validated end-to-end against real providers in
    ``review/extraction.py`` (commit ``91b2951``).
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        # ponytail: fence without newline (```json{...}```) is not stripped —
        # no provider observed emitting it; json.loads then fails and every
        # call site falls back safely. Handle it here if one ever does.
        first_nl = stripped.find("\n")
        if first_nl >= 0:
            stripped = stripped[first_nl + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[:-3].strip()
    return stripped
