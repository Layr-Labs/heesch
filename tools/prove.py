"""Produce the non-tiler proof a submission needs (architecture §13.2).

The harness is fail-closed: a shape outside Kaplan's census scores only if
best.heesch carries a `#PROOF` block naming a machine-checkable UNSAT proof of
the multilevel formula F(S, m), m >= hh + 1. This tool builds that proof with
the SAME encoder call the harness makes, solves it with CaDiCaL (pysat) with
proof logging on, writes the DRAT (optionally converted to LRAT with the
vendored drat-trim), computes the digests and rewrites the `#PROOF` block.

    python tools/prove.py submission/best.heesch                # m = hh + 1, LRAT, xz
    python tools/prove.py submission/best.heesch --m 3
    python tools/prove.py submission/best.heesch --format drat --no-xz --check
    python tools/prove.py submission/best.heesch --m 7 --band none   # out-of-band (§13.9)

Requires the `prove` extra (`pip install -e '.[prove]'`, i.e. python-sat) OR
an external solver binary: `bash tools/build_solver.sh` builds a pinned
CaDiCaL into tools/bin/cadical, which is tried first and streams the DRAT to
disk — mandatory in practice for record-scale formulas (F(S,7) of an 11-cell
shape is a 3 GB DRAT; python-sat's in-process tracing needs ~9x that in RAM).
Exit codes: 0 proof written; 2 F(S, m) is SATISFIABLE (no proof exists at
this m — either the shape has a deeper corona than your witness shows or it
is a tiler); 1 any other failure.

Safety: `--out` is a plain basename validated BEFORE any work (never
best.heesch, no directories, suffix must match the format); existing outputs
are not overwritten without `--force`; every intermediate lives in a private
`.prove-*` temp dir next to the shape that is removed on every exit path; the
proof, core and rewritten shape file are installed atomically only after the
new `#PROOF` block has been parsed back successfully.

`--check` runs the finished submission through the same ProofCarryingGate the
harness uses (checkers from $HEESCH_CHECKER_DIR or ./tools/bin; cake_lpr is
x86-64-Linux-only, so on other hosts expect CHECKER_UNAVAILABLE — the record
tier is checked on the Linux benchmark runner).
"""

from __future__ import annotations

import argparse
import hashlib
import lzma
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from heesch_verify.canonical import canonical_form  # noqa: E402
from heesch_verify.parse import (  # noqa: E402
    PROOF_ENCODER_REVISION, PROOF_ENCODER_VERSION, PROOF_SCHEMA_VERSION,
)
from heesch_verify.profile import PROFILES  # noqa: E402
from heesch_verify.proofgate import HARNESS_PROOF_BAND, in_band, in_harness_band  # noqa: E402,F401
from heesch_verify.witness import VerifyConfig, verify_witness  # noqa: E402
from heesch_encoder.multilevel.api import encode_multilevel_stream, in_feasibility_band  # noqa: E402


def strip_proof_block(text: str) -> str:
    out = []
    for line in text.split("\n"):
        toks = line.split()
        if toks and toks[0] == "#PROOF":
            break
        out.append(line)
    return "\n".join(out).rstrip("\n") + "\n"


def proof_block(m, cnf_digest, num_vars, num_clauses, name, fmt, comp, payload_sha,
                core=None) -> str:
    text = (
        f"#PROOF {PROOF_SCHEMA_VERSION}\n"
        f"encoder {PROOF_ENCODER_VERSION} {PROOF_ENCODER_REVISION} {m}\n"
        f"cnf {cnf_digest} {num_vars} {num_clauses}\n"
        f"file {name} {fmt} {comp} {payload_sha}\n"
    )
    if core is not None:
        core_name, core_comp, core_sha, core_n = core
        text += f"core {core_name} {core_comp} {core_sha} {core_n}\n"
    return text


