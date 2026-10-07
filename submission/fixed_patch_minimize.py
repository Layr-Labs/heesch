#!/usr/bin/env python3
"""Minimize partial-tile count on fixed promoted P4 with pocket CEGAR.

The solver objective counts placements. Any proposed packing is passed to
heesch_verify.defect.verify_defect before it can be saved. Pocket cuts are
sound: a pocket-free packing must either remove a tile on the current pocket
wall or select a legal tile covering a pocket cell.
"""
from __future__ import annotations
import json, sys, time
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ortools.sat.python import cp_model
from heesch_verify.defect import verify_defect
from heesch_verify.parse import DefectBlock, parse_submission
from heesch_verify.patch import check_corona, required_set
from heesch_verify.shape import holes_of
from heesch_verify.transform import Xform
from heesch_verify.witness import verify_witness

SUB=Path(__file__).resolve().parent
SOURCE=SUB/'best.heesch'
OUT=SUB/'fixed_patch_minimize.json'
CANDIDATE=SUB/'compact-candidate.heesch'
MAX_SOLVE_SECONDS=120
MAX_CEGAR_ROUNDS=200
MAX_TOTAL_SECONDS=300


def enumerate_candidates(shape, grid, patch):
    contact=grid.contact('point'); by_cells={}
    for sym in grid.orientations:
        oriented=tuple((sym.a*x+sym.b*y+sym.c0,sym.d*x+sym.e*y+sym.f0) for x,y in shape)
        for p in patch:
            for n in contact.neighbors(p):
                for q in oriented:
                    tx,ty=n[0]-q[0],n[1]-q[1]
                    cells=frozenset((x+tx,y+ty) for x,y in oriented)
                    if cells.isdisjoint(patch):
                        by_cells.setdefault(cells,Xform(sym.a,sym.b,sym.c0+tx,sym.d,sym.e,sym.f0+ty))
    return [(cells,xf) for cells,xf in by_cells.items()]


