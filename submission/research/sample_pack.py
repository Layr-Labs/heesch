"""Construct and improve fifth rings on verified alternative inner footprints."""
from argparse import ArgumentParser
from fractions import Fraction
import json
from pathlib import Path
import random
import time

from heesch_verify import verify_witness
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of
from pack import Packing, Placement, enumerate_tiles, write_candidate


def holes_and_gaps(grid, patch, required, chosen):
    occupied = set().union(*(t.cells for t in chosen))
    gaps = required - occupied
    pockets = holes_of(patch | occupied, grid)
    return len(gaps | pockets), len(gaps)


def greedy(grid, patch, required, domain, carried, rng):
    selected = list(carried)
    occupied = set().union(*(t.cells for t in selected))
    ranked = list(domain)
    rng.shuffle(ranked)
    ranked.sort(key=lambda t: len(t.cells & required), reverse=True)
    for t in ranked:
        if t.cells.isdisjoint(occupied):
            occupied.update(t.cells)
            selected.append(t)
    d, h = holes_and_gaps(grid, patch, required, selected)
    # Breaking an enclosed pocket can pay for the newly uncovered cells.
    while True:
        removed = None
        for i in range(len(selected)):
            new_d,new_h = holes_and_gaps(grid,patch,required,selected[:i]+selected[i+1:])
            if new_d < d:
                removed = i
                d, h = new_d,new_h
        if removed is None:
            return selected, d, h
        selected.pop(removed)


def main():
    cli = ArgumentParser()
    cli.add_argument("--samples",type=Path,default=Path("work/fourth-lane/changed-sample"))
    cli.add_argument("--source",type=Path,default=Path("work/inherited-baseline/best.heesch"))
    cli.add_argument("--out",type=Path,default=Path("work/fourth-lane/changed-p3-packing"))
    cli.add_argument("--seconds",type=float,default=0)
    cli.add_argument("--workers",type=int,default=1)
    cli.add_argument("--trials",type=int,default=2)
    opt=cli.parse_args()
    base=verify_witness(opt.source.read_text())
    shape=frozenset(base.submission.cells)
    grid,contact=base.submission.grid,base.contact
    incumbent=[Placement(xf.apply_all(shape),xf) for _,xf in base.submission.defect.tiles]
    rng=random.Random(14719)
    best=None
    records=[]
    for file in sorted(opt.samples.glob("*.heesch")):
        source=file.read_text()
        check=verify_witness(source)
        p4=check.hc_corona.patch_cells
        r=required_set(p4,contact)
        viable=[t for t in incumbent if t.cells.isdisjoint(p4) and t.cells & r]
        candidates=enumerate_tiles(shape,grid,p4,r)
        runs=[greedy(grid,p4,r,candidates,viable,rng) for _ in range(opt.trials)]
        runs.append((viable,*holes_and_gaps(grid,p4,r,viable)))
        partial,d,hh=min(runs,key=lambda run: (run[1],len(run[0])))
        print(json.dumps({"file":file.name,"partial":len(partial),"defect":d,"required":len(r)}),flush=True)
        def save(tiles,defect,gaps):
            nonlocal best
            score=Fraction(defect,len(r))
            if best is None or score<best:
                best=score
                print(json.dumps(write_candidate(opt.out/"best.heesch",source.splitlines()[0],
                    check.submission.patches[0],tiles,file,{"defect":defect,"hh":gaps,
                    "required":len(r),"inner_source":file.name})),flush=True)
        save(partial,d,hh)
        records.append((Fraction(d,len(r)),file,source,check,p4,r,partial,d))
    for _,file,source,check,p4,r,partial,d in sorted(records):
        if opt.seconds<=0:
            break
        # Binary search geometric damage. Every SAT result uses exact flood
        # checking; time limits give UNKNOWN and stop only the current bracket.
        lo,hi=0,d
        while hi>lo:
            target=(hi+lo)//2
            packing=Packing(grid,shape,p4,contact,target)
            # Feasibility suffices here because the bracketing proves
            # minimum damage without requesting a separate tile minimum.
            packing.model.clear_objective()
            packing.add_hint({t.cells for t in partial})
            found,stats=packing.solve(time.monotonic()+opt.seconds,opt.workers,14719)
            print(json.dumps({"fixed_patch":file.name,"budget":target,"search":stats}),flush=True)
            if found is not None:
                hi=stats['defect']
                partial=found
                save(found,hi,stats['hh'])
            elif stats["status"]=="INFEASIBLE":
                lo=target+1
            else:
                break


if __name__=="__main__":
    main()
