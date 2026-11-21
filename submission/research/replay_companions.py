"""Verify the archived alternate packing and five-ring periodic example."""
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path

from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect


def replay(directory):
    alternate = verify_witness((directory / "alternate-fourth.heesch").read_text())
    defect = verify_defect(frozenset(alternate.submission.cells), alternate.submission.grid,
                           alternate.hc_corona, alternate.submission.defect, alternate.contact)
    if (alternate.hc_corona.max_level, defect.defect_hc, defect.required,
            defect.partial_tiles) != (4, 3, 253, 43):
        raise ValueError("Alternate packing metrics differ from the archived result")

    witness = verify_witness((directory / "periodic-five.heesch").read_text())
    ring_sizes = Counter(level for level, _ in witness.submission.patches[0])
    if witness.hc_corona.max_level != 5 or list(sorted(ring_sizes.items())) != list(
            enumerate([1, 6, 12, 18, 24, 30])):
        raise ValueError("Five-ring witness differs from the archived result")
    cert = json.loads((directory / "periodic-certificate.json").read_text())
    a, b, c = cert["hnf"]
    if not (a > 0 and c > 0 and 0 <= b < a):
        raise ValueError("Invalid lattice basis")
    coverage = Counter()
    for orient, tx, ty in cert["tiles"]:
        transform = witness.submission.grid.orientations[orient]
        for cell in witness.submission.cells:
            x, y = transform.apply(cell)
            periods, y = divmod(y + ty, c)
            coverage[(x + tx - b * periods) % a, y] += 1
    if coverage != {(x, y): 1 for x in range(a) for y in range(c)}:
        raise ValueError("Period has gaps or overlaps")
    print(json.dumps({"alternate": asdict(defect), "ring_sizes": dict(ring_sizes),
                      "tiles_per_period": len(cert["tiles"]), "cells_per_period": a * c}))


if __name__ == "__main__":
    replay(Path(__file__).resolve().parent)
