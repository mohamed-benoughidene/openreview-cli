"""Accuracy validation for PII detection on real legal contracts."""

from pathlib import Path

import pytest

from openreview_cli.parsing.models import Clause, Document
from openreview_cli.pii.engine import strip_pii

SAMPLE_SIZE = 10
MIN_ENTITIES_PER_DOC = 5
CUAD_DIR = Path(__file__).resolve().parent.parent.parent / "data/legalbenchrag/corpus/cuad"


@pytest.mark.integration
@pytest.mark.accuracy
class TestPiiAccuracy:
    """Validate PII detection on real contracts from the CUAD dataset."""

    @pytest.mark.timeout(300)
    def test_finds_pii_on_real_contracts(self) -> None:
        """Run detection on real CUAD contracts with shared PiiEngine.

        The autouse ``_inject_shared_pii_engine`` fixture (conftest.py)
        monkeypatches ``strip_pii`` to use the session-scoped engine.
        """
        if not CUAD_DIR.is_dir():
            pytest.skip(f"CUAD corpus not found at {CUAD_DIR}")

        contract_paths = sorted(CUAD_DIR.glob("*.txt"))[:SAMPLE_SIZE]
        assert contract_paths, f"No contracts in {CUAD_DIR}"

        results: list[tuple[str, int]] = []
        for path in contract_paths:
            text = path.read_text(encoding="utf-8", errors="replace")
            clause = Clause(
                id=path.name,
                title=None,
                text=text,
                level=0,
                parent_id=None,
                source_page=1,
                source_paragraph=None,
                source_span=None,
            )
            document = Document(
                source_path=path,
                format="pdf",
                page_count=1,
                clause_count=1,
                parse_duration_seconds=0.0,
                warnings=[],
            )
            result = strip_pii(clauses=[clause], document=document, strip_metadata=False)
            entity_count = len(result.entities)
            results.append((path.name, entity_count))

        avg = sum(r[1] for r in results) / len(results)
        min_seen = min(r[1] for r in results)
        max_seen = max(r[1] for r in results)

        print(f"Average: {avg:.1f}, Min: {min_seen}, Max: {max_seen}")

        assert avg >= MIN_ENTITIES_PER_DOC, f"Average {avg:.1f} < {MIN_ENTITIES_PER_DOC}"

    def test_no_false_positives_on_clean_text(self, fixtures_dir: Path) -> None:
        """Ensure PII-free document yields zero detections."""
        doc_path = fixtures_dir / "pii/seeded_contracts/no_pii_document.txt"
        if not doc_path.exists():
            pytest.skip("Clean-text fixture not found")
        text = doc_path.read_text(encoding="utf-8")

        clause = Clause(
            id="no_pii",
            title=None,
            text=text,
            level=0,
            parent_id=None,
            source_page=1,
            source_paragraph=None,
            source_span=None,
        )
        document = Document(
            source_path=doc_path,
            format="pdf",
            page_count=1,
            clause_count=1,
            parse_duration_seconds=0.0,
            warnings=[],
        )

        result = strip_pii(
            clauses=[clause],
            document=document,
            strip_metadata=False,
        )

        detected = result.entities
        assert len(detected) == 0, (
            f"Expected 0 PII detections on clean text, got {len(detected)}: "
            + ", ".join(f"{e.original_value} ({e.entity_type})" for e in detected)
        )
