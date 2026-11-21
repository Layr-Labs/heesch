"""Replay the submitted triangular geometry and independent census evidence."""
from collections import Counter
from fractions import Fraction
import json
from pathlib import Path
import sys

from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.gates import IsohedralGate
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of


def replay(path):
    w=verify_witness(path.read_text()); s=w.submission
    shape=frozenset(s.cells); grid=s.grid
    assert grid.grid_id=='I' and len(shape)==10
    primary,secondary=s.patches
    assert Counter(l for l,_ in primary)==dict(enumerate([1,6,11,18]))
    assert Counter(l for l,_ in secondary)==dict(enumerate([1,6,11,18,28]))
    assert [(l,t) for l,t in secondary if l<=3]==list(primary)
    core=w.hc_corona.patch_cells
    required=required_set(core,w.contact)
    outer=frozenset().union(*(t.apply_all(shape) for _,t in s.defect.tiles))
    full=frozenset().union(*(t.apply_all(shape) for _,t in secondary))
    gaps=required-outer
    pocket=holes_of(core|outer,grid)-gaps
    hh_pockets=holes_of(full,grid)
    measured=verify_defect(shape,grid,w.hc_corona,s.defect,w.contact)
    gate=IsohedralGate(grid).evaluate(shape)
    assert (gate.census_hc,gate.census_hh)==(3,4)
    assert (len(required), measured.partial_tiles, measured.defect_hc, measured.defect_hh)==(139,27,2,1)
    assert gaps=={(-29,19)} and pocket=={(4,19)}
    assert hh_pockets=={(-33,15),(-32,13),(-21,-6),(4,19)}
    score=3+Fraction(len(required)-measured.defect_hc,len(required))
    return {'score_fraction':str(score),'score_before_rounding':float(score),'census':[3,4],
            'full_ring_pockets':sorted(hh_pockets),'partial_required':len(required),
            'partial_gaps':sorted(gaps),'partial_extra_pocket':sorted(pocket)}


if __name__=='__main__':
    path=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'best.heesch'
    print(json.dumps(replay(path),sort_keys=True))
