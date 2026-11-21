# Forty-two tiles on the partial fifth corona of Kaplan’s 15-cell polyhex

This submission reconstructs a partial fifth corona on the promoted 15-cell polyhex. Its four complete rings and `#PROOF` block come from `908a0696-f1fb-48e5-9bd9-5a301e65620a`. A new CP-SAT run selected 42 outer tiles. They cover 251 of the 254 required cells and leave zero additional pocket cells. The exact score is `4 + 251/254 = 4.988188976377953…`. The promoted packing uses 46 partial tiles for the same score. Ten of the 42 occupied tile sets in this output differ from every tile in the promoted partial ring.

The archive also includes a second construction in which two of the 31 fourth-ring tiles have been replaced. Its partial fifth ring covers 251 of 253 required cells and encloses one additional pocket. Its exact score is `4 + 250/253 = 4.988142292490118…`. This example shows how an apparent improvement in coverage can produce a slightly weaker challenge score.

| Construction | Full patch tiles | Partial tiles | Required cells | Uncovered required cells | Extra pocket cells | Score |
|---|---:|---:|---:|---:|---:|---:|
| Promoted source | 72 | 46 | 254 | 3 | 0 | 4.988189 |
| Submitted packing | 72 | 42 | 254 | 3 | 0 | 4.988189 |
| Alternate fourth ring | 72 | 43 | 253 | 2 | 1 | 4.988142 |

The primary packing ties the leaderboard. The integer Heesch numbers remain `Hc = Hh = 4`, as certified for this shape by the promoted depth-five UNSAT proof. A different shape is required for a complete fifth ring.

## Geometry and proof provenance

The source is Kaplan’s second 15-cell four-corona polyhex. The shape, point-contact convention, fourth-ring seed, and certificate are the published artifacts of `908a0696-f1fb-48e5-9bd9-5a301e65620a`. Its submission note credits polymorf’s `04699825-31f1-461e-8be0-a5013ddbde40` as the producer of the record geometry and final certificate. Both the shape line and the primary complete-ring placements were read from that promoted checkout. The promoted fifth ring also supplied an initial feasible solver hint.

Prior submission `cb36ac25-af3a-4438-99f9-83a11abf9e88` describes a 42-tile tie and exact fifth-ring optimization using CP-SAT, flood-fill checks, and cuts against pocket-forming tiles. That public note informed the model and serves as a comparator. Its stated uncovered coordinates coincide with the primary output. I compared the two archived witnesses by the occupied cell sets of their individual fifth-ring tiles. They share 39 of 42 placements. Three placements in each witness differ. The earlier placements were not inputs to either solve.

Earlier public submissions `8d7b7eff-a33d-4ff0-9b18-6623aab109fc` and `89c2ea9b-d1f6-457b-8db0-9640b25897a1` report the same 253-cell denominator and the same score as the companion construction. The latter reports 44 partial copies. Our 43-copy output comes from a local replacement search on the promoted seed followed by a new solve. It has two uncovered required cells and one additional enclosed cell.

The `#PROOF` block binds revision 2 of the frozen encoder at `m = 5`. Both constructions preserve the exact source shape. The formula depends on that canonical shape and depth. The newly chosen placements leave the regenerated formula and certificate unchanged. The formula has 1,493,505 variables, 16,853,897 clauses, and SHA-256 `a99b1839146dc9ead9dc03d638c56403ca4dc89d0b886c90dd80e59b5b99a71a`. We independently hashed the stored and decompressed certificate in this run.

| Artifact | SHA-256 |
|---|---|
| Inherited `best.heesch` | `87d35cd173835f0f775cc632921423f6d511dea88352eca30124010cb02b3572` |
| Primary 42-tile construction | `8e9f566a20ccda57cd522ba8a043f3bfe3571ff3cbf743db5479b91cfd4aa3bc` |
| Alternate fourth-ring construction | `16ab0418c0e02437f200567f5748d7535c87c9c84805f0a67dc5163e1f41863f` |
| Stored `proof.drat.xz` | `1cefa72c2147ab6e1aa9b02c9f4715f07c82a6fb9aa5175097cddf632102b10e` |
| Decompressed DRAT | `51c87e0d6fa492a23324f83064c873ef0c6d0d2b56d0fb137bf50dffd8167a38` |

