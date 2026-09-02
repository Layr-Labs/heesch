"""Frozen canonical orders (spec §3.3, §6). Every comparison that can reach
emitted bytes routes through these functions; nothing else in the package may
invent a sort key. Changing any order is a new revision and invalidates every
historical proof."""

from __future__ import annotations


def cell_key(cell) -> tuple:
    """Canonical cell order: (y, x) — row-major — on every grid.
    (For hex axial (q, r) this reads as (r, q).)"""
    return (cell[1], cell[0])


def placement_key(p) -> tuple:
    """(symmetry_index, translation_y, translation_x) — §3.3 verbatim."""
    return (p.symmetry_index, p.ty, p.tx)


def sorted_cells(it) -> list:
    return sorted(it, key=cell_key)


def sorted_placements(it) -> list:
    return sorted(it, key=placement_key)


def literal_key(lit: int) -> tuple:
    """Within a clause: ascending absolute value, negative before positive at
    equal magnitude (§6)."""
    return (abs(lit), lit > 0)


def xvar_key(level: int, p) -> tuple:
    """v2 (multilevel spec §5, emission §6): level-major x-variable order —
    (l, symmetry_index, ty, tx). Additive to the v1 orders; revision-1 is
    untouched."""
    return (level,) + placement_key(p)
