"""Replay Holindauer’s archived full-coverage objective on the submitted geometry."""
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from ortools.sat.python import cp_model
from heesch_verify import verify_witness
from heesch_verify.patch import required_set
from heesch_verify.transform import Xform
from heesch_verify.shape import holes_of

@dataclass
class Placement:
    cells: frozenset
    xf: Xform

def enumerate_tiles(shape, grid, patch, required):
    placements = {}
    for sym in grid.orientations:
        oriented = frozenset(sym.apply(cell) for cell in shape)
        translations = {(rx - x, ry - y) for rx, ry in required for x, y in oriented}
        for dx, dy in sorted(translations):
            cells = frozenset((x + dx, y + dy) for x, y in oriented)
            if not cells & patch:
                placements.setdefault(cells, Xform(sym.a, sym.b, dx + sym.c0,
                                                   sym.d, sym.e, dy + sym.f0))
    return [Placement(c, xf) for c, xf in placements.items()]

def coverage(w, seconds):
    s = w.submission
    shape = frozenset(s.cells)
    core = w.hc_corona.patch_cells
    boundary = required_set(core, w.contact)
    items = enumerate_tiles(shape, s.grid, core, boundary)
    objective = []
    model = cp_model.CpModel()
    variables = [model.new_bool_var(str(i)) for i in range(len(items))]
    covers = defaultdict(list)
    for tile, v in zip(items, variables):
        for point in tile.cells:
            covers[point].append(v)
        objective.append((1000 * len(tile.cells & boundary) - 1) * v)
    for choices in covers.values():
        model.add_at_most_one(choices)
    model.maximize(sum(objective))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = 1
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return [], solver.status_name(status)
    return [p for p,v in zip(items, variables) if solver.value(v)], solver.status_name(status)

if __name__ == "__main__":
    source = Path(__file__).resolve().parent / "four.heesch"
    w = verify_witness(source.read_text())
    core = w.hc_corona.patch_cells
    sites = required_set(core,w.contact)
    choices = enumerate_tiles(frozenset(w.submission.cells),w.submission.grid,core,sites)
    chosen,status = coverage(w,30)
    cells = frozenset().union(*(p.cells for p in chosen))
    gaps = sites-cells
    holes = holes_of(core|cells,w.submission.grid)
    assert status == "OPTIMAL" and len(choices)==1865 and len(sites)==175 and len(gaps)==21 and len(chosen)==30
    print("Coverage",status,"placements",len(choices),"uncovered",len(gaps),"copies",len(chosen),"extra enclosed cells of returned optimum",len(holes-gaps))
