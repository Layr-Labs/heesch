"""Placement universe (spec §3) — obligation E1, the one whose failure
produces false records.

Completeness argument (published in the soundness note, tested in §9.3):
a legal corona-(k+1) copy touches P_k and does not overlap it, so under the
frozen contact relation at least one of its cells lies in
R = contact_neighbors(P_k) \\ P_k. Enumerating, for every point-group element
M and every pair (tile cell c, required cell h), the translation t = h - M(c)
therefore visits every legal placement at least once. Filtering with the
membership predicate and deduplicating yields exactly U. No halo-radius
arithmetic is involved, so there is no off-by-one to get wrong.
"""

from __future__ import annotations

from heesch_verify.grids import Contact, Grid
from heesch_verify.patch import required_set, touches

from .ordering import sorted_placements
from .types import Placement


def materialize(p: Placement, tile_cells, grid: Grid) -> frozenset:
    sym = grid.orientations[p.symmetry_index]
    tx, ty = p.tx, p.ty
    return frozenset((x + tx, y + ty) for (x, y) in map(sym.apply, tile_cells))


def in_universe(p: Placement, tile_cells, patch_cells, grid: Grid,
                contact: Contact) -> bool:
    """§3.1 membership, verbatim: disjoint from P_k and touching it.
    `touches` is heesch_verify.patch.touches with the threaded contact —
    obligation E5, no local adjacency."""
    sym = grid.orientations[p.symmetry_index]
    if not grid.translation_legal(p.tx, p.ty):
        return False
    cells = materialize(p, tile_cells, grid)
    if cells & patch_cells:
        return False
    return touches(cells, patch_cells, contact)


def enumerate_universe(tile_cells, patch_cells, grid: Grid,
                       contact: Contact) -> list[Placement]:
    """All legal corona placements on P_k, in §3.3 canonical order."""
    R = required_set(patch_cells, contact)
    tile = tuple(tile_cells)
    seen = set()
    out = []
    for si in range(len(grid.orientations)):
        sym = grid.orientations[si]
        img = [sym.apply(c) for c in tile]
        for (hx, hy) in R:
            for (cx, cy) in img:
                t = (hx - cx, hy - cy)
                p = Placement(si, t[1], t[0])
                if p in seen:
                    continue
                seen.add(p)
                if in_universe(p, tile, patch_cells, grid, contact):
                    out.append(p)
    return sorted_placements(out)
