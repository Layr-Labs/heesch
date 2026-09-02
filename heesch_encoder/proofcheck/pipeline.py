"""The frozen proof-check order of operations (encoder spec §8, arch §13.3):

1. Regenerate the CNF server-side from the shape + verified patch.
2. Digest match — BEFORE any submitted proof byte is parsed, sniffed or
   handed to a checker. (The harness gate has already streamed, decompressed
   and hashed the payload to scratch under fixed size caps before step 1 —
   regenerating F(S, m) is the expensive step, so the cheap bounded
   materialisation runs first; see architecture §13.3 and THREAT-MODEL A-3.)
3. Header var/clause counts match.
4. Size gate.
5. Format sniff on a bounded window; reject SAT models and empty files.
6. Dispatch to checkers; record tier requires TWO independent VERIFIED
   verdicts (a formally verified checker plus drat-trim/lrat-check).

Two encoders feed the same steps 2-6:

* v1 `check_proof` — F_v1(S, P_k), one submitted patch. UNSAT there proves
  only that THAT patch has no hole-allowed corona k+1; the inference to
  Hh <= k is sound only at k = 0 (docs/soundness-note.md, E8).
* v2 `check_proof_v2` — the multilevel F(S, m). UNSAT verified means no weak
  m-configuration exists over ALL patches, so Hh <= m-1 and the shape is not
  a tiler; with a verified witness hh = m-1 the value is exact (multilevel
  spec §2.2). This is the path the harness enforces (arch §2.2/§13).

A SAT outcome is EXACT_UNDECIDED_HOLE_CASE — an honest "not yet", never
shown as a failure (spec §5).
"""

from __future__ import annotations

import enum
import hashlib
import os
import tempfile
from dataclasses import dataclass, field

from ..api import encode
from . import checkers as ck
from .formats import ProofFormat, sniff, tail_wellformed

MAX_PROOF_BYTES = 8 * 1024**3  # 8 GiB size gate; oversized -> requeue out-of-band


class Tier(str, enum.Enum):
    TRIAGE = "triage"
    RECORD = "record"


class ProofStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    PROOF_CNF_DIGEST_MISMATCH = "PROOF_CNF_DIGEST_MISMATCH"
    PROOF_HEADER_MISMATCH = "PROOF_HEADER_MISMATCH"
    PROOF_TRUNCATED = "PROOF_TRUNCATED"
    GATE_PROOF_INVALID = "GATE_PROOF_INVALID"
    RESOURCE_EXCEEDED = "RESOURCE_EXCEEDED"
    CHECKER_UNAVAILABLE = "CHECKER_UNAVAILABLE"


@dataclass(frozen=True)
class ProofOutcome:
    status: ProofStatus
    detail: str = ""
    cnf_digest: str = ""
    encoder_vars: int = 0
    encoder_clauses: int = 0
    cnf_bytes: int = 0
    proof_bytes: int = 0
    check_seconds: float = 0.0
    checker_results: tuple = field(default_factory=tuple)
    core_clauses: int = 0          # > 0 when the checkers ran on a verified core subset
    detected_format: str = ""      # formats.ProofFormat.value sniffed from the bytes


def format_class(fmt: ProofFormat) -> str:
    """The submission-schema class ("drat" | "lrat") of a sniffed format, or
    "" when the bytes are not a proof at all."""
    if fmt in (ProofFormat.DRAT_TEXT, ProofFormat.DRAT_BINARY):
        return "drat"
    if fmt is ProofFormat.LRAT_TEXT:
        return "lrat"
    return ""


@dataclass(frozen=True)
class ProofSubmission:
    proof_path: str
    claimed_cnf_digest: str
    claimed_vars: int
    claimed_clauses: int
    claimed_core_clauses: int = 0   # with a core list: its declared clause count
    # The format the submitter DECLARED ("drat" | "lrat"; "" = unchecked, for
    # library callers). The pipeline dispatches on the sniffed bytes, so a
    # mismatch is rejected rather than silently re-routed and misreported
    # (audit 2026-08-19 Medium 4).
    declared_format: str = ""


def _has_empty_clause(dimacs: bytes) -> bool:
    """True iff the DIMACS body contains the empty clause — a standalone '0'
    clause line (audit F5). Comments ('c'), the header ('p ...') and any clause
    with literals are excluded, so this only fires on a genuine contradiction."""
    for raw in dimacs.split(b"\n"):
        line = raw.strip()
        if not line or line[:1] in (b"c", b"p"):
            continue
        if line.split() == [b"0"]:
            return True
    return False


