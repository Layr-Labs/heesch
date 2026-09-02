"""Measure the full record-scale proof cycle for one shape and level, the
way the benchmark will see it: encode F(S,m) (streamed) -> solve with proof
logging -> drat-trim verify + LRAT -> lrat-check -> core extraction ->
lrat-check on the core -> xz sizes -> (optionally) cake_lpr on the core CNF.
Prints one JSON object per run (and a markdown row) — the numbers that set
the resource profiles' bands (heesch_verify/profile.py, docs/ml-feasibility.md).

    python tools/measure_record_cycle.py --shape hex11-kaplan-hc4hh4 --m 7 --work /mnt/scratch/m7
    python tools/measure_record_cycle.py --shape submission/best.heesch --m 6 --solver-bin tools/bin/cadical

Participant-side / maintainer-side tool; never run by the harness."""

from __future__ import annotations

import argparse
import importlib.util
import json
import lzma
import os
import pathlib
import resource
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from heesch_encoder.multilevel.api import encode_multilevel_stream  # noqa: E402
from heesch_encoder.proofcheck.checkers import checker_path  # noqa: E402
from heesch_verify.grids import GRIDS  # noqa: E402
from heesch_verify.parse import parse_submission  # noqa: E402
from ml_feasibility import KAPLAN_SHAPES  # noqa: E402


