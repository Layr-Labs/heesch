"""Canonical DIMACS emission and digest (spec §6). Byte-identical output is a
correctness requirement: the server regenerates and hash-matches before any
proof is checked. No hash-order iteration reaches this path; clauses arrive
already fully ordered from clauses.py."""

from __future__ import annotations

import hashlib

from .types import Formula


def emit_dimacs(formula: Formula) -> bytes:
    parts = [f"p cnf {formula.num_vars} {len(formula.clauses)}\n"]
    for cl in formula.clauses:
        if cl:
            parts.append(" ".join(str(l) for l in cl) + " 0\n")
        else:
            parts.append("0\n")
    return "".join(parts).encode("ascii")


def cnf_digest(dimacs: bytes) -> str:
    return hashlib.sha256(dimacs).hexdigest()
