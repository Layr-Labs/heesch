"""Check five rings and periodic tilings, plus the parent's fixed placements."""
import json
from collections import Counter
from pathlib import Path

from heesch_verify import verify_witness
from heesch_verify.canonical import canonical_form
from heesch_verify.grids import GRIDS

BASE = Path(__file__).resolve().parent


def residue_counts(cells, cert):
    a, b, c = cert["hnf"]
    grid = GRIDS["H"]
    out = Counter()
    for orientation, tx, ty in cert["tiles"]:
        for p in cells:
            x, y = grid.orientations[orientation].apply(p)
            turns, ry = divmod(y + ty, c)
            out[(x + tx - b * turns) % a, ry] += 1
    return out


def main():
    parent = verify_witness((BASE / "parent.heesch").read_text())
    parent_shape = frozenset(parent.submission.cells)
    parent_period = json.loads((BASE / "parent-period.json").read_text())
    periods = {p["id"]: p for l in (BASE / "periods.jsonl").read_text().splitlines()
               if (p := json.loads(l))}
    moves = {p["id"]: p for l in (BASE / "moves.jsonl").read_text().splitlines()
             if (p := json.loads(l))["id"] in periods}
    found = {r[0] for l in (BASE / "star5.tsv").read_text().splitlines()
             if (r := l.split())[1] == "FOUND"}
    results = []
    for key in sorted(found):
        cert = periods[key]
        patch = verify_witness((BASE / "patch5" / f"{key}.d5.heesch").read_text())
        assert patch.hc_corona.max_level == 5
        a, b, c = cert["hnf"]
        assert residue_counts(patch.submission.cells, cert) == {(x, y): 1 for x in range(a) for y in range(c)}
        move = moves[key]
        cells = (parent_shape - set(map(tuple, move["removed"]))) | set(map(tuple, move["added"]))
        assert canonical_form(cells, GRIDS["H"], True) == tuple(sorted(patch.submission.cells))
        cover = residue_counts(cells, parent_period)
        pa, _, pc = parent_period["hnf"]
        assert move["parent_period_missing"] == pa * pc - len(cover)
        assert move["parent_period_overlapped"] == sum(n - 1 for n in cover.values())
        results.append(dict(**move, cells=len(cells), ring_tiles=[sum(level == i for level, _ in
                            patch.submission.patches[0]) for i in range(6)], period=cert["hnf"], copies=cert["k"]))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
