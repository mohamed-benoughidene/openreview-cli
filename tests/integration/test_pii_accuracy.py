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

    def test_finds_pii_on_real_contracts(self) -> None:
        """Run detection on real CUAD contracts.  No synthetic data needed."""
        if not CUAD_DIR.is_dir():
            pytest.skip(f"CUAD corpus not found at {CUAD_DIR}")

        contract_paths = sorted(CUAD_DIR.glob("*.txt"))[:SAMPLE_SIZE]
        if not contract_paths:
            pytest.fail(f"No contracts found in {CUAD_DIR}")

        results = []
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

            result = strip_pii(
                clauses=[clause],
                document=document,
                strip_metadata=False,
            )

            entity_count = len(result.entities)
            types = sorted({e.entity_type for e in result.entities})
            results.append((path.name, entity_count, types))

        avg = sum(r[1] for r in results) / len(results)
        min_seen = min(r[1] for r in results)
        max_seen = max(r[1] for r in results)

        print()
        print("=" * 80)
        print("PII DETECTION REPORT — REAL CONTRACTS (CUAD)")
        print("=" * 80)
        print(f"{'Contract':<60} {'Entities':>8}")
        print("-" * 80)
        for name, count, _ in results:
            print(f"{name:<60} {count:>8}")
        print("-" * 80)
        print(f"{f'Average ({len(results)} contracts)':<60} {avg:>8.1f}")
        print(f"{'Minimum':<60} {min_seen:>8}")
        print(f"{'Maximum':<60} {max_seen:>8}")
        print()
        print(f"Entity types seen: {sorted({t for _, _, types in results for t in types})}")
        print("=" * 80)

        assert avg >= MIN_ENTITIES_PER_DOC, (
            f"Average {avg:.1f} entities per contract is below {MIN_ENTITIES_PER_DOC}"
        )

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
