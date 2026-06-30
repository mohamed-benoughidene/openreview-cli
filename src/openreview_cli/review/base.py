"""Base review command with PII integration."""

import hashlib
import logging
from pathlib import Path
from typing import Any

from openreview_cli.pii.cache import PiiCache
from openreview_cli.pii.config_hash import compute_config_hash
from openreview_cli.pii.engine import strip_and_persist
from openreview_cli.pii.mapping import ensure_encryption_key

logger = logging.getLogger(__name__)


class ReviewCommand:
    """Base class for review subcommands.

    Orchestrates: parse document → strip PII (if enabled) → run analysis
    → create encrypted mapping → write audit trail → return result path.
    """

    def __init__(
        self,
        document_path: str,
        pii_enabled: bool = True,
        threshold: float | None = None,
        output_dir: str | None = None,
        force_reprocess: bool = False,
    ):
        self._document_path = Path(document_path)
        self._pii_enabled = pii_enabled
        self._threshold = threshold
        self._output_dir = Path(output_dir) if output_dir else Path.cwd() / "review_results"
        self._force_reprocess = force_reprocess

    def run(self) -> dict[str, Any]:
        if not self._document_path.exists():
            raise FileNotFoundError(f"Document not found: {self._document_path}")

        doc_hash = self._compute_hash()
        review_dir = self._output_dir / doc_hash[:12]
        review_dir.mkdir(parents=True, exist_ok=True)

        result_path = review_dir / "memo.txt"

        if self._pii_enabled:
            threshold = self._threshold if self._threshold is not None else 0.7
            config_hash = self._compute_config_hash()
            cache = self._get_cache()

            if not self._force_reprocess and cache.is_valid(doc_hash, config_hash):
                cached = cache.get(doc_hash)
                if cached and Path(cached["review_result_path"]).exists():
                    return {
                        "document_hash": doc_hash,
                        "review_dir": str(review_dir),
                        "result_path": cached["review_result_path"],
                        "pii_entities": 0,
                        "failed_pages": [],
                        "cached": True,
                    }

            clauses, document = self._parse_document()
            pii_result = strip_and_persist(
                clauses,
                document,
                review_id=doc_hash[:12],
                threshold=threshold,
                encryption_key=self._get_encryption_key(),
            )
            result_path.write_text(pii_result.stripped_text)

            cache.put(
                doc_hash,
                config_hash,
                str(result_path),
                str(review_dir / "pii_map.enc"),
            )

            return {
                "document_hash": doc_hash,
                "review_dir": str(review_dir),
                "result_path": str(result_path),
                "pii_entities": len(pii_result.entities),
                "failed_pages": pii_result.failed_pages or [],
                "cached": False,
            }
        else:
            clauses, document = self._parse_document()
            raw_text = " ".join(c.text for c in clauses)
            result_path.write_text(raw_text)
            logger.warning("PII stripping disabled. Raw text processed.")
            return {
                "document_hash": doc_hash,
                "review_dir": str(review_dir),
                "result_path": str(result_path),
                "pii_entities": 0,
                "failed_pages": [],
                "cached": False,
            }

    def _compute_hash(self) -> str:
        return hashlib.sha256(self._document_path.read_bytes()).hexdigest()

    def _load_config(self) -> dict[str, Any]:
        from openreview_cli.config.loader import load_config
        from openreview_cli.config.paths import get_config_dir

        return load_config(get_config_dir() / "config.yml")

    def _compute_config_hash(self) -> str:
        pii_config = self._load_config().get("privacy", {})
        return compute_config_hash(pii_config)

    def _get_cache(self) -> PiiCache:
        from openreview_cli.config.paths import get_data_dir

        db_path = get_data_dir() / "openreview.db"
        return PiiCache(db_path)

    def _parse_document(self) -> tuple[list[Any], Any]:
        from openreview_cli.parsing.stream import parse_document

        doc, clauses = parse_document(str(self._document_path))
        return clauses, doc

    def _get_encryption_key(self) -> str:
        from openreview_cli.config.paths import get_config_dir

        return ensure_encryption_key(self._load_config(), get_config_dir() / "config.yml")
