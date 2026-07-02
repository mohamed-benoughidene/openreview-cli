"""PII accuracy evaluator.

Runs the PII detection engine against seeded documents and compares
detected entities against ground truth by (value, type) exact match.
"""

from collections import Counter
from collections.abc import Callable

from openreview_cli.benchmark.metrics import _f1_from_counts
from openreview_cli.benchmark.models import MetricValue

# Entity types from ground_truth.json
PII_ENTITY_TYPES = frozenset(
    {
        "PERSON",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "LOCATION",
        "DATE_TIME",
        "AMOUNT",
        "TAX_ID",
        "ACCT",
        "ID_DOCUMENT",
        "REG_NUMBER",
        "ORGANIZATION",
    }
)


def evaluate_pii_accuracy(
    documents: list[tuple[str, str, list[dict[str, str]]]],
    detect_fn: Callable[[str], list[dict[str, str]]],
) -> dict[str, MetricValue]:
    """Evaluate PII detection accuracy against ground truth.

    Args:
        documents: List of (doc_id, text, ground_truth_entities) tuples
        detect_fn: Function that takes text and returns list of
                   {'value': str, 'type': str} detections

    Returns:
        Dict of metric_name -> MetricValue, including per-type breakdown
    """
    all_predictions: list[bool] = []
    per_type_total: Counter[str] = Counter()
    per_type_correct: Counter[str] = Counter()

    for _doc_id, text, gt_entities in documents:
        detected = detect_fn(text)

        # Build normalized sets for comparison
        detected_pairs = {(d["value"].strip().lower(), d["type"]) for d in detected}
        gt_pairs = {(g["value"].strip().lower(), g["type"]) for g in gt_entities}

        # Overall
        for pair in detected_pairs:
            all_predictions.append(pair in gt_pairs)
        for pair in gt_pairs:
            _type = pair[1]
            if _type in PII_ENTITY_TYPES:
                per_type_total[_type] += 1
                if pair in detected_pairs:
                    per_type_correct[_type] += 1

    metrics: dict[str, MetricValue] = {}

    # Overall metrics
    if all_predictions:
        total_predicted_correct = sum(all_predictions)
        total_ground_truths = sum(per_type_total.values())
        total_precision = total_predicted_correct / len(all_predictions)
        total_recall = total_predicted_correct / total_ground_truths if total_ground_truths else 0.0
        overall_f1 = _f1_from_counts(
            total_predicted_correct,
            len(all_predictions) - total_predicted_correct,
            total_ground_truths - total_predicted_correct,
        )

        metrics["pii_recall"] = MetricValue(
            value=total_recall, n=total_ground_truths, unit="recall"
        )
        metrics["pii_precision"] = MetricValue(
            value=total_precision, n=len(all_predictions), unit="precision"
        )
        metrics["pii_f1"] = MetricValue(value=overall_f1, n=total_ground_truths, unit="f1")
    else:
        metrics["pii_recall"] = MetricValue(value=0.0, n=0, unit="recall")
        metrics["pii_precision"] = MetricValue(value=0.0, n=0, unit="precision")
        metrics["pii_f1"] = MetricValue(value=0.0, n=0, unit="f1")

    # Per-type breakdown
    for entity_type, total in per_type_total.items():
        correct = per_type_correct[entity_type]
        type_recall = correct / total
        metrics[f"pii_recall_{entity_type.lower()}"] = MetricValue(
            value=type_recall, n=total, unit="recall"
        )

    return metrics
