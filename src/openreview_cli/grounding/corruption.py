"""Corruption strategies for grounding-accuracy testing — and the mandatory guard.

Adapts P-6's four corruption strategies from court citations to contract clauses:
  - clause_swap:    Replace clause ID with a different clause from the same document
  - category_swap:  Replace playbook category while keeping clause text
  - hallucination:  Generate claim text with no support in any clause
  - anachronism:    Cite a non-existent clause ID

**Which helpers may produce a grounding negative.** Only ``unsupported_claim``,
``paraphrased_unsupported`` and ``hallucination`` (``GROUNDING_VALID_NEGATIVES``) can produce
a claim that is genuinely unsupported by the clause it is asserted against.
``paraphrased_unsupported`` is ``unsupported_claim`` rewritten by the narrow ``paraphrase`` map
below, so it stays foreign to the cited clause. ``unsupported_claim`` draws its claim from
either a *different document* or the cited clause's own sentence with one operand changed
(``operand_change``); both are foreign to the cited clause by construction. The other three
cannot, and must not be scored as grounding negatives:

  - ``category_swap`` is a *classification* case: it rewrites a playbook category label and
    never receives the clause text, so the claim stays supported by its clause.
  - ``anachronism`` is a *citation-validity* case: it rewrites the clause-id reference inside
    the claim text. Whether the cited id exists is a different question from whether the
    cited clause supports the claim, so it would need its own harness with its own contract.
  - ``clause_swap`` is not used. It edits the claim *text* with ``str.replace``, which no-ops
    on ordinary prose — the claim comes back unchanged and would be mislabelled as
    unsupported. It is superseded by ``unsupported_claim``, which asserts a real sentence
    from *another* clause against the cited clause instead of editing the claim string.

**The mandatory guard.** Every generated negative — from any valid generator — MUST be
checked with ``is_genuine_negative`` before it enters a label set, and the harness MUST count
and report how many negatives each generator lost to the guard. A negative whose claim text
appears verbatim in the cited clause is *supported* and its label would be a lie; such a
negative is dropped, never kept silently.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, NamedTuple

from openreview_cli.grounding.presence import normalise
from openreview_cli.parsing.clause_detector import nupunkt_detect_boundaries

if TYPE_CHECKING:
    from openreview_cli.parsing.models import Clause

# A sentence only qualifies as a claim when it is long enough to assert something.
# Same bar for the harness's positives and for cross-clause negatives (design §2.1/§2.2).
MIN_SENTENCE_WORDS = 8
MIN_SENTENCE_CHARS = 40

# The only corruption helpers that may produce a *grounding* negative. The others are
# classification (`category_swap`), citation-validity (`anachronism`) or claim-text no-ops
# on prose (`clause_swap`); see the module docstring. `paraphrased_unsupported` is the
# rewritten cross-clause claim; `paraphrased_supported` is a *positive* and is deliberately
# absent from this tuple.
GROUNDING_VALID_NEGATIVES: tuple[str, ...] = (
    "unsupported_claim",
    "hallucination",
    "paraphrased_unsupported",
)

# The one constant, reviewed substitution map behind every paraphrase label. Applied to any
# sentence by ``paraphrase`` (which never returns ``None``); the caller drops a rewrite that
# changed nothing. Each pair is meaning-preserving, so a rewritten clause sentence is still the
# clause's own assertion and a rewritten cross-clause sentence is still foreign to the cited
# clause:
#   - "receiving party" -> "recipient": the same defined role under its plain name;
#   - "in no event" -> "under no circumstances": the same exclusion, an equivalent idiom;
#   - "shall not" -> "must not": the same prohibition under a different modal verb;
#   - "prior to" -> "before": the same temporal order.
# Longest source first, so no shorter term rewrites part of a longer one's match or of an
# earlier replacement.
_PARAPHRASE_MAP: tuple[tuple[str, str], ...] = (
    ("receiving party", "recipient"),
    ("in no event", "under no circumstances"),
    ("shall not", "must not"),
    ("prior to", "before"),
)

# Word-bounded at both ends so a term never rewrites part of a longer word ("shall" inside
# "marshall"). Case-sensitive on purpose: the map is narrow, and a sentence it does not match
# is left unchanged rather than half-rewritten.
_PARAPHRASE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(rf"\b{re.escape(source)}\b"), replacement)
    for source, replacement in _PARAPHRASE_MAP
)

# The bare modal is the one pair that is not meaning-preserving on its own. Under a negated or
# quantified subject ("Neither party shall disclose...", "No party shall be liable...",
# "Nothing shall obligate...") "shall" states a prohibition, and "must" would read as an
# absence of obligation -- a different claim. So it is applied last, and skipped entirely when
# the sentence contains a negation word; the sentence then comes back unchanged (or partly
# rewritten by the other pairs) and the caller counts the no-op skip. This keeps the map
# meaning-safe without dropping the bare modal's coverage.
_BARE_MODAL_PATTERN = re.compile(r"\bshall\b")
_BARE_MODAL_REPLACEMENT = "must"
_NEGATION_RE = re.compile(r"\b(?:no|neither|none|nothing|nor|not)\b", re.IGNORECASE)


class ClauseUnit(NamedTuple):
    """A harness source unit: a clause id and its plain text.

    Deliberately *not* ``parsing.models.Clause``: the harness reads plain paragraphs out of
    the corpus, and ``CitationGroundingDiscriminator.ground_claim`` builds its own ``Clause``
    from the arguments. Construct one at the call site — ``ClauseUnit(id=..., text=...)`` —
    so a harness unit type never has to leak into this module.

    ``document`` names the contract the paragraph came from, so the harness can draw its
    cross-clause negative from a *different* document (a sentence that cannot be supported by
    the cited clause). It is ``None`` when the caller does not track provenance.
    """

    id: str
    text: str
    document: str | None = None


def _normalize_for_guard(text: str) -> str:
    """Case-fold and collapse whitespace, so the guard compares claim to clause fairly."""
    return normalise(text)


def _sentences(text: str) -> list[str]:
    """Verbatim, stripped sentences of ``text`` in order (repo's own boundary detector)."""
    if not text.strip():
        return []
    return [
        s for s in (text[start:end].strip() for start, end in nupunkt_detect_boundaries(text)) if s
    ]


def _qualifies(sentence: str) -> bool:
    return len(sentence) >= MIN_SENTENCE_CHARS and len(sentence.split()) >= MIN_SENTENCE_WORDS


def first_qualifying_sentence(text: str) -> str | None:
    """Return the first sentence of ``text`` that is long enough to be a claim.

    The rule is ``>= MIN_SENTENCE_WORDS`` words and ``>= MIN_SENTENCE_CHARS`` characters,
    applied to verbatim, whitespace-stripped sentences from the repo's own boundary detector
    (``nupunkt_detect_boundaries``); no RNG, so the choice is reproducible.

    Returns:
        The verbatim sentence, or ``None`` when ``text`` is empty or no sentence qualifies.
    """
    for sentence in _sentences(text):
        if _qualifies(sentence):
            return sentence
    return None


def paraphrase(sentence: str) -> str:
    """Rewrite ``sentence`` with the constant, narrow substitution map (``_PARAPHRASE_MAP``).

    The map is deliberately small and meaning-preserving, so a rewritten clause sentence is
    still supported by its clause and a rewritten cross-clause sentence is still unsupported by
    the clause it is asserted against. The one unsafe swap, the bare modal (``shall`` ->
    ``must``), is skipped when the sentence contains a negation word (``no``, ``neither``,
    ``none``, ``nothing``, ``nor``, ``not``): under a negated or quantified subject the swap
    would turn a prohibition into an absence of obligation, a different claim. The map
    under-represents real human paraphrases, and the receipt says so.

    Always returns a ``str`` — never ``None`` — including ``sentence`` unchanged when no map
    term occurs (or when only the negation-guarded bare modal would have matched). The caller
    drops an unchanged rewrite and counts the drop: such a label would duplicate one already
    present, not add a harder one.

    Args:
        sentence: The sentence to rewrite.

    Returns:
        The rewritten sentence, or the input unchanged when nothing matched.
    """
    for pattern, replacement in _PARAPHRASE_PATTERNS:
        sentence = pattern.sub(replacement, sentence)
    # Last, and only when no negation word is present: see ``_BARE_MODAL_PATTERN`` above.
    if not _NEGATION_RE.search(sentence):
        sentence = _BARE_MODAL_PATTERN.sub(_BARE_MODAL_REPLACEMENT, sentence)
    return sentence


def unsupported_claim(clause_a: ClauseUnit, clause_b: ClauseUnit) -> str | None:
    """Build a genuine unsupported claim: a sentence from ``clause_b`` asserted against ``clause_a``.

    No string surgery is involved — the claim is real prose taken from a *different* clause,
    so it is unsupported by ``clause_a`` by construction. This is the honest replacement for
    ``clause_swap``, which edits the claim text and no-ops on prose.

    Args:
        clause_a: The ``(id, text)`` unit the claim will be cited against.
        clause_b: The ``(id, text)`` unit the claim sentence is taken from.

    Returns:
        The first qualifying sentence of ``clause_b.text`` (see
        ``first_qualifying_sentence``), or ``None`` in two degenerate cases the caller
        simply skips:

        - ``clause_a.id == clause_b.id`` — the same clause passed twice, where any sentence
          taken from ``clause_b`` is supported by ``clause_a`` and the label would be wrong;
        - ``clause_b`` has no qualifying sentence (empty text, or only sentences under the
          word/character bar), so there is no claim to assert.

        ``None`` is never a claim: callers must skip the pair rather than send an empty one.

    Note:
        The caller still MUST run ``is_genuine_negative`` on the returned claim against
        ``clause_a.text``: two distinct unit ids can carry the same paragraph text, and the
        guard is what catches that (and counts the drop).
    """
    if clause_a.id == clause_b.id:
        return None
    return first_qualifying_sentence(clause_b.text)


def is_genuine_negative(claim_text: str, clause_text: str) -> bool:
    """The mandatory guard: is ``claim_text`` really unsupported by ``clause_text``?

    A negative label claims the discriminator should reject ``claim_text`` as unsupported by
    ``clause_text``. If the claim text appears verbatim in the clause text, the claim *is*
    supported and the label would be a lie — typically the silently no-op'd output of a
    claim-text corruption such as ``clause_swap`` or ``anachronism``.

    The test is a substring test on the normalised pair, ``" ".join(s.split()).casefold()``,
    so case and whitespace differences cannot smuggle a supported claim past the guard. It is
    deliberately a lexical test on the exact claim the discriminator will see and the exact
    clause text it will be given: anything subtler is the discriminator's job, not the label's.

    Args:
        claim_text: The negative claim exactly as it will be sent to ``ground_claim``.
        clause_text: The cited clause text exactly as it will be sent to ``ground_claim``.

    Returns:
        ``True`` when the claim does not appear in the cited clause (a trustworthy negative).
        ``False`` when it does — including an empty or whitespace-only claim, which is a
        subset of every clause and never a usable negative.

    Note:
        Callers MUST drop the negatives this rejects **and count them**, per generator, and
        report that count even when it is zero. A run that silently keeps a mislabelled
        negative measures its own labelling error instead of the discriminator.
    """
    normalized_claim = _normalize_for_guard(claim_text)
    if not normalized_claim:
        return False
    return normalized_claim not in _normalize_for_guard(clause_text)


def paraphrased_supported(unit: ClauseUnit) -> str | None:
    """Rewrite the clause's own qualifying sentence — a genuine positive.

    Composition of ``first_qualifying_sentence`` with ``paraphrase``: the rewrite is the
    clause's own assertion in different words, so it is supported by the clause **by
    construction**. It is labelled supported directly, never routed through
    ``is_genuine_negative``: that guard is a substring test and cannot certify support, so a
    paraphrase would slip past it (see the module docstring and the harness notes).

    Args:
        unit: The clause whose sentence is rewritten.

    Returns:
        The rewritten sentence, or ``None`` when ``unit`` has no qualifying sentence. The
        caller keeps it only when it differs from the original sentence; an unchanged rewrite
        is a skip, not a label.
    """
    sentence = first_qualifying_sentence(unit.text)
    if sentence is None:
        return None
    return paraphrase(sentence)


def paraphrased_unsupported(clause_a: ClauseUnit, clause_b: ClauseUnit) -> str | None:
    """Rewrite a sentence from ``clause_b`` and assert it against ``clause_a``.

    Composition of ``unsupported_claim`` (the honest cross-clause negative) with
    ``paraphrase``: the sentence is taken from a *different* clause and the meaning-preserving
    rewrite keeps it foreign to ``clause_a``, so it stays a genuine negative.

    Args:
        clause_a: The ``(id, text)`` unit the claim will be cited against.
        clause_b: The ``(id, text)`` unit the sentence is taken from.

    Returns:
        The rewritten sentence, or ``None`` in the same degenerate cases as
        ``unsupported_claim`` (same clause twice, or no qualifying sentence). The caller keeps
        it only when it differs from the un-rewritten sentence, and still runs
        ``is_genuine_negative`` before scoring it.
    """
    sentence = unsupported_claim(clause_a, clause_b)
    if sentence is None:
        return None
    return paraphrase(sentence)


# The reviewed operand map, limited to the operands this corpus carries: a
# prior-written-consent phrase, the two party labels, a survival period and a payment period.
# Anything else is dead weight the corpus never reaches. The first matching pair wins.
_OPERAND_MAP: tuple[tuple[str, str], ...] = (
    ("prior written consent", "prior oral consent"),
    ("receiving party", "disclosing party"),
    ("five years", "nine years"),
    ("thirty", "ninety"),
)
_OPERAND_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(rf"\b{re.escape(source)}\b", re.IGNORECASE), replacement)
    for source, replacement in _OPERAND_MAP
)


