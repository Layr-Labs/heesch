"""Replay the tile edit and defect. --proof also checks the frozen CNF and DRAT."""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
import lzma
from pathlib import Path
import subprocess
import tempfile

from heesch_verify import verify_witness
from heesch_verify.canonical import canonical_form
from heesch_verify.defect import verify_defect
from heesch_verify.shape import holes_of
from heesch_verify.transform import Xform


def replay(directory, check_proof):
    dest = Path(directory)
    original = verify_witness((dest/"research/parent20.heesch").read_text())
    result = verify_witness((dest/"best.heesch").read_text())
    sub = result.submission
    grid = sub.grid
    tile = frozenset(sub.cells)

    parent = frozenset(original.submission.cells)
    left = {p for p in parent if p[0] <= 4}
    right = parent - left
    child = left | Xform(1, 0, 0, -1, -1, 18).apply_all(right) | {(3, 9), (4, 10)}
    assert (len(left), len(right), len(child)) == (11, 9, 22)
    assert canonical_form(child, grid, True) == canonical_form(tile, grid, True)
    assert original.result.hc_verified == 4
    levels = Counter(l for l, xf in sub.patches[0])
    assert [levels[i] for i in range(4)] == [1, 6, 12, 18]
    assert result.result.hc_verified == result.result.hh_verified == 3

    patch = result.hc_corona.patch_cells
    boundary = {q for p in patch for q in grid.point_neighbors(p)} - patch
    filled = set()
    for level, motion in sub.defect.tiles:
        copy = motion.apply_all(tile)
        assert level == 4 and copy & boundary and not copy & filled and not copy & patch
        filled.update(copy)
    gaps = boundary - filled
    pockets = holes_of(patch | filled, grid) - boundary
    measured = verify_defect(tile, grid, result.hc_corona, sub.defect, result.contact)
    assert (len(boundary), len(gaps), len(pockets), len(sub.defect.tiles)) == (209,12,4,24)
    assert (measured.defect_hh, measured.defect_hc) == (len(gaps), len(gaps | pockets))

    proof = sub.proof
    stored = (dest/proof.file_name).read_bytes()
    decoded = lzma.decompress(stored)
    assert proof.m == 4 and proof.num_vars == 550371 and proof.num_clauses == 3004341
    assert hashlib.sha256(decoded).hexdigest() == proof.payload_sha256
    assert len(stored) == 140004 and len(decoded) == 691017
    scalar = 3 + Fraction(len(boundary) - len(gaps | pockets), len(boundary))
    report = {"area": len(tile), "ring_counts": [levels[i] for i in range(4)],
              "required": len(boundary), "covered": len(boundary) - len(gaps),
              "uncovered": sorted(gaps), "extra_pockets": sorted(pockets),
              "defect_hc": measured.defect_hc, "partial_tiles": len(sub.defect.tiles),
              "score": str(scalar), "cnf_digest": proof.cnf_digest,
              "stored_sha256": hashlib.sha256(stored).hexdigest(),
              "payload_sha256": proof.payload_sha256, "payload_bytes": len(decoded)}
    if check_proof:
        from heesch_encoder.multilevel.api import encode_multilevel_stream
        from heesch_encoder.proofcheck.checkers import checker_path
        checker = checker_path("drat-trim")
        if not checker:
            raise RuntimeError("build or install the benchmark drat-trim checker")
        with tempfile.TemporaryDirectory() as tmp:
            cnf = Path(tmp)/"formula.cnf"
            dat = Path(tmp)/"proof.bin"
            canonical = frozenset(canonical_form(tile, grid, True))
            enc = encode_multilevel_stream(canonical, grid, result.contact, 4, cnf)
            assert (enc.digest, enc.num_vars, enc.num_clauses) == (
                proof.cnf_digest, proof.num_vars, proof.num_clauses)
            dat.write_bytes(decoded)
            proc = subprocess.run([str(checker), str(cnf), str(dat), "-i", "-w"],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if "s VERIFIED" not in (line.strip() for line in proc.stdout.splitlines()):
                raise RuntimeError(proc.stdout[-1600:])
        report["checked_against_regenerated_formula"] = True
    return report


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--proof", action="store_true")
    cli.add_argument("--submission", type=Path, default=Path(__file__).resolve().parents[1])
    args = cli.parse_args()
    print(json.dumps(replay(args.submission, args.proof), indent=2))
