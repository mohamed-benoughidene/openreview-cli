"""End-to-end mocked coverage for all 23 named product modes.

The coverage test reads the COMMITTED fixtures under tests/fixtures/benchmark/<mode>/,
so it fails until task D4 generates them. It does not generate fixtures itself;
generating them here would make the test pass immediately and hide the gap.

The script harness patches the gateway itself (task D4 Step 4), so this test patches
nothing. It instead asserts on the observable result of that stub, so a silent
fallback to the real gateway cannot pass.
"""

from __future__ import annotations

import json

import pytest

from openreview_cli.app import _PRODUCT_MODES
from tests.helpers.benchmark_scripts import load_benchmark_script

BENCH = load_benchmark_script("benchmark_product_modes")
NAMED_MODES = sorted({entry[0] for entry in _PRODUCT_MODES})
# The deterministic stub in scripts/benchmark_product_modes.py returns this citation.
STUB_CITATION = "Deterministic benchmark response."
# A mode whose fixtures are committed on HEAD, so the stub test has data before D4 generates the rest.
SMOKE_MODE = "indemnitycheck"


@pytest.mark.slow
def test_all_named_modes_reach_full_recall_on_committed_fixtures() -> None:
    assert len(NAMED_MODES) == 23
    failures: list[str] = []
    for mode in NAMED_MODES:
        ground_truth_path = BENCH.FIXTURES / mode / "ground_truth.json"
        assert ground_truth_path.exists(), (
            f"no committed ground truth for '{mode}' at {ground_truth_path}; run "
            "`uv run python scripts/benchmark_product_modes.py --generate-only` (task D4 Step 6)"
        )
        docs = json.loads(ground_truth_path.read_text(encoding="utf-8"))
        result = BENCH._run_mode_benchmark(mode, docs[:1])
        if result["recall"] != 1.0 or result["matched_categories"] != result["expected_categories"]:
            failures.append(f"{mode}: {result}")
    assert not failures, "modes with unwired categories: " + "; ".join(failures)


@pytest.mark.slow
def test_pipeline_uses_the_deterministic_stub_not_the_real_gateway() -> None:
    """Prove the mocked path is reached. On HEAD this FAILS.

    On HEAD _run_doc_pipeline rebinds openreview_cli.review._gateway.call_gateway_chat,
    but extraction and qa bound that name at import time, so the real gateway runs and
    extract_clause falls back to its error path: assessment.error is set and
    assessment.citation is empty.
    """
    docs = json.loads(
        (BENCH.FIXTURES / SMOKE_MODE / "ground_truth.json").read_text(encoding="utf-8")
    )
    doc_path = (BENCH.FIXTURES / SMOKE_MODE / f"doc_{docs[0]['doc_index']}.pdf").resolve()
    assessments = BENCH._run_doc_pipeline(
        doc_path=str(doc_path),
        playbook_path=str(BENCH.BUNDLED_PLAYBOOKS[SMOKE_MODE]),
        mode=SMOKE_MODE,
    )
    assert assessments, f"no assessments for '{SMOKE_MODE}'"
    for assessment in assessments:
        assert assessment.error is None, (
            f"the real gateway was reached for '{SMOKE_MODE}': {assessment.error}"
        )
        assert assessment.citation == STUB_CITATION, (
            f"the deterministic stub was not used for '{SMOKE_MODE}': {assessment.citation!r}"
        )
