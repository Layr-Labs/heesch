"""Close the open censuses with the v2 encoder + a SAT solver, and measure
the weak gap (multilevel spec §9.4; the v2 build's acceptance milestone).

  hex6:   F(S,3) over every unclassified hole-free 6-hex. UNSAT => W<=2 =>
          non-tiler with Hh<=2; extract a hole-free F(S,2) model as an Hc=2
          witness. Exactly ONE shape must land here (the known missing
          Hc=2 hex).
  omino8: same at F(S,2) for the one unclassified octomino => Hc=Hh=1.
  gap:    for every corpus shape with known exact values, solve F(S, k+1)
          where k = Hh. UNSAT = v2 exactness reproduction; SAT = a measured
          weak-gap instance (verified genuinely holed, else it's an M-bug).

Dev-tier tool (pysat): solver verdicts here close the *census*; record-tier
claims still require checked proof artifacts.

Usage: python tools/close_census.py {hex6|omino8|gap} [jobs]
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pysat.solvers import Solver  # noqa: E402

from heesch_verify.canonical import canonical_digest  # noqa: E402
from heesch_verify.grids import GRIDS  # noqa: E402
from heesch_verify.parse import parse_submission  # noqa: E402
from heesch_verify.patch import check_corona  # noqa: E402
from heesch_verify.result import VerifyError  # noqa: E402
from heesch_verify.shape import holes_of  # noqa: E402
from heesch_verify.witness import verify_witness  # noqa: E402
from heesch_verify.gates import IsohedralGate, Verdict  # noqa: E402
from heesch_encoder.multilevel.api import encode_multilevel  # noqa: E402
from heesch_encoder.multilevel.model import (  # noqa: E402
    config_to_corona_placements,
    decode_model,
)

sys.path.insert(0, str(ROOT / "tools"))
import classify  # noqa: E402

CORPUS = ROOT / "tests" / "corpus"
BLOCK_CAP = 50_000


def solve_F(tile, grid, contact, m):
    """Returns ("UNSAT", None) or ("SAT", model)."""
    enc = encode_multilevel(tile, grid, contact, m)
    if any(len(c) == 0 for c in enc.formula.clauses):
        return "UNSAT", None, enc
    with Solver(name="cadical195",
                bootstrap_with=[list(c) for c in enc.formula.clauses]) as s:
        if s.solve():
            return "SAT", s.get_model(), enc
        return "UNSAT", None, enc


def extract_hc_witness(tile, grid, contact, k):
    """A hole-free weak k-configuration = an Hc >= k witness.

    Two attempts: (1) the classifier's hole-free exact-cover DFS, first
    chain to depth k wins — fast, but limited to irredundant covers;
    (2) F(S,k) model enumeration with symmetry duplicates collapsed and
    holed models blocked — complete over all configurations, capped.
    Returns placement list [(level, Xform)] or None (cap/budget exhaustion,
    NOT proof of nonexistence)."""
    tile = frozenset(tile)

    # --- attempt 1: DFS ---
    state = classify._State(tile, grid, contact, time.time() + 300)
    hit = []

    def rec(patch_cells, config, depth):
        if depth == k:
            hit.append(list(config))
            return True
        for sol in classify._iter_completions(state, patch_cells,
                                              want_hole_free=True):
            if sol is classify.ANY_SAT:
                continue
            cells = set(patch_cells)
            for p in sol:
                cells |= classify.materialize(p, tile, grid)
            if rec(frozenset(cells), config + [(depth + 1, p) for p in sol],
                   depth + 1):
                return True
        return False

    try:
        found = rec(tile, [], 0)
    except classify.Budget:
        found = False
    if found:
        placements = config_to_corona_placements(tile, hit[0], grid)
        try:
            check_corona(tile, placements, grid, contact, hole_mode="hc")
            return placements
        except VerifyError:
            pass  # fall through to SAT attempt

    # --- attempt 2: blocked SAT enumeration ---
    enc = encode_multilevel(tile, grid, contact, k)
    if any(len(c) == 0 for c in enc.formula.clauses):
        return None
    ml = enc.formula
    groups: dict = {}
    for li, lv in enumerate(ml.levels):
        for i, p in enumerate(lv):
            v = ml.level_offsets[li] + i + 1
            cs = classify.materialize(p, tile, grid)
            groups.setdefault((li + 1, cs), []).append(v)
    assumptions = [-v for vs in groups.values() for v in vs[1:]]

    with Solver(name="cadical195",
                bootstrap_with=[list(c) for c in ml.clauses]) as s:
        for _ in range(BLOCK_CAP):
            if not s.solve(assumptions=assumptions):
                return None
            model = s.get_model()
            config = decode_model(ml, model)
            placements = config_to_corona_placements(tile, config, grid)
            try:
                check_corona(tile, placements, grid, contact, hole_mode="hc")
                return placements
            except VerifyError:
                total_x = ml.level_offsets[-1] + len(ml.levels[-1])
                s.add_clause([-v for v in range(1, total_x + 1)
                              if model[v - 1] > 0])
    return None


def known_corpus_digests(prefix, grid):
    out = {}
    for p in sorted(CORPUS.glob(f"{prefix}*.txt")):
        sub = parse_submission(p.read_text(encoding="ascii"))
        out[canonical_digest(sub.cells, grid, True)] = p.name
    return out


def emit_witness(tile, gid, hc, hh, placements, path):
    text = classify.witness_file(sorted(tile), gid, hc, hh, [placements])
    out = verify_witness(text)
    assert out.result.hc_verified == hc and out.result.hh_verified == hh, (
        f"witness verifies at ({out.result.hc_verified},{out.result.hh_verified}), "
        f"expected ({hc},{hh})"
    )
    path.write_text(text, encoding="ascii", newline="\n")


def close_family(gid, n, kind, m_test, expect_hc):
    grid = GRIDS[gid]
    contact = grid.contact("point")
    known = known_corpus_digests(f"{kind}{n}-", grid)
    shapes = classify.free_polyforms(gid, n)
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
    print(f"{kind}{n}: {len(pool)} unclassified shapes; solving F(S,{m_test})",
          flush=True)

    closed = []
    for i, cells in enumerate(pool):
        tile = frozenset(cells)
        t0 = time.time()
        verdict, _model, enc = solve_F(tile, grid, contact, m_test)
        print(f"  [{i + 1}/{len(pool)}] {verdict} "
              f"(vars={enc.num_vars} clauses={enc.num_clauses} "
              f"{time.time() - t0:.1f}s)", flush=True)
        if verdict == "UNSAT":
            k = m_test - 1
            placements = extract_hc_witness(tile, grid, contact, k)
            assert placements is not None, (
                f"F(S,{m_test}) UNSAT but no hole-free {k}-config found — "
                "either Hc<k (weaker witness needed) or an M-bug"
            )
            closed.append((cells, placements))
            print(f"    -> non-tiler, Hc={k} witness extracted", flush=True)

    assert len(closed) == 1, (
        f"{kind}{n}: expected exactly 1 census-closing shape, got {len(closed)}"
    )
    cells, placements = closed[0]
    k = m_test - 1
    idx = len(known)
    path = CORPUS / f"{kind}{n}-nontiler-{idx}-hc{k}hh{k}.txt"
    emit_witness(frozenset(cells), gid, k, k, placements, path)
    print(f"census closed: {path.name}", flush=True)


def gap():
    rows = []
    for p in sorted(CORPUS.glob("*nontiler*.txt")):
        sub = parse_submission(p.read_text(encoding="ascii"))
        grid = sub.grid
        contact = grid.contact("point")
        tile = frozenset(sub.cells)
        k = sub.hh_claim  # exact for classified corpus shapes
        t0 = time.time()
        verdict, model, enc = solve_F(tile, grid, contact, k + 1)
        note = ""
        if verdict == "SAT":
            # must be a genuinely holed configuration, else it's an M-bug
            config = decode_model(enc.formula, model)
            placements = config_to_corona_placements(tile, config, grid)
            check_corona(tile, placements, grid, contact, hole_mode="none")
            try:
                check_corona(tile, placements, grid, contact, hole_mode="hh")
                raise AssertionError(
                    f"{p.name}: SAT model is a legal Hh {k + 1}-patch — the "
                    "shape's known Hh is wrong or the encoder is broken"
                )
            except VerifyError:
                note = "weak-gap instance (holed inner corona)"
        rows.append((p.name, sub.grid_id, len(sub.cells), k, verdict, note,
                     round(time.time() - t0, 1)))
        print(f"  {p.name}: F(S,{k + 1}) {verdict} {note}", flush=True)

    unsat = sum(1 for r in rows if r[4] == "UNSAT")
    lines = [
        "# v2 weak-gap measurement (multilevel spec §9.4)", "",
        f"Corpus shapes with known exact Heesch values: {len(rows)}. "
        f"F(S, k+1) UNSAT (exactness reproduced): {unsat}. "
        f"SAT (weak-gap instances): {len(rows) - unsat}.", "",
        "| shape | grid | cells | k | F(S,k+1) | note | secs |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append("| " + " | ".join(str(x) for x in r) + " |")
    out = ROOT / "docs" / "ml-weak-gap.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out}: {unsat}/{len(rows)} exactness reproductions", flush=True)


def main():
    cmd = sys.argv[1]
    if cmd == "hex6":
        close_family("H", 6, "hex", 3, 2)
    elif cmd == "omino8":
        close_family("O", 8, "omino", 2, 1)
    elif cmd == "gap":
        gap()
    else:
        raise SystemExit("usage: close_census.py {hex6|omino8|gap}")


if __name__ == "__main__":
    main()
