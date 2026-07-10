"""NDA benchmark corpus for bilateral comparison evaluation.

Provides template loading, mutation application, and pair generation
for constructing a synthetic benchmark of pre/post negotiation NDA pairs
with known ground-truth diffs.
"""

from __future__ import annotations

from tests.fixtures.nda_corpus.generate import (
    CORPUS_SIZE,
    generate_corpus,
    list_templates,
    load_template,
    load_templates,
)
from tests.fixtures.nda_corpus.generate import (
    PAIRS_DIR as CORPUS_DIR,
)
from tests.fixtures.nda_corpus.loader import CorpusPair, load_corpus_pairs
from tests.fixtures.nda_corpus.mutations import (
    ALL_MUTATIONS,
    CLAUSE_CATEGORIES,
    MutationDef,
)

__all__ = [
    "ALL_MUTATIONS",
    "CLAUSE_CATEGORIES",
    "CORPUS_DIR",
    "CORPUS_SIZE",
    "CorpusPair",
    "MutationDef",
    "generate_corpus",
    "list_templates",
    "load_corpus_pairs",
    "load_template",
    "load_templates",
]
