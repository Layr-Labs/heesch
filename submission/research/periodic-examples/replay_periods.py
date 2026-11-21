"""Check the geometric witnesses and plane-tiling certificates in this folder."""
from collections import Counter
import json
from pathlib import Path

from heesch_verify import verify_witness
from heesch_verify.transform import Xform


def replay(case, directory):
    witness = verify_witness((directory / case["witness"]).read_text())
    rings = Counter(level for level, _ in witness.submission.patches[0])
    assert witness.hc_corona.max_level == 5
    assert [rings[i] for i in range(6)] == case["ring_tiles"]
    a, b, c = case["hnf"]
    assert a > 0 and c > 0 and 0 <= b < a
    orientations = witness.submission.grid.orientations
    allowed = {(t.a,t.b,t.d,t.e) for t in orientations}
    coverage = Counter()
    for matrix in case["transforms"]:
        t = Xform(*matrix)
        assert (t.a,t.b,t.d,t.e) in allowed
        for x, y in t.apply_all(witness.submission.cells):
            winding, reduced_y = divmod(y, c)
            coverage[(x-b*winding) % a, reduced_y] += 1
    assert coverage == {(x, y): 1 for x in range(a) for y in range(c)}
    print(f'{case["witness"]}: {sum(rings.values())} patch tiles, '
          f'{len(case["transforms"])} copies per period, {a*c} residues covered once')


if __name__ == "__main__":
    directory = Path(__file__).resolve().parent
    for case in json.loads((directory / "periods.json").read_text()):
        replay(case, directory)
