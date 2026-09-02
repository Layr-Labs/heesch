"""Encoder test fixtures: shapes and verified patches across grids.

Each fixture is (name, grid_id, tile_cells, patch_placements) where the
patch is P_k as a list of (level, Xform) already known valid — the geometry
oracle re-verifies before any encoder test uses it."""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from heesch_verify.grids import GRIDS
from heesch_verify.patch import check_corona
from heesch_verify.transform import Xform


def T(dx, dy):
    return Xform(1, 0, dx, 0, 1, dy)


def _mono_p1():
    """Monomino P_1 (3x3 block): encoder target is corona 2."""
    pl = [(0, T(0, 0))]
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if (dx, dy) != (0, 0):
                pl.append((1, T(dx, dy)))
    return pl


FIXTURES = [
    # Elongated shapes stress the universe bound hardest (spec §9.3).
    ("mono-p0", "O", [(0, 0)], [(0, T(0, 0))]),
    ("mono-p1", "O", [(0, 0)], _mono_p1()),
    ("domino-p0", "O", [(0, 0), (1, 0)], [(0, T(0, 0))]),
    ("strip8-p0", "O", [(x, 0) for x in range(8)], [(0, T(0, 0))]),
    ("strip15-p0", "O", [(x, 0) for x in range(15)], [(0, T(0, 0))]),
    ("L-arm-p0", "O", [(x, 0) for x in range(10)] + [(0, y) for y in range(1, 4)],
     [(0, T(0, 0))]),
    ("T-p0", "O", [(0, 0), (1, 0), (2, 0), (1, 1), (1, 2)], [(0, T(0, 0))]),
    # A deep concavity: U with tall arms (its own arm can reach back in —
    # good stress case for the round trips).
    ("deepU-p0", "O",
     [(0, 0), (1, 0), (2, 0)] + [(0, y) for y in range(1, 5)] + [(2, y) for y in range(1, 5)],
     [(0, T(0, 0))]),
    # Slotted block: width-1 depth-2 slot in a chunky rectangle. No copy has
    # a 1-wide length-2 protrusion, so the slot-bottom R-cell is uncoverable
    # and the formula must contain a real empty clause (§4.3).
    ("slotblock-p0", "O",
     [(x, y) for x in range(5) for y in range(3) if (x, y) not in ((2, 1), (2, 2))],
     [(0, T(0, 0))]),
    # Hex fixtures.
    ("hex1-p0", "H", [(0, 0)], [(0, T(0, 0))]),
    ("hexchain5-p0", "H", [(x, 0) for x in range(5)], [(0, T(0, 0))]),
    ("hexprop-p0", "H", [(0, 0), (1, 0), (-1, 1), (0, -1)], [(0, T(0, 0))]),
    # Iamond fixtures (Kaplan x-mod-3 encoding; up cells ≡(0,0), down ≡(1,1) mod 3).
    ("iam2-p0", "I", [(0, 0), (1, 1)], [(0, T(0, 0))]),
    ("iamstrip-p0", "I", [(0, 0), (1, 1), (3, 0), (4, 1), (6, 0), (7, 1)],
     [(0, T(0, 0))]),
]


@pytest.fixture(params=FIXTURES, ids=[f[0] for f in FIXTURES])
def fixture(request):
    name, gid, cells, placements = request.param
    grid = GRIDS[gid]
    contact = grid.contact("point")
    corona = check_corona(frozenset(cells), placements, grid, contact,
                          hole_mode="hc")
    return {
        "name": name,
        "grid": grid,
        "contact": contact,
        "tile": frozenset(cells),
        "patch": corona.patch_cells,
        "corona": corona,
    }
