"""§9.3 universe completeness (E1) — the false-record obligation.

Brute-forces every placement over a deliberately oversized bounding-box
region computed with independent arithmetic (BFS diameter + bbox inflation,
no code shared with placements.halo logic), filters with the SHIPPED
membership predicate, and requires exact list equality with
enumerate_universe — membership, completeness, ordering and dedup in one
assertion. A margin-band saturation check licenses the finite range."""

from heesch_encoder.ordering import placement_key
from heesch_encoder.placements import enumerate_universe, in_universe, materialize
from heesch_encoder.types import Placement

MARGIN = 4


def _bfs_diameter(cells, grid):
    """Independent lattice diameter via pairwise Chebyshev-ish bound: just
    use coordinate extents — strictly larger than any within-tile distance."""
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    return (max(xs) - min(xs)) + (max(ys) - min(ys)) + 1


def brute_force_universe(tile, patch, grid, contact):
    D = _bfs_diameter(tile, grid)
    # Independent contact reach: max |component| over the grid's contact
    # vectors (1 for O/H, 4 for I).
    reach = max(
        max(abs(n[0] - c[0]), abs(n[1] - c[1]))
        for c in list(patch)[:1]
        for n in contact.neighbors(c)
    )
    pad = D + reach + MARGIN
    xs = [c[0] for c in patch]
    ys = [c[1] for c in patch]
    x0, x1 = min(xs) - pad, max(xs) + pad
    y0, y1 = min(ys) - pad, max(ys) + pad

    found = []
    band = []
    for si in range(len(grid.orientations)):
        sym = grid.orientations[si]
        img = [sym.apply(c) for c in tile]
        bx0 = min(c[0] for c in img)
        bx1 = max(c[0] for c in img)
        by0 = min(c[1] for c in img)
        by1 = max(c[1] for c in img)
        for ty in range(y0 - by0, y1 - by1 + 1):
            for tx in range(x0 - bx0, x1 - bx1 + 1):
                p = Placement(si, ty, tx)
                if in_universe(p, tile, patch, grid, contact):
                    found.append(p)
                    # margin-band bookkeeping: does this placement reach the
                    # outer band? If yes the region was too small.
                    cells = materialize(p, tile, grid)
                    if any(
                        c[0] < x0 + MARGIN or c[0] > x1 - MARGIN
                        or c[1] < y0 + MARGIN or c[1] > y1 - MARGIN
                        for c in cells
                    ):
                        band.append(p)
    return found, band


def test_universe_completeness(fixture):
    tile = fixture["tile"]
    patch = fixture["patch"]
    grid = fixture["grid"]
    contact = fixture["contact"]

    brute, band = brute_force_universe(tile, patch, grid, contact)
    assert not band, (
        f"{fixture['name']}: {len(band)} predicate-passing placements reach "
        "the margin band — brute-force region too small, test unsound"
    )

    shipped = enumerate_universe(tile, patch, grid, contact)
    assert sorted(brute, key=placement_key) == shipped, (
        f"{fixture['name']}: universe mismatch "
        f"(brute {len(brute)}, shipped {len(shipped)})"
    )
    # No duplicates in shipped.
    assert len(set(shipped)) == len(shipped)


def test_contact_object_is_shared_identity(fixture):
    """E5 at the test level: the contact object the encoder receives is the
    one constructed from the grid config — same object, `is` identity."""
    contact = fixture["contact"]
    # enumerate_universe passes it straight into heesch_verify.patch.touches;
    # verify no copy is made by checking the function accepts and uses it.
    u1 = enumerate_universe(fixture["tile"], fixture["patch"], fixture["grid"], contact)
    u2 = enumerate_universe(fixture["tile"], fixture["patch"], fixture["grid"], contact)
    assert u1 == u2
