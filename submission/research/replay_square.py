"""Replay the square witness, its defect accounting, and the stored proof digests.

Run in the cloned benchmark as:
  python submission/research/replay_square.py submission/best.heesch
For the proof kernel, use the benchmark harness on an x86-64 Linux runner.
"""
from collections import Counter
import hashlib
import json
import lzma
from pathlib import Path
import sys

from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main(path):
    raw = path.read_bytes()
    checked = verify_witness(raw.decode("ascii"))
    sub = checked.submission
    shape = frozenset(sub.cells)
    corona = checked.hc_corona
    block = sub.defect
    measured = verify_defect(shape, sub.grid, corona, block, checked.contact)
    required = required_set(corona.patch_cells, checked.contact)
    placed = frozenset().union(*(xf.apply_all(shape) for _, xf in block.tiles))
    uncovered = required - placed
    holes = holes_of(corona.patch_cells | placed, sub.grid)
    assert (measured.defect_hc, measured.defect_hh) == (len(uncovered | holes), len(uncovered))
    patches = []
    for patch in sub.patches:
        counts = Counter(level for level, _ in patch)
        occupied = frozenset().union(*(xf.apply_all(shape) for _, xf in patch))
        patches.append({"ring_tiles": [counts[k] for k in range(max(counts)+1)],
                        "outer_hole_cells": sorted(holes_of(occupied, sub.grid))})
    proof = sub.proof
    artifacts = {}
    for name, expected in ((proof.file_name, proof.payload_sha256),
                            (proof.core_file, proof.core_sha256)):
        compressed = (path.parent/name).read_bytes()
        decompressed = lzma.decompress(compressed)
        actual = digest(decompressed)
        assert actual == expected, (name, expected, actual)
        artifacts[name] = {"stored_bytes":len(compressed), "stored_sha256":digest(compressed),
                           "plain_bytes":len(decompressed), "plain_sha256":actual}
    print(json.dumps({
        "shape": sorted(shape), "witness_sha256": digest(raw),
        "verified_geometry": {"hc":checked.result.hc_verified, "hh":checked.result.hh_verified,
                              "patches":patches},
        "defect": {"required":len(required), "covered":len(required)-len(uncovered),
                   "uncovered":sorted(uncovered), "extra_pockets":sorted(holes-required),
                   "charged":len(uncovered | holes), "partial_tiles":len(block.tiles),
                   "scalar":corona.max_level+(len(required)-len(uncovered | holes))/len(required)},
        "proof": {"m":proof.m,"cnf_digest":proof.cnf_digest,"artifacts":artifacts},
    }, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
