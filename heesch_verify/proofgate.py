"""Gate 3 — the proof-carrying non-tiler gate (architecture §2.3, §13).

A submission whose shape is outside the census can only score by carrying a
machine-checked UNSAT proof of the multilevel formula F(S, m) (encoder v2).
UNSAT of F(S, m) means no weak m-configuration exists over ALL patches, so
Hh <= m-1 and the shape is not a plane tiler; with a verified witness of
hh = m-1 the value is exact (multilevel spec §2.2). This module turns the
`#PROOF` block of a parsed submission into an enforced verdict:

  1. level rule        m >= hh_verified + 1, else PROOF_LEVEL_INCONSISTENT
                       (a witness deeper than the proof allows is a
                       contradiction — never scored, never "fixed up")
  2. checker preflight all three vendored checkers present, else
                       CHECKER_UNAVAILABLE (fail closed; never a downgrade)
  3. bands             harness band and the encoder feasibility band, else RESOURCE_EXCEEDED
  4. proof file        regular file inside submission/, size caps, optional
                       xz with bounded decompression, sha256 verified before
                       any checker sees a byte (same for the optional core
                       clause list — the subset of F an LRAT proof refutes;
                       heesch_encoder.proofcheck.core checks every clause is
                       a clause of the regenerated F, exactly)
  5. check_proof_v2    regenerate F(S, m), digest/header match, sniff, then
                       RECORD tier: two independent VERIFIED verdicts, one of
                       them cake_lpr (formally verified)

Never imported by witness.py or anything it imports; heesch_encoder is
imported lazily inside check() so the lower-bound path stays independent.
"""

from __future__ import annotations

import dataclasses
import errno
import hashlib
import lzma
import os
import pathlib
import shutil
import stat
import tempfile

from .canonical import canonical_form
from .profile import RECORD, STANDARD, ResourceProfile
from .result import ErrorCode

# Every budget of the proof path lives in heesch_verify/profile.py; the names
# below are the STANDARD values, kept for library/test callers. The gate reads
# its own `self.profile` (the harness passes profile.detect()).
# Stored cap: the proof / core file as submitted (plain or .xz), coupled to
# benchmark.json's maxSubmissionBytes (512 MiB): best.heesch (<= 2 MiB) +
# proof + core must fit. Payload cap: decompressed bytes, streamed to scratch
# on disk, never in memory (an F(S,7) core LRAT is ~0.4 GB raw / ~20 MB xz).
PROOF_MAX_STORED_BYTES = STANDARD.proof_max_stored_bytes
PROOF_MAX_PAYLOAD_BYTES = STANDARD.proof_max_payload_bytes
_XZ_MEMLIMIT = 256 * 1024 * 1024
_CHUNK = 1024 * 1024

# In-harness proof band (cells, max m). Narrower than the encoder's
# feasibility band because the harness must ENCODE F(S, m) inside the
# benchmark job as well as check it. The STANDARD band's (<= 20, 5) admits
# the exactness proof of every known Hc = 4 shape (11-20 cells); (<= 12, 6)
# admits an Hc = 5 certificate up to 12 cells WHEN Hh = 5 (measured: F(S,6)
# of the 11-hex — 112 s encode at 2.5 GB RSS, drat-trim 61 s, lrat-check
# 16 s on the 513 MB LRAT). An Hc = 5 shape with Hh = 6 needs F(S,7):
# out of the STANDARD band, but inside RECORD's (16,8) (20,7) ... band on
# the benchmark runner (§13.5/§13.9). See docs/ml-feasibility.md.
HARNESS_PROOF_BAND = STANDARD.harness_band   # the standard profile's band; RECORD.harness_band is wider
# Wall-clock guard around the in-process ENCODING step only (pipeline passes
# it to heesch_encoder.proofcheck.guard); the checkers are bounded separately
# by the CheckBudget the caller supplies. The numbers are per-profile
# (profile.py): STANDARD caps drat-trim 600 s / cake_lpr 900 s / lrat-check
# 300 s inside a 1500 s deadline with the encoder allowed the first 600 s;
# RECORD is 3600/3600/1800 s inside 9000 s with a 3600 s encode guard. The
# deadline counts from the budget's construction, which the harness does
# before this gate runs. Exceeding either is RESOURCE_EXCEEDED, never a
# crash.
ENCODE_TIMEOUT_S = STANDARD.encode_timeout_s

CHECKER_NAMES = ("drat-trim", "lrat-check", "cake_lpr")


