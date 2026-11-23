"""Replay the carrier markings, the 53-cell lift, both axial folds, and two scored patches."""
import hashlib
import json
import lzma
from collections import Counter
from pathlib import Path

from heesch_verify import GRIDS, VerifyConfig, canonical_digest, verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.shape import spans

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GRID = GRIDS['I']

def registration(cells):
    forms = [GRID.normalize([s.apply(p) for p in cells]) for s in GRID.orientations]
    return min(forms, key=lambda f: (sum(spans(f, GRID)), f))

def axial_fold(cells, row):
    if 'fold' in row:
        axis, low, high, dx, dy = row['fold']
        def coordinate(p):
            x, y = p
            return (x, y, -x-y)[axis] // 3
        left = {p for p in cells if coordinate(p) < low}
        right = {(x+dx, y+dy) for x,y in cells if coordinate((x,y)) >= high}
        assert left.isdisjoint(right)
        return registration(left | right)
    updated = set(cells)
    if row['remove'] is not None: updated.remove(tuple(row['remove']))
    if row['add'] is not None: updated.add(tuple(row['add']))
    return registration(updated)

def subdivide(p):
    x,y = p
    orientation = x % 3
    a,b = (x-orientation)//3, (y-orientation)//3
    return {(3*(3*a+i)+s, 3*(3*b+j)+s) for i in range(3) for j in range(3)
            for s in (0,1) if int(i+j+s>=3)==orientation}

def check_carrier():
    src = verify_witness((HERE/'marked-carrier.heesch').read_text()); sub=src.submission
    marks=json.loads((HERE/'carrier-marks.json').read_text()); words={(tuple(p),tuple(q)):z for p,q,z in marks['marks']}
    assert sum(words.values()) == -1
    tile=set(sub.cells); parent=set().union(*(subdivide(p) for p in tile))
    for (p,q),charge in words.items():
        if not charge: continue
        pair=sorted((u,v) for u in subdivide(p) for v in GRID.edge_neighbors(u) if v in subdivide(q))[1]
        if charge>0: parent.add(pair[1])
        else: parent.remove(pair[0])
    held={};pairs=0
    for level,t in sub.patches[0]:
        for (p,q),mark in words.items():
            u,v=t.apply(p),t.apply(q)
            if (v,u) in held:assert held[v,u]+mark==0;pairs+=1
            held[u,v]=mark
    assert pairs==marks['contacts']==90
    lifted=verify_witness((HERE/'parent53.heesch').read_text(), VerifyConfig(max_span_sum=100));shape=lifted.submission.cells
    assert parent==set(shape) and len(shape)==53 and len(lifted.submission.patches[0])==37
    fringe={q for p in parent for q in GRID.edge_neighbors(p)}-parent
    recesses=sum(sum(q in parent for q in GRID.edge_neighbors(p))>=2 for p in fringe)
    leaves=sum(sum(q in parent for q in GRID.edge_neighbors(p))==1 for p in parent)
    assert(recesses,leaves)==(3,2)
    return tuple(shape)

def digest_xz(path):
    h=hashlib.sha256()
    with lzma.open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1<<20), b''): h.update(chunk)
    return h.hexdigest()

def run():
    parent=check_carrier()
    for row in json.loads((HERE/'construction.json').read_text()):
        shape=parent
        for step in row['moves']:
            shape=axial_fold(shape,step)
            assert len(shape)==step['cells'] and sum(spans(shape,GRID))==step['span']
        path=ROOT/row['file']; raw=path.read_text(); ck=verify_witness(raw); s=ck.submission
        assert canonical_digest(shape,GRID,True)==row['digest']==canonical_digest(s.cells,GRID,True)
        assert [Counter(k for k,_ in s.patches[0])[i] for i in range(4)]==row['rings'] and ck.result.hc_verified==3
        d=verify_defect(frozenset(s.cells),s.grid,ck.hc_corona,s.defect,ck.contact)
        assert (d.defect_hc,d.defect_hh,d.required,d.partial_tiles)==(row['charged'],row['gaps'],row['required'],row['partial'])
        for line in raw.splitlines():
            tokens=line.split()
            if tokens and tokens[0]=='file':assert digest_xz(path.parent/tokens[1])==tokens[4]
            if tokens and tokens[0]=='core':assert digest_xz(path.parent/tokens[1])==tokens[3]
        print(row['area'],row['digest'],row['rings'],d, row['score'])
    prior=json.loads((HERE/'census16.json').read_text())[0];v=list(map(int,prior['coordinates'].split()));assert prior['classification']=='Hc = 3 Hh = 3' and canonical_digest(list(zip(v[::2],v[1::2])),GRID,True)==json.loads((HERE/'construction.json').read_text())[1]['digest']
if __name__=='__main__':run()
