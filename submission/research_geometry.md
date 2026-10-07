# Geometry research: improving the 15-hex partial fifth corona

## Verified target and exact improvement condition

The promoted candidate described in `frontier-note.txt` has `Hc=4`, fifth-corona required set size `B=254`, defect `D=3`, and score `4 + 251/254 = 4.988188976...`. The defect is the number of required cells left uncovered (plus pockets for the Hc score); here pockets are zero. A strict improvement on this shape therefore needs a legal packing with `D<=2`. More generally, any same-Hc shape with fifth-boundary size `B'` and defect `D'` beats this candidate exactly when `254*D' < 3*B'`. Since the board clamps fractions below one, `D'=0` still scores below 5 until a complete fifth corona is verified.

## Exact finite placement pool

Use the verifier's own contact relation and symmetry table. For this 15-cell hex, build `P4` from the verified patch and compute `R = required_set(P4, contact)` (`heesch_verify.patch.required_set`). For every `grid.orientations` element and every pair `(p,s)` where `p` is a cell of `P4`, `s` is a cell of the oriented shape, and `n` is a point-contact neighbor of `p`, form translation `t=n-s`. Deduplicate the resulting oriented translated cell sets. This enumerates every legal tile that can touch `P4`: any legal touching tile has at least one such contact pair. Discard candidates intersecting `P4` or the enclosed set `holes_of(P4, grid)`; retain the rest, including cells outside `R`, because the defect checker permits a tile anywhere outside the patch if it touches the patch.

For each candidate `i`, define `T_i` as its full cell set and `C_i=T_i∩R`. Solve the weighted set-packing problem:

`maximize Σ_i |C_i| x_i`, with `x_i∈{0,1}` and `Σ_{i:q∈T_i}x_i ≤ 1` for every cell `q` in the union of candidate tiles.

The objective equals covered required cells because selected tiles are disjoint. It is important to conflict on all tile cells, including cells outside `R`; using only `C_i` conflicts can create false feasible packings. A robust alternative uses pairwise constraints `x_i+x_j≤1` for any `T_i∩T_j≠∅`. Seed with the submitted 46 placements, then run exact optimization (CP-SAT / MILP) or large-neighborhood search around that incumbent. The verifier remains the final authority: rebuild `#DEFECT 5 u_hc u_hh 254`, pass all selected transforms to `verify_defect(shape_cells, grid, hc_corona, block, contact)`, and independently run `python3 -m heesch_verify submission/best.heesch` / the harness.

## Practical search order

1. Enumerate the complete candidate pool and calculate every candidate's `C_i`, outside-R footprint, and overlap degree. Check the incumbent selection reproduces 251 covered required cells and no pocket cells before optimizing.
2. Try local repair neighborhoods first: remove 1–4 current tiles, then solve the induced packing over all replacements whose footprints intersect a removed tile or touch one of its newly exposed `R` cells. Keep every incumbent tile outside the neighborhood fixed. This finds one-for-one and multi-tile replacements without disturbing the rest of the 46-tile solution.
3. Run weighted independent-set / set-packing with incumbent hints and maximize covered cells; repeat with randomized candidate ordering and neighborhoods centered on the three uncovered required cells. A solution covering either one or two of these cells is sufficient for a strict improvement at the same denominator, provided it does not uncover more elsewhere.
4. If this 15-cell shape is locally optimal at `D=3`, test denominator expansion on alternate 11–20 cell Hc=4 hexes: compute `B'` first, then target `D'≤floor((3B'-1)/254)`. Larger `B'` helps only if the increased ring can be packed proportionally; the proof gate still requires an independently checked UNSAT certificate for `F(S,5)`.

## Relevant implementation interfaces and cautions

- `heesch_verify.parse.parse_submission(text)` returns `Submission`, including shape, patches, and `defect` block.
- `heesch_verify.patch.check_corona(...)` returns the verified `CoronaResult`, including `patch_cells`; the same `contact` object must be threaded through.
- `heesch_verify.defect.verify_defect(shape_cells, grid, corona, block, contact)` reports `required`, `defect_hc`, `defect_hh`, and `pocket_cells`; its claims are ceilings and do not establish optimality.
- `Grid.orientations` and `Contact.neighbors` are the frozen symmetry/contact APIs. Do not hand-code a second hex adjacency relation.
- Local `python3 -m heesch_verify` reports the witness geometry but does not run the proof gate; use the harness or `tools/prove.py --check` for certificate status. The current local run only established `Hc=Hh=4`; it is not remote leaderboard evidence.

## Geometric denominator assessment

The score's denominator is the actual size of the next required ring `|R|`, not the number of placements or covered cells. Expanding it is not free: the threshold `254D'<3B'` makes the necessary residual defect grow at only about `0.01181` per new boundary cell. For example, `B'=300` can tolerate at most `D'=3`; a boundary of 339 still tolerates only `D'=3`; `D'=4` first becomes viable at `B'=339` only if strict inequality is checked carefully (`254*4=1016 < 3*339=1017`). Therefore prioritize eliminating one of the current three misses before investing in larger shapes. A complete corona (`D'=0`) is only a fractional 4.999999-style entry under the score clamp unless the witness is extended and verified as a fifth full corona, which changes the integer `Hc` to 5 and requires a matching `F(S,6)` UNSAT proof.
