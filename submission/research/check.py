"""Rebuild the scored cavity, catalogue identification, three rings and proof payload."""
from collections import Counter
from fractions import Fraction
from hashlib import sha256, file_digest
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import json
import lzma

from heesch_verify import canonical_digest, canonical_form, verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of
from atlas import solve


def run():
    d=Path(__file__).resolve().parent
    bank=d/"cavity-bank"
    spec=spec_from_file_location("cavities",bank/"replay.py")
    replay=module_from_spec(spec)
    spec.loader.exec_module(replay)
    chart, old, edited, pieces, cavity=replay.reconstruct("1134")
    assert chart["attempt"]==17 and chart["center_index"]==0
    assert len(old)==20 and set(old)-edited=={(1,4),(0,6)} and len(edited)==18
    assert len(cavity)==22 and len(pieces)==5
    for source in replay.charts:
        blob=(bank/"parents"/f"attempt-{source['attempt']:03d}.heesch").read_bytes()
        assert sha256(blob).hexdigest()==source["source_sha256"]
    w=verify_witness((d.parent/"best.heesch").read_text())
    s=w.submission
    shape=frozenset(s.cells)
    g=s.grid
    ident=canonical_form(shape,g,True)
    assert ident==canonical_form(cavity,g,True)
    book=(d/"22iamond_2up.txt").read_text().splitlines()
    def match(record):
        coords=iter(map(int,book[2*(record-1)].split()))
        return canonical_form(frozenset(zip(coords,coords)),g,True)==ident
    assert match(6) and not match(3) and book[11].strip()=="Hc = 3 Hh = 3"
    assert w.result.hc_verified==w.result.hh_verified==3
    at=solve(shape)
    assert at==json.loads((d/"atlas-checked.json").read_text()) and at["layers"][-1]==0
    req=required_set(w.hc_corona.patch_cells,w.contact)
    placed=frozenset().union(*(t.apply_all(shape) for _,t in s.defect.tiles))
    missed=req-placed
    extra=holes_of(w.hc_corona.patch_cells|placed,g)-missed
    defect=verify_defect(shape,g,w.hc_corona,s.defect,w.contact)
    assert defect.defect_hc==len(missed)+len(extra) and defect.defect_hh==len(missed)
    proof=json.loads((d/"proof-check.json").read_text())
    assert s.proof.cnf_digest==proof["cnf_digest"] and s.proof.payload_sha256==proof["raw_proof_sha256"]
    with lzma.open(d.parent/s.proof.file_name,"rb")as stream:
        assert file_digest(stream,"sha256").hexdigest()==s.proof.payload_sha256
    print(json.dumps(dict(shape_sha256=canonical_digest(shape,g,True),catalogue_record=6,
                          complete_rings=dict(sorted(Counter(w.hc_corona.levels).items())),
                          partial_tiles=defect.partial_tiles,required=len(req),covered=len(req)-len(missed),
                          missing=len(missed),additional_pocket_cells=len(extra),charged_defect=defect.defect_hc,
                          score=str(4-Fraction(defect.defect_hc,defect.required)),
                          proof=proof),indent=1))


if __name__=="__main__":
    run()
