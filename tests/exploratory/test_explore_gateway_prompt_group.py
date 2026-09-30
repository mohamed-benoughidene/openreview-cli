"""Exploratory probes: the gateway group, the custom-provider group and the
``prompt`` group.

Offline only: ``gateway setup`` (interactive wizard) and ``gateway refresh``
(network) are intentionally not invoked.  Findings are ``RT-NNN`` register rows.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import Result

EXIT_USER_ERROR = 1
EXIT_USAGE = 2


def _text(result: Result) -> str:
    raw = (getattr(result, "output", "") or "") + (getattr(result, "stderr", "") or "")
    return " ".join(raw.split())


def _user_version(db_path: Path) -> int:
    """Read ``PRAGMA user_version`` from a SQLite database."""
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()


# ── gateway ───────────────────────────────────────────────────────────────


@pytest.mark.fast
@pytest.mark.parametrize("args", [["gateway", "status"], ["gateway", "providers"]])
def test_gateway_read_only_commands_succeed(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], args: list[str]
) -> None:
    result = invoke(args)
    assert result.exit_code == 0, (args, result.exit_code, _text(result))
    assert (result.output or "").strip(), "read-only gateway command must render output"


@pytest.mark.fast
def test_gateway_models_unknown_provider_is_user_error(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    result = invoke(["gateway", "models", "nosuch"])
    assert result.exit_code == EXIT_USER_ERROR, (result.exit_code, _text(result))
    assert "No provider" in _text(result)


@pytest.mark.fast
def test_gateway_set_and_test_reject_unknown_slot(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    set_result = invoke(["gateway", "set", "badslot", "m"])
    assert set_result.exit_code == EXIT_USER_ERROR, (set_result.exit_code, _text(set_result))
    assert "Invalid slot" in _text(set_result)

    test_result = invoke(["gateway", "test", "badslot"])
    assert test_result.exit_code == EXIT_USER_ERROR, (test_result.exit_code, _text(test_result))
    assert "Invalid slot" in _text(test_result)


@pytest.mark.fast
def test_gateway_fallback_validation(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    no_model = invoke(["gateway", "fallback", "extraction"])
    assert no_model.exit_code == EXIT_USER_ERROR, (no_model.exit_code, _text(no_model))
    assert "Provide a model id" in _text(no_model)

    no_slash = invoke(["gateway", "fallback", "extraction", "noSlash"])
    assert no_slash.exit_code == EXIT_USER_ERROR, (no_slash.exit_code, _text(no_slash))
    assert "provider/model id" in _text(no_slash)

    removed_slot = invoke(["gateway", "fallback", "embedding", "openai/x"])
    assert removed_slot.exit_code == EXIT_USER_ERROR, (
        removed_slot.exit_code,
        _text(removed_slot),
    )
    assert "Invalid slot" in _text(removed_slot)


@pytest.mark.fast
def test_gateway_costs_without_selector_is_noop(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    result = invoke(["gateway", "costs"])
    assert result.exit_code == 0, (result.exit_code, _text(result))
    assert "Use --today or --session" in _text(result)

    today = invoke(["gateway", "costs", "--today"])
    assert today.exit_code == 0, (today.exit_code, _text(today))
    assert "Daily cost limit" in _text(today)


@pytest.mark.fast
def test_gateway_provider_add_then_collision(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    first = invoke(["gateway", "provider", "add", "myprov", "--base-url", "http://127.0.0.1:9/v1"])
    assert first.exit_code == 0, (first.exit_code, _text(first))
    assert "Added provider 'myprov'" in _text(first)

    second = invoke(["gateway", "provider", "add", "myprov", "--base-url", "http://127.0.0.1:9/v1"])
    assert second.exit_code == EXIT_USER_ERROR, (second.exit_code, _text(second))
    assert "collision" in _text(second)


@pytest.mark.fast
@pytest.mark.parametrize("cred", ["bad", "k="])
def test_gateway_provider_add_rejects_malformed_cred(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], cred: str
) -> None:
    result = invoke(
        [
            "gateway",
            "provider",
            "add",
            "p",
            "--base-url",
            "http://127.0.0.1:9/v1",
            "--cred",
            cred,
        ]
    )
    assert result.exit_code == EXIT_USAGE, (cred, result.exit_code, _text(result))
    assert "--cred" in _text(result)


# ── prompt ────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_prompt_command_does_not_rewind_schema_version(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    """RT-004: ``PromptStore.init`` executes the raw ``004_prompts.sql`` file,
    which ends in ``PRAGMA user_version = 4`` (``004_prompts.sql:26``).  Running
    any ``prompt`` command therefore rewinds the shared database's schema
    version from its current value (14 here) back to 4, so the *next* CLI
    invocation re-runs migrations 005 to 014 and logs a swallowed-warning storm.

    Intended: schema versioning is monotonic; a read/list command must not
    downgrade it.
    """
    from openreview_cli.config.paths import get_data_dir

    invoke(["config", "get", "privacy.tier"])  # first init runs migrations
    db_path = get_data_dir() / "openreview.db"
    before = _user_version(db_path)
    assert before > 4, before  # reachability: migrations really ran

    invoke(["prompt", "list"])
    after = _user_version(db_path)
    assert after >= before, (before, after)


@pytest.mark.fast
def test_prompt_list_on_empty_db_succeeds(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    result = invoke(["prompt", "list"])
    assert result.exit_code == 0, (result.exit_code, _text(result))
    assert "Prompts" in _text(result)


@pytest.mark.fast
def test_prompt_create_then_duplicate_and_show(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    created = invoke(["prompt", "create", "--name", "p", "--content", "hello"])
    assert created.exit_code == 0, (created.exit_code, _text(created))
    assert "Created prompt 'p' version 1" in _text(created)

    duplicate = invoke(["prompt", "create", "--name", "p", "--content", "hello"])
    assert duplicate.exit_code == EXIT_USER_ERROR, (duplicate.exit_code, _text(duplicate))
    assert "already exists" in _text(duplicate)

    shown = invoke(["prompt", "show", "p"])
    assert shown.exit_code == 0, (shown.exit_code, _text(shown))
    assert "hello" in _text(shown)


@pytest.mark.fast
def test_prompt_show_missing_is_user_error(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    result = invoke(["prompt", "show", "nosuch"])
    assert result.exit_code == EXIT_USER_ERROR, (result.exit_code, _text(result))


@pytest.mark.fast
def test_prompt_show_version_zero_is_rejected(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    """RT-007: ``--version 0`` is falsy, so ``prompt show`` silently returns the
    *latest* version instead of rejecting a non-existent version 0
    (``prompts/cli.py:119`` uses ``if version`` rather than ``is not None``).

    Intended: version 0 is not a valid version, so it must be rejected.
    """
    invoke(["prompt", "create", "--name", "r7", "--content", "body"])
    result = invoke(["prompt", "show", "r7", "--version", "0"])
    assert result.exit_code == EXIT_USAGE, (result.exit_code, _text(result))


@pytest.mark.fast
def test_prompt_delete_missing_is_user_error(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    result = invoke(["prompt", "delete", "nosuch", "--force"])
    assert result.exit_code == EXIT_USER_ERROR, (result.exit_code, _text(result))


@pytest.mark.fast
def test_prompt_diff_missing_version_is_usage_error(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    invoke(["prompt", "create", "--name", "d", "--content", "one"])
    result = invoke(["prompt", "diff", "d", "--from", "1", "--to", "99"])
    assert result.exit_code == EXIT_USAGE, (result.exit_code, _text(result))
    assert "version" in _text(result).lower()


@pytest.mark.fast
def test_prompt_bind_unbind_bindings(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    missing = invoke(
        ["prompt", "bind", "--slot", "extraction", "--prompt", "nosuch", "--version", "1"]
    )
    assert missing.exit_code == EXIT_USER_ERROR, (missing.exit_code, _text(missing))

    bindings = invoke(["prompt", "bindings"])
    assert bindings.exit_code == 0, (bindings.exit_code, _text(bindings))

    unbind = invoke(["prompt", "unbind", "--slot", "extraction"])
    assert unbind.exit_code == EXIT_USER_ERROR, (unbind.exit_code, _text(unbind))


@pytest.mark.fast
def test_prompt_test_version_parsing_and_roadmap_exit(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    invoke(["prompt", "create", "--name", "t", "--content", "body"])

    malformed = invoke(["prompt", "test", "--prompt", "t", "--versions", "abc"])
    assert malformed.exit_code == EXIT_USAGE, (malformed.exit_code, _text(malformed))
    assert "comma-separated version numbers" in _text(malformed)

    empty_token = invoke(["prompt", "test", "--prompt", "t", "--versions", "1,,2"])
    assert empty_token.exit_code == EXIT_USAGE, (empty_token.exit_code, _text(empty_token))

    # Valid versions reach the roadmap placeholder and exit 3.
    reached = invoke(["prompt", "test", "--prompt", "t", "--versions", "1"])
    assert reached.exit_code == 3, (reached.exit_code, _text(reached))
    assert "benchmark harness" in _text(reached)


@pytest.mark.fast
def test_prompt_test_missing_prompt_is_user_error(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    result = invoke(["prompt", "test", "--prompt", "nosuch", "--versions", "1"])
    assert result.exit_code == EXIT_USER_ERROR, (result.exit_code, _text(result))
    assert "not found" in _text(result)


@pytest.mark.fast
def test_prompt_optimize_paths(isolated_dirs: Path, invoke: Callable[[list[str]], Result]) -> None:
    missing = invoke(["prompt", "optimize", "--prompt", "nosuch"])
    assert missing.exit_code == EXIT_USER_ERROR, (missing.exit_code, _text(missing))
    assert "not found" in _text(missing)

    invoke(["prompt", "create", "--name", "o", "--content", "body"])
    bad_iterations = invoke(["prompt", "optimize", "--prompt", "o", "--iterations", "0"])
    assert bad_iterations.exit_code == 3, (bad_iterations.exit_code, _text(bad_iterations))
    assert "Iterations" in _text(bad_iterations)


@pytest.mark.fast
def test_prompt_export_empty_succeeds(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    result = invoke(["prompt", "export"])
    assert result.exit_code == 0, (result.exit_code, _text(result))


@pytest.mark.fast
def test_prompt_import_missing_and_malformed(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], tmp_path: Path
) -> None:
    missing = invoke(["prompt", "import", str(tmp_path / "missing.yaml")])
    assert missing.exit_code == EXIT_USER_ERROR, (missing.exit_code, _text(missing))
    assert "File not found" in _text(missing)

    malformed = tmp_path / "bad.yaml"
    malformed.write_text("- : not a prompt mapping\n", encoding="utf-8")
    bad = invoke(["prompt", "import", str(malformed)])
    assert bad.exit_code == EXIT_USAGE, (bad.exit_code, _text(bad))
    assert "Cannot import" in _text(bad)


# ── negative control ──────────────────────────────────────────────────────


@pytest.mark.fast
def test_negative_control_oracle_rejects_a_wrong_exit_code(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    """Negative control: flip the inner assertion and this case fails."""
    result = invoke(["gateway", "models", "nosuch"])
    assert result.exit_code == EXIT_USER_ERROR, (result.exit_code, _text(result))
    with pytest.raises(AssertionError):
        assert result.exit_code == 0, "negative control: exit 1 is not exit 0"
