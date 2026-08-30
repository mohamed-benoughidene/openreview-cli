"""Unit tests for P3-C2: UTC/local-midnight message defect.

The router at `src/openreview_cli/gateway/router.py:420` says
"Reset at local midnight" but the actual reset is at UTC midnight
(per `src/openreview_cli/storage/costs.py:41`: ``date('now')`` is UTC).

P3-C2 changes the in-CLI message to "Reset at UTC midnight" so the
message matches the SQL truth. The skill side (lines 626, 642) was
already corrected in P2.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROUTER_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "openreview_cli" / "gateway" / "router.py"
)


@pytest.fixture(scope="module")
def router_text() -> str:
    assert ROUTER_PATH.exists(), f"router.py not found at {ROUTER_PATH}"
    return ROUTER_PATH.read_text(encoding="utf-8")


def test_cost_limit_message_says_utc_not_local(router_text: str) -> None:
    """P3-C2: in-CLI cost-limit message must say 'UTC midnight', not 'local midnight'."""
    # The original buggy text: "Reset at local midnight or increase limit in config.yml"
    # The expected fixed text:  "Reset at UTC midnight or increase limit in config.yml"
    assert "local midnight" not in router_text, (
        "P3-C2 regression: 'local midnight' is still in router.py. "
        "The reset window is UTC-based (storage/costs.py:41 uses date('now') which is UTC); "
        "the message must say 'UTC midnight' to match the SQL truth."
    )
    # The fixed message must be present.
    assert "Reset at UTC midnight" in router_text, (
        "P3-C2 not applied: the 'Reset at UTC midnight' message is missing from router.py"
    )


def test_cost_limit_message_still_offers_config_increase(router_text: str) -> None:
    """P3-C2 regression guard: the 'or increase limit in config.yml' clause must remain."""
    # Find the line near the message
    match = re.search(r"Reset at \w+ midnight.*config\.yml", router_text)
    assert match, (
        "P3-C2 regression: 'Reset at ... midnight or increase limit in config.yml' missing"
    )
    assert "config.yml" in match.group(0), "P3-C2 regression: 'config.yml' clause missing"
