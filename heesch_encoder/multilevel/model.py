"""Model decode / configuration evaluate — shared by the round-trip suites
and the runtime witness-model self-check (spec §7). Not on the emission path."""

from __future__ import annotations

from heesch_verify.transform import Xform

from ..amo import aux_assignment
from .types import MLFormula


def decode_model(ml: MLFormula, model) -> list:
    """Positive x literals of a pysat model -> [(level, Placement)]."""
    out = []
    total_x = ml.level_offsets[-1] + len(ml.levels[-1])
    for v in range(1, total_x + 1):
        if model[v - 1] > 0:
            out.append(ml.placement_of_var(v))
    return out


def config_assignment(ml: MLFormula, config) -> dict:
    """A weak configuration [(level, Placement)] -> full assignment including
    the canonical Sinz extension. Raises KeyError if a placement is not in
    its level's universe (an M1 violation caught loudly)."""
    index = []
    for lv in ml.levels:
        index.append({p: i for i, p in enumerate(lv)})
    total_x = ml.level_offsets[-1] + len(ml.levels[-1])
    assign = {v: False for v in range(1, ml.num_vars + 1)}
    for level, p in config:
        assign[ml.var_of(level, index[level - 1][p])] = True
    for g in ml.amo_groups:
        if g.kind == "sequential":
            assign.update(
                aux_assignment(list(g.variables), g.aux_start, g.aux_count, assign)
            )
    return assign


def violated_clause(ml: MLFormula, assign) -> tuple | None:
    for cl in ml.clauses:
        if not any((l > 0) == assign.get(abs(l), False) for l in cl):
            return cl
    return None


def config_to_corona_placements(tile_cells, config, grid) -> list:
    """[(level, Placement)] -> verifier placement list [(level, Xform)],
    with the fixed central copy prepended."""
    out = [(0, Xform(1, 0, 0, 0, 1, 0))]
    for level, p in config:
        sym = grid.orientations[p.symmetry_index]
        out.append((level, Xform(sym.a, sym.b, sym.c0 + p.tx,
                                 sym.d, sym.e, sym.f0 + p.ty)))
    return out
