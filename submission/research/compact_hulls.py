"""Enumerate legal 19/20-hex shapes with an exact six-direction bounding hull."""
from collections import Counter
from hashlib import sha256
from itertools import combinations
from pathlib import Path
import sys

from heesch_verify.canonical import canonical_form
from heesch_verify.grids import GRIDS
from heesch_verify.shape import connected, holes_of

GRID = GRIDS["H"]
HULLS = [(4, 6, 0, 7), (4, 6, 0, 8), (4, 6, 1, 7), (4, 7, 0, 6),
         (4, 7, 1, 7), (5, 5, 0, 6), (5, 5, 0, 7), (5, 5, 1, 7),
         (5, 6, 0, 6), (5, 6, 1, 6), (5, 6, 2, 7)]
BASE = Path(__file__).resolve().parent


def flood(seeds, allowed, adjacent):
    todo = seeds
    seen = seeds
    while todo:
        bit = todo & -todo
        newly = adjacent[bit.bit_length() - 1] & allowed & ~seen
        todo = (todo ^ bit) | newly
        seen |= newly
    return seen


def generate(name, parameters):
    width, height, low, high = parameters
    hull = [(x, y) for x in range(width) for y in range(height) if low <= x + y <= high]
    indices = {p: i for i, p in enumerate(hull)}
    adjacent = [sum(1 << indices[q] for q in GRID.edge_neighbors(p) if q in indices) for p in hull]
    rim = sum(1 << i for i, n in enumerate(adjacent) if n.bit_count() != 6)
    faces = []
    for values in ([p[0] for p in hull], [p[1] for p in hull], [sum(p) for p in hull]):
        for endpoint in (min(values), max(values)):
            faces.append(sum(1 << i for i, v in enumerate(values) if v == endpoint))
    # Each legal child touches all six faces. Thus normalizing the parent gives
    # the same offsets as normalizing the child for all twelve symmetries.
    oriented = []
    for o in GRID.orientations:
        points = list(map(o.apply, hull))
        x0 = min(x for x, y in points)
        y0 = min(y for x, y in points)
        flags = tuple(1 << (255 - ((x - x0) * 16 + y - y0)) for x, y in points)
        oriented.append((sum(flags), flags))
    all_cells = (1 << len(hull)) - 1
    counts = Counter()
    with (BASE / f"{name}.tsv").open("w") as output:
        for size in (20, 19):
            seen = set()
            for removed in combinations(range(len(hull)), len(hull) - size):
                missing = sum(1 << i for i in removed)
                shape = all_cells ^ missing
                if any(not face & shape for face in faces):
                    continue
                if flood(missing & rim, missing, adjacent) != missing:
                    continue
                if flood(shape & -shape, shape, adjacent) != shape:
                    continue
                form = max(parent - sum(flags[i] for i in removed) for parent, flags in oriented)
                if form in seen:
                    continue
                seen.add(form)
                encoded = []
                tail = form
                while tail:
                    i = tail.bit_length() - 1
                    encoded.append(divmod(255 - i, 16))
                    tail ^= 1 << i
                if counts[size] % 251 == 0:
                    raw = frozenset(p for i, p in enumerate(hull) if shape & (1 << i))
                    assert connected(raw, GRID) and not holes_of(raw, GRID)
                    assert tuple(encoded) == canonical_form(raw, GRID, True)
                counts[size] += 1
                text = "H? " + " ".join(f"{x} {y}" for x, y in encoded)
                output.write(f"{sha256(text.encode()).hexdigest()[:20]} {text}\n")
    print(name, parameters, len(hull), dict(counts), flush=True)


if __name__ == "__main__":
    for index in map(int, sys.argv[1:] or range(len(HULLS))):
        generate(f"hull{index:02}", HULLS[index])
