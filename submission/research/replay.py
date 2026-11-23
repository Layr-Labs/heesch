"""Replay the scored 16-hex, both charts of its research companion, and a period."""
from pathlib import Path
from collections import Counter
from itertools import product
import json

from heesch_verify import verify_witness, canonical_form, Xform
from heesch_verify.defect import verify_defect
from heesch_verify.transform import check_symmetry

here=Path(__file__).resolve().parent
w=verify_witness((here.parent/"best.heesch").read_text())
grid=w.submission.grid
shape=frozenset(w.submission.cells)
check=verify_defect(shape,grid,w.hc_corona,w.submission.defect,w.contact)
assert (len(shape),w.result.hc_verified,w.result.hh_verified)==(16,4,4)
assert Counter(w.hc_corona.levels)=={0:1,1:5,2:11,3:21,4:28}
assert (check.required,check.partial_tiles,check.defect_hh,check.pocket_cells)==(221,35,22,2)
print("16-hex: 66 full copies, 199 of 221 exterior cells covered, 2 additional empty cells in pockets.")
record=json.loads((here/"majority-child.json").read_text())
def compose(a,b):
    m,n,p,q=a;x,y,u,v=b
    return m*x+n*u,m*y+n*v,p*x+q*u,p*y+q*v
registered=[]
for donor in record["donors"]:
    n=donor["orientation"]
    matrix=(1,0,0,1)
    for _ in range(n//2):matrix=compose((0,-1,1,1),matrix)
    if n%2:matrix=compose(matrix,(0,1,1,0))
    a,b,d,e=matrix;x,y=donor["translation"]
    xf=Xform(a,b,x,d,e,y);check_symmetry(xf,grid,True)
    registered.append(xf.apply_all(map(tuple,donor["cells"])))
seed=frozenset(map(tuple,record["parent_cells"]))
a,b=registered
child=(seed & (a|b)) | (a&b)
assert (len(child-seed),len(seed-child))==(record["added"],record["removed"])
for filename,hc,copies in [("majority-child.heesch",5,102),("majority-child-outer-holes.heesch",4,101)]:
    result=verify_witness((here/filename).read_text())
    assert (result.result.hc_verified,result.result.hh_verified,result.result.patch_size)==(hc,5,copies)
    assert canonical_form(result.submission.cells,grid,True)==canonical_form(child,grid,True)
words=(here/"majority-child-period.tsv").read_text().split()
used=frozenset(result.submission.cells)
n,a,b,c=map(int,words[2:6])
counts=Counter()
for value in words[6:]:
    pose=Xform(*map(int,value.split(",")));check_symmetry(pose,grid,True)
    for x,y in pose.apply_all(used):
        shift,r=divmod(y,c);counts[(x-b*shift)%a,r]+=1
assert n==len(words[6:])==16 and counts==Counter(product(range(a),range(c)))
print("19-hex: five complete rings in 102 copies; 16 copies cover 304 periodic residues exactly once.")
