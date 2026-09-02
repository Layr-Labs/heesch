"""One entry point: encode(tile, patch, grid, contact) -> EncodingResult.

The level k+1 never appears as a parameter — it is implicit in patch = P_k
(passing a level invites an off-by-one)."""

from __future__ import annotations

from dataclasses import dataclass

from heesch_verify.grids import Contact, Grid

from .clauses import build_formula
from .amo import AMO_THRESHOLD
from .dimacs import cnf_digest, emit_dimacs
from .types import Formula


@dataclass(frozen=True)
class EncodingResult:
    dimacs: bytes
    digest: str
    num_vars: int
    num_clauses: int
    formula: Formula


def encode(tile_cells, patch_cells, grid: Grid, contact: Contact,
           amo_threshold: int = AMO_THRESHOLD) -> EncodingResult:
    formula = build_formula(tile_cells, patch_cells, grid, contact, amo_threshold)
    dimacs = emit_dimacs(formula)
    return EncodingResult(
        dimacs=dimacs,
        digest=cnf_digest(dimacs),
        num_vars=formula.num_vars,
        num_clauses=len(formula.clauses),
        formula=formula,
    )


@dataclass(frozen=True)
class DigestMismatch:
    expected: str
    computed: str


def regenerate_and_match(claimed_digest: str, tile_cells, patch_cells,
                         grid: Grid, contact: Contact):
    """Server-side step 1 of proof checking: regenerate the CNF and compare
    digests BEFORE touching any submitted proof bytes."""
    enc = encode(tile_cells, patch_cells, grid, contact)
    if enc.digest != claimed_digest:
        return DigestMismatch(expected=claimed_digest, computed=enc.digest)
    return enc
