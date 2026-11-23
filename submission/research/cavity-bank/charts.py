"""Recover complete local surrounds from checked finite triangular witnesses."""
from pathlib import Path
from collections import Counter
from hashlib import sha256
import json
from heesch_verify import GRIDS, Xform, verify_witness

here = Path(__file__).resolve().parent
grid = GRIDS["I"]

def relative(t, u):
    # Inverse of t followed in composition order by u: take a world pose
    # u into the original tile's coordinate frame.
    a,b,c,d,e,f = t.a,t.b,t.c,t.d,t.e,t.f
    sign = a*e-b*d
    p,q,r,s = sign*e,-sign*b,-sign*d,sign*a
    return (p*u.a+q*u.d,p*u.b+q*u.e,p*(u.c-c)+q*(u.f-f),
            r*u.a+s*u.d,r*u.b+s*u.e,r*(u.c-c)+s*(u.f-f))

def main():
    charts={}
    for n in (8,13,17,20,22):
        file=here/"parents"/f"attempt-{n:03d}.heesch"
        w=verify_witness(file.read_text())
        assert w.submission.grid_id=="I"
        cells=frozenset(w.submission.cells)
        motions=w.submission.patches[0]
        footprints=[m.apply_all(cells) for _,m in motions]
        source_hash=sha256(file.read_bytes()).hexdigest()
        for i,(level,t) in enumerate(motions):
            if level==w.result.hc_verified:
                continue
            halo={q for p in footprints[i] for q in grid.edge_neighbors(p)}-footprints[i]
            touching=[j for j,f in enumerate(footprints) if halo&f]
            assert halo <= set().union(*(footprints[j] for j in touching))
            rel=tuple(sorted(relative(t,motions[j][1]) for j in touching))
            key=(tuple(sorted(cells)),rel)
            if key not in charts:
                charts[key]=dict(id=len(charts),attempt=n,center_index=i,source_sha256=source_hash,
                                 shape=sorted(cells),neighbors=rel)
    (here/"charts.json").write_text(json.dumps(list(charts.values()),separators=(",",":"))+"\n")
    with (here/"charts.txt").open("w") as f:
        for d in charts.values():
            fields=[d["id"],len(d["shape"]),*(v for p in d["shape"] for v in p),
                    len(d["neighbors"]),*(v for t in d["neighbors"] for v in t)]
            f.write(" ".join(map(str,fields))+"\n")
    print(len(charts),"distinct complete local surrounds",Counter(d["attempt"] for d in charts.values()))

if __name__=="__main__":
    main()
