# Ground truth transcribed from isohedral/heesch-sat (Phase 0)

Source: github.com/isohedral/heesch-sat @ master, cloned 2026-08-06 (BSD-3).
Everything below is transcribed from source, not inferred. File references are
to that repo's `src/`.

## Transform representation (`geom.h`)

`xform {a,b,c,d,e,f}` applies as `x' = a·x + b·y + c`, `y' = d·x + e·y + f`.
Printed as `<a,b,c,d,e,f>` (comma-separated, angle brackets, ints).

## File format (`tileio.h`, `common.h`)

```
<G> x1 y1 x2 y2 ... xn yn      # G ∈ {O,H,I,...}; space-separated ints; "G?" prefix = naked/unclassified
~ hc hh P                      # NONTILER record; other record chars: ? O(hole) ! I # $
N                              # patch size (placement count)
<level> <a,b,c,d,e,f>          # one per line; level = corona index, 0 = central
```

- Reader (`IntReader`) tokenizes by scanning for digit/'-' runs — it is extremely
  tolerant: any non-digit separator works. Our parser can be stricter (spec §4
  says reject trailing garbage) but must accept the canonical output format above.
- Patches: `hc` patch first; a second patch present only when `hh > hc`
  (`setNonTiler`: pushes hh_patch only `if hh_ > hc_`). Matches spec `P=2 ⟺ hh=hc+1`.
- Hc=0 ⇒ patches may be absent ("Patches can be implicit if Heesch number is zero").
- Grid letters: `O` omino, `H` hex, `I` iamond (also o/T/A/D/K/h/B for other grids — out of scope).

## OminoGrid (`ominogrid.h`) — square

- Cells `(x,y)`, all translations legal (`translatable` always true).
- Edge neighbours (4): `(0,-1) (-1,0) (1,0) (0,1)`.
- All/contact neighbours (8): adds diagonals — **general contact = any shared
  boundary point** (8-neighbour). This freezes spec §11: contact = boundary point.
- 8 orientations, frozen listing order (index = our symmetry_index):
  ```
  0: < 1, 0,0,  0, 1,0>   identity
  1: < 0,-1,0,  1, 0,0>   rot90   (x,y)→(−y,x)
  2: <-1, 0,0,  0,-1,0>   rot180
  3: < 0, 1,0, -1, 0,0>   rot270
  4: <-1, 0,0,  0, 1,0>   mirror-x
  5: < 0,-1,0, -1, 0,0>
  6: < 1, 0,0,  0,-1,0>   mirror-y
  7: < 0, 1,0,  1, 0,0>
  ```
  (indices 0–3 det=+1, 4–7 det=−1)

## HexGrid (`hexgrid.h`) — hex, axial coords

- Edge and contact neighbours **coincide** (6): `(0,-1) (0,1) (1,0) (-1,0) (1,-1) (-1,1)`
  (`getEdgeNeighbourVectors` returns `all_neighbours`) — spec §6's "verify against
  heesch-sat" item is confirmed: no vertex-only hex contact.
- 12 orientations, frozen order (first 6 rotations det=+1, last 6 reflections):
  ```
  0: < 1, 0,0,  0, 1,0>    6: < 0, 1,0,  1, 0,0>
  1: < 0,-1,0,  1, 1,0>    7: <-1, 0,0,  1, 1,0>
  2: <-1,-1,0,  1, 0,0>    8: <-1,-1,0,  0, 1,0>
  3: <-1, 0,0,  0,-1,0>    9: < 0,-1,0, -1, 0,0>
  4: < 0, 1,0, -1,-1,0>   10: < 1, 0,0, -1,-1,0>
  5: < 1, 1,0, -1, 0,0>   11: < 1, 1,0,  0,-1,0>
  ```
  R60 = index 1: (x,y)→(−y, x+y). All translations legal.

## IamondGrid (`iamondgrid.h`) — triangular. NOT (x+y) mod 2!

- **Orientation from `x mod 3`**: `TRIANGLE_UP ⟺ x ≡ 0 (mod 3)` (C++ `%`: up iff
  `x_ % 3 == 0`; canonical cells sit at x ≡ 0 or 1 mod 3 — origins `(0,0)` up,
  `(1,-2)` down). y is unconstrained mod 3? No: translations…
- **Legal translations**: `translatable(p,q) ⟺ (p.x − q.x) % 3 == 0` — only x is
  constrained. Lattice basis V1=(3,0), V2=(0,3) — but any (dx,dy) with dx≡0 mod 3
  is legal (dy free).
- Edge neighbours (3), parity-dependent:
  - up ("black", x≡0):  `(1,1) (-2,1) (1,-2)`
  - down ("grey"):      `(-1,-1) (2,-1) (-1,2)`
