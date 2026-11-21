"""Move the protrusions of the 19-hex that supports the 112-tile patch."""
from collections import Counter
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path

LANE = Path(__file__).resolve().parent
from heesch_verify.canonical import canonical_form
from heesch_verify.grids import GRIDS
from heesch_verify.shape import connected, holes_of

GRID = GRIDS["H"]
PARENT_ID = "4b4f0f5ae9b1ae49136a"


def neighbors(cells):
    return {q for p in cells for q in GRID.edge_neighbors(p)} - set(cells)


def additions(core, old, size):
    border = neighbors(core) - old
    if size == 0:
        yield ()
    elif size == 1:
        yield from ((p,) for p in sorted(border))
    elif size == 2:
        yield from combinations(sorted(border), 2)
        for p in sorted(border):
            for q in sorted(set(GRID.edge_neighbors(p)) - old - border):
                yield tuple(sorted((p, q)))


def key_data(cells):
    text = "H? " + " ".join(f"{x} {y}" for x, y in canonical_form(cells, GRID, True))
    return sha256(text.encode()).hexdigest()[:20], text


def metric(cells, period):
    a, b, c = period["hnf"]
    cover = Counter()
    for orientation, dx, dy in period["tiles"]:
        transform = GRID.orientations[orientation]
        for point in cells:
            x, y = transform.apply(point)
            wraps, ry = divmod(y + dy, c)
            cover[(x + dx - b * wraps) % a, ry] += 1
    return a * c - len(cover), sum(n - 1 for n in cover.values())


def main():
    line = (LANE / "parent.heesch").read_text().splitlines()[0]
    ints = list(map(int, line.split()[1:]))
    old = frozenset(zip(ints[::2], ints[1::2]))
    period = json.loads((LANE / "parent-period.json").read_text())
    degree = {p: len(old.intersection(GRID.edge_neighbors(p))) for p in old}
    tips = {p for p, n in degree.items() if n <= 2}
    near_tips = old.intersection(tips | neighbors(tips))
    seen = set()
    counts = Counter()
    with (LANE / "family.tsv").open("w") as family, (LANE / "moves.jsonl").open("w") as record:
        for take in range(3):
            for lost in combinations(sorted(near_tips), take):
                if lost and not tips.intersection(lost):
                    continue
                core = old.difference(lost)
                for give in range(3):
                    if not 18 <= len(core) + give <= 20 or take + give == 0:
                        continue
                    for added in additions(core, old, give):
                        child = core.union(added)
                        if not connected(child, GRID) or holes_of(child, GRID):
                            continue
                        key, text = key_data(child)
                        if key == PARENT_ID or key in seen:
                            continue
                        seen.add(key)
                        gap, excess = metric(child, period)
                        counts[(len(child), gap == excess == 0)] += 1
                        family.write(f"{key} {text}\n")
                        record.write(json.dumps(dict(id=key, removed=lost, added=added,
                                                     parent_period_missing=gap,
                                                     parent_period_overlapped=excess)) + "\n")
    print("tip cells", sorted(tips), "near tips", sorted(near_tips),
          "unique size/original-period", dict(counts))


if __name__ == "__main__":
    main()