def _prove():
    spec = importlib.util.spec_from_file_location("prove", ROOT / "tools" / "prove.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rss_gb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / (1e9 if sys.platform == "darwin" else 1e6)


def _verdict(argv, needle):
    t0 = time.time()
    p = subprocess.run(argv, capture_output=True, text=True, errors="replace", stdin=subprocess.DEVNULL)
    ok = any(ln.strip() == needle or ln.strip().startswith(needle) for ln in p.stdout.splitlines())
    return ok, round(time.time() - t0, 1), p.stdout[-400:]


def _xz(src: pathlib.Path) -> tuple[int, float]:
    t0 = time.time()
    dst = src.with_suffix(src.suffix + ".xz")
    with open(src, "rb") as a, lzma.open(dst, "wb", preset=6) as b:
        for chunk in iter(lambda: a.read(1 << 20), b""):
            b.write(chunk)
    return dst.stat().st_size, round(time.time() - t0, 1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="measure_record_cycle.py")
    ap.add_argument("--shape", required=True, help="KAPLAN_SHAPES key or a submission file")
    ap.add_argument("--m", type=int, required=True)
    ap.add_argument("--work", default=None, help="scratch dir (default: $TMPDIR/measure-<shape>-m<m>)")
    ap.add_argument("--solver-bin", default=None, help="external solver (default tools/bin/cadical if built, else pysat cadical153)")
    ap.add_argument("--cake", action="store_true", help="also run cake_lpr on the core CNF (x86-64 Linux)")
    ap.add_argument("--json", default=None, help="append the JSON result to this file")
    args = ap.parse_args(argv)

    prove = _prove()
    if args.shape in KAPLAN_SHAPES:
        gid, cells = KAPLAN_SHAPES[args.shape]
        name = args.shape
    else:
        sub = parse_submission(pathlib.Path(args.shape).read_text(encoding="ascii"))
        gid, cells, name = sub.grid_id, list(sub.cells), pathlib.Path(args.shape).stem
    grid = GRIDS[gid]
    contact = grid.contact("point")
    work = pathlib.Path(args.work or os.path.join(os.environ.get("TMPDIR", "/tmp"), f"measure-{name}-m{args.m}"))
    work.mkdir(parents=True, exist_ok=True)
    bin_dir = ROOT / "tools" / "bin"
    res = {"shape": name, "grid": gid, "cells": len(cells), "m": args.m, "host": os.uname().nodename,
           "cpus": os.cpu_count()}

    cnf = work / "formula.cnf"
    t0 = time.time()
    enc = encode_multilevel_stream(frozenset(cells), grid, contact, args.m, cnf)
    res.update(vars=enc.num_vars, clauses=enc.num_clauses, dimacs_bytes=enc.cnf_bytes,
               encode_s=round(time.time() - t0, 1), encode_rss_gb=round(_rss_gb(), 2), digest=enc.digest)
    print(json.dumps({k: res[k] for k in ("shape", "m", "vars", "clauses", "dimacs_bytes", "encode_s", "encode_rss_gb")}), flush=True)

    solver_bin = args.solver_bin or (str(bin_dir / "cadical") if (bin_dir / "cadical").exists() else None)
    t0 = time.time()
    if solver_bin:
        # No -q, and stream the solver's own periodic report lines: a record-
        # scale UNSAT solve runs for hours, and a silent captured pipe is
        # indistinguishable from a hang in a CI live log.
        sat, drat = prove.solve_with_solver_bin(cnf, solver_bin, work,
                                                extra_args=("--no-binary",),
                                                stream_output=True)
        res["solver"] = solver_bin
    else:
        sat, drat = prove.solve_with_proof(cnf, "cadical153", work)
        res["solver"] = "pysat:cadical153"
    res["solve_s"] = round(time.time() - t0, 1)
    res["sat"] = sat
    if sat:
        print(json.dumps(res), flush=True)
        return 2
    res["drat_bytes"] = drat.stat().st_size
    print(json.dumps({k: res[k] for k in ("solver", "solve_s", "drat_bytes")}), flush=True)

    drat_trim = checker_path("drat-trim", bin_dir)
    lrat_check = checker_path("lrat-check", bin_dir)
    lrat = work / "full.lrat"
    ok, secs, _ = _verdict([str(drat_trim), str(cnf), str(drat), "-L", str(lrat)], "s VERIFIED")
    res.update(drat_trim_verified=ok, drat_trim_s=secs, lrat_bytes=lrat.stat().st_size if lrat.exists() else 0)
    if not ok:
        print(json.dumps(res), flush=True)
        return 1
    ok, secs, _ = _verdict([str(lrat_check), str(cnf), str(lrat)], "c VERIFIED")
    res.update(lrat_check_full_verified=ok, lrat_check_full_s=secs)

    t0 = time.time()
    core_txt, core_lrat, n_core, n_formula = prove.make_core_lrat(cnf, drat, drat_trim, work)
    res.update(core_clauses=n_core, core_s=round(time.time() - t0, 1), core_txt_bytes=core_txt.stat().st_size,
               core_lrat_bytes=core_lrat.stat().st_size)
    core_cnf = work / "core.cnf"
    with open(core_cnf, "w", encoding="ascii", newline="\n") as out, open(core_txt, "r", encoding="ascii") as src:
        out.write(f"p cnf {enc.num_vars} {n_core}\n")
        for line in src:
            out.write(line)
    ok, secs, _ = _verdict([str(lrat_check), str(core_cnf), str(core_lrat)], "c VERIFIED")
    res.update(lrat_check_core_verified=ok, lrat_check_core_s=secs)
    if args.cake:
        cake = checker_path("cake_lpr", bin_dir)
        from heesch_encoder.proofcheck.checkers import cake_lpr_heap_mb
        ok, secs, tail = _verdict([str(cake), f"--CML_HEAP_SIZE={cake_lpr_heap_mb(49152)}", "--CML_STACK_SIZE=1024",
                                   str(core_cnf), str(core_lrat)], "s VERIFIED")
        res.update(cake_lpr_core_verified=ok, cake_lpr_core_s=secs, cake_lpr_tail=tail.strip()[-120:])
    res["core_lrat_xz_bytes"], res["core_lrat_xz_s"] = _xz(core_lrat)
    res["core_txt_xz_bytes"], _ = _xz(core_txt)
    res["peak_rss_gb"] = round(_rss_gb(), 2)
    res["total_s"] = round(res["encode_s"] + res["solve_s"] + res["drat_trim_s"] + res["core_s"], 1)
    print(json.dumps(res, sort_keys=True), flush=True)
    print(f"| {name} | {len(cells)} | {args.m} | {enc.num_vars:,} | {enc.num_clauses:,} | "
          f"{enc.cnf_bytes/1e9:.2f} GB | {res['encode_s']} | {res['encode_rss_gb']} GB | {res['solve_s']} | "
          f"{res['drat_bytes']/1e9:.2f} GB | {res['drat_trim_s']} | {res['lrat_bytes']/1e9:.2f} GB | "
          f"{n_core:,} | {res['core_lrat_bytes']/1e6:.0f} MB / {res['core_lrat_xz_bytes']/1e6:.0f} MB xz | "
          f"{res['lrat_check_core_s']} |", flush=True)
    if args.json:
        with open(args.json, "a", encoding="ascii") as fh:
            fh.write(json.dumps(res, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