def store_proof(path: str, store_dir: str) -> str:
    """Content-addressed sidecar storage; hashing streams in 1 MiB chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    digest = h.hexdigest()
    dest_dir = os.path.join(store_dir, digest[:2])
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, digest)
    if not os.path.exists(dest):
        os.replace(path, dest) if os.path.dirname(path) == dest_dir else _copy(path, dest)
    return digest


def _copy(src, dst):
    with open(src, "rb") as a, open(dst, "wb") as b:
        while True:
            chunk = a.read(1024 * 1024)
            if not chunk:
                break
            b.write(chunk)


def check_proof(sub: ProofSubmission, tile_cells, patch_cells, grid, contact,
                tier: Tier = Tier.RECORD, timeout: float = 3600.0) -> ProofOutcome:
    """v1 path: regenerate F_v1(S, P_k) then run the frozen steps 2-6."""
    enc = encode(tile_cells, patch_cells, grid, contact)
    return check_proof_encoded(sub, enc, tier=tier, timeout=timeout)


def check_proof_v2(sub: ProofSubmission, tile_cells, grid, contact, m: int,
                   tier: Tier = Tier.RECORD, timeout: float = 3600.0,
                   bin_dir=None, budget=None, core_path=None,
                   encode_timeout_s: float | None = None,
                   enforce_band: bool = True,
                   max_proof_bytes: int | None = None,
                   core_max_clauses: int | None = None,
                   core_max_bytes: int | None = None,
                   cake_heap_max_mb: int | None = None) -> ProofOutcome:
    """v2 path: regenerate the multilevel F(S, m) then the same frozen
    steps. UNSAT verified here means no weak m-configuration exists —
    Hh <= m-1 over ALL patches (multilevel spec §2.2).

    The feasibility band (multilevel spec §10.2, measured policy) is enforced BEFORE
    encoding: outside it the answer is RESOURCE_EXCEEDED by policy, so the
    server never starts an encoding it cannot finish.

    `encode_timeout_s` bounds ONLY the in-process encoding step (guard.py);
    it is additionally clipped to the budget's remaining time. The checkers
    are bounded by `budget` (CheckBudget caps + overall deadline), never by
    this guard — audit 2026-08-19 Medium 5.

    `enforce_band=False` skips the feasibility-band policy (the out-of-band
    record re-check of architecture §13.9, run by a maintainer on a machine
    without the job's caps). The harness never passes it.

    `max_proof_bytes` / `core_max_*` / `cake_heap_max_mb`: the resource
    profile's caps (heesch_verify/profile.py); None = the module defaults."""
    import math
    import time

    from ..multilevel.api import encode_multilevel_stream, in_feasibility_band
    from .guard import EncodeTimeout, wall_clock_guard

    n_cells = len(frozenset(tile_cells))
    if enforce_band and not in_feasibility_band(n_cells, m):
        return ProofOutcome(
            ProofStatus.RESOURCE_EXCEEDED,
            f"({n_cells} cells, m={m}) is outside the encoder feasibility band",
        )
    limit = math.inf if encode_timeout_s is None else float(encode_timeout_s)
    if budget is not None:
        limit = min(limit, budget.deadline - time.monotonic())
    if limit <= 0:
        return ProofOutcome(ProofStatus.RESOURCE_EXCEEDED,
                            "proof-check deadline exhausted before encoding")
    # Stream the regenerated CNF to scratch: peak memory is then the universe,
    # not the formula (F(S,6) of an 11-cell shape is 17M clauses / 2 GB, and
    # materialising it took ~15 GB).
    with tempfile.TemporaryDirectory(prefix="heesch-cnf-") as td:
        deadline = None if limit == math.inf else time.monotonic() + limit
        try:
            with wall_clock_guard(limit):
                enc = encode_multilevel_stream(tile_cells, grid, contact, m,
                                               os.path.join(td, "regenerated.cnf"),
                                               deadline=deadline)
        except EncodeTimeout:
            return ProofOutcome(
                ProofStatus.RESOURCE_EXCEEDED,
                f"encoding F(S,{m}) for {n_cells} cells exceeded {limit:.0f} s",
            )
        except OSError as e:
            # ENOSPC / EIO while streaming the DIMACS to scratch: a resource
            # outcome, never a traceback (Plan 3 P3).
            return ProofOutcome(ProofStatus.RESOURCE_EXCEEDED,
                                f"encoding F(S,{m}) failed writing scratch: {e}")
        return check_proof_encoded(sub, enc, tier=tier, timeout=timeout,
                                   bin_dir=bin_dir, budget=budget, core_path=core_path,
                                   max_proof_bytes=max_proof_bytes,
                                   core_max_clauses=core_max_clauses,
                                   core_max_bytes=core_max_bytes,
                                   cake_heap_max_mb=cake_heap_max_mb)


def check_proof_encoded(sub: ProofSubmission, enc, tier: Tier = Tier.RECORD,
                        timeout: float = 3600.0, bin_dir=None, budget=None,
                        core_path=None, max_proof_bytes: int | None = None,
                        core_max_clauses: int | None = None,
                        core_max_bytes: int | None = None,
                        cake_heap_max_mb: int | None = None) -> ProofOutcome:
    """Steps 2-6 of the frozen order, schema-blind: works for any encoding
    object exposing digest/num_vars/num_clauses/dimacs. `bin_dir` locates the
    checker binaries (see checkers._BIN); `budget` is a checkers.CheckBudget.
    The encoding is either in memory (`dimacs` bytes) or streamed
    (`write_dimacs(path)`, `cnf_bytes`, `has_empty_clause`).
    `core_path` (LRAT only): a submitter-supplied clause list; every clause is
    checked to be a clause of the regenerated formula (proofcheck.core) and
    the checkers then run on that verified subset — step 5b."""
    streamed = not hasattr(enc, "dimacs")
    if max_proof_bytes is None:
        max_proof_bytes = MAX_PROOF_BYTES
    cnf_bytes = enc.cnf_bytes if streamed else len(enc.dimacs)
    empty_clause = enc.has_empty_clause if streamed else _has_empty_clause(enc.dimacs)
    # 2. Digest match before touching the proof.
    if enc.digest != sub.claimed_cnf_digest:
        return ProofOutcome(
            ProofStatus.PROOF_CNF_DIGEST_MISMATCH,
            f"claimed {sub.claimed_cnf_digest[:16]}…, regenerated {enc.digest[:16]}…",
            cnf_digest=enc.digest,
        )
    # 3. Header counts.
    if (sub.claimed_vars, sub.claimed_clauses) != (enc.num_vars, enc.num_clauses):
        return ProofOutcome(
            ProofStatus.PROOF_HEADER_MISMATCH,
            f"claimed {sub.claimed_vars}v/{sub.claimed_clauses}c, "
            f"regenerated {enc.num_vars}v/{enc.num_clauses}c",
            cnf_digest=enc.digest,
        )
    # 3b. Argv-injection guard (audit F3). A proof path whose basename begins
    # with '-' is read by the checker as a flag: drat-trim -S forges a proof
    # from stdin, -D deletes it. store_proof's digest basenames are immune, but
    # a direct/operator-wired path is not — reject it before any checker runs.
    if os.path.basename(sub.proof_path).startswith("-"):
        return ProofOutcome(
            ProofStatus.GATE_PROOF_INVALID,
            "proof path basename may not begin with '-'",
            cnf_digest=enc.digest,
        )
    # 4. Size gate.
    try:
        proof_bytes = os.stat(sub.proof_path).st_size
    except OSError as e:
        return ProofOutcome(ProofStatus.GATE_PROOF_INVALID, str(e), cnf_digest=enc.digest)
    if proof_bytes > max_proof_bytes:
        return ProofOutcome(
            ProofStatus.RESOURCE_EXCEEDED,
            f"proof is {proof_bytes} bytes (cap {max_proof_bytes})",
            cnf_digest=enc.digest, proof_bytes=proof_bytes,
        )
    # 5. Sniff (bounded windows only).
    fmt = sniff(sub.proof_path)
    if fmt in (ProofFormat.EMPTY, ProofFormat.UNKNOWN):
        return ProofOutcome(ProofStatus.GATE_PROOF_INVALID, f"unrecognized proof ({fmt.value})",
                            cnf_digest=enc.digest, proof_bytes=proof_bytes)
    if fmt is ProofFormat.SAT_MODEL:
        return ProofOutcome(
            ProofStatus.GATE_PROOF_INVALID,
            "a SAT model is not an UNSAT proof",
            cnf_digest=enc.digest, proof_bytes=proof_bytes,
        )
    if sub.declared_format and sub.declared_format != format_class(fmt):
        return ProofOutcome(
            ProofStatus.GATE_PROOF_INVALID,
            f"declared format {sub.declared_format!r} but the file is {fmt.value}",
            cnf_digest=enc.digest, proof_bytes=proof_bytes, detected_format=fmt.value,
        )
    if fmt in (ProofFormat.DRAT_TEXT, ProofFormat.LRAT_TEXT) and not tail_wellformed(sub.proof_path):
        return ProofOutcome(ProofStatus.PROOF_TRUNCATED, "proof does not end on a terminated line",
                            cnf_digest=enc.digest, proof_bytes=proof_bytes, detected_format=fmt.value)
    if core_path is not None and fmt is not ProofFormat.LRAT_TEXT:
        return ProofOutcome(ProofStatus.GATE_PROOF_INVALID,
                            "a core clause list is only valid with an LRAT proof",
                            cnf_digest=enc.digest, proof_bytes=proof_bytes, detected_format=fmt.value)

    # 6. Checkers.
    with tempfile.TemporaryDirectory() as td:
        if streamed and getattr(enc, "path", None) and os.path.exists(enc.path):
            # The streamed DIMACS already sits in check_proof_v2's scratch
            # (still open); a second multi-GB copy bought nothing (Plan 3 P3).
            cnf_path = enc.path
        else:
            cnf_path = os.path.join(td, "formula.cnf")
            try:
                if streamed:
                    enc.write_dimacs(cnf_path)
                else:
                    with open(cnf_path, "wb") as fh:
                        fh.write(enc.dimacs)
            except OSError as e:
                # ENOSPC/EIO copying the multi-GB CNF into checker scratch:
                # a resource outcome, never a traceback.
                return ProofOutcome(ProofStatus.RESOURCE_EXCEEDED,
                                    f"writing the regenerated CNF to scratch failed: {e}",
                                    cnf_digest=enc.digest, proof_bytes=proof_bytes)
        core_clauses = 0
        if core_path is not None:
            # 5b. Core subset: exact membership against F, then the checkers
            # run on the core CNF WE write from F's own lines.
            from . import core as core_mod

            try:
                core_lines = core_mod.parse_core_file(
                    core_path, max_clauses=core_max_clauses, max_bytes=core_max_bytes)
                core_res = core_mod.check_and_write_core(
                    core_lines, cnf_path, enc.num_vars, os.path.join(td, "core.cnf"))
            except core_mod.CoreError as e:
                return ProofOutcome(ProofStatus[e.code], "core: " + e.message,
                                    cnf_digest=enc.digest, proof_bytes=proof_bytes)
            except (OSError, ValueError) as e:
                # Second net: parse_core_file already maps decode/IO errors
                # to CoreError; anything that still escapes is a structured
                # rejection, never a traceback (audit 2026-08-19 Medium 3).
                return ProofOutcome(ProofStatus.GATE_PROOF_INVALID, f"core: {e}",
                                    cnf_digest=enc.digest, proof_bytes=proof_bytes)
            core_clauses = core_res.num_clauses
            if sub.claimed_core_clauses and sub.claimed_core_clauses != core_clauses:
                return ProofOutcome(ProofStatus.PROOF_HEADER_MISMATCH,
                                    f"core declares {sub.claimed_core_clauses} clauses, "
                                    f"file has {core_clauses}",
                                    cnf_digest=enc.digest, proof_bytes=proof_bytes)
            cnf_path = core_res.core_cnf_path

        # Record tier needs two independent VERIFIED verdicts, and one of them
        # MUST come from the formally-verified checker (cake_lpr). lrat-check is
        # never substituted for that slot (audit F2) — it is not formally
        # verified and (audit F1) is vacuously forgeable (`N 0 0` -> `c
        # VERIFIED` on any formula), so a record must never rest on it. If
        # cake_lpr is absent, a missing-checker result forces CHECKER_UNAVAILABLE
        # below rather than silently downgrading the trust boundary.
        results = []
        if fmt in (ProofFormat.DRAT_TEXT, ProofFormat.DRAT_BINARY):
            lrat_out = os.path.join(td, "converted.lrat")
            r1 = ck.drat_trim(cnf_path, sub.proof_path, emit_lrat=lrat_out,
                              timeout=timeout, bin_dir=bin_dir, budget=budget)
            results.append(r1)
            if tier is Tier.RECORD and r1.status is ck.CheckStatus.VERIFIED:
                # Formally-verified slot: cake_lpr only, over the LRAT drat-trim
                # emitted. No lrat-check fallback.
                results.append(ck.cake_lpr(cnf_path, lrat_out, timeout=timeout,
                                           bin_dir=bin_dir, budget=budget,
                                           heap_max_mb=cake_heap_max_mb))
        elif tier is Tier.RECORD:  # LRAT_TEXT, record tier
            # cake_lpr is the formally-verified primary; lrat-check backs it as
            # the second independent verdict only after cake_lpr VERIFIED.
            r_fv = ck.cake_lpr(cnf_path, sub.proof_path, timeout=timeout,
                               bin_dir=bin_dir, budget=budget, heap_max_mb=cake_heap_max_mb)
            results.append(r_fv)
            if r_fv.status is ck.CheckStatus.VERIFIED:
                results.append(ck.lrat_check(cnf_path, sub.proof_path, timeout=timeout,
                                             bin_dir=bin_dir, budget=budget))
        else:  # LRAT_TEXT, triage tier — any available checker suffices
            r1 = ck.cake_lpr(cnf_path, sub.proof_path, timeout=timeout,
                             bin_dir=bin_dir, budget=budget, heap_max_mb=cake_heap_max_mb)
            if r1.status is ck.CheckStatus.CHECKER_MISSING:
                r1 = ck.lrat_check(cnf_path, sub.proof_path, timeout=timeout,
                                   bin_dir=bin_dir, budget=budget)
            results.append(r1)

    seconds = sum(r.seconds for r in results)

    if any(r.status is ck.CheckStatus.CHECKER_MISSING for r in results):
        # F5: a formula carrying the empty clause is UNSAT with Python-level
        # certainty (no SAT reasoning needed), so an honest trivially-UNSAT
        # record stays recordable even when the formal checker is unavailable —
        # equivalent to synthesizing the one-line empty-clause LRAT and having
        # the checker confirm it. This never grants a record the geometry does
        # not, because the empty clause IS the contradiction.
        if empty_clause:
            return ProofOutcome(
                ProofStatus.VERIFIED,
                "trivial UNSAT: regenerated formula contains the empty clause "
                "(checker-independent)",
                cnf_digest=enc.digest, encoder_vars=enc.num_vars,
                encoder_clauses=enc.num_clauses, cnf_bytes=cnf_bytes,
                proof_bytes=proof_bytes, check_seconds=seconds,
                checker_results=tuple(results), detected_format=fmt.value,
            )
        return ProofOutcome(ProofStatus.CHECKER_UNAVAILABLE,
                            "; ".join(f"{r.checker}: {r.detail}" for r in results),
                            cnf_digest=enc.digest, proof_bytes=proof_bytes,
                            checker_results=tuple(results), detected_format=fmt.value, check_seconds=seconds)
    if any(r.status is ck.CheckStatus.RESOURCE_EXCEEDED for r in results):
        return ProofOutcome(ProofStatus.RESOURCE_EXCEEDED,
                            "checker resource limit: " + "; ".join(
                                f"{r.checker} {r.status.value} after {r.seconds:.0f}s"
                                + (f" ({r.detail[:160]})" if r.detail else "") for r in results),
                            cnf_digest=enc.digest, proof_bytes=proof_bytes,
                            checker_results=tuple(results), detected_format=fmt.value, check_seconds=seconds)

    need = 2 if tier is Tier.RECORD else 1
    verified = [r for r in results if r.status is ck.CheckStatus.VERIFIED]
    if len(verified) >= need:
        return ProofOutcome(
            ProofStatus.VERIFIED,
            f"{len(verified)} checker(s): " + ", ".join(r.checker for r in verified),
            cnf_digest=enc.digest, encoder_vars=enc.num_vars,
            encoder_clauses=enc.num_clauses, cnf_bytes=cnf_bytes,
            proof_bytes=proof_bytes, check_seconds=seconds,
            checker_results=tuple(results), detected_format=fmt.value, core_clauses=core_clauses,
        )
    return ProofOutcome(
        ProofStatus.GATE_PROOF_INVALID,
        "; ".join(f"{r.checker}: {r.status.value} {r.detail[:120]}" for r in results),
        cnf_digest=enc.digest, proof_bytes=proof_bytes,
        checker_results=tuple(results), detected_format=fmt.value, check_seconds=seconds,
    )
