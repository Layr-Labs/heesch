"""Reconstruct each cavity and replay positive witnesses and quotient tilings."""
from collections import Counter
from pathlib import Path
import json

from heesch_verify import GRIDS, Xform, canonical_form, holes_of, verify_witness
from heesch_verify.shape import check_shape, connected
from heesch_verify.transform import check_symmetry


here = Path(__file__).resolve().parent
grid = GRIDS["I"]
charts = json.loads((here / "charts.json").read_text())
bank = {r.split()[0]: r.split() for r in (here / "bank.tsv").read_text().splitlines()}
origins = {r.split()[0]: r.split() for r in (here / "origins.tsv").read_text().splitlines()}


def shape(key):
    coords = iter(map(int, bank[key][2:]))
    return frozenset(zip(coords, coords))


def reconstruct(key):
    _, chart_number, overlap, same, x, y, *words = origins[key]
    chart = charts[int(chart_number)]
    old = frozenset(map(tuple, chart["shape"]))
    edited = set(old)
    slides = {}
    actions = iter(words)
    for action in actions:
        if action == "move":
            idx, dx, dy = (int(next(actions)) for _ in range(3))
            assert grid.translation_legal(dx, dy)
            slides[idx] = (dx, dy)
        else:
            cell = (int(next(actions)), int(next(actions)))
            if action == "cut":
                edited.remove(cell)
            else:
                assert action == "add" and cell not in edited
                edited.add(cell)
    assert connected(edited, grid) and not holes_of(edited, grid)
    occupied = set()
    pieces = []
    for i, terms in enumerate(chart["neighbors"]):
        motion = Xform(*terms)
        check_symmetry(motion, grid, True)
        dx, dy = slides.get(i, (0, 0))
        footprint = {(a + dx, b + dy) for a, b in motion.apply_all(edited)}
        assert not occupied & footprint
        occupied.update(footprint)
        pieces.append(footprint)
    seed = int(x), int(y)
    assert seed not in occupied
    stack = [seed]
    cavity = {seed}
    while stack:
        for q in grid.edge_neighbors(stack.pop()):
            if q not in occupied and q not in cavity:
                cavity.add(q)
                stack.append(q)
                assert len(cavity) <= 45
    target = shape(key)
    check_shape(tuple(target), grid)
    ident = canonical_form(target, grid, True)
    assert len(cavity) >= 19 and len(cavity & old) == int(overlap)
    assert ident == canonical_form(cavity, grid, True)
    assert (ident == canonical_form(edited, grid, True)) == bool(int(same))
    return chart, old, edited, pieces, cavity


def obstruction(cells):
    rim = {q for p in cells for q in grid.edge_neighbors(p)} - cells
    demands = [p for p in rim if len(cells.intersection(grid.edge_neighbors(p))) >= 2]
    leaves = [p for p in cells if len(cells.intersection(grid.edge_neighbors(p))) == 1]
    if len(demands) > len(leaves):
        return {"notches": sorted(demands), "leaves": sorted(leaves)}


def run():
    assert bank.keys() == origins.keys()
    counts, parents, areas = {}, Counter(), Counter()
    deep, certificates = {}, {}
    for key in bank:
        chart, _, _, _, cavity = reconstruct(key)
        parents[chart["attempt"]] += 1
        areas[len(cavity)] += 1
        result = obstruction(shape(key))
        if result:
            certificates[key] = result
    for name, depth in [("three", 3), ("four", 4), ("five", 5),
                        ("retry-three", 3), ("retry-five", 5)]:
        rows = [r.split() for r in (here / f"{name}.tsv").read_text().splitlines()]
        if not name.startswith("retry"):
            assert len(rows) == len(bank) and {r[0] for r in rows} == bank.keys()
        counts[name] = Counter(r[1] for r in rows)
        for k, status, *_ in rows:
            if status in ("FOUND", "TIMEOUT"):
                result = deep.setdefault(k, {})
                if status == "FOUND":
                    w = verify_witness((here / name / f"{k}.d{depth}.heesch").read_text())
                    assert w.result.hc_verified == depth and frozenset(w.submission.cells) == shape(k)
                    result[name] = {"copies": w.result.patch_size, "rings": Counter(w.hc_corona.levels)}
                else:
                    result[name] = status
    for row in (here / "period12.tsv").read_text().splitlines():
        k, status, *args = row.split()
        if status == "UNKNOWN":
            continue
        assert status == "TILER" and k not in certificates
        copies, a, b, c = map(int, args[:4])
        cover = Counter()
        for pose in args[4:]:
            t = Xform(*map(int, pose.split(",")))
            check_symmetry(t, grid, True)
            for x, y in t.apply_all(shape(k)):
                u, kx = divmod(x, 3)
                v, ky = divmod(y, 3)
                assert kx == ky in (0, 1)
                q, r = divmod(v, c)
                cover[(u - q*b) % a, r, kx] += 1
        assert copies == len(args[4:]) and copies * len(shape(k)) == 2*a*c
        assert cover == Counter((u, v, kx) for u in range(a) for v in range(c) for kx in (0, 1))
        deep[k]["period"] = {"copies": copies, "translation_basis": [[3*a, 0], [3*b, 3*c]]}
    report = {"size": len(bank), "parents": parents, "areas": areas, "screens": counts,
              "deep": deep, "local_nontilers": certificates}
    (here / "audit.json").write_text(json.dumps(report, separators=(",", ":")) + "\n")
    print(len(bank), "reconstructed,", len(certificates), "notch-count non-tilers,",
          sum("period" in d for d in deep.values()), "independent periodic certificates", flush=True)


if __name__ == "__main__":
    run()
