"""At-most-one encodings (spec §4.4). The threshold is a frozen constant
recorded in the revision manifest; changing it is a new revision.

`aux_assignment` lives HERE, beside the clause generator, so the §9.2
geometry->model extension and the encoder can never drift apart."""

from __future__ import annotations

AMO_THRESHOLD = 20


def pairwise(variables: list[int]) -> list[tuple[int, int]]:
    """(¬x_i ∨ ¬x_j) for i < j; variables must be pre-sorted ascending."""
    out = []
    n = len(variables)
    for i in range(n):
        for j in range(i + 1, n):
            out.append((-variables[i], -variables[j]))
    return out


def sequential(variables: list[int], next_aux: int) -> tuple[list[tuple[int, ...]], int]:
    """Sinz sequential AMO. Returns (clauses, aux_count). Aux variables are
    next_aux .. next_aux + n - 2 (s_1..s_{n-1})."""
    n = len(variables)
    assert n >= 2
    s = [next_aux + i for i in range(n - 1)]
    clauses: list[tuple[int, ...]] = []
    clauses.append((-variables[0], s[0]))
    for i in range(1, n - 1):
        clauses.append((-variables[i], s[i]))
        clauses.append((-s[i - 1], s[i]))
        clauses.append((-variables[i], -s[i - 1]))
    clauses.append((-variables[n - 1], -s[n - 2]))
    return clauses, n - 1


def aux_assignment(variables: list[int], aux_start: int, aux_count: int,
                   x: dict[int, bool]) -> dict[int, bool]:
    """The functional extension: s_i = OR(x_1..x_{i+1's prefix}). For any
    assignment with at most one true variable this satisfies every
    sequential clause (obligation E2's projection direction)."""
    out = {}
    prefix = False
    for i in range(aux_count):
        prefix = prefix or x.get(variables[i], False)
        out[aux_start + i] = prefix
    return out