def in_band(band, n_cells: int, m: int) -> bool:
    """True iff (n_cells, m) is inside `band` = ((max_cells, max_m), ...)
    ascending in max_cells (first matching row decides)."""
    for max_cells, max_m in band:
        if n_cells <= max_cells:
            return 1 <= m <= max_m
    return False


def in_harness_band(n_cells: int, m: int) -> bool:
    return in_band(HARNESS_PROOF_BAND, n_cells, m)


# Named bands for the out-of-band record procedure (architecture §13.9):
# `harness` is the STANDARD profile's band (the benchmark job enforces its
# machine-detected profile's band — RECORD on the record runner, so this
# name is a floor, not the job's policy); `encoder` is the encoder's own
# measured feasibility band (what the pipeline will ENCODE at all); `none`
# disables the gate-side band AND the pipeline's feasibility check, for a
# maintainer re-check on a machine without the job's caps. The harness never
# selects anything but `harness` (no env var, no config) — the strict default
# is structural.
BAND_CHOICES = ("harness", "record", "encoder", "none")


def named_band(name: str):
    if name == "harness":
        return HARNESS_PROOF_BAND
    if name == "record":
        return RECORD.harness_band
    if name == "encoder":
        from heesch_encoder.multilevel.api import feasibility_band
        return feasibility_band()
    if name == "none":
        return None
    raise ValueError(f"unknown band {name!r}; choose one of {BAND_CHOICES}")


@dataclasses.dataclass(frozen=True)
class ProofVerdict:
    code: ErrorCode | None      # None == VERIFIED
    detail: str
    m: int = 0
    cnf_digest: str = ""
    proof_sha256: str = ""
    fmt: str = ""
    checkers_verified: tuple = ()
    hh_exact: bool = False
    exact: bool = False
    core_clauses: int = 0
    detected_format: str = ""   # what the bytes were (formats.ProofFormat value)

    def to_json(self) -> dict:
        return {
            "status": "VERIFIED" if self.code is None else self.code.value,
            "detail": self.detail,
            "m": self.m,
            "cnf_digest": self.cnf_digest,
            "proof_sha256": self.proof_sha256,
            "format": self.fmt,
            "format_detected": self.detected_format,
            "checkers_verified": list(self.checkers_verified),
            "hh_exact": self.hh_exact,
            "exact": self.exact,
            "core_clauses": self.core_clauses,
        }


class ProofFileError(Exception):
    def __init__(self, code: ErrorCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _oserror_code(e: OSError) -> ErrorCode:
    """Scratch exhaustion is a resource outcome; any other I/O failure while
    handling a proof file rejects as an invalid proof file (fail closed)."""
    if e.errno in (errno.ENOSPC, getattr(errno, "EDQUOT", errno.ENOSPC)):
        return ErrorCode.RESOURCE_EXCEEDED
    return ErrorCode.PROOF_FILE_INVALID


def _open_regular(path: pathlib.Path) -> int:
    """Open a submission-side file refusing symlinks and non-regular files
    (the same discipline harness/verify.py applies to best.heesch)."""
    try:
        st = os.lstat(path)
    except OSError as e:
        raise ProofFileError(ErrorCode.PROOF_FILE_INVALID, f"cannot stat proof file: {e}")
    if not stat.S_ISREG(st.st_mode):
        raise ProofFileError(ErrorCode.PROOF_FILE_INVALID, "proof file is not a regular file")
    flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
             | getattr(os, "O_BINARY", 0))
    try:
        fd = os.open(path, flags)
    except OSError as e:
        raise ProofFileError(ErrorCode.PROOF_FILE_INVALID, f"cannot open proof file: {e}")
    fst = os.fstat(fd)
    if not stat.S_ISREG(fst.st_mode) or (fst.st_dev, fst.st_ino) != (st.st_dev, st.st_ino):
        os.close(fd)
        raise ProofFileError(ErrorCode.PROOF_FILE_INVALID, "proof file changed under us")
    return fd


