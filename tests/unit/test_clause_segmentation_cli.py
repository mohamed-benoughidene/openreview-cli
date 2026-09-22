"""R3/D2: the clause-segmentation benchmark can be pointed at CUAD or MAUD."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers.benchmark_scripts import load_benchmark_script

SEG = load_benchmark_script("benchmark_cuad_segmentation")
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_cuad_defaults_are_unchanged() -> None:
    """The published CUAD reproduction command and receipt command must keep working."""
    args = SEG.parse_args([])
    assert args.dataset == "cuad"
    assert args.corpus == Path("data/legalbenchrag/benchmarks/cuad.json")
    assert args.corpus_root == Path("data/legalbenchrag/corpus")
    assert args.output == Path(".benchmark-reports/cuad-segmentation.json")


def test_maud_defaults_point_at_the_local_corpus() -> None:
    args = SEG.parse_args(["--dataset", "maud"])
    assert args.corpus == Path("data/legalbenchrag/benchmarks/maud.json")
    assert args.corpus_root == Path("data/legalbenchrag/corpus")
    assert args.output == Path(".benchmark-reports/maud-segmentation.json")
    # The corpus lives under the gitignored data/ tree, so a fresh CI clone has
    # none. The defaults above must hold everywhere; only the on-disk presence
    # check is environment-dependent.
    if not (REPO_ROOT / args.corpus).is_file():
        pytest.skip("MAUD corpus is gitignored; absent in CI")


def test_main_derives_the_benchmark_label_from_the_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drive the real ``main`` and assert the label it hands to ``evaluate``.

    The label is ``f"{args.dataset}-segmentation"``, so CUAD stays ``cuad-segmentation``
    and ``--dataset maud`` yields ``maud-segmentation``. (A constant-expression assert
    like ``f"{'cuad'}-segmentation" == "cuad-segmentation"`` proves nothing.)
    """
    seen: dict[str, str] = {}

    def fake_evaluate(
        corpus_path: Path, corpus_root: Path, corpus_label: str, benchmark: str
    ) -> dict[str, object]:
        seen["benchmark"] = benchmark
        return {
            "benchmark": benchmark,
            "corpus": corpus_label,
            "documents_loaded": 1,
            "spans_evaluated": 1,
            "spans_contained": 1,
            "containment_rate": 1.0,
            "token_f1_mean": 1.0,
            "tests_with_span": 1,
            "tests_any_span_contained": 1,
            "test_coverage_rate": 1.0,
            "missing_snippets": 0,
            "unreadable_file_paths": [],
            "elapsed_seconds": 0.0,
        }

    monkeypatch.setattr(SEG, "evaluate", fake_evaluate)
    output = tmp_path / "out.json"
    SEG.main(["--dataset", "maud", "--output", str(output)])
    assert seen["benchmark"] == "maud-segmentation"
    assert json.loads(output.read_text(encoding="utf-8"))["benchmark"] == "maud-segmentation"


def test_evaluate_puts_the_passed_benchmark_into_the_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``evaluate``'s 4th argument is what lands in the result's ``benchmark`` key."""
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    (corpus_root / "doc_a.txt").write_text("Hello world.", encoding="utf-8")
    corpus_path = tmp_path / "maud.json"
    corpus_path.write_text(
        json.dumps({"tests": [{"snippets": [{"file_path": "doc_a.txt", "span": [0, 5]}]}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(SEG, "segment", lambda text: [])
    result = SEG.evaluate(corpus_path, corpus_root, "tiny-subset", "maud-segmentation")
    assert result["benchmark"] == "maud-segmentation"
    assert result["corpus"] == "tiny-subset"
