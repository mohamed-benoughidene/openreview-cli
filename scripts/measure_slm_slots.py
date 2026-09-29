"""Measure clause-detection quality of local (Ollama) models on the bundled fixtures.

This is a measurement, not a test. It runs the product review pipeline for one
mode's documents with one model on the text slots, then scores the result against
that mode's ``ground_truth.json`` (expected category + expected position per
document). It writes a JSON result and prints a markdown summary.

Intended to run against a local Ollama server (see
``.github/workflows/slm-measurement.yml``). Reranking is not measured: no local
Ollama rerank is supported.

Usage:
    uv run python scripts/measure_slm_slots.py --model ollama/qwen3:4b --out results/qwen3-4b.json
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

FIXTURES = Path("tests/fixtures/benchmark")

# Route every text slot to the model under test, so the run is internally consistent.
_SLOT_ENV_KEYS = {
    slot: f"OPENREVIEW_GATEWAY__MODELS__{slot.upper()}__PRIMARY"
    for slot in ("extraction", "reasoning", "grounding", "graph")
}


def _git_sha() -> str:
    return os.environ.get("GITHUB_SHA", "unknown")[:12]


def _configure_slots(model: str) -> None:
    """Point every text slot at ``model`` via the documented env override."""
    for env_key in _SLOT_ENV_KEYS.values():
        os.environ[env_key] = model


def _score(assessments: list[Any], expected: list[dict[str, str]]) -> dict[str, int]:
    """Return category-match and position-match counts for one document."""
    detected = {a.playbook_category: a.position.value for a in assessments}
    matched = 0
    position_ok = 0
    for exp in expected:
        category = exp["category_id"]
        if category in detected:
            matched += 1
            if detected[category] == exp["expected_position"]:
                position_ok += 1
    return {"matched": matched, "position_ok": position_ok}


def _markdown(result: dict[str, Any]) -> str:
    totals = result["totals"]
    lines = [
        f"### {result['model']} — {result['mode']}",
        "",
        f"- documents: {result['documents']}",
        f"- categories matched: {totals['matched']}/{totals['expected']} "
        f"(recall {result['recall']})",
        f"- position correct: {totals['position_ok']}/{totals['expected']} "
        f"(accuracy {result['position_accuracy']})",
        "",
        "| doc | matched | position ok | seconds | error |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {d['doc']} | {d['matched']}/{len(d['expected'])} | {d['position_ok']} | "
        f"{d['seconds']} | {d['error'] or ''} |"
        for d in result["per_document"]
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Model under test, e.g. ollama/qwen3:4b.")
    parser.add_argument("--mode", default="indemnitycheck", help="Mode whose fixtures to use.")
    parser.add_argument("--fixtures-dir", type=Path, default=FIXTURES)
    parser.add_argument("--out", type=Path, required=True, help="Where to write the JSON result.")
    args = parser.parse_args()

    _configure_slots(args.model)

    from openreview_cli.review import run_review
    from openreview_cli.review.playbook import BUNDLED_PLAYBOOKS

    mode_dir = args.fixtures_dir / args.mode
    ground_truth: list[dict[str, Any]] = json.loads((mode_dir / "ground_truth.json").read_text())
    playbook_path = str(BUNDLED_PLAYBOOKS[args.mode])

    totals = {"matched": 0, "position_ok": 0, "expected": 0}
    per_document: list[dict[str, Any]] = []
    for entry in ground_truth:
        doc_path = Path(entry["path"])
        expected = entry["expected_categories"]
        started = time.perf_counter()
        error: str | None = None
        score = {"matched": 0, "position_ok": 0}
        try:
            reports = run_review(
                paths=[str(doc_path)],
                playbook_path=playbook_path,
                extraction_model="extraction",
                qa_model=None,
                no_pii=True,  # synthetic fixtures; skips the spaCy/PII dependency
                mode=args.mode,
            )
            assessments = [a for r in reports for a in r.assessments]
            score = _score(assessments, expected)
            totals["matched"] += score["matched"]
            totals["position_ok"] += score["position_ok"]
        except Exception as exc:  # a failing document is recorded, not fatal
            error = f"{type(exc).__name__}: {exc}"
        totals["expected"] += len(expected)
        per_document.append(
            {
                "doc": doc_path.name,
                "expected": expected,
                "matched": score["matched"],
                "position_ok": score["position_ok"],
                "seconds": round(time.perf_counter() - started, 2),
                "error": error,
            }
        )
        print(
            f"[{args.model}] {doc_path.name}: {score['matched']}/{len(expected)} matched",
            flush=True,
        )

    expected_total = totals["expected"]
    result: dict[str, Any] = {
        "model": args.model,
        "mode": args.mode,
        "git_sha": _git_sha(),
        "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "documents": len(per_document),
        "totals": totals,
        "recall": round(totals["matched"] / expected_total, 4) if expected_total else 0.0,
        "position_accuracy": (
            round(totals["position_ok"] / expected_total, 4) if expected_total else 0.0
        ),
        "per_document": per_document,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))

    print("\n" + _markdown(result))
    print(f"\nJSON written to {args.out}")


if __name__ == "__main__":
    main()
