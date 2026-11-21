"""Exact geometry and proof-payload replay. Run in the benchmark checkout."""
from collections import Counter
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from heesch_verify import GRIDS, Xform, canonical_form, verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.proofgate import materialize_proof
from heesch_verify.profile import STANDARD, RECORD


def main():
    parent_result = verify_witness((HERE / "parent.heesch").read_text())
    parent = frozenset(parent_result.submission.cells)
    record = json.loads((HERE / "construction.json").read_text())
    assert parent == frozenset(map(tuple, record["source"]))
    pose = Xform(*map(int, record["transform"][1:-1].split(",")))
    removed, added = (frozenset(map(tuple, record[key])) for key in ("cut", "added"))
    assert pose.apply_all(removed) == added
    initial, final = parent, (parent - removed) | added
    macro = frozenset(map(tuple, record["macro"]))
    for left in (initial, final):
        right = pose.apply_all(left)
        assert len(left) == len(right) == 18 and not left & right and left | right == macro
    result = verify_witness((HERE.parent / "best.heesch").read_text())
    sub = result.submission
    assert canonical_form(final, GRIDS["H"], True) == canonical_form(sub.cells, sub.grid, True)
    assert result.result.hc_verified == result.result.hh_verified == 3
    assert Counter(level for level, pose in sub.patches[0]) == {0:1, 1:5, 2:10, 3:18}
    damage = verify_defect(sub.cells, sub.grid, result.hc_corona, sub.defect, result.contact)
    assert (damage.required, damage.defect_hh, damage.defect_hc, damage.partial_tiles) == (158, 17, 18, 25)
    print("Two congruent subdivisions of the same 36-hex, three solid rings, 25 partial fourth-ring tiles.")
    print("141/158 sites are covered. The score fraction is 140/158 after charging the additional pocket.")
    proof = sub.proof
    assert proof.m == 4 and proof.num_vars == 785191 and proof.num_clauses == 4935987
    with tempfile.TemporaryDirectory() as scratch:
        for name, compression, expected in ((proof.file_name, proof.compression, proof.payload_sha256),
                                           (proof.core_file, proof.core_compression, proof.core_sha256)):
            size, actual = materialize_proof(HERE.parent / name, Path(scratch) / name, compression)
            assert expected == actual
            assert size <= STANDARD.proof_max_payload_bytes <= RECORD.proof_max_payload_bytes
            print(f"{name}: raw bytes {size}, SHA-256 {actual}")


if __name__ == "__main__":
    main()
