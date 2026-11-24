"""Reconstruct the candidate and check the solid corona, gap count and proof digests."""
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
import lzma
from pathlib import Path
from heesch_verify import canonical_form, verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of
from outline_replay import GRID, families, reconstruct

HERE=Path(__file__).resolve().parent


def main():
    s=HERE.parent
    candidate=verify_witness((s/"best.heesch").read_text())
    g=candidate.submission.grid
    assert candidate.result.hc_verified==candidate.result.hh_verified==3
    parents,child=reconstruct(families(HERE/"parents.tsv"),(HERE/"origin.tsv").read_text().split())
    assert canonical_form(child,GRID,True)==canonical_form(candidate.submission.cells,GRID,True)
    region=candidate.hc_corona.patch_cells
    tile=frozenset(candidate.submission.cells)
    rim=required_set(region,candidate.contact)
    occupancy=Counter(q for lv,t in candidate.submission.defect.tiles for q in t.apply_all(tile))
    assert max(occupancy.values())==1 and set(occupancy).isdisjoint(region)
    gaps=rim-set(occupancy)
    holes=holes_of(region|set(occupancy),g)
    defect=verify_defect(tile,g,candidate.hc_corona,candidate.submission.defect,candidate.contact)
    assert (defect.defect_hc,defect.defect_hh,defect.required)==(len(gaps|holes),len(gaps),len(rim))==(6,6,166)
    rank=json.loads((HERE/"rank.json").read_text())
    assert all(Fraction(v["lower"],v["B"])>=Fraction(6,166) for v in rank.values())
    proof=candidate.submission.proof
    m=json.loads((HERE/"manifest.json").read_text())
    raw=lzma.decompress((s/proof.file_name).read_bytes())
    assert len(raw)==m["payload_bytes"] and sha256(raw).hexdigest()==m["proof_sha256"]
    assert m["canonical_digest"]==candidate.result.canonical_digest
    assert m["formula_depth"]==proof.m==4 and m["formula_sha256"] in (s/"best.heesch").read_text()
    for f,token in (("full-drat-check.log","s VERIFIED"),("full-lrat-check.log","c VERIFIED")):
        assert token in (HERE/f).read_text().splitlines()
    print(f"{len(tile)} hexagons, Hc=Hh=3, {len(rim)-len(gaps)}/{len(rim)} sites covered; proof SHA-256 {m['proof_sha256']}")


if __name__=="__main__":
    main()
