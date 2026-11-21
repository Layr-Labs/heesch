"""Repack a partial fourth ring, including every pocket cell in comparisons."""
from pathlib import Path
import random, time
from dataclasses import dataclass
from heesch_verify.transform import Xform
from collections import Counter
BASE = Path(__file__).resolve().parent
from heesch_verify import verify_witness
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of
from heesch_verify.defect import verify_defect

@dataclass
class Placement:
    cells: frozenset
    xf: Xform


def enumerate_tiles(shape, grid, patch, required):
    placements = {}
    for sym in grid.orientations:
        oriented = frozenset(sym.apply(cell) for cell in shape)
        translations = {(rx - x, ry - y) for rx, ry in required for x, y in oriented}
        for dx, dy in sorted(translations):
            cells = frozenset((x + dx, y + dy) for x, y in oriented)
            if not cells & patch:
                placements.setdefault(cells, Xform(sym.a, sym.b, dx + sym.c0,
                                                   sym.d, sym.e, dy + sym.f0))
    return [Placement(c, xf) for c, xf in placements.items()]

def pack(f):
 bare=f.read_text().split('#DEFECT')[0].split('#PROOF')[0].rstrip()+'\n';w=verify_witness(bare);base=w.hc_corona.patch_cells;shape=set(w.submission.cells);grid=w.submission.grid;req=required_set(base,w.contact);items=enumerate_tiles(shape,grid,base,req);hits=[len(q.cells&req) for q in items];rng=random.Random(111);best=9999;bestids=[];idx=list(range(len(items)));loops=0;start=time.monotonic()
 while loops<800:
  if bestids and rng.randrange(4):keep=[i for i in bestids if rng.random()>.22]
  else:keep=[]
  occ=set(base);sel=keep[:]
  for i in keep:occ|=items[i].cells
  rnd=rng.uniform(.25,4);order=sorted(idx,key=lambda k:-(hits[k]+rng.random()*rnd))
  for i in order:
   if items[i].cells.isdisjoint(occ):sel.append(i);occ|=items[i].cells
  holes=holes_of(occ,grid);defect=len((req-occ)|holes);hh=len(req-occ);loops+=1
  if defect<best:
   best=defect;bestids=sel;text=bare.rstrip()+f'\n#DEFECT 4 {defect} {hh} {len(req)}\n{len(sel)}\n'+''.join(f'4 {items[i].xf.as_text()}\n' for i in sel);u=verify_witness(text);c=verify_defect(shape,grid,u.hc_corona,u.submission.defect,u.contact);assert c.defect_hc==defect;print(f.stem,'defect',defect,'hh',hh,'required',len(req),'copies',len(sel),'elapsed',round(time.monotonic()-start,1),flush=True)
if __name__=='__main__':
 for f in [BASE.parent/'best.heesch', BASE/'38-square.heesch']:pack(f)
