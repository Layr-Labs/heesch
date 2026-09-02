"""V1 regression (2026-08 audit, archived in Linear): the flat 160-edge
boundary cap let a 132-cell translation-tiling comb (boundary 178) skip
layer 1, evade the <= 8-cell tiler table, and score 5.0 through the harness —
above the class record of 4. The per-grid caps now sit above the longest
boundary any legal shape can have, so the comb is constructively proven
TILER and the scoring path rejects it."""

import os
import subprocess
import sys

from util import ROOT  # noqa: F401

from heesch_verify import GRIDS
from heesch_verify.boundary import (
    MAX_BOUNDARY_HEX,
    MAX_BOUNDARY_SQUARE,
    boundary_word,
)
from heesch_verify.gates import IsohedralGate, Verdict

# The audit's comb: columns x in [0, 12), 11 cells each, odd columns shifted
# down by 6. 132 cells, span 12+17 = 29 (at cap), tiles the plane by the
# translation lattice (12,0) x (0,11); boundary word 178 (> the old 160 cap).
COMB_CELLS = frozenset(
    (x, y) for x in range(12) for y in range(-6 * (x % 2), 11 - 6 * (x % 2))
)
# Ring 1 of the witness patch, extracted from the tiling (the audit PoC).
COMB_RING1 = [(-12, 0), (-12, 11), (0, -11), (0, 11), (12, -11), (12, 0)]


def test_caps_cover_every_legal_shape():
    # Hole-free connected n-cell perimeter <= 2n+2 (square) / 4n+2 (hex);
    # n <= 200 by the frozen cell cap.
    assert MAX_BOUNDARY_SQUARE > 2 * 200 + 2
    assert MAX_BOUNDARY_HEX > 4 * 200 + 2


def test_comb_boundary_exceeds_old_cap():
    word = boundary_word(COMB_CELLS, GRIDS["O"])
    assert len(word) == 178  # above the old flat cap of 160
    assert len(word) < MAX_BOUNDARY_SQUARE


def test_comb_is_constructively_proven_tiler():
    assert IsohedralGate(GRIDS["O"]).check(COMB_CELLS) is Verdict.TILER


def _comb_witness() -> str:
    cells = " ".join(f"{x} {y}" for x, y in sorted(COMB_CELLS))
    placements = ["0 <1,0,0,0,1,0>"] + [
        f"1 <1,0,{dx},0,1,{dy}>" for dx, dy in COMB_RING1
    ]
    return f"O {cells}\n~ 1 1 1\n{len(placements)}\n" + "\n".join(placements) + "\n"


def test_comb_witness_rejected_e2e(tmp_path):
    """The audit PoC, closed: the scoring path now rejects GATE_IS_TILER
    (and, per the TNCOO invariant, leaves no score file)."""
    repo = tmp_path / "repo"
    (repo / "submission").mkdir(parents=True)
    (repo / "submission" / "best.heesch").write_text(_comb_witness(), encoding="ascii")
    env = {
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": str(ROOT),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
    }
    proc = subprocess.run(
        [sys.executable, "-P", "-m", "harness.verify"],
        cwd=repo, env=env, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "GATE_IS_TILER" in proc.stdout
    assert not (repo / "score.json").exists()
