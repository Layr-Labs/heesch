"""Participant-side bounded joint corona search; never part of verification.
Each witness is independently checked by the frozen official routines.
"""
import sys, json, time, argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from collections import defaultdict
from ortools.sat.python import cp_model
from heesch_verify.grids import GRIDS
from heesch_verify.transform import Xform
from heesch_verify.patch import contact_neighbors, required_set
from heesch_verify.shape import holes_of
from heesch_verify.witness import verify_witness
from heesch_verify.defect import verify_defect
from tools.ml_feasibility import KAPLAN_SHAPES

def search(args):
 t0=time.monotonic()
 if args.control:
  control=verify_witness(Path('submission/baseline.heesch').read_text());gid=control.submission.grid_id;S=control.submission.cells
 else:gid,S=KAPLAN_SHAPES[args.shape]
 S=frozenset(S); g=GRIDS[gid]; ct=g.contact('point')
 # Restrict all footprints to a symmetric hexagonal ball. This is a search
 # bound, not a completeness claim or a modification of official limits.
 ball={(x,y) for x in range(-args.radius,args.radius+1) for y in range(-args.radius,args.radius+1) if abs(x+y)<=args.radius}
 forbidden=S|contact_neighbors(S,ct)
 places=[];seen=set()
 for sym in g.orientations:
  img=frozenset(sym.apply(c) for c in S)
  for tx in range(-args.radius,args.radius+1):
   for ty in range(-args.radius,args.radius+1):
    cs=frozenset((x+tx,y+ty) for x,y in img)
    if not cs<=ball or cs&S or cs in seen:continue
    seen.add(cs); halo=contact_neighbors(cs,ct)
    places.append((Xform(sym.a,sym.b,tx,sym.d,sym.e,ty),cs,halo,bool(halo&S)))
 if args.control:
  wanted={xf.apply_all(S) for l,xf in control.submission.patches[0] if l>0}|{xf.apply_all(S) for l,xf in control.submission.defect.tiles}
  places=[p for p in places if p[1] in wanted]
  assert len(places)==len(wanted), 'control radius too small'
 print('universe',len(places),'cells',len(ball),'build_sec',time.monotonic()-t0,flush=True)
 model=cp_model.CpModel(); layers=[{}, {}, {}, {}, {}]; cover=[defaultdict(list) for _ in range(5)]; xs=[]
 diameter=max(max(abs(a[0]-b[0]),abs(a[1]-b[1]),abs(sum(a)-sum(b))) for a in S for b in S)
 center_radius=max(max(abs(x),abs(y),abs(x+y)) for x,y in S)
 for i,(xf,cs,halo,central_touch) in enumerate(places):
  for l in range(5):
   if (l==0)!=central_touch:continue
   if args.reach_bound and max(max(abs(x),abs(y),abs(x+y)) for x,y in cs)>center_radius+(l+1)*(diameter+1):continue
   v=model.new_bool_var(f'x{l+1}_{i}');layers[l][i]=v;xs.append(v)
   for c in cs: cover[l][c].append(v)
 # Exact occupancy and global no-overlap, at cell level.
 occupied=[{} for _ in range(5)]; cumulative=[{} for _ in range(4)]
 def zero():return model.new_constant(0)
 for c in sorted(ball-S):
  vs=[v for l in range(5) for v in cover[l].get(c,())]
  if not vs:continue
  model.add_at_most_one(vs)
  for l in range(5):
   vs=cover[l].get(c,())
   if vs:
    o=model.new_bool_var(f'o{l+1}_{c}'); model.add(sum(vs)==o);occupied[l][c]=o
  for k in range(4):
   vs=[occupied[l][c] for l in range(k+1) if c in occupied[l]]
   if vs:
    o=model.new_bool_var(f'a{k+1}_{c}');model.add(sum(vs)==o);cumulative[k][c]=o
 # A selected tile must touch the preceding layer and avoid earlier layers.
 for l in range(1,5):
  for i,v in layers[l].items():
   halo=places[i][2]
   prev=[occupied[l-1][c] for c in halo if c in occupied[l-1]]
   model.add_bool_or([v.Not()]+prev)
   if l>=2:
    for c in halo:
     if c in cumulative[l-2]:model.add_bool_or([v.Not(),cumulative[l-2][c].Not()])
 # Complete surrounds through layer 4. For prefix k, every contacted cell
 # must lie in prefix k+1; the central tile is a fixed occupancy.
 for c in required_set(S,ct): model.add(cumulative[0].get(c,0)==1)
 for k in range(3):
  for c,o in cumulative[k].items():
   for n in ct.neighbors(c):
    if n not in S:model.add(o<=cumulative[k+1].get(n,0))
 # No singleton holes at each prefix; larger holes handled by sound repair
 # cuts after official checks. All relevant cells are within the ball.
 for k in range(4):
  for c in sorted(ball-S):
   ns=g.edge_neighbors(c)
   if all(n in S or n in cumulative[k] for n in ns):
    clause=[cumulative[k][n].Not() for n in ns if n not in S]
    if c in cumulative[k]:clause.append(cumulative[k][c])
    model.add_bool_or(clause)
 required=[];uncovered=[]
 boundary_cells=set().union(*(places[i][2] for i in layers[3]))-S
 for c in sorted(boundary_cells):
  ns=[cumulative[3][n] for n in ct.neighbors(c) if n in cumulative[3]]
  if not ns:continue
  adjacent=model.new_bool_var(f'nb_{c}');model.add_max_equality(adjacent,ns)
  req=model.new_bool_var(f'r_{c}');own=cumulative[3].get(c)
  if own is not None:
   model.add(req<=adjacent);model.add(req+own<=1);model.add(req>=adjacent-own)
  else:model.add(req==adjacent)
  d=model.new_bool_var(f'd_{c}');five=occupied[4].get(c)
  if five is not None:
   model.add(d<=req);model.add(d+five<=1);model.add(d>=req-five)
  else:model.add(d==req)
  required.append(req);uncovered.append(d)
 model.add(3*sum(required)-254*sum(uncovered)>=(0 if args.control else 1))
 if args.control:
  known={xf.apply_all(S):l for l,xf in control.submission.patches[0] if l>0}
  known.update({xf.apply_all(S):5 for l,xf in control.submission.defect.tiles})
  for l in range(5):
   for i,v in layers[l].items():model.add(v==int(known[places[i][1]]==l+1))
 model.add(sum(uncovered)<=args.defect)
 model.maximize(3*sum(required)-254*sum(uncovered))
 print('model',len(xs),'placement_vars','boundary_vars',len(required),'build_sec',time.monotonic()-t0,flush=True)
 solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=args.seconds;solver.parameters.num_search_workers=args.workers;solver.parameters.random_seed=args.seed
 solver.parameters.log_search_progress=args.log
 cuts=0;out={'shape':args.shape,'radius':args.radius,'seed':args.seed,'max_seconds':args.seconds,'placement_variables':len(xs),'placement_universe':len(places),'boundary_variables':len(required)}
 while time.monotonic()-t0<args.seconds+300:
  status=solver.solve(model);print('verdict',solver.status_name(status),'objective',solver.objective_value,'bound',solver.best_objective_bound,'solve_seconds',solver.wall_time,flush=True)
  out.update(status=solver.status_name(status),objective=solver.objective_value,best_bound=solver.best_objective_bound,solve_seconds=solver.wall_time,cuts=cuts)
  if status not in [cp_model.OPTIMAL,cp_model.FEASIBLE]:break
  selected=[[(i,v) for i,v in layers[l].items() if solver.value(v)] for l in range(5)]
  # Sound hole cuts: remove a chosen wall placement or add a filler.
  bad=False
  for k in range(4):
   chosen=[i for l in range(k+1) for i,v in selected[l]];P=S|set().union(*(places[i][1] for i in chosen))
   hs=holes_of(P,g)
   if hs:
    wall={n for h in hs for n in ct.neighbors(h)}&P
    wallvars=[v for l in range(k+1) for i,v in selected[l] if places[i][1]&wall]
    fillers=[v for l in range(k+1) for i,v in layers[l].items() if places[i][1]&hs]
    model.add_bool_or([v.Not() for v in wallvars]+fillers);cuts+=1;bad=True;break
  if bad:continue
  patch=[(0,Xform(1,0,0,0,1,0))]+[(l+1,places[i][0]) for l in range(4) for i,v in selected[l]]
  P=S|set().union(*(places[i][1] for l in range(4) for i,v in selected[l]))
  C=set().union(*(places[i][1] for i,v in selected[4]))
  R=required_set(P,ct);u=R-C;pockets=holes_of(P|C,g);D=len(u|pockets)
  text=gid+' '+' '.join(str(z) for c in S for z in c)+'\n~ 4 4 1\n'+str(len(patch))+'\n'+'\n'.join(f'{l} {xf.as_text()}' for l,xf in patch)+'\n'
  text+=f'#DEFECT 5 {D} {len(u)} {len(R)}\n{len(selected[4])}\n'+'\n'.join('5 '+places[i][0].as_text() for i,v in selected[4])+'\n'
  outcome=verify_witness(text);d=verify_defect(S,g,outcome.hc_corona,outcome.submission.defect,ct)
  print('official_geometry',d,flush=True)
  if args.control:
   assert d.defect_hc==3 and d.required==254;out['positive_control']='official incumbent reproduced';break
  if 254*d.defect_hc<3*d.required:
   Path('submission/joint-candidate.heesch').write_text(text);out['candidate_score']=4+1-D/len(R);break
  # Allow pocket repairs when blocking a partial-packing counterexample.
  wall={n for h in pockets for n in ct.neighbors(h)}&(P|C)
  walls=[v for l in range(5) for i,v in selected[l] if places[i][1]&wall]
  fillers=[v for l in range(5) for i,v in layers[l].items() if places[i][1]&pockets]
  model.add_bool_or([v.Not() for v in walls]+fillers);cuts+=1
 out['total_seconds']=time.monotonic()-t0;Path(args.out).write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--reach-bound',action='store_true');p.add_argument('--control',action='store_true');p.add_argument('--shape',default='hex13-kaplan-hc4hh4');p.add_argument('--radius',type=int,default=22);p.add_argument('--seconds',type=int,default=600);p.add_argument('--workers',type=int,default=4);p.add_argument('--seed',type=int,default=61);p.add_argument('--defect',type=int,default=3);p.add_argument('--log',action='store_true');p.add_argument('--out',default='submission/joint-result.json');search(p.parse_args())
