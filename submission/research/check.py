"""Replay each recorded gain and the inherited proof digest with the official geometry."""
from fractions import Fraction
from hashlib import file_digest
import json
import lzma
from math import atan2, radians, remainder, pi, sqrt
from pathlib import Path
from heesch_verify import canonical_form, verify_witness
from heesch_verify.defect import verify_defect

here=Path(__file__).resolve().parent


def read(path):
    w=verify_witness(path.read_text())
    shape=frozenset(w.submission.cells)
    d=verify_defect(shape,w.submission.grid,w.hc_corona,w.submission.defect,w.contact)
    assert w.result.hc_verified == w.result.hh_verified == 4
    layers=[{t.apply_all(shape) for lv,t in w.submission.patches[0] if lv==i} for i in range(5)]
    layers.append({t.apply_all(shape) for lv,t in w.submission.defect.tiles})
    return w,layers,Fraction(5*d.required-d.defect_hc,d.required),d


def main():
    start=here/"baseline.heesch"
    parent,layers,best,_=read(start)
    previous=start
    core=frozenset().union(*(p for level in layers[:4] for p in level))
    cx=sum(x for x,y in core)/len(core)
    cy=sum(y for x,y in core)/len(core)
    gains=0
    for entry in json.loads((here/"history.json").read_text()):
        assert entry["seed"]==previous.name and Fraction(entry["seed_score"])==best
        if "witness" not in entry:
            continue
        improved=here/"witnesses"/entry["witness"]
        child,after,score,defect=read(improved)
        assert layers[:4]==after[:4] and score>best and score==Fraction(entry["improved"])
        assert child.submission.proof==parent.submission.proof
        for level in (4,5):
            for cells in layers[level]^after[level]:
                x=sum(p[0] for p in cells)/len(cells)-cx
                y=sum(p[1] for p in cells)/len(cells)-cy
                angle=atan2(sqrt(3)*y/2,x+y/2)-radians(entry["degrees"])
                assert abs(remainder(angle,2*pi)) <= radians(entry["half_width"])+1e-12
        assert (entry["charged"],entry["missing"],entry["boundary"])==(defect.defect_hc,defect.defect_hh,defect.required)
        gains+=1
        previous,layers,best=improved,after,score
    result=here.parent/"best.heesch"
    assert previous.read_bytes()==result.read_bytes()
    final,_,score,d=read(result)
    p=final.submission.proof
    with lzma.open(here.parent/p.file_name,"rb") as stream:
        assert file_digest(stream,"sha256").hexdigest()==p.payload_sha256
    bounds=here/"global-bounds"
    def footprint(path):
        w=verify_witness(path.read_text())
        assert w.result.canonical_digest==final.result.canonical_digest
        pts=frozenset().union(*(t.apply_all(w.submission.cells) for lv,t in w.submission.patches[0] if lv<=3))
        return canonical_form(pts,w.submission.grid,True)
    assert footprint(start)==footprint(bounds/"original.heesch")==footprint(bounds/"known-1.heesch")
    assert footprint(start)!=footprint(bounds/"known-2.heesch")
    assert "EXHAUSTED 0 3" in (bounds/"run.log").read_text().splitlines()[-1]
    for n in (1,2):
        b=json.loads((bounds/f"branch-{n}.json").read_text())
        group=b["partitions"][-1]
        assert len({a["sector"] for a in group["sectors"]})==len(group["sectors"])
        assert all(a["status"]=="OPTIMAL" for a in group["sectors"])
        assert group["minimum_missing"]==sum(a["lower"] for a in group["sectors"])
        assert 254*group["minimum_missing"]>=3*b["upper_boundary"]
    print(json.dumps(dict(area=len(final.submission.cells),rings=[len(l) for l in layers[:5]],
                          gains=gains,outer=len(layers[5]),missed=d.defect_hh,extra_pocket=d.pocket_cells,
                          boundary=d.required,score=str(score),proof=p.payload_sha256)))


if __name__=="__main__":
    main()
