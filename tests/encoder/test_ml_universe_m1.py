"""v2 obligation M1 (spec §9.2): per-level universe completeness.

Brute-forces each level over an independently-computed metric box (no code
shared with the reachability BFS), with the level-l predicate existential
over the previous BRUTE-FORCED level — inductive licensing, mirroring the M1
proof. Margin-band saturation licenses the finite region per level. One
sorted-list equality per level checks membership, completeness, ordering,
dedup and symmetry re-expansion at once."""

import pytest

from conftest import ROOT  # noqa: F401

from heesch_encoder.multilevel.universe import multilevel_universe
from heesch_encoder.ordering import placement_key
from heesch_encoder.placements import materialize
from heesch_encoder.types import Placement
from heesch_verify.grids import GRIDS
from heesch_verify.patch import touches

MARGIN = 4

ML_M1_FIXTURES = [
    ("mono", "O", [(0, 0)], 3),
    ("domino", "O", [(0, 0), (1, 0)], 3),
    ("T", "O", [(0, 0), (1, 0), (2, 0), (1, 1)], 2),
    ("strip6", "O", [(x, 0) for x in range(6)], 2),
    ("deepU", "O",
     [(0, 0), (1, 0), (2, 0)] + [(0, y) for y in range(1, 4)] + [(2, y) for y in range(1, 4)],
     2),
    ("slotblock", "O",
     [(x, y) for x in range(5) for y in range(3) if (x, y) not in ((2, 1), (2, 2))],
     2),
    ("hex1", "H", [(0, 0)], 3),
    ("hexprop", "H", [(0, 0), (1, 0), (-1, 1), (0, -1)], 2),
    ("iam2", "I", [(0, 0), (1, 1)], 3),
    ("iamstrip", "I", [(0, 0), (1, 1), (3, 0), (4, 1)], 2),
]


def _diameter(cells):
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    return (max(xs) - min(xs)) + (max(ys) - min(ys)) + 1


def _reach(contact, cells):
    c0 = next(iter(cells))
    return max(
        max(abs(n[0] - c0[0]), abs(n[1] - c0[1])) for n in contact.neighbors(c0)
    )


def _brute_level(tile, grid, contact, prev_cellsets, box, band):
    """All placements in `box` satisfying the level predicate over
    prev_cellsets (None = level 1: touch S). Returns (placements, band_hits)."""
    x0, x1, y0, y1 = box
    tile_set = frozenset(tile)
    found = []
    band_hits = []
    for si, sym in enumerate(grid.orientations):
        img = [sym.apply(c) for c in tile]
        bx0 = min(c[0] for c in img)
        bx1 = max(c[0] for c in img)
        by0 = min(c[1] for c in img)
        by1 = max(c[1] for c in img)
        for ty in range(y0 - by0, y1 - by1 + 1):
            for tx in range(x0 - bx0, x1 - bx1 + 1):
                p = Placement(si, ty, tx)
                if not grid.translation_legal(tx, ty):
                    continue
                cells = materialize(p, tile_set, grid)
                if cells & tile_set:
                    continue
                if prev_cellsets is None:
                    if not touches(cells, tile_set, contact):
                        continue
                else:
                    if touches(cells, tile_set, contact):
                        continue
                    if not any(
                        not (cells & q) and touches(cells, q, contact)
                        for q in prev_cellsets
                    ):
                        continue
                found.append(p)
                if any(
                    c[0] < x0 + band or c[0] > x1 - band
                    or c[1] < y0 + band or c[1] > y1 - band
                    for c in cells
                ):
                    band_hits.append(p)
    return found, band_hits


@pytest.mark.parametrize("name,gid,cells,m", ML_M1_FIXTURES,
                         ids=[f[0] for f in ML_M1_FIXTURES])
def test_multilevel_universe_completeness(name, gid, cells, m):
    grid = GRIDS[gid]
    contact = grid.contact("point")
    tile = frozenset(cells)
    uni = multilevel_universe(tile, grid, contact, m)

    D = _diameter(cells)
    reach = _reach(contact, cells)
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]

    prev = None
    for l in range(1, m + 1):
        pad = l * (D + reach) + MARGIN
        box = (min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad)
        brute, band_hits = _brute_level(tile, grid, contact, prev, box, MARGIN)
        assert not band_hits, (
            f"{name} level {l}: {len(band_hits)} predicate-passing placements "
            "reach the margin band — region too small, test unsound"
        )
        shipped = list(uni.levels[l - 1])
        assert sorted(brute, key=placement_key) == shipped, (
            f"{name} level {l}: brute {len(brute)} vs shipped {len(shipped)}"
        )
        assert len(set(shipped)) == len(shipped)
        # Structural W3-vs-level-0 exclusion (spec §4.2).
        if l >= 2:
            for p in shipped:
                assert not touches(uni.cells_of[p], tile, contact), (
                    f"{name} level {l}: {p} touches S"
                )
        prev = {frozenset(materialize(p, tile, grid)) for p in brute}
