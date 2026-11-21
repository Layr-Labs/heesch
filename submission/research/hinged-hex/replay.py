"""Check the 17-to-18-hex edit, its 107-copy patch and its 6-copy repeating unit."""
from collections import Counter
import json
from pathlib import Path
from heesch_verify import GRIDS, verify_witness
from heesch_verify.canonical import canonical_form

HERE = Path(__file__).resolve().parent
GRID = GRIDS['H']


def connected_components(cells):
    todo = set(cells)
    while todo:
        first = todo.pop()
        part, queue = {first}, [first]
        while queue:
            for q in GRID.edge_neighbors(queue.pop()):
                if q in todo:
                    todo.remove(q)
                    part.add(q)
                    queue.append(q)
        yield part


def pivot(cells, hinge, orientation):
    px, py = hinge
    motion = GRID.orientations[orientation]
    rotated = (motion.apply((x-px, y-py)) for x, y in cells)
    return {(px+x, py+y) for x, y in rotated}


def main():
    study = json.loads((HERE/'hinge.json').read_text())
    parent = {tuple(p) for p in study['parent']['shape']}
    edit = study['edit']
    neck = {tuple(p) for p in edit['neck']}
    parts = sorted(connected_components(parent-neck), key=lambda s: (-len(s), sorted(s)))
    child = set.union(neck, *parts[2:])
    child |= pivot(parts[0], edit['ax'], edit['i'])
    child |= pivot(parts[1], edit['bx'], edit['j'])
    child.update(tuple(p) for p in edit['tabs'])
    witness = verify_witness((HERE/'five.heesch').read_text())
    shape = witness.submission.cells
    assert (len(parent), len(child)) == (17, 18)
    assert canonical_form(child, GRID, True) == canonical_form(shape, GRID, True)
    assert witness.result.hc_verified == witness.result.hh_verified == 5
    rings = Counter(level for level, pose in witness.submission.patches[0])
    assert [rings[k] for k in range(6)] == [1, 7, 14, 21, 28, 36]
    period = study['period']
    a,b,c = period['hnf']
    assert a*c == period['k']*len(shape) == 108
    counts = Counter()
    for orientation, dx, dy in period['tiles']:
        for site in shape:
            x,y = GRID.orientations[orientation].apply(site)
            quotient, ry = divmod(y+dy, c)
            counts[((x+dx-quotient*b) % a, ry)] += 1
    assert counts == Counter((x,y) for x in range(a) for y in range(c))
    print('Verified 107 copies in five rings and a six-copy tiling of 108 residues.')


if __name__ == '__main__':
    main()
