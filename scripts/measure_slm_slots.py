"""Measure clause-detection quality of gateway models on the bundled fixtures.

This is a measurement, not a test. It runs the product review pipeline for one
mode's documents with a given model (local Ollama or a cloud provider), then scores
the result against that mode's ``ground_truth.json``. It writes a JSON result and
prints a markdown summary.

Two ways to choose the model:
- ``--model ollama/qwen3:4b`` routes every text slot to that model (used by the
  CI matrix; add ``--no-pii`` there, since Ollama is local and CI has no spaCy).
- ``--configured`` uses the slots already configured in config.yml (the real
  product setup); PII stripping then runs, as the balanced privacy tier requires
  before cloud egress.

Reranking is not measured: the `reranking` slot was removed (no local reranker
works on legal text).

``--grounding-accuracy`` switches to a second mode: it scores
``CitationGroundingDiscriminator.ground_claim`` as a real confusion matrix over
real CUAD clauses — bad claims caught, good claims wrongly rejected, the uncertain
columns and per-call latency. It skips gracefully when the (gitignored) corpus is
absent, and it deliberately does **not** use ``compute_cg_metrics`` as a signal
(that structural function returns ``1.0`` for everything when nothing is grounded —
the exact failure mode this mode exists to expose). See
``docs/specs/plans/2026-09-30-grounding-accuracy-harness-design.md``.

This mode strips PII before any model call, with the same
``openreview_cli.pii.strip_pii_clauses`` machinery the review path runs: the
balanced tier's PII-before-egress gate otherwise refuses every cloud call
("No successful strip was recorded for this operation"), so the harness could
never measure the cloud arm as written. The clause text fed to ``ground_claim``
is the stripped text — the same placeholders the product sends — and the
positive claims are sentences taken from that stripped text. ``--no-pii`` is the
explicit opt-out for local runs: it resets the gate and the receipt records, in
plain text, that raw clause text was sent (stripping is never skipped silently).

Usage:
    uv run python scripts/measure_slm_slots.py --model ollama/qwen3:4b --no-pii --out results/qwen3-4b.json
    uv run python scripts/measure_slm_slots.py --configured --out results/cloud.json
    uv run python scripts/measure_slm_slots.py --grounding-accuracy --limit 20 --arm local --out results/grounding-local.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import time
from pathlib import Path
from typing import Any

from openreview_cli.grounding.corruption import (
    GROUNDING_VALID_NEGATIVES,
    ClauseUnit,
    first_qualifying_sentence,
    hallucination,
    is_genuine_negative,
    unsupported_claim,
)

FIXTURES = Path("tests/fixtures/benchmark")

# Route every text slot to the model under test, so the run is internally consistent.
_SLOT_ENV_KEYS = {
    slot: f"OPENREVIEW_GATEWAY__MODELS__{slot.upper()}__PRIMARY"
    for slot in ("extraction", "reasoning", "grounding")
}

# The shipped local grounding default (plan T1.5). Used by ``--arm local``.
_LOCAL_GROUNDING_MODEL = "ollama/granite4:3b"

# A source unit is a blank-line-separated corpus paragraph big enough to be a clause
# (design §5). The first *qualifying* sentence (the corruption module's rule) becomes the
# positive; the paragraph text is what the claim is grounded against.
_MIN_UNIT_CHARS = 200
_MIN_UNIT_SENTENCES = 2

# Stated with every receipt; the report repeats them in prose.
GROUNDING_ACCURACY_CAVEATS: tuple[str, ...] = (
    "Positives are verbatim sentences taken from the cited clause as sent to the model "
    "(PII-stripped clause text by default; raw clause text under --no-pii), so they are "
    "trivially grounded: this positive set is easier than a human-labelled one. No "
    "real-world false-positive rate may be quoted from this harness — the negative arm is "
    "the signal.",
    "Single-sample smoke measurement, not a benchmark: model replies vary run to run.",
    "Clause ids here are harness-local units (c<index>), not the product's clause numbering.",
    "The CUAD corpus under data/ is gitignored, so CI cannot use it. CI instead assembles a "
    "deterministic corpus from the repository's tracked fixtures and runs this mode on that; the "
    "full CUAD sample remains a local/on-demand run.",
    "Clause text is PII-stripped before any model call with the review path's own "
    "strip_pii_clauses machinery; --no-pii is the explicit, receipt-recorded opt-out.",
    "negatives_dropped_guard counts generated negatives whose claim text appears verbatim in "
    "the cited clause (mislabels). They are dropped, never scored, and the count is reported "
    "per generator even when it is zero.",
)


def _git_sha() -> str:
    return os.environ.get("GITHUB_SHA", "unknown")[:12]


def _configure_slots(model: str) -> None:
    """Point every text slot at ``model`` via the documented env override."""
    for env_key in _SLOT_ENV_KEYS.values():
        os.environ[env_key] = model


def _configured_slots() -> dict[str, str]:
    """Return the text-slot primaries already configured in config.yml."""
    from openreview_cli.config.loader import load_config
    from openreview_cli.config.paths import get_config_dir

    config = load_config(get_config_dir() / "config.yml")
    models = config.get("gateway", {}).get("models", {})
    return {slot: (models.get(slot) or {}).get("primary", "") for slot in _SLOT_ENV_KEYS}


def _write_receipt(path: Path, payload: dict[str, Any]) -> None:
    """Write the single JSON output format both modes share."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _score(assessments: list[Any], expected: list[dict[str, str]]) -> dict[str, int]:
    """Return category-match / position-match / failure counts for one document.

    Assessments carrying an ``error`` are the pipeline's failure fallback: it
    stamps ``playbook_category`` with the category id, so counting them would
    report every category as "detected" even when the model never answered.
    """
    ok = [a for a in assessments if getattr(a, "error", None) is None]
    detected = {a.playbook_category: a.position.value for a in ok}
    matched = 0
    position_ok = 0
    for exp in expected:
        category = exp["category_id"]
        if category in detected:
            matched += 1
            if detected[category] == exp["expected_position"]:
                position_ok += 1
    return {
        "matched": matched,
        "position_ok": position_ok,
        "extraction_errors": len(assessments) - len(ok),
    }


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
        f"- extraction failures, excluded from the counts: {totals['extraction_errors']}",
        "",
        "| doc | matched | position ok | extraction errors | seconds | error |",
        "|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {d['doc']} | {d['matched']}/{len(d['expected'])} | {d['position_ok']} | "
        f"{d['extraction_errors']} | {d['seconds']} | {d['error'] or ''} |"
        for d in result["per_document"]
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Grounding-accuracy mode (plan T3.2 / design sections 4-6)
# ---------------------------------------------------------------------------


