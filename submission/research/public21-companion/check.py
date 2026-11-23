"""Independently enumerate every complete fourth footprint for the first three rings of b17_cand_511."""
from collections import Counter, defaultdict
from fractions import Fraction
from hashlib import sha1, sha256
from pathlib import Path
import json
from heesch_verify import Xform, verify_witness
from heesch_verify.canonical import canonical_digest
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of

HERE=Path(__file__).resolve().parent


def load(path):
    w=verify_witness(path.read_text())
    shape=frozenset(w.submission.cells)
    d=verify_defect(shape,w.submission.grid,w.hc_corona,w.submission.defect,w.contact)
    prefix=frozenset().union(*(t.apply_all(shape) for l,t in w.submission.patches[0] if l<=3))
    return w,shape,prefix,d


def fourths(region,required,shape,grid):
    raw=set()
    for op in grid.orientations:
        oriented=tuple(op.apply(c) for c in shape)
        offsets={(x-a,y-b) for x,y in required for a,b in oriented}
        for dx,dy in offsets:
            placed=frozenset((x+dx,y+dy) for x,y in oriented)
            if not placed&region:
                raw.add(placed)
    tiles=sorted(raw,key=lambda t:sorted(t))
    providers=defaultdict(set)
    halo=[]
    collisions=[]
    for i,t in enumerate(tiles):
        halo.append(t&required)
        for p in t:providers[p].add(i)
    for t in tiles:
        collisions.append(set().union(*(providers[p]for p in t)))
    covers=0
    solid=set()
    def visit(rest, available, body):
        nonlocal covers
        if not rest:
            covers+=1
            if not holes_of(body,grid):
                solid.add(body)
            return
        choices=min((providers[cell]&available for cell in rest),key=len)
        for i in choices:
            visit(rest-halo[i],available-collisions[i],body|tiles[i])
    visit(required,set(range(len(tiles))),region)
    return covers,solid


def main():
    data=json.loads((HERE/"attribution.json").read_text())
    published=(HERE/"published.heesch")
    raw=published.read_bytes()
    assert sha256(raw).hexdigest()==data["source_sha256"]
    assert sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()==data["git_blob"]
    old,shape,p3,prev=load(published)
    new,cells,p3b,now=load(HERE/"improved.heesch")
    assert shape==cells and len(shape)==21 and p3==p3b
    assert (prev.defect_hc,prev.defect_hh,prev.required,prev.partial_tiles,prev.pocket_cells)==(11,11,175,32,0)
    assert (now.defect_hc,now.defect_hh,now.required,now.partial_tiles,now.pocket_cells)==(9,9,178,33,0)
    assert old.result.hc_verified==new.result.hc_verified==4
    grid=old.submission.grid
    projection=json.loads((HERE/"global.json").read_text())
    assert canonical_digest(p3,grid,True)==projection["third_digest"]
    assert projection["third_cells"]==len(p3)==798
    assert projection["other_solid_thirds"]==projection["holed_intermediate_models"]==0
    assert "EXHAUSTED 0 0 seconds" in (HERE/"frozen-third.log").read_text()
    r4=required_set(p3,old.contact)
    total,solid=fourths(p3,r4,shape,grid)
    assert (total,len(solid))==(144,17)
    enc=json.loads((HERE/"fourths.json").read_text())
    poses=[Xform(*map(int,z[1:-1].split(","))).apply_all(shape)for z in enc["fourth"]]
    matched={}
    for row in (HERE/"fourths.tsv").read_text().splitlines():
        key,B,mask=row.split();mask=int(mask,16)
        footprint=p3|frozenset().union(*(set(v)for i,v in enumerate(poses)if(mask>>i)&1))
        assert footprint in solid and len(required_set(footprint,old.contact))==int(B)
        matched[int(key)]=footprint
    assert set(matched.values())==solid and matched[6]==new.hc_corona.patch_cells
    reports=json.loads((HERE/"packing.json").read_text())
    assert len(reports)==len(solid)
    for r in reports:
        run=r["runs"];B=r["required"]
        assert run[0]["status"]=="INFEASIBLE" and run[0]["cap"]==(3*B-1)//254
        assert run[-1]["status"]=="INFEASIBLE" and run[-1]["cap"]>=(9*B-1)//178
    assert data["peer_scored_cells"]==20 and data["peer_scored_required"]==237
    print(json.dumps(dict(old=old.result.canonical_digest,unique_third=projection["third_digest"],complete_fourths=total,solid_fourths=len(solid),
                          baseline=str(5-Fraction(11,175)),improved=str(5-Fraction(9,178)),
                          improved_levels=dict(Counter(l for l,t in new.submission.patches[0])),
                          partial=now.partial_tiles)))


if __name__=="__main__":
    main()
