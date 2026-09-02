"""Text format -> Submission (spec §4, §9.2.7, §13.2). Syntax only.

Accepts heesch-sat's canonical output byte-for-byte (CRLF and repeated spaces
tolerated); rejects structural garbage with distinct codes, never a crash.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .grids import GRIDS, Cell, Grid
from .result import ErrorCode, VerifyError
from .transform import Xform

MAX_INT = 2**31
MAX_LINE_CHARS = 1_000_000

# re.ASCII: \d and \s must not match Unicode digits/whitespace — the frozen
# grammar is ASCII, and str-mode \d would otherwise accept e.g. '١'.
_PLACEMENT_RE = re.compile(
    r"^\s*(-?\d+)\s*<\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,"
    r"\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*>\s*$",
    re.ASCII,
)
_INT_RE = re.compile(r"-?[0-9]+", re.ASCII)

Placement = tuple[int, Xform]


def _marker(line: str) -> str | None:
    """The section marker a line opens, or None. Exact first-token match
    (audit V7): the old startswith('#DEFECT') test accepted '#DEFECTXYZ ...'
    as a defect block, admitting out-of-spec bytes into the record."""
    toks = line.split()
    if toks and toks[0] in ("#DEFECT", "#PROOF"):
        return toks[0]
    return None


def _is_defect_marker(line: str) -> bool:
    return _marker(line) == "#DEFECT"


def _is_section_marker(line: str) -> bool:
    return _marker(line) is not None


# §13.2 proof block: the file that carries the proof lives next to
# best.heesch under submission/ and is named by a plain basename only.
PROOF_SCHEMA_VERSION = 1
PROOF_ENCODER_VERSION = "heesch-encoder/v2"
PROOF_ENCODER_REVISION = 2
PROOF_MAX_M = 8
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_PROOF_BASENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def validate_proof_basename(name: str, fmt: str, comp: str, *,
                            forbid: tuple[str, ...] = ("best.heesch",)) -> None:
    """The `file` line's naming rule, shared by the parser and tools/prove.py
    (which must refuse an illegal `--out` BEFORE it does any work — audit
    2026-08-19 High 2). A proof file is a plain basename next to best.heesch:
    no path separators, no leading `.`/`-` (argv-injection / hidden files),
    <= 64 chars, never `best.heesch`, and the suffix must spell the declared
    format and compression. Raises VerifyError(PARSE_SYNTAX)."""
    if not _PROOF_BASENAME_RE.match(name) or name in forbid:
        raise VerifyError(
            ErrorCode.PARSE_SYNTAX, f"proof block: illegal proof file name {name[:80]!r}"
        )
    if fmt not in ("drat", "lrat"):
        raise VerifyError(ErrorCode.PARSE_SYNTAX, f"proof block: format must be drat|lrat, got {fmt[:20]!r}")
    if comp not in ("none", "xz"):
        raise VerifyError(ErrorCode.PARSE_SYNTAX, f"proof block: compression must be none|xz, got {comp[:20]!r}")
    expected_suffix = "." + fmt + (".xz" if comp == "xz" else "")
    if not name.endswith(expected_suffix):
        raise VerifyError(
            ErrorCode.PARSE_SYNTAX,
            f"proof block: file name must end in {expected_suffix!r} for format {fmt}/{comp}",
        )


def validate_core_basename(core_file: str, core_comp: str, *, proof_name: str) -> None:
    """The optional `core` line's naming rule (same basename discipline; may
    not collide with best.heesch or the proof file; `.xz` iff compressed)."""
    if not _PROOF_BASENAME_RE.match(core_file) or core_file in ("best.heesch", proof_name):
        raise VerifyError(ErrorCode.PARSE_SYNTAX,
                          f"proof block: illegal core file name {core_file[:80]!r}")
    if core_comp not in ("none", "xz"):
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "proof block: core compression must be none|xz")
    if core_comp == "xz" and not core_file.endswith(".xz"):
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "proof block: xz core file must end in .xz")
    if core_comp == "none" and core_file.endswith(".xz"):
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "proof block: uncompressed core file must not end in .xz")


@dataclass(frozen=True)
class DefectBlock:
    level: int
    u_hc: int
    u_hh: int
    required: int
    tiles: tuple[Placement, ...]


@dataclass(frozen=True)
class ProofBlock:
    """`#PROOF` block (§13.2): binds a proof file to this shape.

        #PROOF 1
        encoder heesch-encoder/v2 2 <m>
        cnf <cnf_sha256> <num_vars> <num_clauses>
        file <basename> <drat|lrat> <none|xz> <payload_sha256>
        core <basename> <none|xz> <payload_sha256> <num_clauses>   (optional, lrat only)

    `payload_sha256` is over the DEcompressed bytes (what the checkers read);
    `cnf_sha256` is the digest of the regenerated DIMACS for F(S, m). The
    optional `core` line names a clause list — a subset of F the LRAT proof
    refutes (architecture §13.3 step 5b); its clause ids in the LRAT are
    positions in that list.
    """

    m: int
    encoder_version: str
    revision: int
    cnf_digest: str
    num_vars: int
    num_clauses: int
    file_name: str
    fmt: str            # "drat" | "lrat"
    compression: str    # "none" | "xz"
    payload_sha256: str
    core_file: str | None = None
    core_compression: str = "none"
    core_sha256: str | None = None
    core_clauses: int = 0


@dataclass(frozen=True)
class Submission:
    grid_id: str
    grid: Grid
    cells: tuple[Cell, ...]
    hc_claim: int
    hh_claim: int
    patch_count: int
    patches: tuple[tuple[Placement, ...], ...]
    defect: DefectBlock | None
    proof: ProofBlock | None = None


def _int(tok: str, what: str) -> int:
    # The frozen grammar is ASCII decimal only: int() alone also accepts
    # Unicode digits ('١'), underscores ('1_0') and a leading '+', which
    # would let out-of-spec bytes canonicalize to an in-spec shape.
    if not _INT_RE.fullmatch(tok):
        # Truncate the echoed token (audit V6): an attacker-controlled first
        # token can be up to MAX_LINE_CHARS long and would otherwise flood the
        # CI log verbatim (and amplify V3's exfil channel).
        raise VerifyError(ErrorCode.PARSE_SYNTAX, f"expected integer for {what}, got {tok[:80]!r}")
    v = int(tok)
    if abs(v) > MAX_INT:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, f"oversized integer for {what}: {tok[:80]}")
    return v


class _Lines:
    def __init__(self, text: str):
        self.lines = text.split("\n")
        self.pos = 0

    def next(self, what: str) -> str:
        while self.pos < len(self.lines):
            raw = self.lines[self.pos]
            if len(raw) > MAX_LINE_CHARS:
                raise VerifyError(ErrorCode.PARSE_SYNTAX, f"line {self.pos + 1} too long")
            self.pos += 1
            line = raw.rstrip("\r")
            if line.strip():
                return line
        raise VerifyError(ErrorCode.PARSE_SYNTAX, f"unexpected end of file: expected {what}")

    def assert_exhausted(self):
        for i in range(self.pos, len(self.lines)):
            # Enforce the line-length cap on trailing lines too (audit V8):
            # next() enforces it, assert_exhausted did not, so an oversized
            # whitespace-only trailing line was silently accepted.
            if len(self.lines[i]) > MAX_LINE_CHARS:
                raise VerifyError(ErrorCode.PARSE_SYNTAX, f"line {i + 1} too long")
            if self.lines[i].strip():
                raise VerifyError(
                    ErrorCode.PARSE_SYNTAX,
                    f"trailing garbage at line {i + 1}: {self.lines[i][:60]!r}",
                )


def _parse_placement(line: str, what: str) -> Placement:
    m = _PLACEMENT_RE.match(line)
    if not m:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, f"bad placement line in {what}: {line[:80]!r}")
    vals = [_int(g, what) for g in m.groups()]
    level = vals[0]
    return (level, Xform(*vals[1:]))


def _parse_patch(lines: _Lines, what: str, max_placements: int) -> tuple[Placement, ...]:
    count_line = lines.next(f"{what} placement count")
    toks = count_line.split()
    if len(toks) != 1:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, f"expected bare placement count for {what}")
    n = _int(toks[0], f"{what} placement count")
    if n < 0:
        raise VerifyError(ErrorCode.PARSE_COUNT_MISMATCH, f"negative placement count for {what}")
    if n > max_placements:
        raise VerifyError(
            ErrorCode.RESOURCE_EXCEEDED,
            f"{what} has {n} placements, cap is {max_placements}",
        )
    out = []
    for i in range(n):
        try:
            line = lines.next(f"{what} placement {i + 1}/{n}")
        except VerifyError as e:
            if e.code is ErrorCode.PARSE_SYNTAX and "unexpected end" in e.message:
                raise VerifyError(
                    ErrorCode.PARSE_COUNT_MISMATCH,
                    f"{what} declares {n} placements but file ends after {i}",
                )
            raise
        # A stray section marker where a placement should be means the declared
        # count disagrees with the actual line count.
        if _is_section_marker(line):
            raise VerifyError(
                ErrorCode.PARSE_COUNT_MISMATCH,
                f"{what} declares {n} placements but only {i} present before {_marker(line)}",
            )
        out.append(_parse_placement(line, what))
    return tuple(out)


def _peek_marker(lines: _Lines) -> str | None:
    """Return the next non-blank line WITHOUT consuming it (or None at a clean
    end of file). A line-length violation is re-raised rather than swallowed
    as generic trailing garbage (audit V8)."""
    if lines.pos >= len(lines.lines):
        return None
    save = lines.pos
    try:
        nxt = lines.next("end of file")
    except VerifyError as e:
        if "too long" in e.message:
            raise
        return None
    lines.pos = save
    return nxt


def _parse_defect_block(header: str, lines: _Lines, max_placements: int) -> DefectBlock:
    dtoks = header.split()
    if len(dtoks) != 5:
        raise VerifyError(
            ErrorCode.PARSE_SYNTAX, "defect header must be '#DEFECT k u_hc u_hh r'"
        )
    d_level = _int(dtoks[1], "defect corona level")
    d_uhc = _int(dtoks[2], "defect u_hc")
    d_uhh = _int(dtoks[3], "defect u_hh")
    d_req = _int(dtoks[4], "defect required")
    if min(d_level, d_uhc, d_uhh, d_req) < 0:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "negative value in defect header")
    tiles = _parse_patch(lines, "defect block", max_placements)
    return DefectBlock(level=d_level, u_hc=d_uhc, u_hh=d_uhh, required=d_req, tiles=tiles)


def _proof_line(lines: _Lines, keyword: str, arity: int) -> list[str]:
    line = lines.next(f"proof block '{keyword}' line")
    toks = line.split()
    if len(toks) != arity or toks[0] != keyword:
        raise VerifyError(
            ErrorCode.PARSE_SYNTAX,
            f"proof block: expected '{keyword}' line with {arity - 1} fields, got {line[:80]!r}",
        )
    return toks


def _parse_proof_block(header: str, lines: _Lines) -> ProofBlock:
    htoks = header.split()
    if len(htoks) != 2:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "proof header must be '#PROOF 1'")
    if _int(htoks[1], "proof schema version") != PROOF_SCHEMA_VERSION:
        raise VerifyError(
            ErrorCode.PARSE_SYNTAX, f"unsupported proof block schema {htoks[1][:20]!r}"
        )
    enc = _proof_line(lines, "encoder", 4)
    if enc[1] != PROOF_ENCODER_VERSION:
        raise VerifyError(
            ErrorCode.PARSE_SYNTAX, f"proof block: unsupported encoder {enc[1][:40]!r}"
        )
    if _int(enc[2], "proof encoder revision") != PROOF_ENCODER_REVISION:
        raise VerifyError(
            ErrorCode.PARSE_SYNTAX, f"proof block: unsupported encoder revision {enc[2][:20]!r}"
        )
    m = _int(enc[3], "proof level m")
    if not 1 <= m <= PROOF_MAX_M:
        raise VerifyError(
            ErrorCode.PARSE_SYNTAX, f"proof block: m must be in 1..{PROOF_MAX_M}, got {m}"
        )
    cnf = _proof_line(lines, "cnf", 4)
    if not _HEX64_RE.match(cnf[1]):
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "proof block: cnf digest must be 64 lowercase hex")
    num_vars = _int(cnf[2], "proof num_vars")
    num_clauses = _int(cnf[3], "proof num_clauses")
    if num_vars < 1 or num_clauses < 1:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "proof block: num_vars/num_clauses must be >= 1")
    fl = _proof_line(lines, "file", 5)
    name, fmt, comp, payload = fl[1], fl[2], fl[3], fl[4]
    validate_proof_basename(name, fmt, comp)
    if not _HEX64_RE.match(payload):
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "proof block: payload digest must be 64 lowercase hex")
    core_file = None
    core_comp = "none"
    core_sha = None
    core_n = 0
    nxt = _peek_marker(lines)
    if nxt is not None and nxt.split()[0] == "core":
        lines.next("proof block 'core' line")
        ct = nxt.split()
        if len(ct) != 5:
            raise VerifyError(ErrorCode.PARSE_SYNTAX,
                              "proof block: expected 'core <file> <none|xz> <sha256> <num_clauses>'")
        if fmt != "lrat":
            raise VerifyError(ErrorCode.PARSE_SYNTAX, "proof block: a core list requires format lrat")
        core_file, core_comp, core_sha = ct[1], ct[2], ct[3]
        validate_core_basename(core_file, core_comp, proof_name=name)
        if not _HEX64_RE.match(core_sha):
            raise VerifyError(ErrorCode.PARSE_SYNTAX, "proof block: core digest must be 64 lowercase hex")
        core_n = _int(ct[4], "proof core clause count")
        if core_n < 1:
            raise VerifyError(ErrorCode.PARSE_SYNTAX, "proof block: core clause count must be >= 1")
    return ProofBlock(
        m=m, encoder_version=enc[1], revision=PROOF_ENCODER_REVISION, cnf_digest=cnf[1],
        num_vars=num_vars, num_clauses=num_clauses, file_name=name, fmt=fmt,
        compression=comp, payload_sha256=payload, core_file=core_file,
        core_compression=core_comp, core_sha256=core_sha, core_clauses=core_n,
    )



def parse_submission(text: str, *, max_placements: int = 20_000) -> Submission:
    if not isinstance(text, str):
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "submission is not text")
    lines = _Lines(text)

    # --- shape line: "<G> x1 y1 x2 y2 ..." ---
    shape_line = lines.next("shape line")
    toks = shape_line.split()
    head = toks[0]
    if head.endswith("?"):
        raise VerifyError(
            ErrorCode.PARSE_SYNTAX, "unclassified ('?') record is not a valid submission"
        )
    if len(head) != 1:
        # Truncate (audit V6): head is the untrusted first token of the file.
        raise VerifyError(ErrorCode.PARSE_UNKNOWN_GRID, f"bad grid designator {head[:80]!r}")
    grid = GRIDS.get(head)
    if grid is None:
        raise VerifyError(ErrorCode.PARSE_UNKNOWN_GRID, f"unknown grid {head!r}")
    coord_toks = toks[1:]
    if not coord_toks:
        raise VerifyError(ErrorCode.SHAPE_EMPTY, "no cells on shape line")
    if len(coord_toks) % 2 != 0:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "odd number of coordinates on shape line")
    coords = [_int(t, "cell coordinate") for t in coord_toks]
    cells = tuple(zip(coords[0::2], coords[1::2]))
    seen = set()
    for c in cells:
        if c in seen:
            raise VerifyError(
                ErrorCode.SHAPE_DUPLICATE_CELL, f"duplicate cell on shape line: {c}", (c,)
            )
        seen.add(c)
    for c in cells:
        if not grid.cell_valid(c):
            raise VerifyError(
                ErrorCode.PARSE_SYNTAX, f"cell {c} is not on the {head} grid lattice", (c,)
            )

    # --- claim line: "~ hc hh P" ---
    claim_line = lines.next("claim line")
    ctoks = claim_line.split()
    if not ctoks or ctoks[0] != "~":
        raise VerifyError(
            ErrorCode.PARSE_SYNTAX,
            f"expected non-tiler claim line '~ hc hh P', got {claim_line[:60]!r}",
        )
    if len(ctoks) != 4:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "claim line must be '~ hc hh P'")
    hc = _int(ctoks[1], "hc")
    hh = _int(ctoks[2], "hh")
    pcount = _int(ctoks[3], "patch count")
    if hc < 0 or hh < 0:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "negative Heesch claim")
    if hh not in (hc, hc + 1):
        raise VerifyError(ErrorCode.PARSE_SYNTAX, f"hh must be hc or hc+1, got hc={hc} hh={hh}")
    if pcount not in (0, 1, 2):
        raise VerifyError(ErrorCode.PARSE_SYNTAX, f"patch count must be 0, 1 or 2, got {pcount}")
    if pcount == 2 and hh != hc + 1:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "second patch requires hh == hc + 1")
    if pcount < 2 and hh != hc:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "hh == hc + 1 requires a second patch")
    if pcount == 0 and hc != 0:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "hc > 0 requires a witness patch")

    patches = tuple(
        _parse_patch(lines, f"patch {i + 1}", max_placements) for i in range(pcount)
    )

    # --- optional blocks: #DEFECT (§9.2.7) then #PROOF (§13.2), in that order ---
    defect = None
    proof = None
    nxt = _peek_marker(lines)
    if nxt is not None and _marker(nxt) == "#DEFECT":
        lines.next("defect header")
        defect = _parse_defect_block(nxt, lines, max_placements)
        nxt = _peek_marker(lines)
    if nxt is not None and _marker(nxt) == "#PROOF":
        lines.next("proof header")
        proof = _parse_proof_block(nxt, lines)
        nxt = _peek_marker(lines)
    if nxt is not None and _marker(nxt) == "#DEFECT":
        raise VerifyError(
            ErrorCode.PARSE_SYNTAX,
            "#DEFECT must precede #PROOF" if proof is not None else "duplicate #DEFECT block",
        )
    if nxt is not None and _marker(nxt) == "#PROOF":
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "duplicate #PROOF block")
    lines.assert_exhausted()

    return Submission(
        grid_id=head,
        grid=grid,
        cells=cells,
        hc_claim=hc,
        hh_claim=hh,
        patch_count=pcount,
        patches=patches,
        defect=defect,
        proof=proof,
    )
