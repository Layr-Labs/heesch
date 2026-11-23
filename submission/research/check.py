"""Verify the fixed-boundary lower bound and replay the geometrical companion."""
from collections import Counter, deque
from hashlib import sha256
import json,lzma,sys,subprocess,tempfile
from pathlib import Path
from heesch_verify import GRIDS, Xform, canonical_form, verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.transform import check_symmetry
from bound import enum_tiles, build

here=Path(__file__).resolve().parent

def check(gate):
    g=GRIDS['H']
    A=verify_witness((here/'attempt19.heesch').read_text());B=verify_witness((here.parent/'best.heesch').read_text())
    assert A.submission.patches==B.submission.patches and A.submission.cells==B.submission.cells
    assert A.submission.proof==B.submission.proof and sha256(lzma.decompress((here.parent/'proof.drat.xz').read_bytes())).hexdigest()==B.submission.proof.payload_sha256
    assert A.result.hc_verified==B.result.hc_verified==4
    for w,stats in [(A,(175,21,15,36,30)),(B,(175,24,1,25,32))]:
        d=verify_defect(frozenset(w.submission.cells),g,w.hc_corona,w.submission.defect,w.contact)
        assert (d.required,d.defect_hh,d.pocket_cells,d.defect_hc,d.partial_tiles)==stats
    inner=B.hc_corona.patch_cells; required=set(required_set(inner,B.contact)); choices=enum_tiles(B.submission.cells,g,inner,required)
    report=json.loads((here/'bound.json').read_text()); f=build(g,inner,required,choices,report['cuts'],24)
    assert len(choices)==1865 and (f.n,len(f.clauses))==(34492,131787)
    with tempfile.TemporaryDirectory() as tmp:
        cnf=Path(tmp)/'bound.cnf';f.write(cnf)
        assert sha256(cnf.read_bytes()).hexdigest()==report['cnf_sha256']
        proof=Path(tmp)/'bound.drat';proof.write_bytes(lzma.decompress((here/'fixed.drat.xz').read_bytes()))
        assert sha256(proof.read_bytes()).hexdigest()==report['drat_sha256']
        process=subprocess.run([str(gate),str(cnf),str(proof)],capture_output=True,text=True,check=True)
        assert 's VERIFIED' in process.stdout
    print('Four-ring chart and prior proof match. 25 charged cells attained. Every partial corona of defect at most 24 on this chart is excluded by checked DRAT.')
    example=json.loads((here/'cavity.json').read_text());old=frozenset(B.submission.cells);chart=example['chart']
    motions=B.submission.patches[0];center=motions[chart['center_index']][1]
    halo={q for p in center.apply_all(old) for q in g.edge_neighbors(p)}-center.apply_all(old)
    actual={frozenset(u.apply_all(old)) for lv,u in motions if not halo.isdisjoint(u.apply_all(old))}
    rel=[Xform(*m) for m in chart['neighbors']]
    assert actual=={frozenset(center.apply_all(m.apply_all(old))) for m in rel}
    edited=old-set(map(tuple,example['cuts']));barrier=set()
    for m in rel:
        covered=m.apply_all(edited);assert not barrier&covered;barrier.update(covered)
    cavity=set();queue=deque([tuple(example['anchor'])]);
    while queue:
        q=queue.popleft()
        if q in barrier or q in cavity:continue
        cavity.add(q); assert len(cavity)<=18;queue.extend(g.edge_neighbors(q))
    C=verify_witness((here/'cavity-five.heesch').read_text());shape=frozenset(C.submission.cells)
    assert len(edited)==13 and len(cavity)==len(shape)==18 and canonical_form(cavity,g,True)==canonical_form(shape,g,True)
    assert C.result.hc_verified==5 and C.result.patch_size==100
    copies,a,b,c=map(int,example['quotient'][:4]);counts=Counter()
    for pose in example['quotient'][4:]:
        t=Xform(*map(int,pose.split(',')));check_symmetry(t,g,True)
        for x,y in t.apply_all(shape):
            s,r=divmod(y,c);counts[(x-s*b)%a,r]+=1
    assert copies==len(example['quotient'][4:])==8 and a*c==len(counts)==144 and set(counts.values())=={1}
    print('18-hex cavity verified in the original parent frame. A 100-copy fifth ring and an eight-copy quotient of 144 cells both replay.')
if __name__=='__main__':check(Path(sys.argv[1]) if len(sys.argv)>1 else Path('tools/bin/drat-trim'))
