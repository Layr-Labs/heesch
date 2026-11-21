"""Joint optimization of corona 4 and its fifth-corona packing for a fixed P3."""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
import json
from pathlib import Path
from shutil import copy2
import time

from ortools.sat.python import cp_model
from heesch_verify import verify_witness
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of

from pack import encode_full, enumerate_tiles, write_candidate


def consistent_placements(items, required):
    cover = defaultdict(int)
    for i, tile in enumerate(items):
        for c in tile.cells:
            cover[c] |= 1 << i
    conflict = [0] * len(items)
    for i, tile in enumerate(items):
        for c in tile.cells:
            conflict[i] |= cover[c]
    active = (1 << len(items)) - 1
    while True:
        updated = active
        for i, tile in enumerate(items):
            if not (active >> i) & 1:
                continue
            available = active & ~conflict[i]
            if any(c not in tile.cells and not (cover[c] & available) for c in required):
                updated ^= 1 << i
        if active == updated:
            break
        active = updated
    return [t for i,t in enumerate(items) if (active >> i) & 1]


def enclosures(holes, owner, grid):
    pending = set(holes)
    while pending:
        c = pending.pop()
        queue = deque([c])
        pocket = {c}
        shell = set()
        while queue:
            for n in grid.edge_neighbors(queue.popleft()):
                if n in pending:
                    pending.remove(n)
                    pocket.add(n)
                    queue.append(n)
                elif n in owner:
                    shell.add(owner[n])
        yield pocket, shell


def local_support(tiles, outer, upper_damage, p3, r4, grid):
    """Exclude outer tiles inconsistent with filling the inner boundary.

    Optional budget cuts use all outer tiles, so they cannot overestimate
    the missed boundary cells conditional on the chosen pair of tiles.
    """
    by4,by5=defaultdict(int),defaultdict(int)
    for i,t in enumerate(tiles):
        for c in t.cells: by4[c]|=1<<i
    for i,t in enumerate(outer):
        for c in t.cells: by5[c]|=1<<i
    def conflicts(t,lookup):
        m=0
        for c in t.cells: m|=lookup.get(c,0)
        return m
    all4=(1<<len(tiles))-1
    r4covers=[by4[c] for c in r4]
    keep=[]
    for t in outer:
        allowed4=all4&~conflicts(t,by4)
        if any(not covers&allowed4 for covers in r4covers):
            continue
        # Only placements with some disjoint contacting inner tile can occur.
        halo={n for c in t.cells for n in grid.edge_neighbors(c)}-t.cells
        if not any(by4.get(c,0)&allowed4 for c in halo):
            continue
        keep.append(t)
    print(json.dumps({"outer_before":len(outer),"outer_after_exact_inner_support":len(keep)}),flush=True)
    outer=keep
    by5=defaultdict(int)
    for i,t in enumerate(outer):
        for c in t.cells: by5[c]|=1<<i
    all5=(1<<len(outer))-1
    c4x4=[conflicts(t,by4) for t in tiles]
    c4x5=[conflicts(t,by5) for t in tiles]
    c5x4=[conflicts(t,by4) for t in outer]
    c5x5=[conflicts(t,by5) for t in outer]
    inner_halos=[{n for c in t.cells for n in grid.edge_neighbors(c)}-t.cells-p3-r4 for t in tiles]
    core_covers=[sorted((by4[c] for c in r4-t.cells),key=int.bit_count) for t in tiles]
    forbidden=[]
    if upper_damage is not None:
        for i,t in enumerate(tiles):
            allowed4=all4&~c4x4[i]
            allowed5=all5&~c4x5[i]
            must_be_outer=[c for c in inner_halos[i] if not by4.get(c,0)&allowed4]
            allowed_by_c={c:by5.get(c,0)&allowed5 for c in must_be_outer}
            for j,u in enumerate(outer):
                if (c4x5[i]>>j)&1: continue
                pair4=allowed4&~c5x4[j]
                if any(not m&pair4 for m in core_covers[i]):
                    forbidden.append((i,j))
                    continue
                available5=allowed5&~c5x5[j]
                # c outside occupied R4 and both selected tiles is required
                # if it neighbors tile i and cannot be occupied by level 4.
                if sum(c not in u.cells and not opt5&available5
                       for c,opt5 in allowed_by_c.items())>upper_damage:
                    forbidden.append((i,j))
    print(json.dumps({"additional_pair_cuts":len(forbidden)}),flush=True)
    return outer,forbidden