def operand_change(clause_text: str) -> str | None:
    """The clause's own qualifying sentence with one operand changed, or ``None`` when it has
    no qualifying sentence or no mapped operand — the caller then uses the cross-document
    negative rather than keep an unchanged sentence."""
    sentence = first_qualifying_sentence(clause_text)
    if sentence is None:
        return None
    for pattern, replacement in _OPERAND_PATTERNS:
        changed = pattern.sub(replacement, sentence)
        if changed != sentence:
            return changed
    return None


def clause_swap(claim: str, clauses: list[Clause], original_clause_id: str) -> str:
    """Replace clause ID in a claim with a different clause ID from the same document.

    **Not a grounding negative** (module docstring). This is a claim-text rewrite: it only
    changes the *citation* string inside the claim and leaves the assertion untouched. On
    ordinary prose the clause id does not appear in the text at all, so ``str.replace`` is a
    no-op and the "corrupted" claim comes back **unchanged** — which is why a caller that
    labels its output unsupported would be lying. Use ``unsupported_claim`` for support
    (cross-clause) negatives; if claim-text citation edits are ever scored, that is a
    citation-validity measurement with its own contract.

    Args:
        claim: The original claim text (contains original_clause_id).
        clauses: All clauses from the source document.
        original_clause_id: The clause ID currently cited in the claim.

    Returns:
        Claim text with a different (random) clause ID substituted in.
        Returns the original claim unchanged if no candidate clause exists — and, on prose
        that never mentioned the id, unchanged even when candidates exist.
    """
    candidates = [c for c in clauses if c.id != original_clause_id]
    if not candidates:
        return claim
    # Pick deterministically by hash for reproducibility
    idx = hash(claim + original_clause_id) % len(candidates)
    replacement = candidates[idx].id
    return claim.replace(original_clause_id, replacement)


