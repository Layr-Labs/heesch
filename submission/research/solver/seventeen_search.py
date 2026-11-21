"""Measure and improve partial outer rings on freshly generated four-ring footprints."""
import argparse
from hashlib import sha256
from fractions import Fraction
from pathlib import Path
import json
from shutil import copy2
import sys
import time
from collections import defaultdict
from ortools.sat.python import cp_model

HERE=Path(__file__).resolve().parent

from pack import Packing, Placement, enumerate_tiles, encode_full
from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of


def search(base):
    shape=frozenset(base.submission.cells); grid=base.submission.grid
    patch=base.hc_corona.patch_cells; required=required_set(patch,base.contact)
    items=enumerate_tiles(shape,grid,patch,required); model=cp_model.CpModel()
    take=[model.new_bool_var(f"t{i}") for i in range(len(items))]
    at=defaultdict(list)
    for i,t in enumerate(items):
        for c in t.cells:at[c].append(take[i])
    for a in at.values():model.add_at_most_one(a)
    model.maximize(sum((len(required&t.cells)*2000-1)*v for t,v in zip(items,take)))
    solver=cp_model.CpSolver();solver.parameters.num_search_workers=1;solver.parameters.max_time_in_seconds=1.5
    status=solver.solve(model)
    if status not in (cp_model.OPTIMAL,cp_model.FEASIBLE):return None
    partial=[t for t,v in zip(items,take) if solver.value(v)]
    covered=frozenset().union(*(t.cells for t in partial)); uncovered=required-covered
    defect=uncovered|holes_of(covered|patch,grid)
    return len(uncovered),len(defect),len(required),partial,solver.status_name(status)


def serialize(base,partial):
    shape=frozenset(base.submission.cells); grid=base.submission.grid
    patch=base.hc_corona.patch_cells; r=required_set(patch,base.contact)
    covered=frozenset().union(*(t.cells for t in partial)); gaps=r-covered
    holes=holes_of(patch|covered,grid); cost=len(gaps|holes)
    source=(HERE.parent.parent/'best.heesch').read_text()
    text=encode_full(source.splitlines()[0],base.submission.patches[0])
    text+=f"#DEFECT 5 {cost} {len(gaps)} {len(r)}\n{len(partial)}\n"
    text+=''.join(f"5 {t.xf.as_text()}\n" for t in partial)
    if "#PROOF" in source: text+="#PROOF"+source.split("#PROOF",1)[1]
    checked=verify_witness(text); d=verify_defect(shape,grid,checked.hc_corona,checked.submission.defect,checked.contact)
    assert d.defect_hc==cost and d.required==len(r)
    return text,cost,len(r)


