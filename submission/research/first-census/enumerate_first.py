"""Enumerate complete first-ring domains with the benchmark's fixed-tile CNF."""
from collections import defaultdict
from pathlib import Path
import ctypes
import json
import os
import argparse
import sys
import time

from heesch_encoder.multilevel.api import encode_multilevel_stream
from heesch_encoder.multilevel.universe import multilevel_universe
from heesch_verify import verify_witness
from heesch_verify.patch import check_corona
from heesch_verify.result import VerifyError
from heesch_verify.shape import holes_of
from heesch_verify.transform import Xform


BASE=Path(__file__).resolve().parent
SOURCE=BASE/"original.heesch"

class Solver:
    def __init__(self, formula, total_vars):
        self.lib=ctypes.CDLL(str(Path(os.getenv("HEESCH_BRIDGE",str(BASE/"bridge.dylib")))))
        self.lib.first_solver.restype=ctypes.c_void_p
        self.lib.first_load.argtypes=[ctypes.c_void_p,ctypes.c_char_p]
        self.lib.first_load.restype=ctypes.c_char_p
        self.lib.first_clause.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_int),ctypes.c_int]
        self.lib.first_model.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_int),ctypes.c_int]
        self.lib.first_solve.argtypes=[ctypes.c_void_p]
        self.lib.first_phase.argtypes=[ctypes.c_void_p,ctypes.c_int]
        self.context=self.lib.first_solver()
        error=self.lib.first_load(self.context,str(formula).encode())
        if error:
            raise RuntimeError(error.decode())
        self.total_vars=total_vars
    def add_clause(self, values):
        vector=(ctypes.c_int*len(values))(*values)
        self.lib.first_clause(self.context,vector,len(values))
    def solve(self):
        status=self.lib.first_solve(self.context)
        assert status in (10,20)
        return status==10
    def phase(self, v):
        self.lib.first_phase(self.context,v)
    def get_model(self):
        vector=(ctypes.c_int*self.total_vars)()
        self.lib.first_model(self.context,vector,self.total_vars)
        return vector

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--workdir",type=Path,required=True)
    opt=parser.parse_args()
    opt.workdir.mkdir(exist_ok=True,parents=True)
    depth=4
    valid=verify_witness(SOURCE.read_text())
    sub=valid.submission;grid=sub.grid;shape=frozenset(sub.cells)
    layers=sub.patches[0]
    src_first=frozenset().union(*(t.apply_all(shape) for l,t in layers if l==1))
    universe=multilevel_universe(shape,grid,valid.contact,depth)
    print("placements",list(map(len,universe.levels)),flush=True)
    started=time.monotonic()
    cnf=opt.workdir/f"weak{depth}.cnf"
    if not cnf.exists():
        encode_multilevel_stream(shape,grid,valid.contact,depth,cnf)
    with cnf.open("rb")as file:
        _,_,nvars,nclauses=file.readline().split()
    nvars=int(nvars)
    solver=Solver(cnf,sum(map(len,universe.levels)))
    print("loaded",nvars,nclauses,time.monotonic()-started,flush=True)
    sites=defaultdict(list); all_cover=defaultdict(list); config={}
    offset=0
    for li,level in enumerate(universe.levels):
        for i,p in enumerate(level):
            var=offset+i+1
            si=grid.orientations[p.symmetry_index]
            t=Xform(si.a,si.b,si.c0+p.tx,si.d,si.e,si.f0+p.ty)
            coords=universe.cells_of[p]
            config[var]=(li+1,t,coords)
            for c in coords:
                all_cover[c].append(var)
            if li==0:
                for c in coords:
                    sites[c].append(var)
        offset+=len(level)
    occ={}
    preferred={(l,t) for l,t in layers}
    for v,(l,t,_) in config.items():
        if (l,t) in preferred:
            solver.phase(v)
    for i,(p,pvars)in enumerate(sorted(sites.items())):
        x=nvars+i+1;occ[p]=x
        solver.add_clause([-x,*pvars])
        for v in pvars:
            solver.add_clause([-v,x])

    def exclude(positive):
        solver.add_clause([-v if p in positive else v for p,v in occ.items()])
    exclude(src_first)
    found=[];rejects=0
    out=opt.workdir/f"exact{depth}"
    out.mkdir(exist_ok=True)
    while solver.solve():
        model=solver.get_model()
        selected=[v for v in config if model[v-1]>0]
        tiles=[(0,Xform(1,0,0,0,1,0)),*((l,m)for v in selected for l,m,s in [config[v]])]
        footprint=frozenset().union(*(s for v in selected for l,m,s in [config[v]] if l==1))
        assert footprint!={*src_first}
        try:
            cor=check_corona(shape,tiles,grid,valid.contact,hole_mode="hc")
            assert cor.max_level==depth
        except VerifyError as err:
            if rejects<5:
                print("weak model",rejects+1,"footprint difference",len(src_first^footprint),"geometry",str(err),flush=True)
            first_holes=holes_of(shape|footprint,grid)
            if first_holes:
                exclude(footprint)
            else:
                # A closed hole remains a hole if all its immediate wall cells
                # remain occupied and one enclosed cell stays empty. Some wall
                # owner must therefore move, or each enclosed site must fill.
                cut_count=0
                owner={c:0 for c in shape}
                for level in range(1,depth+1):
                    owner.update((c,v) for v in selected if config[v][0]==level
                                 for c in config[v][2])
                    pending=set(holes_of(frozenset(owner),grid))
                    while pending:
                        first=pending.pop()
                        stack=[first]; component={first}; walls=set()
                        while stack:
                            for n in grid.edge_neighbors(stack.pop()):
                                if n in pending:
                                    pending.remove(n); component.add(n); stack.append(n)
                                elif n in owner and owner[n]:
                                    walls.add(owner[n])
                        for c in sorted(component):
                            possible=[v for v in all_cover[c] if config[v][0]<=level
                                      and config[v][2]<=component]
                            solver.add_clause([*[-v for v in sorted(walls)],*possible])
                            cut_count+=1
                if not cut_count:
                    raise RuntimeError("Weak model failed geometry without any hole") from err
            rejects+=1
            if rejects%10==0: print("rejected",rejects,flush=True)
            continue
        exclude(footprint)
        index=len(found)+1
        item={"i":index,"first_cells_minus_center":len(footprint),"changed":len(src_first^footprint),"ring_counts":[sum(l==i for l,m in tiles)for i in range(depth+1)],"seconds":time.monotonic()-started}
        print(json.dumps(item),flush=True);found.append(item)
        text="H "+" ".join(f"{x} {y}"for x,y in sorted(shape))+f"\n~ {depth} {depth} 1\n{len(tiles)}\n"+"".join(f"{l} {t.as_text()}\n"for l,t in tiles)
        assert verify_witness(text).result.hc_verified==depth
        (out/f"changed-{index:05}.heesch").write_text(text)
    print("EXHAUSTED",len(found),rejects,"seconds",time.monotonic()-started,flush=True)
    (out/"results.json").write_text(json.dumps(found,indent=2)+"\n")


if __name__=="__main__":
    main()
