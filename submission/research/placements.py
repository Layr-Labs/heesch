"""Enumerate the congruent poses used by the initial greedy packing."""
from dataclasses import dataclass
from heesch_verify.transform import Xform

@dataclass
class Placement:
    cells: frozenset
    xf: Xform


def enumerate_tiles(shape, grid, patch, required):
    placements = {}
    for sym in grid.orientations:
        oriented = frozenset(sym.apply(cell) for cell in shape)
        translations = {(rx - x, ry - y) for rx, ry in required for x, y in oriented}
        for dx, dy in sorted(translations):
            cells = frozenset((x + dx, y + dy) for x, y in oriented)
            if not cells & patch:
                placements.setdefault(cells, Xform(sym.a, sym.b, dx + sym.c0,
                                                   sym.d, sym.e, dy + sym.f0))
    return [Placement(c, xf) for c, xf in placements.items()]