def category_swap(claim: str, original_category: str, categories: list[str]) -> str:
    """Replace the playbook category label while keeping clause text unchanged.

    **Not a grounding negative** (module docstring). This is a *classification* case: the
    clause text is not an argument to this function and is never touched, so the claim stays
    as supported by its clause as it was before the swap. It can only score whether the
    product classifies a clause into the right playbook category.

    Args:
        claim: Claim text that may reference the playbook category.
        original_category: The current category label.
        categories: All available category labels.

    Returns:
        Claim text with a different category substituted in.
        Returns the original claim unchanged if no other category exists.
    """
    candidates = [c for c in categories if c != original_category]
    if not candidates:
        return claim
    idx = hash(claim + original_category) % len(candidates)
    replacement = candidates[idx]
    return claim.replace(original_category, replacement)


def hallucination(claim: str) -> str:
    """Generate a claim with no support in any clause of the source document.

    **A grounding negative, but only through the guard.** It draws from ten fixed sentences
    that are fabricated for an ordinary agreement — except where a sentence happens to be
    supported by the clause in hand: the indemnification fabrication ("shall indemnify and
    hold harmless") is genuinely supported by an indemnity clause. So every output MUST pass
    ``is_genuine_negative`` against the cited clause before it is scored, and the harness
    MUST count and report the ones the guard drops.

    Args:
        claim: The original claim text (used as seed for deterministic selection).

    Returns:
        A fabricated claim text unrelated to any source clause.
    """
    fabrications: list[str] = [
        "The receiving party shall pay liquidated damages of $1,000,000 per breach.",
        "All disputes arising under this agreement shall be resolved by binding arbitration in Geneva, Switzerland.",
        "This agreement shall remain in effect for a term of 99 years from the effective date.",
        "Either party may terminate this agreement for any reason or no reason upon 30 days prior written notice.",
        "The receiving party shall indemnify and hold harmless the disclosing party against all third-party claims.",
        "This agreement may be assigned by either party without the other party's consent.",
        "The prevailing party in any legal proceeding shall be entitled to recover its reasonable attorneys' fees.",
        "The parties agree to a non-compete period of five years following termination of this agreement.",
        "Interest shall accrue on all late payments at the rate of 18 percent per annum.",
        "This agreement constitutes a binding partnership between the parties for tax purposes.",
    ]
    seed = hash(claim) % len(fabrications)
    return fabrications[seed]


def anachronism(claim: str, clause_id: str) -> str:
    """Cite a non-existent clause number.

    **Not a grounding negative** (module docstring). It is a *citation-validity* case: it
    rewrites the clause-id reference inside the claim's text, so it asks whether the citation
    resolves, not whether the cited clause supports the claim. Like ``clause_swap`` it uses
    ``str.replace`` and therefore no-ops on prose that never mentioned the id — the claim
    comes back unchanged.

    Replaces the clause_id reference in the claim text with a fabricated
    version number that does not exist in any real document.

    Args:
        claim: Claim text containing the clause_id.
        clause_id: The valid clause ID to be replaced.

    Returns:
        Claim text with a non-existent clause ID substituted in.
    """
    fake_id = f"v{abs(hash(clause_id)) % 9999}.99"
    return claim.replace(clause_id, fake_id)
