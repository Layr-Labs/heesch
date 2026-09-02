"""Census-gate regression (external comparative audit, 2026-08-16).

The audit ran the gate over every free polyform at the first size beyond the
old known-tiler tables and found 89 nine-omino / 37 seven-hex / 79 ten-iamond
tilers escaping as INCONCLUSIVE — shapes that then scored. The census layer
(Kaplan 2022's complete non-tiler lists, heesch_verify/known_nontilers.json)
now decides every hole-free polyomino n <= 10, polyhex n <= 8 and polyiamond
n <= 12 exactly, so these tests pin:

  * zero misses at every in-census size (the audit's exact experiment);
  * every listed non-tiler -> NON_TILER with the published Hc/Hh;
  * the table's per-size counts equal Kaplan's published counts;
  * the constructive criteria never call a census non-tiler TILER — the
    strongest soundness check available for the boundary-word layer, run
    over all 3 943 published non-tilers rather than the ~50-shape corpus.

The enumerator is tools/polyforms.free_polyforms (one implementation shared
with the generator).
"""

import functools
import importlib.util
import json

import pytest

from util import ROOT

from heesch_verify import GRIDS
from heesch_verify.canonical import canonical_digest
from heesch_verify.gates import IsohedralGate, Verdict
from heesch_verify.shape import holes_of

_spec = importlib.util.spec_from_file_location("polyforms", ROOT / "tools" / "polyforms.py")
polyforms = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(polyforms)

TABLE = json.loads((ROOT / "heesch_verify" / "known_nontilers.json").read_text())


@functools.lru_cache(maxsize=None)
def _forms(gid, n):
    return tuple(polyforms.free_polyforms(gid, n))

# Kaplan 2022 published non-tiler counts per (grid, n); 0 where no list exists.
PUBLISHED = {
    ("O", 7): 3, ("O", 8): 20, ("O", 9): 198, ("O", 10): 1390,
    ("H", 6): 4, ("H", 7): 37, ("H", 8): 381,
    ("I", 7): 1, ("I", 9): 20, ("I", 10): 103, ("I", 11): 594, ("I", 12): 1192,
}
# The audit's exact experiment sizes (first size beyond the old tables) plus
# the census bounds.
SIZES = [("O", 9), ("O", 10), ("H", 7), ("H", 8), ("I", 10), ("I", 11), ("I", 12)]


def test_bounds_and_table_shape():
    assert TABLE["bounds"] == {"O": 10, "H": 8, "I": 12}
    for gid in ("O", "H", "I"):
        assert len(TABLE[gid]) == sum(v for (g, n), v in PUBLISHED.items() if g == gid)
        for d, v in TABLE[gid].items():
            assert len(d) == 64 and len(v) == 2 and v[0] <= v[1] <= v[0] + 1


@pytest.mark.parametrize("gid,n", SIZES)
def test_census_decides_every_shape_and_misses_nothing(gid, n):
    grid = GRIDS[gid]
    gate = IsohedralGate(grid)
    forms = _forms(gid, n)
    assert len(forms) == polyforms.FREE_COUNTS[gid][n]
    listed = 0
    tilers = 0
    holed = 0
    for cells in forms:
        tile = frozenset(cells)
        if holes_of(tile, grid):
            holed += 1
            continue
        v = gate.evaluate(tile)
        d = canonical_digest(cells, grid, True)
        if d in TABLE[gid]:
            listed += 1
            assert v.verdict is Verdict.NON_TILER and v.detail == "nontiler:census"
            assert [v.census_hc, v.census_hh] == TABLE[gid][d]
        else:
            tilers += 1
            # The audit's "gate misses" column: must be zero at every size.
            assert v.verdict is Verdict.TILER, f"{gid}{n} tiler missed: {sorted(cells)}"
            assert v.detail == "tiler:census"
    assert listed == PUBLISHED.get((gid, n), 0)
    assert listed + tilers + holed == len(forms)


@pytest.mark.parametrize("gid,n", SIZES)
def test_criteria_never_call_a_census_nontiler_tiler(gid, n, monkeypatch):
    """Soundness of the constructive layer (boundary-word factorizations,
    periodic search) against the complete published non-tiler lists. The
    periodic search is budget-bounded per shape here (its verdicts are
    re-verified partitions, so soundness does not depend on the budget);
    tests/test_periodic.py runs the full budget on a sample."""
    import heesch_verify.periodic as periodic
    monkeypatch.setattr(periodic, "DEFAULT_BUDGET", 60_000)
    grid = GRIDS[gid]
    gate = IsohedralGate(grid)
    for cells in _forms(gid, n):
        d = canonical_digest(cells, grid, True)
        if d not in TABLE[gid]:
            continue
        v = gate.evaluate(frozenset(cells), use_census=False)
        assert v.verdict is not Verdict.TILER, (
            f"FALSE TILER ({v.detail}) on census non-tiler {gid}{n} {sorted(cells)}"
        )


def test_audit_examples_are_now_tilers():
    # The three concrete tilers the audit reported as missed
    # (evaluated:no_factorization) — now decided by the census.
    cases = {
        "O": [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6), (1, 0), (1, 3)],
        "H": [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (1, 0), (1, 3)],
        "I": [(0, 0), (0, 3), (0, 6), (0, 9), (1, 1), (1, 4), (1, 7), (1, 10), (3, 9), (4, 7)],
    }
    for gid, cells in cases.items():
        v = IsohedralGate(GRIDS[gid]).evaluate(frozenset(cells))
        assert (v.verdict, v.detail) == (Verdict.TILER, "tiler:census")
