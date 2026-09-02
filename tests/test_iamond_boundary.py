"""V2 real fix (2026-08 audit, archived in Linear): the iamond gate was
structurally absent beyond the n<=9 census table, so every >=10-cell iamond
tiler scored by default. boundary.iamond_boundary_word + the Beauquier-Nivat /
Conway criteria now evaluate every polyiamond.

Soundness is load-bearing: a wrong TILER verdict rejects a legitimate
submission. The decisive test enumerates ALL 112 free polyiamonds n<=8 and
asserts every shape the criteria call TILER is in the exhaustive known-tiler
table — zero false positives.
"""

import json

from util import ROOT  # noqa: F401

from heesch_verify import GRIDS
from heesch_verify import boundary as B
from heesch_verify.canonical import canonical_digest
from heesch_verify.gates import IsohedralGate, Verdict

GRID = GRIDS["I"]
# Kaplan's complete census: every polyiamond n <= 12 that is NOT in this
# table (and is hole-free) is a tiler, so a criterion verdict of TILER on a
# listed shape would be a false TILER.
_NONTILERS = set(
    json.loads((ROOT / "heesch_verify" / "known_nontilers.json").read_text())["I"]
)


def _side_triangle(side):
    cells = []
    for i in range(side):
        for j in range(side - i):
            cells.append((3 * i, 3 * j))          # up
        for j in range(side - i - 1):
            cells.append((3 * i + 1, 3 * j + 1))  # down
    return frozenset(cells)


def _verdict(cells):
    # Criteria only: the census layer would decide every n <= 12 iamond by
    # lookup, which is not what these tests validate.
    return IsohedralGate(GRID).evaluate(cells, use_census=False)


def test_side4_triangle_is_tiler():
    # The exact V2 PoC (16 unit triangles) — must be caught, not scored.
    verdict, detail = _verdict(_side_triangle(4))
    assert verdict is Verdict.TILER
    assert detail.startswith("tiler:")


def test_all_side_triangles_are_tilers():
    for side in range(1, 9):  # up to 64 cells, well past the n<=9 table
        verdict, _ = _verdict(_side_triangle(side))
        assert verdict is Verdict.TILER, f"side-{side} triangle not caught"


def _all_free_iamonds(maxn):
    seen = {}
    frontier = [frozenset({(0, 0)})]
    seen[canonical_digest(frontier[0], GRID, True)] = frontier[0]
    for _ in range(maxn - 1):
        new = []
        for s in frontier:
            for c in list(s):
                for n in GRID.edge_neighbors(c):
                    if n not in s:
                        t = frozenset(s | {n})
                        dg = canonical_digest(t, GRID, True)
                        if dg not in seen:
                            seen[dg] = t
                            new.append(t)
        frontier = frontier + new
    return seen


def test_no_false_tiler_over_full_enumeration():
    shapes = _all_free_iamonds(8)
    assert len(shapes) == 112, f"incomplete enumeration: {len(shapes)} (expect 112)"
    for dg, s in shapes.items():
        verdict, _ = _verdict(s)
        if verdict is Verdict.TILER:
            assert dg not in _NONTILERS, (
                f"FALSE TILER on an n={len(s)} iamond listed as a census non-tiler"
            )


def test_holed_iamond_is_inconclusive_not_crash():
    line = (ROOT / "tests" / "corpus" / "iamond9-holed-1.txt").read_text().splitlines()[0]
    toks = line.split()[1:]
    cells = frozenset(zip(map(int, toks[0::2]), map(int, toks[1::2])))
    verdict, detail = _verdict(cells)
    assert verdict is Verdict.INCONCLUSIVE
    assert detail.startswith(("unchecked:", "evaluated:"))


def test_opposite_direction_is_plus_three():
    # The alphabet invariant the BN/Conway criteria rely on.
    for d, (dx, dy) in enumerate(B._TRI_DIRS):
        ox, oy = B._TRI_DIRS[(d + 3) % 6]
        assert (ox, oy) == (-dx, -dy)
