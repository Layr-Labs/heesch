"""Shape validity (spec §7 Stage 2) and the single flood-fill implementation.

`holes_of` is the one hole detector in the codebase — Stage 2, Stage 5d and
the defect pocket computation (§9.2.3) all call it. Do not add a second.
Holes are always defined via EDGE adjacency of empty cells, per the spec's
padded-bounding-box flood fill.
"""

from __future__ import annotations

from dataclasses import dataclass

from .grids import Cell, Grid
from .result import ErrorCode, VerifyError


@dataclass(frozen=True)
class ShapeInfo:
    cells: frozenset
    span_x: int
    span_y: int


def connected(cells: frozenset, grid: Grid) -> bool:
    """Edge-connectivity BFS."""
    if not cells:
        return True
    it = iter(cells)
    start = next(it)
    seen = {start}
    stack = [start]
    while stack:
        c = stack.pop()
        for n in grid.edge_neighbors(c):
            if n in cells and n not in seen:
                seen.add(n)
                stack.append(n)
    return len(seen) == len(cells)


def holes_of(occupied: frozenset, grid: Grid) -> frozenset:
    """Empty valid cells enclosed by `occupied`: pad the bounding box, flood
    the complement from the padding ring via edge adjacency, return every
    empty valid cell in the padded box that was not reached."""
    if not occupied:
        return frozenset()
    pad = grid.flood_pad
    xs = [c[0] for c in occupied]
    ys = [c[1] for c in occupied]
    x0, x1 = min(xs) - pad, max(xs) + pad
    y0, y1 = min(ys) - pad, max(ys) + pad

    def in_box(c: Cell) -> bool:
        return x0 <= c[0] <= x1 and y0 <= c[1] <= y1

    # Seed from the entire padding ring (every valid empty cell on the border
    # band) — on sparse lattices a single corner seed might be an invalid cell.
    seeds = []
    for x in range(x0, x1 + 1):
        for y in (y0, y1):
            c = (x, y)
            if grid.cell_valid(c) and c not in occupied:
                seeds.append(c)
    for y in range(y0, y1 + 1):
        for x in (x0, x1):
            c = (x, y)
            if grid.cell_valid(c) and c not in occupied:
                seeds.append(c)

    reached = set(seeds)
    stack = list(seeds)
    while stack:
        c = stack.pop()
        for n in grid.edge_neighbors(c):
            if n not in reached and n not in occupied and in_box(n):
                reached.add(n)
                stack.append(n)

    holes = set()
    for x in range(x0 + 1, x1):
        for y in range(y0 + 1, y1):
            c = (x, y)
            if c not in occupied and c not in reached and grid.cell_valid(c):
                holes.add(c)
    return frozenset(holes)


def is_hole_free(occupied: frozenset, grid: Grid) -> bool:
    return not holes_of(occupied, grid)


def spans(cells, grid: Grid) -> tuple[int, int]:
    """Bounding-box extent (max - min + 1) per axis, in grid coordinates."""
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    return (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)


def check_shape(cells: tuple, grid: Grid, *, max_cells: int = 200,
                max_span_sum: int = 29) -> ShapeInfo:
    """Stage 2 checks, in spec order. `cells` comes from the parser, which
    already rejected duplicates and off-lattice cells."""
    if not cells:
        raise VerifyError(ErrorCode.SHAPE_EMPTY, "shape has no cells")
    if len(cells) > max_cells:
        raise VerifyError(
            ErrorCode.SHAPE_TOO_LARGE, f"{len(cells)} cells, cap is {max_cells}"
        )
    cellset = frozenset(cells)
    if not connected(cellset, grid):
        raise VerifyError(ErrorCode.SHAPE_DISCONNECTED, "shape is not edge-connected")
    hs = holes_of(cellset, grid)
    if hs:
        sample = tuple(sorted(hs))[:5]
        raise VerifyError(
            ErrorCode.SHAPE_HAS_HOLE, f"shape encloses empty cells, e.g. {sample}", sample
        )
    sx, sy = spans(cells, grid)
    if sx + sy > max_span_sum:
        raise VerifyError(
            ErrorCode.SHAPE_SPAN_EXCEEDED,
            f"span_x + span_y = {sx} + {sy} > {max_span_sum}",
        )
    return ShapeInfo(cells=cellset, span_x=sx, span_y=sy)
