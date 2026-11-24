"""Replay the solid and porous patches, partial covers and half-turn domains from physical coordinates."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.shape import holes_of

here=Path(__file__).resolve().parent


def read(p):
    w=verify_witness(p.read_text())
    s=w.submission
    shape=frozenset(s.cells)
    geometry=[]
    for patch in s.patches:
        occupied=frozenset().union(*(t.apply_all(shape) for _,t in patch))
        geometry.append([len(patch),len(holes_of(occupied,s.grid))])
    partial=None if not s.defect else verify_defect(shape,s.grid,w.hc_corona,s.defect,w.contact)
    return w,geometry,partial


def main():
    w,g,d=read(here.parent/"best.heesch")
    assert (w.result.hc_verified,w.result.hh_verified,g)==(3,4,[[30,0],[58,24]])
    assert (d.required,d.defect_hh,d.defect_hc,d.pocket_cells,d.partial_tiles)==(149,4,4,0,27)
    previous,pg,pd=read(here/"previous-third.heesch")
    minimum,mg,_=read(here/"minimum-pocket.heesch")
    identity=w.result.canonical_digest
    assert identity==previous.result.canonical_digest==minimum.result.canonical_digest
    assert pg==[[29,0],[56,20]] and mg==[[29,0],[54,14]]
    assert (pd.required,pd.defect_hh,pd.defect_hc,pd.pocket_cells)==(126,5,5,0)
    counts={k:int(v) for k,v in (line.split() for line in (here/"complete-fourth-counts.tsv").read_text().splitlines())}
    assert sum(v for k,v in counts.items() if k.isdigit())==counts["raw_placements"]==226755
    assert min(int(k) for k in counts if k.isdigit())==14 and counts["remaining"]==0
    for row in json.loads((here/"shared-center.json").read_text()):
        (a,_),(b,c)=row["periods"]
        first=set(map(tuple,row["first"]))
        assert row["digest"]==identity
        from heesch_verify.canonical import canonical_digest
        assert canonical_digest(first,w.submission.grid,True)==identity
        other={(-x,-y) for x,y in first}
        assert other==set(map(tuple,row["second"])) and first&other=={(0,0)}
        occ=Counter(((x-b*(y//c))%a,y%c) for x,y in first|other)
        assert a*c==len(occ)==39 and all(v==1 for v in occ.values())
    if w.submission.proof is not None:
        from heesch_verify.proofgate import materialize_proof
        from heesch_verify.profile import RECORD
        from tempfile import TemporaryDirectory
        block=w.submission.proof
        manifest=json.loads((here/"proof-manifest.json").read_text())
        assert block.m==5 and block.cnf_digest==manifest["formula_sha256"]
        with TemporaryDirectory() as tmp:
            raw,digest=materialize_proof(here.parent/block.file_name,Path(tmp)/"proof","xz",
                                      RECORD.proof_max_stored_bytes,RECORD.proof_max_payload_bytes)
        assert digest==block.payload_sha256 and raw==manifest["payload_bytes"]
        assert "s VERIFIED" in (here/"full-drat-check.log").read_text()
        assert "c VERIFIED" in (here/"full-lrat-check.log").read_text()
    print(json.dumps(dict(shape=identity,solid=3,porous=4,covered=145,required=149,score=3+145/149)))


if __name__=="__main__":
    main()
