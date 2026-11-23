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
    def records(path):
        return [json.loads(line) for line in path.read_text().splitlines() if line.startswith("{")]
    projections = sorted((ROOT / "full-census").rglob("project.log"))
    assert len(projections) == 19
    counts = Counter()
    for log in projections:
        run = records(log)
        assert run[-1]["status"] == "INFEASIBLE"
        depth = len(log.relative_to(ROOT / "full-census").parts)
        files = list(log.parent.glob("patch-???.heesch"))
        counts[depth] += len(files)
        assert len(files) == sum("file" in entry for entry in run)
    assert [counts[i] for i in (1,2,3)] == record["counts"][0]
    bounds = records(ROOT / "thirds/01.bound.log")[-1]
    assert bounds["upper_bound"] == record["p3"][0]["B_max"] and bounds["status"] == "OPTIMAL"
    for name in ("01.strict.log", "01.reported-fraction.log", "01.conditional-strict.log", "01.conditional-reported.log"):
        assert records(ROOT / "thirds" / name)[-1]["status"] == "INFEASIBLE"
    print(json.dumps({"tile":record["shape"],"previous":old,"scored":metrics,"score":5-metrics["damage"]/metrics["required"],
                      "third_footprints":len(occupied),"largest_relaxed_B":max(z["B_max"] for z in record["p3"])}))


if __name__=="__main__":
    replay()
