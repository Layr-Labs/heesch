"""Dev-only local Heesch classifier: enumerate small polyforms, classify
Hc/Hh exactly by backtracking corona search (our frozen encoder + pysat),
and emit witnesses in heesch-sat text format for tests/corpus.

Witnesses are self-certifying — heesch_verify re-checks them independently —
and the published counts (Kaplan 2022 tables) anchor the classification:
heptominoes must come out as 104 tilers, 1 holed, 1 x (Hc=0, Hh=1),
2 x (Hc=1, Hh=1).

Not shipped; not imported by the packages. Usage:
    python tools/classify.py omino 7 out_dir/
"""

from __future__ import annotations

import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from pysat.solvers import Solver  # noqa: E402

from heesch_verify.canonical import canonical_form  # noqa: E402
from heesch_verify.grids import GRIDS  # noqa: E402

from heesch_verify.shape import connected, holes_of  # noqa: E402
from heesch_verify.transform import Xform  # noqa: E402
from heesch_verify.witness import verify_witness  # noqa: E402
from heesch_verify.gates import IsohedralGate, Verdict  # noqa: E402
from heesch_encoder.api import encode  # noqa: E402
from heesch_encoder.placements import materialize  # noqa: E402

DEPTH_CAP = 3
COMPLETIONS_CAP = 4000
SHAPE_BUDGET_S = 120.0


# ---------------------------------------------------------------- enumeration

from polyforms import free_polyforms  # noqa: E402,F401  (shared enumerator)


# ---------------------------------------------------------------- search

class Budget(Exception):
    pass


class _State:
    def __init__(self, tile, grid, contact, deadline):
        self.tile = tile
        self.grid = grid
        self.contact = contact
        self.deadline = deadline
        self.memo: dict = {}
        self.best_hc = 0
        self.best_hh = 0
        self.best_hc_patch = None   # placements list for the best Hc patch
        self.hh_from = None         # (hc_patch_placements, corona_placements)


def _completions(state, patch_cells, want_hole_free: bool):
    """One-shot eager enumeration (used only by emission helpers)."""
    sols = []
    any_sat = False
    for placements in _iter_completions(state, patch_cells, want_hole_free):
        if placements is ANY_SAT:
            any_sat = True
            continue
        sols.append(placements)
        if len(sols) > COMPLETIONS_CAP:
            raise Budget
    return sols, any_sat


ANY_SAT = object()  # sentinel yielded once when the formula is satisfiable


def _iter_completions(state, patch_cells, want_hole_free: bool):
    """Lazily yield corona completions of P_k as exact covers of R by the
    placement universe, geometrically deduped, min-candidate branching.

    ASSUMPTION (documented, validated against published values): only
    IRREDUNDANT covers are enumerated — every tile covers some R-cell chosen
    as a branch point. Any cover contains an irredundant subcover, so corona
    EXISTENCE (the ANY_SAT sentinel) is exact; but a hole-free REDUNDANT
    cover could in principle exist whose irredundant subcovers all have
    pockets (a redundant tile plugging a pocket). The heptomino and 6-hex
    calibrations reproduce Kaplan's published values under this assumption.
    """
    from heesch_encoder.placements import enumerate_universe
    from heesch_verify.patch import required_set

    universe = enumerate_universe(state.tile, patch_cells, state.grid, state.contact)
    R = sorted(required_set(patch_cells, state.contact))
    if not R:
        return
    cells_of_p = {p: materialize(p, state.tile, state.grid) for p in universe}
    # geometric dedupe: one canonical placement per distinct cell set
    canon: dict = {}
    for p in universe:
        canon.setdefault(cells_of_p[p], p)
    cellsets = list(canon.keys())
    cover_of = {c: [cs for cs in cellsets if c in cs] for c in R}
    if any(not cover_of[c] for c in R):
        return  # some required cell unreachable: no corona at all

    seen_sat = [False]
    count = [0]

    def rec(uncovered, chosen_sets, chosen_cells):
        if time.time() > state.deadline:
            raise Budget
        if not uncovered:
            if not seen_sat[0]:
                seen_sat[0] = True
                yield ANY_SAT
            if want_hole_free and holes_of(
                frozenset(patch_cells | chosen_cells), state.grid
            ):
                return
            count[0] += 1
            if count[0] > COMPLETIONS_CAP:
                raise Budget
            yield [canon[cs] for cs in chosen_sets]
            return
        c = min(uncovered, key=lambda cc: (len(cover_of[cc]), cc[1], cc[0]))
        for cs in cover_of[c]:
            if cs & chosen_cells:
                continue
            yield from rec(uncovered - cs, chosen_sets + [cs], chosen_cells | cs)

    yield from rec(frozenset(R), [], frozenset())


