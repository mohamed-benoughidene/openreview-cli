"""End-to-end tests for PII stripping via strip_pii."""

from pathlib import Path

import pytest

from openreview_cli.pii.engine import PiiEngine


class TestStripPiiEndToEnd:
    """Integration tests that exercise the full PII stripping pipeline."""

    @pytest.mark.integration
    def test_strip_pii_end_to_end(self) -> None:
        """Real PII in clause text is detected, replaced with placeholders, and mapped."""
        from openreview_cli.parsing.models import Clause, Document
        from openreview_cli.pii.engine import strip_pii

        clause = Clause(
            id="1",
            title=None,
            text="John Smith works at ABC Corp. Email: john@acme.com. Phone: 555-0123.",
            level=1,
            parent_id=None,
            source_page=1,
            source_paragraph=None,
            source_span=None,
        )
        doc = Document(
            source_path=Path("/tmp/test.pdf"),
            format="pdf",
            page_count=1,
            clause_count=1,
            parse_duration_seconds=0.1,
            warnings=[],
            author="John Smith",
            title="Employment Agreement",
            company="ABC Corp.",
        )

        result = strip_pii([clause], doc, strip_metadata=False)

        markers = ["[NAME_1]", "[PARTY_A]", "[EMAIL_1]", "[PHONE_1]"]
        assert any(m in result.stripped_text for m in markers), (
            f"No placeholder found in: {result.stripped_text[:200]}"
        )
        assert len(result.mapping) > 0
        assert len(result.entities) > 0
        assert result.duration_seconds >= 0
        assert isinstance(result.warnings, list)

    @pytest.mark.integration
    def test_email_detection_needs_no_suffix_list_network(self, pii_engine: PiiEngine) -> None:
        """Email detection must work without a tldextract cache or the network.

        Regression guard: Presidio's EmailRecognizer.validate_result() calls
        ``tldextract.extract()``, which downloads the public suffix list on a
        cache miss.  Under the suite's ``--disable-socket`` addopt that download
        raises ``pytest_socket.SocketBlockedError`` — a ``RuntimeError``, not the
        ``requests.exceptions.RequestException`` tldextract tolerates — so the
        bundled-snapshot fallback was skipped and every clause containing an
        email address crashed the PII engine on a cold cache (fresh CI runner,
        fresh checkout, or ``isolated_xdg`` redirecting ``XDG_CACHE_HOME``).
        """
        import tldextract.tldextract as tldextract_impl

        assert len(tldextract_impl.TLD_EXTRACTOR.suffix_list_urls) == 0, (
            "the test session must resolve public suffixes from tldextract's bundled "
            "snapshot; see tests/conftest.py::_tldextract_resolves_suffixes_offline"
        )

        entities = pii_engine.detect_on_page("Email: john@acme.com.")

        assert any(e.entity_type == "EMAIL_ADDRESS" for e in entities), (
            f"email address not detected without the public suffix list fetch: {entities}"
        )

    @pytest.mark.integration
    def test_strip_pii_no_pii(self) -> None:
        """Clause with no PII returns the original text and an empty mapping."""
        from openreview_cli.parsing.models import Clause, Document
        from openreview_cli.pii.engine import strip_pii

        fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures"
        text = (fixtures_dir / "pii" / "seeded_contracts" / "no_pii_document.txt").read_text()
        clause = Clause(
            id="1",
            title=None,
            text=text,
            level=1,
            parent_id=None,
            source_page=1,
            source_paragraph=None,
            source_span=None,
        )
        doc = Document(
            source_path=Path("/tmp/none.pdf"),
            format="pdf",
            page_count=1,
            clause_count=1,
            parse_duration_seconds=0.1,
            warnings=[],
        )

        result = strip_pii([clause], doc, strip_metadata=False)
        assert isinstance(result.entities, list)
        assert result.mapping == {}, f"Expected empty mapping, got: {result.mapping}"
