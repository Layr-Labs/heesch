"""Independently reconstruct the scored tile starting from each registered parent."""
from collections import Counter
import json
from pathlib import Path

from heesch_verify import GRIDS, canonical_form, verify_witness
from heesch_verify.canonical import canonical_digest
from heesch_verify.defect import verify_defect


HERE=Path(__file__).resolve().parent
GRID=GRIDS["H"]


def check_halves(shape):
    row=json.loads((HERE/"half-turn-origin.json").read_text())
    domain=set(map(tuple,row["macro"]))
    (a,_),(b,c)=row["periods"]
    assert len(domain)==37 and {(-x,-y) for x,y in domain}==domain
    assert a*c==len({((x-b*(y//c))%a,y%c) for x,y in domain})
    pairs=sorted(p for p in domain if p<(-p[0],-p[1]))
    code=row["pair_mask"]
    chosen={(-x,-y) if code>>i&1 else (x,y) for i,(x,y) in enumerate(pairs)}|{(0,0)}
    other={(-x,-y) for x,y in chosen}
    assert chosen|other==domain and chosen&other=={(0,0)}
    assert canonical_form(chosen,GRID,True)==canonical_form(shape,GRID,True)
    father=set(map(tuple,row["donor"]))
    assert len(father)==16 and canonical_digest(father,GRID,True)==row["parent_digest"]
    added=set(map(tuple,row["added"]))
    prior=domain-added
    assert len(prior)==31
    # The donor can be placed, up to a lattice isometry, in the prior domain.
    for scale in GRID.orientations:
        coords={scale.apply(p) for p in father}
        for ax,ay in coords:
            placed={(x-ax,y-ay) for x,y in coords}
            if placed|{(-x,-y) for x,y in placed}==prior:
                return
    raise ValueError("Donor and half-turn region disagree")


def check_distances(shape):
    row=json.loads((HERE/"pair-distance-origin.json").read_text())
    a,b,c=row["hnf"]
    assert (a,b,c)==(36,12,1)
    def project(p):
        x,y=p
        return (x-b*y)%a
    donor={project(p) for p in row["donor_cells"]}
    vacant=set(range(36))-donor
    transformed=set(vacant)
    assert len(donor)==17 and len(vacant)==19
    for p,q in row["switched_orbits"]:
        assert (p-q)%36==18 and len({p,q}&transformed)==1
        transformed.symmetric_difference_update({p,q})
    lift=set(map(tuple,row["physical_lift"]))
    assert len(lift)==19 and {project(p) for p in lift}==transformed
    assert canonical_form(lift,GRID,True)==canonical_form(shape,GRID,True)
    differences=lambda coords:Counter((x-y)%36 for x in coords for y in coords)
    assert differences(transformed)==differences(vacant)
    assert [differences(transformed)[i] for i in range(36)]==row["covariogram"]


def main():
    best=verify_witness((HERE.parent/"best.heesch").read_text())
    s=best.submission
    shape=frozenset(s.cells)
    check_halves(shape)
    check_distances(shape)
    for source in ("original-third.heesch","second-construction.heesch"):
        earlier=verify_witness((HERE/source).read_text())
        assert earlier.result.canonical_digest==best.result.canonical_digest
        assert earlier.result.hc_verified==3 and len(earlier.submission.patches[0])==36
    assert best.result.hc_verified==3 and len(shape)==19
    d=verify_defect(shape,s.grid,best.hc_corona,s.defect,best.contact)
    print(json.dumps(dict(digest=best.result.canonical_digest,solid=3,charged=d.defect_hc,
                          required=d.required,missed=d.defect_hh,pockets=d.pocket_cells,
                          score=4-d.defect_hc/d.required)))


if __name__=="__main__":
    main()
