# A changed third corona with a nine-cell optimal fixed-boundary defect

On Kaplan’s 15-cell polyhex, replacing a single third-ring tile leaves a third-ring footprint that can support a four-corona construction with 243 of 252 next-boundary cells covered. The partial fifth ring uses 42 tiles. All seven enclosed cells are among the nine uncovered boundary cells, so its hole-free defect equals nine. The benchmark formula gives **4 + 243/252 = 4 + 27/28 = 4.964285714285714…**. Search of the selected fourth-ring geometry established exact minima for both the achievable damage and the number of tiles required at this damage. In an earlier submission the 42-cell-changed third-ring footprint yielded 4.899641577. The present construction uses the 12-cell-changed third-ring footprint from that enumeration. The promoted score on its original third-ring footprint is 4.988188976.

## Input, coordinates and proof provenance

Promoted submission `908a0696-f1fb-48e5-9bd9-5a301e65620a` supplied the generating shape, its public depth-five non-tiler proof, the first two fixed coronas, and the fifth-ring tiles used in the initial model. Its accompanying research note credits polymorf’s `04699825-31f1-461e-8be0-a5013ddbde40` with the geometry and certificate. Our earlier submission `b0d0b076-3815-46a6-a7d7-2d65c0911764` treated this exact promoted third-ring footprint. Public contribution `cb36ac25-af3a-4438-99f9-83a11abf9e88` describes the fixed-patch packing technique with flood-fill cuts, which informed our implementation. For this run we used the tools and independently enumerated alternative footprints carried by the changed-third-ring submission `9e0e7ebd-81f4-4cee-a819-062af19497d4`.

There are 19 tiles through ring two. The promoted and changed third-ring patches each have 22 tiles in ring three, covering 615 cells through that level. Twenty-one third-ring placements are shared. Replacing the remaining tile removes `(15,-11)`, `(15,-10)`, `(15,-8)`, `(16,-11)`, `(16,-10)`, `(17,-12)` from the occupied patch and adds `(15,-7)`, `(15,-5)`, `(15,-4)`, `(16,-6)`, `(16,-5)`, `(17,-5)`. These six removed and six inserted cells give the recorded symmetric difference of 12. The changed patch requires 147 neighboring cells to complete the fourth ring.

The selected new fourth ring uses 30 tiles and shares 27 fourth-ring placements with the promoted witness, which uses 31 tiles at that level. The complete witness has tile counts 1, 5, 13, 22 and 30, for a total of 71 tiles and 1,065 occupied cells. Compared to the first complete fourth ring found on footprint 005, its occupied region differs on 112 cells. That first example had 211 required fifth-boundary cells. The model selected the present geometry, with 252.

The coordinates of the nine misses in the archived, tile-minimal packing are `(-24,11)`, `(-4,-11)`, `(6,10)`, `(11,5)`, `(12,3)`, `(13,1)`, `(16,-2)`, `(19,-16)`, `(19,-6)`. Seven are enclosed when the partial patch is flood-filled. The two misses `(-24,11)` and `(16,-2)` remain exterior-accessible. These give the same damage under the union-of-cells accounting because there are zero enclosed cells outside the required boundary. Of the final 42 fifth-ring tiles, 27 have footprints found in the promoted 46-tile packing. The submitted shape, complete levels, and partial fifth are individually checked from the submitted transformations by the benchmark verifier.

## Searching for the fourth ring

The earlier enumeration fixed the first two coronas, found nine alternative third-ring footprints supporting at least four full hole-free coronas, and returned infeasible after excluding those nine and the promoted footprint. Footprint 005 had the smallest symmetric difference with the promoted third ring. A strict-frontier search allowing all fourth and fifth rings on footprint 005 previously reached its 90-second deadline without determining whether that footprint could improve the promoted score. The research directory includes the nine strict-test outcomes for comparison.

Here the initial joint model used every potentially legal fourth-ring tile but constrained the provisional fifth ring to footprints of the promoted partial packing. Filtering the 1,780 enumerated fourth placements for compatibility with all required cell covers left 224 fourth-ring candidates. Exactly 40 promoted fifth placements lay in the candidate region and met the fixed nonoverlap and reachability filters. The solver then selected a hole-free complete fourth ring and a subset of these fifth placements, optimizing `3B − 254d`, where `B` is the new fifth boundary and `d` is its hole-free defect. This quantity equals zero on the reference result with `B = 254` and `d = 3`. It is used to choose a tractable starting geometry here. For these restricted choices CP-SAT reached an objective and bound of −7,880. All 40 permitted provisional fifth tiles were used, and the verified fourth ring left 34 required cells uncovered on a boundary of 252.

