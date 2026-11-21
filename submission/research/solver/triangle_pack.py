from collections import defaultdict,deque
from dataclasses import dataclass
from pathlib import Path
from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of
from heesch_verify.transform import Xform

HERE=Path(__file__).resolve().parent
@dataclass(frozen=True)
class Placement:
    cells:frozenset
    xf:Xform

def enumerate_tiles(shape,grid,patch,required):
    found={}
    for sym in grid.orientations:
        oriented=frozenset(sym.apply(c) for c in shape)
        ts={(rx-x,ry-y) for x,y in oriented for rx,ry in required if grid.translation_legal(rx-x,ry-y)}
        for dx,dy in sorted(ts):
            cells=frozenset((x+dx,y+dy) for x,y in oriented)
            if cells&patch:continue
            xf=Xform(sym.a,sym.b,dx+sym.c0,sym.d,sym.e,dy+sym.f0);found.setdefault(cells,Placement(cells,xf))
    return sorted(found.values(),key=lambda t:tuple(sorted(t.cells)))

def encode_full(line, placements):
    return f'{line}\n~ 4 4 1\n{len(placements)}\n'+''.join(f'{lev} {xf.as_text()}\n' for lev,xf in placements)

def serialize(base,partial):
    sub=base.submission;shape=frozenset(sub.cells);patch=base.hc_corona.patch_cells;req=required_set(patch,base.contact);covered=frozenset().union(*(t.cells for t in partial));gaps=req-covered;holes=holes_of(patch|covered,sub.grid);d=len(gaps|holes)
    line='I '+' '.join(f'{x} {y}' for x,y in sub.cells);txt=encode_full(line,sub.patches[0])+f'#DEFECT 5 {d} {len(gaps)} {len(req)}\n{len(partial)}\n'+''.join(f'5 {t.xf.as_text()}\n' for t in partial);w=verify_witness(txt);v=verify_defect(shape,sub.grid,w.hc_corona,w.submission.defect,w.contact);assert v.defect_hc==d;return txt,d,len(req)
