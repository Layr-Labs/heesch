"""Independently replay consistency of adjacent local tiling stars as cell partitions."""
from pathlib import Path
from collections import Counter,defaultdict
from hashlib import sha256
import json, sys
from heesch_verify import Xform,GRIDS,verify_witness
from heesch_verify.shape import holes_of
from heesch_verify.transform import check_symmetry

D=Path(__file__).resolve().parent
G=GRIDS['O']
identity=Xform(1,0,0,0,1,0)

def invert(t):
    a,b,c,d,e,f=(t.a,t.b,t.c,t.d,t.e,t.f); sign=a*e-b*d
    return Xform(sign*e,-sign*b,sign*(b*f-e*c),-sign*d,sign*a,sign*(d*c-a*f))

def compose(t,s):
    a,b,c,d,e,f=(t.a,t.b,t.c,t.d,t.e,t.f); g,h,i,j,k,l=(s.a,s.b,s.c,s.d,s.e,s.f)
    return Xform(a*g+b*j,a*h+b*k,a*i+b*l+c,d*g+e*j,d*h+e*k,d*i+e*l+f)

def all_stars(shape):
    frontier={outside for p in shape for outside in G.edge_neighbors(p)}-shape
    poses={}
    for o in G.orientations:
        rotated={o.apply(p) for p in shape}
        for x,y in {(a-p,b-q) for a,b in frontier for p,q in rotated if G.translation_legal(a-p,b-q)}:
            pose=Xform(o.a,o.b,o.c0+x,o.d,o.e,o.f0+y); cells=pose.apply_all(shape)
            if cells&shape or len(holes_of(cells|shape,G))%len(shape):continue
            poses[pose]=cells
    assert len(set(poses.values()))==len(poses)
    ops=list(poses);covers={p:set() for p in frontier};conflicts={}
    for t in ops:
        for p in frontier & poses[t]:covers[p].add(t)
        conflicts[t]={u for u in ops if poses[t]&poses[u]}
    full=[]
    def place(remain,eligible,star):
        if not remain:
            full.append(tuple(star));return
        alternatives=min((covers[p]&eligible for p in remain),key=len)
        for t in alternatives:place(remain-poses[t],eligible-conflicts[t],star+[t])
    place(frontier,set(ops),[]);return poses,full

def coarsen(possible,groups):
    active_directions={t for t,sids in groups.items() if t!='stars' and not sids.isdisjoint(possible)}
    viable={t for t in active_directions if invert(t) in active_directions}
    return {index for index in possible if all(t in viable for t in groups['stars'][index])}

def solve(shape,trace=None,fixed_stars=None):
    poses,stars=all_stars(shape);n=len(stars);members=defaultdict(set)
    for sid,star in enumerate(stars):
        for t in star:members[t].add(sid)
    members['stars']=stars;remaining=set(range(n));rec=[]
    while True:
        surviving=coarsen(remaining,members);rec.append(len(surviving))
        if surviving==remaining:break
        remaining=surviving
    remaining=sorted(remaining);selected=[stars[j] for j in remaining];N=len(selected)
    exists={k:bytearray((N+7)//8) for k in poses}
    for j,star in enumerate(selected):
        for t in star:exists[t][j//8]|=1<<(j%8)
    exists={k:int.from_bytes(v,'little') for k,v in exists.items()};eligible=(1<<N)-1
    supports={};relevant=[k for k,v in exists.items() if v]
    # At tile A place tB. A third-copy pose s around A is compatible with
    # a third-copy pose v around B iff their cells are disjoint or exactly equal.
    for t in relevant:
        back=invert(t);incoming=exists[back]
        cells_by_point=defaultdict(list)
        for v in relevant:
            if exists[v]&incoming:
                image=t.apply_all(poses[v]);
                for p in image:cells_by_point[p].append((v,image))
        for s in relevant:
            if not exists[s]&exists[t]:continue
            center_image=poses[s];compatible=incoming
            all_overlapping={v for p in center_image for v,img in cells_by_point[p] if img!=center_image}
            for v in all_overlapping:compatible&=~exists[v]
            supports[t,s]=compatible
    stats=[]
    while True:
        keep=bytearray((N+7)//8); x=eligible
        while x:
            bit=x&-x;index=bit.bit_length()-1;x^=bit;star=selected[index];ok=True
            for t in star:
                candidates=eligible
                for s in star:
                    candidates&=supports[t,s]
                    if not candidates:break
                if not candidates:ok=False;break
            if ok:keep[index//8]|=1<<(index%8)
        nxt=int.from_bytes(keep,'little');stats.append(nxt.bit_count());print('compatibility',len(stats),stats[-1],flush=True)
        if trace is not None and nxt:
            sid=(nxt&-nxt).bit_length()-1
            trace.append(dict(pass_number=len(stats),remaining=stats[-1],poses=sorted(x.as_text() for x in selected[sid])))
        if not nxt or nxt==eligible:
            if fixed_stars is not None:
                live=[j for j in range(N) if nxt>>j&1];axes={j:i for i,j in enumerate(live)}
                for j in live:
                    star=selected[j];links=[]
                    for t in sorted(star,key=lambda pose:pose.as_text()):
                        cand=nxt
                        for s in star:cand&=supports[t,s]
                        links.append(dict(pose=t.as_text(),neighbors=[axes[q] for q in live if cand>>q&1]))
                    fixed_stars.append(links)
            break
        eligible=nxt
    return dict(poses=len(poses),raw=len(stars),reciprocal=rec,layers=stats)

if __name__=='__main__':
    import argparse
    args=argparse.ArgumentParser();args.add_argument('input',type=Path);args.add_argument('output',type=Path);args.add_argument('--trace',type=Path);opts=args.parse_args();sub=verify_witness(opts.input.read_text()).submission;trace=[];answer=solve(frozenset(sub.cells),trace);opts.output.write_text(json.dumps(answer,indent=2)+'\n');print(answer,flush=True)
    if opts.trace:opts.trace.write_text(json.dumps(trace,indent=2)+'\n')