def _latency(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-call latency over ``seconds``: calls, mean, median, p95 (nearest-rank), max."""
    seconds = [float(row.get("seconds") or 0.0) for row in rows]
    if not seconds:
        return {"calls": 0, "mean": None, "median": None, "p95": None, "max": None}
    ordered = sorted(seconds)
    idx = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "calls": len(seconds),
        "mean": round(statistics.fmean(seconds), 6),
        "median": round(statistics.median(seconds), 6),
        "p95": round(ordered[idx], 6),
        "max": round(max(seconds), 6),
    }


def compute_grounding_matrix(labels: list[dict[str, Any]]) -> dict[str, Any]:
    """The harness's ONLY signal: a real confusion matrix over labelled verdicts.

    One row per call to ``ground_claim``. Positives are expected-*supported* claims,
    negatives expected-*unsupported*. ``uncertain`` is its own column on both arms.

    Degenerate cases the design pins:

    - ``negatives_kept == 0`` (the guard drained the negative arm): ``bad_caught == 0``
      and ``caught_rate is None`` — never ``1.0``, because there was nothing to catch;
    - a grounding that rejects everything: ``bad_caught == negatives_kept`` AND
      ``false_reject_rate == 1.0`` — that second number is what exposes it.

    ``compute_cg_metrics`` is deliberately not called here (see the module docstring).
    """
    positives = [row for row in labels if row.get("expected") == "supported"]
    negatives = [row for row in labels if row.get("expected") == "unsupported"]

    def _count(rows: list[dict[str, Any]], verdict: str) -> int:
        return sum(1 for row in rows if row.get("verdict") == verdict)

    good_rejected = _count(positives, "ungrounded")
    bad_caught = _count(negatives, "ungrounded")
    n_pos = len(positives)
    n_neg = len(negatives)
    return {
        "positives": n_pos,
        "negatives_kept": n_neg,
        "good_accepted": _count(positives, "grounded"),
        "good_rejected": good_rejected,
        "good_uncertain": _count(positives, "uncertain"),
        "bad_caught": bad_caught,
        "bad_missed": _count(negatives, "grounded"),
        "bad_uncertain": _count(negatives, "uncertain"),
        # None (never 1.0) when the denominator is empty: nothing to score.
        "caught_rate": round(bad_caught / n_neg, 4) if n_neg else None,
        "false_reject_rate": round(good_rejected / n_pos, 4) if n_pos else None,
        "latency": _latency(labels),
    }


def _paragraphs(text: str) -> list[str]:
    """Blank-line-separated, stripped paragraphs of a corpus contract."""
    return [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]


def _count_sentences(text: str) -> int:
    """Sentence count via the repo's own boundary detector (no new dependency)."""
    from openreview_cli.parsing.clause_detector import nupunkt_detect_boundaries

    return sum(1 for start, end in nupunkt_detect_boundaries(text) if text[start:end].strip())


def _unit_qualifies(text: str) -> bool:
    return len(text) >= _MIN_UNIT_CHARS and _count_sentences(text) >= _MIN_UNIT_SENTENCES


def _load_corpus_units(corpus_dir: Path, limit: int) -> tuple[list[ClauseUnit], int]:
    """First ``limit`` qualifying source units, in sorted-file then unit order.

    Deterministic (design §9.5): sorted file names, then paragraph order. Ids are
    harness-local (``c<index>``); the discriminator builds its own ``Clause`` from the
    arguments, so the id only has to be stable and distinct.
    """
    units: list[ClauseUnit] = []
    if limit < 1:
        return units, 0
    files_scanned = 0
    for path in sorted(corpus_dir.glob("*.txt")):
        files_scanned += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        for paragraph in _paragraphs(text):
            if not _unit_qualifies(paragraph):
                continue
            units.append(ClauseUnit(id=f"c{len(units):03d}", text=paragraph))
            if len(units) >= limit:
                return units, files_scanned
    return units, files_scanned


def _strip_grounding_units(
    units: list[ClauseUnit], *, no_pii: bool
) -> tuple[list[ClauseUnit], dict[str, Any]]:
    """Strip PII from unit text exactly as the review path does, before any model call.

    The balanced privacy tier refuses every cloud call until a strip has been recorded in
    this process (``gateway/router.py`` ``_pii_available``), and the review path satisfies
    that gate by running ``strip_pii_clauses`` and then ``mark_pii_available()``
    (``pipeline/adapters/strip.py``). This does the same, over the harness units, so the
    cloud arm can actually be measured. Stripping *before* the labels are built keeps the
    positive sentence meaningful: it is taken from the stripped text the model will see.

    ``--no-pii`` is the explicit opt-out: it resets the gate and returns the raw text, and
    the returned note states plainly that raw clause text was sent. Stripping is never
    skipped silently.

    Returns:
        ``(units, pii_info)`` — possibly-stripped units and the receipt's ``pii`` block.

    Raises:
        Exception: any strip failure propagates, so the caller aborts rather than sending
            unstripped text to a cloud tier.
    """
    from openreview_cli.gateway.router import mark_pii_available, reset_pii_available

    if no_pii:
        reset_pii_available()
        return list(units), {
            "stripped": False,
            "no_pii": True,
            "entities": 0,
            "engine": None,
            "note": (
                "--no-pii: PII stripping was SKIPPED. Raw clause text was sent to the model; "
                "the balanced/maximum cloud tiers will refuse these calls."
            ),
        }

    from openreview_cli.parsing.models import Clause
    from openreview_cli.pii import strip_pii_clauses

    clauses = [
        Clause(
            id=unit.id,
            title=None,
            text=unit.text,
            level=0,
            parent_id=None,
            source_page=None,
            source_paragraph=None,
            source_span=None,
        )
        for unit in units
    ]
    # strip_metadata=False: harness units are plain paragraphs, not a parsed Document,
    # so there is no filename/author metadata to redact (and document is None here).
    stripped, pii_result = strip_pii_clauses(clauses, None, strip_metadata=False)
    mark_pii_available()
    stripped_units = [ClauseUnit(id=clause.id, text=clause.text) for clause in stripped]
    return stripped_units, {
        "stripped": True,
        "no_pii": False,
        "entities": len(pii_result.entities),
        "engine": None,
        "note": (
            f"PII stripped before any model call ({len(pii_result.entities)} entity/entities) "
            "with the review path's strip_pii_clauses machinery. Clause text and positive "
            "claims are the stripped text (PII placeholders), as sent for cloud egress."
        ),
    }


def _label(claim_text: str, unit: ClauseUnit, expected: str, generator: str) -> dict[str, Any]:
    return {
        "claim_text": claim_text,
        "unit_id": unit.id,
        "clause_text": unit.text,
        "expected": expected,
        "generator": generator,
    }


def _build_grounding_labels(
    units: list[ClauseUnit],
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    """Build the label set and the per-generator guard accounting.

    Positives: a verbatim sentence from the clause (``first_qualifying_sentence``) —
    trivially supported. Negatives: ``unsupported_claim`` over the next distinct unit,
    plus ``hallucination``. Every negative passes ``is_genuine_negative`` before use;
    a rejected negative is dropped and counted per generator (never silently kept).
    """
    drops = dict.fromkeys(GROUNDING_VALID_NEGATIVES, 0)
    generated = dict.fromkeys(GROUNDING_VALID_NEGATIVES, 0)
    labels: list[dict[str, Any]] = []
    count = len(units)
    for index, unit in enumerate(units):
        positive = first_qualifying_sentence(unit.text)
        if positive is None:
            continue
        labels.append(_label(positive, unit, "supported", "positive"))

        if count > 1:
            other = units[(index + 1) % count]
            if other.id != unit.id:
                cross = unsupported_claim(unit, other)
                if cross is not None:  # None = degenerate pair, nothing to score
                    generated["unsupported_claim"] += 1
                    if is_genuine_negative(cross, unit.text):
                        labels.append(_label(cross, unit, "unsupported", "unsupported_claim"))
                    else:
                        drops["unsupported_claim"] += 1

        fabricated = hallucination(positive)
        generated["hallucination"] += 1
        if is_genuine_negative(fabricated, unit.text):
            labels.append(_label(fabricated, unit, "unsupported", "hallucination"))
        else:
            drops["hallucination"] += 1
    return labels, drops, generated


def _resolve_grounding_slots(arm: str) -> dict[str, str]:
    """The per-slot model ids for the run.

    - ``local`` overrides every text slot to the shipped local default before the
      gateway is built (the documented env override);
    - ``cloud``/``configured`` read config.yml as-is.
    """
    if arm == "local":
        _configure_slots(_LOCAL_GROUNDING_MODEL)
    return _configured_slots()


def _is_cloud_model(model: str) -> bool:
    return bool(model) and model.split("/", 1)[0] != "ollama"


# The CLI's per-socket smoke test is a real grounding call (app.py: ``gateway test``); this
# is the same prompt shape, so the pre-flight exercises the path a measurement call takes.
_PREFLIGHT_PROMPT = "Reachability check: does clause 1 require confidentiality? Answer OK."


def _preflight_arm_reachability() -> tuple[bool, str | None]:
    """One cheap call to the arm's grounding model, through the real gateway.

    This is the guard for the measurement-integrity bug where a failed gateway call is
    swallowed by ``CitationGroundingDiscriminator.ground_claim`` and returned as
    ``uncertain`` (``grounding/discriminator.py``): an unreachable arm — no local server, or
    a cloud key at its spend limit — then reads as model uncertainty.

    The call shape is the CLI's own smoke test (``app.py`` ``gateway test``)::

        Gateway().chat("grounding", [{"role": "user", "content": ...}],
                       requirement=CapabilityRequirement(capability="reasoning"))

    The balanced tier's PII gate must already be satisfied (the caller strips and marks it,
    exactly as the review path does) or a cloud arm self-refuses before the network — which
    is itself a reason to abort, not to proceed.

    Returns ``(ok, error)``: ``error`` is the underlying ``Type: message`` (redacted) when
    the call fails, else ``None``.
    """
    from openreview_cli.gateway.models import CapabilityRequirement
    from openreview_cli.gateway.router import Gateway

    try:
        gateway = Gateway()
        gateway.chat(
            "grounding",
            [{"role": "user", "content": _PREFLIGHT_PROMPT}],
            requirement=CapabilityRequirement(capability="reasoning"),
        )
    except Exception as exc:  # an unreachable arm must abort, never become a matrix
        from openreview_cli.gateway.redaction import redact_text

        return False, redact_text(f"{type(exc).__name__}: {exc}")
    return True, None


def _make_discriminator() -> Any:
    """Build the discriminator under test: real Gateway, throwaway audit dir."""
    import tempfile

    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
    from openreview_cli.storage.database import init_database

    # The gateway's cost-limit check reads the app database, so create it (with
    # migrations) first (the `no such table: cost_logs` bug).
    init_database(get_data_dir() / "openreview.db")
    audit_dir = tempfile.mkdtemp(prefix="grounding_accuracy_audit_")
    return CitationGroundingDiscriminator(mode="strict", output_dir=audit_dir)


def _grounding_skip_receipt(
    corpus_dir: Path,
    limit: int,
    arm: str,
    reason: str,
    slots: dict[str, str] | None = None,
    skip_kind: str | None = None,
) -> dict[str, Any]:
    models = dict(slots or {})
    return {
        "mode": "grounding-accuracy",
        "arm": arm,
        "model_ids": models,
        "slots": {"grounding": models.get("grounding", "")},
        "corpus_dir": str(corpus_dir),
        "corpus_files_scanned": 0,
        "limit": limit,
        "skipped": True,
        # Distinguishes an absent corpus (a documented CI skip) from an unreachable arm
        # (a measurement that could not run). ``None`` only for a run that never got here.
        "skip_kind": skip_kind,
        "skip_reason": reason,
        "git_sha": _git_sha(),
        "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pii_stripped": False,
        "pii": {
            "stripped": False,
            "no_pii": False,
            "entities": 0,
            "engine": None,
            "note": "no strip was run: the mode skipped before any model call",
        },
        "positives": 0,
        "negatives_kept": 0,
        "negatives_generated": dict.fromkeys(GROUNDING_VALID_NEGATIVES, 0),
        "negatives_dropped_guard": 0,
        "negatives_dropped_guard_by_generator": dict.fromkeys(GROUNDING_VALID_NEGATIVES, 0),
        "caught_rate": None,
        "false_reject_rate": None,
        # No matrix ran, so nothing can be all-uncertain.
        "all_uncertain": False,
        "all_uncertain_note": None,
        "latency": {"calls": 0, "mean": None, "median": None, "p95": None, "max": None},
        "caveats": list(GROUNDING_ACCURACY_CAVEATS),
        "per_label": [],
    }


def _print_grounding_summary(receipt: dict[str, Any], out: Path) -> None:
    latency = receipt["latency"]
    drops = receipt["negatives_dropped_guard_by_generator"]
    print(
        f"[grounding-accuracy] arm={receipt['arm']} model={receipt['slots']['grounding']} "
        f"units={receipt['units']} positives={receipt['positives']} "
        f"negatives_kept={receipt['negatives_kept']} "
        f"negatives_dropped_guard={receipt['negatives_dropped_guard']}"
    )
    print(
        f"[grounding-accuracy] bad_caught={receipt['bad_caught']}/{receipt['negatives_kept']} "
        f"(caught_rate={receipt['caught_rate']}) "
        f"good_rejected={receipt['good_rejected']}/{receipt['positives']} "
        f"(false_reject_rate={receipt['false_reject_rate']}) "
        f"uncertain good/bad={receipt['good_uncertain']}/{receipt['bad_uncertain']}"
    )
    if receipt.get("all_uncertain"):
        print(
            "[grounding-accuracy] *** WARNING: EVERY verdict is 'uncertain' — this is not a "
            "result. A failed gateway call is swallowed and returned as 'uncertain' "
            "(grounding/discriminator.py), so an all-uncertain matrix almost always means the "
            f"arm '{receipt['arm']}' was unreachable, not that the model was cautious. Check "
            "the arm (local server down? cloud key at its spend limit?) before quoting any of "
            "these numbers. ***"
        )
    print(
        "[grounding-accuracy] guard drops by generator: "
        + ", ".join(f"{name}={count}" for name, count in drops.items())
    )
    pii = receipt["pii"]
    if pii["stripped"]:
        print(
            f"[grounding-accuracy] pii: stripped {pii['entities']} entity/entities before any "
            "model call (review path's strip_pii_clauses); clause text and positives are the "
            "stripped text."
        )
    else:
        print(
            "[grounding-accuracy] pii: *** STRIPPING SKIPPED (--no-pii) *** raw clause text was "
            "sent to the model; the cloud tiers refuse these calls."
        )
    print(
        "[grounding-accuracy] caveat: positives are verbatim clause sentences (weaker than "
        "human-labelled data); the negative arm is the signal."
    )
    print(
        f"[grounding-accuracy] latency calls={latency['calls']} mean={latency['mean']} "
        f"median={latency['median']} p95={latency['p95']} max={latency['max']} seconds"
    )
    print(f"[grounding-accuracy] JSON receipt written to {out}")


def run_grounding_accuracy(
    *, corpus_dir: Path, limit: int, arm: str, out: Path, no_pii: bool = False
) -> dict[str, Any]:
    """Run the grounding-accuracy mode; write the JSON receipt; return it.

    Skips gracefully (exit 0 from ``main``) when the corpus is absent, so CI — where
    ``data/`` is gitignored — never fails on a missing directory. The markdown report
    is assembled by hand later; this mode writes only the JSON receipt.

    PII is stripped (the review path's machinery) before the labels are built and before
    the discriminator runs, so the balanced tier's egress gate is satisfied and the clauses
    the model sees are the stripped ones. ``no_pii`` is the explicit opt-out.
    """
    corpus_dir = Path(corpus_dir)
    out = Path(out)

    if not corpus_dir.is_dir() or not any(corpus_dir.glob("*.txt")):
        reason = f"corpus absent at {corpus_dir}"
        receipt = _grounding_skip_receipt(corpus_dir, limit, arm, reason, skip_kind="corpus_absent")
        _write_receipt(out, receipt)
        print(f"[grounding-accuracy] {reason} — skipping. Receipt: {out}")
        return receipt

    slots = _resolve_grounding_slots(arm)
    grounding_model = slots.get("grounding", "") or ""
    if arm == "cloud" and not _is_cloud_model(grounding_model):
        reason = (
            "cloud arm needs a cloud grounding model; configured grounding primary is "
            f"'{grounding_model or '(unset)'}'"
        )
        receipt = _grounding_skip_receipt(
            corpus_dir, limit, arm, reason, slots=slots, skip_kind="arm_misconfigured"
        )
        _write_receipt(out, receipt)
        print(f"[grounding-accuracy] {reason} — skipping. Receipt: {out}")
        return receipt

    units, files_scanned = _load_corpus_units(corpus_dir, limit)

    # Strip BEFORE labels are built: the positive sentence is taken from the stripped text
    # the model will see, and the tier's PII gate must pass before any cloud call.
    try:
        units, pii_info = _strip_grounding_units(units, no_pii=no_pii)
    except Exception as exc:  # a failed strip must abort, never send raw text to a cloud tier
        reason = f"PII stripping failed: {type(exc).__name__}: {exc}"
        _write_receipt(
            out,
            _grounding_skip_receipt(
                corpus_dir, limit, arm, reason, slots=slots, skip_kind="pii_unavailable"
            ),
        )
        print(f"[grounding-accuracy] {reason}")
        raise SystemExit(1) from exc

    # Guard 1: the arm must be reachable BEFORE any label is built or scored. Otherwise a
    # broken gateway call becomes a matrix full of ``uncertain`` — a measurement that looks
    # like model uncertainty but is really "the call never happened" (no local server, or a
    # cloud key at its spend limit). The PII gate is already satisfied by the strip above.
    reachable, preflight_error = _preflight_arm_reachability()
    if not reachable:
        reason = (
            f"arm '{arm}' unreachable: the grounding model refused the pre-flight call "
            f"({preflight_error}); no measurement was run"
        )
        receipt = _grounding_skip_receipt(
            corpus_dir, limit, arm, reason, slots=slots, skip_kind="arm_unreachable"
        )
        receipt["preflight"] = {
            "ok": False,
            "arm": arm,
            "grounding_model": grounding_model,
            "error": preflight_error,
        }
        _write_receipt(out, receipt)
        print(f"[grounding-accuracy] {reason}")
        raise SystemExit(1)
    print(
        f"[grounding-accuracy] pre-flight OK: arm '{arm}' grounding model "
        f"'{grounding_model}' answered the reachability check."
    )

    labels, drops, generated = _build_grounding_labels(units)

    try:
        discriminator = _make_discriminator()
    except Exception as exc:  # an unbuildable gateway is an environment error, not a number
        reason = f"cannot start the grounding run: {type(exc).__name__}: {exc}"
        _write_receipt(
            out,
            _grounding_skip_receipt(
                corpus_dir, limit, arm, reason, slots=slots, skip_kind="gateway_unavailable"
            ),
        )
        print(f"[grounding-accuracy] {reason}")
        raise SystemExit(1) from exc

    per_label: list[dict[str, Any]] = []
    for label in labels:
        started = time.perf_counter()
        error: str | None = None
        confidence = 0.0
        try:
            verdict, _provenances, confidence = discriminator.ground_claim(
                label["claim_text"], label["unit_id"], label["clause_text"]
            )
            verdict_value = verdict.value
        except Exception as exc:
            verdict_value = "uncertain"
            confidence = 0.0
            error = f"{type(exc).__name__}: {exc}"
        per_label.append(
            {
                "unit_id": label["unit_id"],
                "claim_text": label["claim_text"],
                "expected": label["expected"],
                "generator": label["generator"],
                "verdict": verdict_value,
                "confidence": confidence,
                "seconds": round(time.perf_counter() - started, 6),
                "error": error,
            }
        )

    matrix = compute_grounding_matrix(per_label)

    # Guard 2: every-uncertain is almost always a broken arm, not a cautious model. Flag it
    # so it cannot pass as a normal measurement. (The discriminator swallows a failed gateway
    # call and returns ``uncertain``; see grounding/discriminator.py.)
    all_uncertain = bool(per_label) and all(row["verdict"] == "uncertain" for row in per_label)
    all_uncertain_note = None
    if all_uncertain:
        all_uncertain_note = (
            f"ALL {len(per_label)} verdicts are 'uncertain'. A failed gateway call is swallowed "
            "by the discriminator and returned as 'uncertain' (grounding/discriminator.py), so "
            "an all-uncertain matrix almost always means the arm was unreachable (no local "
            "server, or a cloud key at its spend limit) rather than a cautious model. Check the "
            "arm before trusting this run; do not quote these numbers."
        )

    receipt: dict[str, Any] = {
        "mode": "grounding-accuracy",
        "arm": arm,
        "model_ids": dict(slots),
        "slots": {"grounding": grounding_model},
        "corpus_dir": str(corpus_dir),
        "corpus_files_scanned": files_scanned,
        "limit": limit,
        "skipped": False,
        "skip_reason": None,
        "git_sha": _git_sha(),
        "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "units": len(units),
        "pii_stripped": bool(pii_info["stripped"]),
        "pii": pii_info,
        **matrix,
        "all_uncertain": all_uncertain,
        "all_uncertain_note": all_uncertain_note,
        "negatives_generated": generated,
        "negatives_dropped_guard": sum(drops.values()),
        "negatives_dropped_guard_by_generator": drops,
        "harness_notes": {
            "positive_set": (
                "verbatim sentence from the (PII-stripped by default) cited clause text as "
                "sent to the model; trivially supported"
            ),
            "negative_generators": list(GROUNDING_VALID_NEGATIVES),
            "guard": "is_genuine_negative; rejected negatives dropped and counted per generator",
            "unit_ids": "harness-local c<index>, not the product's clause numbering",
            "signal": "confusion matrix only; compute_cg_metrics is deliberately not used",
            "pii": "clause text stripped with the review path's strip_pii_clauses before any call",
        },
        "caveats": list(GROUNDING_ACCURACY_CAVEATS),
        "per_label": per_label,
    }
    _write_receipt(out, receipt)
    _print_grounding_summary(receipt, out)
    return receipt


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        help="Model under test, e.g. ollama/qwen3:4b. Omit with --configured.",
    )
    parser.add_argument(
        "--configured",
        action="store_true",
        help="Use the slots configured in config.yml instead of overriding them.",
    )
    parser.add_argument(
        "--no-pii",
        action="store_true",
        help="Skip PII stripping (local models only; the cloud tiers require it).",
    )
    parser.add_argument("--mode", default="indemnitycheck", help="Mode whose fixtures to use.")
    parser.add_argument(
        "--grounding-mode",
        choices=["strict", "lenient"],
        default=None,
        help="Run the grounding slot too (the `precheck review` CLI default is 'strict').",
    )
    parser.add_argument(
        "--grounding-accuracy",
        action="store_true",
        help="Run the grounding-accuracy mode instead of the review mode.",
    )
    parser.add_argument(
        "--arm",
        choices=["local", "cloud", "configured"],
        default="configured",
        help=(
            "Grounding model source: local = ollama/granite4:3b; cloud = the configured "
            "cloud grounding slot; configured = config.yml as-is."
        ),
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="Max source units to label (grounding mode)."
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path("data/legalbenchrag/corpus/cuad"),
        help="Directory of *.txt contracts; skipped gracefully when absent.",
    )
    parser.add_argument("--fixtures-dir", type=Path, default=FIXTURES)
    parser.add_argument("--out", type=Path, required=True, help="Where to write the JSON result.")
    args = parser.parse_args(argv)

    if args.grounding_accuracy:
        run_grounding_accuracy(
            corpus_dir=args.corpus_dir,
            limit=args.limit,
            arm=args.arm,
            out=args.out,
            no_pii=args.no_pii,
        )
        return

    if not args.configured and not args.model:
        parser.error("pass --model <id> or --configured")

    if args.configured:
        slots = _configured_slots()  # read config as-is; do not override any slot
        label = slots.get("extraction", "") or "configured slots"
    else:
        _configure_slots(args.model)
        slots = dict.fromkeys(_SLOT_ENV_KEYS, args.model)
        label = args.model

    # The gateway's cost-limit check reads the app database, so create it (with
    # migrations) first. Without this every model call fails with
    # "no such table: cost_logs" and the pipeline silently returns fallbacks.
    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.storage.database import init_database

    init_database(get_data_dir() / "openreview.db")

    from openreview_cli.review import run_review
    from openreview_cli.review.playbook import BUNDLED_PLAYBOOKS

    mode_dir = args.fixtures_dir / args.mode
    ground_truth: list[dict[str, Any]] = json.loads((mode_dir / "ground_truth.json").read_text())
    playbook_path = str(BUNDLED_PLAYBOOKS[args.mode])

    totals = {
        "matched": 0,
        "position_ok": 0,
        "expected": 0,
        "extraction_errors": 0,
        "grounding_grounded": 0,
        "grounding_ungrounded": 0,
        "grounding_uncertain": 0,
        "grounding_assessed": 0,
    }
    per_document: list[dict[str, Any]] = []
    for entry in ground_truth:
        doc_path = Path(entry["path"])
        expected = entry["expected_categories"]
        started = time.perf_counter()
        error: str | None = None
        score = {"matched": 0, "position_ok": 0, "extraction_errors": 0}
        grounding = {"grounded": 0, "ungrounded": 0, "uncertain": 0, "assessed": 0}
        try:
            reports = run_review(
                paths=[str(doc_path)],
                playbook_path=playbook_path,
                extraction_model="extraction",
                qa_model=None,
                no_pii=args.no_pii,
                grounding_mode=args.grounding_mode,
                mode=args.mode,
            )
            assessments = [a for r in reports for a in r.assessments]
            score = _score(assessments, expected)
            totals["matched"] += score["matched"]
            totals["position_ok"] += score["position_ok"]
            totals["extraction_errors"] += score["extraction_errors"]
            verdicts = [
                a.grounding_verdict.value if a.grounding_verdict is not None else None
                for a in assessments
            ]
            grounding = {v: verdicts.count(v) for v in ("grounded", "ungrounded", "uncertain")}
            grounding["assessed"] = sum(1 for v in verdicts if v is not None)
            for key in ("grounded", "ungrounded", "uncertain", "assessed"):
                totals[f"grounding_{key}"] += grounding[key]
        except Exception as exc:  # a failing document is recorded, not fatal
            error = f"{type(exc).__name__}: {exc}"
        totals["expected"] += len(expected)
        per_document.append(
            {
                "doc": doc_path.name,
                "expected": expected,
                "matched": score["matched"],
                "position_ok": score["position_ok"],
                "extraction_errors": score["extraction_errors"],
                "grounding": grounding,
                "seconds": round(time.perf_counter() - started, 2),
                "error": error,
            }
        )
        print(
            f"[{label}] {doc_path.name}: {score['matched']}/{len(expected)} matched, "
            f"{score['extraction_errors']} extraction failures",
            flush=True,
        )

    expected_total = totals["expected"]
    result: dict[str, Any] = {
        "model": label,
        "slots": slots,
        "pii_stripped": not args.no_pii,
        "grounding_mode": args.grounding_mode,
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
    _write_receipt(args.out, result)

    print("\n" + _markdown(result))
    print(f"\nJSON written to {args.out}")


if __name__ == "__main__":
    main()
