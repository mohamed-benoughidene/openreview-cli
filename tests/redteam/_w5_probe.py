"""Private W5 red-team harness: the dispatch seam, the registry doubles, the oracle.

W5 is discovery-only, so the attack technique matters more than the assertions
that follow it. The technique is the plan's own (section 10, W5): patch the
dispatch seam so that it *records the call and then raises*
``AssertionError("dispatched <model>")``. A test that then passes proves the
network was never reached — not merely that a boolean came back correct. The
record matters because ``Gateway._call_with_fallback`` catches ``Exception`` and
re-classifies it, so a bare ``AssertionError`` is swallowed into
``UnclassifiedProviderError`` and would otherwise be invisible: the record is
what makes the dispatch observable, and the cloud-call counter now counts every
dispatch attempt too.

Kept as one private module, following the W4 precedent
(``tests/fuzz/_state_probe.py``), because the plan keeps the redteam tree
conftest-free and both W5 suites need the same three seams:

* :func:`prepare_state` redirects all four XDG roots — including
  ``XDG_STATE_HOME``, which is where ``_init`` (``app.py:231-232``) writes
  ``openreview.log`` — at a per-test ``tmp_path``. No test touches the
  developer's real config/data/state/cache trees.
* :class:`DispatchRecorder` is the instrumented dispatch seam. ``fail=True``
  raises after recording (the no-dispatch oracle); ``fail=False`` returns a
  response double so a *successful* dispatch can be measured against the
  counter.
* :func:`make_gateway` builds ``Gateway.__new__(Gateway)`` (the verified partial
  construction seam) with a real migrated database, because ``_prepare_chat``
  opens ``PromptStore(self._data_path)``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

from openreview_cli.app import app
from openreview_cli.gateway.models import Capability, ProviderInfo
from openreview_cli.gateway.router import Gateway
from openreview_cli.gateway.tier_config import TierConfig
from openreview_cli.storage.database import init_database
from tests.helpers.stream_doubles import StreamChunk, TerminatedStream

REPO_ROOT = Path(__file__).resolve().parents[2]
NDA_PDF = REPO_ROOT / "tests/fixtures/nda_with_pii.pdf"
NDA_PLAYBOOK = REPO_ROOT / "tests/fixtures/playbooks/precheck-nda-v1.yaml"

XDG_VARS = ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME")

# Synthetic key material. Never a real credential (plan section 9.7).
CANARY_KEY = "sk-test-CANARY-123"
# The body of the canary, so a partially-redacted leak is caught too:
# ``redact_key`` keeps the first four characters.
CANARY_BODY = "CANARY-123"

CLOUD_PRIMARY = "anthropic/claude-3-5-sonnet"
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"
OLLAMA_BASE_URL = "http://localhost:11434/v1"


def state_config(tier: str, primary: str) -> str:
    """Return the config.yml body a suite drives the real CLI against."""
    return (
        f"privacy:\n  tier: {tier}\n"
        "gateway:\n"
        "  models:\n"
        "    extraction:\n"
        f"      primary: {primary}\n"
        "  fallback:\n"
        "    retries: 2\n"
        "    retry_delay: 0.0\n"
        "    timeout: 5\n"
    )


@dataclass
class State:
    """The isolated XDG tree a W5 suite drives the real CLI against."""

    root: Path
    config_dir: Path
    config_path: Path
    data_dir: Path
    db_path: Path
    auth_path: Path
    log_dir: Path
    output_dir: Path


def prepare_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    tier: str = "maximum",
    primary: str = CLOUD_PRIMARY,
    auth: dict[str, Any] | None = None,
) -> State:
    """Redirect every XDG root at *tmp_path* and seed a config, auth and database."""
    for var in XDG_VARS:
        monkeypatch.setenv(var, str(tmp_path / var.lower()))
    monkeypatch.delenv("OPENREVIEW_OUTPUT_DIR", raising=False)

    config_dir = tmp_path / "xdg_config_home" / "openreview"
    data_dir = tmp_path / "xdg_data_home" / "openreview"
    log_dir = tmp_path / "xdg_state_home" / "openreview" / "log"
    output_dir = tmp_path / "out"
    for directory in (config_dir, data_dir, log_dir, output_dir):
        directory.mkdir(parents=True, exist_ok=True)

    config_path = config_dir / "config.yml"
    config_path.write_text(state_config(tier, primary), encoding="utf-8")

    db_path = data_dir / "openreview.db"
    init_database(db_path)

    auth_path = config_dir / "auth.json"
    if auth is not None:
        import json

        auth_path.write_text(json.dumps(auth), encoding="utf-8")
        auth_path.chmod(0o600)

    return State(
        root=tmp_path,
        config_dir=config_dir,
        config_path=config_path,
        data_dir=data_dir,
        db_path=db_path,
        auth_path=auth_path,
        log_dir=log_dir,
        output_dir=output_dir,
    )


def run_cli(args: list[str]) -> Result:
    """Invoke the real Typer app with *args* through a one-shot CliRunner."""
    return CliRunner().invoke(app, args)


# ── Registry doubles ────────────────────────────────────────────────────────


def cloud_registry() -> dict[str, ProviderInfo]:
    """A registry holding one plain cloud provider."""
    return {
        "anthropic": ProviderInfo(
            name="anthropic",
            env_key="ANTHROPIC_API_KEY",
            base_url=ANTHROPIC_BASE_URL,
            is_local=False,
            capabilities=Capability(reasoning=True, context_window=200_000),
        )
    }


def local_registry() -> dict[str, ProviderInfo]:
    """A registry holding one genuine local provider."""
    return {
        "ollama": ProviderInfo(
            name="ollama",
            env_key=None,
            auth_required=False,
            base_url=OLLAMA_BASE_URL,
            is_local=True,
            capabilities=Capability(reasoning=True, embedding=True, context_window=32_000),
        )
    }


def unclassifiable_registry() -> dict[str, ProviderInfo]:
    """The exact shape the bundled registry gives ``bedrock`` and ``vertex``.

    ``base_url=None`` and ``is_local=False``: ``classify_provider`` cannot
    classify it, ``_enforce_tier`` treats it as cloud, ``_record_cloud_call``
    refuses to count it. See RT-027.
    """
    return {
        "bedrock": ProviderInfo(
            name="bedrock",
            env_key="AWS_ACCESS_KEY_ID",
            base_url=None,
            is_local=False,
            capabilities=Capability(reasoning=True, context_window=200_000),
        )
    }


def make_gateway(
    state: State,
    *,
    primary: str,
    tier: str,
    fallback: str | None = None,
    retries: int = 2,
    auth: dict[str, Any] | None = None,
) -> Gateway:
    """Partially construct a real ``Gateway`` over *state*'s database."""
    from unittest.mock import MagicMock

    slot: dict[str, Any] = {"primary": primary}
    if fallback is not None:
        slot["fallback"] = fallback
    gw = Gateway.__new__(Gateway)
    gw._config = {
        "gateway": {
            "models": {"extraction": slot},
            "fallback": {"retries": retries, "retry_delay": 0.0, "timeout": 5},
        }
    }
    gw._cloud_calls_made = 0
    gw._cost_tracker = MagicMock()
    gw._tier_config = TierConfig.from_config({"privacy": {"tier": tier}})
    gw._auth = auth or {}
    gw._data_path = state.db_path
    return gw


