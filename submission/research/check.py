"""Replay the exact quotient covers, physical third ring, flood debit and compact proof digest."""
from pathlib import Path
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json,tarfile,lzma
from heesch_verify import verify_witness,canonical_digest,canonical_form
from heesch_verify.defect import verify_defect
D=Path(__file__).resolve().parent

def replay():
 meta=json.loads((D/'geometry.json').read_text());rows=json.loads((D/'strongest.json').read_text());n=meta['id'];files={n:D.parent/'best.heesch',meta['sibling']:D/'companion.heesch'};g=None;hashed={}
 for row in rows:
  label=row['id'];w=verify_witness(files[label].read_text());g=w.submission.grid;s=frozenset(w.submission.cells);charged=verify_defect(s,g,w.hc_corona,w.submission.defect,w.contact);assert (charged.defect_hc,charged.defect_hh,charged.required,charged.partial_tiles)==(row['damage'],row['hh'],row['required'],row['partial']);assert Counter(l for l,t in w.submission.patches[0])=={int(k):v for k,v in row['rings'].items()};assert w.result.hc_verified==3;hashed[label]=w.result.canonical_digest
 assert hashed[n]==meta['digest'] and hashed[meta['sibling']]==meta['companionDigest'] and len(set(hashed.values()))==2
 donor=frozenset(verify_witness((D/'donor.heesch').read_text()).submission.cells)
 for line in (D/'origins.tsv').read_text().splitlines():
  id,seed,overlap,a,b,c,A,B,E,F,sx,sy,dx,dy,*points=line.split();a,b,c,A,B,E,F,sx,sy,dx,dy=map(int,(a,b,c,A,B,E,F,sx,sy,dx,dy));p={tuple(map(int,x.split(','))) for x in points};assert canonical_digest(p,g,True)==hashed[id] and len(donor&p)==int(overlap)==13;half=[(x+sx,y+sy)for x,y in p]+[(A*x+B*y+dx,E*x+F*y+dy)for x,y in p];counts=Counter()
  for _ in range(3):
   for x,y in half:counts[(x-(y//c)*b)%a,y%c]+=1
   half=[(-x-y,x)for x,y in half]
  assert a*c==121 and len(counts)==120 and set(counts.values())=={1} and (0,0)not in counts
 footprints=set()
 with tarfile.open(D/'sampled-thirds.tar.xz') as tar:
  for member in tar.getmembers():
   w=verify_witness(tar.extractfile(member).read().decode());assert w.result.hc_verified==3 and w.result.canonical_digest==hashed[n];key=sha256(repr(tuple(canonical_form(w.hc_corona.patch_cells,g,True))).encode()).hexdigest();assert member.name==key+'.heesch';footprints.add(key)
 assert len(footprints)==meta['sampledThirds'];w=verify_witness(files[n].read_text());d=w.submission.proof
 if d:
  manifest=json.loads((D/'proof-manifest.json').read_text());assert d.m==4 and d.cnf_digest==manifest['cnf_digest'] and (d.num_vars,d.num_clauses)==(manifest['vars'],manifest['clauses']); h=sha256()
  with lzma.open(D.parent/d.file_name,'rb')as stream:
   while chunk:=stream.read(1<<20):h.update(chunk)
  assert h.hexdigest()==d.payload_sha256==manifest['proof_sha256']
  assert d.core_file=='proof.core.xz' and d.core_clauses==manifest['core_clauses']
  h=sha256()
  with lzma.open(D.parent/d.core_file,'rb')as stream:
   while chunk:=stream.read(1<<20):h.update(chunk)
  assert h.hexdigest()==d.core_sha256==manifest['core_sha256']
 print(json.dumps(dict(primary=n,outline=hashed[n],sampled_thirds=len(footprints),score=meta['nominal'],certificate=bool(d)),indent=2))
if __name__=='__main__':replay()
