"""Boundary-word extraction and isohedral tiling criteria (spec §2.1 gate 1).

Square grid. The boundary word is the cyclic sequence of unit-edge directions
walking the outer boundary counterclockwise (interior on the left). Criteria:

- Translation criterion (Beauquier–Nivat): the cyclic boundary factors as
  A B C Â B̂ Ĉ, where X̂ is the reversed complement (the same run walked
  backwards), with up to two factors empty. Constructive: a match yields an
  explicit tiling by translations.
- Conway criterion: the cyclic boundary factors as A B C D E F where
  D = Â and each of B, C, E, F is centrosymmetric (symmetric under 180°
  rotation about its midpoint — for direction words, a literal palindrome),
  with some factors possibly empty. Constructive: half-turn tiling.

Failing both proves nothing (rotation-only and anisohedral tilers exist);
callers treat no-match as INCONCLUSIVE, never NON_TILER.

Boundary words longer than the per-grid cap are not tested (the criteria are
O(n^3)). The caps sit above the longest boundary any submittable shape can
have — a hole-free connected n-cell polyomino has perimeter <= 2n+2 = 402 at
the 200-cell cap, a polyhex <= 4n+2 = 802 — so layer 1 runs on EVERY legal
shape. (Audit finding V1: the old flat cap of 160 let a 132-cell
translation-tiling comb with boundary 178 skip the criteria, evade the
<= 8-cell tiler table, and score 5.0.)
"""

from __future__ import annotations

from .grids import Grid, SquareGrid, TriGrid

# Above the maxima: 402 (square) / 802 (hex) edges at the 200-cell cap.
MAX_BOUNDARY_SQUARE = 410
MAX_BOUNDARY_HEX = 810


def max_boundary(n_dirs: int) -> int:
    """Longest boundary word tested for a grid: 4 directions (square) or 6 (hex)."""
    return MAX_BOUNDARY_SQUARE if n_dirs == 4 else MAX_BOUNDARY_HEX

_TURN_PREFERENCE = (3, 0, 1)  # right turn, straight, left turn (mod 4 deltas)


class UnsupportedGrid(Exception):
    pass


class BoundaryError(Exception):
    pass


def boundary_word(cells, grid: Grid) -> list[int]:
    """Trace the outer boundary of a hole-free, edge-connected polyomino
    counterclockwise; return the direction word. Directions: 0=+x, 1=+y,
    2=-x, 3=-y. Cell (x, y) occupies the unit square [x,x+1] x [y,y+1].

    Pinch vertices (two diagonal cells meeting at a point) have four
    boundary edges; the walk takes the sharpest right turn, which keeps the
    interior contiguously on the left and yields one cycle."""
    if not isinstance(grid, SquareGrid):
        raise UnsupportedGrid(grid.grid_id)
    cellset = frozenset(cells)

    # Directed boundary edges, interior on the left.
    out_edges: dict[tuple[int, int], list[int]] = {}

    def add(v, d):
        out_edges.setdefault(v, []).append(d)

    for (x, y) in cellset:
        if (x, y - 1) not in cellset:
            add((x, y), 0)          # bottom edge, runs +x
        if (x + 1, y) not in cellset:
            add((x + 1, y), 1)      # right edge, runs +y
        if (x, y + 1) not in cellset:
            add((x + 1, y + 1), 2)  # top edge, runs -x
        if (x - 1, y) not in cellset:
            add((x, y + 1), 3)      # left edge, runs -y

    total = sum(len(v) for v in out_edges.values())
    start = min(out_edges)
    d0 = min(out_edges[start])
    word: list[int] = []
    cur, d = start, d0
    remaining = {v: set(ds) for v, ds in out_edges.items()}
    vec = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
    for _ in range(total):
        remaining[cur].discard(d)
        word.append(d)
        cur = (cur[0] + vec[d][0], cur[1] + vec[d][1])
        if cur == start and not any(remaining.values()):
            break
        cands = remaining.get(cur)
        if not cands:
            raise BoundaryError(f"walk dead-ends at {cur}")
        for delta in _TURN_PREFERENCE:
            nd = (d + delta) % 4
            if nd in cands:
                d = nd
                break
        else:
            raise BoundaryError(f"no continuation at {cur}")
    if len(word) != total:
        raise BoundaryError("outer boundary is not a single cycle")
    return word


