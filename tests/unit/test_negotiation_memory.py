"""Memory budget validation for the negotiation module.

Asserts peak RSS < 5 MB over baseline for a 30-clause negotiation.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from openreview_cli.negotiation.solvers import solve_level_k, solve_nash, solve_qre


@pytest.mark.memory
class TestNegotiationMemory:
    """Memory budget: negotiation module must add <5 MB peak."""

    def test_qre_memory_30_clauses(self, memory_tracker: object) -> None:
        """30 QRE computations stay within memory budget."""
        # memory_tracker fixture activated — tracks peak memory

        # Create 30 random 3x3 games
        for _ in range(30):
            A = np.random.rand(3, 3).tolist()
            B = np.random.rand(3, 3).tolist()
            user_strat, cp_strat, eq_type = solve_qre(A, B, lam=1.0, max_iter=100, tol=1e-4)
            assert len(user_strat) == 3
            assert abs(sum(user_strat) - 1.0) < 1e-6

    def test_nash_memory_30_clauses(self, memory_tracker: object) -> None:
        """30 Nash computations stay within memory budget."""
        # memory_tracker fixture activated
        for _ in range(30):
            A = np.random.rand(3, 3).tolist()
            B = np.random.rand(3, 3).tolist()
            user_strat, cp_strat, eq_type, *_ = solve_nash(A, B)
            assert abs(sum(user_strat) - 1.0) < 1e-6

    def test_levelk_memory_30_clauses(self, memory_tracker: object) -> None:
        """30 Level-k computations stay within memory budget."""
        # memory_tracker fixture activated
        for _ in range(30):
            A = np.random.rand(3, 3).tolist()
            B = np.random.rand(3, 3).tolist()
            user_strat, cp_strat, eq_type = solve_level_k(A, B, k=2)
            assert abs(sum(user_strat) - 1.0) < 1e-6


class TestNegotiationPerformance:
    """Performance: 30-clause negotiation completes in <5s."""

    def test_30_qre_completes_under_5s(self) -> None:
        """30 QRE computations complete in <5 seconds."""
        start = time.time()
        for _ in range(30):
            A = np.random.rand(3, 3).tolist()
            B = np.random.rand(3, 3).tolist()
            solve_qre(A, B, lam=1.0, max_iter=100, tol=1e-4)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"QRE 30 clauses took {elapsed:.2f}s"

    def test_30_nash_completes_under_5s(self) -> None:
        """30 Nash computations complete in <5 seconds."""
        start = time.time()
        for _ in range(30):
            A = np.random.rand(3, 3).tolist()
            B = np.random.rand(3, 3).tolist()
            solve_nash(A, B)  # returns 4-tuple, ignore extra value
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Nash 30 clauses took {elapsed:.2f}s"

    def test_30_levelk_completes_under_5s(self) -> None:
        """30 Level-k computations complete in <5 seconds."""
        start = time.time()
        for _ in range(30):
            A = np.random.rand(3, 3).tolist()
            B = np.random.rand(3, 3).tolist()
            solve_level_k(A, B, k=2)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Level-k 30 clauses took {elapsed:.2f}s"
