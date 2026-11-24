"""Independently replay the incidence changes of every deep geometric witness."""
from collections import Counter, defaultdict
from pathlib import Path
import json
import sys
from heesch_verify import GRIDS,canonical_form,verify_witness

HERE=Path(__file__).resolve().parent
GRID=GRIDS["H"]
DIR=((1,0),(0,1),(-1,1),(-1,0),(0,-1),(1,-1))
CORNERS=((2,0),(1,1),(-1,1),(-2,0),(-1,-1),(1,-1))


def neighbor(p,i):
    x,y=p
    u,v=DIR[i]
    return x+u,y+v


def edge(i,j):
    return tuple(sorted((i,j)))


def get_xy(tokens):
    data=iter(map(int,tokens))
    return tuple(zip(data,data,strict=True))


def physical_graph(xy):
    at={p:i for i,p in enumerate(xy)}
    assert len(at)==len(xy)
    return {edge(i,at[q]) for i,p in enumerate(xy) for q in GRID.edge_neighbors(p) if q in at}


def domino(source,u,v):
    index={p:i for i,p in enumerate(source)}
    rim={}
    for z in [u,v]:
        x,y=source[z];center=(3*x,x+2*y)
        for k in range(6):
            a=tuple(map(sum,zip(center,CORNERS[k])))
            b=tuple(map(sum,zip(center,CORNERS[(k+1)%6])))
            if (b,a) in rim:
                del rim[b,a]
            else:
                rim[a,b]=z,index.get(neighbor(source[z],k))
    parent={a:b for a,b in rim}
    a=min(parent);walk=[]
    for _ in range(10):
        b=parent[a];walk.append(rim[a,b]);a=b
    assert a==min(parent) and len(rim)==10
    return walk


def reconstruct(original,words,kind):
    bonds=physical_graph(original)
    absent=set()
    n=len(original)
    nextid=n
    index={p:i for i,p in enumerate(original)}
    for word in words:
        op=word[0] if kind=="flips-pilot" else "S" if kind=="pilot" else "T"
        vals=tuple(map(int,(word[1:] if kind=="flips-pilot" else word).split(",")))
        if op=="S":
            v,mask,common=vals
            bonds.add(edge(v,nextid))
            for k in range(6):
                if not mask&(1<<k):
                    continue
                j=index[neighbor(original[v],k)]
                if not common&(1<<k):
                    bonds.remove(edge(v,j))
                bonds.add(edge(nextid,j))
            nextid+=1
        elif op=="F":
            u,v,a,b=vals
            bonds.remove(edge(u,v));bonds.add(edge(a,b));absent.add(edge(u,v))
            assert all(edge(i,j) in bonds for i in (u,v) for j in (a,b))
        elif op=="E":
            bonds.remove(edge(*vals))
        else:
            assert op=="T"
            u,v,_,*masks=vals
            ring=domino(original,u,v)
            for own,j in ring:
                if j is not None:
                    bonds.discard(edge(own,j))
            vertices=[u,v,nextid]
            for i,mask in enumerate(masks):
                bonds.add(edge(vertices[i],vertices[(i+1)%3]))
                for k,(_,other) in enumerate(ring):
                    if mask&(1<<k) and other is not None:
                        bonds.add(edge(vertices[i],other))
            nextid+=1
    return nextid,bonds,absent


def main(folder):
    report=json.loads((folder/"patch-audit.json").read_text())
    leads=report["leads"]
    deep={k for k,x in leads.items() if "four" in x or "five" in x or "porous" in x}
    picked={f[0]:(f[1],get_xy(f[2:])) for line in (folder/"routes.tsv").open() if (f:=line.split()) and f[0] in deep}
    assert set(picked)==deep
    requested={j for j,xy in picked.values()}
    systems={f[0]:(f[1],f[7:]) for line in (folder/"systems.tsv").open() if (f:=line.split()) and f[0] in requested}
    assert systems.keys()==requested
    sources={f[0]:get_xy(f[1:]) for l in (HERE.parent/"cell-transport/finite.tsv").open() if (f:=l.split())}
    hist=Counter();shapes={}
    for key,(system,labeled) in picked.items():
        donor,words=systems[system]
        n,needed,absent=reconstruct(sources[donor],words,folder.name)
        physical=physical_graph(labeled)
        assert n==len(labeled) and needed<=physical and not absent&physical
        canonical=canonical_form(labeled,GRID,True)
        value=leads[key]
        name,level=("five",5) if "five" in value else ("four",4)
        w=verify_witness((folder/name/f"{key}.d{level}.heesch").read_text())
        assert canonical==canonical_form(w.submission.cells,GRID,True)
        additional=len(physical-needed)
        hist[additional]+=1
        shapes[key]=dict(source=donor,system=system,moves=words,bonds=len(needed),additional=additional,
                         area=n,digest=w.result.canonical_digest,depth=level,copies=value[name],period=value.get("period"))
    (folder/"deep-origin-audit.json").write_text(json.dumps(dict(count=len(deep),extra_bonds=hist,
                                                cases=shapes),separators=(",",":"))+"\n")
    print(folder.name,len(deep),"deep lineages replayed",sorted(hist.items()),flush=True)


if __name__=="__main__":
    for arg in sys.argv[1:]:main(Path(arg))
