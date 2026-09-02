"""Error codes, statuses, and the Result record.

Error codes are API (spec §8): agents parse them in search loops. Every
rejection carries a stable code, a human message, and, where meaningful,
offending coordinates.
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field


class ErrorCode(str, enum.Enum):
    # Parse
    PARSE_SYNTAX = "PARSE_SYNTAX"
    PARSE_COUNT_MISMATCH = "PARSE_COUNT_MISMATCH"
    PARSE_UNKNOWN_GRID = "PARSE_UNKNOWN_GRID"
    # Shape
    SHAPE_TOO_LARGE = "SHAPE_TOO_LARGE"
    SHAPE_SPAN_EXCEEDED = "SHAPE_SPAN_EXCEEDED"
    SHAPE_DISCONNECTED = "SHAPE_DISCONNECTED"
    SHAPE_HAS_HOLE = "SHAPE_HAS_HOLE"
    SHAPE_DUPLICATE_CELL = "SHAPE_DUPLICATE_CELL"
    SHAPE_EMPTY = "SHAPE_EMPTY"
    # Transform
    XFORM_NOT_SYMMETRY = "XFORM_NOT_SYMMETRY"
    XFORM_REFLECTION_BANNED = "XFORM_REFLECTION_BANNED"
    # Patch
    PATCH_OVERLAP = "PATCH_OVERLAP"
    PATCH_LEVEL_MISMATCH = "PATCH_LEVEL_MISMATCH"
    PATCH_ORPHAN_TILE = "PATCH_ORPHAN_TILE"
    PATCH_GAP = "PATCH_GAP"
    PATCH_HOLE_IN_CORONA = "PATCH_HOLE_IN_CORONA"
    PATCH_NO_CENTRAL_TILE = "PATCH_NO_CENTRAL_TILE"
    PATCH_MULTIPLE_CENTRAL = "PATCH_MULTIPLE_CENTRAL"
    # Claims
    CLAIM_BELOW_THRESHOLD = "CLAIM_BELOW_THRESHOLD"
    CLAIM_WEAKER_THAN_STATED = "CLAIM_WEAKER_THAN_STATED"
    # Defect (§9.2)
    DEFECT_XFORM_INVALID = "DEFECT_XFORM_INVALID"
    DEFECT_TILE_OVERLAP = "DEFECT_TILE_OVERLAP"
    DEFECT_TILE_NOT_TOUCHING = "DEFECT_TILE_NOT_TOUCHING"
    DEFECT_TILE_OUT_OF_BAND = "DEFECT_TILE_OUT_OF_BAND"
    DEFECT_CLAIM_MISMATCH = "DEFECT_CLAIM_MISMATCH"
    DEFECT_LEVEL_MISMATCH = "DEFECT_LEVEL_MISMATCH"
    # Gates (§2.2 fail-closed rule) and the proof path (§13)
    GATE_IS_TILER = "GATE_IS_TILER"
    GATE_INCONCLUSIVE = "GATE_INCONCLUSIVE"
    CENSUS_CONTRADICTION = "CENSUS_CONTRADICTION"
    GATE_PROOF_INVALID = "GATE_PROOF_INVALID"
    PROOF_CNF_DIGEST_MISMATCH = "PROOF_CNF_DIGEST_MISMATCH"
    PROOF_TRUNCATED = "PROOF_TRUNCATED"
    PROOF_HEADER_MISMATCH = "PROOF_HEADER_MISMATCH"
    PROOF_LEVEL_INCONSISTENT = "PROOF_LEVEL_INCONSISTENT"
    PROOF_FILE_INVALID = "PROOF_FILE_INVALID"
    PROOF_FILE_DIGEST_MISMATCH = "PROOF_FILE_DIGEST_MISMATCH"
    CHECKER_UNAVAILABLE = "CHECKER_UNAVAILABLE"
    # Store / resources
    DUPLICATE = "DUPLICATE"
    RESOURCE_EXCEEDED = "RESOURCE_EXCEEDED"


class Status(str, enum.Enum):
    """Non-terminal statuses, distinct from rejection codes (spec §8)."""

    PROMOTED = "PROMOTED"
    SUPERSEDED = "SUPERSEDED"
    EXACT_UNDECIDED_HOLE_CASE = "EXACT_UNDECIDED_HOLE_CASE"


class VerifyError(Exception):
    def __init__(self, code: ErrorCode, message: str, cells: tuple = ()):
        super().__init__(f"{code.value}: {message}")
        self.code = code
        self.message = message
        self.cells = tuple(cells)

    def to_json(self) -> dict:
        out = {"error": self.code.value, "message": self.message}
        if self.cells:
            out["cells"] = [list(c) for c in self.cells]
        return out


@dataclass(frozen=True)
class Result:
    """Everything recorded per accepted submission (spec §9, §9.2.8)."""

    hc_verified: int
    hh_verified: int
    cell_count: int
    span_x: int
    span_y: int
    symmetry_order: int
    patch_size: int
    grid: str
    reflections_used: bool
    canonical_digest: str
    gate_tier: str = "none"
    verified_claim: str = ""
    claim_discrepancy: bool = False
    hc_claimed: int = 0
    hh_claimed: int = 0
    # Defect fields (§9.2.8) — recorded on every submission regardless of the
    # board flag, so toggling the board needs no re-verification; the flag
    # decides whether the defect fraction enters the score / ranking.
    defect_enabled: bool = True    # scoring honours it (score.yukon_score, board keys)
    defect_block_present: bool = False
    defect_corona_level: int = 0
    defect_hc: int = 0
    defect_hh: int = 0
    defect_required: int = 0
    defect_pocket_cells: int = 0
    defect_partial_tiles: int = 0
    # Non-tiler evidence (§2.2/§2.3): how non-tilerhood was established.
    # `census` = Kaplan 2022 complete census (published exact Hc/Hh);
    # `proof` = machine-checked UNSAT proof of F(S, m).
    non_tiler_evidence: str = ""
    tier: str = ""                 # "lower_bound" | "exact_proof"
    census_hc: int | None = None
    census_hh: int | None = None
    proof_status: str = ""
    proof_m: int = 0
    proof_cnf_digest: str = ""
    proof_sha256: str = ""
    proof_format: str = ""             # declared in the #PROOF block (drat | lrat)
    proof_format_detected: str = ""    # sniffed from the bytes (e.g. lrat-text); must agree
    proof_checkers: tuple = ()
    proof_core_clauses: int = 0    # > 0 when checked on a verified core subset of F
    hh_exact: bool = False         # Hh established exactly (= hh_verified)
    exact: bool = False            # Hc = Hh = hc_verified established exactly
    # Record flags (§2.3/§13.9): `record_eligible` = proof-backed non-tiler
    # with hc_verified >= 5 — a certified record-breaking lower bound whatever
    # the exact value (Hc in {Hh-1, Hh}); `record_exact` additionally requires
    # `exact` (Hc = Hh = hc pinned by a proof at m = hh + 1).
    record_eligible: bool = False
    record_exact: bool = False
    # Which resource profile the harness ran under (heesch_verify/profile.py):
    # "record" on the dedicated runner, "standard" on an 8 GB job. Decides the
    # proof band and budgets, never the acceptance rule.
    resource_profile: str = ""
    # Frozen conventions (§11) written into every record.
    conventions: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        out = {
            "hc_verified": self.hc_verified,
            "hh_verified": self.hh_verified,
            "cell_count": self.cell_count,
            "span_x": self.span_x,
            "span_y": self.span_y,
            "symmetry_order": self.symmetry_order,
            "patch_size": self.patch_size,
            "grid": self.grid,
            "reflections_used": self.reflections_used,
            "canonical_digest": self.canonical_digest,
            "gate_tier": self.gate_tier,
            "verified_claim": self.verified_claim,
            "claim_discrepancy": self.claim_discrepancy,
            "hc_claimed": self.hc_claimed,
            "hh_claimed": self.hh_claimed,
            "defect_enabled": self.defect_enabled,
            "defect_block_present": self.defect_block_present,
            "defect_corona_level": self.defect_corona_level,
            "defect_hc": self.defect_hc,
            "defect_hh": self.defect_hh,
            "defect_required": self.defect_required,
            "defect_pocket_cells": self.defect_pocket_cells,
            "defect_partial_tiles": self.defect_partial_tiles,
            "non_tiler_evidence": self.non_tiler_evidence,
            "tier": self.tier,
            "census_hc": self.census_hc,
            "census_hh": self.census_hh,
            "proof_status": self.proof_status,
            "proof_m": self.proof_m,
            "proof_cnf_digest": self.proof_cnf_digest,
            "proof_sha256": self.proof_sha256,
            "proof_format": self.proof_format,
            "proof_format_detected": self.proof_format_detected,
            "proof_checkers": list(self.proof_checkers),
            "proof_core_clauses": self.proof_core_clauses,
            "hh_exact": self.hh_exact,
            "exact": self.exact,
            "record_eligible": self.record_eligible,
            "record_exact": self.record_exact,
            "resource_profile": self.resource_profile,
            "conventions": dict(self.conventions),
        }
        return out

    def to_json_str(self) -> str:
        return json.dumps(self.to_json(), sort_keys=True, separators=(",", ":"))
