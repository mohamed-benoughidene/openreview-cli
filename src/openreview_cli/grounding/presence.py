"""Claim-to-clause presence: how much of a claim's wording appears in the clause it cites.

A measurement primitive only. ``coverage`` returns the share of the claim's tokens (matched
as a multiset by ``[a-z0-9]+`` on the normalised pair) that also occur in the clause;
``measure`` returns that number beside a single ``wording_absent`` boolean for the model to
read. Claim and clause text never leave this module — the number and the boolean are the
entire output.

**No verdict may be derived from the number.** The design rejects a coverage veto because
the harness's planted bad claims reach 0.689 while supported paraphrases fall to 0.200, so
any single line either misses mislabels or rejects real findings (design §1). The boolean is
a conservative hint, not a gate: it is ``False`` whenever the measurement would be
meaningless — no clause text, a claim under five tokens, or a claim that is only a reference
such as ``4.3``.
"""

from __future__ import annotations

import re
from collections import Counter

# Tokens are word characters, case-folded by ``normalise``; everything else is a separator.
_TOKEN_RE = re.compile(r"[a-z0-9]+")
# A claim that is only a citation reference, e.g. "4.3", "v12.4": nothing to measure.
_REFERENCE_RE = re.compile(r"v?\d+(?:\.\d+)*")
# Below this many claim tokens the score is too noisy to trust, so the guard stands down.
_MIN_CLAIM_TOKENS = 5
# The internal bar for "the wording is absent". Not part of the public surface, and not a
# verdict: it only decides whether the hint is shown.
_WORDING_ABSENT_THRESHOLD = 0.5


def normalise(text: str) -> str:
    """Case-fold and collapse whitespace, so a claim and a clause compare fairly."""
    return " ".join(text.split()).casefold()


def _tokens(normalised_text: str) -> list[str]:
    """The ``[a-z0-9]+`` tokens of already-normalised text."""
    return _TOKEN_RE.findall(normalised_text)


def coverage(claim_text: str, clause_text: str) -> float:
    """The share of the claim's tokens that also occur in the clause.

    Tokens are ``[a-z0-9]+`` matches on the normalised pair, matched as a multiset: a token
    used three times in the claim needs three occurrences in the clause to count three times.
    The denominator is the claim's token count, so a long clause never dilutes a short quote.
    An empty (or token-free) claim scores ``0.0``.

    Args:
        claim_text: The claim exactly as it appears in the review.
        clause_text: The cited clause text exactly as it was sent to the model.

    Returns:
        A float in ``[0.0, 1.0]``. Measurement only — never a verdict.
    """
    claim_tokens = _tokens(normalise(claim_text))
    if not claim_tokens:
        return 0.0
    clause_counts = Counter(_tokens(normalise(clause_text)))
    matched = sum(
        min(count, clause_counts[token]) for token, count in Counter(claim_tokens).items()
    )
    return matched / len(claim_tokens)


def measure(claim_text: str, clause_text: str) -> tuple[float, bool]:
    """Return ``(coverage, wording_absent)`` for a claim and the clause it cites.

    The number always equals ``coverage(claim_text, clause_text)``; the boolean is ``False``
    — never "absent" — when the measurement would be meaningless:

    - the clause text is empty or whitespace-only;
    - the claim has fewer than five tokens;
    - the claim is only a reference such as ``4.3`` (``v?\\d+(?:\\.\\d+)*``).

    Otherwise it is ``coverage(...) < _WORDING_ABSENT_THRESHOLD``. The hint only tells the
    model the claim's wording does not appear in the clause; the model still decides.

    Args:
        claim_text: The claim exactly as it appears in the review.
        clause_text: The cited clause text exactly as it was sent to the model.

    Returns:
        The coverage score and the ``wording_absent`` flag, in that order.
    """
    score = coverage(claim_text, clause_text)
    if not clause_text.strip():
        return score, False
    normalised_claim = normalise(claim_text)
    if len(_tokens(normalised_claim)) < _MIN_CLAIM_TOKENS:
        return score, False
    if _REFERENCE_RE.fullmatch(normalised_claim):
        return score, False
    return score, score < _WORDING_ABSENT_THRESHOLD
