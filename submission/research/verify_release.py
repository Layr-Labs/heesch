"""Recreate both compressions, validate the scored anchor and decode the porous companion."""
from pathlib import Path
from collections import Counter
from hashlib import sha256
import lzma,json,tempfile
from heesch_verify import verify_witness,canonical_form
from heesch_verify.defect import verify_defect
from heesch_verify.shape import holes_of
from heesch_verify.patch import required_set
from decode_square import universe,materialize

D=Path(__file__).resolve().parent

def outcome(src): return verify_witness(src.read_text())

def profile(src):
    v=outcome(src);s=v.submission;d=verify_defect(set(s.cells),s.grid,v.hc_corona,s.defect,v.contact)
    return dict(rings=sorted(Counter(v.hc_corona.levels).items()),required=d.required,charged=d.defect_hc,raw=d.defect_hh,pockets=d.pocket_cells,extra_copies=d.partial_tiles)

if __name__=='__main__':
    old=outcome(D/'parent-99.heesch'); cells=old.submission.cells; grid=old.submission.grid
    assert len(cells)==99; norm={(x-min(p[0] for p in cells),y-min(p[1] for p in cells)) for x,y in cells}
    parent29=D/'strip-family/parent-29.heesch'; anchor=D.parent/'best.heesch'; companion=D/'partial-38.heesch'
    for file,xs in [(anchor,[0,2,4,6,7,8,9,12,15,19]),(companion,[0,2,3,6,7,9,11,12,14,16,17,18,19])]:
        shape={(i,j) for i,x in enumerate(xs) for j,y in enumerate([0,1,2,5]) if (x,y) in norm}
        assert canonical_form(shape,grid,True)==canonical_form(outcome(file).submission.cells,grid,True)
    s=outcome(anchor); a=outcome(parent29);assert canonical_form(s.submission.cells,grid,True)==canonical_form(a.submission.cells,grid,True)
    assert s.result.hc_verified==s.result.hh_verified==3
    assert anchor.read_text().split('#PROOF')[1]==parent29.read_text().split('#PROOF')[1]
    raw=(D.parent/'proof.drat.xz').read_bytes(); meta=json.loads((D/'anchor-certificate.json').read_text())
    assert sha256(raw).hexdigest()==meta['compressed_sha256'] and sha256(lzma.decompress(raw)).hexdigest()==meta['proof_raw_sha256']
    former=profile(parent29); now=profile(anchor); assert (former['charged'],former['required'])==(35,246) and (now['charged'],now['required'])==(16,272)
    print('29-square original and improved:',json.dumps([former,now]),flush=True)
    m=outcome(D/'model-four.heesch');assert (m.result.hc_verified,m.result.hh_verified)==(3,4) and not m.result.claim_discrepancy
    assert [len(p) for p in m.submission.patches]==[37,68]; shape=frozenset(m.submission.cells)
    levels=universe(shape,grid,m.contact,4);p=json.loads((D/'model-four.json').read_text());assert list(map(len,levels))==p['universe']
    with tempfile.TemporaryDirectory() as tmp:
        out=Path(tmp)/'model.heesch';materialize(shape,grid,m.contact,levels,set(p['selected_variables']),out)
        assert out.read_bytes()==(D/'model-four.heesch').read_bytes()
    assert p['holes']==[0,0,0,0,36] and p['gaps']==[0]*5
    print('The 29-square proof envelope and both geometric witnesses replayed.')