def materialize_proof(src: pathlib.Path, dst: pathlib.Path, compression: str,
                      max_stored_bytes: int | None = None,
                      max_payload_bytes: int | None = None) -> tuple[int, str]:
    """Stream the submitted proof into `dst` (decompressing xz with a bounded
    output), returning (payload_bytes, payload_sha256). Raises ProofFileError.
    Caps default to the module constants (STANDARD) so tests can monkeypatch
    them; the gate passes its profile's."""
    if max_stored_bytes is None:
        max_stored_bytes = PROOF_MAX_STORED_BYTES
    if max_payload_bytes is None:
        max_payload_bytes = PROOF_MAX_PAYLOAD_BYTES
    fd = _open_regular(src)
    with os.fdopen(fd, "rb", closefd=True) as fh:
        size = os.fstat(fh.fileno()).st_size
        if size > max_stored_bytes:
            raise ProofFileError(
                ErrorCode.RESOURCE_EXCEEDED,
                f"proof file is {size} bytes (cap {max_stored_bytes})",
            )
        h = hashlib.sha256()
        total = 0
        with open(dst, "wb") as out:
            if compression == "none":
                while True:
                    chunk = fh.read(_CHUNK)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_payload_bytes:
                        raise ProofFileError(
                            ErrorCode.RESOURCE_EXCEEDED,
                            f"proof payload exceeds {max_payload_bytes} bytes",
                        )
                    h.update(chunk)
                    out.write(chunk)
            else:
                dec = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=_XZ_MEMLIMIT)
                try:
                    while True:
                        chunk = fh.read(_CHUNK)
                        if not chunk and dec.needs_input:
                            break
                        data = dec.decompress(chunk, max_length=_CHUNK)
                        while True:
                            total += len(data)
                            if total > max_payload_bytes:
                                raise ProofFileError(
                                    ErrorCode.RESOURCE_EXCEEDED,
                                    f"decompressed proof exceeds {max_payload_bytes} bytes",
                                )
                            h.update(data)
                            out.write(data)
                            if dec.needs_input or dec.eof:
                                break
                            data = dec.decompress(b"", max_length=_CHUNK)
                        if dec.eof:
                            break
                except lzma.LZMAError as e:
                    raise ProofFileError(ErrorCode.PROOF_FILE_INVALID, f"xz: {e}")
                if not dec.eof:
                    raise ProofFileError(ErrorCode.PROOF_FILE_INVALID, "xz stream truncated")
                if dec.unused_data or fh.read(1):
                    raise ProofFileError(ErrorCode.PROOF_FILE_INVALID,
                                         "trailing data after the xz stream")
    return total, h.hexdigest()


