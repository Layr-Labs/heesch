"""JOB A: the cheap witness checker (spec §2 job A, §7 pipeline).

Stdlib only, side-effect free. This is the module published for agents to run
in their inner search loop; identical code runs server-side. Solver
dependencies live behind gates.py and are never imported here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import canonical, parse, patch, shape
from .grids import GRIDS, Contact
from .result import ErrorCode, Result, VerifyError
from .transform import check_symmetry

CONVENTIONS_REVISION = "v1"


@dataclass(frozen=True)
class VerifyConfig:
    """Frozen conventions (spec §11) plus resource caps. The defaults are the
    calibrated values; changing any of them is a new revision."""

    contact_mode: str = "point"       # boundary-point contact, per heesch-sat
    allow_reflections: bool = True
    max_cells: int = 200
    max_span_sum: int = 29
    max_placements: int = 20_000
    strict_claims: bool = False       # True: claim mismatch is a rejection
    # Defect credit (§9.2.6) is part of the public score: the flag is live —
    # yukon_score and the board keys consult Result.defect_enabled — and on
    # by default (audit 2026-08-19 Low 13: the emitted `defect_enabled` must
    # agree with what the scalar contains).
    defect_board_enabled: bool = True

    def conventions(self) -> dict:
        return {
            "revision": CONVENTIONS_REVISION,
            "contact": self.contact_mode,
            "reflections": "allowed" if self.allow_reflections else "banned",
            "corona_mode": "hc_primary_hh_computed",
            "inner_holes": "never",
            "tile_disk": True,
            "central_identity_required": False,
        }


@dataclass(frozen=True)
class WitnessOutcome:
    """Internal richer result: Result plus the geometry needed downstream
    (defect verification, gates, encoder)."""

    result: Result
    submission: parse.Submission
    contact: Contact
    hc_corona: patch.CoronaResult | None   # the verified Hc patch (None if hc=0)


def verify_witness(text: str, config: VerifyConfig | None = None) -> WitnessOutcome:
    """Stages 1–5. Raises VerifyError with a stable code on rejection.

    Defect-block verification (§9.2) is a separate pass in defect.py, run by
    the harness after this succeeds; parsing of the block happens here.
    """
    config = config or VerifyConfig()

    # Stage 1 — parse.
    sub = parse.parse_submission(text, max_placements=config.max_placements)
    grid = sub.grid

    # Stage 2 — shape validity.
    info = shape.check_shape(
        sub.cells, grid, max_cells=config.max_cells, max_span_sum=config.max_span_sum
    )

    # Stage 3 — canonical form.
    digest = canonical.canonical_digest(sub.cells, grid, config.allow_reflections)
    sym_order = canonical.symmetry_order(sub.cells, grid, config.allow_reflections)

    # Stage 4 — transform validity, all placements in all patches.
    reflections_used = False
    for p in sub.patches:
        for _lvl, xf in p:
            sym = check_symmetry(xf, grid, config.allow_reflections)
            if sym.det < 0:
                reflections_used = True

    # The one contact relation for this run, threaded everywhere (§11.1).
    contact = grid.contact(config.contact_mode)

    # Stage 5 — patch legality.
    hc_verified = 0
    hh_verified = 0
    hc_corona: patch.CoronaResult | None = None
    discrepancy = False
    notes = []

    if sub.patch_count >= 1:
        # Patch 1 is the Hc patch. Verify under hole-allowed rules, then
        # interpret: a hole in its outermost corona downgrades hc to L-1
        # (P_{L-1} is verified hole-free) while still establishing Hh >= L.
        c1 = patch.check_corona(
            info.cells, sub.patches[0], grid, contact, hole_mode="hh",
            max_work=patch.MAX_CORONA_WORK,
        )
        if c1.has_outer_holes:
            if config.strict_claims:
                raise VerifyError(
                    ErrorCode.PATCH_HOLE_IN_CORONA,
                    f"outermost corona {c1.max_level} of the Hc patch encloses empty cells",
                )
            hc_verified = c1.max_level - 1
            hh_verified = c1.max_level
            discrepancy = True
            notes.append(
                f"hc patch outer corona has holes: downgraded to hc>={hc_verified}, "
                f"hh>={hh_verified}"
            )
        else:
            hc_verified = c1.max_level
            hh_verified = c1.max_level
        hc_corona = c1

    if sub.patch_count == 2:
        c2 = patch.check_corona(
            info.cells, sub.patches[1], grid, contact, hole_mode="hh",
            max_work=patch.MAX_CORONA_WORK,
        )
        hh_verified = max(hh_verified, c2.max_level)

    # Stage 5e — report what was actually established.
    if hc_verified < sub.hc_claim or hh_verified < sub.hh_claim:
        if config.strict_claims:
            raise VerifyError(
                ErrorCode.CLAIM_WEAKER_THAN_STATED,
                f"claimed hc={sub.hc_claim} hh={sub.hh_claim}, "
                f"verified hc={hc_verified} hh={hh_verified}",
            )
        discrepancy = True
        notes.append(
            f"claimed hc={sub.hc_claim} hh={sub.hh_claim}; accepted weaker verified claim"
        )

    verified_claim = f"hc>={hc_verified}, hh>={hh_verified} (lower bound)"
    if notes:
        verified_claim += "; " + "; ".join(notes)

    result = Result(
        hc_verified=hc_verified,
        hh_verified=hh_verified,
        cell_count=len(sub.cells),
        span_x=info.span_x,
        span_y=info.span_y,
        symmetry_order=sym_order,
        patch_size=sum(len(p) for p in sub.patches),
        grid=sub.grid_id,
        reflections_used=reflections_used,
        canonical_digest=digest,
        verified_claim=verified_claim,
        claim_discrepancy=discrepancy,
        hc_claimed=sub.hc_claim,
        hh_claimed=sub.hh_claim,
        defect_block_present=sub.defect is not None,
        defect_enabled=config.defect_board_enabled,
        conventions=config.conventions(),
    )
    return WitnessOutcome(result=result, submission=sub, contact=contact, hc_corona=hc_corona)
