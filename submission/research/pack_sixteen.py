"""Find and verify a partial fifth ring, including the pocket charges."""
import json
from pathlib import Path
import sys
import time

from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of

here = Path(__file__).resolve().parent
from pocket_solver import Packing
from coverage_solver import coverage

text = (here / "four.heesch").read_text()
checked = verify_witness(text)
shape = frozenset(checked.submission.cells)
grid = checked.submission.grid
inner = checked.hc_corona.patch_cells
required = required_set(inner, checked.contact)

def record(chosen, phase):
    covered = frozenset().union(*(p.cells for p in chosen))
    gaps = required - covered
    pockets = holes_of(inner | covered, grid) - gaps
    defect = len(gaps) + len(pockets)
    block = f"#DEFECT 5 {defect} {len(gaps)} {len(required)}\n{len(chosen)}\n"
    witness = text + block + "".join(f"5 {p.xf.as_text()}\n" for p in chosen)
    replay = verify_witness(witness)
    d = verify_defect(shape, grid, replay.hc_corona, replay.submission.defect, replay.contact)
    assert (d.defect_hc, d.defect_hh, d.pocket_cells) == (defect, len(gaps), len(pockets))
    (here / "packed.heesch").write_text(witness)
    print(json.dumps(dict(phase=phase, required=len(required), gaps=len(gaps),
                          extra_pockets=len(pockets), copies=len(chosen), defect=defect)), flush=True)
    return defect

chosen, status = coverage(checked, 60)
assert chosen, status
best = record(chosen, status)
while best > 1:
    search = Packing(grid, shape, inner, checked.contact, best - 1)
    search.model.clear_objective()
    search.add_hint({p.cells for p in chosen})
    proposed, stats = search.solve(time.monotonic() + 40, 2, 1219)
    if proposed is None:
        print(json.dumps(stats), flush=True)
        break
    chosen = proposed
    best = record(chosen, "pocket-aware")
