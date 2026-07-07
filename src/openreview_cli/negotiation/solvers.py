"""Equilibrium solvers — Nash, QRE, and Level-k."""

from __future__ import annotations

import contextlib
import itertools

import numpy as np


def _solve_support(
    a: np.ndarray,
    b: np.ndarray,
    row_support: tuple[int, ...],
    col_support: tuple[int, ...],
) -> tuple[np.ndarray, np.ndarray] | None:
    """Solve for mixed strategies with given support pair.

    Solves the linear system implied by Nash equilibrium conditions
    for the given support sets. Returns None if no equilibrium exists
    with these supports (singular system, negative probabilities, or
    best-response violations).
    """
    m, n = a.shape
    r, c = len(row_support), len(col_support)

    if r != c:
        return None

    # --- Solve for y (column player's mixed strategy) ---
    # Condition: for i in row_support, (a[i,:] @ y) equal across i
    m_y = np.zeros((r, r))
    b_y = np.zeros(r)
    for k in range(1, r):
        m_y[k - 1, :] = a[row_support[k], col_support] - a[row_support[0], col_support]
    m_y[r - 1, :] = 1.0
    b_y[r - 1] = 1.0

    try:
        y_j = np.linalg.solve(m_y, b_y)
    except np.linalg.LinAlgError:
        return None

    if np.any(y_j < -1e-10):
        return None
    y_j = np.maximum(y_j, 0.0)

    y = np.zeros(n)
    y[np.array(col_support)] = y_j

    # Check rows not in support get no better payoff
    v = float(a[row_support[0], :] @ y)
    row_support_set = set(row_support)
    for i in range(m):
        if i not in row_support_set and float(a[i, :] @ y) > v + 1e-8:
            return None

    # --- Solve for x (row player's mixed strategy) ---
    m_x = np.zeros((r, r))
    b_x = np.zeros(r)
    for k in range(1, r):
        m_x[k - 1, :] = b[row_support, col_support[k]] - b[row_support, col_support[0]]
    m_x[r - 1, :] = 1.0
    b_x[r - 1] = 1.0

    try:
        x_i = np.linalg.solve(m_x, b_x)
    except np.linalg.LinAlgError:
        return None

    if np.any(x_i < -1e-10):
        return None
    x_i = np.maximum(x_i, 0.0)

    x = np.zeros(m)
    x[np.array(row_support)] = x_i

    # Check columns not in support get no better payoff
    u = float(x @ b[:, col_support[0]])
    col_support_set = set(col_support)
    for j in range(n):
        if j not in col_support_set and float(x @ b[:, j]) > u + 1e-8:
            return None

    return x, y


