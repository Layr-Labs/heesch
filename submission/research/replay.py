"""Replay the construction, two H4 charts, the scored footprint and five-ring periodic controls."""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import json
import lzma
import re
from heesch_verify import GRIDS, Xform, canonical_digest, verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.shape import spans
from heesch_verify.transform import check_symmetry

ROOT = Path(__file__).resolve().parent
GRID = GRIDS['I']


def motion(text):
    transform = Xform(*map(int, re.findall(r'-?\d+', text)))
    check_symmetry(transform, GRID, True)
    return transform


def compose(left, right):
    a,b,c,d,e,f = (left.a,left.b,left.c,left.d,left.e,left.f)
    p,q,r,s,t,u = (right.a,right.b,right.c,right.d,right.e,right.f)
    return Xform(a*p+b*s, a*q+b*t, a*r+b*u+c, d*p+e*s, d*q+e*t, d*r+e*u+f)


def inverse(t):
    det = t.a*t.e-t.b*t.d
    return Xform(t.e*det,-t.b*det,(t.b*t.f-t.e*t.c)*det,-t.d*det,t.a*det,(t.d*t.c-t.a*t.f)*det)


def transform_cut(parent, chunks):
    removed, placed = set(), set()
    for cut in chunks:
        piece = set(map(tuple, cut['cut']))
        assert piece <= parent and piece.isdisjoint(removed)
        transformed = motion(cut['relative']).apply_all(piece)
        dx, dy = cut.get('move',cut.get('seam_shift'))
        assert GRID.translation_legal(dx,dy)
        transformed = {(x+dx,y+dy) for x,y in transformed}
        assert transformed.isdisjoint(placed)
        removed.update(piece)
        placed.update(transformed)
    core = parent - removed
    assert core.isdisjoint(placed)
    return core | placed


def witness(path):
    return verify_witness(path.read_text())


def observed(submission):
    all_poses = [(level,pose,pose.apply_all(submission.cells)) for level,pose in submission.patches[0]]
    counts = Counter()
    for level, pose, cells in all_poses:
        if level >= 3:
            continue
        halo = {q for p in cells for q in GRID.edge_neighbors(p)} - cells
        for _, other, neighbor in all_poses:
            if halo & neighbor:
                counts[compose(inverse(pose),other).as_text()] += 1
    return counts


def construction():
    info=json.loads((ROOT/'data/recovered20.json').read_text())
    parent = witness(ROOT/'patches/fold27.heesch').submission
    charges = observed(parent)
    trim = set(map(tuple,info['trim']))
    assert len(trim)==7 and trim<=set(parent.cells)
    for move in info['chunk_steps']:
        assert charges[move['relative']]==move['instances']==4
    literal=transform_cut(set(parent.cells)-trim,info['chunk_steps'])
    assert literal==set(map(tuple,info['recovered_coords']))
    actual = witness(ROOT.parent/'best.heesch')
    registered=motion(info['registration']).apply_all(literal)
    assert registered==frozenset(actual.submission.cells)
    src = ROOT / info['chart_source']
    assert hashlib.sha256(src.read_bytes()).hexdigest()==info['chart_source_sha256']
    prior = witness(src).submission
    assert motion(info['to_attempt17']).apply_all(literal)==frozenset(prior.cells)
    transported=witness(ROOT/'patches/transported-four.heesch').submission
    assert [(l,t.apply_all(transported.cells)) for l,t in transported.patches[0]]==[(l,t.apply_all(prior.cells)) for l,t in prior.patches[0]]
    fresh=witness(ROOT/'patches/fresh-four.heesch')
    assert fresh.submission.patches==actual.submission.patches
    assert Counter(l for l,_ in actual.submission.patches[0])=={0:1,1:5,2:12,3:19,4:30}
    assert actual.result.hc_verified==4 and actual.result.hh_verified==4
    d=verify_defect(registered,GRID,actual.hc_corona,actual.submission.defect,actual.contact)
    assert (d.required,d.defect_hh,d.pocket_cells,d.defect_hc,d.partial_tiles)==(396,73,2,75,43)
    assert canonical_digest(literal,GRID,True)==info['digest']
    print('20-triangle child; 67 full copies; 43 partial; 4 + 321/396; 66-copy comparator transported exactly')
    return registered, observed(fresh.submission)


def data_file(name):
    with lzma.open(ROOT/'data'/f'{name}.xz', mode='rt') as f:
        return f.read().splitlines()


def screen(parent, contacts, verify_every_origin):
    rows = [line.split() for line in data_file('third.tsv')]
    shapes={r[0]:frozenset(zip(*[iter(map(int,r[2:]))]*2)) for r in rows}
    records=[json.loads(line) for line in data_file('third-origins.jsonl')]
    assert len(records)==len(shapes)==22377 and {r['id'] for r in records}==set(shapes)
    assert Counter(len(r.get('edits',[r])) for r in records)=={1:921,2:21456}
    if verify_every_origin:
        for record in records:
            edits=record.get('edits',[record]);child=transform_cut(parent,edits)
            for edit in edits:
                assert contacts[edit['relative']]==edit['instances']
            reps=[GRID.normalize([o.apply(p) for p in child]) for o in GRID.orientations]
            assert min(reps,key=lambda cells:(sum(spans(cells,GRID)),cells))==tuple(sorted(shapes[record['id']]))
    stages={row[0]:row[1] for line in data_file('third-d5.tsv') if len(row:=line.split())==4}
    assert set(stages)==set(shapes) and Counter(stages.values())=={'NO_DEEP_CONTACT':20430,'ISOHEDRAL':1915,'FOUND':25,'TIMEOUT':7}
    periods={}
    for line in (ROOT/'data/third-periods.tsv').read_text().splitlines():
        sid, status, count, a,b,c,*transforms=line.split(); count,a,b,c=map(int,(count,a,b,c))
        assert status=='TILER' and len(transforms)==count and a>0 and c>0
        occ=Counter()
        for text in transforms:
            for x,y in motion(text).apply_all(shapes[sid]):
                x,i=divmod(x,3); y,j=divmod(y,3); assert i==j and i in (0,1)
                q,y=divmod(y,c); occ[(x-b*q)%a,y,i]+=1
        assert len(occ)==2*a*c==count*len(shapes[sid]) and set(occ.values())=={1}
        periods[sid]=count
    assert set(periods)=={k for k,v in stages.items() if v in ('FOUND','TIMEOUT')}
    patches=list((ROOT/'certificates').glob('*.heesch'))
    for path in patches:
        sid=path.name.split('.')[0]; v=witness(path)
        assert sid in periods and frozenset(v.submission.cells)==shapes[sid] and v.result.hc_verified==5
    assert len(patches)==28
    print('22,377 outlines; 28 independently replayed fifth rings across two passes; 32 periodic controls')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--all-origins',action='store_true')
    args=parser.parse_args()
    parent,contacts=construction();screen(parent,contacts,args.all_origins)
