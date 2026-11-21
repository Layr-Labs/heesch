"""Replay the 17-hex geometry and the compressed proof payload."""
from collections import Counter
from fractions import Fraction
from hashlib import file_digest
import json
import lzma
from pathlib import Path

from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of


def main():
    path = Path(__file__).resolve().parents[1] / "best.heesch"
    v = verify_witness(path.read_text())
    s = v.submission
    tile = frozenset(s.cells)
    full = v.hc_corona.patch_cells
    r = required_set(full, v.contact)
    extra = frozenset().union(*(t.apply_all(tile) for _, t in s.defect.tiles))
    gap = r - extra
    holes = holes_of(full | extra, s.grid)
    damage = gap | holes
    verified = verify_defect(tile, s.grid, v.hc_corona, s.defect, v.contact)
    assert len(damage) == verified.defect_hc == len(gap)
    assert v.hc_corona.max_level == v.result.hh_verified == 4
    declared = s.proof
    with lzma.open(path.parent / declared.file_name, "rb") as fh:
        digest = file_digest(fh, "sha256").hexdigest()
    assert digest == declared.payload_sha256
    counts = Counter(level for level, t in s.patches[0])
    print(json.dumps(dict(
        cells=len(tile), ring_tiles=[counts[i] for i in range(5)], partial_tiles=len(s.defect.tiles),
        boundary=len(r), gaps=sorted(gap), additional_holes=sorted(holes-gap),
        score=str(4 + Fraction(len(r)-len(damage), len(r))), proof_depth=declared.m,
        proof_payload_sha256=digest,
    ), indent=2))


if __name__ == "__main__":
    main()