def make_core_lrat(cnf_path: pathlib.Path, drat_path: pathlib.Path, drat_trim: pathlib.Path,
                   workdir: pathlib.Path):
    """From F (cnf_path) and a verified DRAT, produce
      core.txt  — the original clauses the LRAT actually references (by
                  F-id), one per line, F's own bytes, in F order — the
                  submitted core list; and
      core.lrat — the LRAT with clause ids renumbered to positions in
                  core.txt (lemmas densely after |core|); deletions of
                  non-core originals are dropped.
    Returns (core_txt, core_lrat, n_core, n_formula) or raises RuntimeError.
    Only the submitter runs this; the harness re-derives everything it trusts
    (proofcheck.core: exact membership of every core clause in F). The core is
    defined by ids, not clause text, because F may contain the same clause
    at two ids and only one of them is used by the proof."""
    full_lrat = workdir / "full.lrat"
    proc = subprocess.run([str(drat_trim), str(cnf_path), str(drat_path), "-L", str(full_lrat)],
                          capture_output=True, text=True, errors="replace",
                          stdin=subprocess.DEVNULL)
    if not any(ln.strip() == "s VERIFIED" for ln in proc.stdout.splitlines()):
        raise RuntimeError("drat-trim did not verify the DRAT while emitting the LRAT:\n"
                           + proc.stdout[-800:])
    n_formula = 0
    with open(cnf_path, "r", encoding="ascii") as fh:
        head = fh.readline().split()
        n_formula = int(head[3])
    # Pass 1: which original ids do the hints reference?
    used = set()
    with open(full_lrat, "r", encoding="ascii") as fh:
        for raw in fh:
            toks = raw.split()
            if len(toks) < 2 or toks[1] == "d":
                continue
            rest = [int(t) for t in toks[1:]]
            z = rest.index(0)
            for h in rest[z + 1:]:
                a = -h if h < 0 else h
                if 0 < a <= n_formula:
                    used.add(a)
    if not used:
        raise RuntimeError("the LRAT references no original clause")
    core_ids = sorted(used)
    fid_to_core = {fid: i + 1 for i, fid in enumerate(core_ids)}
    # Pass over F: F's own bytes for the core ids, in F order.
    core_txt = workdir / "core.txt"
    n_core = 0
    with open(cnf_path, "r", encoding="ascii") as fh, \
            open(core_txt, "w", encoding="ascii", newline="\n") as out:
        next(fh)
        for fid, raw in enumerate(fh, 1):
            if fid in fid_to_core:
                out.write(raw if raw.endswith("\n") else raw + "\n")
                n_core += 1
    if n_core != len(core_ids):
        raise RuntimeError("core id beyond the formula's clause count")
    # Pass 2: renumber the LRAT.
    lemma_map = {}
    next_id = n_core
    core_lrat = workdir / "core.lrat"

    def map_id(x, allow_missing=False):
        neg = x < 0
        a = -x if neg else x
        m = fid_to_core.get(a) if a <= n_formula else lemma_map.get(a)
        if m is None:
            if allow_missing:
                return None
            raise RuntimeError(f"LRAT references clause id {a} that is not in the core")
        return -m if neg else m

    with open(full_lrat, "r", encoding="ascii") as fh, \
            open(core_lrat, "w", encoding="ascii", newline="\n") as out:
        for raw in fh:
            toks = raw.split()
            if not toks:
                continue
            if len(toks) >= 2 and toks[1] == "d":
                ids = [map_id(int(t), allow_missing=True) for t in toks[2:] if t != "0"]
                ids = [i for i in ids if i is not None]
                if ids:
                    out.write(f"{next_id} d " + " ".join(str(i) for i in ids) + " 0\n")
                continue
            old_id = int(toks[0])
            rest = [int(t) for t in toks[1:]]
            z = rest.index(0)
            lits, hints = rest[:z], rest[z + 1:]
            if hints and hints[-1] == 0:
                hints = hints[:-1]
            next_id += 1
            lemma_map[old_id] = next_id
            hints_m = [map_id(h) for h in hints]
            out.write(f"{next_id} " + " ".join(str(l) for l in lits) + " 0 "
                      + " ".join(str(h) for h in hints_m) + " 0\n")
    return core_txt, core_lrat, n_core, n_formula


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _worker(cnf_path: str, drat_path: str, result_path: str, solver: str) -> None:
    """Solve the DIMACS at cnf_path with proof logging and write the DRAT.
    Runs in a child process: python-sat's proof-logging mode can crash the
    interpreter during finalization on some platforms (seen on Windows,
    0xC0000409 fail-fast) AFTER the solve is complete, so the work is done
    here, files are flushed, and the process leaves via os._exit(0) without
    running interpreter teardown. The parent trusts nothing from this process
    except the files: the DRAT is verified by drat-trim / the harness.

    The output paths are fresh files the parent just created a temp dir for;
    refusing to overwrite ANY existing file (open mode 'x') means a manual
    `prove.py --worker ... <some existing file>` cannot clobber it."""
    import json

    for p in (drat_path, result_path):
        if os.path.lexists(p):
            raise SystemExit(f"--worker: refusing to overwrite existing {p!r} "
                             "(worker outputs must be fresh paths)")

    from pysat.solvers import Solver

    # Feed clauses straight from the DIMACS file (no in-memory clause list:
    # record-scale formulas have tens of millions of clauses).
    with Solver(name=solver, with_proof=True) as s:
        with open(cnf_path, "r", encoding="ascii") as fh:
            for line in fh:
                if not line or line[0] in "cp":
                    continue
                lits = [int(t) for t in line.split()]
                if lits and lits[-1] == 0:
                    lits.pop()
                s.add_clause(lits)
        sat = s.solve()
        proof = None if sat else s.get_proof()
    if not sat:
        with open(drat_path, "x", encoding="ascii", newline="\n") as fh:
            fh.write("\n".join(proof) + "\n0\n")
            fh.flush()
            os.fsync(fh.fileno())
    with open(result_path, "x", encoding="ascii") as fh:
        json.dump({"sat": bool(sat), "solver": solver}, fh)
        fh.flush()
        os.fsync(fh.fileno())
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


