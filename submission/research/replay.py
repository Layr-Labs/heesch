"""Check both square patches, their charged fourth layers, and the local plane obstruction."""
from collections import Counter
from pathlib import Path
from fractions import Fraction
from hashlib import sha256
import json
from heesch_verify import verify_witness,canonical_digest
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of,spans
from atlas import solve

D=Path(__file__).resolve().parent

def inspect(path):
    parsed=verify_witness(path.read_text())
    s=parsed.submission
    shape=frozenset(s.cells)
    full=parsed.hc_corona.patch_cells
    required=required_set(full,parsed.contact)
    occ=frozenset().union(*(t.apply_all(shape)for _,t in s.defect.tiles))
    gaps=required-occ
    extras=holes_of(full|occ,s.grid)-gaps
    d=verify_defect(shape,s.grid,parsed.hc_corona,s.defect,parsed.contact)
    assert len(gaps)==d.defect_hh and len(extras)==d.pocket_cells and d.defect_hc==len(gaps)+len(extras)
    rings=Counter(l for l,t in s.patches[0])
    assert sum(rings.values())==len(s.patches[0]) and parsed.result.hc_verified==3
    return shape,dict(canonical=canonical_digest(shape,s.grid,True),area=len(shape),span=spans(shape,s.grid),
               rings=dict(sorted(rings.items())),required=len(required),covered=len(required)-len(gaps),
               missing=sorted(gaps),extra_pocket_cells=sorted(extras),charged=d.defect_hc,
               partial_tiles=d.partial_tiles,score_with_accepted_nontiler_gate=float(4-Fraction(d.defect_hc,d.required)))

if __name__=="__main__":
    old,initial=inspect(D/"previous-38.heesch")
    new,current=inspect(D/"partial-38.heesch")
    assert new==old and current["canonical"]=="ce7621c826fa7af1112fc98e05e11041bd5ed81dce10106f5b808d821c4ebe84"
    assert initial["charged"]==29 and initial["required"]==293
    assert current["charged"]==5 and current["required"]==304
    atlas=solve(new)
    assert atlas==json.loads((D/"atlas-result.json").read_text())["result"] and atlas["layers"][-1]==0
    final=dict(earlier=initial,submitted=current,edge_star_consistency=atlas)
    print(json.dumps(final,indent=1))