- Contact neighbours (12 each), parity-dependent:
  - up:   `(3,0) (0,3) (-3,3) (-3,0) (0,-3) (3,-3) (1,1) (-2,4) (-2,1) (-2,-2) (1,-2) (4,-2)`
  - down: `(3,0) (0,3) (-3,3) (-3,0) (0,-3) (3,-3) (2,2) (2,-1) (2,-4) (-1,-1) (-4,2) (-1,2)`
- 12 orientations — **affine**: first 6 have c=f=0, last 6 have c=f=1 (these swap
  up/down orientation classes):
  ```
  0: < 1, 0,0,  0, 1,0>    6: < 0,-1,1, -1, 0,1>
  1: <-1,-1,0,  1, 0,0>    7: <-1, 0,1,  1, 1,1>
  2: < 0, 1,0, -1,-1,0>    8: < 1, 1,1,  0,-1,1>
  3: < 1, 0,0, -1,-1,0>    9: < 1, 1,1, -1, 0,1>
  4: < 0, 1,0,  1, 0,0>   10: <-1, 0,1,  0,-1,1>
  5: <-1,-1,0,  0, 1,0>   11: < 0,-1,1,  1, 1,1>
  ```
  Symmetry membership for a placement `<a,b,c,d,e,f>`: linear part must equal one
  of the 12 linear parts, and `(c − c₀, f − f₀)` must be a legal translation
  (i.e. `(c − c₀) ≡ 0 mod 3`) where `(c₀,f₀)` is that orientation's affine offset.
  Which of the 6 rotations are det=+1 vs reflections: indices 0,1,2 are rotations
  (det +1: id, and two with det... VERIFY numerically during implementation);
  compute det per matrix rather than trusting position.

## Hole / connectivity semantics (`shape.h`)

- `simplyConnected()`: shape's **vertex halo** (contact-neighbour set minus shape)
  must be a single **edge-connected** component. NOT a flood fill from infinity.
  For our Stage 2 we implement the spec's padded-bbox flood fill but add a
  differential test against this halo-connectivity definition on random shapes;
  any disagreement is a convention bug to chase (likely equivalent for
  edge-connected shapes).
- Halo/border (`getHaloAndBorder`): halo = contact neighbours of the shape not in
  it; border = shape cells with at least one non-shape contact neighbour.

## Corona/contact semantics (`cloud.h`, `heesch.h`)

- A copy T·S is **adjacent** (legal corona contact) iff some border cell of T·S
  lands on a **vertex-halo** cell of S and the pair doesn't overlap ⇒ contact =
  share ≥1 boundary point. Confirms §11 default.
- heesch-sat further splits adjacencies: `adjacent_` (pair forms simply connected
  union) vs `adjacent_hole_` (pair encloses a hole). For the outermost corona
  under Hc it forbids hole-adjacencies, and iteratively excludes larger
  multi-tile holes on SAT models (CEGAR). This is exactly the loop our encoder
  (v1 spec §4 clauses; multilevel spec §2.1 weak configurations) avoids by
  encoding hole-allowed coronas only. Our geometric witness checker checks holes
  directly by flood fill — no pairwise approximation needed.
- `surroundable_ = false` when some halo cell admits no legal placement ⇒ Hc=0
  immediately (mirrors our "empty coverage clause" case, encoder spec §4.3).
- Default corona search cap in `sat` tool: `-maxlevel` 7 (Revision uses 12).

## Data / fixtures

- Repo `data/hex/nontile-{6..10}.txt`: unclassified (`H?`) non-tiling n-hexes.
  Useful as classifier-agreement corpus once our pipeline runs; witnesses must be
  generated (build heesch-sat, or use our own brute-force for small Hc).
- Kaplan 2022 paper (arXiv 2105.09438, "Heesch numbers of unmarked polyforms")
  Figs 1/7/8/9 give the minimal-cell shapes for Hc=1..4 per grid — transcribe
  coordinates for tests/corpus during Phase 2.
- heesch-sat has no square/iamond data checked in.

## Consequences for our implementation

1. Contact convention: **boundary point**, frozen (calibration will re-confirm).
2. Hex: single 6-neighbour relation for both modes.
3. TriGrid: use Kaplan's x-mod-3 encoding verbatim (cells, neighbours,
   orientations, translation lattice). Do not invent a parity bit.
4. Symmetry membership check must be affine-aware (linear part + offset-translation
   legality), not just matrix membership — on O and H the offset rule degenerates
   to "any translation", so one code path covers all grids.
5. Parser: accept heesch-sat canonical output byte-for-byte; stricter on garbage.
6. `span` is not computed anywhere in heesch-sat grids (no span_x/span_y) — the
   ≤29 span limit is Epoch's addition; define span in cell coordinates per grid
   and document (bbox extent in x and y).
