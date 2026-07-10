"""Corpus generator: applies mutations to templates and writes pair JSON files.

Usage:
    python -m tests.fixtures.nda_corpus.generate

Generates ~500+ NDA pairs from 2 templates x 11 clause categories x 5-8 mutations each.
Output: tests/fixtures/nda_corpus/pairs/*.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from tests.fixtures.nda_corpus.mutations import ALL_MUTATIONS, MutationDef

FIXTURES_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = FIXTURES_DIR / "templates"
PAIRS_DIR = FIXTURES_DIR / "pairs"

CORPUS_SIZE: int = 500  # target minimum pair count

# Change types for ground truth
CHANGE_TYPES = {"addition", "contradiction", "equivalent"}


def load_template(path: Path) -> dict[str, str]:
    """Load a template file and extract clauses by their ``##CLAUSE:`` markers.

    Returns a dict mapping ``clause_id`` (e.g. "confidentiality_definition")
    to the clause text.

    Raises ``ValueError`` if no clause markers are found.
    """
    text = path.read_text(encoding="utf-8")
    clauses: dict[str, str] = {}

    pattern = re.compile(r"##CLAUSE:\s*(\w+)#*\s*\n(.*?)(?=\n##CLAUSE:|\Z)", re.DOTALL)
    for match in pattern.finditer(text):
        clause_id = match.group(1)
        clause_text = match.group(2).strip()
        clauses[clause_id] = clause_text

    if not clauses:
        raise ValueError(f"No ##CLAUSE: markers found in {path}")

    return clauses


def load_templates() -> dict[str, dict[str, str]]:
    """Load all template files from the templates directory.

    Returns a dict mapping ``template_id`` (stem of filename) to its
    ``{clause_id: text}`` dict.
    """
    templates: dict[str, dict[str, str]] = {}
    for fpath in sorted(TEMPLATES_DIR.glob("*.txt")):
        tid = fpath.stem
        templates[tid] = load_template(fpath)
    return templates


def list_templates() -> list[str]:
    """Return template IDs available in the templates directory."""
    return [p.stem for p in sorted(TEMPLATES_DIR.glob("*.txt"))]


def _apply_mutation(clause_text: str, mutation: MutationDef) -> str | None:
    """Apply a single mutation to clause text.

    Tries primary ``find_text`` first, then each alternative in
    ``find_text_alternatives``. Returns mutated text, or ``None`` if
    no pattern matched.
    """
    if not mutation.find_text:
        return None
    # Try primary pattern
    if mutation.find_text in clause_text:
        return clause_text.replace(mutation.find_text, mutation.replace_text)
    # Try alternatives
    for alt in mutation.find_text_alternatives:
        if alt in clause_text:
            return clause_text.replace(alt, mutation.replace_text)
    return None


def _word_positions(words: list[str], text: str) -> list[int]:
    """Return start position of each word in text (iterative find)."""
    positions: list[int] = []
    pos = 0
    for word in words:
        idx = text.find(word, pos)
        if idx < 0:
            idx = pos
        positions.append(idx)
        pos = idx + len(word)
    return positions


def _compute_ground_truth(
    original: str, mutated: str, mutation: MutationDef, clause_id: str
) -> list[dict[str, Any]]:
    """Compute ground-truth diff between original and mutated clause text.

    Uses word-level difflib to find the actual textual diff (same method as
    the bilateral detector), ensuring ground truth aligns with what the
    detector produces.
    """
    import difflib

    orig_words = original.split()
    mut_words = mutated.split()
    orig_positions = _word_positions(orig_words, original)
    matcher = difflib.SequenceMatcher(None, orig_words, mut_words)

    ground_truth: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        old = " ".join(orig_words[i1:i2])
        new = " ".join(mut_words[j1:j2])
        if not old and not new:
            continue

        # Find character position in original clause text
        if old:
            pos = orig_positions[i1] if i1 < len(orig_positions) else 0
            pos = max(pos, 0)
            end = pos + len(old)
        else:
            # Insertion — after preceding equal word, or at start
            pos = orig_positions[i1 - 1] + len(orig_words[i1 - 1]) if i1 > 0 else 0
            end = pos  # zero-length interval for insertion

        ground_truth.append(
            {
                "clause_id": clause_id,
                "change_type": mutation.expected_diff_type,
                "span_start": pos,
                "span_end": end if old else pos,
                "old_text": old,
                "new_text": new,
            }
        )

    if not ground_truth:
        # Fallback: report whole clause
        ground_truth.append(
            {
                "clause_id": clause_id,
                "change_type": mutation.expected_diff_type,
                "span_start": 0,
                "span_end": len(original),
                "old_text": original,
                "new_text": mutated,
            }
        )

    return ground_truth


def _build_full_text(clauses: dict[str, str]) -> str:
    """Build full document text from clause dict, maintaining ordering."""
    # Clause ordering priority - NDA sections in standard order
    order = [
        "confidentiality_definition",
        "exclusions",
        "obligations",
        "permitted_disclosures",
        "term",
        "return_obligations",
        "no_license",
        "disclaimer_warranties",
        "remedies",
        "assignment",
        "governing_law",
        "jurisdiction",
        "survival",
    ]
    parts: list[str] = []
    for key in order:
        if key in clauses and clauses[key].strip():
            parts.append(clauses[key].strip())
    # Any remaining clauses not in order
    for key, text in clauses.items():
        if key not in order and text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts)


def generate_pair(
    template_id: str,
    clauses: dict[str, str],
    mutation: MutationDef,
    pair_index: int,
) -> dict[str, Any] | None:
    """Generate one NDA pair: (base, mutated, ground_truth_diff).

    Returns the pair dict, or ``None`` if the mutation cannot apply to
    this template (missing clause or missing find_text).
    """
    if mutation.category.value not in clauses:
        return None

    clause_text = clauses[mutation.category.value]
    mutated_text = _apply_mutation(clause_text, mutation)
    if mutated_text is None:
        return None

    # Build base document (original clauses)
    base_clauses = dict(clauses)
    base_full = _build_full_text(base_clauses)

    # Build mutated document
    mutated_clauses = dict(clauses)
    mutated_clauses[mutation.category.value] = mutated_text
    mutated_full = _build_full_text(mutated_clauses)

    # Compute ground truth diff on the full document (not just clause)
    # so positions are naturally full-document-relative, matching the detector.
    ground_truth = _compute_ground_truth(base_full, mutated_full, mutation, mutation.category.value)

    pair_id = f"{template_id}__{mutation.category.value}__{mutation.name}__{pair_index:04d}"
    mutated_id = f"{pair_id}_mutated"

    return {
        "pair_id": pair_id,
        "base_id": pair_id,
        "mutated_id": mutated_id,
        "template": template_id,
        "category": mutation.category.value,
        "mutation_name": mutation.name,
        "expected_diff_type": mutation.expected_diff_type,
        "base_text": base_full,
        "mutated_text": mutated_full,
        "ground_truth_diff": ground_truth,
        "metadata": {
            "mutation_description": mutation.description,
            "direction": "forward",
        },
    }


def generate_reverse_pair(
    forward_pair: dict[str, Any],
) -> dict[str, Any]:
    """Generate the reverse-direction pair (mutated becomes base, base becomes mutated).

    This doubles the corpus size by providing pairs in both directions.
    """
    return {
        "pair_id": forward_pair["pair_id"].replace("__", "__rev__"),
        "base_id": forward_pair["mutated_id"],
        "mutated_id": forward_pair["base_id"],
        "template": forward_pair["template"],
        "category": forward_pair["category"],
        "mutation_name": forward_pair["mutation_name"],
        "expected_diff_type": forward_pair["expected_diff_type"],
        "base_text": forward_pair["mutated_text"],
        "mutated_text": forward_pair["base_text"],
        "ground_truth_diff": [
            {
                "clause_id": d["clause_id"],
                "change_type": d["change_type"],
                "span_start": d["span_start"],
                "span_end": d["span_end"],
                "old_text": d["new_text"],
                "new_text": d["old_text"],
            }
            for d in forward_pair["ground_truth_diff"]
        ],
        "metadata": {
            "mutation_description": forward_pair["metadata"]["mutation_description"],
            "direction": "reverse",
            "forward_pair_id": forward_pair["pair_id"],
        },
    }


def generate_corpus() -> list[dict[str, Any]]:
    """Generate the full NDA pair corpus.

    Iterates over all templates, categories, and mutations, producing
    (base, mutated, ground_truth_diff) tuples for every applicable
    combination. Also generates reverse-direction pairs to double the
    corpus size.

    Returns the list of pair dicts (also written to ``pairs/*.json``).
    """
    PAIRS_DIR.mkdir(parents=True, exist_ok=True)
    templates = load_templates()

    pairs: list[dict[str, Any]] = []
    pair_index = 0

    for template_id, clauses in templates.items():
        for mutation in ALL_MUTATIONS:
            pair = generate_pair(template_id, clauses, mutation, pair_index)
            if pair is not None:
                pairs.append(pair)
                pair_index += 1

    # Generate reverse-direction pairs
    reverse_pairs: list[dict[str, Any]] = []
    for pair in pairs:
        rev = generate_reverse_pair(pair)
        reverse_pairs.append(rev)

    all_pairs = pairs + reverse_pairs

    # Write pairs to individual JSON files
    for pair in all_pairs:
        pair_path = PAIRS_DIR / f"{pair['pair_id']}.json"
        pair_path.write_text(json.dumps(pair, indent=2, ensure_ascii=False), encoding="utf-8")

    # Write a manifest with all pair IDs
    manifest = {
        "total_pairs": len(all_pairs),
        "template_count": len(templates),
        "templates": list(templates.keys()),
        "mutations": len(ALL_MUTATIONS),
        "pair_ids": [p["pair_id"] for p in all_pairs],
        "forward_count": len(pairs),
        "reverse_count": len(reverse_pairs),
    }
    manifest_path = PAIRS_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    return all_pairs


def main() -> int:
    """CLI entry point: generate corpus and print summary."""
    pairs = generate_corpus()
    print(f"Generated {len(pairs)} NDA pairs")
    print(f"Templates: {list_templates()}")
    print(f"Output: {PAIRS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
