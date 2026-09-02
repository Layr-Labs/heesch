"""v2 round trips (multilevel spec §9.1/§9.3): M3 model->geometry with the
M6 label check, M4 geometry->model via the classifier DFS, geometric
cross-count equality, the M7 window-vs-family-5 structural test, and the
family-3 implication check."""

import importlib.util
import pathlib

import pytest

pysat_solvers = pytest.importorskip("pysat.solvers")
Solver = pysat_solvers.Solver

from conftest import ROOT

from heesch_encoder.multilevel.api import encode_multilevel
from heesch_encoder.multilevel.model import (
    config_assignment,
    config_to_corona_placements,
    decode_model,
    violated_clause,
)
from heesch_verify.grids import GRIDS
from heesch_verify.patch import check_corona
from heesch_verify.result import VerifyError

MODEL_CAP = 2500

_spec = importlib.util.spec_from_file_location(
    "classify", pathlib.Path(ROOT) / "tools" / "classify.py"
)
classify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(classify)

ML_FIXTURES = [
    ("mono", "O", [(0, 0)], 2),
    ("domino", "O", [(0, 0), (1, 0)], 2),
    ("T", "O", [(0, 0), (1, 0), (2, 0), (1, 1)], 1),
    ("deepU", "O",
     [(0, 0), (1, 0), (2, 0)] + [(0, y) for y in range(1, 4)] + [(2, y) for y in range(1, 4)],
     1),
    ("slotblock", "O",
     [(x, y) for x in range(5) for y in range(3) if (x, y) not in ((2, 1), (2, 2))],
     1),
    ("hex1", "H", [(0, 0)], 2),
    ("iam2", "I", [(0, 0), (1, 1)], 1),
]


def _setup(name):
    _n, gid, cells, m = next(f for f in ML_FIXTURES if f[0] == name)
    grid = GRIDS[gid]
    contact = grid.contact("point")
    tile = frozenset(cells)
    return tile, grid, contact, m, encode_multilevel(tile, grid, contact, m)


def _has_empty(enc):
    return any(len(c) == 0 for c in enc.formula.clauses)


@pytest.mark.parametrize("name", [f[0] for f in ML_FIXTURES])
def test_m3_models_decode_with_correct_labels(name):
    tile, grid, contact, m, enc = _setup(name)
    if _has_empty(enc):
        return  # trivially UNSAT (empty clause) — M3 vacuous
    total_x = enc.formula.level_offsets[-1] + len(enc.formula.levels[-1])
    with Solver(name="cadical195",
                bootstrap_with=[list(c) for c in enc.formula.clauses]) as s:
        for i, model in enumerate(s.enum_models()):
            if i >= MODEL_CAP:
                break
            config = decode_model(enc.formula, model)
            placements = config_to_corona_placements(tile, config, grid)
            try:
                corona = check_corona(tile, placements, grid, contact,
                                      hole_mode="none")
            except VerifyError as e:
                raise AssertionError(
                    f"{name}: model rejected by oracle ({e.code.value}) — "
                    "M6 mislabel or over-permissive encoder"
                )
            assert corona.max_level == m, (
                f"{name}: model has {corona.max_level} coronas, expected {m} "
                "— M6 nonemptiness violated"
            )


def _weak_configs(tile, grid, contact, m, cap=30_000):
    """Enumerate weak m-configurations via the classifier DFS, hole-agnostic."""
    import time

    state = classify._State(tile, grid, contact, time.time() + 600)
    out = []

    def rec(patch_cells, placements, k):
        if len(out) > cap:
            raise classify.Budget
        if k == m:
            out.append(tuple(placements))
            return
        for sol in classify._iter_completions(state, patch_cells,
                                              want_hole_free=False):
            if sol is classify.ANY_SAT:
                continue
            cells = set(patch_cells)
            for p in sol:
                cells |= classify.materialize(p, tile, grid)
            rec(frozenset(cells), placements + [(k + 1, p) for p in sol], k + 1)

    try:
        rec(frozenset(tile), [], 0)
    except classify.Budget:
        return None
    return out


