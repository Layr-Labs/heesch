"""Grids: the one home of adjacency and symmetry data in this codebase.

All neighbor tables and orientation lists are transcribed verbatim from
Kaplan's heesch-sat (src/ominogrid.h, hexgrid.h, iamondgrid.h) — see
tools/NOTES-kaplan.md for provenance. Do not edit them; they are frozen
conventions (spec §11) and changing any is a new revision.

The `Contact` relation object is constructed once per verification run and
threaded as a parameter into every corona-related function (spec §11.1).
There is deliberately no module-level default Contact and no second
implementation of adjacency anywhere else in the package.
"""

from __future__ import annotations

from dataclasses import dataclass

Cell = tuple[int, int]


@dataclass(frozen=True)
class Symmetry:
    """One point-group element: linear part plus affine offset.

    On the square and hex grids all offsets are zero. On the iamond grid the
    six orientation-swapping elements carry offset (1, 1) — a pure matrix
    cannot map up-triangles to down-triangles.
    """

    index: int
    a: int
    b: int
    d: int
    e: int
    c0: int = 0
    f0: int = 0

    def apply(self, cell: Cell) -> Cell:
        x, y = cell
        return (self.a * x + self.b * y + self.c0, self.d * x + self.e * y + self.f0)

    @property
    def det(self) -> int:
        return self.a * self.e - self.b * self.d

    @property
    def linear(self) -> tuple[int, int, int, int]:
        return (self.a, self.b, self.d, self.e)


class Contact:
    """The frozen contact relation, threaded per spec §11.1.

    Identity (`is`) comparison is meaningful: plain object, no __eq__.
    """

    __slots__ = ("grid", "mode")

    def __init__(self, grid: "Grid", mode: str):
        if mode not in ("edge", "point"):
            raise ValueError(f"unknown contact mode: {mode}")
        self.grid = grid
        self.mode = mode

    def neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        if self.mode == "edge":
            return self.grid.edge_neighbors(cell)
        return self.grid.point_neighbors(cell)


def _sym(index: int, row: tuple[int, ...]) -> Symmetry:
    # heesch-sat xform order is (a, b, c, d, e, f) with x' = ax+by+c, y' = dx+ey+f
    a, b, c, d, e, f = row
    return Symmetry(index=index, a=a, b=b, d=d, e=e, c0=c, f0=f)


class Grid:
    """Base class; concrete grids provide frozen tables."""

    grid_id: str = "?"
    flood_pad: int = 1
    orientations: tuple[Symmetry, ...] = ()

    def cell_valid(self, cell: Cell) -> bool:
        return True

    def edge_neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        raise NotImplementedError

    def point_neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        raise NotImplementedError

    def translation_legal(self, dx: int, dy: int) -> bool:
        return True

    def normalize(self, cells) -> tuple[Cell, ...]:
        """Translate to a canonical origin by a legal translation; return
        the sorted cell tuple (deterministic)."""
        raise NotImplementedError

    def contact(self, mode: str) -> Contact:
        return Contact(self, mode)

    def orientation_by_linear(self, linear: tuple[int, int, int, int]) -> Symmetry | None:
        return self._by_linear.get(linear)

    def _finish_init(self):
        self._by_linear = {s.linear: s for s in self.orientations}
        # Linear parts must be distinct within a grid or membership testing
        # is ambiguous; true for O/H/I (verified in tests).
        assert len(self._by_linear) == len(self.orientations)


def _offsets_to_neighbors(cell: Cell, offsets) -> tuple[Cell, ...]:
    x, y = cell
    return tuple((x + dx, y + dy) for dx, dy in offsets)


class SquareGrid(Grid):
    grid_id = "O"
    flood_pad = 1

    _EDGE = ((0, -1), (-1, 0), (1, 0), (0, 1))
    _POINT = (
        (-1, -1), (0, -1), (1, -1),
        (-1, 0), (1, 0),
        (-1, 1), (0, 1), (1, 1),
    )

    orientations = tuple(
        _sym(i, row)
        for i, row in enumerate(
            [
                (1, 0, 0, 0, 1, 0),
                (0, -1, 0, 1, 0, 0),
                (-1, 0, 0, 0, -1, 0),
                (0, 1, 0, -1, 0, 0),
                (-1, 0, 0, 0, 1, 0),
                (0, -1, 0, -1, 0, 0),
                (1, 0, 0, 0, -1, 0),
                (0, 1, 0, 1, 0, 0),
            ]
        )
    )

    def __init__(self):
        self._finish_init()

    def edge_neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        return _offsets_to_neighbors(cell, self._EDGE)

    def point_neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        return _offsets_to_neighbors(cell, self._POINT)

    def normalize(self, cells) -> tuple[Cell, ...]:
        mx = min(c[0] for c in cells)
        my = min(c[1] for c in cells)
        return tuple(sorted((x - mx, y - my) for x, y in cells))


