"""Enumerate the exact registered star-and-seam system that generated the 18-hexagon child."""
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from ortools.sat.python import cp_model
from heesch_verify import GRIDS,Xform,canonical_form
from heesch_verify.shape import connected,holes_of
import json

r=json.loads((Path(__file__).resolve().parent/'origin.json').read_text());g=GRIDS['H'];source=frozenset(map(tuple,r['donor']));child=frozenset(map(tuple,r['child']));pool=set(source)
for _ in range(2):pool|={q for c in tuple(pool)for q in g.edge_neighbors(c)}
locations=sorted(pool);indices={c:i for i,c in enumerate(locations)};m=cp_model.CpModel();bits=[m.new_bool_var(f's{i}')for i in range(len(locations))];m.add(sum(bits)==18);m.add(sum(bits[indices[c]]for c in source)>=10);m.add(sum(bits[indices[c]]for c in source)<=17)
star=[Xform(1,0,0,0,1,0),*(Xform(*v)for v in r['star'])];providers=defaultdict(list)
for t in star:
    for i,c in enumerate(locations):providers[t.apply(c)].append(i)
for xs in providers.values():
    for i,j in combinations(xs,2):m.add_bool_or([~bits[i],~bits[j]])
for i,c in enumerate(locations):
    for q in g.edge_neighbors(c):m.add_bool_or([~bits[i],*(bits[j]for j in providers[q])]);
    m.add_bool_or([~bits[i],*(bits[indices[q]]for q in g.edge_neighbors(c)if q in indices)])
motion=Xform(*r['cut']);collide=[]
for i,c in enumerate(locations):
    q=motion.apply(c)
    if q not in indices:continue
    j=indices[q]
    if j<i:continue
    if j==i:collide.append(bits[i]);continue
    together=m.new_bool_var('');m.add_bool_and([bits[i],bits[j]]).only_enforce_if(together);collide.append(together)
m.add_bool_or(collide);solver=cp_model.CpSolver();solver.parameters.num_search_workers=1;models=solid=0;found=False
while True:
    status=solver.solve(m)
    if status==cp_model.INFEASIBLE:break
    assert status==cp_model.OPTIMAL;body=frozenset(c for c,b in zip(locations,bits)if solver.value(b));models+=1;m.add_bool_or([~b if c in body else b for c,b in zip(locations,bits)])
    if not connected(body,g)or holes_of(body,g):continue
    halo={q for c in body for q in g.edge_neighbors(c)}-body;copies=[t.apply_all(body)for t in star];area=frozenset().union(*copies)
    if any(not p&halo for p in copies[1:]) or not halo<=area or holes_of(area,g):continue
    assert len(area)==len(body)*len(star);solid+=1;found|=body==child
assert models==24 and solid==9 and found
print(f'{models} outline masks, {solid} physically valid complete central stars, submitted outline recovered')
