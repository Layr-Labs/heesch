"""Bounded-window proof format sniffing. Python never reads a proof body —
only os.stat, a head window, and a tail window (multi-GB proofs stream
through the checkers, not through us)."""

from __future__ import annotations

import enum
import os

HEAD_WINDOW = 64 * 1024
TAIL_WINDOW = 4 * 1024


class ProofFormat(str, enum.Enum):
    DRAT_TEXT = "drat-text"
    DRAT_BINARY = "drat-binary"
    LRAT_TEXT = "lrat-text"
    SAT_MODEL = "sat-model"      # someone submitted a model, not a proof
    EMPTY = "empty"
    UNKNOWN = "unknown"


def sniff(path: str) -> ProofFormat:
    size = os.stat(path).st_size
    if size == 0:
        return ProofFormat.EMPTY
    with open(path, "rb") as fh:
        head = fh.read(min(HEAD_WINDOW, size))
    if not head.strip():
        return ProofFormat.EMPTY

    # Binary DRAT: drat-trim's binary format starts each lemma with 'a'
    # (0x61) or 'd' (0x64) and uses bytes >= 0x80 in literals; presence of
    # non-printable non-whitespace bytes is the signal.
    printable = set(b"0123456789- dat\r\n\t")
    if any(b not in printable for b in head[:4096]):
        # allow 'c'/'s'/'v' checks below to classify text files with headers
        if not head[:1] in (b"c", b"s", b"v", b"p"):
            return ProofFormat.DRAT_BINARY

    text = head.decode("latin-1", errors="replace")
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not lines:
        return ProofFormat.EMPTY
    # A SAT model ("v 1 -2 ... 0" / "s SATISFIABLE") is not a proof and must
    # be rejected before any checker runs (encoder spec §8 step 5; tested in the §9.5 negative suite).
    for ln in lines[:20]:
        if ln.startswith("v ") or ln.startswith("s SATISFIABLE"):
            return ProofFormat.SAT_MODEL

    def _tokens_ok(ln, lrat):
        toks = ln.split()
        if lrat:
            # LRAT: "<id> [d] lits 0 hints 0" — first token is a clause id.
            if toks[0] == "d" or not toks[0].lstrip("-").isdigit():
                return False
            return True
        return all(t == "d" or t.lstrip("-").isdigit() for t in toks)

    body = [ln for ln in lines if not ln.startswith("c")]
    if not body:
        return ProofFormat.UNKNOWN
    # LRAT lines end with two zero-terminated sections and START with an id;
    # DRAT lines are bare literal lists (optionally 'd'-prefixed). Heuristic:
    # an LRAT line has >= 2 '0' tokens or is "<id> d ... 0".
    lrat_votes = 0
    drat_votes = 0
    for ln in body[:50]:
        toks = ln.split()
        if len(toks) >= 2 and toks[0].isdigit() and (toks[1] == "d" or toks.count("0") >= 2):
            lrat_votes += 1
        elif _tokens_ok(ln, lrat=False):
            drat_votes += 1
    if lrat_votes > drat_votes:
        return ProofFormat.LRAT_TEXT
    if drat_votes:
        return ProofFormat.DRAT_TEXT
    return ProofFormat.UNKNOWN


def tail_wellformed(path: str) -> bool:
    """Cheap fast-fail: a text proof whose final bytes are mid-line is
    truncated. The checker remains the authority on the final-empty-clause
    rule; this only pre-rejects obviously chopped files."""
    size = os.stat(path).st_size
    if size == 0:
        return False
    with open(path, "rb") as fh:
        fh.seek(max(0, size - TAIL_WINDOW))
        tail = fh.read()
    stripped = tail.rstrip(b" \r\n")
    return stripped.endswith(b"0")
