"""Hallucination rate measurement.

Current implementation: ROUGE-L lexical overlap placeholder.
Flagged as EXPERIMENTAL — upgraded to CG-DPO when parallel spec lands.

Provides:
- HallucinationDetector ABC (interface for all detectors)
- LexicalOverlapDetector (current, ROUGE-L based)
- CGDPODetector (uses CitationGroundingDiscriminator)
- Backward-compatible standalone functions
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

    from openreview_cli.gateway.router import Gateway

logger = logging.getLogger(__name__)


class HallucinationDetector(ABC):
    """Abstract base for hallucination detection strategies."""

    @abstractmethod
    def detect(self, claims: list[str], sources: list[str]) -> list[bool]:
        """Detect hallucinated claims.

        Args:
            claims: List of claim texts to evaluate.
            sources: List of source clause texts.

        Returns:
            list[bool]: True if the claim is supported (not hallucinated),
            False if hallucinated.
        """
        ...


def _lcs_length(a: Sequence[str], b: Sequence[str]) -> int:
    """Longest common subsequence length between two token sequences.

    Uses two-row rolling DP array for O(n) space.
    """
    m, n = len(a), len(b)
    if m == 0 or n == 0:
        return 0
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = prev[j] if prev[j] > curr[j - 1] else curr[j - 1]
        prev, curr = curr, prev
    return prev[n]


def _per_claim_recalls(claims: list[str], sources: list[str]) -> list[float]:
    """Compute ROUGE-L recall for each claim against source text."""
    if not claims or not sources:
        return []
    source_tokens = " ".join(sources).split()
    recalls: list[float] = []
    for claim in claims:
        if not claim.strip():
            continue
        claim_tokens = claim.split()
        if not claim_tokens:
            continue
        recalls.append(_lcs_length(claim_tokens, source_tokens) / len(claim_tokens))
    return recalls


class LexicalOverlapDetector(HallucinationDetector):
    """ROUGE-L lexical overlap hallucination detector.

    Measures what fraction of claim tokens overlap with source text
    via longest common subsequence.
    """

    def __init__(self, threshold: float = 0.3) -> None:
        self._threshold = threshold

    def detect(self, claims: list[str], sources: list[str]) -> list[bool]:
        """Detect hallucinated claims using ROUGE-L threshold.

        Returns True (supported) if recall >= threshold, False (hallucinated) otherwise.
        """
        recalls = _per_claim_recalls(claims, sources)
        return [r >= self._threshold for r in recalls] if recalls else []


class CGDPODetector(HallucinationDetector):
    """CG-DPO hallucination detector using the CitationGroundingDiscriminator.

    Wraps the discriminator to evaluate claims against source clauses.
    Conservative per R-9: UNCERTAIN and UNGROUNDED are both treated as
    hallucinated (returns False).
    """

    def __init__(
        self,
        mode: Literal["strict", "lenient"] = "strict",
        gateway: Gateway | None = None,
        model: str | None = None,
    ) -> None:
        self._mode = mode
        self._gateway = gateway
        self._model = model
        self._discriminator: Any = None  # lazy init — CitationGroundingDiscriminator

    def _get_discriminator(self) -> Any:
        """Lazy-init the discriminator to defer import."""
        if self._discriminator is None:
            from openreview_cli.grounding.discriminator import (
                CitationGroundingDiscriminator,
            )

            self._discriminator = CitationGroundingDiscriminator(
                mode=self._mode,
                gateway=self._gateway,
                model=self._model,
            )
        return self._discriminator

    def detect(self, claims: list[str], sources: list[str]) -> list[bool]:
        """Detect hallucinated claims using the grounding discriminator.

        Each claim is checked against the corresponding source clause.
        Returns True for GROUNDED, False for UNGROUNDED/UNCERTAIN.

        Args:
            claims: List of claim texts.
            sources: List of source clause texts (must match claims length).

        Returns:
            list[bool]: True if grounded, False if hallucinated/uncertain.
        """
        if not claims:
            return []

        from openreview_cli.grounding.models import GroundingVerdict

        # Build a single-claim-at-a-time detection
        results: list[bool] = []
        discriminator = self._get_discriminator()

        for claim_text, source_text in zip(claims, sources, strict=False):
            if not claim_text.strip():
                results.append(False)
                continue
            try:
                verdict, _, _ = discriminator.ground_claim(
                    claim_text=claim_text,
                    cited_clause_id="source",
                    clause_text=source_text,
                )
                # Conservative: only GROUNDED → True
                results.append(verdict == GroundingVerdict.GROUNDED)
            except Exception:
                logger.warning("CG-DPO detection failed for claim, defaulting to hallucinated")
                results.append(False)

        return results


# ── Backward-compatible standalone functions ──────────────────────────────


def rouge_l_recall(claims: list[str], sources: list[str]) -> float:
    """Compute average ROUGE-L recall between claims and source text.

    Measures what fraction of claim tokens overlap with source text
    via longest common subsequence. Lower recall = more hallucination.

    Returns a value in [0.0, 1.0].
    """
    recalls = _per_claim_recalls(claims, sources)
    if not recalls:
        return 1.0
    return sum(recalls) / len(recalls)


def hallucination_rate(claims: list[str], sources: list[str], threshold: float = 0.3) -> float:
    """Calculate hallucination rate as proportion of claims below recall threshold.

    Returns value in [0.0, 1.0].
    """
    if not claims:
        return 0.0
    recalls = _per_claim_recalls(claims, sources)
    hallucinated = sum(1 for r in recalls if r < threshold)
    return hallucinated / len(claims)
