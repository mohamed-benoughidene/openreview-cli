"""Clause alignment engine — 3-tier heading cascade for bilateral comparison.

Implements the three-tier alignment cascade from research.md RQ-1:
1. Exact heading match (case-insensitive equality)
2. Fuzzy heading match (difflib.SequenceMatcher ratio >= 0.8)
3. Positional fallback (same index in clause list)

Zero new dependencies — ``difflib`` is stdlib in Python 3.12.
"""

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING

from openreview_cli.bilateral.models import AlignmentPair, AlignmentTable, MatchingMethod

if TYPE_CHECKING:
    from openreview_cli.parsing.models import Clause

FUZZY_THRESHOLD: float = 0.7
"""Minimum SequenceMatcher ratio for a fuzzy heading match (RQ-1)."""

_FALLBACK_TEXT_PREFIX_LEN: int = 40
"""Default heading text prefix length when a clause has no ``title``."""


def align_clauses(clauses_a: list[Clause], clauses_b: list[Clause]) -> AlignmentTable:
    """Align clauses between two documents.

    Parameters
    ----------
    clauses_a : list[Clause]
        All clauses from Party A's document.
    clauses_b : list[Clause]
        All clauses from Party B's document.

    Returns
    -------
    AlignmentTable
        All matched pairs, followed by unmatched clauses from each side.
    """
    if not clauses_a or not clauses_b:
        return AlignmentTable(
            matched_pairs=[],
            unmatched_a=list(clauses_a),
            unmatched_b=list(clauses_b),
        )

    headings_a = [_get_heading(c) for c in clauses_a]
    headings_b = [_get_heading(c) for c in clauses_b]

    # Track which indices have been matched
    matched_a: set[int] = set()
    matched_b: set[int] = set()
    matched_pairs: list[AlignmentPair] = []

    # Tier 1: Exact match
    a_to_b = _exact_pass(headings_a, headings_b, matched_b)
    for a_idx, b_idx in a_to_b.items():
        matched_a.add(a_idx)
        matched_b.add(b_idx)
        matched_pairs.append(
            AlignmentPair(
                pair_id=f"A{a_idx}-B{b_idx}",
                clause_a=clauses_a[a_idx],
                clause_b=clauses_b[b_idx],
                method=MatchingMethod.exact,
                score=1.0,
            )
        )

    # Tier 2: Fuzzy match
    fuzzy_matches = _fuzzy_pass(headings_a, headings_b, matched_a, matched_b)
    for a_idx, (b_idx, fscore) in fuzzy_matches.items():
        matched_a.add(a_idx)
        matched_b.add(b_idx)
        matched_pairs.append(
            AlignmentPair(
                pair_id=f"A{a_idx}-B{b_idx}",
                clause_a=clauses_a[a_idx],
                clause_b=clauses_b[b_idx],
                method=MatchingMethod.fuzzy,
                score=round(fscore, 4),
            )
        )

    # Tier 3: Positional fallback
    pairs, unmatched_a, unmatched_b = _positional_pass(clauses_a, clauses_b, matched_a, matched_b)
    matched_pairs.extend(pairs)

    return AlignmentTable(
        matched_pairs=matched_pairs,
        unmatched_a=unmatched_a,
        unmatched_b=unmatched_b,
    )


def _get_heading(clause: Clause) -> str:
    """Extract a heading string from a Clause.

    Uses ``clause.title`` if available, otherwise falls back to the
    first N characters of ``clause.text``.
    """
    if clause.title:
        return clause.title.strip()
    return clause.text[:_FALLBACK_TEXT_PREFIX_LEN].strip()


def _exact_pass(
    headings_a: list[str],
    headings_b: list[str],
    used_b: set[int],
) -> dict[int, int]:
    """Tier 1: Match clauses with identical headings (case-insensitive).

    Returns a mapping ``{index_a: index_b}`` for exact matches.
    Skips B indices already matched in a prior pass.
    """
    result: dict[int, int] = {}
    for a_idx, heading_a in enumerate(headings_a):
        if a_idx in result:
            continue
        normalized_a = heading_a.lower()
        for b_idx, heading_b in enumerate(headings_b):
            if b_idx in used_b or b_idx in result.values():
                continue
            if heading_b.lower() == normalized_a:
                result[a_idx] = b_idx
                break
    return result


def _fuzzy_pass(
    headings_a: list[str],
    headings_b: list[str],
    used_a: set[int],
    used_b: set[int],
    threshold: float = FUZZY_THRESHOLD,
) -> dict[int, tuple[int, float]]:
    """Tier 2: Match remaining clauses via fuzzy heading comparison.

    Returns a mapping ``{index_a: (index_b, score)}`` for pairs whose
    ``SequenceMatcher.ratio()`` meets or exceeds the threshold.

    Each unmatched A clause is paired with its best-matching unmatched B
    clause (greedy — pick the highest ratio first).
    """
    candidates: list[tuple[float, int, int]] = []

    for a_idx, heading_a in enumerate(headings_a):
        if a_idx in used_a:
            continue
        na = heading_a.lower()
        for b_idx, heading_b in enumerate(headings_b):
            if b_idx in used_b:
                continue
            nb = heading_b.lower()
            ratio = difflib.SequenceMatcher(None, na, nb).ratio()
            if ratio >= threshold:
                candidates.append((ratio, a_idx, b_idx))

    # Sort descending by ratio so we pick the best matches first
    candidates.sort(key=lambda x: x[0], reverse=True)

    result: dict[int, tuple[int, float]] = {}
    matched_a: set[int] = set(used_a)
    matched_b: set[int] = set(used_b)

    for ratio, a_idx, b_idx in candidates:
        if a_idx in matched_a or b_idx in matched_b:
            continue
        result[a_idx] = (b_idx, ratio)
        matched_a.add(a_idx)
        matched_b.add(b_idx)

    return result


def _positional_pass(
    clauses_a: list[Clause],
    clauses_b: list[Clause],
    used_a: set[int],
    used_b: set[int],
) -> tuple[list[AlignmentPair], list[Clause], list[Clause]]:
    """Tier 3: Match remaining clauses by their positional index.

    Pairs unmatched clauses at the same index position with
    ``alignment_quality = 0.5``. Remaining truly unmatched clauses
    on each side are returned separately.
    """
    pairs: list[AlignmentPair] = []
    max_len = max(len(clauses_a), len(clauses_b))

    for idx in range(max_len):
        a_matched = idx in used_a or idx >= len(clauses_a)
        b_matched = idx in used_b or idx >= len(clauses_b)

        if not a_matched and not b_matched:
            # Both are unmatched at this position — pair them
            pairs.append(
                AlignmentPair(
                    pair_id=f"A{idx}-B{idx}",
                    clause_a=clauses_a[idx],
                    clause_b=clauses_b[idx],
                    method=MatchingMethod.positional,
                    score=0.5,
                )
            )
            used_a.add(idx)
            used_b.add(idx)

    # Collect remaining unmatched
    unmatched_a = [c for i, c in enumerate(clauses_a) if i not in used_a]
    unmatched_b = [c for i, c in enumerate(clauses_b) if i not in used_b]

    return pairs, unmatched_a, unmatched_b
