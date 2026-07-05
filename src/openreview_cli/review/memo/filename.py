"""Filename generation, sanitization, deduplication, and output directory logic."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openreview_cli.review.memo.models import MemoFormat

DEFAULT_OUTPUT_DIR = Path("review_results")


def sanitize_stem(stem: str) -> str:
    """Sanitize a document stem for use in filenames.

    Spaces → hyphens, special characters removed, lowercased.
    Falls back to ``"document"`` if the result is empty.
    """
    stem = stem.lower().strip()
    stem = stem.replace(" ", "-")
    stem = re.sub(r"[^a-z0-9_-]", "", stem)
    stem = re.sub(r"-+", "-", stem)
    stem = stem.strip("-")
    return stem or "document"


def generate_filename(mode: str, document_stem: str, fmt: MemoFormat) -> str:
    """Generate a memo output filename per FR-09 convention.

    Pattern: ``{mode}-{document_stem}-{YYYYMMDD-HHMMSS}.{ext}``
    """
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    stem = sanitize_stem(document_stem)
    return f"{mode}-{stem}-{ts}.{fmt.value}"


def resolve_output_dir(path: str | Path | None) -> Path:
    """Resolve and optionally create the output directory.

    Returns
    -------
    Path
        The resolved output directory path.

    Raises
    ------
    ValueError
        If *path* exists and is not a directory.
    """
    if path is None:
        return DEFAULT_OUTPUT_DIR
    p = Path(path)
    if p.exists() and not p.is_dir():
        raise ValueError(f"Output path exists and is not a directory: {p}")
    p.mkdir(parents=True, exist_ok=True)
    return p


def deduplicate(filepath: Path) -> Path:
    """Append a numeric suffix if *filepath* already exists.

    Never overwrites an existing file. Returns the original path if it does
    not exist, or ``{stem}-N{ext}`` for the first non-existent variant.
    """
    if not filepath.exists():
        return filepath
    stem = filepath.stem
    suffix = filepath.suffix
    parent = filepath.parent
    n = 1
    while True:
        candidate = parent / f"{stem}-{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1