def _explore(state, patch_cells, placements_so_far, k):
    """Exhaustively extend the hole-free patch P_k; update best hc/hh.
    Lazy: recurses on each completion as found, so tilers hit the depth cap
    after one chain instead of after exhaustive sibling enumeration."""
    key = frozenset(patch_cells)
    if key in state.memo:
        return
    state.memo[key] = True

    if k >= DEPTH_CAP:
        raise Budget  # reached the cap: shape behaves like a tiler here

    for sol in _iter_completions(state, patch_cells, want_hole_free=True):
        if sol is ANY_SAT:
            if k + 1 > state.best_hh:
                state.best_hh = k + 1
                state.hh_from = list(placements_so_far)
            continue
        new_placements = placements_so_far + [(k + 1, p) for p in sol]
        if k + 1 > state.best_hc:
            state.best_hc = k + 1
            state.best_hc_patch = list(new_placements)
            if k + 1 > state.best_hh:
                state.best_hh = k + 1
        cells = set(patch_cells)
        for p in sol:
            cells |= materialize(p, state.tile, state.grid)
        _explore(state, frozenset(cells), new_placements, k + 1)


def classify(cells, grid_id="O", budget_s=SHAPE_BUDGET_S):
    """Returns dict with kind in {HOLE, TILER, NONTILER, INCONCLUSIVE} and,
    for NONTILER, exact hc/hh plus witness placements."""
    grid = GRIDS[grid_id]
    tile = frozenset(cells)
    if not connected(tile, grid):
        raise ValueError("disconnected")
    if holes_of(tile, grid):
        return {"kind": "HOLE"}
    if IsohedralGate(grid).check(tile) is Verdict.TILER:
        return {"kind": "TILER"}

    contact = grid.contact("point")
    state = _State(tile, grid, contact, time.time() + budget_s)
    try:
        _explore(state, tile, [(0, Xform(1, 0, 0, 0, 1, 0))], 0)
    except Budget:
        return {"kind": "INCONCLUSIVE", "reached": state.best_hc}
    return {
        "kind": "NONTILER",
        "hc": state.best_hc,
        "hh": state.best_hh,
        "hc_patch": state.best_hc_patch,
        "hh_base": state.hh_from,
    }


# ---------------------------------------------------------------- emission

def placement_to_xform(p, grid) -> Xform:
    sym = grid.orientations[p.symmetry_index]
    return Xform(sym.a, sym.b, sym.c0 + p.tx, sym.d, sym.e, sym.f0 + p.ty)


def witness_file(cells, grid_id, hc, hh, patches) -> str:
    """patches: list of placement lists [(level, Xform|Placement)]."""
    grid = GRIDS[grid_id]
    lines = [grid_id + " " + " ".join(f"{x} {y}" for x, y in sorted(cells))]
    lines.append(f"~ {hc} {hh} {len(patches)}")
    for patch in patches:
        lines.append(str(len(patch)))
        for lvl, xf in patch:
            if not isinstance(xf, Xform):
                xf = placement_to_xform(xf, grid)
            lines.append(f"{lvl} {xf.as_text()}")
    return "\n".join(lines) + "\n"


def emit_nontiler(cells, grid_id, res, out_path: pathlib.Path):
    """Build the witness file (P=1 or 2 per hh) and verify it before writing."""
    grid = GRIDS[grid_id]
    contact = grid.contact("point")
    patches = [res["hc_patch"] or [(0, Xform(1, 0, 0, 0, 1, 0))]]
    if res["hh"] == res["hc"] + 1:
        # Second patch: the hh_base patch plus one hole-allowed corona.
        base = res["hh_base"] or [(0, Xform(1, 0, 0, 0, 1, 0))]
        tile = frozenset(cells)
        cellsU = set()
        for lvl, xf in base:
            x = xf if isinstance(xf, Xform) else placement_to_xform(xf, grid)
            cellsU |= x.apply_all(tile)
        # find ONE hole-allowed completion — lazy, first solution wins
        state = _State(tile, grid, contact, time.time() + 120)
        sol = None
        for item in _iter_completions(state, frozenset(cellsU), want_hole_free=False):
            if item is ANY_SAT:
                continue
            sol = item
            break
        assert sol is not None, "hh witness vanished"
        k = max(lvl for lvl, _ in base)
        patches.append(list(base) + [(k + 1, p) for p in sol])

    text = witness_file(cells, grid_id, res["hc"], res["hh"], patches)
    out = verify_witness(text)
    assert out.result.hc_verified == res["hc"], (
        f"witness verifies at {out.result.hc_verified}, classified {res['hc']}"
    )
    assert out.result.hh_verified == res["hh"]
    out_path.write_text(text, encoding="ascii", newline="\n")
    return text


