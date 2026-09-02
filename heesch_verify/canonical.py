"""Canonical form and duplicate-detection digest (spec §7 Stage 3).

Two submissions of the same shape under different rotations/translations
(and reflections, when allowed) must produce the same digest.
"""

from __future__ import annotations

import hashlib

from .grids import Grid


def canonical_form(cells, grid: Grid, allow_reflections: bool) -> tuple:
    best = None
    for sym in grid.orientations:
        if not allow_reflections and sym.det < 0:
            continue
        key = grid.normalize([sym.apply(c) for c in cells])
        if best is None or key < best:
            best = key
    return best


def canonical_digest(cells, grid: Grid, allow_reflections: bool) -> str:
    form = canonical_form(cells, grid, allow_reflections)
    payload = grid.grid_id + repr(form)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def symmetry_order(cells, grid: Grid, allow_reflections: bool) -> int:
    """Number of allowed point-group elements fixing the shape (§9 field)."""
    base = grid.normalize(list(cells))
    count = 0
    for sym in grid.orientations:
        if not allow_reflections and sym.det < 0:
            continue
        if grid.normalize([sym.apply(c) for c in cells]) == base:
            count += 1
    return count
