"""§9.1 (E3, model -> geometry) and §9.2 (E4, geometry -> model) round trips
against the geometry oracle, plus a geometric cross-count.

The shipped formula deliberately contains no symmetry breaking (§4.5), so a
symmetric tile yields one variable per orientation for the SAME cell set and
placement-level counts explode. The tests therefore work at two levels:

- E3 samples raw models (capped) and requires every one to decode to a
  corona the Stage 5 oracle accepts.
- E4 and the cross-count collapse to GEOMETRY: cellset-level covers. For
  model enumeration, non-canonical duplicate variables are forced off with
  test-side solver assumptions (a bijection onto geometric covers, since
  duplicates cover identical cells); for the brute force, the universe is
  pre-deduplicated by cell set.
"""

import pytest

pysat_solvers = pytest.importorskip("pysat.solvers")
Solver = pysat_solvers.Solver

from conftest import FIXTURES

from heesch_encoder.amo import aux_assignment
from heesch_encoder.api import encode
from heesch_encoder.placements import materialize
from heesch_verify.grids import GRIDS
from heesch_verify.patch import check_corona
from heesch_verify.transform import Xform

MODEL_CAP = 3000
COVER_CAP = 20_000


def _setup(name):
    _n, gid, cells, placements = next(f for f in FIXTURES if f[0] == name)
    grid = GRIDS[gid]
    contact = grid.contact("point")
    tile = frozenset(cells)
    corona = check_corona(tile, placements, grid, contact, hole_mode="hc")
    fix = {
        "name": name, "grid": grid, "contact": contact, "tile": tile,
        "patch": corona.patch_cells, "k": corona.max_level,
        "patch_placements": list(placements),
    }
    enc = encode(tile, corona.patch_cells, grid, contact)
    return fix, enc


def _placement_to_xform(p, grid):
    sym = grid.orientations[p.symmetry_index]
    return Xform(sym.a, sym.b, sym.c0 + p.tx, sym.d, sym.e, sym.f0 + p.ty)


def _oracle_accepts(fix, chosen) -> bool:
    placements = list(fix["patch_placements"])
    for p in chosen:
        placements.append((fix["k"] + 1, _placement_to_xform(p, fix["grid"])))
    try:
        check_corona(fix["tile"], placements, fix["grid"], fix["contact"],
                     hole_mode="hh")
        return True
    except Exception:
        return False


def _dup_groups(fix, enc):
    """cellset -> ascending var list (vars of placements covering identical
    cells)."""
    groups = {}
    for var, p in enumerate(enc.formula.universe, start=1):
        cs = materialize(p, fix["tile"], fix["grid"])
        groups.setdefault(cs, []).append(var)
    return groups


@pytest.mark.parametrize("name", [f[0] for f in FIXTURES])
def test_e3_models_decode_to_legal_coronas(name):
    fix, enc = _setup(name)
    if any(len(c) == 0 for c in enc.formula.clauses):
        # A real empty clause (§4.3: an R-cell no copy reaches) means
        # trivially UNSAT — zero models, E3 holds vacuously. pysat cannot
        # bootstrap an empty clause, so short-circuit.
        return
    n_x = len(enc.formula.universe)
    checked = 0
    with Solver(name="cadical195",
                bootstrap_with=[list(c) for c in enc.formula.clauses]) as s:
        for i, model in enumerate(s.enum_models()):
            if i >= MODEL_CAP:
                break
            chosen = [enc.formula.universe[v - 1]
                      for v in range(1, n_x + 1) if model[v - 1] > 0]
            assert _oracle_accepts(fix, chosen), (
                f"{name}: SAT model with {len(chosen)} placements rejected by "
                "the geometry oracle — over-permissive encoder"
            )
            checked += 1
    # Fixtures where no corona exists at all are legitimate (deep concavity):
    # zero models is a valid outcome; the E4 side confirms zero covers too.


@pytest.mark.parametrize("name", [f[0] for f in FIXTURES])
def test_e4_and_geometric_cross_count(name):
    fix, enc = _setup(name)
    grid = fix["grid"]
    groups = _dup_groups(fix, enc)

    # --- geometric brute force over the deduped universe ---
    canon = {cs: vars_[0] for cs, vars_ in groups.items()}
    cellsets = list(canon.keys())
    R = list(enc.formula.required_cells)
    cover_of = {c: [cs for cs in cellsets if c in cs] for c in R}
    covers = set()
    cap_hit = []

    def rec(uncovered, chosen, chosen_cells):
        if len(covers) > COVER_CAP:
            cap_hit.append(True)
            return
        if not uncovered:
            covers.add(frozenset(chosen))
            return
        c = min(uncovered, key=lambda cc: (len(cover_of[cc]), cc[1], cc[0]))
        for cs in cover_of[c]:
            if cs & chosen_cells:
                continue
            rec(uncovered - cs, chosen + [cs], chosen_cells | cs)

    rec(frozenset(R), [], frozenset())
    if cap_hit:
        pytest.skip(f"{name}: geometric cover count exceeds cap")

    var_by_placement = {p: i + 1 for i, p in enumerate(enc.formula.universe)}
    placement_by_var = {v: p for p, v in var_by_placement.items()}

    # --- E4: every oracle-legal geometric cover satisfies F ---
    legal = set()
    for cover in covers:
        chosen_p = [placement_by_var[canon[cs]] for cs in cover]
        if not _oracle_accepts(fix, chosen_p):
            continue
        legal.add(cover)
        n_x = len(enc.formula.universe)
        assign = {v: False for v in range(1, n_x + 1)}
        for cs in cover:
            assign[canon[cs]] = True
        for g in enc.formula.amo_groups:
            if g.kind == "sequential":
                assign.update(
                    aux_assignment(list(g.variables), g.aux_start, g.aux_count, assign)
                )
        for cl in enc.formula.clauses:
            assert any((l > 0) == assign.get(abs(l), False) for l in cl), (
                f"{name}: legal corona violates clause {cl} — over-restrictive "
                "encoder (the false-record direction)"
            )

    # In the hole-allowed formula every exact cover IS legal (disjoint +
    # coverage are the only constraints); assert that equivalence too.
    assert legal == covers, (
        f"{name}: {len(covers) - len(legal)} exact covers rejected by oracle — "
        "formula and geometry disagree on legality"
    )

    # --- geometric cross-count via assumption-collapsed model enumeration ---
    if any(len(c) == 0 for c in enc.formula.clauses):
        # Empty clause: UNSAT by construction. The brute force must agree.
        assert covers == set(), f"{name}: covers exist despite empty clause"
        return
    assumptions = [-v for vars_ in groups.values() for v in vars_[1:]]
    model_covers = set()
    exhausted = True
    n_x = len(enc.formula.universe)
    with Solver(name="cadical195",
                bootstrap_with=[list(c) for c in enc.formula.clauses]) as s:
        for i, model in enumerate(s.enum_models(assumptions=assumptions)):
            if i >= MODEL_CAP:
                exhausted = False
                break
            chosen = frozenset(
                materialize(placement_by_var[v], fix["tile"], grid)
                for v in range(1, n_x + 1)
                if model[v - 1] > 0
            )
            model_covers.add(chosen)
    if exhausted:
        assert model_covers == covers, (
            f"{name}: collapsed models ({len(model_covers)}) != geometric "
            f"covers ({len(covers)})"
        )
