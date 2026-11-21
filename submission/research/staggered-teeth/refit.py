"""Fit new tile outlines on the observed staggered-tooth placement charts."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys

from ortools.sat.python import cp_model
from heesch_verify import GRIDS, verify_witness
from heesch_verify.canonical import canonical_form
from heesch_verify.result import VerifyError
from heesch_verify.shape import connected, holes_of

HERE = Path(__file__).resolve().parent
G = GRIDS["H"]


def derivatives(row, depth, limit):
    seed_file = next(HERE.glob(f"five*/{row['id']}.d5.heesch"))
    template = verify_witness(seed_file.read_text()).submission
    base = frozenset(template.cells)
    sites = sorted(base | {n for p in base for n in G.edge_neighbors(p)})
    model = cp_model.CpModel()
    shape = [model.new_bool_var(f"s.{x}.{y}") for x,y in sites]
    model.add_linear_constraint(sum(shape), 17, 20)
    model.add(sum(v for p,v in zip(sites,shape) if p in base) >= len(base) - 6)
    model.add_bool_or([v.Not() if p in base else v for p,v in zip(sites,shape)])
    chart = [(l,t) for l,t in template.patches[0] if l<=depth]
    world = [defaultdict(list) for _ in range(depth+1)]
    for layer, t in chart:
        for index, p in enumerate(sites):
            world[layer][t.apply(p)].append(index)
    all_cells = set().union(*world)
    occupancy = {q:sum([layer.get(q,[]) for layer in world],[]) for q in all_cells}
    conflicts = {tuple(sorted(indices)) for indices in occupancy.values() if len(indices)>1}
    for indices in conflicts:
        model.add(sum(shape[i] for i in indices)<=1)
    implications = set()
    for layer in range(depth):
        inner = {q:sum([lvl.get(q,[]) for lvl in world[:layer+1]],[]) for q in set().union(*world[:layer+1])}
        outer = {q:sum([lvl.get(q,[]) for lvl in world[:layer+2]],[]) for q in all_cells}
        for q, indices in inner.items():
            for n in G.edge_neighbors(q):
                difference = Counter(indices)
                difference.subtract(outer.get(n,[]))
                coeff = tuple(sorted((i,w) for i,w in difference.items() if w))
                if coeff and any(w>0 for _,w in coeff):
                    implications.add(coeff)
    for coefficients in implications:
        model.add(sum(weight*shape[i] for i,weight in coefficients)<=0)

    # A new outline must actually disrupt the seed's checked repeating layout.
    a,b,c = row["hnf"]
    bucket = defaultdict(list)
    for index, p in enumerate(sites):
        for orient, tx, ty in row["tiles"]:
            x,y = G.orientations[orient].apply(p)
            qu, rem = divmod(y+ty, c)
            bucket[((x+tx-qu*b)%a,rem)].append(index)
    violations = []
    for indices in {tuple(sorted(v)) for v in bucket.values()}:
        changed = model.new_bool_var("")
        model.add(sum(shape[i] for i in indices)!=1).only_enforce_if(changed)
        violations.append(changed)
    model.add_bool_or(violations)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = 7
    codes = Counter()
    found = {}
    last = "LIMIT"
    for _ in range(limit):
        state = solver.solve(model)
        if state not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            last = solver.status_name(state)
            break
        cells = frozenset(p for p,v in zip(sites,shape) if solver.value(v))
        model.add_bool_or([v.Not() if p in cells else v for p,v in zip(sites,shape)])
        if not connected(cells,G) or holes_of(cells,G):
            codes["tile_topology"] += 1
            continue
        key = " ".join(f"{x} {y}" for x,y in canonical_form(cells,G,True))
        coords = " ".join(f"{x} {y}" for x,y in sorted(cells))
        proposal = chart
        if depth == 1:
            boundary = {q for p in cells for q in G.edge_neighbors(p)} - cells
            proposal = [(l,t) for l,t in chart if not l or boundary & t.apply_all(cells)]
        text = f"H {coords}\n~ {depth} {depth} 1\n{len(proposal)}\n" + "".join(f"{l} {t.as_text()}\n" for l,t in proposal)
        try:
            w = verify_witness(text)
        except VerifyError:
            w = None
        if w is None or w.result.hc_verified != depth:
            codes["failed_geometry"] += 1
            continue
        tile_id = sha256(key.encode()).hexdigest()[:18]
        found[tile_id] = key
        (HERE/f"refits{depth}/{tile_id}.heesch").write_text(text)
    return found, codes, last


def main(depth, limit):
    (HERE/f"refits{depth}").mkdir(exist_ok=True)
    rows = json.loads((HERE/"five-periods.json").read_text())
    found = {}
    for r in sorted(rows,key=lambda r:-r["k"]):
        hits, errors, status = derivatives(r,depth,limit)
        found.update(hits)
        print(r["id"],len(hits),status,dict(errors),flush=True)
    (HERE/f"refits{depth}.tsv").write_text("".join(f"{k} H? {text}\n" for k,text in found.items()))
    print("distinct new verified charts",len(found),flush=True)


if __name__ == "__main__":
    main(*map(int,sys.argv[1:]))
