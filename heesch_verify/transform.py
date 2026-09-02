"""Placement transforms and Stage 4 symmetry membership (spec §7 Stage 4).

Membership is tested against the explicit point group — det = ±1 is NOT
sufficient (a shear like <1,1,0,0,1,0> has det 1 and is not a grid symmetry).
On the iamond grid the check is affine-aware: the linear part must match an
orientation and the residual translation must be lattice-legal.
"""

from __future__ import annotations

from dataclasses import dataclass

from .grids import Cell, Grid, Symmetry
from .result import ErrorCode, VerifyError


@dataclass(frozen=True)
class Xform:
    a: int
    b: int
    c: int
    d: int
    e: int
    f: int

    def apply(self, cell: Cell) -> Cell:
        x, y = cell
        return (self.a * x + self.b * y + self.c, self.d * x + self.e * y + self.f)

    def apply_all(self, cells) -> frozenset:
        a, b, c, d, e, f = self.a, self.b, self.c, self.d, self.e, self.f
        return frozenset((a * x + b * y + c, d * x + e * y + f) for x, y in cells)

    @property
    def linear(self) -> tuple[int, int, int, int]:
        return (self.a, self.b, self.d, self.e)

    @property
    def det(self) -> int:
        return self.a * self.e - self.b * self.d

    def as_text(self) -> str:
        return f"<{self.a},{self.b},{self.c},{self.d},{self.e},{self.f}>"


def check_symmetry(xf: Xform, grid: Grid, allow_reflections: bool,
                   code: ErrorCode = ErrorCode.XFORM_NOT_SYMMETRY) -> Symmetry:
    """Validate that xf is a legal grid motion; return the matching orientation.

    `code` lets the defect path report DEFECT_XFORM_INVALID with identical logic.
    """
    sym = grid.orientation_by_linear(xf.linear)
    if sym is None:
        raise VerifyError(code, f"matrix part of {xf.as_text()} is not a grid symmetry")
    if not grid.translation_legal(xf.c - sym.c0, xf.f - sym.f0):
        raise VerifyError(
            code,
            f"translation part of {xf.as_text()} is not on the grid lattice",
        )
    if not allow_reflections and sym.det < 0:
        raise VerifyError(
            ErrorCode.XFORM_REFLECTION_BANNED,
            f"{xf.as_text()} is a reflection and reflections are banned on this board",
        )
    return sym
