"""Greedy upper bound retained from the public previous hex-packing solver."""
from heesch_verify.shape import holes_of

def holes_and_gaps(grid, patch, required, chosen):
    occupied = set().union(*(t.cells for t in chosen))
    gaps = required - occupied
    pockets = holes_of(patch | occupied, grid)
    return len(gaps | pockets), len(gaps)


def greedy(grid, patch, required, domain, carried, rng):
    selected = list(carried)
    occupied = set().union(*(t.cells for t in selected))
    ranked = list(domain)
    rng.shuffle(ranked)
    ranked.sort(key=lambda t: len(t.cells & required), reverse=True)
    for t in ranked:
        if t.cells.isdisjoint(occupied):
            occupied.update(t.cells)
            selected.append(t)
    d, h = holes_and_gaps(grid, patch, required, selected)
    # Breaking an enclosed pocket can pay for the newly uncovered cells.
    while True:
        removed = None
        for i in range(len(selected)):
            new_d,new_h = holes_and_gaps(grid,patch,required,selected[:i]+selected[i+1:])
            if new_d < d:
                removed = i
                d, h = new_d,new_h
        if removed is None:
            return selected, d, h
        selected.pop(removed)


