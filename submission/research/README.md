# The exact fifth-ring defect on a fixed 60-copy patch of the finite 15-hex

Thirty-two outer copies attain a scored defect of 25 on the 175-site boundary of the four-ring chart from Attempt 19. A separate, checkable propositional proof excludes every partial fifth ring of defect 24 or less on that footprint. The attained score is `4 + 150/175 = 34/7`. Attempt 19 attained `4 + 139/175` on the identical footprint. Its packing maximized the number of required sites covered and trapped 15 additional empty cells. In the new packing, three more required sites are left open and fourteen fewer additional cells are trapped. These changes recover eleven units of scored defect. The previously scored 15-hex documented in Attempt 07 is a different outline. Its three-gap result involves a different set of 254 boundary sites. [Source four-ring chart and earlier packing](https://github.com/Layr-Labs/heesch/tree/6db5223e82a07185fe3fd9f2d9ab23aec0452304/submission)

## The tile and the two certificates

The scored outline is Kaplan’s 15-hex record 279. The witness has one central tile, followed by 4, 10, 20 and 25 tiles in the four completed rings. The plane non-tiling certificate in `submission/proof.drat.xz` and the four verified levels are inherited byte-for-byte from the preceding 15-hex entry. Its frozen encoder formula `F(S,5)` has 993,094 variables and 10,112,615 clauses. The changed fifth ring is partial. The earlier proof remains applicable because the formula depends on the outline and the depth. The first three integers in the new defect header are the level 5, the scored defect 25, and the number 24 of uncovered required sites. The verifier gives one additional enclosed cell. This certificate establishes the finite Heesch number four independently of which partial outer packing is chosen. [Kaplan’s public 15-hex classification table](https://cs.uwaterloo.ca/~csk/heesch/hex/15hex_3up.txt)

The second certificate is specific to these 60 solid copies. `research/bound.py` writes the CNF and `research/fixed.drat.xz` carries its independently checkable refutation. These files live in the research companion. Moving a single fourth-ring copy can change the optimum and requires a new calculation. The picture `research/packing.pdf` displays the two partial fifth rings in the same coordinate convention with red gaps and outlined amber pockets.

## Enumerating every eligible exterior placement

Let `P` be the occupied cells of the entire four-ring patch, and `R` the verifier’s point-contact boundary of `P`. For each of the twelve allowed hex-grid orientations, pair each rotated tile cell with each site of `R`. Their difference determines a unique translation, so any allowed partial-corona tile will be proposed. Remove proposals that intersect `P` and representations with identical physical footprints. This leaves 1,865 distinct placements. The enclosure-aware CP-SAT search uses one choice variable per footprint and unit capacity on occupied cells. Each time a proposed packing fails a full exterior flood fill, the enclosing boundary supplies additional constraints for empty cells inside. The initial feasibility pass at budget 27 produced 26 open boundary sites and one additional enclosed cell. Budget 25 produced the archived 32-copy arrangement. Separate runs reported infeasibility at budgets 23 and 24. The explicit SAT refutation below establishes the relevant lower bound independently of these CP-SAT reports. The packing module comes from our 17-hex study. Its solve-and-flood ancestry includes Mahmoud514’s published enclosure-cut method. [Packing implementation](https://github.com/Layr-Labs/heesch/blob/fb6bb1e589d000f2d0c5876b06181078f9f438f9/submission/research/solver/pack.py)

## Proving the lower bound for the fixed footprint

Use a Boolean variable for each placement and an occupancy variable at each potentially occupied cell. Occupancy equals the disjunction of the incident placements. A sequential at-most-one encoding prevents overlaps. An uncovered required site contributes one unit to a unary cardinality bound. For an eligible exterior site outside `R`, occupancy of all six adjacent hexagons forces a charge whenever the site itself remains vacant. These constraints give a lower bound on the verifier’s charged defect. A real packing with charged defect at most 24 would therefore satisfy the constraints, with its enclosed extra cells charged.

The first SAT solution of this relaxation left 22 required sites open and trapped 13 additional empty cells. An edge flood identified four enclosures containing respectively four, four, four and one additional empty cells. Each enclosure survives with just the fixed patch and two specific selected outer tiles as barriers. For each such pair, the rebuilt encoding recomputes the enclosed sites using their actual footprints. If both bounding tiles are retained, any designated site in the enclosure must either be filled by a chosen tile or incur its own extra-cell charge. This adds 13 clauses. Each extra site has a single common charge variable throughout the counting circuit.

The resulting budget-24 CNF has 34,492 variables and 131,787 clauses. CaDiCaL returned UNSAT. Independent backward verification with `drat-trim` used 686 proof lemmas, 10,399 input clauses and 70,450 resolution steps before reporting `s VERIFIED`. Exact clause ordering and hashes are in `research/bound.json`. `research/check.py` regenerates the formula and checks the supplied refutation. Because the 32-copy witness realizes 25, no other packing on these exact 60 solid copies scores higher.

## A five-ring outline obtained from empty space

A separate construction asks what outline is enclosed when the neighbors of a tile change shape. In a complete local surround from the same 15-hex patch, the center tile’s edge halo is fully occupied. Express the neighboring copies in its own coordinates. Remove the two cells `(2,1)` and `(0,1)` from the 15-hex in each neighboring pose, leaving 13 cells per surrounding copy. The edited copies remain disjoint. The edge-connected component of their complement containing `(2,1)` has 18 cells. Canonicalize this cavity under translations, rotations and reflections to obtain the new tile. All affine poses are archived and the replay recovers the same complement starting from the scored four-ring chart.

A fresh single-tile search on this 18-hex produced five complete rings with 100 copies. An eight-copy periodic cover also exists, with translation vectors `(9,0)` and `(1,16)`. It covers each of the 144 residue cells exactly once. This establishes an infinite tiling of the new outline. `research/cavity.pdf` draws the original surround, the edited neighbors with their enclosed shape, and the independently solved five-ring arrangement. The plane-tiling example illustrates a way to search for new outlines from actual geometric contacts. Further experiments can vary those contacts or vary the 60-copy footprint whose partial fifth ring is capped by the first calculation.

## Replay on the benchmark checkout

We ran the search and the independent certificate check on an Apple silicon Mac using the benchmark Python environment, OR-Tools, the pinned CaDiCaL executable and the vendored `drat-trim`. The companion replay needs the benchmark Python package and `drat-trim`. The first command recomputes both defect counts, checks the second certificate and verifies the cavity and its periodic domain. The second reads the submitted arrangement through the standard verifier.

```sh
PYTHONPATH=. python submission/research/check.py tools/bin/drat-trim
python -m heesch_verify submission/best.heesch
```

To reproduce the auxiliary refutation from scratch, run the command below. The script saves the intermediate SAT assignments, enclosures, clause counts, final DIMACS file and binary proof in the specified output directory. The frozen benchmark uses the primary shape proof to decide the scored submission. Both geometric witnesses, the four-ring bound and the public ancestor file can be checked independently of the packing solver’s run-time scheduling.

```sh
PYTHONPATH=. python submission/research/bound.py submission/best.heesch /tmp/15hex-fixed-bound tools/bin/cadical --budget 24
tools/bin/drat-trim /tmp/15hex-fixed-bound/fixed.cnf /tmp/15hex-fixed-bound/fixed.drat
```
