"""Core encoder types. Placement field order IS the §3.3 canonical sort key —
NamedTuple ordering gives (symmetry_index, ty, tx) for free; do not reorder
fields, that is a new revision."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple


class Placement(NamedTuple):
    symmetry_index: int
    ty: int
    tx: int


@dataclass(frozen=True)
class AmoGroup:
    """One at-most-one constraint: the cell, its covering variables (sorted
    ascending), the encoding used, and any auxiliary variable range.
    Consumed by the §9.2 aux-extension test — not on the emission path."""

    cell: tuple
    variables: tuple[int, ...]
    kind: str                    # "pairwise" | "sequential"
    aux_start: int = 0           # first aux var (sequential only)
    aux_count: int = 0


@dataclass(frozen=True)
class Formula:
    num_vars: int
    clauses: tuple[tuple[int, ...], ...]   # final emission order
    universe: tuple[Placement, ...]        # var i (1-indexed) = universe[i-1]
    amo_groups: tuple[AmoGroup, ...]
    required_cells: tuple                  # R in canonical cell order