def _comp(d: int, n_dirs: int = 4) -> int:
    return (d + n_dirs // 2) % n_dirs


def _hat(w: list[int], n_dirs: int = 4) -> list[int]:
    """Reversed complement: the same boundary run walked backwards."""
    return [_comp(d, n_dirs) for d in reversed(w)]


def _is_centrosymmetric(w: list[int]) -> bool:
    """Symmetric under 180° rotation about the run's midpoint. The half-turn
    maps direction d to d+2 and reverses traversal, so the rotated run read
    from its new start has the ORIGINAL direction sequence reversed twice —
    i.e. the condition on the word is a literal palindrome."""
    return w == w[::-1]


def _rotations(w: list[int]):
    for i in range(len(w)):
        yield w[i:] + w[:i]


def translation_criterion(word: list[int], n_dirs: int = 4) -> bool:
    """Beauquier–Nivat A B C Â B̂ Ĉ factorization over all rotations."""
    n = len(word)
    if n == 0 or n % 2 != 0 or n > max_boundary(n_dirs):
        return False
    half = n // 2
    for w in _rotations(word):
        for i in range(half + 1):
            if w[half:half + i] != _hat(w[:i], n_dirs):
                continue
            for j in range(i, half + 1):
                if w[half + i:half + j] != _hat(w[i:j], n_dirs):
                    continue
                if w[half + j:] == _hat(w[j:half], n_dirs):
                    return True
    return False


def _is_theta_drome(w: list[int], theta_quarter: int) -> bool:
    """Langerman–Winslow Θ-drome: X = Y · t_{Θ+180}(Ỹ). Even length; the
    second half is the (Θ+180°)-rotation of the reversed first half.
    theta_quarter counts CCW quarter turns (90-drome -> 1)."""
    n = len(w)
    if n % 2 != 0:
        return False
    rot = (theta_quarter + 2) % 4
    half = n // 2
    return all(w[half + i] == (w[half - 1 - i] + rot) % 4 for i in range(half))


def quarter_turn_criterion(word: list[int]) -> bool:
    """Langerman–Winslow quarter-turn form: some rotation of the cyclic
    boundary factors as W = A B C with A a palindrome and B, C 90-dromes
    (factors may be empty). Constructive: yields an isohedral tiling using
    90° rotations."""
    n = len(word)
    if n == 0 or n > MAX_BOUNDARY_SQUARE:
        return False
    for w in _rotations(word):
        for i in range(n + 1):
            if not _is_centrosymmetric(w[:i]):
                continue
            for j in range(i, n + 1):
                if _is_theta_drome(w[i:j], 1) and _is_theta_drome(w[j:], 1):
                    return True
    return False


def conway_criterion(word: list[int], n_dirs: int = 4) -> bool:
    """Conway A B C D E F factorization (D = Â; B, C, E, F palindromes)
    over all rotations."""
    n = len(word)
    if n == 0 or n > max_boundary(n_dirs):
        return False

    def splits_into_two_palindromes(w: list[int]) -> bool:
        return any(
            _is_centrosymmetric(w[:s]) and _is_centrosymmetric(w[s:])
            for s in range(len(w) + 1)
        )

    for w in _rotations(word):
        for la in range(n // 2 + 1):
            a_hat = _hat(w[:la], n_dirs)
            for k in range(la, n - la + 1):
                if w[k:k + la] != a_hat:
                    continue
                if splits_into_two_palindromes(w[la:k]) and splits_into_two_palindromes(
                    w[k + la:]
                ):
                    return True
    return False


# ---------------------------------------------------------------------------
# Hex boundary words (review finding 1b). Vertex coordinates follow
# heesch-sat's hexgrid.h scheme: cell (q, r) has vertex centre 3*(q, r) and
# six corners at the offsets below, listed counterclockwise. The travel
# alphabet is the six corner-to-corner vectors, indexed so that the opposite
# direction is +3 mod 6 — which is what _hat/_comp(n_dirs=6) require.

_HEX_CORNERS = ((1, 1), (-1, 2), (-2, 1), (-1, -1), (1, -2), (2, -1))
_HEX_TRAVEL = tuple(
    (_HEX_CORNERS[(i + 1) % 6][0] - _HEX_CORNERS[i][0],
     _HEX_CORNERS[(i + 1) % 6][1] - _HEX_CORNERS[i][1])
    for i in range(6)
)
_HEX_TRAVEL_INDEX = {v: i for i, v in enumerate(_HEX_TRAVEL)}
# CCW walk with interior on the left: prefer the sharpest right turn at
# multi-choice (pinch) vertices, mirroring the square walker's rule.
_HEX_TURN_PREFERENCE = (5, 4, 0, 1, 2, 3)


def _hex_side_corners(grid):
    """For each neighbor direction index d, the (i, j) corner indices of the
    shared edge, oriented so corner[i] -> corner[j] walks CCW around the
    cell (interior on the left). Computed from the grid tables at first use
    rather than hand-transcribed."""
    out = []
    for d, (dq, dr) in enumerate(grid._NEIGH):
        shared = []
        for i, (ox, oy) in enumerate(_HEX_CORNERS):
            # corner of this cell (centre 0,0): (ox, oy); corners of the
            # neighbor: 3*(dq,dr) + offsets. Shared iff present in both sets.
            if any(ox == 3 * dq + nx and oy == 3 * dr + ny
                   for nx, ny in _HEX_CORNERS):
                shared.append(i)
        assert len(shared) == 2, (d, shared)
        i, j = shared
        # CCW order around the cell: j must be i+1 (mod 6)
        if (i + 1) % 6 == j:
            out.append((i, j))
        else:
            assert (j + 1) % 6 == i
            out.append((j, i))
    return tuple(out)


_hex_side_corner_cache = {}


def hex_boundary_word(cells, grid) -> list[int]:
    """Trace the outer boundary of a hole-free, edge-connected polyhex
    counterclockwise; return the 6-letter direction word."""
    key = id(type(grid))
    if key not in _hex_side_corner_cache:
        _hex_side_corner_cache[key] = _hex_side_corners(grid)
    side_corners = _hex_side_corner_cache[key]
    cellset = frozenset(cells)

    out_edges: dict[tuple[int, int], list[int]] = {}
    total = 0
    for (q, r) in cellset:
        for d, n in enumerate(grid.edge_neighbors((q, r))):
            if n in cellset:
                continue
            i, j = side_corners[d]
            vi = (3 * q + _HEX_CORNERS[i][0], 3 * r + _HEX_CORNERS[i][1])
            letter = (i + 0) % 6  # travel vector corner[i]->corner[i+1]
            out_edges.setdefault(vi, []).append(letter)
            total += 1

    start = min(out_edges)
    d0 = min(out_edges[start])
    word: list[int] = []
    cur, d = start, d0
    remaining = {v: set(ds) for v, ds in out_edges.items()}
    for _ in range(total):
        remaining[cur].discard(d)
        word.append(d)
        vec = _HEX_TRAVEL[d]
        cur = (cur[0] + vec[0], cur[1] + vec[1])
        if cur == start and not any(remaining.values()):
            break
        cands = remaining.get(cur)
        if not cands:
            raise BoundaryError(f"hex walk dead-ends at {cur}")
        for delta in _HEX_TURN_PREFERENCE:
            nd = (d + delta) % 6
            if nd in cands:
                d = nd
                break
        else:
            raise BoundaryError(f"no continuation at {cur}")
    if len(word) != total:
        raise BoundaryError("hex outer boundary is not a single cycle")
    return word


# ---------------------------------------------------------------------------
# Iamond boundary words (audit finding V2). The triangular grid embeds into a
# vertex lattice V(i, j): Kaplan up-triangle (x, y) is rhombus (x//3, y//3) and
# down-triangle (x, y) is rhombus ((x-1)//3, (y-1)//3). Each triangle is one of
# the two triangles of its rhombus; boundary edges are steps between vertices,
# whose six directions (opposite = +3 mod 6, matching _hat/_comp with
# n_dirs=6) let the Beauquier–Nivat / Conway criteria run unchanged.
#
# Validated before shipping (a wrong TILER rejects a legitimate submission):
# the full enumeration of all 112 free polyiamonds n<=8 yields ZERO shapes the
# criteria call TILER that are absent from the exhaustive known-tiler table,
# every side-k triangle is proven TILER, and no corpus iamond non-tiler is a
# false TILER. See tests/test_iamond_boundary.py.

# The six vertex-lattice directions; opposite(d) = (d + 3) % 6.
_TRI_DIRS = ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1))
_TRI_DIR_INDEX = {v: i for i, v in enumerate(_TRI_DIRS)}
_TRI_TURN_PREFERENCE = (5, 4, 0, 1, 2, 3)  # sharpest right first, as for hexes


