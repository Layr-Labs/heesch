"""Corona reconstruction and the Stage 5 checks — the mathematical core.

`check_corona` is deliberately standalone (no parsing, no gates, no scoring):
it is the oracle for the encoder's round-trip suites (spec §13.6) and the
function agents call in their inner search loop via witness.py.

Every function here takes the threaded `contact` relation as an explicit
parameter (spec §11.1). No module-level defaults, no local adjacency.
"""

from __future__ import annotations

from dataclasses import dataclass

from .grids import Cell, Contact, Grid
from .result import ErrorCode, VerifyError
from .shape import holes_of
from .transform import Xform

MAX_LEVELS = 64  # resource bound, far above the corona search cap of 12
# Audit V4: MAX_LEVELS alone bounds depth but not total work — a deep patch of
# large per-level coronas (nested translation rings) runs stages 5c/5d ~L times
# over the whole accumulated patch, ~380 s for a valid 64-level 196-cell
# witness. This budget caps the cumulative cells-times-levels those loops touch
# (contact_neighbors in 5c, the flood fill in 5d), bringing that worst case
# down to ~15 s — a >20x cut, well within CI budgets. The ceiling is set for
# benchmark integrity, not tightness: a maximal hole-free hc=12 witness (the
# corona search cap) of a 200-cell tile is ~1.2M, and even an unprecedented
# hc~30 witness (the class record is 4) stays under this, so a genuine
# discovery is never rejected. Only deep or ring-inflated abuse patches reach
# it. It is a resource bound, not a frozen convention, so no revision bump is
# needed (lowering MAX_LEVELS toward 12 is the deferred revision-2 change).
# Applied only on the participant path (witness.py); the encoder oracle passes
# max_work=None so its large round-trip patches are unaffected.
MAX_CORONA_WORK = 8_000_000


def contact_neighbors(cells, contact: Contact) -> frozenset:
    """All cells in contact with the set, excluding the set itself."""
    out = set()
    for c in cells:
        out.update(contact.neighbors(c))
    out.difference_update(cells)
    return frozenset(out)


def required_set(patch_cells, contact: Contact) -> frozenset:
    """R = contact_neighbors(P_k) \\ P_k — the cells a complete corona must
    fill (§9.2.1, encoder spec §4.3). Same function both sides use (E5)."""
    return contact_neighbors(patch_cells, contact)


def touches(a, b, contact: Contact) -> bool:
    """Do cell sets a and b share a contact (without sharing a cell)?"""
    small, big = (a, b) if len(a) <= len(b) else (b, a)
    for c in small:
        for n in contact.neighbors(c):
            if n in big:
                return True
    return False


def enclosed_cells(patch_cells, grid: Grid) -> frozenset:
    """Cells enclosed by the patch (not reachable from infinity). The band a
    corona-(k+1) tile may occupy is the complement of the patch and this set;
    the defect check (§9.2.3) rejects placements entering it as
    DEFECT_TILE_OUT_OF_BAND. Same flood fill as Stage 2 and 5d."""
    return holes_of(patch_cells, grid)


@dataclass(frozen=True)
class CoronaResult:
    levels: tuple[int, ...]            # recomputed level per placement
    max_level: int                     # L: number of complete coronas
    tile_cells: tuple[frozenset, ...]  # materialized cells per placement
    level_cells: dict                  # level -> frozenset of cells
    patch_cells: frozenset             # union of all levels
    has_outer_holes: bool              # P_L encloses empty cells


def materialize(shape_cells, placements) -> tuple[frozenset, ...]:
    return tuple(xf.apply_all(shape_cells) for _lvl, xf in placements)


HOLE_MODES = ("hc", "hh", "none")


