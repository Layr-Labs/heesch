"""Gate detail contract (2026-08 audits). `evaluate` says WHICH proof fired
(census / factorization) or WHY a shape escaped evaluation, and the harness
emits `gate_detail` in metrics. Under the fail-closed rule (architecture
§2.2) an INCONCLUSIVE shape without a proof is rejected, so `gate_detail` on
a scored entry is always `nontiler:*`.
"""

import json
import os
import subprocess
import sys

from util import ROOT, census_baseline  # noqa: F401

from heesch_verify import GRIDS
from heesch_verify.gates import IsohedralGate, Verdict

# Side-4 equilateral triangle (the audit PoC): 16 unit triangles, tiles the
# plane. Kaplan encoding: up (3a,3b), down (3a+1,3b+1).
IAMOND_TRIANGLE = frozenset(
    [(3 * i, 3 * j) for i in range(4) for j in range(4 - i)]
    + [(3 * i + 1, 3 * j + 1) for i in range(4) for j in range(3 - i)]
)
# A holed square ring: boundary_word raises BoundaryError (two cycles), and
# the gate must report that instead of a plain inconclusive.
HOLED_RING = frozenset((x, y) for x in range(3) for y in range(3)) - {(1, 1)}

BASELINE = census_baseline()


def _cells_from_corpus(name: str) -> frozenset:
    line = (ROOT / "tests" / "corpus" / f"{name}.txt").read_text().splitlines()[0]
    toks = line.split()[1:]
    return frozenset(zip(map(int, toks[0::2]), map(int, toks[1::2])))


def test_census_tiler_names_the_proof():
    v = IsohedralGate(GRIDS["O"]).check_detailed(frozenset({(0, 0)}))
    assert (v.verdict, v.detail) == (Verdict.TILER, "tiler:census")
    verdict, detail = v  # tuple-unpack compatibility
    assert (verdict, detail) == (Verdict.TILER, "tiler:census")


def test_iamond_beyond_table_tiler_is_now_caught():
    # Audit V2, real fix: the >=10-cell iamond tiler that used to score by
    # default (flagged only as unchecked:iamond_beyond_table in the interim)
    # is now constructively proven a TILER by the boundary-word criteria.
    verdict, detail = IsohedralGate(GRIDS["I"]).check_detailed(IAMOND_TRIANGLE)
    assert verdict is Verdict.TILER
    assert detail in ("tiler:conway", "tiler:translation")


def test_census_nontiler_carries_published_values():
    # An n <= 12 iamond listed in Kaplan's census is a proven non-tiler and
    # the gate reports the published exact Hc/Hh alongside.
    cells = _cells_from_corpus("iamond9-nontiler-0-hc0hh0")
    v = IsohedralGate(GRIDS["I"]).check_detailed(cells)
    assert v.verdict is Verdict.NON_TILER
    assert v.detail == "nontiler:census"
    assert (v.census_hc, v.census_hh) == (0, 0)


def test_beyond_census_criteria_miss_is_inconclusive():
    # An 11-omino from Kaplan's 11omino_2up list (Hc=1, Hh=2): a non-tiler
    # above the census bound. No factorization exists, so the gate is
    # honestly INCONCLUSIVE and the harness will demand a #PROOF block.
    cells = frozenset([(2, 0), (4, 0), (0, 1), (1, 1), (2, 1), (3, 1), (4, 1),
                       (2, 2), (3, 2), (4, 2), (5, 2)])
    v = IsohedralGate(GRIDS["O"]).check_detailed(cells)
    assert v.verdict is Verdict.INCONCLUSIVE
    assert v.detail == "evaluated:no_factorization"


def test_boundary_error_is_flagged_unchecked():
    verdict, detail = IsohedralGate(GRIDS["O"]).check_detailed(HOLED_RING)
    assert verdict is Verdict.INCONCLUSIVE
    assert detail == "unchecked:boundary_error"


def test_honest_small_nontiler_is_census_decided():
    cells = _cells_from_corpus("omino7-nontiler-0-hc1hh1")
    v = IsohedralGate(GRIDS["O"]).check_detailed(cells)
    assert v.verdict is Verdict.NON_TILER
    assert v.detail == "nontiler:census"
    assert (v.census_hc, v.census_hh) == (1, 1)
    # Criteria alone (census switched off) prove nothing about it.
    c = IsohedralGate(GRIDS["O"]).evaluate(cells, use_census=False)
    assert c.verdict is Verdict.INCONCLUSIVE
    assert c.detail == "evaluated:no_factorization"


def test_check_remains_verdict_only():
    # Backward-compatible: check() keeps returning a bare Verdict (== the
    # check_detailed verdict), here TILER for the side-4 iamond tiler.
    assert IsohedralGate(GRIDS["I"]).check(IAMOND_TRIANGLE) is Verdict.TILER


def test_gate_detail_reaches_score_json(tmp_path):
    repo = tmp_path / "repo"
    (repo / "submission").mkdir(parents=True)
    (repo / "submission" / "best.heesch").write_text(BASELINE, encoding="ascii")
    env = {
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": str(ROOT),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
    }
    proc = subprocess.run(
        [sys.executable, "-P", "-m", "harness.verify"],
        cwd=repo, env=env, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    metrics = json.loads((repo / "score.json").read_text())["metrics"]
    assert metrics["gate_tier"] == "nontiler_census"
    assert metrics["gate_detail"] == "nontiler:census"
    assert metrics["non_tiler_evidence"] == "census"
    assert metrics["tier"] == "lower_bound"
    assert (metrics["census_hc"], metrics["census_hh"]) == (1, 1)
    assert metrics["exact"] is True and metrics["record_eligible"] is False
    assert metrics["record_exact"] is False  # census evidence, hc = 1
