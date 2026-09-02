"""Score tuples, board orderings (§9, §9.2.5) and the Yukon scalar.

The verifier emits invariants; boards are orderings over them. Defect
fractions are compared exactly via integers (Fraction) — never floats,
never rounded decimals (§9.2.4). The verified integer Heesch number is
always the primary key: a near-miss on a harder ring strictly beats a good
partial on an easier one, enforced by lexicographic order.
"""

from __future__ import annotations

from fractions import Fraction

from .result import Result

# A missing defect block scores as the worst possible fraction for ranking:
# the whole required set uncovered.
_WORST = Fraction(1)


def _defect_fraction(defect: int, required: int, present: bool, enabled: bool = True) -> Fraction:
    if not enabled or not present or required <= 0:
        return _WORST
    return Fraction(defect, required)


def hc_board_key(r: Result) -> tuple:
    """Hc board (§9.2.5): higher tuple = better. Reads defect_hc ONLY —
    ranking an Hc board on defect_hh is the bug §9.2.1 exists to prevent,
    made impossible here by construction (see test_score assertions)."""
    frac = _defect_fraction(r.defect_hc, r.defect_required, r.defect_block_present, r.defect_enabled)
    return (
        r.hc_verified,
        -frac,
        r.hh_verified,
        -r.cell_count,
        -(r.span_x + r.span_y),
        -r.patch_size,
    )


def hh_board_key(r: Result) -> tuple:
    """Hh board: same shape, its own matching defect number."""
    frac = _defect_fraction(r.defect_hh, r.defect_required, r.defect_block_present, r.defect_enabled)
    return (
        r.hh_verified,
        -frac,
        r.hc_verified,
        -r.cell_count,
        -(r.span_x + r.span_y),
        -r.patch_size,
    )


def strictly_better(new: Result, old: Result, board=hc_board_key) -> bool:
    return board(new) > board(old)


def improvement_component(new: Result, old: Result, board=hc_board_key) -> str:
    """Name the first tuple component where the records differ — used in
    DUPLICATE messages (§7 Stage 7)."""
    names = ("primary", "defect_fraction", "secondary", "cell_count", "span", "patch_size")
    a, b = board(new), board(old)
    for name, x, y in zip(names, a, b):
        if x != y:
            return name
    return "identical"


def yukon_score(r: Result) -> float:
    """The single scalar for Yukon promotion: verified corona count plus
    defect progress toward the next ring. The fractional part is clamped to
    [0, 0.999999] so no defect achievement can roll into the next integer —
    only a verified corona does that. This is NOT a Heesch number and must
    never be labelled as one (§9.2.6). `defect_enabled` (VerifyConfig.
    defect_board_enabled, on by default) gates the fractional part, so the
    emitted flag always agrees with what the scalar contains (audit
    2026-08-19 Low 13)."""
    base = float(r.hc_verified)
    if not r.defect_enabled or not r.defect_block_present or r.defect_required <= 0:
        return base
    frac = 1.0 - (r.defect_hc / r.defect_required)
    frac = max(0.0, min(frac, 0.999999))
    return base + frac
