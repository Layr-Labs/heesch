"""Independently replay the geometric census and equality witness from the benchmark root."""
from collections import Counter
from pathlib import Path
import argparse
import json
import subprocess
import sys
import tempfile
import time

from heesch_verify import verify_witness
from heesch_verify.canonical import canonical_digest
from heesch_verify.defect import verify_defect

ROOT = Path(__file__).resolve().parent


def load(path, hc):
    w = verify_witness(path.read_text())
    assert w.result.hc_verified == hc and w.result.canonical_digest.startswith("432fe86c")
    return w


def region(w, level):
    return frozenset().union(*(cells for n, cells in w.hc_corona.level_cells.items() if n <= level))


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.startswith("{")]


def terminal(path):
    return next(record["status"] for record in reversed(rows(path)) if "status" in record)


def replay():
    source = load(ROOT/"reference/best.heesch", 4)
    w = load(ROOT.parent/"best.heesch", 4)
    assert region(w, 4) == region(source, 4)
    d = verify_defect(frozenset(w.submission.cells), w.submission.grid, w.hc_corona, w.submission.defect, w.contact)
    assert (d.required, d.defect_hc, d.defect_hh, d.partial_tiles) == (254, 3, 3, 51)
    subprocess.run([sys.executable, str(ROOT/"reference/replay.py")], check=True)
    third = set()
    first = {region(source, 1)}
    historical = [ROOT/"reference/original-second/source-four.heesch",
                  *sorted(ROOT.glob("reference/original-second/inner-patches/*.heesch")),
                  *sorted(ROOT.glob("reference/third-rings/*.heesch"))]
    for p in historical:
        ref = load(p, 4)
        r3 = canonical_digest(region(ref, 3), ref.submission.grid, True)
        assert r3 not in third and region(ref, 1) in first
        third.add(r3)
    assert len(third) == 29
    assert "EXHAUSTED 5" in (ROOT/"first-census/enumeration.log").read_text().splitlines()[-1]
    reports = []
    for folder in sorted(ROOT.glob("first-[1-5]")):
        base = load(folder/"source.heesch", 4)
        r1 = region(base, 1)
        assert r1 not in first and terminal(folder/"seconds.log") == "INFEASIBLE"
        first.add(r1)
        seconds = set()
        viable = produced = 0
        parents = sorted(folder.glob("second-???.heesch"))
        assert len(parents) == sum("file" in row for row in rows(folder/"seconds.log"))
        for p in parents:
            second = load(p, 3)
            r2 = region(second, 2)
            assert region(second, 1) == r1 and r2 not in seconds
            seconds.add(r2)
            childdir = p.with_suffix("")
            assert terminal(childdir/"four.log") == "INFEASIBLE"
            descendants = sorted(childdir.glob("four-???.heesch"))
            assert len(descendants) == sum("file" in row for row in rows(childdir/"four.log"))
            viable += bool(descendants)
            for cp in descendants:
                child = load(cp, 4)
                r3 = canonical_digest(region(child, 3), child.submission.grid, True)
                assert region(child, 2) == r2 and r3 not in third
                third.add(r3)
                assert terminal(cp.with_suffix(".strict.log")) == "INFEASIBLE"
                bound = rows(cp.with_suffix(".bound.log"))[-1]
                assert bound["max_damage"] == (3*bound["upper_bound"]-1)//254
                produced += 1
        reports.append([len(seconds),viable,produced])
    assert reports == [[10,1,2], [20,1,1], [51,1,4], [16,4,39], [6,1,4]]
    assert len(first) == 6 and len(third) == 79
    print(json.dumps({"first_footprints":len(first),"P3_free_footprints":len(third),
                      "branches":reports,"partial_tiles":d.partial_tiles,"charged":d.defect_hc,
                      "required":d.required,"score":5-d.defect_hc/d.required}))


def solve_equality():
    sys.path.insert(0, str(ROOT/"reference"))
    from pack import Packing
    s = load(ROOT/"first-census/original.heesch", 4)
    cells = frozenset(s.submission.cells)
    p = Packing(s.submission.grid, cells, s.hc_corona.patch_cells, s.contact, 3)
    p.model.maximize(sum(p.select))
    p.add_hint({t.apply_all(cells) for _,t in s.submission.defect.tiles})
    result, stats = p.solve(time.monotonic()+90, 2, 2601)
    assert result and len(result) == 51 and stats["status"] == "OPTIMAL" and stats["lower_bound"] == 51
    print("Maximum partial fifth tile count with damage at most three on the scored P4 is 51.")


def rerun_strict():
    with tempfile.TemporaryDirectory() as scratch:
        for child in sorted(ROOT.glob("first-[1-5]/second-???/four-???.heesch")):
            b = rows(child.with_suffix(".bound.log"))[-1]
            args = ["--source",child,"--target",1,"--boundary-max",b["upper_bound"],
                    "--damage-max",b["max_damage"],"--seconds",140,"--workers",1,
                    "--geometry-only","--output",Path(scratch)/"trial.heesch"]
            out = subprocess.check_output([sys.executable,str(ROOT/"reference/joint.py"),*map(str,args)],text=True)
            final = next(json.loads(x)["status"] for x in reversed(out.splitlines()) if x.startswith("{") and "status" in json.loads(x))
            assert final == "INFEASIBLE", (child,final)
            print(child.relative_to(ROOT),final, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--equality", action="store_true")
    opt = parser.parse_args()
    replay()
    if opt.equality:
        solve_equality()
    if opt.strict:
        rerun_strict()