# ---------------------------------------------------------------- main

GRID_OF = {"omino": "O", "hex": "H", "iamond": "I"}


def _worker(args):
    gid, cells, budget = args
    try:
        res = classify(cells, grid_id=gid, budget_s=budget)
    except Exception as e:  # a worker crash must not kill the sweep
        res = {"kind": "ERROR", "error": repr(e)}
    return cells, res


def main():
    global SHAPE_BUDGET_S
    kind, n, out_dir = sys.argv[1], int(sys.argv[2]), pathlib.Path(sys.argv[3])
    jobs = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    if len(sys.argv) > 5:
        SHAPE_BUDGET_S = float(sys.argv[5])
    gid = GRID_OF[kind]
    out_dir.mkdir(parents=True, exist_ok=True)
    shapes = free_polyforms(gid, n)
    print(f"{len(shapes)} free {n}-cell {kind}s (jobs={jobs})", flush=True)
    if jobs > 1:
        _main_parallel(kind, gid, n, out_dir, shapes, jobs)
        return
    counts = {"HOLE": 0, "TILER": 0, "NONTILER": 0, "INCONCLUSIVE": 0}
    nontilers = []
    t0 = time.time()
    for i, cells in enumerate(shapes):
        res = classify(cells, grid_id=gid)
        counts[res["kind"]] += 1
        if res["kind"] == "NONTILER":
            nontilers.append((cells, res))
            print(f"  nontiler #{len(nontilers)}: hc={res['hc']} hh={res['hh']} "
                  f"{sorted(cells)[:4]}...", flush=True)
        elif res["kind"] == "INCONCLUSIVE":
            print(f"  inconclusive (reached {res['reached']}): {sorted(cells)}", flush=True)
        elif res["kind"] == "HOLE":
            path = out_dir / f"{kind}{n}-holed-{counts['HOLE']}.txt"
            grid_line = gid + " " + " ".join(f"{x} {y}" for x, y in sorted(cells))
            path.write_text(grid_line + "\n~ 0 0 0\n", encoding="ascii", newline="\n")
        if (i + 1) % 20 == 0:
            print(f"  ... {i + 1}/{len(shapes)} ({time.time() - t0:.0f}s)", flush=True)
    for j, (cells, res) in enumerate(nontilers):
        emit_nontiler(cells, gid, res,
                      out_dir / f"{kind}{n}-nontiler-{j}-hc{res['hc']}hh{res['hh']}.txt")
    print(f"counts: {counts}  ({time.time() - t0:.0f}s)", flush=True)


def _main_parallel(kind, gid, n, out_dir, shapes, jobs):
    import multiprocessing as mp

    t0 = time.time()
    counts = {"HOLE": 0, "TILER": 0, "NONTILER": 0, "INCONCLUSIVE": 0, "ERROR": 0}
    nontilers = []
    with mp.Pool(jobs) as pool:
        done = 0
        for cells, res in pool.imap_unordered(
            _worker, [(gid, c, SHAPE_BUDGET_S) for c in shapes], chunksize=1
        ):
            counts[res["kind"]] += 1
            done += 1
            if res["kind"] == "NONTILER":
                nontilers.append((cells, res))
                print(f"  nontiler #{len(nontilers)}: hc={res['hc']} hh={res['hh']} "
                      f"{sorted(cells)[:4]}...", flush=True)
            elif res["kind"] == "ERROR":
                print(f"  WORKER ERROR: {res['error']} on {sorted(cells)}", flush=True)
            elif res["kind"] == "HOLE":
                path = out_dir / f"{kind}{n}-holed-{counts['HOLE']}.txt"
                grid_line = gid + " " + " ".join(f"{x} {y}" for x, y in sorted(cells))
                path.write_text(grid_line + "\n~ 0 0 0\n", encoding="ascii", newline="\n")
            if done % 25 == 0:
                print(f"  ... {done}/{len(shapes)} ({time.time() - t0:.0f}s) {counts}",
                      flush=True)
    for j, (cells, res) in enumerate(nontilers):
        try:
            emit_nontiler(cells, gid, res,
                          out_dir / f"{kind}{n}-nontiler-{j}-hc{res['hc']}hh{res['hh']}.txt")
        except Exception as e:
            print(f"  EMIT FAILED for nontiler {j}: {e!r}", flush=True)
    print(f"counts: {counts}  ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
