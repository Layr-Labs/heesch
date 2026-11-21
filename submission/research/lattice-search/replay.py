"""Verify the stored five-ring witnesses and all periodic partitions."""
from collections import Counter
from pathlib import Path
import json

from heesch_verify import verify_witness
from heesch_verify.grids import GRIDS


def main():
    directory = Path(__file__).resolve().parent
    cases = json.loads((directory / "periodic-certificates.json").read_text())
    shapes = {}
    for line in (directory / "shapes.tsv").read_text().splitlines():
        identifier, grid_id, *coordinates = line.split()
        assert grid_id == "H?"
        numbers = list(map(int, coordinates))
        shapes[identifier] = frozenset(zip(numbers[::2], numbers[1::2]))
    witnesses = 0
    for identifier, cert in cases.items():
        witness = directory / "witnesses" / f"{identifier}.d5.heesch"
        if witness.is_file():
            verified = verify_witness(witness.read_text())
            assert frozenset(verified.submission.cells) == shapes[identifier]
            assert verified.hc_corona.max_level == 5
            witnesses += 1
        a, b, c = cert["hnf"]
        assert a > 0 and c > 0 and 0 <= b < a
        assert cert["status"] == "TILER" and cert["k"] == len(cert["tiles"])
        coverage = Counter()
        for orient, tx, ty in cert["tiles"]:
            t = GRIDS["H"].orientations[orient]
            for pt in shapes[identifier]:
                x, y = t.apply(pt)
                q, ry = divmod(y + ty, c)
                coverage[(x + tx - b*q) % a, ry] += 1
        assert coverage == {(x, y): 1 for x in range(a) for y in range(c)}
    print(f"{witnesses} five-ring witnesses, {len(cases)} periodic partitions verified.")


if __name__ == "__main__":
    main()
