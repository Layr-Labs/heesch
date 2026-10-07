#!/usr/bin/env python3
"""Independent CP-SAT calibration of the promoted 15-hex fixed P4 packing.

Enumerates every legal corona-5 placement that touches the fixed complete
patch, then imposes cell-level disjointness on complete tile footprints.
Outputs solver and official verifier results under submission/.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from ortools.sat.python import cp_model

from heesch_verify.defect import verify_defect
from heesch_verify.parse import DefectBlock, parse_submission
from heesch_verify.patch import check_corona, required_set
from heesch_verify.transform import Xform

ROOT = Path(__file__).resolve().parent.parent
SUB = Path(__file__).resolve().parent
INPUT = SUB / "best.heesch"
OUT = SUB / "fixed_patch_check.json"


def enumerate_candidates(cells, grid, patch):
    """Exact finite pool: orientation × patch contact × source-shape cell."""
    by_footprint = {}
    contact = grid.contact("point")
    for sym in grid.orientations:
        oriented = tuple(
            (sym.a*x + sym.b*y + sym.c0, sym.d*x + sym.e*y + sym.f0)
            for x, y in cells
        )
        for p in patch:
            for neighbor in contact.neighbors(p):
                for q in oriented:
                    tx, ty = neighbor[0]-q[0], neighbor[1]-q[1]
                    footprint = frozenset((x+tx, y+ty) for x, y in oriented)
                    if footprint.isdisjoint(patch):
                        by_footprint.setdefault(
                            footprint,
                            (sym, tx, ty),
                        )
    return [(footprint, xf) for footprint, xf in by_footprint.items()]


def solve_threshold(candidates, required, max_missing, time_limit=120):
    model = cp_model.CpModel()
    picks = [model.new_bool_var(f"tile_{i}") for i in range(len(candidates))]
    cell_to_tiles = defaultdict(list)
    for i, (footprint, _xf) in enumerate(candidates):
        for cell in footprint:
            cell_to_tiles[cell].append(picks[i])
    # Full tile footprints are used here, including cells outside required R.
    for vars_at_cell in cell_to_tiles.values():
        if len(vars_at_cell) > 1:
            model.add_at_most_one(vars_at_cell)

    covered = []
    for j, cell in enumerate(sorted(required)):
        y = model.new_bool_var(f"covered_{j}")
        incidences = [picks[i] for i, (footprint, _xf) in enumerate(candidates)
                      if cell in footprint]
        if incidences:
            model.add(y <= sum(incidences))
        else:
            model.add(y == 0)
        covered.append(y)
    model.add(sum(covered) >= len(required)-max_missing)
    model.maximize(sum(covered))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 8
    solver.parameters.random_seed = 1
    start = time.monotonic()
    status = solver.solve(model)
    elapsed = time.monotonic()-start
    selected = []
    covered_cells = set()
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for i, var in enumerate(picks):
            if solver.boolean_value(var):
                fp, (sym, tx, ty) = candidates[i]
                xf = Xform(sym.a, sym.b, sym.c0+tx,
                           sym.d, sym.e, sym.f0+ty)
                selected.append(xf)
                covered_cells.update(fp & required)
    return {
        "status": solver.status_name(status),
        "wall_seconds": elapsed,
        "selected_tiles": selected,
        "covered": covered_cells,
        "objective": len(covered_cells),
        "best_bound": solver.best_objective_bound,
    }


def main():
    sub = parse_submission(INPUT.read_text())
    grid = sub.grid
    contact = grid.contact("point")
    corona = check_corona(sub.cells, sub.patches[0], grid, contact,
                          hole_mode="hc")
    patch = corona.patch_cells
    required = required_set(patch, contact)
    candidates = enumerate_candidates(sub.cells, grid, patch)

    baseline_official = verify_defect(
        sub.cells, grid, corona, sub.defect, contact,
    ) if sub.defect is not None else None
    baseline = {
        "tiles": len(sub.defect.tiles) if sub.defect is not None else 0,
        "official_verifier": asdict(baseline_official) if baseline_official else None,
    }

    results = {}
    for max_missing in (2, 3):
        res = solve_threshold(candidates, required, max_missing)
        selected = res.pop("selected_tiles")
        covered = res.pop("covered")
        official = None
        if selected:
            block = DefectBlock(
                level=5, u_hc=len(required), u_hh=len(required),
                required=len(required), tiles=tuple((5, xf) for xf in selected),
            )
            try:
                defect = verify_defect(sub.cells, grid, corona, block, contact)
                official = asdict(defect)
            except Exception as exc:  # preserve diagnostics in result artifact
                official = {"error": type(exc).__name__, "detail": str(exc)}
        results[str(max_missing)] = {
            **res,
            "official_verifier": official,
            "covered_required_cells": len(covered),
            "uncovered_required_cells": len(required-covered),
        }

    OUT.write_text(json.dumps({
        "method": "OR-Tools CP-SAT, full-footprint at-most-one constraints",
        "input": "submission/best.heesch (read only)",
        "grid": sub.grid_id,
        "shape_cells": len(sub.cells),
        "complete_patch_cells": len(patch),
        "verified_coronas": corona.max_level,
        "required_cells": len(required),
        "candidate_placements": len(candidates),
        "fixed_incumbent_witness": baseline,
        "threshold_checks": results,
        "limitations": [
            "Fixed P4 only; no changes to shape or complete-corona witness.",
            "The D<=2 infeasibility applies to defect_hh and therefore also rules out defect_hc<=2. The CP-SAT D<=3 maximum-coverage packing has pockets, so the fixed incumbent is separately checked as a valid defect_hc=3 witness.",
            "No leaderboard submission or score is produced by this calibration.",
        ],
    }, indent=2, default=lambda obj: asdict(obj) if hasattr(obj, "__dataclass_fields__") else str(obj)) + "\n")
    print(OUT)
    print(json.dumps({"candidates": len(candidates), "required": len(required),
                      "results": {k: {x: v for x, v in val.items()
                                      if x != "official_verifier"} | {"official_verifier": val["official_verifier"]}
                                  for k, val in results.items()}}, indent=2, default=str))


if __name__ == "__main__":
    main()