def solve_with_proof(cnf, solver: str, workdir: pathlib.Path) -> tuple[bool, pathlib.Path | None]:
    """Run the worker on a DIMACS file (path) or DIMACS bytes; return
    (sat, drat_path). Raises RuntimeError if the worker produced no result
    (crash before finishing, missing pysat, ...)."""
    import json

    cnf_path = workdir / "formula.cnf"
    drat_path = workdir / "proof.drat"
    result_path = workdir / "solve.json"
    for pth in (drat_path, result_path):
        if pth.exists():
            pth.unlink()
    if isinstance(cnf, (bytes, bytearray)):
        cnf_path.write_bytes(cnf)
    else:
        cnf_path = pathlib.Path(cnf)
    proc = subprocess.run(
        [sys.executable, str(pathlib.Path(__file__).resolve()), "--worker",
         str(cnf_path), str(drat_path), str(result_path), solver],
        capture_output=True, text=True, errors="replace",
    )
    if not result_path.exists():
        raise RuntimeError(
            f"solver worker produced no result (exit {proc.returncode}):\n"
            + (proc.stderr or proc.stdout)[-1500:]
        )
    res = json.loads(result_path.read_text())
    if res["sat"]:
        return True, None
    if not _drat_terminated(drat_path):
        raise RuntimeError("solver worker wrote an incomplete DRAT")
    return False, drat_path


def _drat_terminated(path: pathlib.Path) -> bool:
    """True iff the text DRAT ends with the empty clause line — checked on the
    tail only (a record-scale DRAT is GBs; never read it whole)."""
    size = path.stat().st_size
    if size == 0:
        return False
    with open(path, "rb") as fh:
        fh.seek(max(0, size - 64))
        tail = fh.read().rstrip(b"\r\n")
    return tail.endswith(b"\n0") or tail == b"0"