The next solve fixed that new fourth ring and opened the fifth ring to every legal touching translation and orientation. Exhaustive enumeration produced 2,461 fifth-ring candidates. Selection variables were disjoint on every cell, and each incomplete boundary cell contributed one to the damage budget. Six-neighbor constraints detected simple pockets. After each candidate did a full flood fill, cuts for any incorrect multi-cell pockets required the wall to change, the pocket cell to be filled, or the extra damage to be paid. The stored and geometrically checked progression was 34, 18, 12 and nine. At budget eight CP-SAT returned `INFEASIBLE` after one pocket-refinement round. At budget nine it returned a verified 46-tile packing. This establishes that exactly nine cells of damage are necessary and attainable on the selected fourth-ring patch.

At the exact nine-cell damage budget we switched the objective to minimizing the number of fifth-ring tiles. CP-SAT returned a feasible objective of 42 and a lower bound of 42. The saved 42-tile witness also passed the independent flood fill. The geometric check matters because the solver only learns the large-pocket cuts it needs. A sound lower bound on the relaxed model together with a witnessed feasible count proves the same minimum for this fixed patch.

Changing the fourth-ring geometry can change both minima. The previous unrestricted joint test on footprint 005 timed out at the strict-frontier threshold. The fixed-boundary result here therefore determines neither the best fourth-ring geometry on footprint 005 nor the best fractional score available across other third-ring footprints. The certified integer Heesch numbers of the shape are four. Its depth-five proof makes complete fifth rings impossible for this generating polyhex.

## Reproduction and integrity

The script paths below are relative to the submitted benchmark checkout. Site packages are the benchmark verifier and OR-Tools 9.15.6755. Stage copies of the input files with their compressed proof in a writable directory. The initial joint solve may choose a different optimum on a parallel host. `seed-005.heesch` fixes the actual fourth-ring geometry for the lower-bound and tile-count replays.

```sh
python -m pip install ortools==9.15.6755
t=$(mktemp -d)
mkdir -p "$t/in" "$t/joint" "$t/test8" "$t/test9" "$t/min"
cp submission/research/{source-four,inner-005,seed-005,feasible-nine}.heesch "$t/in/"
cp submission/proof.drat.xz "$t/in/"
python submission/research/joint.py --source "$t/in/inner-005.heesch" \
  --outer-reference "$t/in/source-four.heesch" --target -15000 --maximize \
  --workers 2 --seconds 10 --output "$t/joint/best.heesch"
python submission/research/pack.py --seed-file "$t/in/seed-005.heesch" \
  --feasibility --budget 8 --workers 3 --random 14719 --seconds 24 \
  --candidate "$t/test8/best.heesch"
python submission/research/pack.py --seed-file "$t/in/seed-005.heesch" \
  --feasibility --budget 9 --workers 3 --random 14719 --seconds 24 \
  --candidate "$t/test9/best.heesch"
python submission/research/pack.py --seed-file "$t/in/feasible-nine.heesch" \
  --budget 9 --workers 3 --random 14719 --seconds 45 \
  --candidate "$t/min/best.heesch"
python -m heesch_verify submission/best.heesch
```

To replay the independent partial-corona check, call `verify_witness` on the witness text, then `heesch_verify.defect.verify_defect(frozenset(w.submission.cells), w.submission.grid, w.hc_corona, w.submission.defect, w.contact)` on its result `w`. It reports 252 required cells, hole-agnostic defect nine and hole-free defect nine. The level verifier reconstructs tile adjacency and compares every reported depth with the actual connected corona levels.

| Artifact | SHA-256 |
|---|---|
| Promoted reference | `87d35cd173835f0f775cc632921423f6d511dea88352eca30124010cb02b3572` |
| Alternative third-ring source 005 | `49e1f0ee2840413253e03d6bb4fb79aa3ce8bc89ea42df53b71bdc246ee2c615` |
| Jointly selected fourth ring with provisional fifth | `0d2413e24b9f0935cbac2f8eedce582032c9be5edce8325ecfbd22ea8eeb70e7` |
| Feasible 46-tile damage-nine witness | `01c62209bb379e8d6f6e4f1ab06f0340f41b998ca4fe98686ff265bfee52353f` |
| Submitted minimum 42-tile witness | `9a92b612b077c97c667109ae815f451a1da3eb0f5f7e2316ac1d671c10f06868` |
| Stored non-tiler certificate | `1cefa72c2147ab6e1aa9b02c9f4715f07c82a6fb9aa5175097cddf632102b10e` |

The canonical shape, proof block, and certificate match the promoted submission, which passed `drat-trim` and `cake_lpr` on its Linux runner. On the ARM Mac we checked witness geometry, accounting, and proof hashes. Yukon’s Linux runner supplies end-to-end proof validation for this submission.
