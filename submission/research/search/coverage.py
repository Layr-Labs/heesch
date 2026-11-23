"""Optimize one fixed patch's next corona; independently verify every saved result.

Run with the benchmark installed and ortools==9.15.6755:
  python submission/research/optimize_defect.py INPUT OUTPUT --seconds 60

This is search code, never part of the benchmark verifier. The objective bounds
uncovered required cells; enclosed pockets are measured by the official verifier.
"""

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from ortools.sat.python import cp_model

from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.parse import DefectBlock
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of
from heesch_verify.transform import Xform


def solve(input_path, output_path, seconds, workers, seed):
    text = input_path.read_text(encoding="ascii")
    # A proof must stay bound to its original shape and encoder. This experiment
    # only accepts census inputs and does not copy, transport, or edit a proof.
    if "#PROOF" in text:
        raise ValueError("Use an independent census patch without a proof block.")
    base_text = text.split("#DEFECT", 1)[0].rstrip() + "\n"
    result = verify_witness(base_text)
    corona = result.hc_corona
    shape = frozenset(result.submission.cells)
    grid = result.submission.grid
    patch = corona.patch_cells
    required = required_set(patch, result.contact)
    level = corona.max_level + 1
    if corona.has_outer_holes:
        raise ValueError("The seed patch must be hole-free.")

    # Every touching tile contains at least one required cell. Align every
    # oriented shape cell to every required cell, then deduplicate occupied sets.
    placements = {}
    for sym in grid.orientations:
        oriented = frozenset(sym.apply(cell) for cell in shape)
        for rx, ry in sorted(required):
            for sx, sy in sorted(oriented):
                dx, dy = rx - sx, ry - sy
                if not grid.translation_legal(dx, dy):
                    continue
                cells = frozenset((x + dx, y + dy) for x, y in oriented)
                if cells & patch:
                    continue
                xf = Xform(sym.a, sym.b, sym.c0 + dx,
                           sym.d, sym.e, sym.f0 + dy)
                placements.setdefault(cells, xf)
    items = sorted(placements.items(), key=lambda item: tuple(sorted(item[0])))

    model = cp_model.CpModel()
    variables = [model.new_bool_var(f"tile_{i}") for i in range(len(items))]
    covering = defaultdict(list)
    for i, (cells, _xf) in enumerate(items):
        for cell in cells:
            covering[cell].append(variables[i])
    for indices in covering.values():
        if len(indices) > 1:
            model.add_at_most_one(indices)
    coverage = [len(cells & required) for cells, _xf in items]
    # Coverage is primary; minimizing tile count breaks ties without sacrificing
    # even one covered required cell.
    multiplier = len(items) + 1
    model.maximize(sum((multiplier * n - 1) * var
                       for n, var in zip(coverage, variables)))

    class SaveVerified(cp_model.CpSolverSolutionCallback):
        def __init__(self):
            super().__init__()
            self.best = None
            self.saved = None

        def on_solution_callback(self):
            chosen = [item for item, var in zip(items, variables)
                      if self.value(var)]
            occupied = frozenset().union(*(cells for cells, _xf in chosen))
            uncovered = required - occupied
            pockets = holes_of(patch | occupied, grid)
            hc, hh = len(uncovered | pockets), len(uncovered)
            rank = (hc, hh, len(chosen))
            if self.best is not None and rank >= self.best:
                return
            block = DefectBlock(level, hc, hh, len(required),
                                tuple((level, xf) for _cells, xf in chosen))
            measured = verify_defect(shape, grid, corona, block, result.contact)
            output = base_text + (
                f"#DEFECT {level} {hc} {hh} {len(required)}\n"
                f"{len(chosen)}\n"
                + "".join(f"{level} {xf.as_text()}\n" for _cells, xf in chosen)
            )
            check = verify_witness(output)
            verify_defect(shape, grid, check.hc_corona,
                          check.submission.defect, check.contact)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output, encoding="ascii")
            self.best = rank
            self.saved = {
                "hc": corona.max_level,
                "required": len(required),
                "defect_hc": measured.defect_hc,
                "defect_hh": measured.defect_hh,
                "pocket_cells": measured.pocket_cells,
                "partial_tiles": measured.partial_tiles,
                "score": corona.max_level + max(0, 1 - hc / len(required)),
            }
            print(json.dumps({"saved": self.saved}), flush=True)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = seed
    callback = SaveVerified()
    status = solver.solve(model, callback)
    report = {
        "status": solver.status_name(status),
        "seconds": solver.wall_time,
        "placements": len(items),
        "seed": seed,
        "workers": workers,
        "time_limit": seconds,
        "objective": solver.objective_value,
        "best_objective_bound": solver.best_objective_bound,
        "saved": callback.saved,
        "input_sha256": hashlib.sha256(base_text.encode("ascii")).hexdigest(),
        "output_sha256": (hashlib.sha256(output_path.read_bytes()).hexdigest()
                          if callback.saved else None),
        "scope": "fixed input patch; objective covers required cells",
    }
    output_path.with_suffix(".search.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(json.dumps(report), flush=True)
    if callback.saved is None:
        raise RuntimeError("No verified construction was found.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20261120)
    args = parser.parse_args()
    solve(args.input, args.output, args.seconds, args.workers, args.seed)
