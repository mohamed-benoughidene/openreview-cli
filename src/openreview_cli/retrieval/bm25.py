"""BM25 sparse retrieval — query preprocessing and rank normalization."""

from __future__ import annotations

import re
from typing import Any

_NON_ALPHANUM_RE = re.compile(r"[^\w\s-]")
_WHITESPACE_RE = re.compile(r"\s+")
_FTS_OPERATORS = frozenset({"AND", "OR", "NOT"})


def _tokenize(query_text: str) -> list[str]:
    """Split query text into punctuation-free tokens, preserving inner hyphens."""
    stripped = _NON_ALPHANUM_RE.sub(" ", query_text)
    return [token for token in _WHITESPACE_RE.split(stripped.strip()) if token]


def preprocess_query(query_text: str) -> str:
    """Build a safe FTS5 MATCH expression from raw query text.

    Steps:
    1. Strip punctuation (preserve hyphens in legal terms like "data-processing")
    2. Lowercase and quote each term, so FTS5 metacharacters (" * - : NEAR)
       cannot raise a syntax error
    3. Join terms with OR — FTS5 reads a bare multi-term query as an implicit
       AND, which matches nothing for natural-language questions
    4. Keep uppercase AND/OR/NOT as operators where they separate two terms;
       a leading operator has no left operand and is emitted as an ordinary
       term, since FTS5 operators are uppercase-only and a lowercased operator
       would be silently demoted anyway
    """
    expression: list[str] = []
    pending_operator: str | None = None
    for token in _tokenize(query_text):
        if token in _FTS_OPERATORS and expression:
            pending_operator = token
            continue
        if expression:
            expression.append(pending_operator or "OR")
        expression.append(f'"{token.lower()}"')
        pending_operator = None
    return " ".join(expression)


def normalize_bm25_scores(
    raw_scores: list[tuple[str, float]],
) -> dict[str, int]:
    """Convert FTS5 bm25() results to rank positions for RRF fusion.

    FTS5 bm25() returns negative scores where lower (more negative) = better.
    This function sorts by score ascending (best first) and assigns rank=1
    to the best result.

    Returns:
        dict[chunk_id, rank] where rank=1 is best.
    """
    # Sort by bm25 score ascending (most negative = best)
    sorted_results = sorted(raw_scores, key=lambda x: x[1])
    return {chunk_id: rank for rank, (chunk_id, _) in enumerate(sorted_results, start=1)}


def search_bm25(
    storage: Any,
    query_text: str,
    top_k: int,
) -> list[tuple[str, float]]:
    """Run BM25 search via storage, returning raw (chunk_id, bm25_score) pairs.

    Wraps ``storage.search_fts()`` with preprocessed query.
    """
    processed = preprocess_query(query_text)
    # FTS5 requires non-empty query
    if not processed:
        return []
    rows = storage.search_fts(processed, top_k)
    return [(str(row[0]), float(row[1])) for row in rows]
