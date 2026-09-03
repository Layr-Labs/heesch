"""Core-CNF proof checking (architecture §13.3 step 5b).

A refutation of a SUBSET C of the regenerated formula F refutes F: every
model of F satisfies C, so C unsatisfiable ⇒ F unsatisfiable, for RUP and
RAT steps alike (RAT preserves satisfiability of C; the conclusion does not
depend on F). The submitter may therefore hand the checker only the clauses
the proof actually uses — typically a few percent of F (measured 3.5 % for
an F(S,6) instance) — which is what makes record-scale checking fit the
formally-verified checker's heap.

Soundness rests on ONE thing we do here: every clause of C must be, exactly,
a clause of F. So

  * the submitter's core file is parsed with a strict grammar (one clause
    per line, integers, 0-terminated, no comments) and each clause is
    canonicalised (duplicate literals removed, literals in the encoder's
    frozen order — heesch_encoder.ordering.literal_key, the order F itself is
    emitted in);
  * membership is EXACT string equality against F's own DIMACS lines,
    streamed once (no hashing, no probabilistic structure);
  * the checker never sees the submitter's bytes: the core CNF handed to it
    is written by us and consists solely of F's own lines, in the
    submitter's chosen order (their LRAT ids are positions in that order),
    under a header naming F's variable count.

Any clause not found, any tautology, any grammar deviation ⇒ the proof is
rejected before a checker runs. Caps bound the work (a core as large as F
buys nothing and is refused).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..ordering import literal_key

CORE_MAX_CLAUSES = 4_000_000
CORE_MAX_BYTES = 512 * 1024 * 1024
_MAX_LINE = 1_000_000


class CoreError(Exception):
    """Core file rejected; `code` is one of the ProofStatus names."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CoreResult:
    core_cnf_path: str
    num_clauses: int
    formula_clauses: int


def canonical_clause_line(lits) -> str:
    """The exact text F uses for this clause: literals deduplicated, sorted by
    the frozen literal order, space-joined, `0`-terminated (empty clause →
    "0")."""
    uniq = sorted(set(lits), key=literal_key)
    if not uniq:
        return "0"
    return " ".join(str(l) for l in uniq) + " 0"


def parse_core_file(path: str, max_clauses: int | None = None,
                    max_bytes: int | None = None) -> list[str]:
    """Strict grammar → list of canonical clause lines (submitter order).
    Every rejection is a CoreError: the submitter-controlled bytes may be
    non-ASCII or unreadable (audit 2026-08-19 Medium 3) and that must be a
    structured GATE_PROOF_INVALID, never a UnicodeDecodeError/OSError out of
    the gate. `max_clauses` / `max_bytes`: the resource profile's caps
    (default: the module constants)."""
    try:
        return _parse_core_file_strict(
            path,
            CORE_MAX_CLAUSES if max_clauses is None else max_clauses,
            CORE_MAX_BYTES if max_bytes is None else max_bytes,
        )
    except UnicodeDecodeError as e:
        raise CoreError("GATE_PROOF_INVALID",
                        f"core file is not ASCII text (byte {e.start}: {e.reason})") from None
    except OSError as e:
        raise CoreError("GATE_PROOF_INVALID", f"core file unreadable: {e.strerror or e}") from None


def _parse_core_file_strict(path: str, max_clauses: int, max_bytes: int) -> list[str]:
    size = os.stat(path).st_size
    if size > max_bytes:
        raise CoreError("RESOURCE_EXCEEDED", f"core file is {size} bytes (cap {max_bytes})")
    out: list[str] = []
    with open(path, "r", encoding="ascii", errors="strict") as fh:
        for lineno, raw in enumerate(fh, 1):
            if len(raw) > _MAX_LINE:
                raise CoreError("GATE_PROOF_INVALID", f"core line {lineno} too long")
            line = raw.strip()
            if not line:
                continue
            if line[0] in "cp":
                raise CoreError("GATE_PROOF_INVALID",
                                f"core line {lineno}: comments/headers are not allowed")
            toks = line.split()
            try:
                vals = [int(t) for t in toks]
            except ValueError:
                raise CoreError("GATE_PROOF_INVALID", f"core line {lineno}: non-integer token")
            if not vals or vals[-1] != 0 or any(v == 0 for v in vals[:-1]):
                raise CoreError("GATE_PROOF_INVALID",
                                f"core line {lineno}: clause must be literals then a single 0")
            lits = vals[:-1]
            if any(-l in lits for l in lits):
                raise CoreError("GATE_PROOF_INVALID",
                                f"core line {lineno}: tautology is never a clause of F")
            out.append(canonical_clause_line(lits))
            if len(out) > max_clauses:
                raise CoreError("RESOURCE_EXCEEDED",
                                f"core has more than {max_clauses} clauses")
    if not out:
        raise CoreError("GATE_PROOF_INVALID", "core file has no clauses")
    return out


def check_and_write_core(core_lines: list[str], formula_cnf_path: str, num_vars: int,
                         out_path: str, budget=None) -> CoreResult:
    """Verify every core clause is a line of F (streamed, exact) and write the
    core CNF for the checker from F's own lines in the submitter's order."""
    needed = set(core_lines)
    # `found` holds the CORE's own string objects (hash-equal to F's line), so
    # a 30 M-clause core costs one str per clause, not two (Plan 3 P3).
    found: set = set()
    formula_clauses = 0
    try:
        return _check_and_write_core(core_lines, needed, found, formula_clauses,
                                     formula_cnf_path, num_vars, out_path, budget)
    except (UnicodeDecodeError, OSError) as e:
        # F is our own streamed DIMACS; a read/write failure here is a
        # server-side resource problem, not a verdict on the proof.
        raise CoreError("RESOURCE_EXCEEDED", f"core check I/O failure: {e}") from None


def _check_and_write_core(core_lines, needed, found, formula_clauses,
                          formula_cnf_path, num_vars, out_path, budget=None) -> CoreResult:
    with open(formula_cnf_path, "r", encoding="ascii", errors="strict") as fh:
        header = fh.readline()
        if not header.startswith("p cnf "):
            raise CoreError("GATE_PROOF_INVALID", "regenerated CNF header malformed")
        for raw in fh:
            formula_clauses += 1
            # A record-scale F stream is ~150 M lines; keep the scan under
            # the shared deadline so it rejects cleanly rather than running
            # into the platform's job kill (2026-09-03 rebalance).
            if budget is not None and formula_clauses % 1_000_000 == 0 and budget.remaining() <= 0:
                raise CoreError("RESOURCE_EXCEEDED",
                                "proof-check deadline exhausted during the core membership scan")
            line = raw[:-1] if raw.endswith("\n") else raw
            if line in needed and line not in found:
                found.add(line)
                if len(found) == len(needed):
                    # Keep counting lines is unnecessary once every core
                    # clause is located; the header count is authoritative.
                    break
    missing = [c for c in core_lines if c not in found]
    if missing:
        raise CoreError(
            "GATE_PROOF_INVALID",
            f"{len(missing)} core clause(s) are not clauses of the regenerated formula "
            f"(first: {missing[0][:80]!r})",
        )
    with open(out_path, "w", encoding="ascii", newline="\n") as out:
        out.write(f"p cnf {num_vars} {len(core_lines)}\n")
        for line in core_lines:
            out.write(line)
            out.write("\n")
    return CoreResult(core_cnf_path=out_path, num_clauses=len(core_lines),
                      formula_clauses=formula_clauses)
