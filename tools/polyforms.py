"""Free-polyform enumeration shared by the dev tools and the test suite.

One implementation, imported everywhere (tools/classify.py,
tools/gen_census_tables.py, tests/test_census_gate.py,
tests/test_iamond_boundary.py). Growth is by edge adjacency from a single
seed cell; shapes are deduplicated by canonical form under the grid's full
point group (reflections included), so the output is the set of FREE
polyforms — the population Kaplan 2022 counts and classifies.

Not shipped in the package; not imported by heesch_verify or the harness.
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from heesch_verify.canonical import canonical_form  # noqa: E402
from heesch_verify.grids import GRIDS  # noqa: E402

# Kaplan 2022 (arXiv:2105.09438, Tables 1/3/5): free polyforms per size.
# Used by callers as an enumeration self-check.
FREE_COUNTS = {
    "O": {1: 1, 2: 1, 3: 2, 4: 5, 5: 12, 6: 35, 7: 108, 8: 369, 9: 1285, 10: 4655},
    "H": {1: 1, 2: 1, 3: 3, 4: 7, 5: 22, 6: 82, 7: 333, 8: 1448},
    "I": {1: 1, 2: 1, 3: 1, 4: 3, 5: 4, 6: 12, 7: 24, 8: 66, 9: 160, 10: 448,
          11: 1186, 12: 3334},
}


def free_polyforms(grid_id: str, n: int) -> list[tuple]:
    """All free n-cell polyforms on the grid (holed ones included), each as
    its canonical-form cell tuple."""
    grid = GRIDS[grid_id]
    seen: set = set()
    out: list = []
    visited_partial: set = set()

    def grow(cells: frozenset, frontier):
        if len(cells) == n:
            key = canonical_form(cells, grid, allow_reflections=True)
            if key not in seen:
                seen.add(key)
                out.append(key)
            return
        for c in sorted(frontier):
            for nb in grid.edge_neighbors(c):
                if nb in cells:
                    continue
                new = cells | {nb}
                key = tuple(sorted(new))
                if key in visited_partial:
                    continue
                visited_partial.add(key)
                grow(frozenset(new), sorted(new))

    seed = (0, 0)
    grow(frozenset([seed]), [seed])
    return out


def parse_kaplan_file(text: str) -> list[tuple[list[tuple[int, int]], int, int]]:
    """Parse one of Kaplan's published `*_Nup.txt` files: alternating lines
    `x1 y1 x2 y2 ...` and `Hc = a Hh = b`. Returns (cells, hc, hh) triples."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) % 2:
        raise ValueError("odd line count in Kaplan file")
    out = []
    for cell_line, hc_line in zip(lines[0::2], lines[1::2]):
        vals = list(map(int, cell_line.split()))
        if len(vals) % 2:
            raise ValueError(f"odd coordinate count: {cell_line!r}")
        toks = hc_line.replace("=", " ").split()
        if toks[0] != "Hc" or toks[2] != "Hh":
            raise ValueError(f"bad Hc/Hh line: {hc_line!r}")
        out.append((list(zip(vals[0::2], vals[1::2])), int(toks[1]), int(toks[3])))
    return out
