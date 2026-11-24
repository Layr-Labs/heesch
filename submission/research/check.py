"""Replay the donor tiling, its missing seam, and the submitted fourth-ring calculation."""
from collections import Counter
from fractions import Fraction
from pathlib import Path
from heesch_verify import GRIDS,Xform,canonical_form,verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.shape import holes_of
from heesch_verify.patch import required_set
from heesch_verify.transform import check_symmetry
import json

here=Path(__file__).resolve().parent
origin=json.loads((here/'origin.json').read_text());grid=GRIDS['H']
def shape(coords):return frozenset(map(tuple,coords))
def displacement(a,b):
    det=a.a*a.e-a.b*a.d;u=b.c-a.c;v=b.f-a.f
    return ((a.e*b.a-a.b*b.d)//det,(a.e*b.b-a.b*b.e)//det,(a.e*u-a.b*v)//det,(-a.d*b.a+a.a*b.d)//det,(-a.d*b.b+a.a*b.e)//det,(-a.d*u+a.a*v)//det)

def all_contact(tile,poses,period=None):
    def fold(c):
        if period is None:return c
        a,b,k=period;x,y=c;n,r=divmod(y,k);return (x-n*b)%a,r
    occupied={}
    for i,p in enumerate(poses):
        check_symmetry(p,grid,True)
        for x in p.apply_all(tile):
            key=fold(x);assert key not in occupied;occupied[key]=(i,x)
    if period:assert len(occupied)==period[0]*period[2]
    contacts=Counter()
    for a,p in enumerate(poses):
        edges=set()
        for h in p.apply_all(tile):
            for c in grid.edge_neighbors(h):
                info=occupied.get(fold(c))
                if info is None:continue
                b,r=info;q=poses[b];v=Xform(q.a,q.b,q.c+c[0]-r[0],q.d,q.e,q.f+c[1]-r[1]);
                if p!=v:edges.add((b,displacement(p,v)))
        contacts.update(t for _,t in edges)
    return contacts

a=shape(origin['donor']);b=shape(origin['child']);cut=tuple(origin['cut']);t=Xform(*cut)
reference=verify_witness((here/'donor-five.heesch').read_text());assert reference.result.hc_verified==5 and frozenset(reference.submission.cells)==a
n,p,q,r,*ops=origin['torus'];poses=[Xform(*o)for o in ops];assert p*r==n*len(a)==len(poses)*len(a)
period=all_contact(a,poses,(p,q,r));witness=all_contact(a,[xf for _,xf in reference.submission.patches[0]]);assert period[cut]==2 and witness[cut]==0
assert not a&t.apply_all(a) and sum(z in t.apply_all(a) for x in a for z in grid.edge_neighbors(x))==7
assert len(b&t.apply_all(b))==2 and len(a-b)==len(b-a)==5
center=b;body=set(b);required=required_set(b,reference.contact)
for op in origin['star']:
    part=Xform(*op).apply_all(b);assert not part&body and part&required;body.update(part)
assert required<=body and not holes_of(frozenset(body),grid)
submission=verify_witness((here.parent/'best.heesch').read_text());assert submission.result.hc_verified==3 and canonical_form(b,grid,True)==canonical_form(submission.submission.cells,grid,True)
s=submission.submission;d=verify_defect(frozenset(s.cells),grid,submission.hc_corona,s.defect,submission.contact);assert s.proof and s.proof.m==4
print(json.dumps(dict(canonical_digest=submission.result.canonical_digest,area=len(b),donor_period=n,donor_patch_count=len(reference.submission.patches[0]),period_contact_occurrences=period[cut],patch_contact_occurrences=witness[cut],overlapping_child_cells=sorted(b&t.apply_all(b)),complete_tiles=len(s.patches[0]),partial_tiles=d.partial_tiles,defect_hc=d.defect_hc,defect_hh=d.defect_hh,required=d.required,score=str(4-Fraction(d.defect_hc,d.required)),proof_m=s.proof.m),indent=2))
