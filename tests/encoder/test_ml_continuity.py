"""§9.6 continuity: F_v2(S, 1) and F_v1(S, P_0) are logically equivalent —
same universe object, same SAT/UNSAT verdict on every corpus shape. Bytes
differ BY DESIGN (v2 emits family 1 first per its spec §6; v1 emits AMO
first) — do not "harmonize" either: v1 is frozen, v2's order is its spec."""

import pathlib

import pytest

pysat_solvers = pytest.importorskip("pysat.solvers")
Solver = pysat_solvers.Solver

from conftest import ROOT

from heesch_encoder.api import encode
from heesch_encoder.multilevel.api import encode_multilevel
from heesch_encoder.placements import enumerate_universe
from heesch_verify.grids import GRIDS
from heesch_verify.parse import parse_submission

CORPUS = pathlib.Path(ROOT) / "tests" / "corpus"


def _shapes():
    out = [
        ("mono", "O", [(0, 0)]),
        ("domino", "O", [(0, 0), (1, 0)]),
        ("slotblock", "O",
         [(x, y) for x in range(5) for y in range(3) if (x, y) not in ((2, 1), (2, 2))]),
        ("hex1", "H", [(0, 0)]),
        ("iam2", "I", [(0, 0), (1, 1)]),
    ]
    for p in sorted(CORPUS.glob("*nontiler*.txt")):
        sub = parse_submission(p.read_text(encoding="ascii"))
        out.append((p.stem, sub.grid_id, list(sub.cells)))
    return out


def _verdict(clauses, nvars):
    if any(len(c) == 0 for c in clauses):
        return "UNSAT"
    with Solver(name="cadical195", bootstrap_with=[list(c) for c in clauses]) as s:
        return "SAT" if s.solve() else "UNSAT"


@pytest.mark.parametrize("name,gid,cells", _shapes(),
                         ids=[s[0] for s in _shapes()])
def test_v2_at_m1_equivalent_to_v1(name, gid, cells):
    grid = GRIDS[gid]
    contact = grid.contact("point")
    tile = frozenset(cells)

    # Object-level lemma: the level-1 universe IS the v1 universe.
    v1_universe = enumerate_universe(tile, tile, grid, contact)
    v2 = encode_multilevel(tile, grid, contact, 1)
    assert list(v2.formula.levels[0]) == v1_universe

    v1 = encode(tile, tile, grid, contact)
    assert _verdict(v1.formula.clauses, v1.num_vars) == _verdict(
        v2.formula.clauses, v2.num_vars
    ), f"{name}: v1 and v2(m=1) disagree on satisfiability"
