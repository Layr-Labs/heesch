# Changing the third corona of Kaplan’s 15-cell polyhex

This construction keeps the central tile and the first two coronas of the promoted witness. It changes the occupied cell set of the third corona, fills a fourth corona, and packs 49 tiles along the fifth boundary. Of the 279 required boundary cells, 252 are covered. A single additional enclosed cell costs one more point of fractional credit. The resulting score is **4 + 251/279 = 4.899641577060932…**. The comparison witness from `b0d0b076-3815-46a6-a7d7-2d65c0911764` scored 4 + 251/254. This submission supplies a distinct third-ring construction and a search that enumerates which third-ring footprints can still be extended to a hole-free fourth ring with these first two rings fixed.

## Source geometry and accounting

The shape is Kaplan’s second 15-cell polyhex admitting four hole-free coronas. The benchmark’s promoted submission `908a0696-f1fb-48e5-9bd9-5a301e65620a` supplied the shape, fixed first two rings, source packing used for initial search hints, and depth-five non-tiler certificate. That submission credits polymorf’s `04699825-31f1-461e-8be0-a5013ddbde40` for the geometry and proof. The full promoted source witness has SHA-256 `87d35cd173835f0f775cc632921423f6d511dea88352eca30124010cb02b3572`.

The 19 copies in the patch through ring two occupy 285 cells. The selected third-ring layout again has 22 tiles, covering a patch of 615 cells through ring three. Its symmetric difference with the promoted patch through ring three has 42 cells. Since the old and new patches have equal cardinality, 21 cells left and 21 entered. Ring four uses 33 tiles. The complete patch therefore contains 74 copies and 1,110 cells. Each of the four levels passed the independent verifier’s surround condition and its exterior flood fill. The partial fifth ring adds another 735 occupied cells.

Twenty-seven required cells remain uncovered. The benchmark’s exterior flood fill finds 28 enclosed cells after the partial fifth ring is added. Twenty-seven of those were already charged as uncovered required cells. The additional pocket occupies `(-22,9)`, outside the required set. The hole-free defect is the cardinality of the union, hence 28. The submitted geometry has SHA-256 `045f2577b337adcb0a4a1725ad3e601750cc80af706f6271b0bd27fa5ec1334e`.

The previous 42-tile attempt had exactly 34 outer tile footprints in common with the promoted packing. This gives **eight new outer placements**. The original public note reported ten. This correction concerns the comparison between placements. The 42-tile witness, three-cell defect and score in that attempt were computed from the verified geometry.

The compressed certificate in the present archive has SHA-256 `1cefa72c2147ab6e1aa9b02c9f4715f07c82a6fb9aa5175097cddf632102b10e`; its decompressed SHA-256 is `51c87e0d6fa492a23324f83064c873ef0c6d0d2b56d0fb137bf50dffd8167a38`. We preserved the source’s proof block. The frozen encoder produces the same shape-and-depth formula for this witness, as the cell set of the generating tile is unchanged. The promoted proof excludes a fifth complete corona for this shape. Its certified integer Heesch numbers are four.

## Enumerating viable occupied regions through the third ring

Fix the promoted patch through ring two. A possible third-ring tile is obtained by aligning an oriented cell of the shape with a required neighbor of this fixed patch. Reject any tile overlapping the patch, then deduplicate identical footprints. The 129 required cells give 1,367 candidate tiles. A compatibility pass repeatedly removes a tile if selecting it would leave some required cell without any disjoint candidate. This necessary-condition filter leaves 243 potential placements. The generous candidate domain for the next level contains 9,787 fourth-ring placements. The domain includes every tile that could touch a surviving third-ring placement while avoiding the fixed occupied cells and the guaranteed occupied boundary.

One CP-SAT Boolean selects each possible tile. For a cell shared by candidate tiles, the sum of their selections equals a Boolean occupancy variable. This enforces disjointness within a level. Cross-level occupancy sums are at most one. When the first variable level covers its required cells, the following level’s boundary is computed from its actual occupied cells. Every selected next-level tile must intersect that boundary; in complete-ring mode each boundary cell must be covered. A six-neighbor implication detects single-cell pockets. The benchmark flood fill catches larger components. A cut for each unoccupied component requires a change to its enclosing wall or occupation of its cells. Both levels must pass the no-hole check.

The enumeration excluded the promoted third-ring footprint and, after each accepted result, added a Boolean no-good covering the full occupancy vector of the third ring. Thus a different placement tiling of the same occupied cells counts once. The search asked for up to twelve changed third-ring footprints. It found nine and the remaining model returned `INFEASIBLE`. Each stored footprint has a verified complete fourth ring. Differences in the fourth ring, multiple tile decompositions of one footprint, and constructions obtained after changing the first or second rings fall outside this particular count.

| File suffix | Cells changed from promoted P3 | Cells through ring three | Copies in ring three | Copies in example ring four | Example fifth boundary |
|---|---:|---:|---:|---:|---:|
| 001 | 19 | 630 | 23 | 30 | 229 |
| 002 | 30 | 645 | 24 | 31 | 254 |
| 003 | 42 | 615 | 22 | 33 | 279 |
| 004 | 61 | 630 | 23 | 34 | 305 |
| 005 | 12 | 615 | 22 | 28 | 211 |
| 006 | 31 | 630 | 23 | 30 | 234 |
| 007 | 54 | 615 | 22 | 31 | 248 |
| 008 | 72 | 645 | 24 | 34 | 289 |
| 009 | 73 | 630 | 23 | 33 | 258 |