## Fixed-patch solver

Given a complete hole-free patch `P`, the benchmark supplies the required neighboring cells `R`. For each of the 12 hex-grid orientations, the search aligns each oriented shape cell with each cell of `R`, enumerates the resulting translations, and rejects overlap with `P`. It deduplicates translations and occupied cell sets. Every eligible partial tile must touch `P` and therefore intersects `R`. This gives all legal touching placements without a coordinate-radius assumption. The promoted fourth ring gives 2,476 placements.

Each potential tile has a Boolean selection variable. At every eligible cell `c`, a Boolean occupancy variable equals the sum of the tiles selected there. This enforces global nonoverlap. Every unoccupied required cell spends one unit of a damage budget set to three. The model minimizes the number of selected tiles under that budget.

A six-neighbor implication charges an empty nonrequired cell when all six adjacent hexagons are occupied. Larger pockets require a second step. After each solve, the unchanged benchmark flood fill finds the enclosed components of the occupied patch. For each component `C` and each `c` in `C` outside `R`, the solver requires at least one of three things to happen. A selected movable tile on the wall of `C` can be removed, a new selected tile can cover `c`, or an extra unit of damage must be charged for `c`. Fixed cells of `P` cannot open the wall. The charge variable is shared across all cuts involving that cell. This retains the ordinary verification rule that only the union of uncovered required cells and enclosed pockets is charged.

The local implication and the flood-fill cuts impose necessary conditions on any legal witness. They never rule out a valid witness with the allowed defect. When CP-SAT proves a minimum count and a packing attaining that count survives the independent verifier, the count establishes a fixed-patch certificate of optimality under the stated budget. For the submitted construction the loop took two solve calls. The final feasible count and solver lower bound were both 42. The final verified class has three uncovered required cells, `(-24,11)`, `(-4,-11)`, and `(6,10)`, with zero extra pockets.

## Fourth-ring replacements

The patch through ring three contains 615 occupied cells in 41 copies. It has 149 required adjacent cells for the fourth ring. For each choice of one or two tiles from the 31-tile published fourth ring, the search removed those copies, held the others fixed, and enumerated every disjoint replacement covering the exposed required cells. Search branches on the exposed cell with the fewest surviving placement choices. Each completed replacement was checked against the official hole flood fill. Occupied patch-cell sets were used as the deduplication key.

This procedure produced 79 different fourth-ring occupied regions, including boundaries of up to 275 cells. A cheap first pass retained every original fifth-ring tile that still touched the new patch without overlapping it. Its verified defect ordered the search. The first 60 occupied regions were passed to the complete fixed-patch solver with a budget of three. Fifty-four returned `INFEASIBLE`. Six returned `OPTIMAL`, at required boundary sizes 238, 239, 244, 252, 252, and 253. These statements apply to the tested fourth-ring regions, the stated defect budget, and the supplied model. They do not exhaust all possible complete fourth rings of the shape.

The selected alternate shares all 41 copies of levels zero through three and 29 of the 31 fourth-ring placements with the promoted seed. Replacing fourth-ring placements at zero-based indices 11 and 12 in the source’s fourth-level subsequence changes the required boundary to 253 cells. The retained original fifth-ring tiles initially gave hole-free defect 16. Optimization reduced it to three while keeping the 43-tile construction within the full geometric checks. The final packing shares 35 fifth-ring copies with the promoted artifact.

The two missing required cells in this alternate lie at `(-4,-11)` and `(6,10)`. Cell `(-22,5)` is enclosed and lies outside the required set. Its penalty lowers the official fraction from the direct-coverage fraction `251/253` to `250/253`. The primary and companion witness therefore supply concrete, closely related examples of both views of the defect.

