from pathlib import Path
from heesch_verify import GRIDS,verify_witness
D=Path(__file__).resolve().parent;G=GRIDS['O']
def comp(a,b):
 from heesch_verify import Xform
 return Xform(a.a*b.a+a.b*b.d,a.a*b.b+a.b*b.e,a.a*b.c+a.b*b.f+a.c,a.d*b.a+a.e*b.d,a.d*b.b+a.e*b.e,a.d*b.c+a.e*b.f+a.f)
def inv(t):
 from heesch_verify import Xform
 return Xform(t.a,t.d,-t.a*t.c-t.d*t.f,t.b,t.e,-t.b*t.c-t.e*t.f)
def tup(t):return t.a,t.b,t.c,t.d,t.e,t.f
def spell(seq):return ' '.join(','.join(map(str,a))for a in seq)
with(D/'atlas.tsv').open('w')as o:
 for p in sorted((D/'two').glob('*.d2.heesch')):
  w=verify_witness(p.read_text());shape=sorted(w.submission.cells);first=[t for l,t in w.submission.patches[0]if l==1];atlas=set(first);cells=[(l,t,t.apply_all(shape))for l,t in w.submission.patches[0]]
  for l,t,local in cells:
   if l>1:continue
   halo=set(v for u in local for v in G.point_neighbors(u))-local
   for k,s,placed in cells:
    if t!=s and halo&placed:atlas.add(comp(inv(t),s))
  print('kaplan19_'+p.name.split('.')[0],spell(shape),spell(map(tup,first)),spell(sorted(map(tup,atlas))),sep='|',file=o)
