"""Assemble the deterministic grounding corpus from the repository's tracked fixtures.

The ``--grounding-accuracy`` mode of ``scripts/measure_slm_slots.py`` defaults to the gitignored
CUAD corpus, which is absent in CI, so this builds the corpus the grounding measurement runs
against: every ``tests/fixtures/**/*.txt`` fixture paragraph the harness accepts, plus the
fixture PDFs/DOCX parsed to text with the product's own parser. No network is used.

Units are taken round-robin across source documents so the harness's first ``limit`` units span
many documents rather than the alphabetically-first one. Writes one ``unit_<n>.txt`` per unit to
``--out`` (default ``corpus``), the directory the receipts pass as ``--corpus-dir``.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import pathlib
import re
import sys

EXCLUDE_PARTS = {"pii", "redteam", "prompts", "__pycache__"}
SKIP_NAMES = {
    "corrupt.pdf",
    "empty.pdf",
    "scanned.pdf",
    "password_protected.pdf",
    "500_page.pdf",
    "50_page.pdf",
}
MARKER = re.compile(r"##[A-Za-z_]+##")
MAX_BYTES = 1_000_000


def _load_harness(root: pathlib.Path):
    """Import the measurement harness so its own unit rule is reused, not re-derived."""
    spec = importlib.util.spec_from_file_location(
        "measure_slm_slots", root / "scripts" / "measure_slm_slots.py"
    )
    assert spec is not None and spec.loader is not None
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    return harness


def _normalize(text: str) -> str:
    return " ".join(MARKER.sub(" ", text.replace("CLAUSE:", " ")).split())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    parser.add_argument("--out", default="corpus", help="output directory (default: corpus)")
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()
    harness = _load_harness(root)

    from openreview_cli.parsing.stream import stream_clauses

    seen: set[str] = set()
    per_doc: list[list[str]] = []
    sources: list[str] = []

    def collect(source: str, texts: list[str]) -> None:
        # Reuse the harness's own unit rule so the corpus is exactly the set of
        # paragraphs the harness would accept (>= 200 chars, >= 2 sentences).
        units = []
        for raw in texts:
            text = _normalize(raw)
            if text and text not in seen and harness._unit_qualifies(text):
                seen.add(text)
                units.append(text)
        if units:
            per_doc.append(units)
            sources.append(source)

    considered = 0
    for path in sorted(root.glob("tests/fixtures/**/*.txt")):
        if EXCLUDE_PARTS & set(path.parts) or path.stat().st_size > MAX_BYTES:
            continue
        considered += 1
        collect(
            str(path.relative_to(root)),
            harness._paragraphs(path.read_text(encoding="utf-8", errors="replace")),
        )

    parsed = 0
    for path in sorted(root.glob("tests/fixtures/**/*.pdf")) + sorted(
        root.glob("tests/fixtures/**/*.docx")
    ):
        if EXCLUDE_PARTS & set(path.parts) or path.name in SKIP_NAMES:
            continue
        if path.stat().st_size > MAX_BYTES:
            continue
        considered += 1
        try:
            clauses = list(stream_clauses(path, allow_password_prompt=False))
        except Exception:  # a fixture that cannot parse contributes nothing
            continue
        parsed += 1
        collect(str(path.relative_to(root)), [c.text or "" for c in clauses])

    # Round-robin across source documents so the harness's first `limit` units
    # span many documents, not just the alphabetically-first one.
    interleaved: list[str] = []
    depth = 0
    while True:
        added = False
        for units in per_doc:
            if depth < len(units):
                interleaved.append(units[depth])
                added = True
        if not added:
            break
        depth += 1

    out_dir = pathlib.Path(args.out)
    if out_dir.exists():
        for stale in out_dir.glob("*.txt"):
            stale.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, text in enumerate(interleaved):
        (out_dir / f"unit_{i:04d}.txt").write_text(text + "\n", encoding="utf-8")

    line = (
        f"[corpus] assembled {len(interleaved)} clause units from {len(per_doc)} tracked "
        f"fixture documents ({considered} fixture files considered; {parsed} PDF/DOCX parsed "
        "to text). Source: tests/fixtures/**.txt verbatim + fixture PDFs/DOCX parsed with "
        "openreview_cli.parsing -- NOT the gitignored CUAD corpus."
    )
    print(line)
    contributing = sorted(sources)
    print(f"[corpus] contributing documents: {', '.join(contributing)}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        # Provenance in the job summary: a reader must be able to see the sample
        # (how many qualifying units, from which tracked documents) without the log.
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(
                f"### Grounding corpus\n\n{line}\n\n"
                f"- units assembled: {len(interleaved)}\n"
                f"- contributing documents: {len(contributing)}\n"
                f"- document list: {', '.join(f'`{s}`' for s in contributing)}\n"
            )
    if not interleaved:
        sys.exit("corpus assembly produced no units; refusing to measure an empty corpus")
    return 0


if __name__ == "__main__":
    sys.exit(main())
