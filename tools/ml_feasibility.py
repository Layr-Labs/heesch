"""v2 feasibility table (multilevel spec §10.2): variable/clause COUNTS for F(S, m)
without building clause objects. This is the Phase B gate — the published
(cells, m) band decision comes from this table.

Usage: python tools/ml_feasibility.py out.md
       python tools/ml_feasibility.py --shape NAME|FILE --m M [--m M2 ...]
         (counts for one shape at the given levels, printed; NAME is a key of
          KAPLAN_SHAPES, FILE a submission text file)
"""

from __future__ import annotations

import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from heesch_encoder.amo import AMO_THRESHOLD  # noqa: E402
from heesch_encoder.multilevel.universe import (  # noqa: E402
    multilevel_universe,
    touching_cellset_pairs,
)
from heesch_verify.grids import GRIDS  # noqa: E402
from heesch_verify.parse import parse_submission  # noqa: E402
from heesch_verify.patch import contact_neighbors, required_set  # noqa: E402

ROW_BUDGET_S = 120.0

# Record-adjacent reference shapes from Kaplan 2022's published data
# (cs.uwaterloo.ca/~csk/heesch/, coordinates exactly as listed there — the
# same convention tools/gen_census_tables.py reads). Used for the
# record-scale measurements in docs/ml-feasibility.md: the Hc = 4 11-hex is
# the smallest shape with the known-record value, so F(S,6) (Hc = 5 with
# Hh = 5) and F(S,7) (Hc = 5 with Hh = 6) for a shape of its size are the
# instances an in-band / out-of-band record check must be able to handle.
KAPLAN_SHAPES = {
    # hex/11hex_3up.txt, the one "Hc = 4 Hh = 4" entry
    "hex11-kaplan-hc4hh4": ("H", [(-3, 2), (-3, 4), (-2, 2), (-2, 4), (-1, 1), (-1, 3),
                                   (0, 0), (0, 1), (0, 2), (0, 3), (1, 0)]),
    # hex/13hex_3up.txt, the one "Hc = 4 Hh = 4" entry
    "hex13-kaplan-hc4hh4": ("H", [(-2, 4), (-1, 2), (-1, 3), (0, 0), (0, 1), (0, 2), (0, 3),
                                   (1, 0), (1, 1), (1, 2), (2, 1), (2, 2), (3, 0)]),
    # hex/15hex_3up.txt, first of the two "Hc = 4 Hh = 4" entries
    "hex15-kaplan-hc4hh4-a": ("H", [(-4, 2), (-4, 3), (-3, 2), (-3, 3), (-3, 4), (-2, 1), (-2, 2),
                                     (-2, 3), (-2, 4), (-1, 1), (-1, 2), (0, 0), (0, 1), (1, 0), (1, 1)]),
    # hex/16hex_3up.txt, the one "Hc = 4 Hh = 4" entry
    "hex16-kaplan-hc4hh4": ("H", [(-4, 4), (-3, 3), (-3, 4), (-2, 1), (-2, 2), (-1, 1), (-1, 2),
                                   (0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (1, 3), (2, 0), (2, 2)]),
}


def count_formula(tile, grid, contact, m):
    """(vars, aux, per-family clause counts) from universes alone."""
    t0 = time.time()
    uni = multilevel_universe(tile, grid, contact, m)
    if time.time() - t0 > ROW_BUDGET_S:
        raise TimeoutError
    tile_set = frozenset(tile)

    u = [len(lv) for lv in uni.levels]
    n_x = sum(u)

    # multiplicity per (level, cellset) + per-cell cover counts
    mult = []
    cover_count: dict = {}
    for lv in uni.levels:
        d: dict = {}
        for p in lv:
            cs = uni.cells_of[p]
            d[cs] = d.get(cs, 0) + 1
            for c in cs:
                cover_count[c] = cover_count.get(c, 0) + 1
        mult.append(d)

    R0 = required_set(tile_set, contact)
    f1 = len(R0)

    f2 = 0
    aux = 0
    for n in cover_count.values():
        if n < 2:
            continue
        if n <= AMO_THRESHOLD:
            f2 += n * (n - 1) // 2
        else:
            f2 += 3 * n - 4
            aux += n - 1

    f4 = sum(u[1:])

    # union cellsets with ids for the touch graph
    all_sets = sorted({cs for d in mult for cs in d},
                      key=lambda cs: tuple(sorted(cs)))
    idx = {cs: i for i, cs in enumerate(all_sets)}
    pairs = touching_cellset_pairs(all_sets, contact)

    f5 = 0
    for (a, b) in pairs:
        A, B = all_sets[a], all_sets[b]
        for l in range(m):
            for j in range(m):
                if abs(l - j) < 2:
                    continue
                if l > j:
                    f5 += mult[l].get(A, 0) * mult[j].get(B, 0)
                    f5 += mult[l].get(B, 0) * mult[j].get(A, 0)

    f6 = 0
    for l in range(m - 1):
        for cs, k in mult[l].items():
            halo = contact_neighbors(cs, contact) - tile_set
            f6 += len(halo) * k

    clauses = f1 + f2 + f4 + f5 + f6
    return {
        "u": u, "vars": n_x, "aux": aux,
        "f1": f1, "f2": f2, "f4": f4, "f5": f5, "f6": f6,
        "clauses": clauses,
        "secs": round(time.time() - t0, 1),
    }


def synth_shapes():
    return [
        ("rect5x10", "O", [(x, y) for x in range(10) for y in range(5)]),
        ("square10", "O", [(x, y) for x in range(10) for y in range(10)]),
        ("rect10x20", "O", [(x, y) for x in range(20) for y in range(10)]),
    ]


def _one_shape(argv):
    import argparse

    ap = argparse.ArgumentParser(prog="ml_feasibility.py --shape")
    ap.add_argument("--shape", required=True, help="KAPLAN_SHAPES key or a submission file")
    ap.add_argument("--m", type=int, action="append", required=True)
    ap.add_argument("--budget", type=float, default=None, help="seconds per row")
    args = ap.parse_args(argv)
    if args.budget is not None:
        globals()["ROW_BUDGET_S"] = args.budget
    if args.shape in KAPLAN_SHAPES:
        gid, cells = KAPLAN_SHAPES[args.shape]
        name = args.shape
    else:
        sub = parse_submission(pathlib.Path(args.shape).read_text(encoding="ascii"))
        gid, cells, name = sub.grid_id, list(sub.cells), pathlib.Path(args.shape).stem
    grid = GRIDS[gid]
    contact = grid.contact("point")
    for m in args.m:
        try:
            r = count_formula(frozenset(cells), grid, contact, m)
        except (TimeoutError, MemoryError) as e:
            print(f"{name} ({gid}, {len(cells)} cells) m={m}: DNF ({type(e).__name__})", flush=True)
            continue
        print(f"{name} ({gid}, {len(cells)} cells) m={m}: u={'/'.join(map(str, r['u']))} "
              f"vars={r['vars'] + r['aux']} clauses={r['clauses']} "
              f"(f1={r['f1']} f2={r['f2']} f4={r['f4']} f5={r['f5']} f6={r['f6']}) {r['secs']}s",
              flush=True)
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--shape":
        sys.exit(_one_shape(sys.argv[1:]))
    out_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "ml-feasibility-counts.md"
    rows = []

    shapes = []
    for p in sorted((ROOT / "tests" / "corpus").glob("*nontiler*.txt")):
        sub = parse_submission(p.read_text(encoding="ascii"))
        shapes.append((p.stem, sub.grid_id, list(sub.cells)))
    shapes.extend(synth_shapes())

    for name, gid, cells in shapes:
        grid = GRIDS[gid]
        contact = grid.contact("point")
        max_m = 5 if len(cells) >= 50 else 3
        for m in range(2, max_m + 1):
            try:
                r = count_formula(frozenset(cells), grid, contact, m)
            except (TimeoutError, MemoryError):
                rows.append((name, gid, len(cells), m, None))
                break
            rows.append((name, gid, len(cells), m, r))
            print(f"{name} m={m}: vars={r['vars']+r['aux']} clauses={r['clauses']} "
                  f"({r['secs']}s)", flush=True)
            if r["clauses"] > 50_000_000:
                break

    lines = [
        "# v2 feasibility table (multilevel spec §10.2)", "",
        "Counts from universes alone — no clause objects. DNF = row budget "
        f"({ROW_BUDGET_S:.0f}s) or memory exceeded.", "",
        "| shape | grid | cells | m | u_l | vars | f1 | f2 | f4 | f5 | f6 | clauses | secs |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, gid, n, m, r in rows:
        if r is None:
            lines.append(f"| {name} | {gid} | {n} | {m} | DNF | | | | | | | | |")
        else:
            lines.append(
                f"| {name} | {gid} | {n} | {m} | {'/'.join(map(str, r['u']))} "
                f"| {r['vars'] + r['aux']} | {r['f1']} | {r['f2']} | {r['f4']} "
                f"| {r['f5']} | {r['f6']} | {r['clauses']} | {r['secs']} |"
            )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
