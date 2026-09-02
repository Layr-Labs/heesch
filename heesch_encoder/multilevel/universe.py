"""Per-level placement universes by reachability BFS (v2 spec §4.2).

Obligation M1: U_l contains every placement occurring at level l in ANY weak
configuration. The induction: a level-1 copy touches S and avoids it (the v1
universe predicate with P_0 = S); a level-l copy touches some level-(l-1)
copy — whose cellset is in the previous frontier by induction — avoids S and
cannot touch it (W3). Enumerating candidates from the previous level's
cellsets therefore visits every legal placement.

Emission-path module: sorted containers only; sets/dicts are membership and
caching structures, never iterated into output. The BFS is a level-
synchronous loop — no recursion.
"""

from __future__ import annotations

from dataclasses import dataclass

from heesch_verify.grids import Contact, Grid
from heesch_verify.patch import contact_neighbors, touches

from ..ordering import cell_key, placement_key, sorted_cells, sorted_placements
from ..placements import enumerate_universe, materialize
from ..types import Placement



def _check_deadline(deadline) -> None:
    """Portable encode guard (audit 2026-08-19 Medium 5 follow-up): the
    SIGALRM guard in proofcheck.guard is a no-op off POSIX main threads, so
    the encoder also checks a monotonic deadline between levels / clause
    batches and raises the same EncodeTimeout."""
    if deadline is not None:
        import time

        if time.monotonic() > deadline:
            from ..proofcheck.guard import EncodeTimeout

            raise EncodeTimeout()

def cellset_key(cs) -> tuple:
    """Canonical order for a cell set: the sorted cell tuple."""
    return tuple(sorted_cells(cs))  # ordered-ok: sorted


def placements_of_cellset(cs: frozenset, tile_cells, grid: Grid) -> list[Placement]:
    """All symmetry-indexed representatives producing exactly this cell set,
    in placement_key order (§4.2 re-expansion). Anchoring: a pure translation
    preserves cell_key order, so matching the cell_key-minimal cells of the
    oriented tile image and of cs determines the unique candidate t per
    orientation."""
    target_anchor = min(cs, key=cell_key)
    out = []
    for si, sym in enumerate(grid.orientations):
        img = [sym.apply(c) for c in tile_cells]
        a = min(img, key=cell_key)
        tx, ty = target_anchor[0] - a[0], target_anchor[1] - a[1]
        if not grid.translation_legal(tx, ty):
            continue
        if frozenset((x + tx, y + ty) for x, y in img) == cs:
            out.append(Placement(si, ty, tx))
    return sorted_placements(out)


@dataclass(frozen=True)
class MLUniverse:
    m: int
    levels: tuple                 # tuple[tuple[Placement, ...], ...], 1-indexed by position
    level_cellsets: tuple         # per level: tuple of frozensets in cellset_key order
    cells_of: dict                # Placement -> frozenset, cache shared with clauses.py


def multilevel_universe(tile_cells, grid: Grid, contact: Contact, m: int,
                        deadline: float | None = None) -> MLUniverse:
    if m < 1:
        raise ValueError("m must be >= 1")
    tile = frozenset(tile_cells)
    cells_of: dict = {}

    # U_1: the v1 universe with P_0 = S — literally the same predicate.
    u1 = enumerate_universe(tile, tile, grid, contact)
    for p in u1:
        cells_of[p] = materialize(p, tile, grid)

    levels = [tuple(u1)]
    frontier_sets = sorted(
        {cells_of[p] for p in u1}, key=cellset_key
    )  # ordered-ok: sorted
    level_cellsets = [tuple(frontier_sets)]

    tile_imgs = [
        [sym.apply(c) for c in tile] for sym in grid.orientations
    ]

    _REJECTED = object()

    for _l in range(2, m + 1):
        _check_deadline(deadline)
        # Q-independent verdicts are cached; Q-dependent checks (overlap with
        # the generating frontier cellset) must re-run per Q, because a
        # placement overlapping one frontier cellset may legally touch
        # another.
        status: dict = {}          # Placement -> cells | _REJECTED; cache only
        accepted: set = set()      # membership only
        found: list[Placement] = []
        found_sets: set = set()    # membership only
        for Q in frontier_sets:
            targets = sorted_cells(contact_neighbors(Q, contact))
            for si, img in enumerate(tile_imgs):
                for h in targets:
                    for (cx, cy) in img:
                        p = Placement(si, h[1] - cy, h[0] - cx)
                        st = status.get(p)
                        if st is None:
                            if not grid.translation_legal(p.tx, p.ty):
                                status[p] = _REJECTED
                                continue
                            cells = cells_of.get(p)
                            if cells is None:
                                cells = materialize(p, tile, grid)
                                cells_of[p] = cells
                            if cells & tile or touches(cells, tile, contact):
                                # overlaps S, or structural W3 vs level 0
                                status[p] = _REJECTED
                                continue
                            status[p] = cells
                            st = cells
                        if st is _REJECTED or p in accepted:
                            continue
                        if st & Q:
                            continue  # not via this frontier cellset
                        # Generation guarantees a cell of p lands in
                        # contact_neighbors(Q); with disjointness that IS
                        # touching. Assert the invariant rather than trust it.
                        assert touches(st, Q, contact)
                        accepted.add(p)
                        found.append(p)
                        found_sets.add(st)
        levels.append(tuple(sorted_placements(found)))
        frontier_sets = sorted(found_sets, key=cellset_key)  # ordered-ok: sorted
        level_cellsets.append(tuple(frontier_sets))

    return MLUniverse(
        m=m,
        levels=tuple(levels),
        level_cellsets=tuple(level_cellsets),
        cells_of=cells_of,
    )


def touching_cellset_pairs(cellsets: list, contact: Contact) -> list[tuple[int, int]]:
    """Index pairs (i, j), i < j, of disjoint touching cell sets — the
    geometric touch graph shared by feasibility counting and clause emission
    (families 4/5/6) so the two can never drift. Deterministic: input order
    defines indices; output sorted."""
    cell_index: dict = {}
    for i, cs in enumerate(cellsets):
        for c in cs:
            cell_index.setdefault(c, []).append(i)
    pairs: set = set()  # membership/dedup only
    for i, cs in enumerate(cellsets):
        for c in cs:
            for n in contact.neighbors(c):
                for j in cell_index.get(n, ()):
                    if j == i:
                        continue
                    a, b = (i, j) if i < j else (j, i)
                    pairs.add((a, b))
    # Touching requires disjointness; overlapping sets sharing a neighbor
    # relation are filtered here.
    out = [
        (a, b) for (a, b) in sorted(pairs)  # ordered-ok: sorted
        if not (cellsets[a] & cellsets[b])
    ]
    return out
