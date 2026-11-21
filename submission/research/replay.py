"""Replay the archive from its research directory without network access."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from pack import Packing,write_candidate

ROOT=Path(__file__).resolve().parent


def check():
    w=verify_witness((ROOT.parent/"best.heesch").read_text())
    shape=frozenset(w.submission.cells)
    d=verify_defect(shape,w.submission.grid,w.hc_corona,w.submission.defect,w.contact)
    assert (w.hc_corona.max_level,d.defect_hc,d.required,d.partial_tiles)==(4,3,254,42)
    base=verify_witness((ROOT/"original-second/source-four.heesch").read_text())
    def occupancy(w,depth):
        return frozenset().union(*(t.apply_all(shape) for l,t in w.submission.patches[0] if l<=depth))
    p1=occupancy(base,1)
    p2=occupancy(base,2)
    records=json.loads((ROOT/"changed-second-results.json").read_text())
    seen_p2=set()
    viable=Counter()
    for key,record in records.items():
        witness=verify_witness((ROOT/"second-rings"/f"{key}.heesch").read_text())
        assert witness.hc_corona.max_level==3 and occupancy(witness,1)==p1
        branch=occupancy(witness,2)
        assert len(branch^p2)==record["difference"] and branch not in seen_p2 and branch!=p2
        seen_p2.add(branch)
        assert record["enumeration"][-1]["status"]=="INFEASIBLE"
        seen_p3=set()
        for name,child in record["third_rings"].items():
            deeper=verify_witness((ROOT/"third-rings"/f"{name}.heesch").read_text())
            assert deeper.hc_corona.max_level==4 and occupancy(deeper,2)==branch
            now=occupancy(deeper,3)
            assert now not in seen_p3
            seen_p3.add(now)
            assert child["strict"][-1]["status"]=="INFEASIBLE"
            viable[key]+=1
    assert len(seen_p2)==27 and len(viable)==5 and sum(viable.values())==19
    print("Verified 27 changed second-ring footprints, 19 viable third-ring branches, and the equality witness.")


def strict_run(directory):
    records=json.loads((ROOT/"changed-second-results.json").read_text())
    for record in records.values():
        for name,child in record["third_rings"].items():
            f=ROOT/"third-rings"/f"{name}.heesch"
            cmd=[sys.executable,str(ROOT/"boundary_bound.py"),str(f),"--seconds","30","--workers","3"]
            b=json.loads(subprocess.check_output(cmd,text=True))
            cmd=[sys.executable,str(ROOT/"joint.py"),"--source",str(f),"--target","1","--boundary-max",
                str(b["upper_bound"]),"--damage-max",str(b["max_damage"]),"--seconds","90","--workers","3",
                "--geometry-only","--output",str(directory/f"{name}.heesch")]
            last=json.loads(subprocess.check_output(cmd,text=True).splitlines()[-1])
            print(name,b["upper_bound"],last["status"],flush=True)
            assert last["status"]=="INFEASIBLE" and b["upper_bound"]==child["bound"]["upper_bound"]


def equality_run(directory):
    source=ROOT/"original-second/source-four.heesch"
    text=source.read_text()
    w=verify_witness(text)
    earlier=verify_witness((ROOT/"attempt02.heesch").read_text())
    cells=frozenset(w.submission.cells)
    prior={t.apply_all(cells) for _,t in earlier.submission.defect.tiles}
    promoted={t.apply_all(cells) for _,t in w.submission.defect.tiles}
    p=Packing(w.submission.grid,cells,w.hc_corona.patch_cells,w.contact,3,42)
    p.model.add(sum(v for v,t in zip(p.select,p.items) if t.cells in prior)<=41)
    p.model.minimize(sum(v for v,t in zip(p.select,p.items) if t.cells in promoted))
    p.add_hint(prior)
    picked,stats=p.solve(time.monotonic()+35,3,14701)
    assert picked is not None
    report=write_candidate(directory/"tie.heesch",text.splitlines()[0],w.submission.patches[0],
                           picked,source,stats,copy_proof=False)
    print(json.dumps(report),flush=True)


if __name__=="__main__":
    cli=ArgumentParser()
    cli.add_argument("--strict",action="store_true")
    cli.add_argument("--equality",action="store_true")
    opt=cli.parse_args()
    check()
    with tempfile.TemporaryDirectory() as tmp:
        if opt.strict: strict_run(Path(tmp))
        if opt.equality: equality_run(Path(tmp))