@pytest.mark.parametrize("name", [f[0] for f in ML_FIXTURES])
def test_m4_weak_configs_satisfy_formula_and_cross_count(name):
    tile, grid, contact, m, enc = _setup(name)
    configs = _weak_configs(tile, grid, contact, m)
    if configs is None:
        pytest.skip(f"{name}: config count exceeds cap")

    if _has_empty(enc):
        assert configs == [], f"{name}: configs exist despite empty clause"
        return

    # M4: every enumerated weak configuration satisfies F.
    for config in configs:
        assign = config_assignment(enc.formula, config)
        bad = violated_clause(enc.formula, assign)
        assert bad is None, (
            f"{name}: weak config violates clause {bad} — over-restrictive "
            "encoder (the false-record direction)"
        )

    # Geometric cross-count: collapse symmetry duplicates on both sides.
    groups: dict = {}
    for li, lv in enumerate(enc.formula.levels):
        for i, p in enumerate(lv):
            v = enc.formula.level_offsets[li] + i + 1
            cs = classify.materialize(p, tile, grid)
            groups.setdefault((li + 1, cs), []).append(v)
    assumptions = [-v for vs in groups.values() for v in vs[1:]]

    model_shapes = set()
    exhausted = True
    with Solver(name="cadical195",
                bootstrap_with=[list(c) for c in enc.formula.clauses]) as s:
        for i, model in enumerate(s.enum_models(assumptions=assumptions)):
            if i >= MODEL_CAP:
                exhausted = False
                break
            config = decode_model(enc.formula, model)
            model_shapes.add(frozenset(
                (lvl, classify.materialize(p, tile, grid)) for lvl, p in config
            ))
    if exhausted:
        dfs_shapes = {
            frozenset((lvl, classify.materialize(p, tile, grid))
                      for lvl, p in config)
            for config in configs
        }
        assert model_shapes == dfs_shapes, (
            f"{name}: collapsed models ({len(model_shapes)}) != DFS weak "
            f"configs ({len(dfs_shapes)})"
        )


@pytest.mark.parametrize("name", [f[0] for f in ML_FIXTURES])
def test_m7_window_backed_by_family5(name):
    """Every coverer excluded from a family-6 window must be >= 2 levels away
    AND have its family-5 separation clause present — M7 as a consequence of
    W3, checked mechanically."""
    tile, grid, contact, m, enc = _setup(name)
    ml = enc.formula
    clause_set = {frozenset(c) for c in ml.clauses}
    total_x = ml.level_offsets[-1] + len(ml.levels[-1])

    cover: dict = {}
    for li, lv in enumerate(ml.levels):
        for i, p in enumerate(lv):
            v = ml.level_offsets[li] + i + 1
            for c in classify.materialize(p, tile, grid):
                cover.setdefault(c, []).append(v)

    checked = 0
    for cl in ml.clauses:
        negs = [l for l in cl if l < 0 and abs(l) <= total_x]
        poss = [l for l in cl if l > 0]
        if len(negs) != 1 or not poss:
            continue  # only family-6-shaped clauses (one trigger + coverers)
        v = abs(negs[0])
        lvl_q, q = ml.placement_of_var(v)
        # find the halo cell this clause covers: the cell common to all
        # positive literals' placements... cheaper: check every excluded var.
        pos_set = set(poss)
        # reconstruct h: any cell covered by all present positives isn't
        # reliable; instead verify the window property for each candidate
        # halo cell of q whose windowed cover equals pos_set.
        from heesch_verify.patch import contact_neighbors

        for h in contact_neighbors(classify.materialize(q, tile, grid), contact):
            if h in tile:
                continue
            window = {
                w for w in cover.get(h, ())
                if abs(ml.placement_of_var(w)[0] - lvl_q) <= 1
            }
            if window != pos_set:
                continue
            for w in cover.get(h, ()):
                if w in window:
                    continue
                lvl_w, _ = ml.placement_of_var(w)
                assert abs(lvl_w - lvl_q) >= 2
                assert frozenset((-v, -w)) in clause_set, (
                    f"{name}: windowed-out coverer var {w} (level {lvl_w}) of "
                    f"trigger var {v} (level {lvl_q}) lacks its family-5 clause"
                )
                checked += 1
            break
    # (checked may be 0 at small m where no coverer falls outside the window)


@pytest.mark.parametrize("name", [f[0] for f in ML_FIXTURES])
def test_family3_implied_not_emitted(name):
    """Same-cellset copies at different levels share every cell, so family 2
    covers them; no explicit same-copy AMO family may exist."""
    tile, grid, contact, m, enc = _setup(name)
    ml = enc.formula
    by_cs: dict = {}
    for li, lv in enumerate(ml.levels):
        for i, p in enumerate(lv):
            v = ml.level_offsets[li] + i + 1
            by_cs.setdefault(classify.materialize(p, tile, grid), []).append(v)
    group_vars = [set(g.variables) for g in ml.amo_groups]
    for cs, vs in by_cs.items():
        if len(vs) < 2:
            continue
        vset = set(vs)
        # every cell of cs yields an AMO group containing all of vs
        assert any(vset <= g for g in group_vars), (
            f"{name}: duplicate-cellset vars {vs} not jointly covered by any "
            "AMO group — family-3 implication broken"
        )