# ── The instrumented dispatch seam ──────────────────────────────────────────


class _Message:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str | None) -> None:
        self.message = _Message(content)


class CompletionResponse:
    """Minimal ``litellm`` completion double: only ``choices[0].message.content``."""

    def __init__(self, content: str = "ok") -> None:
        self.choices = [_Choice(content)]


@dataclass(frozen=True)
class Dispatch:
    """One recorded call to a real dispatch seam."""

    site: str
    model: str
    api_base: str | None


class DispatchRecorder:
    """The one remaining dispatch seam, instrumented.

    ``completion`` is a module-level name on ``gateway.router`` (``router.py:15``)
    and is patched there. Spec 035 removed the ``embedding`` and ``reranking``
    sockets, so those transports no longer exist to intercept: the gateway's only
    outbound call site is now ``completion``.
    """

    def __init__(self, *, fail: bool = True, stream_mode: bool = False) -> None:
        self.records: list[Dispatch] = []
        self.fail = fail
        # ``True`` makes ``completion`` yield stream chunks, as a
        # ``completion(stream=True)`` call does for ``Gateway.chat_stream``.
        self.stream_mode = stream_mode

    def _record(self, site: str, kwargs: dict[str, Any]) -> None:
        api_base = kwargs.get("api_base")
        self.records.append(
            Dispatch(
                site=site,
                model=str(kwargs.get("model")),
                api_base=str(api_base) if api_base is not None else None,
            )
        )

    def _maybe_fail(self, site: str, kwargs: dict[str, Any]) -> None:
        if self.fail:
            raise AssertionError(f"dispatched {kwargs.get('model')} via {site}")

    def completion(self, **kwargs: Any) -> Any:
        site = "completion-stream" if self.stream_mode else "completion"
        self._record(site, kwargs)
        self._maybe_fail(site, kwargs)
        if self.stream_mode:
            return TerminatedStream([StreamChunk("he"), StreamChunk("llo")])
        return CompletionResponse()

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Patch the remaining dispatch seam in-process. No sockets are involved."""
        import openreview_cli.gateway.router as router_mod

        monkeypatch.setattr(router_mod, "completion", self.completion)

    def models(self) -> list[str]:
        """Every model string the dispatch seam was handed, in call order."""
        return [record.model for record in self.records]

    def sites(self) -> list[str]:
        """Every dispatch site, in call order."""
        return [record.site for record in self.records]

    def summary(self) -> str:
        """A one-line description of every dispatch, for assertion messages."""
        return ", ".join(f"{r.site}:{r.model}" for r in self.records)


def assert_no_dispatch(recorder: DispatchRecorder, label: str) -> None:
    """The no-dispatch oracle: raise if the network was reached at all.

    This is the predicate every strict-tier case trusts. If it cannot fail, a
    green suite certifies nothing (plan section 9.3 rule 1), which is why each
    W5 file also carries a negative control that drives it into a real dispatch.
    """
    if recorder.records:
        raise AssertionError(
            f"{label}: the network was reached — {len(recorder.records)} dispatch(es) "
            f"[{recorder.summary()}]"
        )


def patch_gateway_factory(
    monkeypatch: pytest.MonkeyPatch, factory: Callable[..., Gateway]
) -> list[int]:
    """Replace ``router.Gateway`` with *factory*, returning a construction counter.

    ``review/_gateway.py:111-113`` and every ``gateway`` subcommand import
    ``Gateway`` lazily at call time, so patching the module attribute intercepts
    the real command path.
    """
    constructed: list[int] = []

    def _factory(*args: Any, **kwargs: Any) -> Gateway:
        constructed.append(1)
        return factory(*args, **kwargs)

    monkeypatch.setattr("openreview_cli.gateway.router.Gateway", _factory)
    return constructed


def gateway_returning(gw: Gateway) -> Callable[..., Gateway]:
    """A factory that always hands back *gw*, whatever the CLI asks for."""

    def _factory(*args: Any, **kwargs: Any) -> Gateway:
        return gw

    return _factory


def gateway_forbidden() -> Callable[..., Gateway]:
    """A factory that fails if a gateway is constructed at all."""

    def _factory(*args: Any, **kwargs: Any) -> Gateway:
        raise AssertionError("gateway constructed")

    return _factory


# ── Anti-vacuity reachability counter ───────────────────────────────────────


@contextmanager
def count_calls(target: object, attr: str) -> Iterator[list[int]]:
    """Count calls to ``target.attr``, restoring the original on exit (plan 9.3)."""
    real: Any = getattr(target, attr)
    hits = [0]

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        hits[0] += 1
        return real(*args, **kwargs)

    setattr(target, attr, wrapper)
    try:
        yield hits
    finally:
        setattr(target, attr, real)