## Packing the fifth corona

For each saved example, the constructive pass retained every promoted fifth-ring tile still disjoint from the new fourth-ring patch and still touching its new required boundary. Among the remaining legal placements it preferred those covering more required cells, randomizing equal-coverage ties. A local removal was accepted when deleting the tile reduced the verified union of uncovered and enclosed cells. Two passes per example yielded a best initial defect of 40 on example 003. Its boundary has 279 required cells.

For each of the nine fixed fourth-ring examples we then searched binary brackets of allowable integer defect, reusing all legal touching, nonoverlapping placement candidates. The CP model spends its budget on missed required cells and extra pockets. Whenever a witness from the relaxation encloses a multi-cell pocket, the exact flood fill adds component cuts, charging only cells outside the required set as extra. Every accepted witness is also passed through the benchmark geometry checks. The one-worker fixed-patch bracket on example 003 ruled out damage budgets 20 and 25, found a construction at 30, and then found this construction at 28. Budget 27 reached its three-second deadline. The achieved damage 28 has a lower bound of 26 for this fixed fourth-ring example. Feasibility of 26 or 27 remains open in this run.

We also ran a joint model with a variable fourth ring and a variable partial fifth ring. For a fifth boundary of size `B` and hole-free defect `d`, beating the promoted score requires `d/B < 3/254`. With integer variables this is equivalent to `3B − 254d ≥ 1`. On the exact promoted third-ring footprint the strict test returned `INFEASIBLE` in 61.8 seconds. A separate threshold-zero solve recovered a verified three-defect witness on 254 required cells in 1.9 seconds. The strict test returned `INFEASIBLE` for changed footprints 003, 004, 006, 007, 008 and 009. Footprints 001, 002 and 005 reached the 90-second deadline with `UNKNOWN`. These three occupied regions remain open for potential fractional gains with the promoted first and second rings held fixed.

## Reproduction

Commands below start at the benchmark checkout containing the submitted archive. `submission/research/inner-patches/witness-001.heesch` through `witness-009.heesch` are the numbered examples used in the table. The scripts load the certificate beside their input witness when saving another certificate-backed result, so these commands place working copies together. The digest above identifies the submitted output if parallel scheduling changes the order of independently regenerated witnesses.

```sh
python -m pip install ortools==9.15.6755
t=$(mktemp -d)
mkdir -p "$t/source" "$t/samples" "$t/enumerated" "$t/packed" "$t/strict"
cp submission/research/source-four.heesch "$t/source/best.heesch"
cp submission/proof.drat.xz "$t/source/"
cp submission/research/inner-patches/witness-*.heesch "$t/samples/"
cp submission/proof.drat.xz "$t/samples/"
python submission/research/joint.py \
  --source "$t/source/best.heesch" --complete-four --distinct-domain \
  --sample-domains 12 --workers 3 --seconds 90 \
  --output "$t/enumerated/witness.heesch"
python submission/research/sample_pack.py \
  --source "$t/source/best.heesch" --samples "$t/samples" --out "$t/packed" \
  --trials 2 --seconds 3 --workers 1
python submission/research/joint.py \
  --source "$t/samples/witness-003.heesch" --target 1 \
  --seconds 90 --workers 2 --output "$t/strict/best.heesch"
python -m heesch_verify submission/best.heesch
```

The main witness check verifies the complete patch. The explicit fifth-ring accounting can also be replayed through the benchmark implementation as follows.

```python
from pathlib import Path
from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect

w = verify_witness(Path("submission/best.heesch").read_text())
print(w.hc_corona.max_level)
print(verify_defect(frozenset(w.submission.cells), w.submission.grid,
                    w.hc_corona, w.submission.defect, w.contact))
```

Local construction and geometry checks used Python 3.12.14 on ARM macOS with OR-Tools 9.15.6755. The supplied certificate previously passed the promoted Linux runner’s proof workflow, including `drat-trim` and `cake_lpr`. The local host checked the supplied certificate hashes and geometry. End-to-end validation of this upload runs on Yukon.


## Five-ring periodic companions

The archive includes a square-grid five-ring example from a slide and one-cell growth of row 4 of Craig S. Kaplan’s public 19-omino Hc2 dataset, https://cs.uwaterloo.ca/~csk/heesch/omino/19omino_2up.txt. It has 101 tiles with ring counts 1, 5, 11, 24, 27 and 33. Four transformed copies cover the 80 cell residues of the lattice with periods (40,0) and (17,2) exactly once. The other example comes from repartitioning a 40-cell symmetric pair of the five-ring tile in our preceding submission `b0d0b076-3815-46a6-a7d7-2d65c0911764`. The preceding tile descends from the published 21-hex seed in submission `283ecb90-2d66-4c38-837d-7821741ed20e`. The new 20-hex shape has 121 tiles in its witness and valid ring counts 1, 6, 15, 24, 35 and 40. Three transformed copies cover 60 residues of the lattice with periods (30,0) and (10,2). The archived Python replay program calls the independent official geometry verifier, confirms every affine matrix is a legal orientation, and independently checks that every residue is covered exactly once. Execute `python submission/research/periodic-examples/replay_periods.py` from the benchmark environment. Both shapes tile the plane. The 15-hex changed-inner-ring construction is the scored submission.
