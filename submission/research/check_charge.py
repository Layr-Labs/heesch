"""Exhaust all possible edge-neighbor stars and evaluate five reciprocal contact weights."""
from collections import Counter
from pathlib import Path
import json
from heesch_verify import GRIDS, Xform, verify_witness
from heesch_verify.shape import holes_of
from replay import inverse

HERE=Path(__file__).resolve().parent
GRID=GRIDS['I']


def neighbor_images(shape, halo):
    images={}
    for orientation in GRID.orientations:
        copy=orientation.apply_all(shape) if hasattr(orientation,'apply_all') else {orientation.apply(p) for p in shape}
        shifts={(x-u,y-v) for x,y in halo for u,v in copy if GRID.translation_legal(x-u,y-v)}
        for dx,dy in shifts:
            image=frozenset((x+dx,y+dy) for x,y in copy)
            if shape & image:
                continue
            if len(holes_of(shape|image,GRID)) % len(shape):
                continue
            t=Xform(orientation.a,orientation.b,dx+orientation.c0,orientation.d,orientation.e,dy+orientation.f0)
            images[t]=image
    assert all(inverse(t) in images for t in images)
    return images


def check():
    record=json.loads((HERE/'data/fold27-integer.json').read_text())
    parent=verify_witness((HERE/'patches/fold27.heesch').read_text()).submission
    shape=frozenset(parent.cells)
    halo={q for p in shape for q in GRID.edge_neighbors(p)}-shape
    images=neighbor_images(shape,halo)
    # The finite tile has trivial stabilizer, so a copy has a unique relative pose.
    assert len(set(images.values()))==len(images)==record['poses'] and len(halo)==record['halo']
    weights={}
    for row in record['weights']:
        t=Xform(*row['transform']);opposite=inverse(t)
        assert t in images and t!=opposite and t not in weights and opposite not in weights
        weights[t]=row['weight'];weights[opposite]=-row['weight']
    owners={p:{t for t,im in images.items() if p in im} for p in halo}
    conflicts={t:{u for u,im in images.items() if im&images[t]} for t in images}
    distribution=Counter(); signatures=set()

    def fill(uncovered, choices, star):
        if not uncovered:
            distribution[sum(weights.get(t,0) for t in star)]+=1
            signed=Counter()
            for t in star:
                a,b=t.as_text(),inverse(t).as_text()
                if a!=b:
                    signed[min(a,b)]+=1 if a<b else -1
            signatures.add(tuple(sorted((s,q) for s,q in signed.items() if q)))
            return
        candidates=min((owners[p]&choices for p in uncovered),key=len)
        for t in candidates:
            fill(uncovered-images[t],choices-conflicts[t],star+(t,))

    fill(halo,set(images),())
    assert min(distribution)>0 and distribution=={1:36,3:9}
    assert sum(distribution.values())==record['stars']==45 and len(signatures)==record['distinct_signed_profiles']==41
    print('Folded 27-iamond: 133 poses, 45 complete edge stars, 41 signed profiles; charges +1 (36) and +3 (9)')

if __name__=='__main__':
    check()
