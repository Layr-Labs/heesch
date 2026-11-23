"""SAT certificate for a lower bound on scored defect on one frozen footprint.

Generate all outer placements, exact occupancy, local enclosure implications,
and a truncated unary counting circuit. CaDiCaL checks the resulting bound.
"""
import json
from collections import defaultdict, deque
from pathlib import Path
import subprocess, sys
from heesch_verify import verify_witness
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of
from heesch_verify.transform import Xform

HERE=Path(__file__).resolve().parent

def enum_tiles(shape,g,inner,required):
    poses={}
    for sym in g.orientations:
        turn=sorted(map(sym.apply,shape))
        offsets={(x-a,y-b) for x,y in required for a,b in turn}
        for x,y in sorted(offsets):
            fp=tuple(sorted((a+x,b+y) for a,b in turn))
            if inner.isdisjoint(fp):poses.setdefault(fp,Xform(sym.a,sym.b,x+sym.c0,sym.d,sym.e,y+sym.f0))
    return sorted(poses.items())

class Formula:
    def __init__(self):self.n=0;self.clauses=[]
    def var(self):self.n+=1;return self.n
    def clause(self,*lits):self.clauses.append(lits)
    def amo(self,vs):
        if len(vs)<2:return
        last=None
        for v in vs[:-1]:
            prefix=self.var();self.clause(-v,prefix)
            if last:self.clause(-last,prefix);self.clause(-v,-last)
            last=prefix
        self.clause(-vs[-1],-last)
    def at_most(self,terms,budget):
        def build(values):
            if len(values)==1:return values
            mid=len(values)//2
            left,right=build(values[:mid]),build(values[mid:])
            counts=[self.var() for _ in range(min(len(values),budget+1))]
            for k,v in enumerate(left):self.clause(-v,counts[k])
            for k,v in enumerate(right):self.clause(-v,counts[k])
            for i,a in enumerate(left):
                for j,b in enumerate(right):
                    if i+j+1<len(counts):self.clause(-a,-b,counts[i+j+1])
            return counts
        root=build(terms)
        if len(root)>budget:self.clause(-root[budget])
    def write(self,p):
        with p.open('w') as f:
            f.write(f'p cnf {self.n} {len(self.clauses)}\n')
            for row in self.clauses:f.write(' '.join(map(str,row))+' 0\n')

def components(sites,g):
    left=set(sites)
    while left:
        s={left.pop()}; work=list(s)
        while work:
            for p in g.edge_neighbors(work.pop()):
                if p in left:left.remove(p);work.append(p);s.add(p)
        yield s

def build(g,inner,required,placements,cuts,budget):
    f=Formula();owners=defaultdict(list)
    for fp,_ in placements:
        v=f.var()
        for q in fp:owners[q].append(v)
    occupied={p:f.var() for p in sorted(owners)}
    for p,o in occupied.items():
        choices=owners[p];f.amo(choices)
        for v in choices:f.clause(-v,o)
        f.clause(-o,*choices)
    forced=f.var();f.clause(forced)
    value=lambda q: forced if q in inner else occupied.get(q,-forced)
    extra={}
    def charge(q):
        if q not in extra:extra[q]=f.var()
        return extra[q]
    for q in sorted(set(occupied)-required):
        sides=[value(n) for n in g.edge_neighbors(q)]
        if -forced not in sides:f.clause(*( -o for o in sides if o!=forced),value(q),charge(q))
    for rec in cuts:
        rim=rec['rim'];holes=set(map(tuple,rec['extra']))
        assert all(1<=v<=len(placements) for v in rim)
        barrier=set(inner)
        for v in rim:barrier.update(placements[v-1][0])
        assert holes <= holes_of(barrier,g)-required
        for q in sorted(holes):f.clause(*(-v for v in rim),value(q),charge(q))
    f.at_most([-value(p) for p in sorted(required)]+[extra[p] for p in sorted(extra)],budget)
    return f

def generate(witness,target,budget,cadical,proof=True):
    w=verify_witness(witness.read_text());g=w.submission.grid;inner=w.hc_corona.patch_cells
    required=set(required_set(inner,w.contact));raw=enum_tiles(w.submission.cells,g,inner,required)
    cuts=[];trials=[];target.mkdir(parents=True,exist_ok=True)
    while True:
        f=build(g,inner,required,raw,cuts,budget)
        cnf=target/'fixed.cnf'; f.write(cnf)
        cmd=[str(cadical),'--seed=24295',str(cnf)]
        if proof:cmd.append(str(target/'fixed.drat'))
        process=subprocess.run(cmd,capture_output=True,text=True)
        (target/f'solve-{len(trials)}.log').write_text(process.stdout)
        print('trial',len(trials),'variables',f.n,'clauses',len(f.clauses),'exit',process.returncode,flush=True)
        if process.returncode==20:break
        if process.returncode!=10:raise RuntimeError(process.stderr)
        selected={v for row in process.stdout.splitlines() if row.startswith('v ') for v in map(int,row.split()[1:]) if 1<=v<=len(raw)}
        owner={q:v for v in selected for q in raw[v-1][0]}
        union=inner|owner.keys(); gaps=required-owner.keys(); holes=holes_of(union,g)
        assert len(owner)==len(selected)*len(w.submission.cells)
        trials.append({'gaps':len(gaps),'pockets':len(holes-gaps),'copies':len(selected)})
        if len(gaps|holes)<=budget:raise ValueError(f'Feasible {trials[-1]}')
        for pocket in components(holes,g):
            extras=sorted(pocket-required)
            if not extras:continue
            rim=sorted({owner[n] for q in pocket for n in g.edge_neighbors(q) if n in owner})
            row={'extra':extras,'rim':rim}
            if row not in cuts:cuts.append(row)
    report={'budget':budget,'solid_copies':w.result.patch_size,'required':len(required),'candidates':len(raw),'vars':f.n,'clauses':len(f.clauses),'cuts':cuts,'counterexamples':trials}
    (target/'bound.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('witness',type=Path);p.add_argument('folder',type=Path);p.add_argument('cadical',type=Path);p.add_argument('--budget',type=int,default=24);args=p.parse_args()
    generate(args.witness,args.folder,args.budget,args.cadical)
