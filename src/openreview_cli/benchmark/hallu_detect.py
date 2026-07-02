"""Hallucination rate measurement.

Current implementation: ROUGE-L lexical overlap placeholder.
Flagged as EXPERIMENTAL — upgraded to CG-DPO when parallel spec lands.
"""

from collections.abc import Sequence


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
