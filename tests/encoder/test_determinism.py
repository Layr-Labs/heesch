"""§9.6 determinism (E6): byte-identical CNF regeneration under randomized
hash seeds, in fresh subprocesses (PYTHONHASHSEED only takes effect at
interpreter start — in-process tests of this are vacuous).

Golden digests are committed in golden/digests.json; the CI matrix
(ubuntu + windows, two Python minors) asserts against the SAME goldens."""

import json
import pathlib
import random
import subprocess
import sys

import pytest

from conftest import FIXTURES, ROOT

GOLDEN = pathlib.Path(__file__).parent / "golden" / "digests.json"

_CHILD = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from heesch_verify.grids import GRIDS
from heesch_verify.patch import check_corona
from heesch_verify.transform import Xform
from heesch_encoder.api import encode

spec = json.loads(sys.stdin.read())
grid = GRIDS[spec["grid"]]
contact = grid.contact("point")
tile = frozenset(tuple(c) for c in spec["cells"])
placements = [(lvl, Xform(*xf)) for lvl, xf in spec["placements"]]
corona = check_corona(tile, placements, grid, contact, hole_mode="hc")
enc = encode(tile, corona.patch_cells, grid, contact)
print(enc.digest)
"""


def _digest_in_subprocess(name, gid, cells, placements, seed):
    spec = json.dumps({
        "grid": gid,
        "cells": [list(c) for c in cells],
        "placements": [[lvl, [xf.a, xf.b, xf.c, xf.d, xf.e, xf.f]] for lvl, xf in placements],
    })
    proc = subprocess.run(
        [sys.executable, "-I", "-c", _CHILD, str(ROOT)],
        input=spec, capture_output=True, text=True, timeout=300,
        env={"PYTHONHASHSEED": str(seed), "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")},
    )
    assert proc.returncode == 0, f"{name}: child failed:\n{proc.stderr[-2000:]}"
    return proc.stdout.strip()


SEEDS = [0, 1, 42, random.SystemRandom().randrange(2**32)]


@pytest.mark.parametrize("name,gid,cells,placements",
                         FIXTURES, ids=[f[0] for f in FIXTURES])
def test_digest_stable_across_hash_seeds(name, gid, cells, placements):
    digests = {
        _digest_in_subprocess(name, gid, cells, placements, seed) for seed in SEEDS
    }
    assert len(digests) == 1, f"{name}: hash-seed-dependent output! {digests}"

    digest = digests.pop()
    goldens = json.loads(GOLDEN.read_text()) if GOLDEN.exists() else {}
    if name in goldens:
        assert digest == goldens[name], (
            f"{name}: digest drifted from committed golden — any change to "
            "ordering, clause schema or emission is a new revision"
        )
    else:
        # First run records the golden; commit the file.
        goldens[name] = digest
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(goldens, indent=2, sort_keys=True) + "\n")
