"""Integration test for P3-C1: runtime --no-pii guard for cloud providers.

P3-C1 defect: ``src/openreview_cli/review/runner.py`` did NOT abort
when ``no_pii=True`` and the configured extraction model resolves to
a cloud provider. The fix adds a runtime guard that aborts the
pipeline before any cloud LLM call. Defense in depth alongside the
agent-level Rule 13 in the skill.

The guard:
- Aborts with ``SystemExit`` when ``no_pii=True`` AND the model is a
  cloud provider (anything other than a known local prefix
  ``ollama/`` or ``local/``).
- Does NOT abort when the model is a known local provider
  (sanctioned Rule 13 resolution).
- Does NOT abort when the model has no ``/`` (test stubs,
  legacy single-token model ids).
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest

RUNNER_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "openreview_cli" / "review" / "runner.py"
)
SKILL_PATH = Path(__file__).resolve().parents[2] / "skill" / "SKILL.md"


@pytest.fixture(scope="module")
def runner_text() -> str:
    assert RUNNER_PATH.exists(), f"runner.py not found at {RUNNER_PATH}"
    return RUNNER_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Text-based structural tests (the guard must exist and reference the
# correct prefixes).
# ---------------------------------------------------------------------------


def test_no_pii_runtime_guard_present(runner_text: str) -> None:
    """P3-C1: the runtime --no-pii guard exists in _run_review_doc_pipeline."""
    fn_match = re.search(
        r"def\s+_run_review_doc_pipeline\s*\([^)]*\)\s*->\s*[^:]+:\s*\n(?P<body>.*?)(?=\ndef\s|\nclass\s|\Z)",
        runner_text,
        re.DOTALL,
    )
    assert fn_match, "_run_review_doc_pipeline not found in runner.py"
    body = fn_match.group("body")
    assert "no_pii" in body and ("ollama" in body or "ollama/" in body), (
        "P3-C1 regression: the runtime --no-pii guard is missing or incomplete in "
        "_run_review_doc_pipeline."
    )


def test_no_pii_guard_accepts_local_prefix(runner_text: str) -> None:
    """P3-C1: the guard must also accept the `local/` prefix (per `_LOCAL_PROVIDER_PREFIXES`).

    The codebase's authoritative local-provider prefix set is
    `{"ollama", "local"}` (see `gateway/tier_router.py:20`). A
    `local/llama-3.1` model with `no_pii=True` is the sanctioned
    Rule 13 resolution. The guard must NOT abort for it.
    """
    fn_match = re.search(
        r"def\s+_run_review_doc_pipeline\s*\([^)]*\)\s*->\s*[^:]+:\s*\n(?P<body>.*?)(?=\ndef\s|\nclass\s|\Z)",
        runner_text,
        re.DOTALL,
    )
    assert fn_match
    body = fn_match.group("body")
    # The guard should reference "local/" as a known local prefix.
    assert '"local/"' in body or "'local/'" in body, (
        "P3-C1 HIGH finding (H-1): the guard does NOT accept the `local/` prefix. "
        "A user running with extraction_model='local/llama-3.1' and --no-pii would be "
        "incorrectly aborted. The fix: add `local/` to the set of known local prefixes "
        "alongside `ollama/` (see `_LOCAL_PROVIDER_PREFIXES` in "
        "`src/openreview_cli/gateway/tier_router.py:20`)."
    )


# ---------------------------------------------------------------------------
# Behavioral tests: drive the actual function with mocked downstream and
# observe the guard's abort / no-abort behavior.
# ---------------------------------------------------------------------------


def _invoke_guard(extraction_model: str, no_pii: bool) -> str:
    """Call _run_review_doc_pipeline and return the result label.

    Returns "ABORT" if the guard raised SystemExit, "PROCEED" if the
    function got past the guard (and then failed downstream with
    some other error), or "OK" if the function completed without
    raising.
    """
    from openreview_cli.review.runner import _run_review_doc_pipeline

    with (
        patch(
            "openreview_cli.review.runner._configured_providers",
            return_value=[],
        ),
        patch(
            "openreview_cli.recovery.coordinator.RecoveryCoordinator.__init__",
            return_value=None,
        ),
    ):
        try:
            _run_review_doc_pipeline(
                doc_path="tests/fixtures/nda_with_pii.pdf",
                playbook=None,
                playbook_version=None,
                extraction_model=extraction_model,
                qa_model=extraction_model,
                no_pii=no_pii,
                verbose=False,
                confidence_threshold=0.7,
            )
        except SystemExit as e:
            msg = str(e)
            if "--no-pii is incompatible with cloud provider" in msg:
                return "ABORT"
            return f"ABORT_OTHER:{msg[:60]}"
        except Exception:
            return "PROCEED"
        return "OK"


def test_guard_aborts_cloud_provider_with_no_pii() -> None:
    """P3-C1: cloud provider + no_pii must abort (the anti-pattern)."""
    assert _invoke_guard("openai/gpt-4o", True) == "ABORT"


def test_guard_aborts_anthropic_cloud_with_no_pii() -> None:
    """P3-C1: anthropic + no_pii must abort."""
    assert _invoke_guard("anthropic/claude-3-5-sonnet", True) == "ABORT"


def test_guard_aborts_openrouter_with_no_pii() -> None:
    """P3-C1: openrouter + no_pii must abort."""
    assert _invoke_guard("openrouter/anthropic/claude-sonnet-4.5", True) == "ABORT"


def test_guard_does_not_abort_ollama_with_no_pii() -> None:
    """P3-C1: ollama + no_pii must NOT abort (sanctioned Rule 13 resolution)."""
    result = _invoke_guard("ollama/qwen3:8b", True)
    assert result != "ABORT", f"ollama + no_pii incorrectly aborted ({result})"


def test_guard_does_not_abort_local_with_no_pii() -> None:
    """P3-C1 H-1: `local/...` + no_pii must NOT abort.

    `_LOCAL_PROVIDER_PREFIXES` in `gateway/tier_router.py:20` includes
    both `ollama` and `local`. The C1 guard must mirror this set.
    """
    result = _invoke_guard("local/llama-3.1", True)
    assert result != "ABORT", (
        f"H-1 regression: `local/llama-3.1` + no_pii incorrectly aborted ({result}). "
        "The guard must accept the `local/` prefix as a known local provider."
    )


def test_guard_does_not_abort_test_stub() -> None:
    """P3-C1: test stubs (e.g. plain 'extraction') must NOT abort."""
    result = _invoke_guard("extraction", True)
    assert result != "ABORT", f"test stub 'extraction' + no_pii incorrectly aborted ({result})"


def test_guard_does_not_abort_when_no_pii_false() -> None:
    """P3-C1: without --no-pii, the guard must NOT abort (PII stripping runs)."""
    result = _invoke_guard("openai/gpt-4o", False)
    assert result != "ABORT", f"openai without no_pii incorrectly aborted ({result})"


# ---------------------------------------------------------------------------
# Skill-text cross-check: the skill must NOT promise ollama-only and must
# mention the local/ alternative.
# ---------------------------------------------------------------------------


def test_skill_documents_local_prefix(skill_text: str) -> None:
    """P3-C1: the skill (or Rule 13) must acknowledge the `local/` provider as well."""
    # The Rule 13 area should mention both ollama and local as sanctioned
    # local providers. The P3 additions to the cost-limit / privacy tier
    # section can also be a home for this.
    body = skill_text
    has_local = "local/" in body or "'local'" in body or '"local"' in body
    assert has_local, (
        "P3-C1 follow-up: the skill should mention the `local/` provider as "
        "a sanctioned local-prefix alongside `ollama/`. See "
        "`_LOCAL_PROVIDER_PREFIXES` in `gateway/tier_router.py:20`."
    )
