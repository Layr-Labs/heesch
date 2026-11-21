"""Independently test whether a charged fourth-ring defect of 17 is attainable."""
from pathlib import Path
from random import Random
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from pocket_pack import pack
from greedy_method import greedy
from placements import enumerate_tiles
from heesch_verify import required_set, verify_witness


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as scratch:
        result = verify_witness((HERE / "three-ring.heesch").read_text())
        sub = result.submission
        region = result.hc_corona.patch_cells
        required = required_set(region, result.contact)
        placements = enumerate_tiles(frozenset(sub.cells), sub.grid, region, required)
        rng = Random(776519)
        best = min(greedy(sub.grid, region, required, placements, [], rng)[1]
                   for trial in range(8))
        assert best == 24 and len(placements) == 1746
        # The initial feasible bound is independently archived in greedy.heesch.
        # Keep the tested witness free of the proof block when materializing
        # alternate defect blocks. A strictly better packing would be written
        # to the temporary output file for inspection.
        target = Path(scratch) / "better.heesch"
        pack(HERE / "greedy.heesch", target, 17, 90)
        if target.exists():
            raise SystemExit("A packing with charged defect at most 17 was found.")
