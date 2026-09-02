"""v2 determinism (M9): universe serialization AND full-CNF digests are
byte-identical across fresh subprocesses with randomized PYTHONHASHSEED,
against committed goldens (same CI-matrix contract as v1)."""

import json
import os
import pathlib
import random
import subprocess
import sys

import pytest

from conftest import ROOT

GOLDEN = pathlib.Path(__file__).parent / "golden" / "ml_digests.json"

_CHILD = r"""
import hashlib, json, sys
sys.path.insert(0, sys.argv[1])
from heesch_verify.grids import GRIDS
from heesch_encoder.multilevel.api import encode_multilevel
from heesch_encoder.multilevel.universe import multilevel_universe

spec = json.loads(sys.stdin.read())
grid = GRIDS[spec["grid"]]
contact = grid.contact("point")
tile = frozenset(tuple(c) for c in spec["cells"])
m = spec["m"]

uni = multilevel_universe(tile, grid, contact, m)
uni_ser = "\n".join(
    f"{l} {p.symmetry_index} {p.ty} {p.tx}"
    for l, lv in enumerate(uni.levels, start=1) for p in lv
)
enc = encode_multilevel(tile, grid, contact, m)
print(hashlib.sha256(uni_ser.encode()).hexdigest(), enc.digest)
"""

ML_DET_FIXTURES = [
    ("mono-m2", "O", [(0, 0)], 2),
    ("domino-m2", "O", [(0, 0), (1, 0)], 2),
    ("T-m2", "O", [(0, 0), (1, 0), (2, 0), (1, 1)], 2),
    ("slotblock-m1", "O",
     [(x, y) for x in range(5) for y in range(3) if (x, y) not in ((2, 1), (2, 2))],
     1),
    ("hex1-m2", "H", [(0, 0)], 2),
    ("hexprop-m2", "H", [(0, 0), (1, 0), (-1, 1), (0, -1)], 2),
    ("iam2-m2", "I", [(0, 0), (1, 1)], 2),
]

SEEDS = [0, 1, 42, random.SystemRandom().randrange(2**32)]


def _digests(name, gid, cells, m, seed):
    spec = json.dumps({"grid": gid, "cells": [list(c) for c in cells], "m": m})
    proc = subprocess.run(
        [sys.executable, "-I", "-c", _CHILD, str(ROOT)],
        input=spec, capture_output=True, text=True, timeout=600,
        env={"PYTHONHASHSEED": str(seed),
             "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")},
    )
    assert proc.returncode == 0, f"{name}: child failed:\n{proc.stderr[-2000:]}"
    uni_d, cnf_d = proc.stdout.split()
    return uni_d, cnf_d


@pytest.mark.parametrize("name,gid,cells,m", ML_DET_FIXTURES,
                         ids=[f[0] for f in ML_DET_FIXTURES])
def test_v2_digests_stable_across_hash_seeds(name, gid, cells, m):
    results = {_digests(name, gid, cells, m, seed) for seed in SEEDS}
    assert len(results) == 1, f"{name}: hash-seed-dependent output! {results}"
    uni_d, cnf_d = results.pop()

    goldens = json.loads(GOLDEN.read_text()) if GOLDEN.exists() else {}
    if name in goldens:
        assert [uni_d, cnf_d] == goldens[name], (
            f"{name}: digest drifted from committed golden — any v2 schema "
            "change is a new revision"
        )
    else:
        goldens[name] = [uni_d, cnf_d]
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(goldens, indent=2, sort_keys=True) + "\n")
