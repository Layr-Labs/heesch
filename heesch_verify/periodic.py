"""Periodic-tiling search (architecture §2.1, Gate 1 constructive layer).

Finds a periodic tiling of the plane by copies of the tile: a translation
lattice L of the grid and K placements (any orientation) that tile the torus
plane/L exactly. Any such cover IS a plane tiling (translate the K copies by
every vector of L), so a hit is a constructive TILER proof — it catches
isohedral AND anisohedral periodic tilers of any size that the boundary-word
factorization criteria miss. A miss proves nothing (INCONCLUSIVE): under the
fail-closed rule (§2.2) this layer only improves the rejection reason
(`GATE_IS_TILER` instead of `GATE_INCONCLUSIVE`); it can never admit a tiler.

Deterministic and bounded: all work — building placement sets and the exact
cover search — is charged to one integer budget, never wall-clock, so the
verdict is reproducible on any host. Search: for K = 1..K_MAX, every
sublattice of index N = K·|S| (cells per lattice unit u = 1 on O/H, 2 on I)
in Hermite normal form {(a,0),(b,c)}, a·c = N, 0 <= b < a; the identity copy
at the origin is forced (any lattice tiling can be moved to contain it, its
lattice becoming another of the enumerated ones); Algorithm-X exact cover of
the remaining torus cells by non-self-overlapping placements. Every found
cover is re-verified as an exact partition of the torus before it is
reported.
"""

from __future__ import annotations

from .grids import Grid, TriGrid

# K_MAX = 8 catches every tiler at the audit's sizes (9-ominoes, 7-hexes,
# 10-iamonds — the three shapes K <= 6 missed need K = 8); the census layer
# decides those sizes anyway, so this is calibration, not coverage.
K_MAX = 8
# Total work units per call (cell-set constructions + search steps). Chosen
# so the gate adds at most ~1 s on the harness path for small shapes and
# gives up quickly on large ones; a resource bound, not a frozen convention.
DEFAULT_BUDGET = 6_000_000


class _Budget(Exception):
    pass


def _lattices(n: int):
    """Hermite normal forms of the index-n sublattices of Z^2: (a, b, c)
    with rows (a, 0), (b, c), a*c = n, 0 <= b < a."""
    out = []
    a = 1
    while a <= n:
        if n % a == 0:
            c = n // a
            for b in range(a):
                out.append((a, b, c))
        a += 1
    return out


def _tile_step(grid: Grid) -> int:
    return 3 if isinstance(grid, TriGrid) else 1


def _reduce_factory(a: int, b: int, c: int, step: int):
    """Map a cell to its canonical representative modulo the lattice
    step·{(a,0),(b,c)} — for the iamond grid the residues mod 3 are kept."""
    if step == 1:
        def red(cell):
            x, y = cell
            k, y = divmod(y, c)
            x = (x - k * b) % a
            return (x, y)
    else:
        def red(cell):
            x, y = cell
            rx, ry = x % step, y % step
            X, Y = (x - rx) // step, (y - ry) // step
            k, Y = divmod(Y, c)
            X = (X - k * b) % a
            return (X * step + rx, Y * step + ry)
    return red


def find_periodic_tiling(cells, grid: Grid, *, k_max: int | None = None,
                         budget: int | None = None) -> str | None:
    """Return a description 'K=<k>;lattice=(a,b,c)' of a verified periodic
    tiling by `cells`, or None (INCONCLUSIVE) — never raises."""
    if k_max is None:
        k_max = K_MAX
    if budget is None:
        budget = DEFAULT_BUDGET
    tile = tuple(sorted(frozenset(cells)))
    n_cells = len(tile)
    if n_cells == 0:
        return None
    step = _tile_step(grid)
    unit = 2 if step == 3 else 1   # cells per lattice unit
    work = [0]

    def charge(units: int):
        work[0] += units
        if work[0] > budget:
            raise _Budget

    images = []
    for sym in grid.orientations:
        images.append(tuple(sym.apply(c) for c in tile))

    try:
        for k in range(1, k_max + 1):
            total = k * n_cells
            if total % unit:
                continue
            n = total // unit
            for (a, b, c) in _lattices(n):
                red = _reduce_factory(a, b, c, step)
                # The identity copy at the origin must embed without
                # self-overlap; its cells are the first block of the cover.
                charge(n_cells)
                base = frozenset(red(x) for x in tile)
                if len(base) != n_cells:
                    continue
                # Torus cells: enumerate representatives.
                torus = set()
                for X in range(a):
                    for Y in range(c):
                        for rx in range(step):
                            cell = (X * step + rx, Y * step + rx)
                            if grid.cell_valid(cell):
                                torus.add(cell)
                if len(torus) != total:
                    continue
                remaining = torus - base
                # Candidate placements: orientation × translation, reduced.
                cand: dict[frozenset, tuple] = {}
                for si, img in enumerate(images):
                    for t in torus:
                        # translation must be lattice-legal
                        tx, ty = t[0] - img[0][0], t[1] - img[0][1]
                        if not grid.translation_legal(tx, ty):
                            continue
                        charge(n_cells)
                        placed = frozenset(red((x + tx, y + ty)) for x, y in img)
                        if len(placed) != n_cells or placed & base:
                            continue
                        if not placed <= remaining:
                            continue
                        cand.setdefault(placed, (si, tx, ty))
                if len(cand) < k - 1:
                    continue
                cover_of: dict = {cell: [] for cell in remaining}
                for placed in cand:
                    for cell in placed:
                        cover_of[cell].append(placed)
                if any(not v for v in cover_of.values()):
                    continue
                for cell in cover_of:
                    cover_of[cell].sort(key=lambda s: sorted(s))
                sol = _exact_cover(remaining, cover_of, charge)
                if sol is None:
                    continue
                # Independent re-verification: exact partition of the torus.
                covered = set(base)
                ok = True
                for placed in sol:
                    if covered & placed:
                        ok = False
                        break
                    covered |= placed
                if ok and covered == torus and len(sol) == k - 1:
                    return f"K={k};lattice=({a},{b},{c})"
    except _Budget:
        return None
    return None


def _exact_cover(remaining: frozenset, cover_of: dict, charge) -> list | None:
    """Algorithm X over cell sets; deterministic branching (fewest candidates,
    ties by cell order)."""
    chosen: list = []
    uncovered = set(remaining)

    def rec():
        charge(len(uncovered) + 1)
        if not uncovered:
            return True
        cell = min(uncovered, key=lambda c: (len([s for s in cover_of[c] if s <= uncovered]), c))
        options = [s for s in cover_of[cell] if s <= uncovered]
        if not options:
            return False
        for s in options:
            uncovered.difference_update(s)
            chosen.append(s)
            if rec():
                return True
            chosen.pop()
            uncovered.update(s)
        return False

    return list(chosen) if rec() else None