def main():
    src=SOURCE.read_text(); sub=parse_submission(src); g=sub.grid; ct=g.contact('point')
    corona=check_corona(sub.cells,sub.patches[0],g,ct,hole_mode='hc')
    P=corona.patch_cells; R=required_set(P,ct); candidates=enumerate_candidates(sub.cells,g,P)
    model=cp_model.CpModel(); x=[model.new_bool_var(f'x{i}') for i in range(len(candidates))]
    by_cell=defaultdict(list)
    for i,(cells,_xf) in enumerate(candidates):
        for c in cells: by_cell[c].append(x[i])
    for vs in by_cell.values():
        if len(vs)>1:model.add_at_most_one(vs)
    covered=[]
    for j,c in enumerate(sorted(R)):
        y=model.new_bool_var(f'covered{j}'); inc=[x[i] for i,(cells,_xf) in enumerate(candidates) if c in cells]
        model.add(y<=sum(inc)) if inc else model.add(y==0)
        covered.append(y)
    model.add(sum(covered)>=len(R)-3)
    model.minimize(sum(x))
    # Baseline is a known pocket-free 46-tile incumbent and a deterministic hint.
    baseline_by_cells={cells:i for i,(cells,_xf) in enumerate(candidates)}
    baseline_indices=[]
    if sub.defect:
        for _level,xf in sub.defect.tiles:
            fp=xf.apply_all(sub.cells)
            baseline_indices.append(baseline_by_cells[fp])
    for i,var in enumerate(x): model.add_hint(var, int(i in set(baseline_indices)))
    solver=cp_model.CpSolver(); solver.parameters.num_search_workers=2; solver.parameters.max_time_in_seconds=MAX_SOLVE_SECONDS
    solver.parameters.random_seed=17
    start=time.monotonic(); rounds=[]; last_valid=None
    for round_no in range(MAX_CEGAR_ROUNDS):
        remaining=MAX_TOTAL_SECONDS-(time.monotonic()-start)
        if remaining<=0: break
        solver.parameters.max_time_in_seconds=min(MAX_SOLVE_SECONDS,remaining)
        st=solver.solve(model); rec={'round':round_no+1,'status':solver.status_name(st),'seconds':solver.wall_time}
        if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): rounds.append(rec); break
        chosen=[i for i,v in enumerate(x) if solver.boolean_value(v)]
        rec.update(tile_count=len(chosen),bound=solver.best_objective_bound)
        selected=[(5,candidates[i][1]) for i in chosen]
        selected_cells=[candidates[i][0] for i in chosen]
        union=set(P).union(*(set(c) for c in selected_cells))
        pockets=holes_of(union,g)
        uncovered=R-union
        block=DefectBlock(level=5,u_hc=len(uncovered)+len(pockets),u_hh=len(uncovered),required=len(R),tiles=tuple(selected))
        try:
            defect=verify_defect(sub.cells,g,corona,block,ct)
            rec['official_defect']={k:getattr(defect,k) for k in ('defect_hc','defect_hh','required','pocket_cells','partial_tiles')}
            if defect.defect_hc<=3:
                last_valid=(chosen,defect,st,solver.best_objective_bound)
                rounds.append(rec); break
            # A nonzero-pocket solution is invalid for the Hc score. Add a
            # disjunction valid for every hole-free continuation of this set.
            wall={n for h in pockets for n in ct.neighbors(h)}&union
            wall_vars=[x[i] for i in chosen if candidates[i][0]&wall]
            filler_vars=[x[i] for i,(cells,_xf) in enumerate(candidates) if cells&pockets]
            model.add_bool_or([v.Not() for v in wall_vars]+filler_vars)
            rec['pocket_cut_literals']={'wall_exclusions':len(wall_vars),'fillers':len(filler_vars)}
        except Exception as exc:
            rec['official_verifier_error']=f'{type(exc).__name__}: {exc}'
            model.add_bool_or([v.Not() if i in chosen else v for i,v in enumerate(x)])
        rounds.append(rec)

    artifact={'shape':'fixed submission/best.heesch P4','shape_cells':len(sub.cells),'P4_cells':len(P),'required_cells':len(R),'candidate_placements':len(candidates),'objective':'minimize partial tile count; cover at least 251/254; full-footprint disjointness; pocket CEGAR','workers':2,'max_seconds_per_solve':MAX_SOLVE_SECONDS,'max_total_seconds':MAX_TOTAL_SECONDS,'rounds':rounds,'total_seconds':time.monotonic()-start,'baseline_tiles':len(baseline_indices),'valid_candidate_found':last_valid is not None}
    if last_valid:
        chosen,defect,st,bound=last_valid
        artifact.update(valid_tile_count=len(chosen),official_defect={k:getattr(defect,k) for k in ('defect_hc','defect_hh','required','pocket_cells','partial_tiles')},optimal_proved=(st==cp_model.OPTIMAL and abs(len(chosen)-bound)<1e-6),objective_bound=bound)
        if len(chosen)<len(baseline_indices):
            prefix=src.split('#DEFECT',1)[0]
            proof_suffix=''
            if '#PROOF' in src: proof_suffix='#PROOF'+src.split('#PROOF',1)[1]
            lines=[prefix.rstrip(),f'#DEFECT 5 {defect.defect_hc} {defect.defect_hh} {defect.required}',str(len(chosen))]
            lines += [f'5 {candidates[i][1].as_text()}' for i in chosen]
            text='\n'.join(lines)+'\n'+proof_suffix
            wo=verify_witness(text); checked=verify_defect(sub.cells,g,wo.hc_corona,wo.submission.defect,ct)
            CANDIDATE.write_text(text)
            artifact['candidate_path']='submission/compact-candidate.heesch'
            artifact['candidate_recheck']={k:getattr(checked,k) for k in ('defect_hc','defect_hh','required','pocket_cells','partial_tiles')}
            artifact['proof_block_preserved']=bool(proof_suffix)
    OUT.write_text(json.dumps(artifact,indent=2)+'\n')
    print(json.dumps(artifact,indent=2))

if __name__=='__main__':main()
