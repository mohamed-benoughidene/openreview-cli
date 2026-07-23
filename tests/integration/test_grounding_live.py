"""Live integration test for the Citation Grounding Discriminator.

Unlike the unit tests (which inject a MagicMock gateway with canned
responses), this test drives the discriminator through a REAL gateway
call against OpenRouter, proving the reasoning-capability wiring
actually works end to end — not just in code.

It is skipped unless OPENROUTER_API_KEY is present in the environment,
so it never fails CI on machines without credentials.
"""

from __future__ import annotations

import os

import pytest

from openreview_cli.gateway.models import CapabilityRequirement
from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
from openreview_cli.grounding.models import GroundingVerdict

_LIVE_MODEL = "openrouter/deepseek/deepseek-r1"

requires_openrouter = pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"),
    reason="requires live OPENROUTER_API_KEY",
)


@pytest.mark.network
@requires_openrouter
def test_ground_claim_live_reasoning_wiring() -> None:
    """Real gateway call: a claim that IS supported by the clause must
    come back GROUNDED with a non-empty reason (not UNCERTAIN, which
    would mean the gateway call failed)."""
    disc = CitationGroundingDiscriminator(mode="lenient")
    verdict, provenances, confidence = disc.ground_claim(
        claim_text="The parties must keep all confidential information secret.",
        cited_clause_id="clause-1",
        clause_text=(
            "Clause 1. Confidentiality. Each party shall keep all "
            "confidential information of the other party strictly secret "
            "and shall not disclose it to any third party."
        ),
    )
    assert verdict == GroundingVerdict.GROUNDED
    assert isinstance(confidence, float)
    assert confidence > 0.0


@pytest.mark.network
@requires_openrouter
def test_ground_claim_live_unsupported_returns_ungrounded() -> None:
    """Real gateway call: a claim that contradicts the clause must come
    back UNGROUNDED (not UNCERTAIN, which would mean the gateway failed)."""
    disc = CitationGroundingDiscriminator(mode="lenient")
    verdict, provenances, confidence = disc.ground_claim(
        claim_text="The disclosing party may publish all confidential data freely.",
        cited_clause_id="clause-1",
        clause_text=(
            "Clause 1. Confidentiality. Each party shall keep all "
            "confidential information of the other party strictly secret "
            "and shall not disclose it to any third party."
        ),
    )
    assert verdict == GroundingVerdict.UNGROUNDED
    assert isinstance(confidence, float)


@pytest.mark.network
@requires_openrouter
def test_discriminator_passes_reasoning_requirement() -> None:
    """Confirm the discriminator's gateway call carries the reasoning
    capability requirement, by spying on the real Gateway.chat call args."""
    from collections.abc import Callable
    from typing import Any

    from openreview_cli.gateway.router import Gateway

    captured: dict[str, Any] = {}

    real_gateway = Gateway()
    original_chat: Callable[..., Any] = real_gateway.chat

    def spy_chat(*args: Any, **kwargs: Any) -> Any:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return original_chat(*args, **kwargs)

    real_gateway.chat = spy_chat  # type: ignore[method-assign]
    disc = CitationGroundingDiscriminator(mode="lenient", gateway=real_gateway)
    disc.ground_claim(
        claim_text="The term of this agreement is twelve months.",
        cited_clause_id="clause-2",
        clause_text="Clause 2. Term. This agreement runs for a period of twelve months.",
    )
    req = captured["kwargs"].get("requirement")
    assert isinstance(req, CapabilityRequirement)
    assert req.capability == "reasoning"
