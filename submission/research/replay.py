"""Verify the synthesized square, fractional packing, finite-star obstruction and proof hashes."""
from collections import Counter
from pathlib import Path
import hashlib,json,lzma,math,random
from heesch_verify import verify_witness,canonical_form, canonical_digest
from heesch_verify.patch import required_set
from heesch_verify.defect import verify_defect
from heesch_verify.shape import holes_of
from atlas import solve
D=Path(__file__).resolve().parent

def check(file):return verify_witness(file.read_text())

if __name__=='__main__':
 old=check(D/'parent-19.heesch');s=old.submission.cells;grid=old.submission.grid
 kap=(D/'kaplan-record40.txt').read_text().splitlines();num=list(map(int,kap[0].split()));assert frozenset(zip(num[::2],num[1::2]))==frozenset(s)
 avg=(sum(x for x,y in s)/len(s),sum(y for x,y in s)/len(s));center=min(s,key=lambda p:(sum((a-b)**2 for a,b in zip(p,avg)),p));conf=json.loads((D/'construction.json').read_text());k=conf['scale'];local=check(D/'synthesized-one.heesch');recenter={(round(k*(x-center[0])),round(k*(y-center[1]))) for x,y in s};domain=recenter|{q for p in recenter for q in grid.edge_neighbors(p)};new=frozenset(local.submission.cells);assert len(new)==20 and new<=domain and local.result.hc_verified==1
 # Verify every selected local registration is among the three alternatives generated for its group.
 rng=random.Random(conf['seed']);by={};parents=old.submission.patches[0];signs=[(1,0),(-1,0),(0,1),(0,-1)];chosen={}
 for i,((level,t),(lev,u))in enumerate(zip(parents,local.submission.patches[0])):
  assert (level,t.linear)==(lev,u.linear);g=('center',) if i==0 else (t.linear,level%2)
  if g not in by:by[g]=[(0,0)] if i==0 else [(0,0),*rng.sample(signs,2)]
  a,b,c,d,e,f=t.a,t.b,t.c,t.d,t.e,t.f;cx,cy=center
  base=(round(k*(a*cx+b*cy+c-cx)),round(k*(d*cx+e*cy+f-cy)));diff=u.c-base[0],u.f-base[1];assert diff in by[g] and chosen.get(g,diff)==diff;chosen[g]=diff
 anchor=check(D.parent/'best.heesch');tier2=check(D/'two.heesch');assert canonical_form(new,grid,True)==canonical_form(anchor.submission.cells,grid,True)==canonical_form(tier2.submission.cells,grid,True)
 assert (anchor.result.hc_verified,anchor.result.hh_verified)==(2,2) and not anchor.result.claim_discrepancy
 inner=anchor.hc_corona.patch_cells;outer=frozenset().union(*(t.apply_all(anchor.submission.cells) for l,t in anchor.submission.defect.tiles));req=required_set(inner,anchor.contact);gaps=sorted(req-outer);extra=holes_of(inner|outer,grid)-set(gaps);v=verify_defect(frozenset(anchor.submission.cells),grid,anchor.hc_corona,anchor.submission.defect,anchor.contact)
 assert Counter(anchor.hc_corona.levels)=={0:1,1:4,2:11};assert len(req)==171 and len(gaps)==v.defect_hc==v.defect_hh==5 and len(extra)==v.pocket_cells==0 and v.partial_tiles==27
 assert solve(new)==json.loads((D/'edge-stars.json').read_text());h=json.loads((D/'proof-metadata.json').read_text());proof=(D.parent/'proof.drat.xz').read_bytes();assert hashlib.sha256(proof).hexdigest()==h['xz_sha256'] and hashlib.sha256(lzma.decompress(proof)).hexdigest()==h['raw_proof_sha256'];assert h['cnf_digest'] in (D.parent/'best.heesch').read_text()
 print('19-parent center',center,'selected registrations',chosen);print('20-square',anchor.result.canonical_digest,'rings 1/4/11, 27 partial, required',len(req),'missing',gaps,'extra pockets',len(extra),'score',508/171)
 charts=json.loads((D/'packing-charts/attempts.json').read_text());seen=set()
 for rec in charts:
  h=check(D/'packing-charts'/rec['source']);foot=sorted(h.hc_corona.patch_cells);key=hashlib.sha256(repr(foot).encode()).hexdigest()[:20];assert key==rec['footprint'] and h.result.hc_verified==h.result.hh_verified==2 and len(required_set(h.hc_corona.patch_cells,h.contact))==rec['required'];seen.add(key)
 assert len(charts)==150 and len(seen)==86;print('All 150 chart witnesses verified across 86 footprints.')