def check_corona(shape_cells, placements, grid: Grid, contact: Contact,
                 *, hole_mode: str,
                 max_levels: int = MAX_LEVELS,
                 max_work: int | None = None) -> CoronaResult:
    """Stages 5a–5d on one patch. `placements` is a sequence of
    (submitted_level, Xform); transforms are assumed already
    symmetry-checked (Stage 4 runs in witness.py).

    hole_mode governs Stage 5d only (5a–5c always run):
      "hc"   — every accumulated patch P_i must be hole-free;
      "hh"   — inner patches hole-free, outermost may enclose holes;
      "none" — the hole-agnostic oracle (multilevel encoder spec §9.1):
               no hole check ever raises; has_outer_holes reports the
               full-patch flood fill.
    """
    if hole_mode not in HOLE_MODES:
        raise ValueError(f"hole_mode must be one of {HOLE_MODES}, got {hole_mode!r}")

    # Central tile: exactly one level-0 placement.
    centrals = [i for i, (lvl, _xf) in enumerate(placements) if lvl == 0]
    if not centrals:
        raise VerifyError(ErrorCode.PATCH_NO_CENTRAL_TILE, "no level-0 placement")
    if len(centrals) > 1:
        raise VerifyError(
            ErrorCode.PATCH_MULTIPLE_CENTRAL,
            f"placements {centrals} all claim level 0",
        )
    central = centrals[0]

    tile_cells = materialize(shape_cells, placements)

    # 5a — disjointness, first collision names both placements.
    owner: dict[Cell, int] = {}
    for j, cells in enumerate(tile_cells):
        for c in cells:
            other = owner.get(c)
            if other is not None:
                raise VerifyError(
                    ErrorCode.PATCH_OVERLAP,
                    f"cell {c} occupied by placements {other} and {j}",
                    (c,),
                )
            owner[c] = j

    # 5b — recompute corona levels; never trust the submitted labels.
    n = len(placements)
    level = {central: 0}
    # A tile touches the growing patch iff its closed contact neighborhood
    # intersects cells added in a previous round.
    closed_nbhd = []
    for cells in tile_cells:
        nb = set(cells)
        for c in cells:
            nb.update(contact.neighbors(c))
        closed_nbhd.append(nb)

    pending = set(range(n)) - {central}
    new_cells = set(tile_cells[central])
    cur = 0
    while pending:
        cur += 1
        if cur > max_levels:
            raise VerifyError(
                ErrorCode.RESOURCE_EXCEEDED, f"more than {max_levels} corona levels"
            )
        newly = [j for j in pending if closed_nbhd[j] & new_cells]
        if not newly:
            break
        new_cells = set()
        for j in newly:
            level[j] = cur
            pending.discard(j)
            new_cells.update(tile_cells[j])

    if pending:
        j = min(pending)
        raise VerifyError(
            ErrorCode.PATCH_ORPHAN_TILE,
            f"placement {j} is disconnected from the patch",
        )

    for j, (submitted, _xf) in enumerate(placements):
        if submitted != level[j]:
            raise VerifyError(
                ErrorCode.PATCH_LEVEL_MISMATCH,
                f"placement {j} labelled level {submitted}, recomputed level {level[j]}",
            )

    max_level = max(level.values())
    level_cells: dict[int, frozenset] = {}
    for j, lvl in level.items():
        level_cells.setdefault(lvl, set())
    tmp: dict[int, set] = {lvl: set() for lvl in level_cells}
    for j, lvl in level.items():
        tmp[lvl].update(tile_cells[j])
    level_cells = {lvl: frozenset(s) for lvl, s in tmp.items()}

    # 5c — surround condition, the check that actually matters.
    # `work` accumulates the cells-times-levels the per-level passes touch
    # (audit V4); both 5c and 5d rescan the growing patch each level.
    work = 0
    inner = set(level_cells[0])
    for i in range(1, max_level + 1):
        work += len(inner)
        if max_work is not None and work > max_work:
            raise VerifyError(
                ErrorCode.RESOURCE_EXCEEDED,
                f"corona work budget exceeded at level {i} ({work} > {max_work})",
            )
        gap = contact_neighbors(inner, contact) - level_cells[i]
        if gap:
            sample = tuple(sorted(gap))[:5]
            raise VerifyError(
                ErrorCode.PATCH_GAP, f"gap at corona {i}: {sample}", sample
            )
        inner.update(level_cells[i])

    # 5d — hole condition, governed by hole_mode.
    has_outer_holes = False
    acc = set(level_cells[0])
    if hole_mode == "none":
        # Hole-agnostic: one flood fill over the full patch, never raises.
        for i in range(1, max_level + 1):
            acc.update(level_cells[i])
        has_outer_holes = bool(holes_of(frozenset(acc), grid))
    else:
        for i in range(1, max_level + 1):
            work += len(acc)
            if max_work is not None and work > max_work:
                raise VerifyError(
                    ErrorCode.RESOURCE_EXCEEDED,
                    f"corona work budget exceeded at level {i} ({work} > {max_work})",
                )
            acc.update(level_cells[i])
            hs = holes_of(frozenset(acc), grid)
            if hs:
                if i < max_level or hole_mode == "hc":
                    sample = tuple(sorted(hs))[:5]
                    raise VerifyError(
                        ErrorCode.PATCH_HOLE_IN_CORONA,
                        f"patch through corona {i} encloses empty cells, e.g. {sample}",
                        sample,
                    )
                has_outer_holes = True

    return CoronaResult(
        levels=tuple(level[j] for j in range(n)),
        max_level=max_level,
        tile_cells=tile_cells,
        level_cells=level_cells,
        patch_cells=frozenset(acc),
        has_outer_holes=has_outer_holes,
    )
