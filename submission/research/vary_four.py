"""Exact local replacement of one or two level-four tiles, followed by outer packing."""
from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter, defaultdict
import itertools
import json
from pathlib import Path
import time

from pack import Packing, enumerate_tiles, encode_full, write_candidate
from heesch_verify import verify_witness
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of


def make_variants(o, max_replace=2):
    shape, grid, contact = frozenset(o.submission.cells), o.submission.grid, o.contact
    inner = [(l, xf) for l, xf in o.submission.patches[0] if l < 4]
    current = [(xf.apply_all(shape), xf) for l, xf in o.submission.patches[0] if l == 4]
    p3 = frozenset().union(*(xf.apply_all(shape) for l, xf in inner))
    full = o.hc_corona.patch_cells
    r4 = required_set(p3, contact)
    placements = enumerate_tiles(shape, grid, p3, r4)
    prev_partial = [(xf.apply_all(shape), xf) for _, xf in o.submission.defect.tiles]
    variants = {}
    for sz in range(1, max_replace + 1):
        for removed in itertools.combinations(range(len(current)), sz):
            outside = full.difference(*(current[i][0] for i in removed))
            remaining = r4 - outside
            oldcells = {current[i][0] for i in removed}
            local = [t for t in placements if not t.cells & outside and t.cells & remaining]
            cover = {c: [t for t in local if c in t.cells] for c in remaining}

            def search(rest, picked, used):
                if rest:
                    options = [[t for t in cover[c] if not used & t.cells] for c in rest]
                    for t in min(options, key=len):
                        search(rest - t.cells, picked + [t], used | t.cells)
                    return
                if set(t.cells for t in picked) == oldcells:
                    return
                new = outside | used
                if new in variants or holes_of(new, grid):
                    return
                r5 = required_set(new, contact)
                surviving = [(c, xf) for c, xf in prev_partial if not c & new and c & r5]
                pres = frozenset().union(*(c for c, xf in surviving))
                # Cheap, valid score from the existing partial packing after
                # deleting conflicts. This only orders candidates.
                hh = len(r5 - pres)
                d = len((r5 - pres) | holes_of(new | pres, grid))
                levels = inner + [(4, xf) for i,(c, xf) in enumerate(current) if i not in removed]
                levels.extend((4,t.xf) for t in picked)
                variants[new] = (d, hh, len(r5), levels, surviving, removed)

            search(remaining, [], frozenset())
    return variants


def main():
    options = ArgumentParser()
    options.add_argument("--seconds", type=float, default=8)
    options.add_argument("--limit", type=int, default=40)
    options.add_argument("--infile", type=Path, default=Path("work/inherited-baseline/best.heesch"))
    options.add_argument("--output", type=Path, default=Path("work/fourth-lane/variant"))
    options.add_argument("--budget", type=int, default=3)
    options.add_argument("--radius", type=int, default=2)
    opt = options.parse_args()
    source = opt.infile.read_text()
    o = verify_witness(source)
    variants = make_variants(o, opt.radius)
    # The denominator can improve the frontier only with 255 or more when d=3.
    key = lambda v: (v[0]/v[2], -v[2])
    ordered = sorted(variants.items(), key=lambda pair: key(pair[1]))
    print(json.dumps({"alternate_patches":len(ordered), "max_boundary":max(v[2] for _,v in ordered),
                      "retained_defects":dict(Counter(v[0] for _,v in ordered).most_common(15))}), flush=True)
    shape = frozenset(o.submission.cells)
    best = None
    for step, (p4, (raw_d, raw_hh, required, full, keep, removed)) in enumerate(ordered[:opt.limit]):
        if best is None or raw_d/required < best:
            from pack import Placement
            partial = [Placement(c,xf) for c,xf in keep]
            report = write_candidate(opt.output / 'best.heesch',source.splitlines()[0],full,partial,opt.infile,
                                     {'defect':raw_d,'hh':raw_hh,'required':required,
                                      'step':step,'mode':'retained','removed':removed})
            print(json.dumps({"NEW":report}), flush=True)
            best = raw_d/required
        packing = Packing(o.submission.grid, shape, p4, o.contact, opt.budget)
        packing.add_hint({c for c,xf in keep})
        partial, stats = packing.solve(time.monotonic()+opt.seconds, 3, 55436+step)
        if partial is not None:
            fraction = stats['defect']/stats['required']
            if fraction < best:
                best = fraction
                report = write_candidate(opt.output / 'best.heesch',source.splitlines()[0],
                                         full,partial,opt.infile,{**stats,'step':step,'mode':'optimized','removed':removed})
                print(json.dumps({"NEW":report}), flush=True)
        print(json.dumps({"step":step,"initial_defect":raw_d,"required":required,
                          "search":stats}), flush=True)


if __name__ == '__main__':
    main()