def _support_enumeration(
    a: np.ndarray,
    b: np.ndarray,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Enumerate all Nash equilibria for a 2-player game.

    Enumerates all equal-sized support pairs and solves the
    equilibrium linear system for each. Deduplicates results.

    Supports up to 6x6 square games.
    """
    m, n = a.shape
    equilibria: list[tuple[np.ndarray, np.ndarray]] = []
    max_r = min(m, n, 6)

    for r in range(1, max_r + 1):
        for row_support in itertools.combinations(range(m), r):
            for col_support in itertools.combinations(range(n), r):
                result = _solve_support(a, b, row_support, col_support)
                if result is None:
                    continue
                # Deduplicate
                eq_x, eq_y = result
                if not any(
                    np.allclose(eq_x, ex_x, atol=1e-8) and np.allclose(eq_y, ex_y, atol=1e-8)
                    for ex_x, ex_y in equilibria
                ):
                    equilibria.append(result)

    return equilibria


def solve_nash(
    payoff_a: list[list[float]] | np.ndarray,
    payoff_b: list[list[float]] | np.ndarray,
) -> tuple[np.ndarray, np.ndarray, str, bool]:
    """Compute Nash equilibrium via support enumeration (hand-rolled NumPy).

    Falls back to QRE with lambda=1.0 if no equilibrium is found.
    When multiple equilibria exist, picks the one maximising user payoff.
    Fourth return value ``is_fallback`` is ``True`` when QRE fallback was used.

    Supports square games up to 6x6.
    """
    payoff_a_np = np.asarray(payoff_a, dtype=float)
    payoff_b_np = np.asarray(payoff_b, dtype=float)
    n = payoff_a_np.shape[0]

    if n < 2:
        raise ValueError("Game must have at least 2 actions")

    equilibria: list[tuple[np.ndarray, np.ndarray]] = []
    with contextlib.suppress(Exception):
        equilibria = _support_enumeration(payoff_a_np, payoff_b_np)

    if not equilibria:
        row_s, col_s, eq_t = solve_qre(payoff_a_np, payoff_b_np, lam=1.0)
        return row_s, col_s, eq_t, True

    eq_type: str
    if len(equilibria) > 1:
        eq_type = "multiple"
        # Pick the one maximising user payoff
        best_eq = max(
            equilibria,
            key=lambda eq: float(np.dot(np.asarray(eq[0]), np.dot(payoff_a_np, np.asarray(eq[1])))),
        )
        row_strat, col_strat = best_eq
    else:
        row_strat, col_strat = equilibria[0]
        row_arr = np.asarray(row_strat)
        col_arr = np.asarray(col_strat)
        if row_arr.size <= 1 or (
            any(abs(p - 1.0) < 1e-6 for p in row_arr) and any(abs(p - 1.0) < 1e-6 for p in col_arr)
        ):
            eq_type = "pure"
        else:
            eq_type = "mixed"

    return np.asarray(row_strat, dtype=float), np.asarray(col_strat, dtype=float), eq_type, False


def solve_qre(
    payoff_a: list[list[float]] | np.ndarray,
    payoff_b: list[list[float]] | np.ndarray,
    lam: float = 1.0,
    max_iter: int = 1000,
    tol: float = 1e-6,
) -> tuple[np.ndarray, np.ndarray, str]:
    """Compute logit Quantal Response Equilibrium (QRE).

    Uses fixed-point iteration on the logit response functions.
    Convergence criterion: maximum change in strategy < ``tol``.
    """
    payoff_a_np = np.asarray(payoff_a, dtype=float)
    payoff_b_np = np.asarray(payoff_b, dtype=float)
    n = payoff_a_np.shape[0]

    if n < 2:
        raise ValueError("Game must have at least 2 actions")

    # Initialise at uniform
    pi_row = np.ones(n) / n
    pi_col = np.ones(n) / n

    for _ in range(max_iter):
        u_row = payoff_a_np @ pi_col
        u_col = payoff_b_np.T @ pi_row

        u_row_shifted = u_row - u_row.max()
        u_col_shifted = u_col - u_col.max()

        exp_row = np.exp(lam * u_row_shifted)
        exp_col = np.exp(lam * u_col_shifted)

        pi_row_new = exp_row / exp_row.sum()
        pi_col_new = exp_col / exp_col.sum()

        delta = max(
            np.max(np.abs(pi_row_new - pi_row)),
            np.max(np.abs(pi_col_new - pi_col)),
        )
        pi_row, pi_col = pi_row_new, pi_col_new

        if delta < tol:
            break

    return pi_row, pi_col, "mixed"


def solve_level_k(
    payoff_a: list[list[float]] | np.ndarray,
    payoff_b: list[list[float]] | np.ndarray,
    k: int = 2,
) -> tuple[np.ndarray, np.ndarray, str]:
    """Compute Level-k equilibrium via iterative best-response.

    Level-0 is uniform random. Level-1 best-responds to Level-0.
    Level-k (k >= 2) best-responds to Level-(k-1).
    """
    payoff_a_np = np.asarray(payoff_a, dtype=float)
    payoff_b_np = np.asarray(payoff_b, dtype=float)
    n = payoff_a_np.shape[0]

    if n < 2:
        raise ValueError("Game must have at least 2 actions")

    # Cap k at 3 per research.md U3
    k_actual = min(max(k, 0), 3)

    # Level 0: uniform random
    pi_row: np.ndarray = np.ones(n) / n
    pi_col: np.ndarray = np.ones(n) / n

    if k_actual == 0:
        return pi_row, pi_col, "mixed"

    # Iterate levels
    for level in range(1, k_actual + 1):
        if level % 2 == 1:
            # Row (user) best-responds to col's previous level
            u_row = payoff_a_np @ pi_col
            best_actions = np.where(u_row == u_row.max())[0]
            pi_row = np.zeros(n)
            pi_row[best_actions] = 1.0 / len(best_actions)
        else:
            # Col (counterparty) best-responds to row's previous level
            u_col = payoff_b_np.T @ pi_row
            best_actions = np.where(u_col == u_col.max())[0]
            pi_col = np.zeros(n)
            pi_col[best_actions] = 1.0 / len(best_actions)

    return pi_row, pi_col, "mixed"
