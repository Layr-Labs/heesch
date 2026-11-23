"""Lower bounds on missing fifth-ring sites over all fourth rings on a given P3."""
from collections import defaultdict
from math import atan2, floor, pi, sqrt, ceil
from pathlib import Path
import json
import sys
from ortools.sat.python import cp_model
from heesch_verify import verify_witness
from heesch_verify.patch import required_set
from joint_fraction import consistent_placements
from pack import enumerate_tiles


def main(source, out):
    out.mkdir(exist_ok=True,parents=True)
    w=verify_witness(source.read_text())
    shape=frozenset(w.submission.cells)
    grid=w.submission.grid
    p3=frozenset().union(*(t.apply_all(shape) for l,t in w.submission.patches[0] if l<4))
    r4=required_set(p3,w.contact)
    fourth=consistent_placements(enumerate_tiles(shape,grid,p3,r4),r4)
    sites=frozenset().union(*(t.cells for t in fourth))
    boundary={n for c in sites for n in w.contact.neighbors(c)}-p3-r4
    outer=enumerate_tiles(shape,grid,p3|r4,boundary)
    cx=sum(x for x,y in p3)/len(p3)
    cy=sum(y for x,y in p3)/len(p3)
    by4=defaultdict(list)
    for i,t in enumerate(fourth):
        for p in t.cells:
            by4[p].append(i)

    def model4():
        m=cp_model.CpModel()
        v=[m.new_bool_var("four") for t in fourth]
        occupied={p:m.new_bool_var("inside") for p in sites}
        for p,idx in by4.items():
            m.add(sum(v[i] for i in idx)==occupied[p])
        for p in r4:
            m.add(occupied[p]==1)
        return m,occupied

    def exposed(m,occ,p):
        touches=m.new_bool_var("touches")
        m.add_max_equality(touches,[occ[q] for q in w.contact.neighbors(p) if q in occ])
        req=m.new_bool_var("required")
        m.add(req<=touches)
        m.add(req+occ.get(p,0)<=1)
        m.add(req>=touches-occ.get(p,0))
        return req

    m,o=model4()
    m.maximize(sum(exposed(m,o,p) for p in boundary))
    solver=cp_model.CpSolver()
    solver.parameters.num_search_workers=2
    solver.parameters.max_time_in_seconds=15
    status=solver.solve(m)
    bound=min(len(boundary),ceil(solver.best_objective_bound)) if status in (cp_model.FEASIBLE,cp_model.OPTIMAL) else len(boundary)
    result=dict(source=source.name,possible_boundary=len(boundary),upper_boundary=bound,max_charges_to_promote=(3*bound-1)//254,partitions=[])
    print("boundary upper bound",bound,"promotion allows",result["max_charges_to_promote"],flush=True)
    for bins,offset in ((8,0),(6,0.5),(4,0.25)):
        parts=[set() for _ in range(bins)]
        for x,y in boundary:
            phi=atan2((y-cy)*sqrt(3)/2,(x-cx)+(y-cy)/2)
            j=floor((phi/(2*pi)*bins+offset)%bins)
            parts[j].add((x,y))
        assert set.union(*parts)==boundary and sum(map(len,parts))==len(boundary)
        group=dict(bins=bins,offset=offset,sectors=[])
        result["partitions"].append(group)
        for idx,sector in enumerate(parts):
            m,occ=model4()
            by5=defaultdict(list)
            for t in outer:
                if not t.cells&sector:
                    continue
                var=m.new_bool_var("five")
                for p in t.cells:
                    by5[p].append(var)
            for p,choices in by5.items():
                m.add(sum(choices)+occ.get(p,0)<=1)
            missed=[]
            for p in sector:
                u=m.new_bool_var("missed")
                m.add(u>=exposed(m,occ,p)-sum(by5[p]))
                missed.append(u)
            m.minimize(sum(missed))
            solver=cp_model.CpSolver()
            solver.parameters.num_search_workers=2
            solver.parameters.max_time_in_seconds=9
            status=solver.solve(m)
            assert status!=cp_model.INFEASIBLE
            lower=max(0,ceil(solver.best_objective_bound-1e-7)) if status in (cp_model.UNKNOWN,cp_model.FEASIBLE,cp_model.OPTIMAL) else 0
            record=dict(sector=idx,sites=len(sector),status=solver.status_name(status),lower=lower)
            group["sectors"].append(record)
            group["minimum_missing"]=sum(p["lower"] for p in group["sectors"])
            print(bins,idx,record,flush=True)
            (out/"bounds.json").write_text(json.dumps(result,indent=2)+"\n")
            if group["minimum_missing"]>result["max_charges_to_promote"]:
                print("Threshold excluded by disjoint site lower bounds",flush=True)
                return


if __name__=="__main__":
    main(*map(Path,sys.argv[1:]))