def solve_with_solver_bin(cnf_path, solver_bin: str, workdir: pathlib.Path,
                          extra_args=("-q", "--no-binary"),
                          stream_output: bool = False) -> tuple[bool, pathlib.Path | None]:
    """Solve with an external CaDiCaL / Kissat binary that writes the DRAT
    straight to disk (`<bin> [args] formula.cnf proof.drat`; exit 10 = SAT,
    20 = UNSAT). This is the record-scale path: the pysat worker holds the
    whole DRAT in Python memory (peak ~9x the DRAT — 27 GB for the 11-hex
    F(S,7)), an external solver streams it. Raises RuntimeError on any other
    exit or a missing/unterminated proof."""
    drat_path = workdir / "proof.drat"
    if drat_path.exists():
        drat_path.unlink()
    argv = [solver_bin, *extra_args, str(cnf_path), str(drat_path)]
    try:
        if stream_output:
            # Long solves need a heartbeat: let the solver's own periodic
            # report lines reach the caller's stdout (e.g. a CI live log)
            # instead of sitting in a captured buffer until the end.
            proc = subprocess.run(argv, stdin=subprocess.DEVNULL)
        else:
            proc = subprocess.run(argv, capture_output=True, text=True, errors="replace",
                                  stdin=subprocess.DEVNULL)
    except OSError as e:
        raise RuntimeError(f"cannot run {solver_bin}: {e}") from None
    if proc.returncode == 10:
        return True, None
    if proc.returncode != 20:
        detail = "" if stream_output else "\n" + ((proc.stderr or proc.stdout or "")[-1500:])
        raise RuntimeError(f"{solver_bin} exited {proc.returncode}:" + detail)
    if not drat_path.exists() or not _drat_terminated(drat_path):
        raise RuntimeError(f"{solver_bin} reported UNSAT but wrote no terminated DRAT")
    return False, drat_path


