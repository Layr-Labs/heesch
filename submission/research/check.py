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


def main():
    w,p= parse(HERE.parent/"best.heesch")
    old,earlier = parse(HERE/"other-third.heesch")
    pore,full = parse(HERE/"complete-porous.heesch")
    old_best,previous=parse(HERE/"three-over-134.heesch")
    shape = frozenset(w.submission.cells)
    digest = w.result.canonical_digest
    assert digest == old.result.canonical_digest == pore.result.canonical_digest
    assert [w.result.hc_verified,w.result.hh_verified]==[3,4]
    assert tuple(earlier.values())==(34,33,166,27)
    assert tuple(previous.values())==(3,2,134,26) and tuple(full.values())==(16,0,134,27)
    assert tuple(p.values())==(2,2,127,24)
    reports=json.loads((HERE/"diversified-thirds.json").read_text())
    assert len(reports)==7 and all(r["status"]["status"]=="INFEASIBLE" for r in reports)
    assert sum(r["B"]==127 and r["cap"]==1 for r in reports)==2
    assert canonical_digest(w.hc_corona.patch_cells,w.submission.grid,True)!=canonical_digest(old.hc_corona.patch_cells,w.submission.grid,True)
    level4=frozenset().union(*(t.apply_all(shape) for l,t in w.submission.patches[1]))
    assert len(holes_of(level4,w.submission.grid))==4
    histogram=dict(l.split() for l in (HERE/'complete-fourth-census/counts.tsv').read_text().splitlines())
    assert int(histogram['raw_placements'])==int(histogram['small_trapped'])==9046575 and int(histogram['remaining'])==0
    assert int(histogram['4'])==552 and min(int(h) for h in histogram if h.isdigit())==4
    prior4=frozenset().union(*(t.apply_all(shape) for l,t in pore.submission.patches[1]))
    assert len(holes_of(prior4,w.submission.grid))==16
    models=json.loads((HERE/"packing.json").read_text())
    assert models["termination"]["status"]=="INFEASIBLE" and models["patches"][-1]["defect"]==3
    frames=[quotient(row,shape)for row in (HERE/"quotients.tsv").read_text().splitlines()]
    print(json.dumps(dict(shape=digest,Hc_lower=3,Hh_lower=4,quotients=frames,
                          first=earlier,full=full,optimized=p,score=str(4-Fraction(2,127)))))


def compact_check():
    from hashlib import sha256
    import lzma
    from heesch_verify.proofgate import materialize_proof
    from heesch_verify.profile import RECORD
    from tempfile import TemporaryDirectory
    data=json.loads((HERE/'compact-certificate.json').read_text())
    witness=verify_witness((HERE.parent/'best.heesch').read_text())
    block=witness.submission.proof
    assert block is not None and block.m==5 and block.cnf_digest==data['formula_sha256']
    assert witness.result.canonical_digest==data['shape_sha256'] and block.payload_sha256==data['payload_sha256']
    assert block.num_vars==data['variables'] and block.num_clauses==data['original_formula_clauses']
    with TemporaryDirectory() as work:
        raw,sha=materialize_proof(HERE.parent/block.file_name,Path(work)/'certificate','xz',RECORD.proof_max_stored_bytes,RECORD.proof_max_payload_bytes)
        assert raw==data['payload_bytes'] and sha==block.payload_sha256
    assert 's VERIFIED' in (HERE/'compact-drat-check.log').read_text()
    assert 'c VERIFIED' in (HERE/'compact-lrat-check.log').read_text()
    print(json.dumps(dict(m=block.m,raw_bytes=raw,sha256=sha,full_cnf=block.cnf_digest,stored_bytes=(HERE.parent/block.file_name).stat().st_size)))

if __name__=="__main__":
    main()
    compact_check()
