"""Reselect a fifth-ring neighborhood around missing cells, then flood-check."""
from pathlib import Path
import json
import random
import sys
import time

from heesch_verify import verify_witness
from heesch_verify.shape import holes_of
from pack import Packing, write_candidate


def distance(a,b):
    x,y=a[0]-b[0],a[1]-b[1]
    return max(abs(x),abs(y),abs(x+y))


def main():
    source=Path(sys.argv[1])
    destination=Path(sys.argv[2])
    patch=verify_witness(source.read_text())
    shape=frozenset(patch.submission.cells)
    partial={t.apply_all(shape) for _,t in patch.submission.defect.tiles}
    grid=patch.submission.grid; base=patch.hc_corona.patch_cells
    rng=random.Random(407255)
    stop=time.monotonic()+float(sys.argv[3])
    best=patch.submission.defect.u_hc
    for trial in range(200):
        if time.monotonic()>=stop:
            break
        model=Packing(grid,shape,base,patch.contact,best-1)
        occupancy=frozenset().union(*partial)
        damaged=(model.required-occupancy)|holes_of(base|occupancy,grid)
        pivot=rng.choice(sorted(damaged))
        radius=rng.choice((7,8,10,12,14,17,21,24))
        active={p for p in model.required if distance(p,pivot)<=radius}
        for tile,v in zip(model.items,model.select):
            if not (tile.cells&active):
                model.model.add(v==int(tile.cells in partial))
        model.model.clear_objective()
        model.add_hint(partial)
        result,stats=model.solve(min(stop,time.monotonic()+3),2,rng.randrange(0,2000000))
        if result:
            partial={t.cells for t in result}
            best=stats["defect"]
            info=write_candidate(destination,source.read_text().splitlines()[0],
                                 patch.submission.patches[0],result,source,stats,copy_proof=False)
            print(json.dumps(dict(trial=trial,pivot=pivot,radius=radius,**info)),flush=True)


if __name__=="__main__":
    main()
