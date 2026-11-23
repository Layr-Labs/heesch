"""Rebuild the five strip substitutions and check them against the stored witnesses."""
from pathlib import Path
from collections import Counter
import json,sys
from heesch_verify import verify_witness,Xform, canonical_form
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from atlas import solve

def warp_chart(path,depth):
    sub=verify_witness(path.read_text()).submission; shape=set(sub.cells); poses=[(l,t) for l,t in sub.patches[0] if l<=depth]
    parent={}
    def root(k):
        p=parent.setdefault(k,k)
        if p!=k:parent[k]=root(p)
        return parent[k]
    def union(k,z):parent[root(k)]=root(z)
    for l,t in poses:
        for x,y in shape:
            u,v=t.apply((x,y)); union((0,u),(0,x) if t.a else (1,y));union((1,v),(0,x) if t.d else (1,y))
    master=sorted({root(k) for k in parent}); ids={k:master.index(root(k)) for k in parent}; print(path.stem,depth,'orbits',len(master),'axis indices',[[ids[(axis,i)] for i in sorted({q[axis] for q in shape})] for axis in (0,1)],flush=True)
    return shape,poses,ids,master

def realize(shape,poses,ids,values):
    axes=[]
    for axis in (0,1):
        indices=[k for a,k in ids if a==axis]; span=range(min(indices),max(indices)+1); ax={span.start:0}
        for n in span:ax[n+1]=ax[n]+(values[ids[axis,n]] if (axis,n) in ids else 1)
        off=ax[0];axes.append({k:w-off for k,w in ax.items()})
    X,Y=axes; tile={(u,v) for x,y in shape for u in range(X[x],X[x+1]) for v in range(Y[y],Y[y+1])}
    spots=[(l,Xform(t.a,t.b,X[t.c+(t.a+t.b<0)]-(t.a+t.b<0),t.d,t.e,Y[t.f+(t.d+t.e<0)]-(t.d+t.e<0))) for l,t in poses]
    return tile,spots


if __name__=='__main__':
    directory=Path(__file__).resolve().parent
    for row in json.loads((directory/'families.json').read_text()):
        source=directory/f"parent-{row['parent_area']}.heesch"
        parent,poses,ids,classes=warp_chart(source,3)
        assert len(classes)==len(row['widths'])==2
        outline,motions=realize(parent,poses,ids,row['widths'])
        witness=verify_witness((directory/f"child-{row['area']}.heesch").read_text())
        assert canonical_form(outline,witness.submission.grid,True)==canonical_form(witness.submission.cells,witness.submission.grid,True)
        assert set((l,t.as_text()) for l,t in motions)==set((l,t.as_text()) for l,t in witness.submission.patches[0])
        assert len(outline)==row['area'] and witness.result.hc_verified==3
        assert solve(frozenset(outline))==row['atlas'] and row['atlas']['layers'][-1]==0
    alt=verify_witness((directory/'independent-108.heesch').read_text())
    ref=verify_witness((directory/'child-108.heesch').read_text())
    assert canonical_form(alt.submission.cells,alt.submission.grid,True)==canonical_form(ref.submission.cells,ref.submission.grid,True)
    assert Counter(alt.hc_corona.levels)[1]==6 and Counter(ref.hc_corona.levels)[1]==5
    print('All five finite shapes and the independent 108-square witness verified.')
