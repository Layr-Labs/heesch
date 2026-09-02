"""§12.4 differential reference: a deliberately slow, obviously-correct
surround checker, materializing everything with no optimizations. Never
import this from the package."""

from __future__ import annotations


def naive_verdict(shape_cells, placements, grid, contact_mode, hole_mode="hc"):
    """Independently verify a patch. Returns (ok, hc_levels, reason).

    placements: list of (level, Xform). Reimplements the rules directly from
    the definition; shares no code with heesch_verify.patch."""

    def neighbors(cell):
        if contact_mode == "edge":
            return grid.edge_neighbors(cell)
        return grid.point_neighbors(cell)

    tiles = []
    for lvl, xf in placements:
        cells = frozenset(xf.apply(c) for c in shape_cells)
        tiles.append((lvl, cells))

    # exactly one central
    centrals = [i for i, (lvl, _c) in enumerate(tiles) if lvl == 0]
    if len(centrals) != 1:
        return False, 0, "central count"

    # disjoint
    seen = set()
    for _lvl, cells in tiles:
        if seen & cells:
            return False, 0, "overlap"
        seen |= cells

    # levels by definition: level of a tile = 1 + min level of touched tiles
    # below it, computed by iterating to fixpoint from the central tile.
    n = len(tiles)
    level = {centrals[0]: 0}
    changed = True
    while changed:
        changed = False
        for i in range(n):
            if i in level:
                continue
            touched_levels = []
            for j in level:
                a, b = tiles[i][1], tiles[j][1]
                if any(nb in b for c in a for nb in neighbors(c)):
                    touched_levels.append(level[j])
            if touched_levels:
                level[i] = min(touched_levels) + 1
                changed = True
    if len(level) != n:
        return False, 0, "orphan"
    for i, (lbl, _c) in enumerate(tiles):
        if level[i] != lbl:
            return False, 0, "level mismatch"

    L = max(level.values())

    # surround, from the definition: every cell in contact with P_{i-1} is
    # covered by level-i tiles
    for i in range(1, L + 1):
        inner = set()
        for j, lv in level.items():
            if lv < i:
                inner |= tiles[j][1]
        ring = set()
        for c in inner:
            for nb in neighbors(c):
                if nb not in inner:
                    ring.add(nb)
        cover_i = set()
        for j, lv in level.items():
            if lv == i:
                cover_i |= tiles[j][1]
        if not ring <= cover_i:
            return False, 0, f"gap at {i}"

    # holes: brute-force flood fill over a huge padded box
    def has_holes(occ):
        xs = [c[0] for c in occ]
        ys = [c[1] for c in occ]
        pad = 8
        x0, x1 = min(xs) - pad, max(xs) + pad
        y0, y1 = min(ys) - pad, max(ys) + pad
        empty = {
            (x, y)
            for x in range(x0, x1 + 1)
            for y in range(y0, y1 + 1)
            if (x, y) not in occ and grid.cell_valid((x, y))
        }
        if not empty:
            return False
        # flood from all border cells
        frontier = [c for c in empty if c[0] in (x0, x1) or c[1] in (y0, y1)]
        reached = set(frontier)
        while frontier:
            c = frontier.pop()
            for nb in grid.edge_neighbors(c):
                if nb in empty and nb not in reached:
                    reached.add(nb)
                    frontier.append(nb)
        return bool(empty - reached)

    if hole_mode != "none":
        for i in range(1, L + 1):
            occ = set()
            for j, lv in level.items():
                if lv <= i:
                    occ |= tiles[j][1]
            if has_holes(occ):
                if i < L or hole_mode == "hc":
                    return False, 0, f"hole at {i}"

    return True, L, "ok"
