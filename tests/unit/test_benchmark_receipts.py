"""Receipt guards for docs/BENCHMARKS.md.

Every receipt cited in the page must exist, be small, carry the required keys,
and contain no clause text. The text check is KEY based, not a substring check:
the ContractNLI live receipt notes legitimately contain the word "citations", so
a substring check on "citation" would fail on a clean receipt (decision D6).
Tables that publish numbers must carry a Last verified line naming their receipt.
Models and git_commit are pinned per receipt so an "unrecorded model" or
"unknown commit" claim cannot pass silently (Revision 3, R9).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BENCHMARKS = REPO_ROOT / "docs" / "BENCHMARKS.md"
RESULTS_DIR = REPO_ROOT / "docs" / "benchmarks" / "results"
RECEIPT_KEYS = {
    "benchmark",
    "command",
    "date",
    "git_commit",
    "models",
    "sample",
    "metrics",
    "notes",
}
MAX_RECEIPT_BYTES = 20_000

# Decision D3: exactly these six receipts.
EXPECTED_RECEIPTS = frozenset(
    {
        "pii-throughput.json",
        "product-modes.json",
        "pii-accuracy.json",
        "contractnli-coverage.json",
        "contractnli-live.json",
        "review-accuracy.json",
    }
)
FORBIDDEN_KEYS = frozenset({"citation", "clause_text", "document_text", "text", "original_value"})

# Revision 3, R9: pin the honesty-critical metadata per receipt. The three generated
# receipts carry a real hex commit; the three projected receipts must keep their
# literal "unknown ..." commit and their recorded models (or the "unrecorded" admission).
GENERATED_GIT_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
GENERATED_RECEIPTS = frozenset({"pii-throughput.json", "pii-accuracy.json", "product-modes.json"})
EXPECTED_MODELS: dict[str, Any] = {
    "pii-throughput.json": "none (local Presidio + spaCy en_core_web_lg)",
    "pii-accuracy.json": "none (local Presidio + spaCy en_core_web_lg)",
    "product-modes.json": (
        "none (deterministic mocked gateway; recall measures mode to playbook category match)"
    ),
    "contractnli-coverage.json": "none (nupunkt sentence segmentation, local)",
    "contractnli-live.json": {
        "extraction": "openrouter/anthropic/claude-sonnet-4.6",
        "qa": "openrouter/anthropic/claude-sonnet-4.6",
    },
    "review-accuracy.json": "unrecorded in source artifact",
}
UNKNOWN_GIT_COMMITS: dict[str, str] = {
    "contractnli-coverage.json": (
        "unknown (source corpus is gitignored; commit of the corpus snapshot is not recorded)"
    ),
    "contractnli-live.json": (
        "unknown (frozen live run predates this branch; the source artifact is gitignored)"
    ),
    "review-accuracy.json": (
        "unknown (re-run predates this branch; the source artifact is gitignored)"
    ),
}

TABLES: dict[str, str] = {
    "## Throughput": "pii-throughput.json",
    "## Pipeline-wiring recall (mocked)": "product-modes.json",
    "## PII accuracy (measured 50 seeded contracts)": "pii-accuracy.json",
    "## Review accuracy (measured 12 labeled NDA clauses)": "review-accuracy.json",
    "## ContractNLI public benchmark (real-world NDAs measured)": "contractnli-coverage.json",
    "### Live LLM extraction + QA verification on real ContractNLI NDAs": "contractnli-live.json",
}


def _page() -> str:
    return BENCHMARKS.read_text(encoding="utf-8")


def _section_after(text: str, heading: str) -> str:
    """Return the text after heading up to the next markdown heading of any level."""
    body = text.split(heading, 1)[1]
    lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("#"):
            break
        lines.append(line)
    return "\n".join(lines)


def _iter_keys(node: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            keys.append(str(key))
            keys.extend(_iter_keys(value))
    elif isinstance(node, list):
        for item in node:
            keys.extend(_iter_keys(item))
    return keys


def test_results_dir_contains_exactly_the_six_expected_receipts() -> None:
    assert RESULTS_DIR.is_dir(), f"missing {RESULTS_DIR}"
    present = {path.name for path in RESULTS_DIR.glob("*.json")}
    assert present == EXPECTED_RECEIPTS, (
        f"missing: {sorted(EXPECTED_RECEIPTS - present)}, "
        f"unexpected: {sorted(present - EXPECTED_RECEIPTS)}"
    )


def test_every_cited_receipt_exists_and_is_well_formed() -> None:
    cited = sorted(set(re.findall(r"docs/benchmarks/results/([A-Za-z0-9_.-]+\.json)", _page())))
    assert cited, "docs/BENCHMARKS.md cites no receipt"
    for name in cited:
        path = RESULTS_DIR / name
        assert path.exists(), f"cited receipt is missing: {path}"
        assert path.stat().st_size <= MAX_RECEIPT_BYTES, f"{name} is too large for a receipt"
        payload = json.loads(path.read_text(encoding="utf-8"))
        missing = RECEIPT_KEYS - set(payload)
        assert not missing, f"{name} is missing keys: {sorted(missing)}"


def test_no_receipt_contains_text_bearing_keys() -> None:
    for path in sorted(RESULTS_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        bad = FORBIDDEN_KEYS & set(_iter_keys(payload))
        assert not bad, f"{path.name} contains text-bearing keys: {sorted(bad)}"


def test_receipt_metadata_is_honest() -> None:
    """Pin models and git_commit per receipt (Revision 3, R9).

    Enforces the "unrecorded model" and "unknown commit" claims: a projected
    receipt that silently gains a real commit, or a generated receipt that claims
    an unknown commit, fails here.
    """
    for name in sorted(EXPECTED_RECEIPTS):
        path = RESULTS_DIR / name
        assert path.exists(), f"missing receipt: {path}"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["models"] == EXPECTED_MODELS[name], f"{name}: unexpected models"
        commit = payload["git_commit"]
        if name in GENERATED_RECEIPTS:
            assert GENERATED_GIT_COMMIT.fullmatch(commit), (
                f"{name}: {commit!r} is not a recorded hex commit"
            )
        else:
            assert commit == UNKNOWN_GIT_COMMITS[name], f"{name}: unexpected git_commit"


def test_each_results_table_has_a_last_verified_line() -> None:
    text = _page()
    for heading, receipt in TABLES.items():
        assert heading in text, f"missing heading: {heading}"
        section = _section_after(text, heading)
        assert "Last verified:" in section, f"no Last verified line under {heading}"
        assert receipt in section, f"{heading} does not cite {receipt}"


def test_pii_throughput_numbers_match_the_receipt() -> None:
    metrics = json.loads((RESULTS_DIR / "pii-throughput.json").read_text(encoding="utf-8"))[
        "metrics"
    ]
    text = _page()
    assert f"{metrics['total_documents']} processed rows" in text
    assert f"{metrics['total_entities_detected']:,} entities" in text
    assert f"{metrics['total_duration_s']} s total" in text
    stress = metrics["stress"]
    assert f"{stress['duration_s']} s" in text
    assert f"~{round(stress['peak_memory_rss_mb'])} MB" in text


def test_product_mode_row_matches_the_receipt() -> None:
    metrics = json.loads((RESULTS_DIR / "product-modes.json").read_text(encoding="utf-8"))[
        "metrics"
    ]
    text = _page()
    assert f"{len(metrics['mode_results'])} modes x 5 docs" in text
    assert f"{metrics['worst_recall']:.0%} recall" in text
