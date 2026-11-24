"""Replay the neighbor inventory, both physical patches, period, defect and proof identity."""
from collections import Counter
from fractions import Fraction
from hashlib import file_digest
import json
import lzma
from pathlib import Path
from heesch_verify import GRIDS, Xform, canonical_form, verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of
from heesch_verify.transform import check_symmetry

HERE=Path(__file__).resolve().parent
GRID=GRIDS["H"]
DIRECTIONS=((1,0),(0,1),(-1,1),(-1,0),(0,-1),(1,-1))


def inventory(cells):
    sites=set(cells)
    patterns=[]
    for x,y in sites:
        bits=[i for i,(a,b) in enumerate(DIRECTIONS) if (x+a,y+b) in sites]
        patterns.append(min(sum(1<<((r+sign*i)%6) for i in bits) for sign in (-1,1) for r in range(6)))
    return sorted(patterns)


def check():
    provenance=json.loads((HERE/"origin.json").read_text())
    manifest=json.loads((HERE/"proof-manifest.json").read_text())
    donor=verify_witness((HERE/"periodic-donor.heesch").read_text())
    child=verify_witness((HERE.parent/"best.heesch").read_text())
    c=frozenset(child.submission.cells)
    d=frozenset(donor.submission.cells)
    assert len(c)==len(d)==18
    assert canonical_form(d,GRID,True)!=canonical_form(c,GRID,True)
    assert canonical_form(c,GRID,True)==canonical_form(tuple(map(tuple,provenance["child"])),GRID,True)
    assert inventory(c)==inventory(d)==provenance["inventory"]
    assert donor.result.canonical_digest==provenance["donor_digest"]
    assert child.result.canonical_digest==manifest["canonical_digest"]
    assert donor.result.hc_verified==5 and len(donor.submission.patches[0])==91
    n,a,b,h=provenance["period"]
    cover=Counter()
    for data in provenance["period_poses"]:
        motion=Xform(*data)
        check_symmetry(motion,GRID,True)
        for x,y in motion.apply_all(d):
            q,r=divmod(y,h)
            cover[(x-q*b)%a,r]+=1
    assert len(provenance["period_poses"])==n and cover==Counter((x,y) for x in range(a) for y in range(h))
    assert (child.result.hc_verified,child.result.hh_verified)==(3,3)
    core=set()
    for level in range(4):
        ring=set()
        incoming=required_set(core,child.contact) if level else set()
        for k,t in child.submission.patches[0]:
            if k!=level:continue
            cells=t.apply_all(c)
            assert not core&cells and not ring&cells
            assert not level or cells&incoming
            ring.update(cells)
        assert incoming<=ring
        core.update(ring)
        assert not holes_of(frozenset(core),GRID)
    rim=required_set(frozenset(core),child.contact)
    partial=set()
    for k,t in child.submission.defect.tiles:
        cells=t.apply_all(c)
        assert k==4 and cells&rim and not core&cells and not partial&cells
        partial.update(cells)
    gaps=rim-partial
    pockets=holes_of(frozenset(core|partial),GRID)-gaps
    score=4-Fraction(len(gaps)+len(pockets),len(rim))
    official=verify_defect(c,GRID,child.hc_corona,child.submission.defect,child.contact)
    assert (official.defect_hc,official.defect_hh,official.required)==(len(gaps)+len(pockets),len(gaps),len(rim))
    proof=child.submission.proof
    assert (proof.m,proof.num_vars,proof.num_clauses,proof.fmt,proof.compression)==(
        4,manifest["vars"],manifest["clauses"],"drat","xz")
    assert proof.cnf_digest==manifest["cnf_sha256"]
    artifact=HERE.parent/proof.file_name
    assert artifact.stat().st_size==manifest["stored_bytes"]
    with lzma.open(artifact,"rb") as payload:
        assert file_digest(payload,"sha256").hexdigest()==proof.payload_sha256==manifest["proof_sha256"]
    assert "s VERIFIED" in (HERE/"full-drat-check.log").read_text().splitlines()
    assert "c VERIFIED" in (HERE/"full-lrat-check.log").read_text().splitlines()
    return dict(donor_digest=donor.result.canonical_digest,child_digest=child.result.canonical_digest,
                inventory=Counter(inventory(c)),donor_fifth_copies=91,period_cells=a*h,period_copies=n,
                rings=[sum(k==level for k,_ in child.submission.patches[0]) for level in range(4)],
                fourth_copies=len(child.submission.defect.tiles),required=len(rim),gap_cells=sorted(gaps),
                additional_pockets=sorted(pockets),score=str(score),upper_depth=4)

if __name__=="__main__":
    print(json.dumps(check(),indent=2))
