"""Diagnose the F(S,3)-UNSAT 6-hex that yields no hole-free 2-corona.

Questions: (1) F(S,2) verdict; (2) does blocked model enumeration EXHAUST
(=> no hole-free 2-config exists at all => Hc <= 1) or cap out; (3) what the
classifier's exact search says at a large budget; (4) does a hole-free
1-corona exist (Hc >= 1)."""

import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from pysat.solvers import Solver  # noqa: E402

import classify  # noqa: E402
from close_census import known_corpus_digests, solve_F  # noqa: E402
from heesch_verify.canonical import canonical_digest  # noqa: E402
from heesch_verify.grids import GRIDS  # noqa: E402
from heesch_verify.patch import check_corona  # noqa: E402
from heesch_verify.result import VerifyError  # noqa: E402
from heesch_verify.shape import holes_of  # noqa: E402
from heesch_verify.gates import IsohedralGate, Verdict  # noqa: E402
from heesch_encoder.multilevel.api import encode_multilevel  # noqa: E402
from heesch_encoder.multilevel.model import (  # noqa: E402
    config_to_corona_placements,
    decode_model,
)

grid = GRIDS["H"]
contact = grid.contact("point")
known = known_corpus_digests("hex6-", grid)
shapes = classify.free_polyforms("H", 6)
pool = []
for cells in shapes:
    tile = frozenset(cells)
    if holes_of(tile, grid):
        continue
    if canonical_digest(cells, grid, True) in known:
        continue
    if IsohedralGate(grid).check(tile) is Verdict.TILER:
        continue
    pool.append(cells)

cells = pool[59]  # shape [60/78], 1-indexed in the log
tile = frozenset(cells)
print("shape:", sorted(cells), flush=True)

for m in (1, 2, 3):
    v, model, enc = solve_F(tile, grid, contact, m)
    print(f"F(S,{m}): {v}  (vars={enc.num_vars})", flush=True)

# exhaustive blocked enumeration at m=2 with explicit outcome
enc = encode_multilevel(tile, grid, contact, 2)
ml = enc.formula
groups = {}
for li, lv in enumerate(ml.levels):
    for i, p in enumerate(lv):
        v = ml.level_offsets[li] + i + 1
        groups.setdefault((li + 1, classify.materialize(p, tile, grid)), []).append(v)
assumptions = [-v for vs in groups.values() for v in vs[1:]]
total_x = ml.level_offsets[-1] + len(ml.levels[-1])

seen = holefree = 0
outcome = "CAP"
t0 = time.time()
with Solver(name="cadical195", bootstrap_with=[list(c) for c in ml.clauses]) as s:
    for _ in range(200_000):
        if not s.solve(assumptions=assumptions):
            outcome = "EXHAUSTED"
            break
        model = s.get_model()
        seen += 1
        config = decode_model(ml, model)
        placements = config_to_corona_placements(tile, config, grid)
        try:
            check_corona(tile, placements, grid, contact, hole_mode="hc")
            holefree += 1
            print(f"  hole-free 2-config FOUND after {seen} models", flush=True)
            break
        except VerifyError:
            pass
        s.add_clause([-v for v in range(1, total_x + 1) if model[v - 1] > 0])
print(f"m=2 enumeration: {outcome} after {seen} models, hole-free={holefree} "
      f"({time.time() - t0:.0f}s)", flush=True)

res = classify.classify(cells, grid_id="H", budget_s=900)
print("classifier:", {k: v for k, v in res.items() if k in ("kind", "hc", "hh", "reached")},
      flush=True)
