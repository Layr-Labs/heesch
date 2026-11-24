"""Check both graph substitutions, all real placements, and the finite score."""
from collections import Counter
from fractions import Fraction
from hashlib import file_digest
from pathlib import Path
import json,lzma
from heesch_verify import GRIDS,canonical_form,verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of
from lineage import reconstruct,physical_graph

here=Path(__file__).resolve().parent
origin=json.loads((here/"origin.json").read_text())
manifest=json.loads((here/"proof-manifest.json").read_text())
donor=list(map(tuple,origin["donor_cells"]))
child=list(map(tuple,origin["embedding"]))
grid=GRIDS["H"]
count,needed,absent=reconstruct(donor,origin["operations"],"triangles")
actual=physical_graph(child)
assert count==len(child)==19 and needed<=actual and not absent&actual
assert len(needed)==origin["required_graph_edges"] and len(actual-needed)==origin["incidental_edges"]
ref=verify_witness((here/"periodic-control.heesch").read_text())
assert ref.result.hc_verified==5 and len(ref.submission.patches[0])==102
q=origin["periodic_control"];total,a,b,c=q["hnf"]
from heesch_verify import Xform
from heesch_verify.transform import check_symmetry
quotient=Counter()
for as_text in q["poses"]:
    t=Xform(*map(int,as_text.split(",")));check_symmetry(t,grid,True)
    for x,y in t.apply_all(ref.submission.cells):
        z,ry=divmod(y,c);quotient[(x-b*z)%a,ry]+=1
assert quotient==Counter((x,y)for x in range(a)for y in range(c)) and len(q["poses"])==total
w=verify_witness((here.parent/"best.heesch").read_text());tile=frozenset(w.submission.cells)
assert canonical_form(child,grid,True)==canonical_form(tile,grid,True)
assert w.result.canonical_digest==origin["canonical_digest"]==manifest["canonical_digest"]
assert w.result.hc_verified==3 and w.result.hh_verified==3
body=frozenset()
for level in range(4):
    new=set()
    for k,t in w.submission.patches[0]:
        if k!=level:continue
        cells=t.apply_all(tile)
        assert not cells&body and not cells&new
        if level:
            assert cells&required_set(body,w.contact)
        new.update(cells)
    if level:
        assert required_set(body,w.contact)<=new
    body=body|new
    assert not holes_of(body,grid)
rim=required_set(body,w.contact);outer=set()
for k,t in w.submission.defect.tiles:
    assert k==4
    covered=t.apply_all(tile)
    assert covered&rim and not covered&body and not covered&outer
    outer.update(covered)
miss=rim-outer;holes=holes_of(body|outer,grid);d=len(miss|holes);B=len(rim)
df=verify_defect(tile,grid,w.hc_corona,w.submission.defect,w.contact)
assert (df.defect_hc,df.defect_hh,df.required)==(d,len(miss),B)
proof=w.submission.proof
assert proof.m==4 and proof.compression=="xz" and proof.fmt=="drat"
assert proof.cnf_digest==manifest["cnf_sha256"] and (proof.num_vars,proof.num_clauses)==(manifest["vars"],manifest["clauses"])
blob=here.parent/proof.file_name
with lzma.open(blob,"rb")as f:
    assert file_digest(f,"sha256").hexdigest()==manifest["proof_sha256"]==proof.payload_sha256
assert blob.stat().st_size==manifest["stored_bytes"]
assert "s VERIFIED" in (here/"full-drat-check.log").read_text().splitlines()
assert "c VERIFIED" in (here/"full-lrat-check.log").read_text().splitlines()
print(json.dumps(dict(canonical_digest=w.result.canonical_digest,donor_order=len(donor),modules=2,
                      graph_bonds=len(needed),incidental_bonds=len(actual-needed),hc=3,hh=3,
                      complete=len(w.submission.patches[0]),partial=len(w.submission.defect.tiles),
                      gaps=len(miss),extra_pockets=len(holes-miss),defect=d,required=B,
                      score=str(4-Fraction(d,B)),proof_m=proof.m,
                      control_repeating_copies=total,control_domain=a*c),indent=2))