class HexGrid(Grid):
    """Axial coordinates. Edge and boundary-point contact coincide on hexes
    (heesch-sat's getEdgeNeighbourVectors returns all_neighbours)."""

    grid_id = "H"
    flood_pad = 1

    _NEIGH = ((0, -1), (0, 1), (1, 0), (-1, 0), (1, -1), (-1, 1))

    orientations = tuple(
        _sym(i, row)
        for i, row in enumerate(
            [
                (1, 0, 0, 0, 1, 0),
                (0, -1, 0, 1, 1, 0),
                (-1, -1, 0, 1, 0, 0),
                (-1, 0, 0, 0, -1, 0),
                (0, 1, 0, -1, -1, 0),
                (1, 1, 0, -1, 0, 0),
                (0, 1, 0, 1, 0, 0),
                (-1, 0, 0, 1, 1, 0),
                (-1, -1, 0, 0, 1, 0),
                (0, -1, 0, -1, 0, 0),
                (1, 0, 0, -1, -1, 0),
                (1, 1, 0, 0, -1, 0),
            ]
        )
    )

    def __init__(self):
        self._finish_init()

    def edge_neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        return _offsets_to_neighbors(cell, self._NEIGH)

    def point_neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        return _offsets_to_neighbors(cell, self._NEIGH)

    def normalize(self, cells) -> tuple[Cell, ...]:
        mx = min(c[0] for c in cells)
        my = min(c[1] for c in cells)
        return tuple(sorted((x - mx, y - my) for x, y in cells))


class TriGrid(Grid):
    """Iamond grid, Kaplan's encoding: valid cells are (x, y) with
    x ≡ y ≡ 0 (mod 3) (up triangle) or x ≡ y ≡ 1 (mod 3) (down triangle).
    Legal translations are ≡ (0, 0) mod 3 componentwise. Six of the twelve
    point-group elements carry affine offset (1, 1)."""

    grid_id = "I"
    flood_pad = 6  # neighbor vector components reach ±4

    _EDGE_UP = ((1, 1), (-2, 1), (1, -2))
    _EDGE_DOWN = ((-1, -1), (2, -1), (-1, 2))
    _POINT_UP = (
        (3, 0), (0, 3), (-3, 3), (-3, 0), (0, -3), (3, -3),
        (1, 1), (-2, 4), (-2, 1), (-2, -2), (1, -2), (4, -2),
    )
    _POINT_DOWN = (
        (3, 0), (0, 3), (-3, 3), (-3, 0), (0, -3), (3, -3),
        (2, 2), (2, -1), (2, -4), (-1, -1), (-4, 2), (-1, 2),
    )

    orientations = tuple(
        _sym(i, row)
        for i, row in enumerate(
            [
                (1, 0, 0, 0, 1, 0),
                (-1, -1, 0, 1, 0, 0),
                (0, 1, 0, -1, -1, 0),
                (1, 0, 0, -1, -1, 0),
                (0, 1, 0, 1, 0, 0),
                (-1, -1, 0, 0, 1, 0),
                (0, -1, 1, -1, 0, 1),
                (-1, 0, 1, 1, 1, 1),
                (1, 1, 1, 0, -1, 1),
                (1, 1, 1, -1, 0, 1),
                (-1, 0, 1, 0, -1, 1),
                (0, -1, 1, 1, 1, 1),
            ]
        )
    )

    def __init__(self):
        self._finish_init()

    @staticmethod
    def _is_up(cell: Cell) -> bool:
        return cell[0] % 3 == 0

    def cell_valid(self, cell: Cell) -> bool:
        x, y = cell
        r = x % 3
        return r == y % 3 and r in (0, 1)

    def edge_neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        offs = self._EDGE_UP if self._is_up(cell) else self._EDGE_DOWN
        return _offsets_to_neighbors(cell, offs)

    def point_neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        offs = self._POINT_UP if self._is_up(cell) else self._POINT_DOWN
        return _offsets_to_neighbors(cell, offs)

    def translation_legal(self, dx: int, dy: int) -> bool:
        return dx % 3 == 0 and dy % 3 == 0

    def normalize(self, cells) -> tuple[Cell, ...]:
        # Shift by multiples of 3 so both min coordinates land in {0, 1, 2}.
        mx = min(c[0] for c in cells)
        my = min(c[1] for c in cells)
        dx = -(mx - mx % 3)
        dy = -(my - my % 3)
        return tuple(sorted((x + dx, y + dy) for x, y in cells))


GRIDS: dict[str, Grid] = {
    "O": SquareGrid(),
    "H": HexGrid(),
    "I": TriGrid(),
}
