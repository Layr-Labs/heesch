"""Replay the two axial row shifts, the parent's tiling and the descendant's fourth-ring damage."""
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import json
import lzma

from heesch_verify import GRIDS, Xform, canonical_form, verify_witness
from heesch_verify.defect import verify_defect

HERE = Path(__file__).resolve().parent
GRID = GRIDS["H"]


def coordinates(values):
    values = list(map(int, values))
    return frozenset(zip(values[::2], values[1::2]))


def canonical(shape):
    return canonical_form(shape, GRID, True)


def row_shift(source, target):
    """Find a row interval and unit displacement that reproduce the target."""
    for basis in [(1, 0, 0, 1), (0, 1, 1, 0), (0, -1, 1, 1)]:
        a, b, d, e = basis
        local = [(a*x+b*y, d*x+e*y) for x, y in source]
        rows = [y for x, y in local]
        for low in range(min(rows)+1, max(rows)+1):
            for high in range(low, max(rows)+1):
                size = sum(low <= y <= high for x, y in local)
                if not 2 <= size <= len(local)-2:
                    continue
                for delta in [-1, 1]:
                    changed = [(x+delta if low <= y <= high else x, y) for x, y in local]
                    if canonical(changed) == canonical(target):
                        return dict(basis=basis, rows=[low, high], delta=delta, moved=size)
    raise AssertionError("No allowed band exchange produces the supplied target")


def quotient(cells, a, b, c):
    tally = Counter()
    for x, y in cells:
        q, ry = divmod(y, c)
        tally[(x-b*q) % a, ry] += 1
    return tally


def period(witness):
    row = (HERE/"parent-period.tsv").read_text().split()
    k, a, b, c = map(int, row[2:6])
    assert len(row[6:]) == k
    tally = Counter()
    for geom in row[6:]:
        pose = Xform(*map(int, geom.split(",")))
        assert pose.linear in {g.linear for g in GRID.orientations}
        tally.update(quotient(pose.apply_all(witness.submission.cells), a, b, c))
    assert tally == Counter((x, y) for x in range(a) for y in range(c))
    return dict(copies=k, cells=a*c, HNF=[a, b, c])


def proof_files(witness):
    declaration = witness.submission.proof
    assert declaration.m == 4 and declaration.fmt == "lrat"
    assert declaration.num_vars == 1174203 and declaration.num_clauses == 6985673
    assert declaration.core_clauses == 645630
    for fname, digest in [(declaration.file_name, declaration.payload_sha256),
                          (declaration.core_file, declaration.core_sha256)]:
        h = sha256()
        with lzma.open(HERE.parent/fname,"rb") as stream:
            while buf := stream.read(1024*1024):
                h.update(buf)
        assert digest == h.hexdigest(), fname
    return dict(m=declaration.m, variables=declaration.num_vars, clauses=declaration.num_clauses,
                core=declaration.core_clauses, formula=declaration.cnf_digest)


def main():
    parent = verify_witness((HERE/"parent.heesch").read_text())
    answer = verify_witness((HERE.parent/"best.heesch").read_text())
    original = (HERE/"parent-origin.tsv").read_text().split()
    a,b,c,ux,uy,vx,vy = map(int, original[1:8])
    old = coordinates(original[8:])
    transfer = (old-{(ux, uy)}) | {(vx, vy)}
    unit = Counter((x, y) for x in range(a) for y in range(c))
    assert quotient(old,a,b,c) == unit
    assert sum((unit-quotient(transfer,a,b,c)).values()) == 1
    assert canonical(transfer) == canonical(parent.submission.cells)
    assert parent.result.hc_verified == 5 and answer.result.hc_verified == 3
    lineage = (HERE/"lineage.tsv").read_text().split()
    middle = coordinates(lineage[3:])
    shifts = [row_shift(canonical(parent.submission.cells), middle),
              row_shift(canonical(middle), answer.submission.cells)]
    shape = frozenset(answer.submission.cells)
    checked = verify_defect(shape, GRID, answer.hc_corona, answer.submission.defect, answer.contact)
    tally = dict(Counter(level for level, pose in answer.submission.patches[0]))
    assert tally == {0:1, 1:6, 2:12, 3:20}
    assert (checked.defect_hc, checked.defect_hh, checked.required, checked.partial_tiles) == (19,18,183,30)
    pack = json.loads((HERE/"pack.json").read_text())
    assert pack["candidate_placements"] == 2076 and pack["final_status"]["status"] == "INFEASIBLE"
    print(json.dumps(dict(digest=answer.result.canonical_digest, parent=period(parent), shifts=shifts, proof=proof_files(answer),
                          completed=tally, partial=checked.partial_tiles, charged=checked.defect_hc,
                          uncovered=checked.defect_hh, required=checked.required,
                          geometric_score=str(3+Fraction(164,183)))))


if __name__ == "__main__":
    main()
