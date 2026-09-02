"""Clause construction (spec §4). Emission order is part of the frozen spec
(§6): all non-overlap clauses (by cell in canonical order, then pair order),
then all coverage clauses (by cell in canonical order).

Determinism discipline: sets/dicts are used only for membership; every
iteration that reaches the Formula goes through ordering.sorted_* on the
same expression. See test_no_unordered_iteration.py.
"""

from __future__ import annotations

from heesch_verify.grids import Contact, Grid
from heesch_verify.patch import required_set

from .amo import AMO_THRESHOLD, pairwise, sequential
from .ordering import literal_key, sorted_cells
from .placements import enumerate_universe, materialize
from .types import AmoGroup, Formula, Placement


def compute_R(patch_cells, contact: Contact) -> list:
    """R in canonical cell order — same required_set the verifier uses (E5).
    The set difference is immediately sorted."""
    return sorted_cells(required_set(patch_cells, contact))  # ordered-ok: sorted


def build_formula(tile_cells, patch_cells, grid: Grid, contact: Contact,
                  amo_threshold: int = AMO_THRESHOLD) -> Formula:
    universe = enumerate_universe(tile_cells, patch_cells, grid, contact)
    R = compute_R(patch_cells, contact)

    # cell -> sorted covering variable list (1-indexed into universe)
    cover: dict = {}
    for var, p in enumerate(universe, start=1):
        for c in materialize(p, tile_cells, grid):
            cover.setdefault(c, []).append(var)
    # Variables were assigned in universe order, so each cover list is
    # already ascending; assert rather than trust.
    for c, vs in cover.items():  # ordered-ok: assertion only, no emission
        assert vs == sorted(vs)

    clauses: list[tuple[int, ...]] = []
    amo_groups: list[AmoGroup] = []
    next_aux = len(universe) + 1

    # Non-overlap: every cell covered by >= 2 placements, canonical order.
    multi = sorted_cells([c for c, vs in cover.items() if len(vs) >= 2])  # ordered-ok: sorted
    for c in multi:
        vs = cover[c]
        if len(vs) <= amo_threshold:
            pcs = pairwise(vs)
            clauses.extend(pcs)
            amo_groups.append(AmoGroup(cell=c, variables=tuple(vs), kind="pairwise"))
        else:
            scs, aux_count = sequential(vs, next_aux)
            clauses.extend(scs)
            amo_groups.append(
                AmoGroup(cell=c, variables=tuple(vs), kind="sequential",
                         aux_start=next_aux, aux_count=aux_count)
            )
            next_aux += aux_count

    # Coverage: every R-cell, canonical order. A cell no copy reaches emits
    # a real empty clause (§4.3) — trivially UNSAT, but the artifact stays
    # uniform and the checker still runs.
    for c in R:
        clauses.append(tuple(cover.get(c, ())))

    # Literal order within each clause (§6).
    ordered = tuple(tuple(sorted(cl, key=literal_key)) for cl in clauses)

    return Formula(
        num_vars=next_aux - 1,
        clauses=ordered,
        universe=tuple(universe),
        amo_groups=tuple(amo_groups),
        required_cells=tuple(R),
    )
