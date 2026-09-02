"""Periodic-tiling search (heesch_verify/periodic.py): a constructive TILER
layer for shapes the boundary-word criteria miss. Verdicts are re-verified
torus partitions, so a hit is a proof; the tests pin catch rate on the
audit's examples, zero false TILERs on census non-tilers at full budget,
determinism, and the budget bound."""

import time

import pytest

from util import ROOT  # noqa: F401

from heesch_verify import GRIDS, periodic
from heesch_verify.gates import IsohedralGate, Verdict

# Tilers the boundary-word criteria miss (audit 2026-08-16 examples and the
# three that need K = 8), all decided by the census in production; here the
# census is bypassed to exercise the search itself.
MISSED_BY_CRITERIA = [
    ("O", [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6), (1, 0), (1, 3)]),
    ("H", [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (1, 0), (1, 3)]),
    ("I", [(0, 0), (0, 3), (0, 6), (0, 9), (1, 1), (1, 4), (1, 7), (1, 10), (3, 9), (4, 7)]),
    ("O", [(0, 0), (0, 1), (1, 1), (1, 3), (1, 4), (1, 5), (2, 1), (2, 2), (2, 3)]),
    ("I", [(0, 0), (0, 3), (1, 1), (1, 4), (3, 3), (4, 4), (6, 3), (7, 1), (7, 4), (9, 0)]),
    ("I", [(0, 3), (1, 1), (1, 4), (1, 7), (3, 3), (3, 6), (4, 1), (4, 4), (6, 3), (7, 4)]),
]


@pytest.mark.parametrize("gid,cells", MISSED_BY_CRITERIA)
def test_finds_periodic_tilings_the_criteria_miss(gid, cells):
    v = IsohedralGate(GRIDS[gid]).evaluate(frozenset(cells), use_census=False)
    assert v.verdict is Verdict.TILER
    assert v.detail.startswith("tiler:periodic:K=")


def _corpus_cells(name):
    line = (ROOT / "tests" / "corpus" / f"{name}.txt").read_text().splitlines()[0]
    toks = line.split()[1:]
    return frozenset(zip(map(int, toks[0::2]), map(int, toks[1::2])))


@pytest.mark.parametrize("name", [
    "omino7-nontiler-0-hc1hh1", "omino7-nontiler-1-hc1hh1", "omino7-nontiler-2-hc0hh1",
    "omino8-nontiler-0-hc0hh1", "omino8-nontiler-5-hc1hh1", "omino8-nontiler-13-hc1hh2",
    "hex6-nontiler-0-hc1hh1", "hex6-nontiler-1-hc1hh1", "hex6-nontiler-2-hc1hh1",
    "iamond7-nontiler-0-hc1hh1", "iamond9-nontiler-0-hc0hh0", "iamond9-nontiler-10-hc1hh1",
])
def test_no_periodic_tiling_for_nontilers_at_full_budget(name):
    gid = {"o": "O", "h": "H", "i": "I"}[name[0]]
    assert periodic.find_periodic_tiling(_corpus_cells(name), GRIDS[gid]) is None


def test_trivial_tilers_and_lattice_forms():
    assert periodic.find_periodic_tiling(frozenset({(0, 0)}), GRIDS["O"]) == "K=1;lattice=(1,0,1)"
    # 2x2 square: K=1, lattice (2,0,2)
    assert periodic.find_periodic_tiling(frozenset({(0, 0), (1, 0), (0, 1), (1, 1)}), GRIDS["O"]).startswith("K=1")
    assert set(periodic._lattices(4)) == {(1, 0, 4), (2, 0, 2), (2, 1, 2), (4, 0, 1), (4, 1, 1), (4, 2, 1), (4, 3, 1)}


def test_deterministic_and_bounded():
    cells = frozenset([(0, 0), (0, 1), (1, 1), (1, 3), (1, 4), (1, 5), (2, 1), (2, 2), (2, 3)])
    a = periodic.find_periodic_tiling(cells, GRIDS["O"])
    b = periodic.find_periodic_tiling(cells, GRIDS["O"])
    assert a == b
    # A tiny budget gives up (INCONCLUSIVE), never raises, and quickly.
    t = time.time()
    assert periodic.find_periodic_tiling(cells, GRIDS["O"], budget=10) is None
    assert time.time() - t < 1.0
    # A 200-cell shape at the default budget returns promptly either way.
    big = frozenset((x, y) for x in range(20) for y in range(10))
    t = time.time()
    assert periodic.find_periodic_tiling(big, GRIDS["O"]) is not None
    assert time.time() - t < 30.0


@pytest.mark.parametrize("gid,n,fname", [("O", 9, "09omino_0up.txt"), ("H", 7, "07hex_0up.txt"),
                                          ("I", 10, "10iamond_0up.txt")])
def test_constructive_layer_catches_every_tiler_at_audit_sizes(gid, n, fname):
    """The audit's experiment with the census bypassed: the boundary-word
    criteria plus the periodic search must catch EVERY tiler at the first
    size beyond the old tables (89 / 37 / 79 were missed before). Uses
    Kaplan's list from the census table to know which shapes are tilers;
    the listed non-tilers are covered by test_census_gate.py (low budget,
    all sizes) and test_no_periodic_tiling_for_nontilers_at_full_budget."""
    import importlib.util
    import json

    spec = importlib.util.spec_from_file_location("polyforms", ROOT / "tools" / "polyforms.py")
    polyforms = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(polyforms)
    from heesch_verify.canonical import canonical_digest
    from heesch_verify.shape import holes_of

    table = json.loads((ROOT / "heesch_verify" / "known_nontilers.json").read_text())[gid]
    grid = GRIDS[gid]
    gate = IsohedralGate(grid)
    missed = []
    for cells in polyforms.free_polyforms(gid, n):
        tile = frozenset(cells)
        if holes_of(tile, grid):
            continue
        if canonical_digest(cells, grid, True) in table:
            continue
        v = gate.evaluate(tile, use_census=False)
        if v.verdict is not Verdict.TILER:
            missed.append(sorted(cells))
    assert not missed, f"{len(missed)} tilers missed at {gid}{n}: {missed[:3]}"
