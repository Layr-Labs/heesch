"""PYTHONPATH=. python submission/research/replay.py from the frozen benchmark root."""
from collections import Counter
from pathlib import Path
import json

from heesch_verify import GRIDS, verify_witness
from heesch_verify.canonical import canonical_form
from heesch_verify.defect import verify_defect
from heesch_verify.transform import Xform

HERE = Path(__file__).resolve().parent
GRID = GRIDS['O']


def compressed(cells, xs, ys):
    left = min(x for x, y in cells)
    bottom = min(y for x, y in cells)
    original = {(x - left, y - bottom) for x, y in cells}
    return frozenset((i, j) for i, x in enumerate(xs) for j, y in enumerate(ys)
                     if (x, y) in original)


def check_fit(path, parent, xs, ys):
    checked = verify_witness(path.read_text())
    shape = frozenset(checked.submission.cells)
    assert canonical_form(shape, GRID, True) == canonical_form(compressed(parent, xs, ys), GRID, True)
    defect = verify_defect(shape, GRID, checked.hc_corona, checked.submission.defect, checked.contact)
    counts = Counter(level for level, _ in checked.submission.patches[0])
    assert checked.result.hc_verified == checked.result.hh_verified == 3
    return dict(cells=len(shape), span=checked.result.span_x + checked.result.span_y,
                complete_ring_sizes=[counts[i] for i in range(4)], partial_tiles=defect.partial_tiles,
                required=defect.required, charged_defect=defect.defect_hc, missing_required=defect.defect_hh,
                enclosed_extra=defect.pocket_cells)


def period_replay():
    checked = verify_witness((HERE / 'five-rings.heesch').read_text())
    assert checked.result.hc_verified == checked.result.hh_verified == 5
    obj = json.loads((HERE / 'four-copy-period.json').read_text())
    a, b, c = obj['hnf']
    counts = Counter()
    for row in obj['motions']:
        t = Xform(*map(int, row.strip('<>').split(',')))
        assert GRID.orientation_by_linear(t.linear) is not None
        for x, y in t.apply_all(checked.submission.cells):
            wraps, ty = divmod(y, c)
            counts[(x - wraps * b) % a, ty] += 1
    assert counts == Counter((x, y) for x in range(a) for y in range(c))
    assert a * c == obj['k'] * checked.result.cell_count
    return dict(cells=checked.result.cell_count, copies=len(checked.submission.patches[0]),
                period_copies=obj['k'], square_residues=len(counts), hnf=obj['hnf'])


if __name__ == '__main__':
    parent = verify_witness((HERE / 'parent-polypillar.heesch').read_text()).submission.cells
    small = check_fit(HERE.parent / 'best.heesch', parent,
                      [0, 2, 4, 6, 7, 8, 9, 12, 15, 19], [0, 1, 2, 5])
    large = check_fit(HERE / '38-square.heesch', parent,
                      [0, 2, 3, 6, 7, 9, 11, 12, 14, 16, 17, 18, 19], [0, 1, 2, 5])
    actual = dict(scored_shape=small, second_compression=large, periodic_example=period_replay())
    print(json.dumps(actual, indent=2))
