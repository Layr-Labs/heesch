"""Replay the donor placements, mixed central surround, scored patch and certificate payload."""
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import json
import lzma

from heesch_verify import GRIDS, Xform, canonical_form, verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of

base=Path(__file__).resolve().parent
data=json.loads((base/"origin.json").read_text())
grid=GRIDS["H"]
identity=Xform(1,0,0,0,1,0)
def parse(t):return Xform(*map(int,t.strip("<>").split(",")))
def compose(a,b):
    return Xform(a.a*b.a+a.b*b.d,a.a*b.b+a.b*b.e,a.a*b.c+a.b*b.f+a.c,
                 a.d*b.a+a.e*b.d,a.d*b.b+a.e*b.e,a.d*b.c+a.e*b.f+a.f)
def inverse(t):
    return Xform(t.e//t.det,-t.b//t.det,(t.b*t.f-t.e*t.c)//t.det,
                 -t.d//t.det,t.a//t.det,(t.d*t.c-t.a*t.f)//t.det)
def star(body,chart):
    rim=required_set(body,donor.contact)
    copies=[t.apply_all(body) for t in chart]
    union=set(body)
    for cells in copies:
        assert cells&rim and not cells&union
        union.update(cells)
    assert rim<=union and not holes_of(frozenset(union),grid)
def observed(w,chart):
    s=frozenset(w.submission.cells)
    poses=w.submission.patches[0]
    need=set(chart)
    for level,t in poses:
        if level>1:continue
        rim=required_set(t.apply_all(s),w.contact)
        neighbors={compose(inverse(t),p) for _,p in poses if p!=t and p.apply_all(s)&rim}
        if neighbors==need:return True
    return False
finite=verify_witness((base/"finite-parent.heesch").read_text())
donor=verify_witness((base/"periodic-parent.heesch").read_text())
assert finite.result.hc_verified==4 and donor.result.hc_verified==5
frame=parse(data["registration"])
fstars=set(map(parse,data["finite_star"]))
pstars=set(map(parse,data["periodic_star"]))
newstar=set(map(parse,data["star"]))
assert observed(finite,fstars)
original_periodic={compose(compose(inverse(frame),u),frame) for u in pstars}
assert observed(donor,original_periodic)
child=frozenset(map(tuple,data["child"]))
assert newstar<=fstars|pstars and newstar&(fstars-pstars) and newstar&(pstars-fstars)
star(child,newstar)
parent=frozenset(donor.submission.cells)
cut=parse(data["broken_contact"])
in_donor=compose(compose(inverse(frame),cut),frame)
n,a,b,c,*ops=data["period"]
ops=list(map(parse,ops))
occ={}
def fold(x,y):
    q,r=divmod(y,c)
    return (x-b*q)%a,r
for i,t in enumerate(ops):
    for z in t.apply_all(parent):
        site=fold(*z)
        assert site not in occ
        occ[site]=(i,z)
assert len(occ)==a*c==n*len(parent)==len(ops)*len(parent)
occurrences=0
for t in ops:
    placed=compose(t,in_donor)
    footprint=placed.apply_all(parent)
    if footprint&required_set(t.apply_all(parent),donor.contact):
        witness=set()
        for x,y in footprint:
            i,(xx,yy)=occ[fold(x,y)]
            p=ops[i]
            witness.add((p.a,p.b,p.c+x-xx,p.d,p.e,p.f+y-yy))
        if len(witness)==1 and Xform(*next(iter(witness)))==placed:occurrences+=1
assert occurrences>0
align=frame.apply_all(parent)
assert not align&cut.apply_all(align) and child&cut.apply_all(child)
result=verify_witness((base.parent/"best.heesch").read_text())
assert result.result.hc_verified==3 and result.submission.proof.m==4
assert canonical_form(child,grid,True)==canonical_form(result.submission.cells,grid,True)
digest=result.result.canonical_digest
manifest=json.loads((base/"manifest.json").read_text())
assert manifest["digest"]==digest and manifest["level"]==4
compressed=(base.parent/"proof.drat.xz").read_bytes()
raw=lzma.decompress(compressed)
assert (len(compressed),len(raw),sha256(raw).hexdigest())==(manifest["stored_bytes"],manifest["payload_bytes"],manifest["payload_sha256"])
d=verify_defect(frozenset(result.submission.cells),grid,result.hc_corona,result.submission.defect,result.contact)
assert (d.defect_hc,d.defect_hh,d.required)==(13,13,145)
print(json.dumps(dict(digest=digest,source_four_rings=finite.result.hc_verified,source_five_rings=donor.result.hc_verified,
    finite_only_neighbors=len(newstar&(fstars-pstars)),periodic_only_neighbors=len(newstar&(pstars-fstars)),
    shared_neighbors=len(newstar&fstars&pstars),periodic_parent_motif=n,periodic_parent_contact_occurrences=occurrences,
    overlap_hexagons=sorted(child&cut.apply_all(child)),complete_tiles=len(result.submission.patches[0]),
    ring_sizes=dict(Counter(l for l,_ in result.submission.patches[0])),partial_tiles=d.partial_tiles,
    required=d.required,defects=d.defect_hc,additional_pockets=d.defect_hc-d.defect_hh,
    score=str(4-Fraction(d.defect_hc,d.required))),indent=2))
