"""Runner preflight for the benchmark job (docs/RUNNER.md): print the
machine's resources and, with `--require record`, exit 1 unless it meets the
`record` resource profile's minima (heesch_verify/profile.py) plus the CPU /
architecture / sandbox the job needs. Run by benchmark.yml BEFORE setup so a
misprovisioned runner fails loudly instead of silently scoring under the
narrow `standard` profile.

    python tools/runner_preflight.py --scratch /mnt/scratch --require record
"""

from __future__ import annotations

import argparse
import os
import pathlib
import platform
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from heesch_verify.profile import GiB, PROFILES, mem_available_bytes, scratch_free_bytes  # noqa: E402

MIN_CPUS_RECORD = 8


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="runner_preflight.py")
    ap.add_argument("--scratch", default=os.environ.get("HEESCH_SCRATCH") or os.environ.get("TMPDIR") or "/tmp")
    ap.add_argument("--require", choices=("none", "standard", "record"), default="none",
                    help="exit 1 unless the machine meets this profile's minima")
    args = ap.parse_args(argv)

    mem = mem_available_bytes()
    free = scratch_free_bytes(args.scratch)
    cpus = os.cpu_count() or 0
    arch = platform.machine()
    bwrap = shutil.which("bwrap")
    print(f"preflight: arch={arch} cpus={cpus} mem_available={(mem or 0) / GiB:.1f} GiB "
          f"scratch={args.scratch} free={(free or 0) / GiB:.1f} GiB bwrap={'yes' if bwrap else 'NO'}")
    from heesch_verify.profile import detect
    print(f"preflight: resource profile the harness will select: {detect(args.scratch).name}")

    if args.require == "none":
        return 0
    prof = PROFILES[args.require]
    problems = []
    if mem is None or mem < prof.min_mem_available_bytes:
        problems.append(f"MemAvailable {(mem or 0) / GiB:.1f} GiB < {prof.min_mem_available_bytes / GiB:.0f} GiB")
    if free is None or free < prof.min_scratch_free_bytes:
        problems.append(f"scratch free {(free or 0) / GiB:.1f} GiB < {prof.min_scratch_free_bytes / GiB:.0f} GiB at {args.scratch}")
    if prof.name == "record":
        if cpus < MIN_CPUS_RECORD:
            problems.append(f"cpus {cpus} < {MIN_CPUS_RECORD}")
        if arch not in ("x86_64", "AMD64"):
            problems.append(f"arch {arch} is not x86-64 (cake_lpr is x86-64 Linux only)")
        if sys.platform != "linux":
            problems.append("not Linux")
        if not bwrap:
            problems.append("bubblewrap (bwrap) not installed")
    if problems:
        print("preflight: FAIL — the runner does not meet the "
              f"{prof.name} profile (docs/RUNNER.md):\n  - " + "\n  - ".join(problems), file=sys.stderr)
        return 1
    print(f"preflight: OK — meets the {prof.name} profile")
    return 0


if __name__ == "__main__":
    sys.exit(main())
