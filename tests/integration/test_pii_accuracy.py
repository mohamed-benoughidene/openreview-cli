"""Accuracy validation for PII detection on real legal contracts."""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from openreview_cli.parsing.models import Clause, Document
from openreview_cli.pii.engine import strip_pii

SAMPLE_SIZE = 10
MIN_ENTITIES_PER_DOC = 5
CUAD_DIR = Path(__file__).resolve().parent.parent.parent / "data/legalbenchrag/corpus/cuad"
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.integration
@pytest.mark.accuracy
class TestPiiAccuracy:
    """Validate PII detection on real contracts from the CUAD dataset."""

    def test_finds_pii_on_real_contracts(self) -> None:
        """Run detection on real CUAD contracts in a subprocess.

        The shared session-scoped PiiEngine holds a spaCy model that some
        earlier integration tests corrupt; running in a fresh interpreter
        avoids the corruption (SocketBlockedError inside tok2vec).
        See pre-existing-test-failures.md item #9.
        """
        if not CUAD_DIR.is_dir():
            pytest.skip(f"CUAD corpus not found at {CUAD_DIR}")

        script = textwrap.dedent(f"""\
        from pathlib import Path
        import sys; sys.path.insert(0, {str(_REPO_ROOT / "src")!r})

        from openreview_cli.parsing.models import Clause, Document
        from openreview_cli.pii.engine import strip_pii

        cuad_dir = Path({str(CUAD_DIR)!r})
        contract_paths = sorted(cuad_dir.glob("*.txt"))[:{SAMPLE_SIZE}]
        assert contract_paths, f"No contracts in {{cuad_dir}}"

        results = []
        for path in contract_paths:
            text = path.read_text(encoding="utf-8", errors="replace")
            clause = Clause(
                id=path.name, title=None, text=text, level=0,
                parent_id=None, source_page=1, source_paragraph=None,
                source_span=None,
            )
            document = Document(
                source_path=path, format="pdf", page_count=1,
                clause_count=1, parse_duration_seconds=0.0, warnings=[],
            )
            result = strip_pii(clauses=[clause], document=document, strip_metadata=False)
            entity_count = len(result.entities)
            types = sorted({{e.entity_type for e in result.entities}})
            results.append((path.name, entity_count, types))

        avg = sum(r[1] for r in results) / len(results)
        min_seen = min(r[1] for r in results)
        max_seen = max(r[1] for r in results)

        print(f"Average: {{avg:.1f}}, Min: {{min_seen}}, Max: {{max_seen}}")
        types_seen = sorted({{t for _, _, types in results for t in types}})
        print(f"Entity types: {{types_seen}}")

        assert avg >= {MIN_ENTITIES_PER_DOC}, f"Average {{avg:.1f}} < {MIN_ENTITIES_PER_DOC}"
        """)
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result.returncode == 0, (
            f"PII accuracy subprocess failed (exit {result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
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