def run(opt):
    source = opt.source.read_text()
    boundary_weight, damage_weight = getattr(opt, "comparison", (3, 254))
    witness = verify_witness(source)
    shape = frozenset(witness.submission.cells)
    grid, contact = witness.submission.grid, witness.contact
    first_level = 3 if opt.complete_four else 4
    inner = [(l,xf) for l,xf in witness.submission.patches[0] if l < first_level]
    p3 = frozenset().union(*(xf.apply_all(shape) for l,xf in inner))
    r4 = required_set(p3, contact)
    raw = enumerate_tiles(shape, grid, p3, r4)
    fourth = consistent_placements(raw, r4)
    possible4 = frozenset().union(*(t.cells for t in fourth))
    possible5halo = frozenset(n for c in possible4 for n in grid.edge_neighbors(c)) - p3 - r4
    fifth = enumerate_tiles(shape, grid, p3 | r4, possible5halo)
    if opt.outer_reference:
        outer_witness=verify_witness(opt.outer_reference.read_text())
        prior={xf.apply_all(shape) for _,xf in outer_witness.submission.defect.tiles}
        fifth=[tile for tile in fifth if tile.cells in prior]
    pair_cuts=[]
    if opt.conditional_support:
        fifth,pair_cuts=local_support(fourth,fifth,opt.damage_max,p3,r4,grid)
    model = cp_model.CpModel()
    v4 = [model.new_bool_var(f"t4.{i}") for i,_ in enumerate(fourth)]
    v5 = [model.new_bool_var(f"t5.{i}") for i,_ in enumerate(fifth)]
    for i,j in pair_cuts:
        model.add_bool_or([v4[i].Not(),v5[j].Not()])
    by4,by5 = defaultdict(list),defaultdict(list)
    for items,lookup in [(fourth,by4),(fifth,by5)]:
        for i,t in enumerate(items):
            for c in t.cells:
                lookup[c].append(i)
    occ4,occ5={},{}
    for cells, lookup, variables, occ, level in [
            (possible4,by4,v4,occ4,4), (by5.keys(),by5,v5,occ5,5)]:
        for c in cells:
            occ[c] = model.new_bool_var(f"o{level}.{c}")
            model.add(sum(variables[i] for i in lookup[c]) == occ[c])
    for c in r4:
        model.add(occ4[c]==1)
    for c in occ4.keys() & occ5.keys():
        model.add(occ4[c]+occ5[c]<=1)

    required, uncovered = {}, {}
    for c in possible5halo:
        neighbors = [occ4[n] for n in grid.edge_neighbors(c) if n in occ4]
        any_neighbor = model.new_bool_var(f"n.{c}")
        model.add_max_equality(any_neighbor,neighbors)
        r = required[c] = model.new_bool_var(f"r.{c}")
        o4,o5 = occ4.get(c,0),occ5.get(c,0)
        model.add(r <= any_neighbor)
        model.add(r <= 1-o4)
        model.add(r >= any_neighbor-o4)
        u = uncovered[c] = model.new_bool_var(f"u.{c}")
        model.add(u<=r)
        model.add(u<=1-o5)
        model.add(u>=r-o5)
    for i,t in enumerate(fifth):
        model.add(v5[i] <= sum(required[c] for c in t.cells if c in required))
    occupied = {c:occ4.get(c,0)+occ5.get(c,0) for c in set(occ4)|set(occ5)}
    penalty={}
    adjacent = set(occupied) | {n for c in occupied for n in grid.edge_neighbors(c)}
    for c in adjacent - p3 - r4:
        ns=[1 if n in p3 else occupied.get(n,0) for n in grid.edge_neighbors(c)]
        if any(type(v) is int and v==0 for v in ns):
            continue
        p = penalty[c] = model.new_bool_var(f"p.{c}")
        model.add(sum(ns) <= 5 + occupied.get(c,0) + required.get(c,0) + p)
    B = sum(required.values())
    def add_target():
        d = sum(uncovered.values()) + sum(penalty.values())
        if opt.damage_max is not None:
            model.add(d<=opt.damage_max)
        if opt.complete_four:
            model.add(d==0)
        else:
            model.add(boundary_weight * B - damage_weight * d >= opt.target)
            if opt.maximize:
                model.maximize(boundary_weight * B - damage_weight * d)
    add_target()
    if opt.boundary_min:
        model.add(B >= opt.boundary_min)
    if opt.boundary_max is not None:
        model.add(B<=opt.boundary_max)
    seed4 = {xf.apply_all(shape) for l,xf in witness.submission.patches[0] if l==first_level}
    if opt.complete_four:
        seed5 = {xf.apply_all(shape) for l,xf in witness.submission.patches[0] if l==4}
    else:
        seed5 = ({xf.apply_all(shape) for _,xf in witness.submission.defect.tiles}
                 if witness.submission.defect else set())
    if opt.distinct4:
        model.add(sum(var for t,var in zip(fourth,v4) if t.cells in seed4) < len(seed4))
    if opt.distinct_domain:
        seed_domain=frozenset().union(*seed4)
        model.add(sum(1-occ4[c] if c in seed_domain else occ4[c] for c in possible4)>=1)
    for tiles,vars_,seed in [(fourth,v4,seed4),(fifth,v5,seed5)]:
        for t,var in zip(tiles,vars_):
            model.add_hint(var,int(t.cells in seed))

    print(json.dumps({"fixed_depth":first_level-1,"fixed_cells":len(p3),"first_required":len(r4),
                      "first_raw":len(raw),"first_possible":len(fourth),"second_possible":len(fifth),
                      "boundary_domain":len(required),
                      "pocket_vars":len(penalty),"target":opt.target}),flush=True)
    solver=cp_model.CpSolver()
    solver.parameters.num_search_workers=opt.workers
    deadline=time.monotonic()+opt.seconds
    step=0
    recorded=0
    while time.monotonic()<deadline:
        solver.parameters.max_time_in_seconds=deadline-time.monotonic()
        status=solver.solve(model)
        print(json.dumps({"step":step,"status":solver.status_name(status),"solve_s":solver.wall_time,
                          "objective":solver.objective_value,"upper_bound":solver.best_objective_bound}),flush=True)
        if status not in [cp_model.OPTIMAL,cp_model.FEASIBLE]:
            return
        picked4=[t for t,v in zip(fourth,v4) if solver.value(v)]
        picked5=[t for t,v in zip(fifth,v5) if solver.value(v)]
        owner4={c:i for i,t in enumerate(fourth) if solver.value(v4[i]) for c in t.cells}
        owner5={c:len(v4)+i for i,t in enumerate(fifth) if solver.value(v5[i]) for c in t.cells}
        chosenvars=v4+v5
        p4=p3|frozenset(owner4)
        rh=required_set(p4,contact)
        hh=rh-owner5.keys()
        holes4=holes_of(p4,grid)
        holes5=holes_of(p4|frozenset(owner5),grid)
        true_d=len(hh|holes5)
        gain=boundary_weight*len(rh)-damage_weight*true_d
        print(json.dumps({"boundary":len(rh),"hh":len(hh),"hc":true_d,"gain":gain,
                          "pocket4":len(holes4),"pocket5":len(holes5)}),flush=True)
        assert len(rh)==solver.value(B)
        optimum_ok = not opt.maximize or gain >= round(solver.objective_value)
        if not holes4 and optimum_ok and ((opt.complete_four and true_d==0) or
                           (not opt.complete_four and gain>=opt.target)):
            levels=inner+[(first_level,t.xf) for t in picked4]
            if opt.complete_four:
                levels.extend((4,t.xf) for t in picked5)
                out=encode_full(source.splitlines()[0],levels)
                out+="#PROOF"+source.split("#PROOF",1)[1]
                checked=verify_witness(out)
                assert checked.hc_corona.max_level==4 and not checked.hc_corona.has_outer_holes
                output=opt.output
                if opt.sample_domains>1:
                    output=output.with_name(f"{output.stem}-{recorded+1:03d}{output.suffix}")
                output.parent.mkdir(exist_ok=True,parents=True)
                output.write_text(out,encoding="ascii")
                name=checked.submission.proof.file_name
                copy2(opt.source.parent/name,output.parent/name)
                print(json.dumps({"file":str(output),"tiles":len(levels),
                                  "P3_difference":len(set(owner4)^frozenset().union(*seed4))}),flush=True)
                recorded+=1
                if recorded<opt.sample_domains:
                    model.add(sum(1-occ4[c] if c in owner4 else occ4[c] for c in possible4)>=1)
                    step+=1
                    continue
            else:
                print(json.dumps(write_candidate(opt.output,source.splitlines()[0],levels,picked5,opt.source,{
                    "required":len(rh),"hh":len(hh),"defect":true_d,"mode":"joint","gain":gain
                })),flush=True)
            return
        for comp,shell in enclosures(holes4,owner4,grid):
            broken=sum(1-chosenvars[i] for i in shell)
            for c in comp:
                model.add(broken+occ4.get(c,0)>=1)
        for comp,shell in enclosures(holes5,owner4|owner5,grid):
            broken=sum(1-chosenvars[i] for i in shell)
            for c in comp:
                if c not in penalty:
                    penalty[c]=model.new_bool_var(f"p.{c}")
                model.add(broken+occupied.get(c,0)+required.get(c,0)+penalty[c]>=1)
        add_target()
        step+=1


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=Path('work/inherited-baseline/best.heesch'))
    parser.add_argument('--output',type=Path,default=Path('work/fourth-lane/joint-attempt/best.heesch'))
    parser.add_argument('--seconds',type=float,default=90)
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--target',type=int,default=1,help='Minimum 3B - 254d')
    parser.add_argument('--distinct4',action='store_true')
    parser.add_argument('--distinct-domain',action='store_true',help='Require a different occupied first-ring footprint')
    parser.add_argument('--complete-four',action='store_true',help='Solve full coronas 3 and 4 on fixed P2')
    parser.add_argument('--sample-domains',type=int,default=1,help='Save distinct first-ring footprints in complete-four mode')
    parser.add_argument('--maximize',action='store_true',help='Maximize the exact score-improvement comparison')
    parser.add_argument('--boundary-min',type=int)
    parser.add_argument('--boundary-max',type=int)
    parser.add_argument('--damage-max',type=int)
    parser.add_argument('--conditional-support',action='store_true')
    parser.add_argument('--outer-reference',type=Path,help='Restrict second-ring candidates to this partial packing')
    run(parser.parse_args())
