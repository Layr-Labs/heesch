"""Replay the 20-square construction, witness geometry, defect score and proof binding using Python's standard library."""
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import json
import lzma

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
EDGE = [(0, 1), (1, 0), (0, -1), (-1, 0)]
POINT = [(x, y) for x in (-1, 0, 1) for y in (-1, 0, 1) if x or y]
SYMMETRIES = [(a, b, d, e) for a, b in EDGE for d, e in EDGE if a*d + b*e == 0]


def motion(text):
    assert text.startswith('<') and text.endswith('>')
    t = tuple(map(int, text[1:-1].split(',')))
    assert len(t) == 6 and (t[0], t[1], t[3], t[4]) in SYMMETRIES
    return t


def placed(t, points):
    a, b, c, d, e, f = t
    return {(a*x+b*y+c, d*x+e*y+f) for x,y in points}


def relative(points, neighbors):
    return {(x+u, y+v) for x,y in points for u,v in neighbors} - set(points)


def canonical(points):
    variants = []
    for a,b,d,e in SYMMETRIES:
        image = placed((a,b,0,d,e,0),points)
        lo = min(x for x,y in image), min(y for x,y in image)
        variants.append(tuple(sorted((x-lo[0], y-lo[1]) for x,y in image)))
    return min(variants)


def empty_pockets(points):
    lo_x = min(x for x,y in points)-1
    hi_x = max(x for x,y in points)+1
    lo_y = min(y for x,y in points)-1
    hi_y = max(y for x,y in points)+1
    queue = [(lo_x,lo_y)]
    exterior = set(queue)
    for x,y in queue:
        for u,v in EDGE:
            q = x+u,y+v
            if lo_x <= q[0] <= hi_x and lo_y <= q[1] <= hi_y and q not in exterior and q not in points:
                exterior.add(q)
                queue.append(q)
    return {(x,y) for x in range(lo_x,hi_x+1) for y in range(lo_y,hi_y+1)} - set(points) - exterior


def patch(lines, start, shape):
    n = int(lines[start])
    copies = []
    occupied = set()
    for line in lines[start+1:start+n+1]:
        level, matrix = line.split()
        cells = placed(motion(matrix),shape)
        assert not (cells & occupied)
        occupied.update(cells)
        copies.append((int(level),cells))
    return copies,occupied,start+n+1


def check():
    info = json.loads((HERE/'candidate.json').read_text())
    lines = (PACKAGE/'best.heesch').read_text().splitlines()
    coordinates = lines[0].split()
    assert coordinates[0] == 'O' and lines[1] == '~ 2 2 1'
    nums = tuple(map(int,coordinates[1:]))
    tile = set(zip(nums[::2],nums[1::2]))
    assert len(tile) == len(nums)//2 == 20 and not empty_pockets(tile)
    queue = [min(tile)]
    reached = set(queue)
    for p in queue:
        for n in relative([p], EDGE) & tile - reached:
            reached.add(n)
            queue.append(n)
    assert reached == tile
    original = set(map(tuple,info['quotient']['candidate']))
    normalized = set(canonical(tile))
    assert canonical(original) == tuple(sorted(normalized))
    A,B,C = info['quotient']['basis']
    residues = Counter()
    for line in info['quotient']['motions']:
        for x,y in placed(motion(line),original):
            j,v = divmod(y,C)
            residues[(x-B*j)%A,v] += 1
    vacant = {(u,v) for u in range(A) for v in range(C)} - set(residues)
    assert set(residues.values()) == {1} and len(residues) == 40
    assert vacant == set(map(tuple,info['quotient']['vacancies'])) and len(vacant) == 2
    donor = set(map(tuple,info['donor']))
    assert len(donor)==19 and len(donor-original)==2 and len(original-donor)==3
    full,inner,offset = patch(lines,2,tile)
    assert full[0] == (0,tile) and sum(level==0 for level,_ in full)==1
    accumulated=set(tile)
    for rank in (1,2):
        rows=[cells for level,cells in full if level==rank]
        halo=relative(accumulated,POINT)
        assert rows and all(cells & halo for cells in rows)
        if rank==2:assert all(not cells & relative(tile,POINT) for cells in rows)
        accumulated.update(*rows)
        assert halo <= accumulated and not empty_pockets(accumulated)
    assert accumulated==inner
    tag,level,claimed_hc,claimed_hh,claimed_required = lines[offset].split()
    assert tag == '#DEFECT' and level == '3'
    partial,outer,offset = patch(lines,offset+1,tile)
    need = relative(inner,POINT)
    assert not outer & inner and all(level==3 and cells & need for level,cells in partial)
    missed = need - outer
    pockets = empty_pockets(inner | outer) - missed
    assert tuple(map(int,(claimed_hc,claimed_hh,claimed_required))) == (len(missed|pockets),len(missed),len(need)) == tuple(info['defect_counts'])
    scalar = 3 - Fraction(len(missed|pockets), len(need))
    assert str(scalar) == info['score_fraction']
    assert lines[offset:offset+2] == ['#PROOF 1', 'encoder heesch-encoder/v2 2 3']
    _,cnf,variables,clauses = lines[offset+2].split()
    _,file_name,fmt,compression,proof_digest = lines[offset+3].split()
    assert (fmt,compression) == ('drat','xz') and file_name == 'proof.drat.xz'
    upper = info['upper']
    assert (cnf,int(variables),int(clauses)) == (upper['cnf_sha256'],upper['cnf_variables'],upper['cnf_clauses'])
    assert proof_digest == upper['proof_sha256'] == sha256(lzma.decompress((PACKAGE/file_name).read_bytes())).hexdigest()
    assert 's VERIFIED' in (HERE/'drat-replay.log').read_text()
    return dict(tile_cells=len(tile),vacant_residues=sorted(vacant),donor_area=len(donor),solid_rings=2,partial_required=len(need),partial_uncovered=len(missed),pocket_cells=len(pockets),score=str(scalar),proof_sha256=proof_digest)


if __name__ == '__main__':
    print(json.dumps(check(),indent=2))
