"""Citation Grounding Discriminator — LLM-based post-hoc grounding validation."""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from openreview_cli.gateway.router import Gateway
    from openreview_cli.parsing.models import Clause, Document
    from openreview_cli.review.models import ReviewReport

from openreview_cli.gateway.models import CapabilityRequirement
from openreview_cli.grounding.audit import GroundingAuditLog
from openreview_cli.grounding.metrics import compute_cg_metrics
from openreview_cli.grounding.models import (
    CGMetrics,
    CGReport,
    CitationProvenance,
    DiscriminationAuditEntry,
    GroundingResult,
    GroundingVerdict,
)
from openreview_cli.grounding.prompts import (
    build_grounding_messages,
    parse_grounding_response,
)

logger = logging.getLogger(__name__)

_BATCH_SIZE = 10  # Max claims per gateway call


class CitationGroundingDiscriminator:
    """LLM-based post-hoc discriminator for contract-clause grounding.

    Validates that each assessment claim in a ReviewReport is actually
    supported by the source document clause it cites.
    """

    def __init__(
        self,
        mode: Literal["strict", "lenient"] = "strict",
        gateway: Gateway | None = None,
        model: str | None = None,
        output_dir: str | None = None,
    ) -> None:
        self.mode: Literal["strict", "lenient"] = mode
        self._model = model
        self._output_dir = output_dir

        from openreview_cli.gateway.router import Gateway as _Gateway

        self._gateway = gateway or _Gateway()

        # Create audit log
        import tempfile

        audit_dir = output_dir or tempfile.mkdtemp(prefix="grounding_audit_")
        self._audit_log = GroundingAuditLog(audit_dir)

    def ground_claim(
        self,
        claim_text: str,
        cited_clause_id: str,
        clause_text: str,
    ) -> tuple[GroundingVerdict, list[CitationProvenance], float]:
        """Ground a single claim against a single clause.

        Args:
            claim_text: The extracted claim text.
            cited_clause_id: The clause ID cited by the claim.
            clause_text: The full text of the cited clause.

        Returns:
            (verdict, provenances, confidence) tuple.
        """
        if not claim_text.strip():
            logger.warning("Zero-length claim text")
            return (GroundingVerdict.UNGROUNDED, [], 0.0)

        # Build a minimal source clauses list
        from openreview_cli.parsing.models import Clause

        source_clause = Clause(
            id=cited_clause_id,
            title=None,
            text=clause_text,
            level=1,
            parent_id=None,
            source_page=None,
            source_paragraph=None,
            source_span=None,
        )

        messages = build_grounding_messages(
            source_clauses=[source_clause],
            claims=[(0, claim_text, cited_clause_id)],
        )

        try:
            chat_kwargs: dict[str, Any] = {
                "requirement": CapabilityRequirement(capability="reasoning")
            }
            if self._model:
                chat_kwargs["model"] = self._model
            response = self._gateway.chat("grounding", messages, **chat_kwargs)
        except Exception as e:
            logger.warning("Gateway call failed: %s", e)
            return (GroundingVerdict.UNCERTAIN, [], 0.0)

        results = parse_grounding_response(response)
        if not results:
            logger.warning("Failed to parse grounding response for claim")
            return (GroundingVerdict.UNCERTAIN, [], 0.0)

        _, verdict, provenances, confidence = results[0]
        return (verdict, provenances, confidence)

    def ground_report(
        self,
        report: ReviewReport,
        document: Document,
        source_clauses: list[Clause] | None = None,
    ) -> CGReport:
        """Ground all claims in a ReviewReport against the source document.

        Skips claims where citation_valid=False.
        Batches claims (5-10 per gateway call).
        Records audit entries for every claim.

        Args:
            report: The ReviewReport from single-party review.
            document: The parsed source document (for clause text lookup).

        Returns:
            CGReport with per-claim verdicts, provenances, and metrics.
        """
        verdicts: list[GroundingResult] = []
        total = len(report.assessments)

        if not report.assessments:
            return CGReport(
                verdicts=[],
                mode=self.mode,
                metrics=CGMetrics(
                    citation_precision=1.0,
                    citation_relevance=1.0,
                    citation_locality=1.0,
                ),
                total_claims=0,
                grounded_count=0,
                ungrounded_count=0,
                uncertain_count=0,
            )

        # Build batches of claims to process
        from openreview_cli.review.models import QAVerdict

        batch: list[tuple[int, str, str]] = []

        for i, assessment in enumerate(report.assessments):
            # Skip claims where QA already flagged as invalid
            if assessment.qa_verdict == QAVerdict.disagree:
                logger.debug("Skipping claim %d: QA disagrees", i)
                continue

            claim_text = assessment.citation or assessment.clause_text
            cited_clause_id = assessment.clause_id

            # Skip assessments where extraction produced no citation
            # (no-match clauses or genuine extraction failures).
            # Grounding a non-existent citation produces a tautology —
            # the claim_text falls back to the full clause_text, which
            # trivially matches itself.
            if not assessment.citation:
                logger.debug("Skipping claim %d: no extraction citation to ground", i)
                continue

            if not claim_text.strip():
                logger.warning("Zero-length claim text at index %d", i)
                verdicts.append(
                    GroundingResult(
                        claim_index=i,
                        verdict=GroundingVerdict.UNGROUNDED,
                        provenances=[],
                        reason="Zero-length claim text",
                    )
                )
                continue

            batch.append((i, claim_text, cited_clause_id))

            if len(batch) >= _BATCH_SIZE:
                verdicts.extend(self._process_batch(batch, document, source_clauses))
                batch = []

        # Process remaining claims
        if batch:
            verdicts.extend(self._process_batch(batch, document, source_clauses))

        # Count verdicts
        counter = Counter(r.verdict for r in verdicts)
        grounded_count = counter.get(GroundingVerdict.GROUNDED, 0)
        ungrounded_count = counter.get(GroundingVerdict.UNGROUNDED, 0)
        uncertain_count = counter.get(GroundingVerdict.UNCERTAIN, 0)

        # Build claim-text lookup for metrics
        claim_text_by_index: dict[int, str] = {
            i: a.clause_text for i, a in enumerate(report.assessments)
        }

        # Compute metrics
        metrics = compute_cg_metrics(verdicts, document, source_clauses, claim_text_by_index)

        return CGReport(
            verdicts=verdicts,
            mode=self.mode,
            metrics=metrics,
            total_claims=total,
            grounded_count=grounded_count,
            ungrounded_count=ungrounded_count,
            uncertain_count=uncertain_count,
        )

    def _process_batch(
        self,
        batch: list[tuple[int, str, str]],
        document: Document,
        source_clauses: list[Clause] | None = None,
    ) -> list[GroundingResult]:
        """Process a batch of claims through the gateway.

        Args:
            batch: List of (claim_index, claim_text, cited_clause_id) tuples.
            document: The source document (metadata only).
            source_clauses: The parsed clause objects from the source document.

        Returns:
            List of GroundingResult objects.
        """
        if not batch:
            return []

        matched_clauses = self._get_clauses_for_batch(batch, document, source_clauses)

        messages = build_grounding_messages(matched_clauses, batch)

        try:
            chat_kwargs: dict[str, Any] = {
                "requirement": CapabilityRequirement(capability="reasoning")
            }
            if self._model:
                chat_kwargs["model"] = self._model
            response = self._gateway.chat("grounding", messages, **chat_kwargs)
        except Exception as e:
            logger.warning("Gateway batch call failed: %s", e)
            return [
                GroundingResult(
                    claim_index=idx,
                    verdict=GroundingVerdict.UNCERTAIN,
                    provenances=[],
                    reason=f"Gateway error: {e}",
                )
                for idx, _, _ in batch
            ]

        parsed = parse_grounding_response(response)

        # Build lookup from parsed results
        parsed_by_index: dict[int, tuple[GroundingVerdict, list[CitationProvenance], float]] = {}
        for claim_index, verdict, provenances, confidence in parsed:
            parsed_by_index[claim_index] = (verdict, provenances, confidence)

        # Map results back to batch items
        results: list[GroundingResult] = []
        for idx, claim_text, cited_clause_id in batch:
            # Determine reason
            reason: str | None = None

            if idx in parsed_by_index:
                verdict, provenances, confidence = parsed_by_index[idx]

                if verdict == GroundingVerdict.UNGROUNDED:
                    reason = f"Claim not supported by clause {cited_clause_id}"
                elif verdict == GroundingVerdict.UNCERTAIN:
                    reason = f"Ambiguous provenance for clause {cited_clause_id}"
            else:
                # Fallback for claims not in parsed response
                verdict = GroundingVerdict.UNCERTAIN
                provenances = []
                reason = "No verdict returned by discriminator"
                confidence = 0.0

            # Mode-dependent multi-provenance handling
            if self.mode == "strict" and len(provenances) > 1:
                # Strict mode: multi-provenance flags as uncertain
                verdict = GroundingVerdict.UNCERTAIN
                reason = f"Multiple provenances ({len(provenances)}) — uncertain in strict mode"
                provenances = []
                confidence = min(confidence, 0.5)

            # Record audit entry
            audit_entry = DiscriminationAuditEntry(
                claim_hash=DiscriminationAuditEntry._hash_claim(claim_text),
                verdict=verdict,
                confidence=confidence,
                provenances=provenances,
                reason=reason,
            )
            self._audit_log.append(audit_entry)

            results.append(
                GroundingResult(
                    claim_index=idx,
                    verdict=verdict,
                    provenances=provenances,
                    reason=reason,
                )
            )

        return results

    def _get_clauses_for_batch(
        self,
        batch: list[tuple[int, str, str]],
        document: Document,
        source_clauses: list[Clause] | None = None,
    ) -> list[Clause]:
        """Get matching Clause objects for a batch of claims.

        Looks up clause objects by the citation ID from each claim.

        Args:
            batch: List of (claim_index, claim_text, cited_clause_id) tuples.
            document: The source document (metadata only, not used here).
            source_clauses: The parsed clause objects from the source document.

        Returns:
            List of Clause objects matching the cited IDs in the batch.
        """
        if not source_clauses:
            return []

        clause_lookup = {c.id: c for c in source_clauses}
        cited_ids = {cited_id for _, _, cited_id in batch}
        return [clause_lookup[cid] for cid in cited_ids if cid in clause_lookup]
