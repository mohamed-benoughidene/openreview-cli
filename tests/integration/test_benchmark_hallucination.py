"""Hallucination detection integration test (T028).

Use ROUGE-L placeholder on seeded non-hallucinated claims,
assert hallucination rate < 5%.
Cover edge cases: empty claims, fully overlapping claims,
claims with partial overlap.
"""

from openreview_cli.benchmark.hallu_detect import hallucination_rate, rouge_l_recall


class TestHallucinationRate:
    def test_no_claims_no_hallucination(self) -> None:
        rate = hallucination_rate([], ["Source text."])
        assert rate == 0.0

    def test_exact_overlap(self) -> None:
        rate = hallucination_rate(
            ["This is a test claim."],
            ["This is a test claim. And more source text."],
        )
        assert rate < 0.5  # ROUGE-L should be high

    def test_fully_supported_claims(self) -> None:
        """Assert high-RougeL claims are not flagged."""
        source = "The contract was signed on January 15, 2024 between Acme Corp and Beta Inc."
        claim = ["The contract was signed on January 15, 2024"]
        rate = hallucination_rate(claim, [source])
        assert rate == 0.0, "Fully overlapping claim should not be hallucinated"

    def test_empty_claims(self) -> None:
        rate = hallucination_rate([], ["Some source text."])
        assert rate == 0.0

    def test_empty_string_claim(self) -> None:
        rate = hallucination_rate([""], ["Source text"])
        assert rate == 0.0  # Empty string is not hallucination

    def test_completely_unrelated_claim(self) -> None:
        rate = hallucination_rate(
            ["Quantum physics is fascinating."],
            ["The contract sets forth the terms and conditions."],
        )
        assert rate == 1.0  # All claims should be flagged as hallucinated


class TestRougeLRecall:
    def test_empty_claims(self) -> None:
        recall = rouge_l_recall([], ["source"])
        assert recall == 1.0

    def test_empty_sources(self) -> None:
        recall = rouge_l_recall(["claim"], [])
        assert recall == 1.0

    def test_partial_overlap(self) -> None:
        recall = rouge_l_recall(
            ["quick brown fox"],
            ["The quick brown fox jumps over the lazy dog"],
        )
        assert recall > 0.5  # 3/4 tokens match

    def test_no_overlap(self) -> None:
        recall = rouge_l_recall(
            ["completely different"],
            ["source text here"],
        )
        assert recall == 0.0

    def test_full_overlap(self) -> None:
        recall = rouge_l_recall(
            ["quick brown fox"],
            ["quick brown fox"],
        )
        assert recall == 1.0