class ProofCarryingGate:
    """Enforced non-tiler proof gate. `submission_dir` is the directory that
    holds best.heesch and the proof file it names; `checker_dir` holds the
    vendored checker binaries."""

    _BAND_UNSET = object()

    def __init__(self, submission_dir, checker_dir, budget=None, band=_BAND_UNSET,
                 profile: ResourceProfile = STANDARD):
        self.submission_dir = pathlib.Path(submission_dir)
        self.checker_dir = pathlib.Path(checker_dir)
        self.budget = budget
        # Every budget comes from `profile` (heesch_verify/profile.py); the
        # harness passes profile.detect() — derived from the machine, never
        # from a participant input. `band` overrides the profile's band for
        # the maintainer CLI (`--band`): a (cells, max m) tuple, or None = no
        # gate band and no encoder feasibility band either (§13.9).
        self.profile = profile
        self.band = profile.harness_band if band is self._BAND_UNSET else band

    def missing_checkers(self) -> list[str]:
        """Names of checkers that are not regular, executable files in
        checker_dir (the same predicate checkers._run applies at spawn)."""
        from heesch_encoder.proofcheck.checkers import checker_path, checker_problem

        return [name for name in CHECKER_NAMES
                if checker_problem(checker_path(name, self.checker_dir)) is not None]

    def check(self, sub, outcome) -> ProofVerdict:
        block = sub.proof
        hc, hh = outcome.result.hc_verified, outcome.result.hh_verified
        m = block.m
        # 1. Level rule.
        if m < hh + 1:
            return ProofVerdict(
                ErrorCode.PROOF_LEVEL_INCONSISTENT,
                f"F(S,{m}) UNSAT would give Hh <= {m - 1} but the witness verifies "
                f"hh = {hh}; the proof must be for m >= {hh + 1}",
                m=m,
            )
        hh_exact = (m - 1 == hh)
        exact = hh_exact and hc == hh
        # 2. Checker preflight — fail closed before touching the proof.
        missing = self.missing_checkers()
        if missing:
            return ProofVerdict(
                ErrorCode.CHECKER_UNAVAILABLE,
                "proof checkers not available: " + ", ".join(missing)
                + f" (looked in {self.checker_dir})",
                m=m,
            )
        # 3. Bands.
        n_cells = len(sub.cells)
        if self.band is not None and not in_band(self.band, n_cells, m):
            which = (f"in-harness ({self.profile.name} profile)"
                     if self.band == self.profile.harness_band else "selected")
            return ProofVerdict(
                ErrorCode.RESOURCE_EXCEEDED,
                f"({n_cells} cells, m={m}) is outside the {which} proof band "
                f"{tuple(self.band)}",
                m=m,
            )
        # 3b. Scratch disk: the regenerated DIMACS (up to ~110 B/clause) plus
        # the payload land in TMPDIR; refuse cleanly rather than ENOSPC mid-way.
        from .profile import scratch_free_bytes

        free = scratch_free_bytes()
        if free is not None and free < self.profile.min_scratch_bytes:
            return ProofVerdict(
                ErrorCode.RESOURCE_EXCEEDED,
                f"scratch disk has {free >> 30} GiB free; the {self.profile.name} "
                f"profile needs {self.profile.min_scratch_bytes >> 30} GiB",
                m=m,
            )
        # 4. Materialize the proof file into scratch.
        src = self.submission_dir / block.file_name
        scratch = pathlib.Path(tempfile.mkdtemp(prefix="heesch-proof-"))
        try:
            dst = scratch / f"proof.{block.fmt}"
            try:
                _, payload_sha = materialize_proof(
                    src, dst, block.compression,
                    self.profile.proof_max_stored_bytes, self.profile.proof_max_payload_bytes)
            except ProofFileError as e:
                return ProofVerdict(e.code, e.message, m=m)
            except OSError as e:
                # Write-side failure (ENOSPC/EDQUOT/EIO on scratch while
                # decompressing): a structured rejection, never a traceback.
                return ProofVerdict(_oserror_code(e), f"materializing proof failed: {e}", m=m)
            if payload_sha != block.payload_sha256:
                return ProofVerdict(
                    ErrorCode.PROOF_FILE_DIGEST_MISMATCH,
                    f"proof payload sha256 {payload_sha[:16]}… != declared "
                    f"{block.payload_sha256[:16]}…",
                    m=m,
                )
            # 5. Regenerate F(S, m) and run the frozen check order.
            from heesch_encoder.proofcheck.pipeline import (
                ProofStatus, ProofSubmission, Tier, check_proof_v2,
            )

            core_dst = None
            if block.core_file is not None:
                core_src = self.submission_dir / block.core_file
                core_dst = scratch / "core.txt"
                try:
                    _, core_sha = materialize_proof(
                        core_src, core_dst, block.core_compression,
                        self.profile.proof_max_stored_bytes, self.profile.proof_max_payload_bytes)
                except ProofFileError as e:
                    return ProofVerdict(e.code, "core: " + e.message, m=m)
                except OSError as e:
                    return ProofVerdict(_oserror_code(e), f"materializing core failed: {e}", m=m)
                if core_sha != block.core_sha256:
                    return ProofVerdict(
                        ErrorCode.PROOF_FILE_DIGEST_MISMATCH,
                        f"core payload sha256 {core_sha[:16]}… != declared {block.core_sha256[:16]}…",
                        m=m,
                    )
            psub = ProofSubmission(
                proof_path=str(dst),
                claimed_cnf_digest=block.cnf_digest,
                claimed_vars=block.num_vars,
                claimed_clauses=block.num_clauses,
                claimed_core_clauses=block.core_clauses,
                declared_format=block.fmt,
            )
            tile = frozenset(canonical_form(sub.cells, sub.grid, True))
            out = check_proof_v2(
                psub, tile, sub.grid, outcome.contact, m,
                tier=Tier.RECORD, timeout=float(self.profile.checker_deadline_s),
                bin_dir=self.checker_dir, budget=self.budget,
                core_path=(str(core_dst) if core_dst is not None else None),
                encode_timeout_s=self.profile.encode_timeout_s,
                enforce_band=self.band is not None,
                max_proof_bytes=self.profile.max_proof_bytes,
                core_max_clauses=self.profile.core_max_clauses,
                core_max_bytes=self.profile.core_max_bytes,
                cake_heap_max_mb=self.profile.cake_heap_max_mb,
            )
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

        if out.status is not ProofStatus.VERIFIED:
            return ProofVerdict(
                ErrorCode(out.status.value), out.detail, m=m,
                cnf_digest=out.cnf_digest, proof_sha256=payload_sha, fmt=block.fmt,
                detected_format=out.detected_format,
            )
        verified = tuple(sorted(
            r.checker for r in out.checker_results if r.status.value == "VERIFIED"
        ))
        return ProofVerdict(
            None, out.detail, m=m, cnf_digest=out.cnf_digest,
            proof_sha256=payload_sha, fmt=block.fmt, checkers_verified=verified,
            hh_exact=hh_exact, exact=exact, core_clauses=out.core_clauses,
            detected_format=out.detected_format,
        )
