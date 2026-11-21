"""Replay the outline edit, the five complete rings, and the four-copy tiling."""
from collections import Counter
import json
from pathlib import Path

from heesch_verify import verify_witness
from heesch_verify.canonical import canonical_form
from heesch_verify.transform import Xform, check_symmetry


def main():
    here = Path(__file__).resolve().parent
    parent = verify_witness((here.parent/"parent20.heesch").read_text())
    witness = verify_witness((here/"five.heesch").read_text())
    cert = json.loads((here/"period.json").read_text())
    grid = witness.submission.grid
    tile = frozenset(witness.submission.cells)
    original = frozenset(parent.submission.cells)
    cut = {tuple(p) for p in cert["remove_from_parent20"]}
    added = {tuple(p) for p in cert["add_to_parent20"]}
    assert len(cut) == 2 and cut <= original
    assert len(added) == 5 and added.isdisjoint(original)
    child = (original - cut) | added
    assert canonical_form(child, grid, True) == canonical_form(tile, grid, True)
    assert cert["area_triangles"] == len(tile) == 23
    assert witness.result.hc_verified == witness.result.hh_verified == 5
    counts = Counter(level for level, xf in witness.submission.patches[0])
    rings = [counts[level] for level in range(6)]
    assert rings == [1, 6, 12, 18, 24, 30]

    (a, zero), (b, c) = cert["period_vectors_in_paired_triangle_coordinates"]
    motions = [Xform(*row) for row in cert["affine_motions_in_witness_coordinates"]]
    assert zero == 0 and a > 0 and c > 0 and 0 <= b < a
    covered = Counter()
    for motion in motions:
        check_symmetry(motion, grid, allow_reflections=True)
        for x, y in motion.apply_all(tile):
            u, kind = divmod(x, 3)
            v, other = divmod(y, 3)
            assert kind == other and kind in (0, 1)
            bands, reduced_v = divmod(v, c)
            reduced_u = (u - bands*b) % a
            covered[(reduced_u, reduced_v, kind)] += 1
    expected = Counter((u, v, kind) for u in range(a) for v in range(c) for kind in (0, 1))
    assert covered == expected and len(covered) == 2*a*c == 92
    print(json.dumps({"area_triangles": len(tile), "ring_sizes": rings,
                      "periodic_copies": len(motions), "triangle_residues_covered_once": len(covered),
                      "period_vectors_in_paired_triangle_coordinates": [[a, 0], [b, c]]}, indent=2))


if __name__ == "__main__":
    main()
