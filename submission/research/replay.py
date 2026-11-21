"""Reconstruct both first footprints, every four-ring result and the proof digest."""
from collections import Counter
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.proofgate import materialize_proof
from heesch_verify.shape import holes_of

HERE=Path(__file__).resolve().parent


def footprint(shape, tiles, level):
    return frozenset().union(*(t.apply_all(shape) for l,t in tiles if l<=level))


def main():
    primary=verify_witness((HERE.parent/"best.heesch").read_text())
    original=verify_witness((HERE/"original.heesch").read_text())
    reference_shape=frozenset(original.submission.cells)
    records=[]
    known=set()
    src=footprint(reference_shape,original.submission.patches[0],1)
    assert len(src)==90
    for path in sorted((HERE/"first-rings").glob("[1-5].heesch")):
        v=verify_witness(path.read_text())
        shape=frozenset(v.submission.cells)
        assert shape==reference_shape and v.result.hc_verified==4
        tiles=v.submission.patches[0]
        first=footprint(shape,tiles,1)
        assert len(first)==105 and len(first^src) in {35,49,59,57,61} and first not in known
        known.add(first)
        for depth in range(5):
            assert not holes_of(footprint(shape,tiles,depth),v.submission.grid)
        counts=Counter(l for l,t in tiles)
        records.append(dict(file=path.name,tiles=[counts[i] for i in range(5)],
                            old_only=len(src-first),new_only=len(first-src),difference=len(src^first),
                            fourth_boundary=len(required_set(v.hc_corona.patch_cells,v.contact))))
    assert len(known)==5
    tiles=primary.submission.patches[0]
    assert footprint(reference_shape,tiles,1) in known
    selected=verify_witness((HERE/"first-rings/3.heesch").read_text())
    assert primary.hc_corona.patch_cells==selected.hc_corona.patch_cells
    d=verify_defect(reference_shape,primary.submission.grid,primary.hc_corona,
                    primary.submission.defect,primary.contact)
    partial=frozenset().union(*(t.apply_all(reference_shape) for l,t in primary.submission.defect.tiles))
    req=required_set(primary.hc_corona.patch_cells,primary.contact)
    gaps=req-partial
    extra=holes_of(primary.hc_corona.patch_cells|partial,primary.submission.grid)-gaps
    assert (d.required,d.defect_hh,d.defect_hc,d.partial_tiles)==(237,24,25,44)
    assert (len(req&partial),len(gaps),len(extra))==(213,24,1)
    original_block=original.submission.proof
    block=primary.submission.proof
    assert block==original_block
    with TemporaryDirectory() as tmp:
        size,digest=materialize_proof(HERE.parent/block.file_name,Path(tmp)/"proof.drat",block.compression)
        assert digest==block.payload_sha256
    result=dict(first_footprints=records,primary=dict(ring_counts=[sum(l==i for l,t in tiles)
                for i in range(5)],partial=44,required=len(req),covered=len(req&partial),
                gaps=len(gaps),extra_pockets=len(extra),pocket_sites=sorted(extra),
                score=str(4+Fraction(len(req)-d.defect_hc,len(req)))),
                proof=dict(m=block.m,materialized_bytes=size,payload_sha256=digest))
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
