"""v2 entry points. The digest depends only on (S, m) — tile_cells is taken
verbatim; callers pass the verifier's canonical form, same contract as v1."""

from __future__ import annotations

from dataclasses import dataclass

from heesch_verify.grids import Contact, Grid

from ..amo import AMO_THRESHOLD
from ..api import DigestMismatch
from ..dimacs import cnf_digest, emit_dimacs
from .clauses import build_ml_formula
from .types import MLFormula


@dataclass(frozen=True)
class MLEncodingResult:
    dimacs: bytes
    digest: str
    num_vars: int
    num_clauses: int
    m: int
    universe_sizes: tuple
    family_counts: tuple
    formula: MLFormula


def encode_multilevel(tile_cells, grid: Grid, contact: Contact, m: int,
                      amo_threshold: int = AMO_THRESHOLD) -> MLEncodingResult:
    formula = build_ml_formula(tile_cells, grid, contact, m, amo_threshold)
    dimacs = emit_dimacs(formula)
    return MLEncodingResult(
        dimacs=dimacs,
        digest=cnf_digest(dimacs),
        num_vars=formula.num_vars,
        num_clauses=len(formula.clauses),
        m=m,
        universe_sizes=tuple(len(lv) for lv in formula.levels),
        family_counts=formula.family_counts,
        formula=formula,
    )


def regenerate_and_match_v2(claimed_digest: str, tile_cells, grid: Grid,
                            contact: Contact, m: int):
    enc = encode_multilevel(tile_cells, grid, contact, m)
    if enc.digest != claimed_digest:
        return DigestMismatch(expected=claimed_digest, computed=enc.digest)
    return enc


# Feasibility band (multilevel spec §10.2): (max_cells, max_m) pairs the
# proof pipeline will ENCODE. Measured policy, not a frozen constant — it
# changes no CNF byte, so widening it is not a new encoder revision; the
# measurement history lives in docs/ml-feasibility.md and the code-checked
# revisions/rev-2-addendum.json. Current basis (2026-08-19/20): 11-hex
# F(S,7) full cycle 187 s encode / 3.1 GB RSS; counts 13-hex F(S,8) 97 M
# clauses / 5.8 GB, 16-hex F(S,8) 146 M / 9.1 GB, 20-iamond F(S,8) 100 M /
# 5.8 GB. (20, 8) here covers the maintainer out-of-band path; the HARNESS
# applies its resource profile's stricter band (heesch_verify/profile.py:
# record (16,8)(20,7)..., standard (12,6)(20,5)...) on top of this one.
FEASIBILITY_BAND = ((20, 8), (50, 4), (100, 3), (200, 2))


def feasibility_band() -> tuple[tuple[int, int], ...]:
    """The enforced band as ((max_cells, max_m), ...), ascending in
    max_cells."""
    return FEASIBILITY_BAND


def in_feasibility_band(n_cells: int, m: int) -> bool:
    """True iff encoding F(S, m) for an n_cells shape is inside the band.
    Outside it check_proof_v2 answers RESOURCE_EXCEEDED by policy."""
    if m < 1 or n_cells < 1:
        return False
    for max_cells, max_m in feasibility_band():
        if n_cells <= max_cells:
            return m <= max_m
    return False


@dataclass(frozen=True)
class MLStreamedEncoding:
    """F(S, m) written straight to disk (multilevel spec §6): the same bytes
    `encode_multilevel` produces, without materialising the clause list —
    peak memory is the universe plus the per-cell cover lists, not the
    formula. Digest and counts are computed while streaming."""

    path: str
    digest: str
    num_vars: int
    num_clauses: int
    m: int
    universe_sizes: tuple
    family_counts: tuple
    cnf_bytes: int
    has_empty_clause: bool

    def write_dimacs(self, dst: str) -> None:
        import shutil

        if str(dst) != str(self.path):
            shutil.copyfile(self.path, dst)


def encode_multilevel_stream(tile_cells, grid: Grid, contact: Contact, m: int,
                             out_path, amo_threshold: int = AMO_THRESHOLD,
                             deadline: float | None = None) -> MLStreamedEncoding:
    """Encode F(S, m) to `out_path` in the frozen DIMACS profile. Two passes
    over the output file (the header needs the final counts): clauses stream
    to `<out_path>.body`, then header + body are concatenated into out_path
    while the sha256 is computed. Byte-identical to encode_multilevel().

    `deadline` (a time.monotonic() value) is the portable encode guard: the
    universe BFS checks it between levels and the clause writer every 4096
    clauses, raising proofcheck.guard.EncodeTimeout — the same exception the
    SIGALRM guard raises where that is available. It never changes a byte."""
    import hashlib
    import os

    from .clauses import MLClauseStream
    from .universe import _check_deadline

    stream = MLClauseStream(tile_cells, grid, contact, m, amo_threshold, deadline=deadline)
    out_path = str(out_path)
    body_path = out_path + ".body"
    empty = False
    with open(body_path, "wb") as body:
        buf = []
        n = 0
        for cl in stream.clauses():
            if cl:
                buf.append(" ".join(str(l) for l in cl) + " 0\n")
            else:
                empty = True
                buf.append("0\n")
            n += 1
            if n % 4096 == 0:
                body.write("".join(buf).encode("ascii"))
                buf = []
                _check_deadline(deadline)
        if buf:
            body.write("".join(buf).encode("ascii"))
    header = f"p cnf {stream.num_vars} {stream.num_clauses}\n".encode("ascii")
    h = hashlib.sha256(header)
    size = len(header)
    with open(out_path, "wb") as out, open(body_path, "rb") as body:
        out.write(header)
        while True:
            chunk = body.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
            size += len(chunk)
            out.write(chunk)
    os.unlink(body_path)
    return MLStreamedEncoding(
        path=out_path, digest=h.hexdigest(), num_vars=stream.num_vars,
        num_clauses=stream.num_clauses, m=m,
        universe_sizes=tuple(len(lv) for lv in stream.uni.levels),
        family_counts=stream.family_counts, cnf_bytes=size, has_empty_clause=empty,
    )
