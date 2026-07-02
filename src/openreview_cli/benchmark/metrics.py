"""Metric calculators for the benchmark harness.

Implements:
- extraction_f1: token-level F1 for extractive QA (CUAD protocol, NeurIPS 2021)
- comparison_f1: binary classification F1 (match/no-match)
- classification_f1: multi-class classification F1
- avg_latency: mean wall-clock time
- peak_memory: max memory usage
"""

from collections.abc import Sequence

from openreview_cli.benchmark.models import MetricValue


def _f1_from_counts(tp: int, fp: int, fn: int) -> float:
    """Compute F1 score from true/false positive/negative counts."""
    precision_val = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall_val = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    if precision_val + recall_val > 0:
        return 2 * precision_val * recall_val / (precision_val + recall_val)
    return 0.0


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenization for metric computation."""
    import re

    return [t for t in re.split(r"[^\w]+", text) if t]


def extraction_f1(
    predicted_spans: Sequence[tuple[int, int]],
    ground_truth_spans: Sequence[tuple[int, int]],
    text: str,
) -> MetricValue:
    """Token-level F1 for extractive QA.

    Matches the NeurIPS 2021 CUAD evaluation protocol using token overlap.
    """
    tokens = _tokenize(text)
    pred_tokens: set[int] = set()
    for start_char, end_char in predicted_spans:
        _add_token_indices(tokens, text, start_char, end_char, pred_tokens)

    gt_tokens: set[int] = set()
    for start_char, end_char in ground_truth_spans:
        _add_token_indices(tokens, text, start_char, end_char, gt_tokens)

    tp = len(pred_tokens & gt_tokens)
    fp = len(pred_tokens - gt_tokens)
    fn = len(gt_tokens - pred_tokens)

    return MetricValue(value=_f1_from_counts(tp, fp, fn), n=1, unit="f1")


def _add_token_indices(
    tokens: list[str], text: str, start_char: int, end_char: int, token_set: set[int]
) -> None:
    """Add token indices overlapping the given character span."""

    pos = 0
    for i, tok in enumerate(tokens):
        idx = text.find(tok, pos)
        if idx == -1:
            pos += len(tok) + 1
            continue
        tok_start = idx
        tok_end = idx + len(tok)
        if tok_start < end_char and tok_end > start_char:
            token_set.add(i)
        pos = tok_end


def comparison_f1(
    predicted_labels: Sequence[bool],
    ground_truth_labels: Sequence[bool],
) -> MetricValue:
    """Binary classification F1 (match/no-match)."""
    n = len(predicted_labels)
    if n == 0:
        return MetricValue(value=0.0, n=1, unit="f1")

    tp = sum(1 for p, g in zip(predicted_labels, ground_truth_labels, strict=False) if p and g)
    fp = sum(1 for p, g in zip(predicted_labels, ground_truth_labels, strict=False) if p and not g)
    fn = sum(1 for p, g in zip(predicted_labels, ground_truth_labels, strict=False) if not p and g)

    return MetricValue(value=_f1_from_counts(tp, fp, fn), n=n, unit="f1")


def classification_f1(
    predicted_labels: Sequence[str],
    ground_truth_labels: Sequence[str],
    classes: Sequence[str] | None = None,
) -> MetricValue:
    """Multi-class macro-averaged F1.

    If classes is None, infers from union of predicted and ground truth.
    """
    all_classes = set(classes) if classes else (set(predicted_labels) | set(ground_truth_labels))
    f1_scores: list[float] = []
    for cls in sorted(all_classes):
        tp = sum(
            1
            for p, g in zip(predicted_labels, ground_truth_labels, strict=False)
            if p == cls and g == cls
        )
        fp = sum(
            1
            for p, g in zip(predicted_labels, ground_truth_labels, strict=False)
            if p == cls and g != cls
        )
        fn = sum(
            1
            for p, g in zip(predicted_labels, ground_truth_labels, strict=False)
            if p != cls and g == cls
        )
        f1_scores.append(_f1_from_counts(tp, fp, fn))

    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
    return MetricValue(value=macro_f1, n=len(predicted_labels), unit="f1")


def avg_latency(latencies_ms: Sequence[int]) -> MetricValue:
    """Mean wall-clock time."""
    if not latencies_ms:
        return MetricValue(value=0.0, n=1, unit="ms")
    return MetricValue(value=sum(latencies_ms) / len(latencies_ms), n=len(latencies_ms), unit="ms")


def peak_memory(memory_values_mb: Sequence[float]) -> MetricValue:
    """Maximum memory usage."""
    if not memory_values_mb:
        return MetricValue(value=0.0, n=1, unit="MB")
    return MetricValue(value=max(memory_values_mb), n=len(memory_values_mb), unit="MB")
