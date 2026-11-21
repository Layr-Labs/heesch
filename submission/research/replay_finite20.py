"""Replay Attempt 06 geometry, defect and source certificate payload digests."""
from collections import Counter
from fractions import Fraction
import hashlib
import json
import lzma
from pathlib import Path
import sys

from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of


def replay(path):
    outcome = verify_witness(path.read_text())
    submission = outcome.submission
    cells = frozenset(submission.cells)
    levels = Counter(level for level, _ in submission.patches[0])
    assert len(cells) == 20 and outcome.hc_corona.max_level == 4
    assert not outcome.hc_corona.has_outer_holes
    assert sorted(levels.items()) == list(enumerate([1, 5, 12, 24, 28]))
    measured = verify_defect(cells, submission.grid, outcome.hc_corona,
                             submission.defect, outcome.contact)
    patch = outcome.hc_corona.patch_cells
    copies = [t.apply_all(cells) for _, t in submission.defect.tiles]
    ring = frozenset().union(*copies)
    required = required_set(patch, outcome.contact)
    gaps = required - ring
    secondary = holes_of(patch | ring, submission.grid) - gaps
    assert len(ring) == sum(map(len, copies)) and patch.isdisjoint(ring)
    assert (len(required), len(gaps), len(secondary), len(copies)) == (231, 9, 1, 36)
    assert measured.defect_hc == 10 and measured.defect_hh == 9
    proof = submission.proof
    assert (proof.m, proof.core_clauses, proof.num_vars, proof.num_clauses) == (
        5, 478114, 1837892, 17508765)
    for name, digest in ((proof.file_name, proof.payload_sha256),
                         (proof.core_file, proof.core_sha256)):
        with lzma.open(path.parent / name, 'rb') as stream:
            payload_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
        assert payload_sha == digest
    exact = 4 + Fraction(len(required) - measured.defect_hc, len(required))
    return {'full_tiles': sum(levels.values()), 'partial_tiles': len(copies),
            'required': len(required), 'gaps': sorted(gaps), 'extra_pocket_cells': sorted(secondary),
            'defect_hc': measured.defect_hc, 'defect_hh': measured.defect_hh,
            'conditional_score_fraction': str(exact), 'conditional_score_decimal': float(exact)}


if __name__ == '__main__':
    file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'best.heesch'
    print(json.dumps(replay(file), sort_keys=True))
