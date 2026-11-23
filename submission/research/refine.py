"""Charge enclosed vacancies while selecting disjoint fourth-layer tiles."""
from collections import defaultdict
from pathlib import Path
import sys
import time

from ortools.sat.python import cp_model
from heesch_verify import verify_witness, holes_of
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from pack import placements


def refine(seed, output, seconds=50):
    text = seed.read_text()
    w = verify_witness(text)
    s = w.submission
    g = s.grid
    shape = frozenset(s.cells)
    full = w.hc_corona.patch_cells
    req = required_set(full, w.contact)
    items = placements(shape,g,full,req)
    cp = cp_model.CpModel()
    keep = [cp.new_bool_var("") for _ in items]
    at = defaultdict(list)
    for i,(cells,t) in enumerate(items):
        for q in cells:
            at[q].append(keep[i])
    for values in at.values():
        if len(values)>1:
            cp.add_at_most_one(values)
    misses = len(req)-sum(len(req&cells)*k for (cells,t),k in zip(items,keep))
    extras = {}
    existing = {t.apply_all(shape) for _,t in s.defect.tiles}
    chosen = {i for i,(cells,t) in enumerate(items) if cells in existing}
    best = s.defect.defect_hc if hasattr(s.defect, "defect_hc") else int(next(z for z in text.splitlines() if z.startswith("#DEFECT")).split()[2])
    prefix = text.split("#DEFECT")[0]
    stop = time.monotonic()+seconds
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers=2
    cuts = set()
    rounds = 0
    output.write_text(text)
    while time.monotonic()<stop:
        owner = {q:i for i in chosen for q in items[i][0]}
        holes = set(holes_of(full|set(owner),g))
        gaps = req-set(owner)
        damage = len(holes|gaps)
        if damage<best:
            result = prefix+f"#DEFECT 4 {damage} {len(gaps)} {len(req)}\n{len(chosen)}\n"
            result += "".join(f"4 {items[i][1].as_text()}\n" for i in sorted(chosen))
            valid = verify_witness(result)
            assert verify_defect(shape,g,valid.hc_corona,valid.submission.defect,valid.contact).defect_hc==damage
            output.write_text(result)
            best=damage
        while holes:
            p=holes.pop()
            stack=[p]
            component={p}
            wall=set()
            while stack:
                for q in g.edge_neighbors(stack.pop()):
                    if q in holes:
                        holes.remove(q)
                        stack.append(q)
                        component.add(q)
                    if q in owner:
                        wall.add(owner[q])
            for q in component-req:
                key=(q,tuple(sorted(wall)))
                if key in cuts:
                    continue
                cuts.add(key)
                if q not in extras:
                    extras[q]=cp.new_bool_var("")
                cp.add_bool_or([~keep[i] for i in wall]+at[q]+[extras[q]])
        objective=misses+sum(extras.values())
        cp.minimize(objective)
        cp.add(objective<=best-1)
        cp.clear_hints()
        for i,k in enumerate(keep):
            cp.add_hint(k,int(i in chosen))
        solver.parameters.max_time_in_seconds=max(.01,min(4,stop-time.monotonic()))
        status=solver.solve(cp)
        rounds+=1
        if status==cp_model.INFEASIBLE:
            break
        if status not in (cp_model.OPTIMAL,cp_model.FEASIBLE):
            solver.parameters.random_seed=1027+rounds
            if time.monotonic()<stop-6:
                solver.parameters.max_time_in_seconds=max(.01,stop-time.monotonic()-1)
                status=solver.solve(cp)
            if status not in (cp_model.OPTIMAL,cp_model.FEASIBLE):
                break
        chosen={i for i,k in enumerate(keep) if solver.value(k)}
    print(seed.name, best,len(req),len(cuts),rounds,flush=True)


if __name__=="__main__":
    refine(Path(sys.argv[1]),Path(sys.argv[2]),int(sys.argv[3]) if len(sys.argv)>3 else 50)
