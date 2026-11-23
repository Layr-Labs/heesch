"""Decode positive level-major variables of the square tile's official F(S,4) model.

The precomputed relative-displacement table enumerates every disjoint point-contact pair.
Translation by a previously reached placement performs the same universe BFS as the frozen encoder.
"""
from collections import Counter
from pathlib import Path
import argparse
import json
import numpy as np
from heesch_verify import canonical_form, verify_witness, Xform
from heesch_verify.patch import check_corona, contact_neighbors, required_set
from heesch_verify.shape import holes_of


def universe(shape, grid, contact, depth):
    oriented = [frozenset(sym.apply(p) for p in shape) for sym in grid.orientations]
    def offsets(a,b):
        collision={(x-u,y-v) for x,y in a for u,v in b}
        touch={(x-u,y-v) for x,y in contact_neighbors(a,contact) for u,v in b}
        return touch-collision, collision|touch
    legal=[[offsets(a,b)[0] for b in oriented] for a in oriented]
    prohibited=[offsets(shape,b)[1] for b in oriented]
    reached=[offsets(shape,b)[0] for b in oriented]
    levels=[]
    for level in range(1,depth+1):
        levels.append([(j,dx,dy) for j,coords in enumerate(reached) for dx,dy in sorted(coords,key=lambda p:(p[1],p[0]))])
        if level==depth: break
        furthest=max(max(abs(i) for i in p) for group in reached for p in group)
        step=max(max(abs(i) for i in p) for row in legal for group in row for p in group)
        margin=furthest+step+1
        images=[np.zeros((2*margin+1,2*margin+1), dtype=np.bool_) for _ in oriented]
        for j,coords in enumerate(reached):
            coords=np.asarray(list(coords),dtype=np.int32)
            for k,group in enumerate(legal[j]):
                for dx,dy in group:
                    images[k][coords[:,0]+dx+margin,coords[:,1]+dy+margin]=True
        reached=[{(int(x)-margin,int(y)-margin) for x,y in np.argwhere(image)}-prohibited[k] for k,image in enumerate(images)]
    return levels


def materialize(shape, grid, contact, levels, positive, out):
    selected=[(0,Xform(1,0,0,0,1,0))]; selected_vars=[]; offset=0
    for level,bucket in enumerate(levels,1):
        for i,(j,dx,dy) in enumerate(bucket,offset+1):
            if i not in positive: continue
            s=grid.orientations[j];selected.append((level,Xform(s.a,s.b,s.c0+dx,s.d,s.e,s.f0+dy)));selected_vars.append(i)
        offset+=len(bucket)
    holes=[]; gaps=[]; counts=[]; points=set(); required=set()
    for k in range(len(levels)+1):
        level_poses=[t for l,t in selected if l==k];counts.append(len(level_poses)); outer=set().union(*(t.apply_all(shape) for t in level_poses))
        gaps.append(len(required-outer)); points.update(outer);holes.append(len(holes_of(points,grid))); required=required_set(points,contact)
    lines=['O '+' '.join(f'{x} {y}' for x,y in sorted(shape,key=lambda p:(p[1],p[0]))),f'~ {len(levels)} {len(levels)} 1',str(len(selected))]
    text='\n'.join(lines+[f'{l} {t.as_text()}' for l,t in selected])+'\n'
    check_corona(shape,selected,grid,contact,hole_mode='none')
    try:
        result=verify_witness(text).result
        if result.hc_verified < result.hh_verified:
            through_solid=[(lev,t) for lev,t in selected if lev<=result.hc_verified]
            records=[lines[0],f'~ {result.hc_verified} {result.hh_verified} 2',str(len(through_solid))]
            records += [f'{lev} {t.as_text()}' for lev,t in through_solid]
            records += [str(len(selected))]+[f'{lev} {t.as_text()}' for lev,t in selected]
            text='\n'.join(records)+'\n'
        validated=verify_witness(text).result
        assert not validated.claim_discrepancy
        verified=[validated.hc_verified,validated.hh_verified]
    except Exception as exc:
        verified=str(exc)
    out.write_text(text); path=out.with_suffix('.json');path.write_text(json.dumps(dict(universe=list(map(len,levels)),copies=counts,gaps=gaps,holes=holes,verified=verified,selected_variables=selected_vars),indent=1)+'\n')
    print(path.read_text(),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('tile',type=Path);parser.add_argument('model',type=Path);parser.add_argument('out',type=Path);args=parser.parse_args()
    parsed=verify_witness(args.tile.read_text());grid=parsed.submission.grid;shape=frozenset(canonical_form(parsed.submission.cells,grid,True)); levels=universe(shape,grid,parsed.contact,4)
    size=sum(len(lv) for lv in levels);positive=set()
    with args.model.open() as stream:
        for line in stream:
            if line.startswith('v '):
                terms=[int(word) for word in line[2:].split()];positive.update(lit for lit in terms if 0<lit<=size)
                if terms and abs(terms[-1])>size:break
    materialize(shape,grid,parsed.contact,levels,positive,args.out)
