"""Independently replay the upper bound over the archived inner footprints."""
from fractions import Fraction
import json
from pathlib import Path
import sys
import time

from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect

BASE = Path(__file__).resolve().parent
from rank_patches import coverage, record, Packing


def main(winner, patches):
    w = verify_witness(winner.read_text())
    shape = frozenset(w.submission.cells)
    d = verify_defect(shape, w.submission.grid, w.hc_corona, w.submission.defect, w.contact)
    goal = Fraction(d.defect_hc, d.required)
    seen, checked, solved = set(), 0, 0
    for path in sorted(patches.glob("*.heesch")):
        txt = path.read_text()
        v = verify_witness(txt)
        assert v.hc_corona.max_level == 3 and frozenset(v.submission.cells) == shape
        footprint = v.hc_corona.patch_cells
        if footprint in seen:
            continue
        seen.add(footprint)
        tiles, status = coverage(v, 30)
        assert status == "OPTIMAL", (path, status)
        _, cost, uncovered, required = record(txt, tiles)
        # The largest integer budget giving STRICTLY less damage per boundary site.
        target = (goal.numerator * required - 1) // goal.denominator
        if uncovered <= target:
            p = Packing(v.submission.grid, shape, footprint, v.contact, target)
            p.model.clear_objective()
            candidate, log = p.solve(time.monotonic()+120, 3, 55)
            assert candidate is None and log["status"] == "INFEASIBLE", (path, target, log)
            solved += 1
        checked += 1
    assert seen and w.hc_corona.patch_cells in seen
    print(json.dumps({"distinct_patches":checked, "pocket_infeasibility_checks":solved,
                      "verified_best_fraction":str(4-goal)}))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
