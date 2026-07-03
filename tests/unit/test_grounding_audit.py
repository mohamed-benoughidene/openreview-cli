"""Unit tests for GroundingAuditLog."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from openreview_cli.grounding.audit import GroundingAuditLog
from openreview_cli.grounding.models import (
    CitationProvenance,
    DiscriminationAuditEntry,
    GroundingVerdict,
)


@pytest.fixture
def temp_dir() -> Path:
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def audit_log(temp_dir: Path) -> GroundingAuditLog:
    return GroundingAuditLog(temp_dir)


class TestGroundingAuditLog:
    def test_creates_output_directory(self, temp_dir: Path) -> None:
        nested = temp_dir / "sub" / "dir"
        log = GroundingAuditLog(nested)
        assert nested.exists()

    def test_append_writes_valid_jsonl(self, audit_log: GroundingAuditLog) -> None:
        entry = DiscriminationAuditEntry(
            claim_hash="abc123",
            verdict=GroundingVerdict.GROUNDED,
            confidence=0.95,
            provenances=[],
        )
        audit_log.append(entry)
        audit_log_path = audit_log._path
        assert audit_log_path.exists()
        content = audit_log_path.read_text(encoding="utf-8").strip()
        data = json.loads(content)
        assert data["claim_hash"] == "abc123"
        assert data["verdict"] == "grounded"
        assert data["confidence"] == 0.95

    def test_append_is_unbuffered(self, audit_log: GroundingAuditLog) -> None:
        """append() writes immediately (not buffered)."""
        entry = DiscriminationAuditEntry(
            claim_hash="def456",
            verdict=GroundingVerdict.UNGROUNDED,
            confidence=0.3,
            provenances=[],
        )
        audit_log.append(entry)
        # Read file immediately — should have content
        content = audit_log._path.read_text(encoding="utf-8").strip()
        assert content

    def test_audit_file_path_format(self, temp_dir: Path) -> None:
        log = GroundingAuditLog(temp_dir)
        assert log._path == temp_dir / "grounding-audit.jsonl"

    def test_multiple_append_entries(self, audit_log: GroundingAuditLog) -> None:
        entries = [
            DiscriminationAuditEntry(
                claim_hash=f"hash{i}",
                verdict=GroundingVerdict.GROUNDED,
                confidence=0.9,
                provenances=[],
            )
            for i in range(3)
        ]
        for e in entries:
            audit_log.append(e)

        lines = audit_log._path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3
        for i, line in enumerate(lines):
            data = json.loads(line)
            assert data["claim_hash"] == f"hash{i}"

    def test_claim_hash_is_64_char_hex(self, audit_log: GroundingAuditLog) -> None:
        claim_text = "The receiving party shall not disclose"
        entry = DiscriminationAuditEntry(
            claim_hash=DiscriminationAuditEntry._hash_claim(claim_text),
            verdict=GroundingVerdict.GROUNDED,
            confidence=0.95,
            provenances=[],
        )
        audit_log.append(entry)
        content = audit_log._path.read_text(encoding="utf-8").strip()
        data = json.loads(content)
        h = data["claim_hash"]
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_append_with_provenances(self, audit_log: GroundingAuditLog) -> None:
        prov = CitationProvenance(clause_id="4.3", paragraph_index=2, confidence=0.95)
        entry = DiscriminationAuditEntry(
            claim_hash="prov_hash",
            verdict=GroundingVerdict.GROUNDED,
            confidence=0.95,
            provenances=[prov],
        )
        audit_log.append(entry)
        data = json.loads(audit_log._path.read_text(encoding="utf-8"))
        assert len(data["provenances"]) == 1
        assert data["provenances"][0]["clause_id"] == "4.3"

    def test_append_with_reason(self, audit_log: GroundingAuditLog) -> None:
        entry = DiscriminationAuditEntry(
            claim_hash="reason_hash",
            verdict=GroundingVerdict.UNGROUNDED,
            confidence=0.2,
            provenances=[],
            reason="No matching clause found",
        )
        audit_log.append(entry)
        data = json.loads(audit_log._path.read_text(encoding="utf-8"))
        assert data["reason"] == "No matching clause found"
