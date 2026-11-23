"""Replay two independent periodic packings with one vacancy, two solid thirds, and a porous fourth."""
from collections import Counter
import json
from pathlib import Path
from fractions import Fraction
from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.canonical import canonical_digest
from heesch_verify.shape import holes_of

HERE=Path(__file__).resolve().parent


def parse(file):
    w=verify_witness(file.read_text())
    shape=frozenset(w.submission.cells)
    d=verify_defect(shape,w.submission.grid,w.hc_corona,w.submission.defect,w.contact)
    return w,dict(charged=d.defect_hc,missed=d.defect_hh,required=d.required,partial=d.partial_tiles)


def quotient(r,shape):
    label,n,k,a,b,c,dx,dy=r.split()
    n,k,a,b,c,dx,dy=map(int,(n,k,a,b,c,dx,dy))
    cells=frozenset((x+dx,y+dy)for x,y in shape)
    counts=Counter()
    for i in range(k):
        for x,y in cells:
            q,t=divmod(y,c)
            counts[(x-q*b)%a,t]+=1
        if k==2:cells=frozenset((-x,-y) for x,y in cells)
        elif k==6:cells=frozenset((-y,x+y) for x,y in cells)
        else:raise AssertionError(k)
    assert n==len(shape) and k*n+1==a*c
    assert len(counts)==k*n and set(counts.values())=={1}
    vacancy={(i,j) for i in range(a) for j in range(c)}-counts.keys()
    assert vacancy=={(0,0)}
    return dict(k=k,lattice=(a,b,c),shift=(dx,dy),occupied=len(counts),vacant=list(vacancy))


def check_certificate(w):
    from hashlib import sha256
    import lzma
    record=json.loads((HERE/"proof-manifest.json").read_text())
    dec=w.submission.proof
    assert w.result.canonical_digest==record['canonical_digest']
    assert (dec.m,dec.num_vars,dec.num_clauses,dec.cnf_digest)==(record["m"],record['num_vars'],record['num_clauses'],record['cnf_digest'])
    assert dec.fmt=='drat' and not dec.core_file
    for name,digest in [(dec.file_name,dec.payload_sha256)]:
        h=sha256()
        with lzma.open(HERE.parent/name,'rb') as f:
            while data:=f.read(1024*1024):h.update(data)
        assert record['certificates'][name]['raw_sha256']==h.hexdigest()==digest

def main():
    w, best = parse(HERE.parent/'best.heesch')
    earlier, compact = parse(HERE/'compact-third.heesch')
    old, start = parse(HERE/'starting-third.heesch')
    native = verify_witness((HERE/'native-third.heesch').read_text())
    keys = {r.result.canonical_digest for r in (w, earlier, old, native)}
    assert keys == {'deb178796af4a803898f879d911e739c137e0f30a6f26e2606d484a27c46b224'}
    assert (w.result.hc_verified,w.result.hh_verified)==(3,3)
    assert tuple(compact.values())==(14,14,186,31)
    assert start['charged']==46 and start['required']==208
    assert tuple(best.values()) == (6,6,181,34)
    wide, wider = parse(HERE/'wide-third.heesch')
    assert tuple(wider.values()) == (8,8,233,43)
    assert wide.result.canonical_digest == w.result.canonical_digest
    earlier_sample=json.loads((HERE/'fixed-sample.json').read_text())
    assert len(earlier_sample)==49 and [r['source'] for r in earlier_sample if r['bound']*233 < 8*r['B']]==['patch-032.heesch']
    assert json.loads((HERE/'six-over-181.json').read_text())[-1]['status']=='INFEASIBLE'
    sample=json.loads((HERE/'sample-240.json').read_text())
    assert len(sample)==240 and sum('exclusion' in r for r in sample)==25
    assert all(r['bound'] > r['strict_budget'] or r['exclusion']['status']=='INFEASIBLE' for r in sample)
    s=frozenset(w.submission.cells)
    frames=[quotient(row,s) for row in (HERE/'quotients.tsv').read_text().splitlines()]
    assert len({canonical_digest(v.hc_corona.patch_cells,v.submission.grid,True) for v in (w,earlier,old)})==3
    bounds=json.loads((HERE/'fixed-bounds.json').read_text())
    entry=next(x for x in bounds if x['source']=='patch-019.heesch')
    assert entry['phases'][-1]['cap']==13 and entry['phases'][-1]['status']=='INFEASIBLE'
    check_certificate(w)
    print(json.dumps(dict(shape=next(iter(keys)),Hc_lower=3,Hh_lower=3,quotients=frames,compact=compact,initial=start,best=best,score=str(4-Fraction(best['charged'],best['required'])))))

if __name__=='__main__':main()
