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
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

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

# Decision D3: exactly these seven receipts.
EXPECTED_RECEIPTS = frozenset(
    {
        "pii-throughput.json",
        "product-modes.json",
        "pii-accuracy.json",
        "contractnli-coverage.json",
        "contractnli-live.json",
        "review-accuracy.json",
        "cuad-segmentation.json",
    }
)
FORBIDDEN_KEYS = frozenset({"citation", "clause_text", "document_text", "text", "original_value"})

# Revision 3, R9: pin the honesty-critical metadata per receipt. The generated
# receipts carry a real hex commit; the projected receipts must keep their
# literal "unknown ..." commit and their recorded models (or the "unrecorded" admission).
GENERATED_GIT_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
GENERATED_RECEIPTS = frozenset(
    {"pii-throughput.json", "pii-accuracy.json", "product-modes.json", "cuad-segmentation.json"}
)
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
    "cuad-segmentation.json": "none (nupunkt sentence segmentation, local)",
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
    "## CUAD public benchmark (scale and timing)": "cuad-segmentation.json",
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


def _git(args: list[str]) -> tuple[bool, str]:
    """Run ``git <args>`` in ``REPO_ROOT``; return ``(ok, stdout.strip())``.

    ``ok`` is false for a non-zero exit code, a missing git binary, or a run that
    times out — callers treat any of those as "the check could not be trusted".
    """
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False, ""
    return completed.returncode == 0, completed.stdout.strip()


def generated_commit_problems() -> list[str] | None:
    """Check the recorded commits of the generated receipts (Revision 3, R9).

    Returns ``None`` when the check cannot be run — there is no usable git
    checkout, or it is a shallow clone whose older objects are absent, so neither
    existence nor ancestry of a recorded commit can be established. Otherwise
    returns a list of human-readable problems: each generated receipt's
    ``git_commit`` must exist (``git cat-file -e <sha>^{commit}``) and be an
    ancestor of ``HEAD`` (``git merge-base --is-ancestor <sha> HEAD``). A shape
    match alone is not enough: a plausible-but-bogus hex string must fail here.
    """
    ok, shallow = _git(["rev-parse", "--is-shallow-repository"])
    if not ok or shallow == "true":
        return None
    problems: list[str] = []
    for name in sorted(GENERATED_RECEIPTS):
        commit = json.loads((RESULTS_DIR / name).read_text(encoding="utf-8"))["git_commit"]
        exists, _ = _git(["cat-file", "-e", f"{commit}^{{commit}}"])
        if not exists:
            problems.append(
                f"{name}: recorded git_commit {commit!r} does not exist in this repository"
            )
            continue
        ancestor, _ = _git(["merge-base", "--is-ancestor", commit, "HEAD"])
        if not ancestor:
            problems.append(f"{name}: recorded git_commit {commit!r} is not an ancestor of HEAD")
    return problems


def test_results_dir_contains_exactly_the_expected_receipts() -> None:
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


def test_generated_receipt_commits_exist_and_are_ancestors() -> None:
    """Guard R9 for real: a shape match is not enough, the commit must be real.

    When the check is unverifiable (shallow clone, or no git checkout) the
    helper returns ``None`` and this test skips loudly rather than passing
    silently — CI checks out shallow, so the guard must degrade, not break.
    """
    problems = generated_commit_problems()
    if problems is None:
        pytest.skip(
            "commit existence/ancestry is unverifiable here (shallow clone or not a "
            "git checkout); the receipt-commit guard runs fully in a full clone"
        )
    assert not problems, "generated receipt commits are untrustworthy: " + "; ".join(problems)


def _patch_git(
    monkeypatch: pytest.MonkeyPatch,
    *,
    shallow: str,
    cat_file_ok: bool,
    merge_base_ok: bool,
) -> None:
    """Replace ``_git`` with a deterministic stub keyed on the git subcommand."""

    def fake_git(args: list[str]) -> tuple[bool, str]:
        if args[:2] == ["rev-parse", "--is-shallow-repository"]:
            return True, shallow
        if args and args[0] == "cat-file":
            return cat_file_ok, ""
        if args and args[0] == "merge-base":
            return merge_base_ok, ""
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(sys.modules[__name__], "_git", fake_git)


def test_generated_commit_problems_flag_a_bogus_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """A plausible-but-bogus hex commit fails both existence and ancestry."""
    _patch_git(monkeypatch, shallow="false", cat_file_ok=False, merge_base_ok=False)
    problems = generated_commit_problems()
    assert problems is not None
    assert len(problems) == len(GENERATED_RECEIPTS)
    assert all("does not exist" in problem for problem in problems)


def test_generated_commit_problems_flag_a_non_ancestor_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real commit that is not an ancestor of HEAD is still a problem."""
    _patch_git(monkeypatch, shallow="false", cat_file_ok=True, merge_base_ok=False)
    problems = generated_commit_problems()
    assert problems is not None
    assert len(problems) == len(GENERATED_RECEIPTS)
    assert all("not an ancestor of HEAD" in problem for problem in problems)


def test_generated_commit_problems_accept_an_ancestor_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An existing commit that is an ancestor of HEAD yields no problems."""
    _patch_git(monkeypatch, shallow="false", cat_file_ok=True, merge_base_ok=True)
    assert generated_commit_problems() == []


def test_generated_commit_problems_return_none_for_a_shallow_clone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A shallow clone cannot check ancestry, so the helper opts out (no problems)."""
    _patch_git(monkeypatch, shallow="true", cat_file_ok=True, merge_base_ok=True)
    assert generated_commit_problems() is None


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


def test_cuad_segmentation_numbers_match_the_receipt() -> None:
    payload = json.loads((RESULTS_DIR / "cuad-segmentation.json").read_text(encoding="utf-8"))
    metrics = payload["metrics"]
    sample = payload["sample"]
    text = _page()
    assert f"{metrics['containment_rate']:.2%} of {sample['spans_evaluated']:,} spans" in text
    assert f"token-F1 {metrics['token_f1_mean']:.3f}" in text
    assert f"{metrics['test_coverage_rate']:.2%} of {metrics['tests_with_span']:,} queries" in text
    assert f"{sample['documents_loaded']} of 462 documents" in text
