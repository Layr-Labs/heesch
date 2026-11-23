"""Reconstruct the offspring from both parent geometries and verify the scored patch."""
import json
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

from heesch_verify import GRIDS, verify_witness
from heesch_verify.canonical import canonical_form, canonical_digest
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of

B = Path(__file__).resolve().parent
G = GRIDS["H"]

def connected_components(cells):
    remaining = set(cells)
    while remaining:
        seed = remaining.pop()
        component = {seed}
        pending = [seed]
        while pending:
            for q in G.edge_neighbors(pending.pop()):
                if q in remaining:
                    remaining.remove(q)
                    pending.append(q)
                    component.add(q)
        yield component

def run(witness):
    data = json.loads((B/"construction.json").read_text())
    cells = lambda r: {tuple(p) for p in data[r]["cells"]}
    parent, donor = cells("recipient"), cells("donor")
    edits = []
    for o,dx,dy,raw,ncommon,ncollar in data["exchange"]["exchanges"]:
        changed = {tuple(p) for p in raw}
        sym = next(t for t in G.orientations if t.index == o)
        placed = {(x+dx,y+dy) for x,y in (sym.apply(p) for p in donor)}
        collar = {q for p in changed for q in G.edge_neighbors(p)} - changed
        assert changed in list(connected_components(parent ^ placed))
        assert parent & collar == placed & collar
        assert len(collar & parent) == ncollar and len(parent & placed) == ncommon
        edits.append(changed)
    assert edits[0].isdisjoint(edits[1])
    assert all(q not in edits[1] for p in edits[0] for q in G.edge_neighbors(p))
    child = parent ^ edits[0] ^ edits[1]
    expected = data["offspring"]["digest"]
    assert canonical_digest(child,G,True) == expected
    assert canonical_form(data["offspring"]["shape"],G,True) == canonical_form(child,G,True)
    verify = verify_witness(witness.read_text())
    s = verify.submission
    assert canonical_digest(s.cells,G,True) == expected
    assert verify.result.hc_verified == verify.result.hh_verified == 4
    full = verify.hc_corona.patch_cells
    required = required_set(full,verify.contact)
    partial = set().union(*(t.apply_all(s.cells) for lv,t in s.defect.tiles))
    gaps = required - partial
    extra = holes_of(full | partial,G) - gaps
    measured = verify_defect(frozenset(s.cells),G,verify.hc_corona,s.defect,verify.contact)
    assert measured.defect_hc == len(gaps) + len(extra)
    assert measured.defect_hh == len(gaps)
    score = 5 - Fraction(measured.defect_hc,len(required))
    print("shape", expected, "rings", sorted(Counter(i for i,t in s.patches[0]).items()))
    print("partial copies",len(s.defect.tiles),"required",len(required),"gaps",len(gaps),
          "extra enclosed",len(extra),"conditional score",score,float(score))

if __name__ == "__main__":
    run(Path(sys.argv[1]) if len(sys.argv)>1 else B.parent/"best.heesch")
