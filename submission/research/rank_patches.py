"""Build, rank, then repair distinct third-ring boundaries of the compact 20-hex."""
from collections import defaultdict
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
import time

from ortools.sat.python import cp_model
from heesch_verify import verify_witness
from heesch_verify.patch import required_set
from heesch_verify.defect import verify_defect
from heesch_verify.shape import holes_of

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent / "fourth-lane"))
from pack import enumerate_tiles, Packing


def record(text, partial):
    core = verify_witness(text)
    s = core.submission
    required = required_set(core.hc_corona.patch_cells, core.contact)
    occupied = frozenset().union(*(p.cells for p in partial))
    gaps = required - occupied
    enclosed = holes_of(occupied | core.hc_corona.patch_cells, s.grid)
    cost = len(gaps | enclosed)
    packed = (text.rstrip() + f"\n#DEFECT 4 {cost} {len(gaps)} {len(required)}\n{len(partial)}\n"
              + "".join(f"4 {p.xf.as_text()}\n" for p in partial))
    v = verify_witness(packed)
    measured = verify_defect(frozenset(s.cells), s.grid, v.hc_corona, v.submission.defect, v.contact)
    assert (measured.defect_hc, measured.defect_hh) == (cost, len(gaps))
    return packed, cost, len(gaps), len(required)


def coverage(w, seconds):
    s = w.submission
    shape = frozenset(s.cells)
    core = w.hc_corona.patch_cells
    boundary = required_set(core, w.contact)
    items = enumerate_tiles(shape, s.grid, core, boundary)
    objective = []
    model = cp_model.CpModel()
    variables = [model.new_bool_var(str(i)) for i in range(len(items))]
    covers = defaultdict(list)
    for tile, v in zip(items, variables):
        for point in tile.cells:
            covers[point].append(v)
        objective.append((1000 * len(tile.cells & boundary) - 1) * v)
    for choices in covers.values():
        model.add_at_most_one(choices)
    model.maximize(sum(objective))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = 1
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return [], solver.status_name(status)
    return [p for p,v in zip(items, variables) if solver.value(v)], solver.status_name(status)


def main():
    folder = BASE / "arrangements"
    folder.mkdir(exist_ok=True)
    input_text = (BASE / "outline.shape").read_text().strip()
    for seed in range(1, 121):
        path = folder / f"seed{seed}.d3.heesch"
        if not path.exists():
            input_file = folder / "input.tsv"
            input_file.write_text(f"seed{seed} {input_text}\n")
            subprocess.run([str(BASE.parent / "witness-lane/star_search_batch"), "--batch",
                           str(input_file), str(folder), "3", str(seed), "3"], check=True, capture_output=True)
    paths = sorted(folder.glob("*.d3.heesch")) + [BASE / "native-full.heesch"]
    seen = set()
    trials = []
    best = Fraction(1)

    def update(output, source, stage, cost, gaps, req, extra):
        nonlocal best
        ratio = Fraction(cost, req)
        print(json.dumps(dict(file=source.name, stage=stage, required=req, cost=cost, gaps=gaps,
                              score=float(4-ratio), **extra)), flush=True)
        if ratio < best:
            best = ratio
            (BASE / "packing-best.heesch").write_text(output)
            (BASE / "packing-best-origin.txt").write_text(source.name + "\n")

    for path in paths:
        text = path.read_text()
        w = verify_witness(text)
        if w.hc_corona.patch_cells in seen:
            continue
        seen.add(w.hc_corona.patch_cells)
        partial, status = coverage(w, 4)
        if partial:
            packed, cost, gaps, req = record(text, partial)
            trials.append((Fraction(gaps, req), Fraction(cost, req), path, partial))
            update(packed, path, "coverage", cost, gaps, req, {"status":status, "tiles":len(partial)})
    for _, _, path, prior in sorted(trials)[:15]:
        text = path.read_text()
        w = verify_witness(text)
        s = w.submission
        _, cost, lower, req = record(text, prior)
        for budget in sorted(set([lower, lower+1, lower+2, lower+4, lower+7, cost-1])):
            if Fraction(budget, req) >= best:
                continue
            model = Packing(s.grid, frozenset(s.cells), w.hc_corona.patch_cells, w.contact, budget)
            model.model.clear_objective()
            model.add_hint({p.cells for p in prior})
            selected, stats = model.solve(time.monotonic()+5, 1, 51)
            if selected:
                prior = selected
                packed, cost, gaps, req = record(text, prior)
                update(packed, path, "pocket repair", cost, gaps, req,
                       {"status":stats["status"], "budget":budget, "tiles":len(prior)})
    print(json.dumps({"distinct_third_ring_patches":len(seen), "best_score":float(4-best)}), flush=True)


if __name__ == "__main__":
    main()
