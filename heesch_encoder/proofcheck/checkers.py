"""Checker subprocess wrappers. Success is a checker-specific, LINE-ANCHORED
verdict on stdout — exit codes are NOT a reliable signal from drat-trim, and
substring matching is unsound (drat-trim prints a non-verdict
`c VERIFIED derivation: ...` progress line; lrat-check's actual verdict is
`c VERIFIED`, not `s VERIFIED`). Any line containing NOT VERIFIED forces
failure regardless. Timeout / OOM map to RESOURCE_EXCEEDED (requeueable)."""

from __future__ import annotations

import enum
import os
import pathlib
import subprocess
import tempfile
from dataclasses import dataclass

# Default checker location for source checkouts. When the package runs from
# an installed copy (the benchmark runs `python -I` against .venv-bench), this
# resolves inside site-packages and does not exist — callers on that path MUST
# pass an explicit `bin_dir` (the harness passes $HEESCH_CHECKER_DIR or
# <repo>/tools/bin).
_BIN = pathlib.Path(__file__).resolve().parents[2] / "tools" / "bin"

CHECKER_NAMES = ("drat-trim", "lrat-check", "cake_lpr")


def checker_path(name: str, bin_dir=None) -> pathlib.Path:
    base = pathlib.Path(bin_dir) if bin_dir is not None else _BIN
    return base / (name + (".exe" if os.name == "nt" else ""))


def checker_problem(path) -> str | None:
    """None iff `path` is a regular, executable file; otherwise the reason.
    Used by the gate's preflight and by _run so a present-but-unusable binary
    (mode 0644, a directory, a dangling symlink — audit 2026-08-19 Medium 7)
    is CHECKER_MISSING / CHECKER_UNAVAILABLE, never a PermissionError out of
    subprocess.run."""
    import stat

    try:
        st = os.stat(path)
    except OSError as e:
        return f"{path} not built (tools/build_checkers.sh): {e.strerror or e}"
    if not stat.S_ISREG(st.st_mode):
        return f"{path} is not a regular file"
    if not os.access(path, os.X_OK):
        return f"{path} is not executable"
    return None


class CheckBudget:
    """Wall-clock budget for one proof check: a per-checker cap plus an
    overall deadline. Every spawn gets min(cap, time left); a non-positive
    remainder is RESOURCE_EXCEEDED without spawning."""

    DEFAULT_CAPS = {"drat-trim": 600.0, "cake_lpr": 900.0, "lrat-check": 300.0}

    def __init__(self, per_checker: dict | None = None, deadline_seconds: float = 1500.0):
        import time

        self.caps = dict(self.DEFAULT_CAPS)
        if per_checker:
            self.caps.update(per_checker)
        self.deadline = time.monotonic() + float(deadline_seconds)

    def timeout_for(self, name: str) -> float:
        import time

        return min(self.caps.get(name, 3600.0), self.deadline - time.monotonic())

    def remaining(self) -> float:
        """Seconds left before the overall deadline; <= 0 means exhausted.
        Cheap enough to poll from streaming loops (materialize, core scan) so
        they reject cleanly instead of running into the platform's job kill."""
        import time

        return self.deadline - time.monotonic()


class CheckStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    RESOURCE_EXCEEDED = "RESOURCE_EXCEEDED"
    CHECKER_MISSING = "CHECKER_MISSING"


@dataclass(frozen=True)
class CheckResult:
    checker: str
    status: CheckStatus
    seconds: float
    detail: str = ""


def _verdict(out: str, success_line) -> bool:
    """True iff some stdout/stderr line satisfies the checker's success
    predicate AND no line anywhere says NOT VERIFIED."""
    lines = [ln.strip().lstrip("\r") for ln in out.split("\n")]
    if any("NOT VERIFIED" in ln for ln in lines):
        return False
    return any(success_line(ln) for ln in lines)