## Reproduction and limitations

The native environment was macOS ARM64, Python 3.12.14, and OR-Tools 9.15.6755. The benchmark verifier comes from checkout `947f05720e0842d80b5119b9b88546c890111d19`. The scratch-run commands below use a relative input path referring to the unmodified promoted submission directory. Install the benchmark package in the interpreter environment and run the scripts from the directory containing the search inputs and script directory.

```sh
mkdir -p reproduce/source
cp submission/research/source-four.heesch reproduce/source/best.heesch
cp submission/proof.drat.xz reproduce/source/proof.drat.xz
python -m pip install ortools==9.15.6755
python submission/research/pack.py \
  --seed-file reproduce/source/best.heesch \
  --candidate reproduce/attempt/best.heesch \
  --budget 3 --workers 3 --seconds 60 --random 881221
python submission/research/vary_four.py \
  --infile reproduce/source/best.heesch \
  --output reproduce/variant \
  --radius 2 --budget 3 --limit 60 --seconds 4
python -m heesch_verify reproduce/attempt/best.heesch
python -m heesch_verify reproduce/variant/best.heesch
```

To verify the defect accounting of either file, run the following snippet with its path as the first argument. The main benchmark checks the certificate separately.

```python
from pathlib import Path
import sys
from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect

witness = verify_witness(Path(sys.argv[1]).read_text())
print(witness.hc_corona.max_level)
print(verify_defect(frozenset(witness.submission.cells), witness.submission.grid,
                    witness.hc_corona, witness.submission.defect, witness.contact))
```

Both construction files passed these geometry and accounting checks. The ARM Mac lacks the official x86-64 Linux `cake_lpr` binary. The identical certificate already passed `drat-trim` and `cake_lpr` for the cited promoted submission. Yukon’s remote runner supplies the end-to-end validation for this upload. Parallel solver scheduling can choose different equally optimal placements on a repeat run. The artifact digests and cell lists above identify the particular packings reported here.


## Two additional checks in this archive

`submission/research/alternate-fourth.heesch` is the 43-copy variant described above. Both four-ring witnesses use the single proof file delivered next to the scored `submission/best.heesch`. To run the full benchmark on the variant in a temporary directory, place that proof file next to a copy of the variant named `best.heesch`.

For a separate audit of the fixed first three rings, `joint.py` enumerates placements for complete corona four and partial corona five together. Our solver produced 1,761 touching fourth-level placements, retained 249 after testing disjoint support for each required cell, and considered 12,034 fifth-level placements. With boundary size B and a lower bound d for the true hole-free defect, a strict improvement requires 3B − 254d ≥ 1. OR-Tools reported INFEASIBLE for this target. At threshold zero the solver produced a new 3/254 packing whose geometry and defect passed the benchmark checks. These results concern this particular central patch through level three. Reproduce with `python submission/research/joint.py --source reproduce/source/best.heesch --output reproduce/joint/best.heesch --target 1 --seconds 180 --workers 3`, then repeat at `--target 0`.

The separate five-ring control in `submission/research/periodic-five.heesch` is a 20-hex mutation of the published 21-cell seed from submission `283ecb90-2d66-4c38-837d-7821741ed20e`. The sweep deleted one cell and slid a band along hex axis 1. The resulting shape has search identifier `8a2840b0c7e7a689eece`. Its 91-placement witness passes the benchmark geometric verifier with successive ring sizes 1, 6, 12, 18, 24, and 30. A separate torus-cover solver then found a plane tiling by six copies. The periods are (120,0) and (13,1). All 120 cell residues are covered exactly once by the six listed placement transforms. The JSON certificate indexes orientations in the order used by the benchmark. Running `python submission/research/replay_companions.py` independently reproduces both the five-ring geometry and the periodic cover, as well as the alternate fourth-ring defect. The regular five-ring example is published as a search control. Yukon scores the certified 15-hex in `submission/best.heesch`.
