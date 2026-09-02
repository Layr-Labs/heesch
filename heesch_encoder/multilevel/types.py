"""v2 formula types. MLFormula duck-types into dimacs.emit_dimacs
(num_vars + clauses only); it is a sibling of v1's Formula, not a subclass."""

from __future__ import annotations

from dataclasses import dataclass

from ..types import AmoGroup  # reused verbatim


@dataclass(frozen=True)
class MLFormula:
    m: int
    num_vars: int
    clauses: tuple                 # tuple[tuple[int, ...], ...], final emission order
    levels: tuple                  # per level: tuple[Placement, ...] in placement_key order
    level_offsets: tuple           # var of levels[l][i] == level_offsets[l] + i + 1
    amo_groups: tuple              # tuple[AmoGroup, ...]
    required_cells: tuple          # R_0 in canonical cell order
    family_counts: tuple           # (("1", n), ("2", n), ("4", n), ("5", n), ("6", n))

    def var_of(self, level: int, index: int) -> int:
        return self.level_offsets[level - 1] + index + 1

    def placement_of_var(self, v: int):
        """(level, Placement) for an x variable; None for auxiliaries."""
        for l in range(self.m, 0, -1):
            off = self.level_offsets[l - 1]
            if v > off:
                idx = v - off - 1
                if idx < len(self.levels[l - 1]):
                    return (l, self.levels[l - 1][idx])
                return None
        return None
