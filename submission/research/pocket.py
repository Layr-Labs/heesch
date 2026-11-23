"""Optimize the 38-square fourth layer with square edge-flood pocket cuts."""
from collections import defaultdict
from pathlib import Path
import json
import time

from ortools.sat.python import cp_model
from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of
from heesch_verify.transform import Xform


def rows(shape,grid,patch,required):
    poses={}
    for o in grid.orientations:
        form=[o.apply(p) for p in shape]
        delta={(a-x,b-y) for a,b in required for x,y in form}
        for dx,dy in sorted(delta):
            if not grid.translation_legal(dx,dy): continue
            cells=frozenset((x+dx,y+dy) for x,y in form)
            if not cells.isdisjoint(patch):continue
            poses.setdefault(cells,Xform(o.a,o.b,dx+o.c0,o.d,o.e,dy+o.f0))
    return list(poses.items())


def pack(file, out, max_damage, cap):
    source=file.read_text()
    v=verify_witness(source)
    sub=v.submission
    shape=frozenset(sub.cells); grid=sub.grid
    patch=v.hc_corona.patch_cells; required=required_set(patch,v.contact)
    candidates=rows(shape,grid,patch,required)
    cp=cp_model.CpModel()
    picked=[cp.new_bool_var(f't{i}') for i in range(len(candidates))]
    by=defaultdict(list)
    for i,(pts,xf) in enumerate(candidates):
        for q in pts: by[q].append(i)
    occupancy={}
    for q,idx in by.items():
        z=occupancy[q]=cp.new_bool_var('c'+str(q))
        cp.add(sum(picked[i] for i in idx)==z)
    gaps=sum(1-occupancy.get(q,0) for q in required)
    charge={}
    cp.add(gaps<=max_damage)
    cp.minimize(gaps)
    hints=({t.apply_all(shape) for l,t in sub.defect.tiles} if sub.defect else set())
    for i,(pts,t) in enumerate(candidates):cp.add_hint(picked[i],int(pts in hints))
    solver=cp_model.CpSolver(); solver.parameters.num_search_workers=2;solver.parameters.random_seed=21117
    end=time.monotonic()+cap; best=None;rounds=0
    while time.monotonic()<end:
        solver.parameters.max_time_in_seconds=end-time.monotonic()
        status=solver.solve(cp); rounds+=1
        if status not in (cp_model.OPTIMAL,cp_model.FEASIBLE):break
        choices=[i for i,q in enumerate(picked) if solver.value(q)]
        owner={q:i for i in choices for q in candidates[i][0]}
        gaps_actual=required-set(owner); holes=holes_of(patch|set(owner),grid)
        damage=len(holes|gaps_actual)
        if damage<=max_damage and (best is None or damage<best):
            txt=source.split('#DEFECT')[0]+f'#DEFECT {v.hc_corona.max_level+1} {damage} {len(gaps_actual)} {len(required)}\n{len(choices)}\n'
            txt+=''.join(f'{v.hc_corona.max_level+1} {candidates[i][1].as_text()}\n' for i in choices)
            result=verify_witness(txt)
            check=verify_defect(shape,grid,result.hc_corona,result.submission.defect,v.contact)
            assert check.defect_hc==damage
            out.write_text(txt);best=damage
            print('verified',file.name,'charged',damage,'missing',len(gaps_actual),
                  'pockets',damage-len(gaps_actual),'required',len(required),flush=True)
            max_damage=damage-1
            if max_damage<0:break
        pending=set(holes)
        while pending:
            cell=pending.pop(); component={cell}; stack=[cell]; shell=set()
            while stack:
                p=stack.pop()
                for q in grid.edge_neighbors(p):
                    if q in pending:pending.remove(q);stack.append(q);component.add(q)
                    if q in owner:shell.add(owner[q])
            opening=sum(1-picked[i] for i in shell)
            for q in component-required:
                if q not in charge:charge[q]=cp.new_bool_var('p'+str(q))
                cp.add(opening+occupancy.get(q,0)+charge[q]>=1)
        cp.add(gaps+sum(charge.values())<=max_damage)
        cp.minimize(gaps+sum(charge.values()))
        cp.clear_hints()
        for i,q in enumerate(picked):
            cp.add_hint(q,int(i in choices))
    print(json.dumps({'input':file.name,'domain':len(candidates),'required':len(required),'best':best,
                      'steps':rounds,'status':solver.status_name(status)}),flush=True)


if __name__=='__main__':
    d=Path(__file__).resolve().parent
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("source",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--bound",type=int,default=35)
    p.add_argument("--seconds",type=int,default=180)
    a=p.parse_args()
    pack(a.source,a.output,a.bound,a.seconds)
