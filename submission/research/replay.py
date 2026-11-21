"""Replay all geometry and companion results from the submitted archive."""
from collections import Counter
from pathlib import Path
import json
import runpy

from heesch_verify import GRIDS, verify_witness
from heesch_verify.defect import verify_defect

HERE = Path(__file__).resolve().parent


def primary():
    w = verify_witness((HERE.parent / "best.heesch").read_text())
    s = w.submission
    d = verify_defect(frozenset(s.cells), s.grid, w.hc_corona, s.defect, w.contact)
    assert w.result.canonical_digest == "fdb7b9acc85977c73b2d77a49047873e1dab745ab9f326e1d0d18e88e91045ce"
    assert Counter(layer for layer,_ in s.patches[0]) == dict(enumerate((1,5,10,19,27)))
    assert (d.required,d.defect_hh,d.defect_hc,d.pocket_cells,d.partial_tiles) == (152,7,7,0,30)
    assert s.proof and s.proof.m == 5
    print("13-hex: 4 full rings, 145/152 fifth-ring sites, no additional pocket cells")


def staggered_tooth():
    p = HERE / "staggered-teeth"
    w = verify_witness((p/"eight-copy.heesch").read_text())
    assert w.result.hc_verified == 5
    assert Counter(layer for layer,_ in w.submission.patches[0]) == dict(enumerate((1,7,13,20,27,34)))
    record = json.loads((p/"eight-copy-period.json").read_text())
    a,b,c = record["hnf"]
    assert (a,b,c) == (80,18,2) and record["k"] == len(record["tiles"]) == 8
    residues = Counter()
    for index, dx, dy in record["tiles"]:
        for pt in w.submission.cells:
            x,y = GRIDS["H"].orientations[index].apply(pt)
            q,yy = divmod(y+dy,c)
            residues[((x+dx-b*q)%a,yy)] += 1
    assert residues == {(x,y):1 for x in range(a) for y in range(c)}
    print("Staggered 20-hex: 102-copy five-ring witness; 8-copy period covers 160/160 residues")


if __name__ == "__main__":
    primary()
    staggered_tooth()
    for companion in ["hexapillars","square-companion"]:
        runpy.run_path(str(HERE/companion/"replay.py"),run_name="__main__")
