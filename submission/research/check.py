"""Check the geometry, distinct footprints, logged bounds and inherited certificate payload."""
from collections import Counter
from hashlib import sha256
from pathlib import Path
import json
import lzma

from heesch_verify import verify_witness
from heesch_verify.canonical import canonical_digest
from heesch_verify.defect import verify_defect

ROOT = Path(__file__).resolve().parent


def measure(p):
    w=verify_witness(p.read_text())
    shape=frozenset(w.submission.cells)
    d=verify_defect(shape,w.submission.grid,w.hc_corona,w.submission.defect,w.contact)
    return w,dict(damage=d.defect_hc,uncovered=d.defect_hh,required=d.required,
                  partial=d.partial_tiles,levels=dict(Counter(l for l,t in w.submission.patches[0])))


def replay():
    record=json.loads((ROOT/"census.json").read_text())
    w,metrics=measure(ROOT.parent/"best.heesch")
    src,old=measure(ROOT/"earlier.heesch")
    assert w.result.hc_verified==4 and w.result.canonical_digest==src.result.canonical_digest==record["shape"]
    assert (metrics["required"]-metrics["damage"])*old["required"]>(old["required"]-old["damage"])*metrics["required"]
    check_file=ROOT.parent/"best.heesch"
    for row in check_file.read_text().splitlines():
        if row.startswith("file ") or row.startswith("core "):
            fields=row.split()
            if fields[0]=="core" and len(fields)<4: continue
            names=[v for v in fields if v.endswith(".xz")]
            digests=[v for v in fields if len(v)==64]
            if not (names and digests):continue
            h=sha256()
            with lzma.open(ROOT.parent/names[0],"rb") as stream:
                while block:=stream.read(1024*1024):h.update(block)
            assert h.hexdigest() in digests
    occupied=set()
    for row in record["p3"]:
        third=verify_witness((ROOT/row["geometry"]).read_text())
        assert third.result.hc_verified==4 and third.result.canonical_digest==record["shape"]
        region=frozenset().union(*(r for l,r in third.hc_corona.level_cells.items() if l<=3))
        digest=canonical_digest(region,third.submission.grid,True)
        assert digest not in occupied and row["digest"]==digest
        occupied.add(digest)
        assert row["B_status"]=="OPTIMAL" and row["strict_status"]=="INFEASIBLE"
    accepted=measure(ROOT / "sequence/starting-20-170.heesch")[1]
    assert (accepted["damage"], accepted["required"]) == (20,170)
    for index in range(1,12):
        query=ROOT / "fraction-checks" / f"{index:02d}.inclusive.log"
        logs=[json.loads(q) for q in query.read_text().splitlines() if q.startswith("{")]
        if index != 2: assert logs[-1]["status"] == "INFEASIBLE"
    query=ROOT / "fraction-checks/02.strict.log"
    assert json.loads(query.read_text().splitlines()[-1])["status"] == "INFEASIBLE"
    backed=measure(ROOT / "sequence/02-retry.heesch")[1]
    assert (backed["damage"],backed["uncovered"],backed["required"]) == (7,7,175)
    assert metrics == backed
    print(json.dumps({"tile":record["shape"],"previous":old,"scored":metrics,"score":5-metrics["damage"]/metrics["required"],
                      "third_footprints":len(occupied),"largest_relaxed_B":max(z["B_max"] for z in record["p3"])}))


if __name__=="__main__":
    replay()
