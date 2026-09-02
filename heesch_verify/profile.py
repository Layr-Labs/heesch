"""Resource profiles: every time / memory / size budget of the proof path,
from ONE place, selected by the machine the harness runs on.

Why (architecture §13.5, §13.9; Plan 3, 2026-08-19): the record-breaking case
`Hc = 5, Hh = 6` needs a checked UNSAT proof of F(S,7) — 36–120 M clauses,
4–13 GB DIMACS, 3–10 min of single-core encoding, and an LRAT whose core is
hundreds of MB — for 11–20-cell shapes. That is physically outside the
standard 2-vCPU / 8 GB / 30-minute job, so the benchmark runs on a dedicated
runner (docs/RUNNER.md) and the harness scales its budgets to it. The profile
is derived from the machine (`/proc/meminfo` MemAvailable and the free space
of TMPDIR), never from a participant-controllable input: participants can only
edit `submission/`, and the workflow preflight asserts the runner meets the
`record` minima (MemAvailable >= 24 GiB, scratch free >= 60 GiB) before any
scoring. A smaller machine silently gets the
`standard` profile — the same fail-closed rule, narrower band — and the
selected profile is written into score.json (`resource_profile`).

Widening a profile is measured policy (docs/ml-feasibility.md), not an
encoder revision: it changes no CNF byte."""

from __future__ import annotations

import dataclasses
import os
import shutil

GiB = 1024 ** 3
MiB = 1024 ** 2


@dataclasses.dataclass(frozen=True)
class ResourceProfile:
    name: str
    # (max_cells, max_m) rows, ascending in max_cells; first matching row decides.
    harness_band: tuple
    encode_timeout_s: int            # wall-clock guard on the in-process encoder call
    checker_caps: dict               # per-checker subprocess caps (seconds)
    checker_deadline_s: int          # overall deadline for the proof stage, from its start
    proof_max_stored_bytes: int      # proof / core file as submitted (plain or .xz)
    proof_max_payload_bytes: int     # decompressed payload, streamed to scratch
    max_proof_bytes: int             # pipeline size gate on the materialised proof
    core_max_clauses: int
    core_max_bytes: int
    cake_heap_max_mb: int            # cap for the auto-sized CakeML heap
    min_scratch_bytes: int           # free TMPDIR required before encoding (RESOURCE_EXCEEDED otherwise)
    # Selection minima (detect()): both must hold for this profile to be chosen.
    min_mem_available_bytes: int
    min_scratch_free_bytes: int

    def in_band(self, n_cells: int, m: int) -> bool:
        for max_cells, max_m in self.harness_band:
            if n_cells <= max_cells:
                return 1 <= m <= max_m
        return False

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "harness_band": [list(r) for r in self.harness_band],
            "encode_timeout_s": self.encode_timeout_s,
            "checker_caps": dict(self.checker_caps),
            "checker_deadline_s": self.checker_deadline_s,
            "proof_max_stored_bytes": self.proof_max_stored_bytes,
            "proof_max_payload_bytes": self.proof_max_payload_bytes,
            "max_proof_bytes": self.max_proof_bytes,
            "core_max_clauses": self.core_max_clauses,
            "core_max_bytes": self.core_max_bytes,
            "cake_heap_max_mb": self.cake_heap_max_mb,
            "min_scratch_bytes": self.min_scratch_bytes,
        }


# The 2-vCPU / 8 GB / 30-minute GitHub runner (CI, and the benchmark before
# the dedicated runner): unchanged values from Plans 1–2.
STANDARD = ResourceProfile(
    name="standard",
    harness_band=((12, 6), (20, 5), (50, 3), (100, 2)),
    encode_timeout_s=600,
    checker_caps={"drat-trim": 600.0, "cake_lpr": 900.0, "lrat-check": 300.0},
    checker_deadline_s=1500,
    proof_max_stored_bytes=48 * MiB,
    proof_max_payload_bytes=1 * GiB,
    max_proof_bytes=8 * GiB,
    core_max_clauses=4_000_000,
    core_max_bytes=512 * MiB,
    cake_heap_max_mb=12288,
    min_scratch_bytes=8 * GiB,
    min_mem_available_bytes=0,
    min_scratch_free_bytes=0,
)

# The record runner (docs/RUNNER.md: Blacksmith blacksmith-32vcpu-ubuntu-2404,
# 128 GB / 1.5 TB; 4-hour job). The minima below assert "record-capable", not
# the exact instance. Band basis — measured on that runner, 2026-08-20 (run
# 32409736648, docs/ml-feasibility.md): the 16-hex F(S,7) full cycle fits
# every budget (encode 697 s / 7.0 GB RSS; core LRAT 62 MB xz; cake_lpr on
# the core 318 s), so F(S,7) is in-band to 20 cells (the 20-cell shapes are
# lighter or comparable: 20-iamond F(S,7) is 54 M clauses vs the 16-hex's
# 77 M). F(S,8) was measured OUT: at 16 cells the core LRAT alone is 33 GB
# raw / 2.2 GB xz (11x the stored cap) and cake_lpr needs 13 903 s (3.9x the
# cap) — so no m = 8 row is in the harness band; that certificate (the
# Hc = 6, Hh = 7 double jump) goes through the maintainer re-check of
# architecture §13.9. Encoding m = 8 is fine (1162 s / 8.6 GB) — the encoder
# band still allows it for the out-of-band path.
RECORD = ResourceProfile(
    name="record",
    harness_band=((20, 7), (50, 4), (100, 3), (200, 2)),
    encode_timeout_s=3600,
    checker_caps={"drat-trim": 3600.0, "cake_lpr": 3600.0, "lrat-check": 1800.0},
    checker_deadline_s=9000,
    proof_max_stored_bytes=200 * MiB,   # proof + core (each <= this) + shape fit maxSubmissionBytes 512 MiB
    proof_max_payload_bytes=8 * GiB,
    max_proof_bytes=32 * GiB,
    core_max_clauses=32_000_000,
    core_max_bytes=4 * GiB,
    cake_heap_max_mb=24576,
    min_scratch_bytes=32 * GiB,
    min_mem_available_bytes=24 * GiB,
    min_scratch_free_bytes=60 * GiB,
)

PROFILES = {p.name: p for p in (STANDARD, RECORD)}


def mem_available_bytes() -> int | None:
    """MemAvailable from /proc/meminfo (Linux; the benchmark sandbox binds
    /proc read-only so this is the real machine), else None."""
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    return None


def scratch_free_bytes(path=None) -> int | None:
    import tempfile

    try:
        return shutil.disk_usage(path or os.environ.get("TMPDIR") or tempfile.gettempdir()).free
    except OSError:
        return None


def detect(tmpdir=None) -> ResourceProfile:
    """RECORD iff the machine meets its minima (memory AND scratch), else
    STANDARD. Deliberately has no override input: the machine is the policy
    (docs/RUNNER.md preflight asserts the record minima before scoring)."""
    mem = mem_available_bytes()
    free = scratch_free_bytes(tmpdir)
    if (mem is not None and free is not None
            and mem >= RECORD.min_mem_available_bytes
            and free >= RECORD.min_scratch_free_bytes):
        return RECORD
    return STANDARD


def by_name(name: str) -> ResourceProfile:
    if name == "auto":
        return detect()
    try:
        return PROFILES[name]
    except KeyError:
        raise ValueError(f"unknown resource profile {name!r}; choose auto|" + "|".join(PROFILES)) from None
