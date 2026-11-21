"""Replay the construction with the challenge verifier at its default bounds."""
from collections import Counter
import json
from pathlib import Path

from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.shape import holes_of


def main():
    source = Path(__file__).with_name("polypillar.heesch")
    verified = verify_witness(source.read_text(encoding="ascii"))
    sub = verified.submission
    assert sub.grid_id == "O" and len(sub.patches) == 1
    shape = frozenset(sub.cells)
    top_markers = [2, 7, 12, 17]
    expected_shape = {(x, y) for x in range(20) for y in range(5)}
    expected_shape -= {(x, 0) for x in top_markers} | {(19, 2)}
    expected_shape |= {(x, 5) for x in top_markers}
    assert shape == expected_shape and len(shape) == 99

    adjacent = lambda p: set(sub.grid.edge_neighbors(p))
    external = {q for p in shape for q in adjacent(p)} - shape
    notches = sorted(q for q in external if len(adjacent(q) & shape) == 3)
    leaves = sorted(p for p in shape if len(adjacent(p) & shape) == 1)
    assert notches == [(2, 0), (7, 0), (12, 0), (17, 0), (19, 2)]
    assert leaves == [(2, 5), (7, 5), (12, 5), (17, 5)]

    assert verified.result.hc_verified == verified.result.hh_verified == 3
    levels = Counter(level for level, xf in sub.patches[0])
    assert [levels[level] for level in range(4)] == [1, 7, 14, 26]
    measured = verify_defect(shape, sub.grid, verified.hc_corona, sub.defect, verified.contact)
    patch = set(verified.hc_corona.patch_cells)
    required = {q for p in patch for q in sub.grid.point_neighbors(p)} - patch
    used = set()
    for level, transform in sub.defect.tiles:
        moved = transform.apply_all(shape)
        assert level == 4 and used.isdisjoint(moved) and patch.isdisjoint(moved)
        assert required & moved
        used.update(moved)
    gaps = required - used
    pockets = holes_of(patch | used, sub.grid) - required
    assert (len(required), len(gaps), len(pockets), len(sub.defect.tiles)) == (576, 32, 11, 39)
    assert (measured.defect_hh, measured.defect_hc, measured.pocket_cells) == (
        len(gaps), len(gaps | pockets), len(pockets))
    print(json.dumps({
        "area": len(shape), "complete_ring_sizes": [levels[k] for k in range(4)],
        "notches": notches, "leaves": leaves, "partial_fourth_ring_tiles": len(sub.defect.tiles),
        "required_squares": len(required), "covered_squares": len(required - gaps),
        "uncovered_squares": len(gaps), "extra_pocket_squares": len(pockets),
        "charged_defects": measured.defect_hc
    }, indent=2))


if __name__ == "__main__":
    main()
