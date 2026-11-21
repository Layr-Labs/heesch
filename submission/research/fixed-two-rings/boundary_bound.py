"""Bound next-boundary size while requiring exact coverage by the fourth ring."""
from collections import defaultdict
from pathlib import Path
import argparse
import json
import math

from ortools.sat.python import cp_model
from heesch_verify import verify_witness
from heesch_verify.patch import required_set
from joint import consistent_placements
from pack import enumerate_tiles


def solve(file,seconds,workers):
    outcome=verify_witness(file.read_text())
    shape=frozenset(outcome.submission.cells)
    grid=outcome.submission.grid
    p3=frozenset().union(*(t.apply_all(shape) for l,t in outcome.submission.patches[0] if l<4))
    r4=required_set(p3,outcome.contact)
    tiles=consistent_placements(enumerate_tiles(shape,grid,p3,r4),r4)
    model=cp_model.CpModel()
    selected=[model.new_bool_var(f"t{i}") for i,t in enumerate(tiles)]
    at=defaultdict(list)
    for i,t in enumerate(tiles):
        for c in t.cells: at[c].append(selected[i])
    occ={c:model.new_bool_var(f"o{c}") for c in at}
    for c,variables in at.items():
        model.add(sum(variables)==occ[c])
    for c in r4: model.add(occ[c]==1)
    possible=frozenset(n for c in at for n in grid.edge_neighbors(c))-p3-r4
    exposed=[]
    for c in possible:
        ns=[occ[n] for n in grid.edge_neighbors(c) if n in occ]
        var=model.new_bool_var(f"b{c}")
        model.add(var <= sum(ns))
        model.add(var+occ.get(c,0)<=1)
        exposed.append(var)
    model.maximize(sum(exposed))
    solver=cp_model.CpSolver()
    solver.parameters.max_time_in_seconds=seconds
    solver.parameters.num_search_workers=workers
    status=solver.solve(model)
    assert status in (cp_model.OPTIMAL,cp_model.FEASIBLE)
    bound=math.ceil(solver.best_objective_bound)
    print(json.dumps({"source":str(file),"status":solver.status_name(status),
           "example_boundary":solver.objective_value,"upper_bound":bound,"max_damage":(3*bound-1)//254,
           "seconds":solver.wall_time}),flush=True)


if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("sources",nargs="+",type=Path)
    cli.add_argument("--seconds",type=float,default=30)
    cli.add_argument("--workers",type=int,default=3)
    opts=cli.parse_args()
    for file in opts.sources:
        solve(file,opts.seconds,opts.workers)