def _tri_ccw_corners(cell):
    """The three vertex-lattice corners of a triangle, counterclockwise
    (interior on the left). Orders precomputed from the lattice embedding."""
    x, y = cell
    if x % 3 == 0:  # up triangle
        i, j = x // 3, y // 3
        return ((i, j), (i + 1, j), (i, j + 1))
    i, j = (x - 1) // 3, (y - 1) // 3  # down triangle
    return ((i + 1, j + 1), (i, j + 1), (i + 1, j))


def iamond_boundary_word(cells, grid) -> list[int]:
    """Trace the outer boundary of a hole-free, edge-connected polyiamond
    counterclockwise; return the 6-letter direction word."""
    if not isinstance(grid, TriGrid):
        raise UnsupportedGrid(getattr(grid, "grid_id", "?"))
    cellset = frozenset(cells)

    out_edges: dict[tuple[int, int], list[int]] = {}
    total = 0
    for c in cellset:
        corners = _tri_ccw_corners(c)
        in_neighbors = frozenset(n for n in grid.edge_neighbors(c) if n in cellset)
        shared_edges = frozenset(
            frozenset(e) for n in in_neighbors
            for e in (set(_tri_ccw_corners(c)) & set(_tri_ccw_corners(n)),)
            if len(e) == 2
        )
        for k in range(3):
            va, vb = corners[k], corners[(k + 1) % 3]
            if frozenset((va, vb)) in shared_edges:
                continue  # interior edge shared with an in-set neighbor
            d = _TRI_DIR_INDEX[(vb[0] - va[0], vb[1] - va[1])]
            out_edges.setdefault(va, []).append(d)
            total += 1

    if total == 0:
        raise BoundaryError("empty polyiamond boundary")
    start = min(out_edges)
    d0 = min(out_edges[start])
    word: list[int] = []
    cur, d = start, d0
    remaining = {v: set(ds) for v, ds in out_edges.items()}
    for _ in range(total):
        remaining[cur].discard(d)
        word.append(d)
        vec = _TRI_DIRS[d]
        cur = (cur[0] + vec[0], cur[1] + vec[1])
        if cur == start and not any(remaining.values()):
            break
        cands = remaining.get(cur)
        if not cands:
            raise BoundaryError(f"iamond walk dead-ends at {cur}")
        for delta in _TRI_TURN_PREFERENCE:
            nd = (d + delta) % 6
            if nd in cands:
                d = nd
                break
        else:
            raise BoundaryError(f"no continuation at {cur}")
    if len(word) != total:
        raise BoundaryError("iamond outer boundary is not a single cycle")
    return word
