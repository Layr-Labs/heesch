from __future__ import annotations

import argparse
from collections import defaultdict, deque
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from shutil import copy2
import time

from ortools.sat.python import cp_model

from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of
from heesch_verify.transform import Xform


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


class Packing:
    def __init__(self, grid, shape, patch, contact, budget, max_tiles=None):
        self.grid = grid
        self.patch = patch
        self.required = required_set(patch, contact)
        self.items = enumerate_tiles(shape, grid, patch, self.required)
        self.model = cp_model.CpModel()
        self.select = [self.model.new_bool_var(f"t{i}") for i in range(len(self.items))]
        cover = defaultdict(list)
        for i, item in enumerate(self.items):
            for c in item.cells:
                cover[c].append(self.select[i])
        self.occupied = {}
        for c, choices in cover.items():
            occ = self.occupied[c] = self.model.new_bool_var(f"o{c}")
            self.model.add(sum(choices) == occ)

        # Every enclosed extra cell must be charged by the eventual flood
        # check. A local six-neighbor implication strengthens the basic model.
        bbox = set(cover) | {n for c in cover for n in grid.edge_neighbors(c)}
        self.pocket_penalty = {}
        for c in bbox - self.required - patch:
            neighbors = [1 if n in patch else self.occupied.get(n, 0)
                         for n in grid.edge_neighbors(c)]
            if any(type(v) is int and v == 0 for v in neighbors):
                continue
            penalty = self.pocket_penalty[c] = self.model.new_bool_var(f"p{c}")
            self.model.add(sum(neighbors) <= 5 + self.occupied.get(c, 0) + penalty)
        self.uncovered = sum(1 - self.occupied.get(c, 0) for c in self.required)
        self.budget = budget
        self.model.add(self.uncovered + sum(self.pocket_penalty.values()) <= budget)
        count = sum(self.select)
        if max_tiles is not None:
            self.model.add(count <= max_tiles)
        self.model.minimize(count)

    def add_hint(self, hint):
        for item, var in zip(self.items, self.select):
            self.model.add_hint(var, int(item.cells in hint))

    def solve(self, deadline, workers, seed):
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = workers
        solver.parameters.random_seed = seed
        cycles = 0
        best = None
        while time.monotonic() < deadline:
            solver.parameters.max_time_in_seconds = max(.05, deadline - time.monotonic())
            status = solver.solve(self.model)
            if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                return best, {"status": solver.status_name(status), "cycles": cycles,
                              "solver_s": solver.wall_time, "lower_bound": solver.best_objective_bound}
            cycles += 1
            chosen_idx = [i for i, v in enumerate(self.select) if solver.value(v)]
            owner = {c: i for i in chosen_idx for c in self.items[i].cells}
            uncovered = self.required - owner.keys()
            holes = holes_of(self.patch | frozenset(owner), self.grid)
            defect = len(uncovered | holes)
            if defect <= self.budget:
                best = [self.items[i] for i in chosen_idx]
                return best, {"status": solver.status_name(status), "cycles": cycles,
                              "solver_s": solver.wall_time, "lower_bound": solver.best_objective_bound,
                              "defect": defect, "required": len(self.required), "hh": len(uncovered)}
            pending = set(holes)
            while pending:
                start = pending.pop()
                component = {start}
                fringe = deque([start])
                adjacent = set()
                while fringe:
                    cell = fringe.popleft()
                    for other in self.grid.edge_neighbors(cell):
                        if other in pending:
                            pending.remove(other)
                            fringe.append(other)
                            component.add(other)
                        elif other in owner:
                            adjacent.add(owner[other])
                shell_open = sum(1 - self.select[i] for i in adjacent)
                # Every extra cell remains enclosed while this shell is intact,
                # unless another selected tile occupies it. Include an explicit
                # budget for cells with geometrically unfillable neighbors too.
                for c in component - self.required:
                    if c not in self.pocket_penalty:
                        self.pocket_penalty[c] = self.model.new_bool_var(f"p{c}")
                    self.model.add(shell_open + self.occupied.get(c, 0) + self.pocket_penalty[c] >= 1)
            self.model.add(self.uncovered + sum(self.pocket_penalty.values()) <= self.budget)
        return best, {"status": "TIMEOUT", "cycles": cycles}


def encode_full(line, placements):
    return f"{line}\n~ 4 4 1\n{len(placements)}\n" + "".join(
        f"{l} {xf.as_text()}\n" for l, xf in placements)


def write_candidate(path, line, placements, partial, proof_source, report):
    full = encode_full(line, placements)
    out = full + f"#DEFECT 5 {report['defect']} {report['hh']} {report['required']}\n"
    out += f"{len(partial)}\n" + "".join(f"5 {tile.xf.as_text()}\n" for tile in partial)
    src = proof_source.read_text()
    out += "#PROOF" + src.split("#PROOF", 1)[1]
    verified = verify_witness(out)
    defect = verify_defect(frozenset(verified.submission.cells), verified.submission.grid,
                           verified.hc_corona, verified.submission.defect, verified.contact)
    assert verified.hc_corona.max_level == 4
    assert defect.required == report["required"] and defect.defect_hc == report["defect"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(out, encoding="ascii")
    proofname = verified.submission.proof.file_name
    copy2(proof_source.parent / proofname, path.parent / proofname)
    return {"file": str(path), "sha256": sha256(out.encode("ascii")).hexdigest(),
            "partial_count": len(partial), **report}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-file", type=Path, default=Path("work/inherited-baseline/best.heesch"))
    parser.add_argument("--candidate", type=Path, default=Path("work/fourth-lane/attempt/best.heesch"))
    parser.add_argument("--budget", type=int, default=3)
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--max-tiles", type=int)
    parser.add_argument("--random", type=int, default=881221)
    args = parser.parse_args()
    source = args.seed_file.read_text()
    verified = verify_witness(source)
    shape = frozenset(verified.submission.cells)
    packing = Packing(verified.submission.grid, shape, verified.hc_corona.patch_cells,
                      verified.contact, args.budget, args.max_tiles)
    hint = {xf.apply_all(shape) for l, xf in verified.submission.defect.tiles}
    packing.add_hint(hint)
    print(json.dumps({"placements": len(packing.items), "budget": args.budget}), flush=True)
    result, stats = packing.solve(time.monotonic() + args.seconds, args.workers, args.random)
    if result:
        stats = write_candidate(args.candidate, source.splitlines()[0],
                                verified.submission.patches[0], result, args.seed_file, stats)
    print(json.dumps(stats), flush=True)