# Per-checker verdict lines, verified against the vendored sources:
#   drat-trim.c:1480-1483  ->  "s VERIFIED" / "s NOT VERIFIED"
#     (drat-trim.c:858 also prints "c VERIFIED derivation: ..." — a progress
#      line, NOT a verdict; exact-line matching excludes it)
#   lrat-check.c:490/496   ->  "c VERIFIED" / "c NOT VERIFIED"
#   cake_lpr               ->  "s VERIFIED UNSAT"
_SUCCESS = {
    "drat-trim": lambda ln: ln == "s VERIFIED",
    "lrat-check": lambda ln: ln == "c VERIFIED",
    "cake_lpr": lambda ln: ln.startswith("s VERIFIED"),
}


# cake_lpr is a CakeML binary with a FIXED heap and stack reserved at start
# in ONE contiguous malloc (basis_ffi.c: cml_heap_sz + cml_stack_sz), wrapper
# flags --CML_HEAP_SIZE=<MB> / --CML_STACK_SIZE=<MB> (defaults 4096/1024).
# The defaults are far too small for record-scale instances (production
# 2026-09-02/03: 21 proofs died "heap space exhausted", 6 more died "stack
# space exhausted" AFTER drat-trim had VERIFIED them). The wrapper therefore
# sizes both from the machine: an 85 % MemAvailable budget covers heap AND
# stack together — heap = min(profile cap, 12/13 of the budget), stack =
# heap/12 with a 1 GB floor — so heap + stack <= 0.85 x MemAvailable and the
# contiguous reservation cannot over-commit. Caps: 12 GB standard / 96 GB
# record. HEESCH_CAKE_HEAP_MB overrides the heap exactly (non-numeric is
# ignored). Exhausting either is a RESOURCE outcome, never a verdict.
CAKE_LPR_HEAP_MB_MAX = 12288
CAKE_LPR_HEAP_MB_MIN = 1024
CAKE_LPR_STACK_MB_MIN = 1024
_CAKE_RESOURCE_MARKERS = ("heap space exhausted", "stack space exhausted")


