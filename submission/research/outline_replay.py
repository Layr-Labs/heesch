"""Replay the three signed fields independently, using breadth-first graph distances."""
import argparse
import json
import sys
from collections import deque
from pathlib import Path

from heesch_verify import GRIDS, canonical_form, verify_witness
from heesch_verify.shape import check_shape

HERE=Path(__file__).resolve().parent
WORK=HERE.parent
GRID=GRIDS["H"]
WEIGHTS=((1,1,1),(3,2,1),(1,3,2),(3,2,-1),(2,-1,3),(-1,2,2))
SLOPES=((1,0),(0,1),(1,1),(-1,0),(0,-1),(-1,-1),
        (2,1),(1,2),(1,-1),(-2,-1),(-1,-2),(-1,1))


def points(values):
    nums=iter(map(int,values))
    return frozenset(zip(nums,nums,strict=True))


def turn(p, index):
    x,y=p
    if index%2:
        x,y=y,x
    for _ in range(index//2):
        x,y=-y,x+y
    return x,y


def field(cells, sites):
    def bfs(seeds, target):
        remain=set(target)
        visited={p:0 for p in seeds}
        todo=deque(seeds)
        while remain:
            p=todo.popleft()
            remain.discard(p)
            for q in GRID.edge_neighbors(p):
                if q not in visited:
                    visited[q]=visited[p]+1
                    todo.append(q)
        return visited
    exterior={q for p in cells for q in GRID.edge_neighbors(p)}-cells
    inside=bfs(exterior,cells.intersection(sites))
    outside=bfs(cells,set(sites)-cells)
    return [2*inside[p]-1 if p in cells else 1-2*outside[p] for p in sites]


def families(file):
    return {v[0]:points(v[1:]) for r in file.open() if (v:=r.split())}


def site_fields(donors,origin):
    _,a,b,rb,xb,yb,c,rc,xc,yc,wi,si,area=map(int,origin)
    primary=donors[str(a)]
    sites=set(primary)
    for _ in range(3):
        sites|={q for p in sites for q in GRID.edge_neighbors(p)}
    sites=sorted(sites)
    def moved(index,rotation,dx,dy):
        return {(u+dx,v+dy) for p in donors[str(index)] for u,v in [turn(p,rotation)]}
    registered=(primary,moved(b,rb,xb,yb),moved(c,rc,xc,yc))
    scores=list(zip(*(field(t,sites) for t in registered),strict=True))
    return registered,sites,scores


def reconstruct(donors,origin):
    *_,wi,si,area=map(int,origin)
    registered,sites,scores=site_fields(donors,origin)
    ranked=[]
    for p,raw in zip(sites,scores,strict=True):
        if max(raw)<0:
            continue
        score=sum(w*v for w,v in zip(WEIGHTS[wi],raw,strict=True))
        sx,sy=SLOPES[si]
        ranked.append((-score,sx*p[0]+sy*p[1],p))
    chosen=frozenset(p for _,_,p in sorted(ranked)[:area])
    check_shape(tuple(chosen),GRID)
    return registered,chosen


def main(folder, donor_file):
    donors=families(donor_file)
    keys={str(i) for i in range(1, 501)}
    natives={}
    for depth,name in ((3,"three"),(4,"four"),(5,"five")):
        for p in (folder/name).glob(f"*.d{depth}.heesch"):
            key=p.name.split(".")[0]
            v=verify_witness(p.read_text())
            assert v.result.hc_verified==depth
            natives.setdefault(key,{})[name]=v.result.patch_size
            keys.add(key)
    shapes={v[0]:points(v[2:]) for r in (folder/"bank.tsv").open() if (v:=r.split()) and v[0] in keys}
    periods={}
    for name in ("periods14","periods40","early-periods"):
        f=folder/(name+".tsv")
        if f.exists():
            for row in f.open():
                v=row.split()
                if v[1]=="TILER": periods[v[0]]=list(map(int,v[2:6]))
    reconstructed=0
    for line in (folder/"origins.tsv").open():
        arg=line.split()
        key=arg[0]
        if key not in keys:
            continue
        parents,body=reconstruct(donors,arg)
        assert canonical_form(body,GRID,True)==tuple(sorted(shapes[key]))
        reconstructed+=1
        if key in natives:
            natives[key].update(parents=[arg[1],arg[2],arg[6]],weights=WEIGHTS[int(arg[10])],
                                period=periods.get(key))
    result=dict(reconstructed=reconstructed,witnesses=natives)
    (folder/"origin-audit.json").write_text(json.dumps(result,indent=2)+"\n")
    print(reconstructed,"registered triples replayed;",len(natives),"positive outlines",flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("folder",type=Path)
    p.add_argument("--donors",type=Path,default=WORK/"cell-transport/finite.tsv")
    args=p.parse_args()
    main(args.folder,args.donors)
