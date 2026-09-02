"""Shared test helpers: programmatic witness construction and mutation.

Negative fixtures are never stored — each test mutates a valid witness so it
isolates exactly one property (spec §12.2).
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from heesch_verify.transform import Xform  # noqa: E402


def xf_t(dx: int, dy: int) -> str:
    """Pure translation transform text."""
    return f"<1,0,{dx},0,1,{dy}>"


def witness_text(grid_id: str, cells, hc: int, hh: int, patches,
                 defect: str | None = None) -> str:
    """Assemble a submission file. `patches` is a list of lists of
    (level, xform_text)."""
    lines = [grid_id + " " + " ".join(f"{x} {y}" for x, y in cells)]
    lines.append(f"~ {hc} {hh} {len(patches)}")
    for p in patches:
        lines.append(str(len(p)))
        for lvl, xf in p:
            lines.append(f"{lvl} {xf}")
    if defect:
        lines.append(defect)
    return "\n".join(lines) + "\n"


def monomino_hc1() -> str:
    """Monomino with a complete 1-corona: the minimal valid witness."""
    placements = [(0, xf_t(0, 0))]
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if (dx, dy) != (0, 0):
                placements.append((1, xf_t(dx, dy)))
    return witness_text("O", [(0, 0)], 1, 1, [placements])


def monomino_hc2() -> str:
    """Monomino with two complete coronas (5x5 block of copies)."""
    placements = [(0, xf_t(0, 0))]
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            if (dx, dy) == (0, 0):
                continue
            lvl = max(abs(dx), abs(dy))
            placements.append((lvl, xf_t(dx, dy)))
    return witness_text("O", [(0, 0)], 2, 2, [placements])


def domino_hc1() -> str:
    """Horizontal domino with a complete 1-corona of dominoes.

    Central: (0,0),(1,0). Corona: a ring of horizontal dominoes covering
    the 12 contact neighbors exactly plus overhang."""
    placements = [(0, xf_t(0, 0))]
    # Row below (y=-1): cells -1..2 -> dominoes at x=-1 and x=1
    placements.append((1, xf_t(-1, -1)))
    placements.append((1, xf_t(1, -1)))
    # Row above (y=1): same
    placements.append((1, xf_t(-1, 1)))
    placements.append((1, xf_t(1, 1)))
    # Left cell (-1,0) and right cell (2,0)
    placements.append((1, xf_t(-2, 0)))
    placements.append((1, xf_t(2, 0)))
    return witness_text("O", [(0, 0), (1, 0)], 1, 1, [placements])


# ---------------------------------------------------------------------------
# The census heptomino below is the frozen test baseline: hc = hh = 1, inside
# the census bound, scores exactly 1.0 with gate_tier nontiler_census. Tests
# must use it — never the live submission/best.heesch, which is participant-
# owned, changes with every Yukon promotion, and can be any tier (the promoted
# record-tier shape carries a #PROOF block and needs checkers + a record-scale
# re-encode that the test matrix cannot run). test_suite_hygiene.py enforces
# this.

def census_baseline() -> str:
    """The census heptomino with a verified 1-corona (hc = hh = 1)."""
    return (
        "O 0 0 0 1 0 2 0 3 0 4 1 0 1 4\n"
        "~ 1 1 1\n"
        "8\n"
        "0 <1,0,0,0,1,0>\n"
        "1 <1,0,2,0,1,3>\n"
        "1 <0,-1,5,1,0,2>\n"
        "1 <-1,0,2,0,-1,1>\n"
        "1 <-1,0,-1,0,-1,4>\n"
        "1 <-1,0,1,0,-1,9>\n"
        "1 <0,1,-3,-1,0,-1>\n"
        "1 <0,1,-5,-1,0,6>\n"
    )


# Proof-path helpers (architecture §13). The 11-omino below is a Kaplan
# non-tiler (11omino_2up: Hc=1, Hh=2) OUTSIDE the census bound (O <= 10), so
# under the fail-closed rule it scores only with a #PROOF block. F(S,2) is
# SAT for it (Hh = 2); F(S,3) is UNSAT and small (a few hundred KB of DRAT).

OMINO11_CELLS = [(0, 1), (1, 1), (2, 0), (2, 1), (2, 2), (3, 1), (3, 2),
                 (4, 0), (4, 1), (4, 2), (5, 2)]


def omino11_hc1() -> str:
    """The 11-omino with a verified 1-corona (hc = hh = 1)."""
    placements = [
        (0, "<1,0,0,0,1,0>"),
        (1, "<1,0,-1,0,-1,0>"), (1, "<-1,0,1,0,1,1>"), (1, "<-1,0,9,0,-1,1>"),
        (1, "<-1,0,6,0,-1,5>"), (1, "<-1,0,0,0,-1,1>"), (1, "<-1,0,10,0,1,1>"),
    ]
    return witness_text("O", OMINO11_CELLS, 1, 1, [placements])


def checker_dir_for_tests(tmp_path) -> pathlib.Path | None:
    """A checker directory the ProofCarryingGate accepts. Uses the real
    tools/bin binaries; where cake_lpr is not buildable (non-x86-64-Linux) a
    SHIM named cake_lpr wraps lrat-check and rewrites its verdict line — TEST
    ONLY, so the record-tier control flow can be exercised everywhere; the
    real formally-verified checker runs on the Linux CI/benchmark runner.
    Returns None if drat-trim/lrat-check are not built."""
    import os
    import shutil
    import stat

    bin_dir = ROOT / "tools" / "bin"
    real = {n: bin_dir / n for n in ("drat-trim", "lrat-check", "cake_lpr")}
    if not real["drat-trim"].exists() or not real["lrat-check"].exists():
        return None
    d = tmp_path / "checkers"
    d.mkdir(exist_ok=True)
    for n in ("drat-trim", "lrat-check"):
        shutil.copy2(real[n], d / n)
    if real["cake_lpr"].exists():
        shutil.copy2(real["cake_lpr"], d / "cake_lpr")
    else:
        shim = d / "cake_lpr"
        shim.write_text(
            "#!/bin/sh\n# TEST SHIM: stands in for cake_lpr where it cannot be built.\n"
            "# Drops the CakeML wrapper flags (--CML_HEAP_SIZE=/--CML_STACK_SIZE=)\n"
            "# the harness passes, then runs lrat-check with the real arguments.\n"
            "for a in \"$@\"; do case \"$a\" in --CML_*) shift;; *) break;; esac; done\n"
            f"'{d / 'lrat-check'}' \"$@\" | sed 's/^c VERIFIED$/s VERIFIED UNSAT/'\n"
        )
        shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return d


def solve_drat(dimacs: bytes, tmp_path, solver: str = "cadical153"):
    """(sat, drat_bytes|None) via tools/prove.py's worker process — the same
    code participants run. The solve happens in a child process (python-sat's
    proof-logging mode can crash the interpreter at exit on Windows) and the
    DRAT is always re-verified by the checkers downstream."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("prove", ROOT / "tools" / "prove.py")
    prove = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prove)
    work = pathlib.Path(tmp_path) / "solve"
    work.mkdir(parents=True, exist_ok=True)
    sat, drat_path = prove.solve_with_proof(dimacs, solver, work)
    return sat, (None if sat else drat_path.read_bytes())
