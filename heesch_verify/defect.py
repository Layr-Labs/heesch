"""Near-corona defect score (spec §9.2). Stdlib only, same tier as witness.py.

Measures how many cells of the next corona's required set a partial corona
FAILS to cover — the inverse of tile-counting, which is what makes it a
gradient (§9.2.1). Fields are computed and recorded on every submission; the
DEFECT_BOARD_ENABLED flag gates whether the fraction enters the scalar
score and the board ordering (score.py §9.2.8) — the fields themselves are
always emitted.

The claim semantics are lower-bound-shaped (§9.2.2): the verifier confirms
"a placement achieving defect <= d exists", never that d is minimal.
"""

from __future__ import annotations

from dataclasses import dataclass

from .grids import Contact, Grid
from .parse import DefectBlock
from .patch import CoronaResult, required_set, touches
from .result import ErrorCode, VerifyError
from .shape import holes_of
from .transform import check_symmetry


@dataclass(frozen=True)
class DefectResult:
    corona_level: int      # k+1
    defect_hc: int         # uncovered cells of R, plus enclosed pockets
    defect_hh: int         # uncovered cells of R only
    required: int          # |R|, shared denominator
    pocket_cells: int      # defect_hc - defect_hh; diagnostic
    partial_tiles: int


def verify_defect(shape_cells, grid: Grid, corona: CoronaResult,
                  block: DefectBlock, contact: Contact,
                  *, allow_reflections: bool = True,
                  patch_cells=None) -> DefectResult:
    """§9.2.3 verbatim. `corona` must already have passed the full Stage 5
    checks; `contact` is the SAME relation object threaded from the grid
    config (§11.1). `patch_cells` overrides corona.patch_cells for callers
    that need a custom P_k (tests exercising the enclosed-band path)."""

    if corona.has_outer_holes and patch_cells is None:
        raise VerifyError(
            ErrorCode.DEFECT_LEVEL_MISMATCH,
            "defect block requires a fully hole-free patch; the outermost corona "
            "of this patch encloses empty cells",
        )
    k = corona.max_level
    if block.level != k + 1:
        raise VerifyError(
            ErrorCode.DEFECT_LEVEL_MISMATCH,
            f"defect block targets corona {block.level}, patch has {k} coronas "
            f"so the partial corona must be level {k + 1}",
        )
    for i, (lvl, _xf) in enumerate(block.tiles):
        if lvl != block.level:
            raise VerifyError(
                ErrorCode.DEFECT_LEVEL_MISMATCH,
                f"defect tile {i} labelled level {lvl}, block is level {block.level}",
            )

    P_k = frozenset(patch_cells) if patch_cells is not None else corona.patch_cells
    R = required_set(P_k, contact)

    # The band a corona-(k+1) tile may occupy: anywhere outside the patch
    # that is not enclosed by it. For a hole-free Hc patch the enclosed set
    # is empty and this check cannot fire; it guards holed patches.
    enclosed = holes_of(P_k, grid)

    covered: set = set()
    for i, (_lvl, xf) in enumerate(block.tiles):
        check_symmetry(xf, grid, allow_reflections, code=ErrorCode.DEFECT_XFORM_INVALID)
        cells = xf.apply_all(shape_cells)
        hit_patch = cells & P_k
        if hit_patch:
            c = min(hit_patch)
            raise VerifyError(
                ErrorCode.DEFECT_TILE_OVERLAP,
                f"defect tile {i} overlaps the patch at {c}",
                (c,),
            )
        hit_prev = cells & covered
        if hit_prev:
            c = min(hit_prev)
            raise VerifyError(
                ErrorCode.DEFECT_TILE_OVERLAP,
                f"defect tile {i} overlaps another partial-corona tile at {c}",
                (c,),
            )
        if not touches(cells, P_k, contact):
            raise VerifyError(
                ErrorCode.DEFECT_TILE_NOT_TOUCHING,
                f"defect tile {i} does not touch the patch — it is not in corona {k + 1}",
            )
        hit_enclosed = cells & enclosed
        if hit_enclosed:
            c = min(hit_enclosed)
            raise VerifyError(
                ErrorCode.DEFECT_TILE_OUT_OF_BAND,
                f"defect tile {i} enters a region enclosed by the patch at {c}",
                (c,),
            )
        covered |= cells

    U = P_k | covered
    uncovered = R - covered
    pockets = holes_of(frozenset(U), grid)

    defect_hh = len(uncovered)
    defect_hc = len(uncovered | pockets)

    # Claims are ceilings the submission must meet; the required-set size is
    # derivable and must match exactly.
    if block.required != len(R):
        raise VerifyError(
            ErrorCode.DEFECT_CLAIM_MISMATCH,
            f"claimed required-set size {block.required}, computed {len(R)}",
        )
    if defect_hh > block.u_hh:
        raise VerifyError(
            ErrorCode.DEFECT_CLAIM_MISMATCH,
            f"claimed defect_hh <= {block.u_hh}, computed {defect_hh}",
        )
    if defect_hc > block.u_hc:
        raise VerifyError(
            ErrorCode.DEFECT_CLAIM_MISMATCH,
            f"claimed defect_hc <= {block.u_hc}, computed {defect_hc}",
        )

    return DefectResult(
        corona_level=k + 1,
        defect_hc=defect_hc,
        defect_hh=defect_hh,
        required=len(R),
        pocket_cells=defect_hc - defect_hh,
        partial_tiles=len(block.tiles),
    )
