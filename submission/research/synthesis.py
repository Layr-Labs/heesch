"""Fit Boolean square occupancy and local translations to a smaller corona scaffold.
Each parent tile's centroid is shrunk about the central centroid. Groups of placements
may adjust their translations independently by one lattice unit. Coverage is imposed
at every level, with congruent copies of a single Boolean-indicator outline.
"""
from pathlib import Path
from collections import defaultdict,Counter
from itertools import product
from hashlib import sha256
import argparse,math,json,random,sys,time
from ortools.sat.python import cp_model
from heesch_verify import GRIDS, Xform, canonical_digest,verify_witness
from heesch_verify.shape import connected,holes_of

G=GRIDS['O'];D=Path(__file__).resolve().parent

def fit(parent,depth,scale,style,criterion,seconds,seed=5038):
    start=time.monotonic();w=verify_witness(parent.read_text());s=w.submission.cells;moves=[(j,t) for j,t in w.submission.patches[-1] if j<=depth];k=scale
    centroid=(sum(x for x,y in s)/len(s),sum(y for x,y in s)/len(s));center=min(s,key=lambda p:(sum((a-b)**2 for a,b in zip(p,centroid)),p));norm={(round(k*(x-center[0])),round(k*(y-center[1]))) for x,y in s}; halo={q for p in norm for q in G.edge_neighbors(p)};points=sorted(norm|halo);idx={p:i for i,p in enumerate(points)}; model=cp_model.CpModel();x=[model.new_bool_var('x'+str(i)) for i in range(len(points))];model.add_linear_constraint(sum(x),14,20);model.add(sum(x[idx[q]] for q in norm)>=round(.65*min(20,len(norm))));model.add(x[idx[0,0]]==1) if (0,0) in idx else None
    if criterion=='expand':
       # Force a new 20-cell tile while keeping the observed first two parent rings.
       model.add(sum(x)==20)
    # Per-orientation/joint alternatives keep each solve compact. The next seed changes the permitted signed offsets.
    rng=random.Random(seed);jitter=[(0,0),(1,0),(-1,0),(0,1),(0,-1)];slots={};groups={};variants={};new=[];cpvars=list(x)
    def group_key(t,i,lev):
       if i==0:return ('center',)
       if style=='independent':return (i,)
       if style=='orientation':return t.linear
       return (t.linear,lev%2)
    for i,(lev,t) in enumerate(moves):
       a,b,c,d,e,f=t.a,t.b,t.c,t.d,t.e,t.f;cx,cy=center
       bx=round(k*(a*cx+b*cy+c-cx));by=round(k*(d*cx+e*cy+f-cy));g=group_key(t,i,lev)
       if g not in groups:
          shifts=[(0,0)] if i==0 or style=='fixed' else [(0,0),*rng.sample(jitter[1:],2)];opts=[]
          for j,z in enumerate(shifts):
             sw=model.new_bool_var('');opts.append(sw)
             if len(shifts)==1:variants[g,j]=list(range(len(points)))
             else:
                row=[]
                for h in x:
                   v=model.new_bool_var('');model.add(v<=sw);model.add(v<=h);model.add(v>=h+sw-1);row.append(len(cpvars));cpvars.append(v)
                variants[g,j]=row
          model.add_exactly_one(opts);groups[g]=[shifts,opts]
       new.append((lev,g,a,b,bx,d,e,by))
    prev={};curr=defaultdict(list);amos=set();covs=set()
    for lev in range(depth+1):
       for l,g,a,b,c,d,e,f in new:
          if l!=lev:continue
          for j,(dx,dy) in enumerate(groups[g][0]):
             for (u,v),lit in zip(points,variants[g,j]):curr[a*u+b*v+c+dx,d*u+e*v+f+dy].append(lit)
       tbl={p:tuple(sorted(h)) for p,h in curr.items()}
       if lev:
          for p,h in prev.items():
             for q in G.point_neighbors(p):
                hh=tbl.get(q,());h1=Counter(h);h2=Counter(hh);l=tuple(sorted((h1-h2).elements()));r=tuple(sorted((h2-h1).elements()));
                if l:covs.add((l,r))
       prev=tbl
    for h in set(tbl.values()):
       if len(h)>1:model.add(sum(cpvars[i] for i in h)<=1)
    for l,r in covs:model.add(sum(cpvars[i] for i in l)<=sum(cpvars[i] for i in r))
    if criterion=='finite':
       demands=[];leaves=[]
       for p in set(points)|{q for t in points for q in G.edge_neighbors(t)}:
          ix=[idx[q] for q in G.edge_neighbors(p) if q in idx];terms=([x[idx[p]]] if p in idx else [])+[x[i] for i in ix];nd=model.new_bool_var('');lf=model.new_bool_var('');table=[]
          for bits in product((0,1),repeat=len(terms)):
             occ=bits[0] if p in idx else 0;num=sum(bits)-occ;table.append((*bits,int(not occ and num==3),int(occ and num==1)))
          model.add_allowed_assignments(terms+[nd,lf],table);demands.append(nd);leaves.append(lf)
       model.add(sum(demands)>sum(leaves))
    # Enforce a connected prototype and connected empty exterior within a one-cell margin.
    low=min(a for a,b in points)-1;high=max(a for a,b in points)+1
    bottom=min(b for a,b in points)-1;top=max(b for a,b in points)+1
    box={(a,b) for a in range(low,high+1) for b in range(bottom,top+1)}
    for domain,tile in [(set(points),True),(box,False)]:
       root=(0,0) if tile else (low,bottom);cap=len(domain)
       member={p:(x[idx[p]] if tile else (1-x[idx[p]] if p in idx else 1)) for p in domain};model.add(member[root]==1)
       outgoing=defaultdict(list);incoming=defaultdict(list)
       for p in domain:
          for q in G.edge_neighbors(p):
             if q not in domain:continue
             flow=model.new_int_var(0,cap,'');model.add(flow<=cap*member[p]);model.add(flow<=cap*member[q]);outgoing[p].append(flow);incoming[q].append(flow)
       for p in domain:
          if p!=root:model.add(sum(incoming[p])-sum(outgoing[p])>=member[p])
    if criterion in ('change','expand'):
       seedform=frozenset((a-center[0],b-center[1]) for a,b in s)
       # Exclude every equivalent orientation/translation within the prototype box.
       bans=set()
       for o in G.orientations:
          img=set(o.apply(t) for t in seedform);u,v=next(iter(img))
          for px,py in points:
             dx,dy=px-u,py-v;trans=frozenset((a+dx,b+dy) for a,b in img)
             if trans<=set(points):bans.add(trans)
       for ban in bans:model.add_bool_or([~x[i] if p in ban else x[i] for i,p in enumerate(points)])
       model.maximize(sum((rng.randrange(-1,3))*v for v in x))
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=seconds;solver.parameters.num_workers=2;solver.parameters.random_seed=seed;result=solver.solve(model)
    ans=dict(parent=parent.name,depth=depth,scale=scale,style=style,criterion=criterion,seed=seed,status=solver.status_name(result),seconds=round(time.monotonic()-start,2),variables=len(cpvars),coverage=len(covs),groups=len(groups));
    if result in (cp_model.OPTIMAL,cp_model.FEASIBLE):
       S=frozenset(p for p,v in zip(points,x) if solver.value(v));key=canonical_digest(S,G,True)[:20];ans.update(area=len(S),key=key);choices={g:shifts[next(i for i,v in enumerate(opts) if solver.value(v))] for g,(shifts,opts) in groups.items()};ps=[(l,Xform(a,b,c+choices[g][0],d,e,f+choices[g][1])) for l,g,a,b,c,d,e,f in new]
       text='O '+' '.join(f'{x} {y}'for x,y in sorted(S))+'\n'+f'~ {depth} {depth} 1\n'+str(len(ps))+'\n'+''.join(f'{l} {t.as_text()}\n'for l,t in ps)
       try:
          v=verify_witness(text);ans.update(hc=v.result.hc_verified,hh=v.result.hh_verified)
          if v.result.hc_verified==depth:(D/f'{criterion}-{key}.d{depth}.heesch').write_text(text)
          if v.result.hh_verified>v.result.hc_verified:
             solid=[(l,t) for l,t in ps if l<=v.result.hc_verified];solidblock=str(len(solid))+'\n'+''.join(f'{l} {t.as_text()}\n'for l,t in solid);text=text.replace(f'~ {depth} {depth} 1\n',f'~ {v.result.hc_verified} {v.result.hh_verified} 2\n'+solidblock);assert not verify_witness(text).result.claim_discrepancy;(D/f'{criterion}-{key}.p{depth}.heesch').write_text(text)
       except Exception as e:ans['geometry_error']=str(e)[:120]
    print(json.dumps(ans),flush=True);return ans

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('parent',type=Path);p.add_argument('depth',type=int);p.add_argument('scale',type=float);p.add_argument('style');p.add_argument('criterion');p.add_argument('seconds',type=int);p.add_argument('seed',type=int);args=p.parse_args();fit(**vars(args))
