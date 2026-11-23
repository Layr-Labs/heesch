"""Replay pair types, their fixed point and a finite integer separator in Python."""
from collections import Counter
from pathlib import Path
import json

from heesch_verify import GRIDS, verify_witness
from heesch_verify.transform import Xform

B = Path(__file__).resolve().parent

def tupled(t):
    return (t.a,t.b,t.c,t.d,t.e,t.f)

def inverse(t):
    a,b,x,d,e,y=tupled(t)
    k=a*e-b*d
    return Xform(k*e,-k*b,k*(b*y-e*x),-k*d,k*a,k*(d*x-a*y))

def compose(t,s):
    return Xform(t.a*s.a+t.b*s.d,t.a*s.b+t.b*s.e,t.a*s.c+t.b*s.f+t.c,
                 t.d*s.a+t.e*s.d,t.d*s.b+t.e*s.e,t.d*s.c+t.e*s.f+t.f)

def solve_tile(witness, certificate):
    outcome = verify_witness(witness.read_text())
    cert = json.loads(certificate.read_text())
    tile = frozenset(outcome.submission.cells)
    assert sorted(tile) == sorted(tuple(p) for p in cert["shape"])
    grid=GRIDS["H"]
    halo = {q for p in tile for q in grid.edge_neighbors(p)} - tile
    sites = sorted(halo)
    motions, shapes = [], []
    for o in grid.orientations:
        turned = {o.apply(p) for p in tile}
        for dx,dy in sorted({(x-u,y-v) for x,y in sites for u,v in turned}):
            shape = frozenset((u+dx,v+dy) for u,v in turned)
            if shape.isdisjoint(tile):
                motions.append(Xform(o.a,o.b,dx,o.d,o.e,dy))
                shapes.append(shape)
    motion_index = {t:i for i,t in enumerate(motions)}
    domain = (1<<len(motions))-1
    coverer = [sum(1<<i for i,shape in enumerate(shapes) if p in shape) for p in sites]
    cover = [sum(1<<j for j,p in enumerate(sites) if p in shape) for shape in shapes]
    disjoint = [sum(1<<j for j,other in enumerate(shapes) if other.isdisjoint(shape)) for shape in shapes]
    inv = [inverse(t) for t in motions]
    rel = [[motion_index.get(compose(t,s),-1) for s in motions] for t in inv]
    reverse = [motion_index[t] for t in inv]
    stars = []
    path = []
    def visit(sites_left,moves):
        if not sites_left:
            stars.append(tuple(path))
            return
        options = min((coverer[i]&moves for i in range(len(sites)) if (sites_left>>i)&1),key=int.bit_count)
        while options:
            bit = options&-options
            i = bit.bit_length()-1
            path.append(i)
            visit(sites_left&~cover[i],moves&disjoint[i])
            path.pop()
            options ^= bit
    visit((1<<len(sites))-1, domain)
    table, decisions = {}, []
    def token(row):
        return table.setdefault(row,len(table))
    for star in stars:
        row = []
        for i in star:
            matches = sorted((j,rel[i][j]) for j in star if j!=i and rel[i][j]>=0)
            own = (i,tuple(j for j,k in matches))
            back = (reverse[i],tuple(sorted(k for j,k in matches)))
            row.append((token(own),token(back)))
        decisions.append(row)
    active = list(range(len(stars)))
    history = [len(active)]
    while active:
        present = {x for i in active for x,y in decisions[i]}
        allowed = [i for i in active if all(y in present for x,y in decisions[i])]
        if active == allowed: break
        active = allowed
        history.append(len(active))
    by_token = {v:k for k,v in table.items()}
    def signature(x):
        n,adj = by_token[x]
        return (tupled(motions[n]), tuple(sorted(tupled(motions[j]) for j in adj)))
    def unpack(value):
        return tuple(value[0]),tuple(tuple(a) for a in value[1])
    weight = {}
    for record in cert["weights"]:
        a,b = unpack(record["forward"]),unpack(record["reverse"])
        assert a != b and a not in weight and b not in weight
        weight[a],weight[b] = record["weight"],-record["weight"]
    margins=[]
    observed=set()
    for i in active:
        total=0
        for a,b in decisions[i]:
            x,y=signature(a),signature(b)
            observed.add(x)
            assert weight.get(x,0) == -weight.get(y,0)
            total+=weight.get(x,0)
        margins.append(total)
    assert set(weight) <= observed
    assert history == cert["unrestricted_pair_history"]
    assert sorted(margins) == cert["margins"] and min(margins) > 0
    assert len(motions)==cert["contacts"]
    print("raw contacts",len(motions),"full-star counts",history,"per-star margins",sorted(margins))

if __name__=="__main__":
    solve_tile(B/"four.heesch",B/"weights.json")
