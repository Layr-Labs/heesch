"""Construct a partial corona and measure its edge-flood defects on two bit planes."""
import argparse
from pathlib import Path
import random

from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.patch import required_set
from heesch_verify.transform import Xform


def placements(shape, grid, patch, required):
    unique = {}
    for sym in grid.orientations:
        local = {sym.apply(p) for p in shape}
        for dx,dy in {(x-a,y-b) for x,y in required for a,b in local
                      if grid.translation_legal(x-a,y-b)}:
            cells = frozenset((x+dx,y+dy) for x,y in local)
            if not cells & patch:
                unique.setdefault(cells, Xform(sym.a,sym.b,sym.c0+dx,sym.d,sym.e,sym.f0+dy))
    return sorted(unique.items(),key=lambda t: tuple(sorted(t[0])))


def pack(seed, output, rounds=400, random_seed=1217):
    text = seed.read_text().split("#DEFECT")[0].rstrip()+"\n"
    w = verify_witness(text)
    g = w.submission.grid
    shape = frozenset(w.submission.cells)
    full = w.hc_corona.patch_cells
    required = required_set(full,w.contact)
    proposals = placements(shape,g,full,required)
    world = set(full).union(required,*(cells for cells,_ in proposals))
    xmin = min(x//3 for x,y in world)-1
    ymin = min(y//3 for x,y in world)-1
    width = max(x//3 for x,y in world)-xmin+2
    height = max(y//3 for x,y in world)-ymin+2
    all_sites = (1<<(height*width))-1
    left = sum(1<<(k*width) for k in range(height))
    right = left<<(width-1)
    edge = (1<<width)-1
    border = left|right|edge|(edge<<((height-1)*width))

    def bits(points):
        r,s = 0,0
        for x,y in points:
            bit = 1<<((y//3-ymin)*width+x//3-xmin)
            if x%3:
                s |= bit
            else:
                r |= bit
        return r,s

    base0,base1 = bits(full)
    req0,req1 = bits(required)
    codes = [bits(c) for c,_ in proposals]
    gains = [len(required & c) for c,_ in proposals]
    size = range(len(codes))

    def measure(z,t):
        vacant0,vacant1 = all_sites^z, all_sites^t
        ext0 = ext1 = border
        while True:
            new0 = (ext0|ext1|((ext1&~right)<<1)|(ext1<<width))&vacant0
            new1 = (ext1|new0|((new0&~left)>>1)|(new0>>width))&vacant1
            if new0==ext0 and new1==ext1:
                break
            ext0,ext1 = new0,new1
        gaps0,gaps1 = req0 & vacant0, req1 & vacant1
        cost = ((vacant0^ext0)|gaps0).bit_count()+((vacant1^ext1)|gaps1).bit_count()
        return cost,gaps0.bit_count()+gaps1.bit_count()

    rng = random.Random(random_seed)
    best, incumbent = (10**9,10**9), []
    level = w.hc_corona.max_level+1
    for iteration in range(rounds):
        chosen = [i for i in incumbent if rng.random()>.30] if iteration%10 else []
        z,t = base0,base1
        for i in chosen:
            a,b = codes[i]
            z,t = z|a,t|b
        spread = rng.uniform(.3,6)
        for i in sorted(size,key=lambda i: gains[i]+spread*rng.random(), reverse=True):
            a,b = codes[i]
            if not (z&a or t&b):
                z,t = z|a,t|b
                chosen.append(i)
        score = measure(z,t)
        rng.shuffle(chosen)
        while True:
            changed = False
            for i in chosen[:]:
                a,b = codes[i]
                candidate = measure(z^a,t^b)
                if candidate < score:
                    score = candidate
                    chosen.remove(i)
                    z,t = z^a,t^b
                    changed = True
            if not changed:
                break
        if score < best:
            best,incumbent = score,chosen[:]
            partial = text+f"#DEFECT {level} {score[0]} {score[1]} {len(required)}\n{len(chosen)}\n"
            partial += "".join(f"{level} {proposals[i][1].as_text()}\n" for i in chosen)
            check = verify_witness(partial)
            result = verify_defect(shape,g,check.hc_corona,check.submission.defect,check.contact)
            assert result.defect_hc==score[0] and result.defect_hh==score[1]
            output.write_text(partial)
    return best,len(required),len(incumbent)


if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("input",type=Path)
    ap.add_argument("output",type=Path)
    ap.add_argument("--rounds",type=int,default=400)
    args=ap.parse_args()
    print(pack(args.input,args.output,args.rounds))
