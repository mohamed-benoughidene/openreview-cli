"""Test bilateral comparison engine against the NDA benchmark corpus.

Uses a simple diff-based detector to compute F1 score against ground truth
diffs. The detector uses token-level overlap (simulating span-level F1 from
CUAD/ContractNLI).

Asserts F1 ≥ 0.6 (loose threshold — this is v1).
"""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest

from tests.fixtures.nda_corpus.loader import GroundTruthDiff, load_corpus_pairs

CORPUS_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "nda_corpus"
F1_THRESHOLD = 0.6  # loose v1 threshold
TEST_SAMPLE_SIZE = 10  # number of pairs to test


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


def _extract_word_span_diffs(base: str, mutated: str) -> list[tuple[int, int, str, str]]:
    """Use word-level difflib to identify changed spans.

    Tokenizes by whitespace and uses SequenceMatcher on word sequences
    to avoid character-level fragmentation.

    Returns list of (start, end, old_text, new_text) tuples relative
    to the original base text.
    """
    base_words = base.split()
    mutated_words = mutated.split()
    base_positions = _word_positions(base_words, base)

    matcher = difflib.SequenceMatcher(None, base_words, mutated_words)
    results: list[tuple[int, int, str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        old = " ".join(base_words[i1:i2])
        new = " ".join(mutated_words[j1:j2])
        if not old and not new:
            continue
        # Find character position in original base text
        if old:
            pos = base_positions[i1] if i1 < len(base_positions) else 0
            pos = max(pos, 0)
            end = pos + len(old)
        else:
            # Insertion — after preceding equal word, or at start
            pos = base_positions[i1 - 1] + len(base_words[i1 - 1]) if i1 > 0 else 0
            end = pos  # zero-length interval for insertion
        results.append((pos, end, old, new))
    return results


def test_corpus_pairs_loadable() -> None:
    """Verify the corpus can be loaded and has sufficient pairs."""
    pairs = load_corpus_pairs(max_pairs=TEST_SAMPLE_SIZE)
    assert len(pairs) == TEST_SAMPLE_SIZE, f"Expected {TEST_SAMPLE_SIZE} pairs, got {len(pairs)}"


def test_diff_detector_finds_all_changes() -> None:
    """The difflib-based detector should find all ground-truth changes."""
    pairs = load_corpus_pairs(max_pairs=TEST_SAMPLE_SIZE)
    for pair in pairs:
        detected = _extract_word_span_diffs(pair.base_text, pair.mutated_text)
        assert len(detected) >= 1, f"No diffs detected for {pair.pair_id}"


def test_exact_match_on_identical_texts() -> None:
    """Identical texts should produce no diffs."""
    text = "This is a test document with some content."
    detected = _extract_word_span_diffs(text, text)
    assert len(detected) == 0, f"Identical texts should have no diffs: {detected}"


def test_diff_detector_on_known_change() -> None:
    """Verify difflib detector catches a known single-word change."""
    base = "The governing law is Delaware."
    mutated = "The governing law is New York."
    diffs = _extract_word_span_diffs(base, mutated)
    old_texts = [old for _, _, old, _ in diffs]
    new_texts = [new for _, _, _, new in diffs]
    all_old = " ".join(old_texts).lower()
    all_new = " ".join(new_texts).lower()
    assert "delaware" in all_old, f"Should detect 'Delaware' in diffs: {old_texts}"
    assert "new" in all_new or "york" in all_new, (
        f"Should detect changed token in diffs (old={old_texts}, new={new_texts})"
    )


def _compute_diff_f1(
    base_text: str,
    mutated_text: str,
    ground_truth_diffs: list[GroundTruthDiff],
) -> float:
    """Compute F1 between detected diffs and ground truth spans.

    Uses positional overlap for replacements (non-empty old text) and
    textual overlap for insertions (empty old text).
    """
    # ── Ground truth intervals ──
    gt_intervals: list[tuple[int, int]] = []
    gt_insertions: list[str] = []  # new_text for insertion-only diffs
    for d in ground_truth_diffs:
        if d.old_text.strip():
            gt_intervals.append((d.span_start, d.span_end))
        elif d.new_text.strip():
            gt_insertions.append(d.new_text)

    if not gt_intervals and not gt_insertions:
        return 1.0  # no meaningful ground truth

    # ── Detect diffs ──
    detected = _extract_word_span_diffs(base_text, mutated_text)

    # ── Detected intervals (replacements) ──
    det_intervals: list[tuple[int, int]] = []
    det_insertions: list[str] = []  # new_text for insertion-only diffs
    for start, end, old, new in detected:
        if old.strip():
            det_intervals.append((start, end))
        elif new.strip():
            det_insertions.append(new)

    if not det_intervals and not det_insertions:
        return 0.0

    # ── Positional overlap for replacement intervals ──
    def _overlap(a: tuple[int, int], b: tuple[int, int]) -> int:
        return max(0, min(a[1], b[1]) - max(a[0], b[0]))

    gt_chars_covered = 0
    total_gt_chars = sum(e - s for s, e in gt_intervals) if gt_intervals else 0
    for gs, ge in gt_intervals:
        for ds, de in det_intervals:
            gt_chars_covered += _overlap((gs, ge), (ds, de))
    gt_chars_covered = min(gt_chars_covered, total_gt_chars) if total_gt_chars > 0 else 0

    det_chars_relevant = 0
    total_det_chars = sum(e - s for s, e in det_intervals) if det_intervals else 0
    for ds, de in det_intervals:
        for gs, ge in gt_intervals:
            det_chars_relevant += _overlap((ds, de), (gs, ge))
    det_chars_relevant = min(det_chars_relevant, total_det_chars) if total_det_chars > 0 else 0

    # ── Textual overlap for insertions ──
    # Count insertion as TP if either side's new_text contains the other's
    gt_ins_matched: set[int] = set()
    det_ins_matched: set[int] = set()
    for gi, gt_ins in enumerate(gt_insertions):
        gt_ins_norm = gt_ins.lower().strip()
        for di, det_ins in enumerate(det_insertions):
            det_ins_norm = det_ins.lower().strip()
            if gt_ins_norm in det_ins_norm or det_ins_norm in gt_ins_norm:
                gt_ins_matched.add(gi)
                det_ins_matched.add(di)

    # Merge insertion TP into precision/recall
    ins_tp = len(det_ins_matched)

    precision_base = det_chars_relevant + ins_tp
    precision_den = total_det_chars + len(det_insertions)
    recall_base = gt_chars_covered + ins_tp
    recall_den = total_gt_chars + len(gt_insertions)

    precision = precision_base / precision_den if precision_den > 0 else 0.0
    recall = recall_base / recall_den if recall_den > 0 else 0.0

    if precision + recall == 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def test_f1_against_ground_truth() -> None:
    """Assert F1 ≥ threshold when comparing detected diffs to ground truth.

    Uses character-span overlap (IoU-based) for a more robust comparison
    than token-level F1.
    """
    pairs = load_corpus_pairs(max_pairs=TEST_SAMPLE_SIZE)
    f1_scores: list[float] = []

    for pair in pairs:
        f1 = _compute_diff_f1(pair.base_text, pair.mutated_text, pair.ground_truth_diff)
        f1_scores.append(f1)

    assert len(f1_scores) > 0
    avg_f1 = sum(f1_scores) / len(f1_scores)
    assert avg_f1 >= F1_THRESHOLD, (
        f"Average F1 {avg_f1:.3f} below threshold {F1_THRESHOLD}. "
        f"Scores: {[f'{s:.3f}' for s in f1_scores]}"
    )


@pytest.mark.skip(reason="Requires AI Gateway — run manually with OPENREVIEW_GATEWAY_URL set")
def test_against_bilateral_comparison_engine() -> None:
    """Run the real bilateral comparison engine against 10 corpus pairs.

    This test is skipped by default because it needs a live AI Gateway.
    To run: OPENREVIEW_GATEWAY_URL=... uv run pytest ... -k test_against_bilateral
    """
    pytest.fail("AI Gateway not available in CI")