def _fail(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 1


def _xz_into(src: pathlib.Path, dst: pathlib.Path) -> None:
    with open(src, "rb") as fh_in, lzma.open(dst, "wb", preset=6) as fh_out:
        for chunk in iter(lambda: fh_in.read(1 << 20), b""):
            fh_out.write(chunk)


def main(argv=None) -> int:
    if argv is None and len(sys.argv) == 6 and sys.argv[1] == "--worker":
        _worker(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        return 0  # unreachable: the worker exits via os._exit
    ap = argparse.ArgumentParser(prog="prove.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("shape_file", help="submission/best.heesch")
    ap.add_argument("--m", type=int, default=None, help="proof level (default hh_verified + 1)")
    ap.add_argument("--format", choices=("drat", "lrat"), default="lrat",
                    help="lrat (default: the trimmed core, ~4x smaller than the DRAT and much "
                         "smaller compressed; needs tools/bin/drat-trim) or drat")
    ap.add_argument("--xz", dest="xz", action="store_true", default=True,
                    help="store the proof xz-compressed (default)")
    ap.add_argument("--no-xz", dest="xz", action="store_false")
    ap.add_argument("--out", default=None,
                    help="proof file name: a plain basename, written next to the shape file "
                         "(no directories; must end in .<format>[.xz]; never best.heesch)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing proof/core file of the same name")
    ap.add_argument("--solver", default="auto",
                    help="pysat solver name, or 'auto' (default): try cadical153, glucose4, "
                         "cadical195, lingeling in turn and keep the first DRAT that drat-trim "
                         "verifies — python-sat's proof tracing has produced unverifiable DRATs "
                         "on some formulas with individual solvers")
    ap.add_argument("--solver-bin", default=None,
                    help="path to an external CaDiCaL/Kissat binary (default: tools/bin/cadical "
                         "if tools/build_solver.sh built it): invoked as `<bin> --solver-args "
                         "formula.cnf proof.drat`, the DRAT streams to disk — use this for "
                         "record-scale formulas (F(S,7)+), the pysat path needs ~9x the DRAT in RAM; "
                         "tried before the pysat solvers, pass --solver none to skip them")
    ap.add_argument("--solver-args", default="-q --no-binary",
                    help="arguments for --solver-bin before the two file names (default '-q --no-binary')")
    ap.add_argument("--no-core", action="store_true",
                    help="submit the LRAT against the full formula instead of the core clause "
                         "list (default: core — the checkers then load only the clauses the "
                         "proof uses, which is what makes record-scale proofs checkable)")
    ap.add_argument("--no-selfcheck", action="store_true",
                    help="skip the drat-trim self-check of the DRAT (default: run it when tools/bin/drat-trim exists)")
    ap.add_argument("--check", action="store_true", help="run the harness's ProofCarryingGate afterwards")
    ap.add_argument("--profile", choices=("record", "standard"), default="record",
                    help="the benchmark's resource profile to check the (cells, m) against "
                         "(default record: the dedicated runner, heesch_verify/profile.py; "
                         "standard: the 8 GB CI tier)")
    ap.add_argument("--band", choices=("profile", "encoder", "none"), default="profile",
                    help="which (cells, m) band to respect: `profile` (default — warn when the "
                         "benchmark job under --profile would answer RESOURCE_EXCEEDED, refuse "
                         "outside the encoder band), `encoder` (refuse only outside the encoder's "
                         "measured band), or `none` (encode anything; maintainer re-check, "
                         "architecture §13.9); also selects the band for --check")
    args = ap.parse_args(argv)

    from heesch_verify.parse import (
        parse_submission, validate_core_basename, validate_proof_basename,
    )
    from heesch_verify.result import VerifyError

    # ---- Resolve and validate every output name BEFORE any work (audit
    # 2026-08-19 High 2: `--out ../x.lrat` escaped the submission directory and
    # `--out best.heesch` overwrote the shape; both only failed afterwards).
    shape_path = pathlib.Path(args.shape_file).resolve()
    if not shape_path.is_file():
        return _fail(f"{shape_path} is not a file")
    dest_dir = shape_path.parent
    try:
        text = shape_path.read_text(encoding="ascii")
    except UnicodeDecodeError as e:
        return _fail(f"{shape_path.name} is not ASCII ({e}); the harness rejects it")
    comp = "xz" if args.xz else "none"
    fmt = args.format

    from heesch_encoder.proofcheck.checkers import checker_path
    checker_dir = pathlib.Path(os.environ.get("HEESCH_CHECKER_DIR") or (ROOT / "tools" / "bin"))
    drat_trim = checker_path("drat-trim", checker_dir)
    have_trim = drat_trim.exists()
    if fmt == "lrat" and not have_trim:
        if args.out is not None:
            return _fail(f"{drat_trim} not built (bash tools/build_checkers.sh), so an LRAT cannot "
                         f"be produced; build it, or pass --format drat with a matching --out name")
        print(f"warning: {drat_trim} not built (bash tools/build_checkers.sh); "
              "falling back to --format drat without a self-check", file=sys.stderr)
        fmt = "drat"
    want_core = fmt == "lrat" and not args.no_core

    name = args.out if args.out is not None else ("proof." + fmt + (".xz" if args.xz else ""))
    core_name = ("core.txt" + (".xz" if args.xz else "")) if want_core else None
    try:
        validate_proof_basename(name, fmt, comp, forbid=("best.heesch", shape_path.name))
        if core_name is not None:
            validate_core_basename(core_name, comp, proof_name=name)
    except VerifyError as e:
        return _fail(f"--out: {e}")
    for out_name in filter(None, (name, core_name)):
        target = dest_dir / out_name
        if target.resolve().parent != dest_dir.resolve():
            return _fail(f"--out {out_name!r} does not stay inside {dest_dir}")
        if target.exists() and not args.force:
            return _fail(f"{target} exists; pass --force to overwrite it")

    body = strip_proof_block(text)
    outcome = verify_witness(body, VerifyConfig())
    sub = outcome.submission
    hh = outcome.result.hh_verified
    m = args.m if args.m is not None else hh + 1
    if m < hh + 1:
        return _fail(f"m={m} but the witness verifies hh={hh}; need m >= {hh + 1}")
    n = len(sub.cells)
    profile = PROFILES[args.profile]
    if args.band != "none" and not in_feasibility_band(n, m):
        return _fail(f"({n} cells, m={m}) is outside the encoder feasibility band "
                     "(pass --band none for a maintainer re-check, architecture §13.9)")
    if not profile.in_band(n, m):
        print(f"warning: ({n} cells, m={m}) is outside the {profile.name} profile's in-harness "
              f"proof band {profile.harness_band}; the benchmark job will answer "
              "RESOURCE_EXCEEDED (architecture §13.9)", file=sys.stderr)

    pysat_ok = True
    try:
        import pysat  # noqa: F401
    except ImportError:
        pysat_ok = False

    selfcheck = have_trim and not args.no_selfcheck
    if not have_trim and not args.no_selfcheck:
        print(f"warning: {drat_trim} not built; skipping the DRAT self-check "
              "(the harness will still verify it)", file=sys.stderr)
    solvers = (["cadical153", "glucose4", "cadical195", "lingeling"]
               if args.solver == "auto" else ([] if args.solver == "none" else [args.solver]))
    solver_bin = args.solver_bin
    if solver_bin is None:
        default_bin = checker_path("cadical", checker_dir)
        if default_bin.exists():
            solver_bin = str(default_bin)
    if solver_bin is not None:
        solvers = [f"bin:{solver_bin}"] + solvers
    if not pysat_ok:
        solvers = [x for x in solvers if x.startswith("bin:")]
        if not solvers:
            return _fail("python-sat not installed (pip install -e '.[prove]') and no "
                         "--solver-bin (tools/build_solver.sh builds CaDiCaL)")
    if not solvers:
        return _fail("no solver: pass --solver-bin PATH (tools/build_solver.sh builds CaDiCaL) "
                     "or a pysat --solver name")

    # Every intermediate lives in a private temp dir on the SAME filesystem as
    # the outputs (so the final os.replace is atomic) and is removed on every
    # exit path — SAT, solver failure, exception, Ctrl-C.
    import tempfile

    with tempfile.TemporaryDirectory(prefix=".prove-", dir=dest_dir) as td:
        tmpdir = pathlib.Path(td)
        tile = frozenset(canonical_form(sub.cells, sub.grid, True))
        print(f"encoding F(S,{m}) for {n} cells (streamed to disk) ...", flush=True)
        cnf_path = tmpdir / "formula.cnf"
        enc = encode_multilevel_stream(tile, sub.grid, outcome.contact, m, cnf_path)
        print(f"  {enc.num_vars} vars, {enc.num_clauses} clauses, {enc.cnf_bytes/1e6:.0f} MB, "
              f"digest {enc.digest[:16]}…", flush=True)
        lrat_path = tmpdir / "proof.lrat"
        drat_path = None
        verified_by = None
        for solver in solvers:
            print(f"solving with {solver} (proof logging on) ...", flush=True)
            try:
                if solver.startswith("bin:"):
                    sat, drat_path = solve_with_solver_bin(cnf_path, solver[4:], tmpdir,
                                                           tuple(args.solver_args.split()))
                else:
                    sat, drat_path = solve_with_proof(cnf_path, solver, tmpdir)
            except RuntimeError as e:
                print(f"  {solver}: {e}", file=sys.stderr)
                continue
            if sat:
                print(f"SAT: F(S,{m}) is satisfiable — a weak {m}-configuration exists, so no "
                      f"UNSAT proof at this m. Try a deeper witness / larger m, or the shape may tile.")
                return 2
            if not (selfcheck or fmt == "lrat"):
                verified_by = solver
                break
            # Self-check with the same checker the harness runs first: a solver's
            # DRAT trace is not guaranteed to verify (python-sat 1.9.dev7 tracing
            # has produced unverifiable DRATs from cadical195 and cadical153 on
            # some formulas), and a rejected proof is a wasted submission.
            cmd = [str(drat_trim), str(cnf_path), str(drat_path)]
            if fmt == "lrat":
                cmd += ["-L", str(lrat_path)]
            proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                                  stdin=subprocess.DEVNULL)
            if any(ln.strip() == "s VERIFIED" for ln in proc.stdout.splitlines()):
                print(f"  drat-trim self-check: s VERIFIED ({solver})", flush=True)
                verified_by = solver
                break
            print(f"  {solver}: drat-trim did NOT verify this DRAT; trying the next solver",
                  file=sys.stderr)
        if verified_by is None:
            return _fail("no solver produced a DRAT that drat-trim verifies "
                         "(tried " + ", ".join(solvers) + ")")
        payload_path = lrat_path if fmt == "lrat" else drat_path
        core = None
        core_staged = None
        if want_core:
            print("extracting the core clause list and renumbering the LRAT ...", flush=True)
            try:
                core_txt, core_lrat, n_core, n_formula = make_core_lrat(cnf_path, drat_path, drat_trim, tmpdir)
            except RuntimeError as e:
                return _fail(str(e))
            print(f"  core: {n_core} of {n_formula} clauses ({100.0 * n_core / n_formula:.1f} %)", flush=True)
            lrat_check = checker_path("lrat-check", checker_dir)
            if lrat_check.exists():
                core_cnf = tmpdir / "core.cnf"
                with open(core_cnf, "w", encoding="ascii", newline="\n") as out, \
                        open(core_txt, "r", encoding="ascii") as src:
                    out.write(f"p cnf {enc.num_vars} {n_core}\n")
                    for line in src:
                        out.write(line)
                proc = subprocess.run([str(lrat_check), str(core_cnf), str(core_lrat)],
                                      capture_output=True, text=True, errors="replace",
                                      stdin=subprocess.DEVNULL)
                if not any(ln.strip() == "c VERIFIED" for ln in proc.stdout.splitlines()):
                    return _fail("lrat-check did not verify the core-relative LRAT:\n" + proc.stdout[-800:])
                print("  lrat-check self-check on the core: c VERIFIED", flush=True)
            payload_path = core_lrat
            core_sha = sha256_file(core_txt)
            core_staged = tmpdir / ("staged-" + core_name)
            if args.xz:
                _xz_into(core_txt, core_staged)
            else:
                os.replace(core_txt, core_staged)
            core = (core_name, comp, core_sha, n_core)
        payload_sha = sha256_file(payload_path)
        staged = tmpdir / ("staged-" + name)
        if args.xz:
            _xz_into(payload_path, staged)
        else:
            os.replace(payload_path, staged)

        # Self-check the block we are about to write BEFORE anything lands in
        # the submission directory; then install proof, core, shape — in that
        # order, each by atomic rename, so a crash never leaves a #PROOF block
        # that names a missing file.
        block = proof_block(m, enc.digest, enc.num_vars, enc.num_clauses, name, fmt, comp,
                            payload_sha, core=core)
        new_text = body + block
        parse_submission(new_text)
        shape_staged = tmpdir / "staged-best.heesch"
        shape_staged.write_text(new_text, encoding="ascii", newline="\n")
        final = dest_dir / name
        os.replace(staged, final)
        if core_staged is not None:
            os.replace(core_staged, dest_dir / core_name)
        os.replace(shape_staged, shape_path)

    print(f"wrote {final} ({final.stat().st_size} bytes)"
          + (f" + {dest_dir / core[0]} ({(dest_dir / core[0]).stat().st_size} bytes)" if core else "")
          + f" and the #PROOF block in {shape_path.name}")
    print(f"  m={m}: UNSAT F(S,{m}) => Hh <= {m - 1}"
          + (" — exact (m = hh + 1)" if m == hh + 1 else " — non-tiler certificate (lower bound stays)"))

    if args.check:
        from heesch_verify.proofgate import ProofCarryingGate, named_band

        outcome2 = verify_witness(new_text, VerifyConfig())
        gate_kwargs = {"profile": profile}
        if args.band != "profile":
            gate_kwargs["band"] = named_band(args.band)
        verdict = ProofCarryingGate(shape_path.parent, checker_dir,
                                    **gate_kwargs).check(outcome2.submission, outcome2)
        print("gate:", verdict.to_json())
        return 0 if verdict.code is None else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
