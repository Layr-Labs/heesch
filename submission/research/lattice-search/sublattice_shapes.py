"""Sample hex outlines by deforming small clusters on an Eisenstein sublattice."""
import hashlib
import random
from pathlib import Path

from heesch_verify.canonical import canonical_form
from heesch_verify.grids import GRIDS
from heesch_verify.shape import connected, holes_of


GRID = GRIDS["H"]


def rim(cells):
    return {n for c in cells for n in GRID.edge_neighbors(c)} - cells


def small_hexes():
    forms = {1: [((0, 0),)]}
    for n in range(2, 8):
        new = set()
        for form in forms[n-1]:
            parent = frozenset(form)
            new.update(canonical_form(parent | {q}, GRID, True) for q in rim(parent))
        forms[n] = sorted(new)
    return forms


def shape_trial(rng, forms):
    # Integer multiplication by a + b*w, with w*w=w-1.
    a,b = rng.choice([(1,1),(2,0),(2,1)])
    index = a*a + a*b + b*b
    size = rng.choice({3:[6,7],4:[5],7:[3]}[index])
    macro = rng.choice(forms[size])
    micro = rng.choice(forms[index])
    residues = {(((a+b)*x+b*y) % index, (-b*x+a*y) % index) for x,y in micro}
    if len(residues) != index:
        return None
    anchors = [(a*x-b*y, b*x+(a+b)*y) for x,y in macro]
    cluster = []
    for center in anchors:
        turn = GRID.orientations[0 if rng.random() < .65 else rng.randrange(12)]
        points = [turn.apply(c) for c in micro]
        cluster.extend((x+center[0],y+center[1]) for x,y in points)
    cells = frozenset(cluster)
    if len(cluster)-len(cells) > 3 or not connected(cells, GRID):
        return None
    target = rng.choice([18,19,20])
    while len(cells)>target:
        exterior = [q for q in sorted(cells) if any(p not in cells for p in GRID.edge_neighbors(q))]
        cells = cells - {rng.choice(exterior)}
        if not connected(cells, GRID):
            return None
    while len(cells)<target:
        cells = cells | {rng.choice(sorted(rim(cells)))}
    if rng.random() < .4:
        edge = [q for q in sorted(cells) if any(p not in cells for p in GRID.edge_neighbors(q))]
        q = rng.choice(edge)
        cells = cells - {q}
        if not connected(cells,GRID):
            return None
        cells = cells | {rng.choice(sorted(rim(cells)))}
    if holes_of(cells, GRID):
        return None
    return canonical_form(cells, GRID, True)


def main():
    d=Path(__file__).resolve().parent
    rng=random.Random(3913370)
    forms=small_hexes()
    seen={line.split()[0] for p in [d/"grow17.tsv",d/"rows50k.txt"] for line in p.read_text().splitlines()}
    size=0
    with (d/"sublattice.tsv").open("w") as result:
        for _ in range(1000000):
            form=shape_trial(rng,forms)
            if form is None:
                continue
            text="H? "+" ".join(f"{x} {y}" for x,y in form)
            digest=hashlib.sha256(text.encode()).hexdigest()[:20]
            if digest in seen:
                continue
            seen.add(digest)
            result.write(f"{digest} {text}\n")
            size+=1
            if size==40000:
                break
    print(f"Saved {size} unique Eisenstein-lattice constructions.")


if __name__ == "__main__":
    main()
