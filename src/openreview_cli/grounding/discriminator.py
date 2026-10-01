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
from openreview_cli.grounding import presence
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
    build_second_pass_messages,
    parse_grounding_response,
    parse_miscited_ids,
)

logger = logging.getLogger(__name__)

_BATCH_SIZE = 10  # Max claims per gateway call


def combine_grounding_passes(
    first: GroundingVerdict,
    second: GroundingVerdict | None,
    *,
    second_available: bool = True,
) -> GroundingVerdict:
    """Both supported accepts; an abstention from either pass is 'not sure'; otherwise the
    disagreement rejects. An unavailable second pass keeps the first verdict — never a
    downgrade, so a broken second call cannot turn an accepted finding into 'not sure' (which
    strict mode would delete)."""
    if not second_available or second is None:
        return first
    if GroundingVerdict.UNCERTAIN in (first, second):
        return GroundingVerdict.UNCERTAIN
    if first is GroundingVerdict.GROUNDED and second is GroundingVerdict.GROUNDED:
        return GroundingVerdict.GROUNDED
    return GroundingVerdict.UNGROUNDED


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
        session_id: str | None = None,
        require_pass_agreement: bool = False,
    ) -> None:
        self.mode: Literal["strict", "lenient"] = mode
        self._model = model
        self._output_dir = output_dir
        self._session_id = session_id
        # Item 4: the both-passes-must-agree rule is off by default, so the shipped product's
        # behaviour is unchanged until the measurement supports turning it on.
        self.require_pass_agreement = require_pass_agreement
        # Answers the reader could not parse: distinct from a model that said
        # "uncertain", which also returns UNCERTAIN at confidence 0.0.
        self.unreadable_answers = 0
        # Second passes that failed or were unreadable: the first pass's verdict was kept.
        # Distinct from ``unreadable_answers`` so a broken second call is visible and is never
        # mistaken for a model that abstained.
        self.second_pass_fallbacks = 0

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

        # The same hint the batch path sends, from the same primitive. Text only.
        _score, wording_absent = presence.measure(claim_text, clause_text)
        messages = build_grounding_messages(
            source_clauses=[source_clause],
            claims=[(0, claim_text, cited_clause_id)],
            wording_absent_indices={0} if wording_absent else None,
        )

        try:
            chat_kwargs: dict[str, Any] = {
                "requirement": CapabilityRequirement(capability="reasoning")
            }
            if self._model:
                chat_kwargs["model"] = self._model
            if self._session_id is not None:
                chat_kwargs["session_id"] = self._session_id
            response = self._gateway.chat("grounding", messages, **chat_kwargs)
        except Exception as e:
            logger.warning("Gateway call failed: %s", e)
            return (GroundingVerdict.UNCERTAIN, [], 0.0)

        results = parse_grounding_response(response)
        if not results:
            logger.warning("Failed to parse grounding response for claim")
            self.unreadable_answers += 1
            return (GroundingVerdict.UNCERTAIN, [], 0.0)

        _, verdict, provenances, confidence = results[0]

        if self.require_pass_agreement:
            # The single-finding entry point is not batched (the measurement runs through it),
            # so its one narrow question is one call for its one finding.
            second = self._second_pass([source_clause], [(0, claim_text, cited_clause_id)])
            verdict, _disagreement, _not_sure = self._apply_pass_agreement(0, verdict, second)

        return (verdict, provenances, confidence)

    def _apply_pass_agreement(
        self,
        idx: int,
        verdict: GroundingVerdict,
        second_verdicts: dict[int, GroundingVerdict] | None,
    ) -> tuple[GroundingVerdict, bool, bool]:
        """Combine one claim's first-pass verdict with the second pass's answer (item 4).

        Returns ``(verdict, pass_disagreement, not_sure)``. The rule is applied only when it is
        on — then ``second_verdicts`` is the batch's map, ``None`` when the second call failed or
        nothing parsed; a missing index is treated the same way. In every other case the first
        verdict is returned unchanged, so the default (off) path cannot move a verdict. A missing
        second verdict keeps the first verdict and counts the fallback — never a downgrade, which
        would let strict mode delete a finding the first pass accepted. The two flags are
        display-only: neither is read by any verdict decision.
        """
        if not self.require_pass_agreement:
            return verdict, False, False
        second = second_verdicts.get(idx) if second_verdicts is not None else None
        if second is None:
            self.second_pass_fallbacks += 1
            return verdict, False, False
        combined = combine_grounding_passes(verdict, second)
        disagreed = {verdict, second} == {
            GroundingVerdict.GROUNDED,
            GroundingVerdict.UNGROUNDED,
        }
        return combined, disagreed, combined is GroundingVerdict.UNCERTAIN

    def _second_pass(
        self,
        prompt_clauses: list[Clause],
        batch: list[tuple[int, str, str]],
    ) -> dict[int, GroundingVerdict] | None:
        """The narrow question, one call per batch, forwarding the same model override and
        session id as the first pass. ``None`` when the call failed or nothing parsed: the
        caller then keeps the first pass's verdict, so a broken second pass can never turn an
        accepted finding into 'not sure' (which strict mode deletes)."""
        messages = build_second_pass_messages(prompt_clauses, batch)
        chat_kwargs: dict[str, Any] = {"requirement": CapabilityRequirement(capability="reasoning")}
        if self._model:
            chat_kwargs["model"] = self._model
        if self._session_id is not None:
            chat_kwargs["session_id"] = self._session_id
        try:
            response = self._gateway.chat("grounding", messages, **chat_kwargs)
        except Exception as e:
            logger.warning("Second grounding pass failed: %s", e)
            return None
        parsed = parse_grounding_response(response)
        return {index: verdict for index, verdict, _p, _c in parsed} if parsed else None

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

        # Recorded for every result this batch produces, including the gateway-error
        # fallbacks below. Neither value is read by any verdict decision.
        presence_by_index = self._measure_presence(batch, matched_clauses)

        # The flagged indices come straight out of that one measurement pass — the measure
        # is never recomputed, so the hint and the recorded flag cannot disagree. The hint
        # only names the measurement; the model still decides the verdict.
        wording_absent_indices = {
            idx for idx, (_number, absent) in presence_by_index.items() if absent
        }

        # Show the cited clauses first, then the document's other sections, so the checker
        # can name a sibling that actually supports a real but wrongly-cited finding. Only
        # the prompt gets the wider list; the hint below still measures the cited clauses.
        cited_ids = {clause.id for clause in matched_clauses}
        prompt_clauses = matched_clauses + [
            clause for clause in (source_clauses or []) if clause.id not in cited_ids
        ]

        messages = build_grounding_messages(prompt_clauses, batch, wording_absent_indices)

        try:
            chat_kwargs: dict[str, Any] = {
                "requirement": CapabilityRequirement(capability="reasoning")
            }
            if self._model:
                chat_kwargs["model"] = self._model
            if self._session_id is not None:
                chat_kwargs["session_id"] = self._session_id
            response = self._gateway.chat("grounding", messages, **chat_kwargs)
        except Exception as e:
            logger.warning("Gateway batch call failed: %s", e)
            return [
                GroundingResult(
                    claim_index=idx,
                    verdict=GroundingVerdict.UNCERTAIN,
                    provenances=[],
                    reason=f"Gateway error: {e}",
                    grounding_presence=presence_by_index[idx][0],
                    wording_absent=presence_by_index[idx][1],
                )
                for idx, _, _ in batch
            ]

        parsed = parse_grounding_response(response)

        # The fourth answer, and the text of every clause the checker could have named.
        # The guard below reads only ids and text; nothing here is logged or recorded.
        miscited_ids = parse_miscited_ids(response)
        all_clause_text_by_id = {c.id: c.text for c in (source_clauses or [])}

        # Build lookup from parsed results
        parsed_by_index: dict[int, tuple[GroundingVerdict, list[CitationProvenance], float]] = {}
        for claim_index, verdict, provenances, confidence in parsed:
            parsed_by_index[claim_index] = (verdict, provenances, confidence)

        # No early return here: a claim whose index the reader did not answer falls
        # through to the UNCERTAIN mapping below, so every absent index is one
        # unreadable answer. A wholly unparsable batch gives an empty mapping and
        # therefore counts the whole batch.
        self.unreadable_answers += sum(1 for index, _, _ in batch if index not in parsed_by_index)

        # Item 4: ONE extra call for the whole batch (≤10 findings), never one per finding.
        # ``None`` when the call failed, nothing parsed, or the rule is off (the default).
        second_verdicts = (
            self._second_pass(prompt_clauses, batch) if self.require_pass_agreement else None
        )

        # Map results back to batch items
        results: list[GroundingResult] = []
        for idx, claim_text, cited_clause_id in batch:
            # Determine reason
            reason: str | None = None
            presence_number, absent = presence_by_index[idx]

            # The fourth answer is a pointer field, never a verdict (FIX 1): it is believed
            # only when the finding's wording is substantially present in the named clause.
            # A failed check clears the pointer and leaves the verdict exactly as the passes
            # produced it — this never writes, downgrades or deletes a verdict.
            named = miscited_ids.get(idx)
            named_text = all_clause_text_by_id.get(named) if named is not None else None
            miscited_to_clause_id = (
                named if (named_text and not presence.measure(claim_text, named_text)[1]) else None
            )

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

            # Item 4: combine the two passes for this claim. Only when the flag turned the
            # second pass on and it really answered for this index. A missing or failed second
            # verdict keeps the first pass's verdict (counted, never a downgrade). The two
            # flags are display-only; neither is read by any verdict decision.
            verdict, pass_disagreement, not_sure = self._apply_pass_agreement(
                idx, verdict, second_verdicts
            )

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
                    grounding_presence=presence_number,
                    wording_absent=absent,
                    miscited_to_clause_id=miscited_to_clause_id,
                    pass_disagreement=pass_disagreement,
                    not_sure=not_sure,
                )
            )

        return results

    def _measure_presence(
        self,
        batch: list[tuple[int, str, str]],
        matched_clauses: list[Clause],
    ) -> dict[int, tuple[float | None, bool]]:
        """Measure each claim against the clause text it was sent with.

        One computation per claim, so the coverage number and the wording-absent hint
        cannot disagree. A claim whose cited clause text is not in hand carries
        ``(None, False)`` — the measure never ran for it. The result is a pure function
        of the two texts; it is never read by a verdict decision.
        """
        clause_text_by_id = {clause.id: clause.text for clause in matched_clauses}
        presence_by_index: dict[int, tuple[float | None, bool]] = {}
        for idx, claim_text, cited_clause_id in batch:
            clause_text = clause_text_by_id.get(cited_clause_id)
            if clause_text is None:
                presence_by_index[idx] = (None, False)
            else:
                presence_by_index[idx] = presence.measure(claim_text, clause_text)
        return presence_by_index

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