def cake_lpr_heap_mb(max_mb: int | None = None) -> int:
    """Heap for cake_lpr in MB: HEESCH_CAKE_HEAP_MB if numeric, else 85 % of
    MemAvailable clamped to [CAKE_LPR_HEAP_MB_MIN, max_mb] (max_mb defaults
    to CAKE_LPR_HEAP_MB_MAX; the resource profile passes its own cap)."""
    if max_mb is None:
        max_mb = CAKE_LPR_HEAP_MB_MAX
    override = os.environ.get("HEESCH_CAKE_HEAP_MB")
    if override:
        try:
            return max(CAKE_LPR_HEAP_MB_MIN, int(override))
        except ValueError:
            pass  # misconfiguration is not a crash: fall through to auto sizing
    avail_mb = None
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    avail_mb = int(line.split()[1]) // 1024
                    break
    except OSError:
        pass
    if avail_mb is None:
        return 4096
    return max(CAKE_LPR_HEAP_MB_MIN, min(max_mb, int(avail_mb * 0.85) * 12 // 13))


def cake_lpr_stack_mb(heap_mb: int) -> int:
    """Stack for cake_lpr in MB, derived from the sized heap (heap/12, floor
    CAKE_LPR_STACK_MB_MIN). Together with cake_lpr_heap_mb's 12/13 factor the
    contiguous heap+stack reservation stays inside the 85 % budget."""
    return max(CAKE_LPR_STACK_MB_MIN, heap_mb // 12)


_OUT_HEAD = 64 * 1024        # bytes of a checker stream kept from the front
_OUT_TAIL = 1024 * 1024      # ...and from the end; every verdict prints there


def _windows(fh, head: int = _OUT_HEAD, tail: int = _OUT_TAIL) -> str:
    """Bounded head+tail windows of a checker's output file. The partial line
    at each cut edge is dropped so a window boundary can never fabricate a
    line-anchored verdict."""
    size = fh.seek(0, 2)
    if size <= head + tail:
        fh.seek(0)
        return fh.read().decode(errors="replace")
    fh.seek(0)
    h = fh.read(head)
    nl = h.rfind(b"\n")
    h = h[:nl + 1] if nl != -1 else b""
    fh.seek(size - tail)
    tl = fh.read(tail)
    nl = tl.find(b"\n")
    if nl != -1:
        tl = tl[nl + 1:]
    return (h + tl).decode(errors="replace")


def _run(name: str, args: list[str], timeout: float, bin_dir=None,
         budget: CheckBudget | None = None, heap_max_mb: int | None = None) -> CheckResult:
    exe = checker_path(name, bin_dir)
    problem = checker_problem(exe)
    if problem is not None:
        return CheckResult(name, CheckStatus.CHECKER_MISSING, 0.0, problem)
    import time

    if budget is not None:
        timeout = min(timeout, budget.timeout_for(name))
    if timeout <= 0:
        return CheckResult(name, CheckStatus.RESOURCE_EXCEEDED, 0.0,
                           "proof-check deadline exhausted before spawn")
    argv = [str(exe)]
    if name == "cake_lpr":
        heap_mb = cake_lpr_heap_mb(heap_max_mb)
        argv += [f"--CML_HEAP_SIZE={heap_mb}", f"--CML_STACK_SIZE={cake_lpr_stack_mb(heap_mb)}"]
    argv += args
    t0 = time.time()
    # A record-scale checker can print hundreds of MB of progress lines;
    # capture_output=True would buffer all of it (and 3-4 further copies for
    # verdict scanning) in THIS process's RSS — RSS that then shrinks the
    # MemAvailable sample sizing the next cake_lpr heap. Stream both pipes to
    # scratch-backed temp files instead and read back bounded head+tail
    # windows: every checker verdict prints at end-of-stream (2026-09-03).
    try:
        with tempfile.TemporaryFile() as f_out, tempfile.TemporaryFile() as f_err:
            try:
                proc = subprocess.run(
                    argv,
                    stdout=f_out,
                    stderr=f_err,
                    # F3: never let a checker read a forged proof from our
                    # stdin (drat-trim -S). We pass proofs by path only.
                    stdin=subprocess.DEVNULL,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                return CheckResult(name, CheckStatus.RESOURCE_EXCEEDED, time.time() - t0,
                                   "wall-clock timeout")
            # F4: hostile proof bytes echoed by the checker must not crash the
            # decode with an unstructured UnicodeDecodeError — _windows
            # decodes with errors="replace".
            out = _windows(f_out) + "\n" + _windows(f_err)
    except MemoryError:
        return CheckResult(name, CheckStatus.RESOURCE_EXCEEDED, time.time() - t0, "oom")
    except OSError as e:
        # Spawn failure (EACCES, ENOEXEC, ENOENT after a TOCTOU race, ...):
        # the checker is unusable, which is an availability outcome — never a
        # traceback and never a verdict on the proof.
        return CheckResult(name, CheckStatus.CHECKER_MISSING, time.time() - t0,
                           f"{exe}: spawn failed: {e}")
    dt = time.time() - t0
    if _verdict(out, _SUCCESS[name]):
        return CheckResult(name, CheckStatus.VERIFIED, dt)
    low = out.lower()
    if name == "cake_lpr" and any(mk in low for mk in _CAKE_RESOURCE_MARKERS):
        return CheckResult(name, CheckStatus.RESOURCE_EXCEEDED, dt, out[-300:].strip())
    return CheckResult(name, CheckStatus.NOT_VERIFIED, dt, out[-500:])


def drat_trim(cnf_path: str, proof_path: str, *, emit_lrat: str | None = None,
              timeout: float = 3600.0, bin_dir=None, budget=None) -> CheckResult:
    args = [cnf_path, proof_path]
    if emit_lrat:
        args += ["-L", emit_lrat]
    return _run("drat-trim", args, timeout, bin_dir, budget)


def lrat_check(cnf_path: str, lrat_path: str, *, timeout: float = 3600.0,
               bin_dir=None, budget=None) -> CheckResult:
    return _run("lrat-check", [cnf_path, lrat_path], timeout, bin_dir, budget)


def cake_lpr(cnf_path: str, lrat_path: str, *, timeout: float = 3600.0,
             bin_dir=None, budget=None, heap_max_mb: int | None = None) -> CheckResult:
    return _run("cake_lpr", [cnf_path, lrat_path], timeout, bin_dir, budget, heap_max_mb)
