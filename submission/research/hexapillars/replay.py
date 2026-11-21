"""Run from the benchmark root with PYTHONPATH=. python path/to/replay.py."""
from collections import Counter
from pathlib import Path
import json

from heesch_verify import GRIDS, VerifyConfig, verify_witness
from heesch_verify.shape import spans

HERE = Path(__file__).resolve().parent


def replay_patch(name, ring_sizes, cells, minimum_span, config=None):
    checked = verify_witness((HERE / name).read_text(), config=config)
    tile = checked.submission.cells
    grid = checked.submission.grid
    patch = checked.submission.patches[0]
    depths = Counter(depth for depth, _ in patch)
    measured = min(sum(spans([ori.apply(c) for c in tile], grid))
                   for ori in grid.orientations)
    assert checked.result.hc_verified == checked.result.hh_verified == 5
    assert len(tile) == cells and measured == minimum_span
    assert depths == dict(enumerate(ring_sizes))
    print(f'{name}  cells={cells}  min_span={measured}  rings={ring_sizes}  copies={len(patch)}')
    return tile


def replay_period(cells):
    record = json.loads((HERE / '18-iamond-period.json').read_text())
    a, b, c = record['hnf']
    assert (a, b, c) == (18, 6, 6)
    assert record['k'] == len(record['transforms']) == 12
    grid = GRIDS['I']
    counts = Counter()
    for orientation, dx, dy in record['transforms']:
        assert 0 <= orientation < len(grid.orientations)
        assert grid.translation_legal(dx, dy)
        for cell in cells:
            x, y = grid.orientations[orientation].apply(cell)
            x, y = x + dx, y + dy
            side = x % 3
            assert side == y % 3 and side in (0, 1)
            u, v = (x - side) // 3, (y - side) // 3
            wraps, rv = divmod(v, c)
            ru = (u - wraps * b) % a
            counts[ru, rv, side] += 1
    fundamental_domain = {(u, v, side) for u in range(a)
                          for v in range(c) for side in (0, 1)}
    assert set(counts) == fundamental_domain
    assert all(multiplicity == 1 for multiplicity in counts.values())
    print(f'18-iamond period  copies=12  triangle_residues={len(counts)}  multiplicity=1')


if __name__ == '__main__':
    replay_patch('mann-four-pillar.heesch', [1, 5, 11, 23, 34, 47], 215, 92,
                 VerifyConfig(max_cells=215, max_span_sum=117))
    tile = replay_patch('18-iamond.heesch', [1, 6, 15, 22, 29, 40], 18, 20)
    replay_period(tile)
