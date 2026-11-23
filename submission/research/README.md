# A better fourth-ring packing for a finite square tile, and a porous fourth corona on its larger relative

The scored 29-square tile has exact Heesch numbers `Hc = Hh = 3`. We replaced its original three-ring patch and packed 33 more copies around the new boundary. Of 272 required sites, 258 are covered and 14 are missing. Two additional empty squares sit in enclosed pockets. The charged fourth-ring defect is therefore `16/272 = 1/17`, giving `4 − 1/17 = 67/17 ≈ 3.94117647`. The previous certificate-bearing submission had a charged defect of `35/246` and scored `3.85772358`. The improvement of approximately `0.08345` applies to the 29-square branch. [Previous 29-square submission](https://github.com/Layr-Labs/heesch/tree/aa509075a6df97c04a5e04edcc2f2b6bed52e358/submission)

## Two outlines from a 99-square polypillar

Both polyominoes are compressions of the same 99-square polypillar. Normalize its bottom-left extent to zero, retain rows `0,1,2,5`, retain the specified columns, and relabel surviving row and column indices consecutively. For the 29-square shape the columns are `0,2,4,6,7,8,9,12,15,19`. For its 38-square relative they are `0,2,3,6,7,9,11,12,14,16,17,18,19`. `research/verify_release.py` checks these reconstructions against the submitted coordinate lists. The earlier 29-square proof, the previously published 38-square comparison and Mann’s 99-square parent are in the archive. [Parent coordinates](https://github.com/Layr-Labs/heesch/blob/7892e9b423efbcd789b3a522d63854a359161f82/submission/research/square-companion/polypillar.heesch) · [First compression archive](https://github.com/Layr-Labs/heesch/tree/507b3b83f8d3474a3b0df4a306531b130acd1ed6/submission) · [Mann, Theorem 2](https://faculty.washington.edu/cemann/Heesch.pdf)

## Improving the certified 29-square packing

The earlier inner patch contained `1,5,10,16` copies from the center through ring three. Repacking its 246 required sites reduced the charged defect from 35 to 23. We then generated 35 depth-three patches with seeds 855 through 889. Each run built its rings by covering the halo of the previous ring under the benchmark’s full square symmetry group. For each solid footprint, we enumerated every translated and oriented copy touching its required set and disjoint from the completed patch. A CP-SAT constraint assigns at most one chosen tile to each cell. Whenever an incumbent closes a pocket, a cut charges its extra enclosed cells if the responsible boundary tiles remain and the cells stay empty. We geometrically replayed each claimed reduction. This repacker adapts the archived triangular placement and pocket-cut solver. [Pocket-cut algorithm](https://github.com/Layr-Labs/heesch/blob/9a6b909b87b37b66f491f837943d29c5d7b56748/submission/research/pocket_pack.py) · [Earlier implementation](https://github.com/Layr-Labs/heesch/blob/da181c8c4015e712a67e2f6fb440c2cbfc977596/submission/research/optimize.py)

Seed 857 gave a charged defect of 14 on 210 sites. Seed 883 has `1,5,10,18` copies from the center through the third ring. The solver considered 1,941 distinct outer placements and found the submitted `16/272`, a smaller fraction. Its final status was `UNKNOWN`, leaving room for better arrangements. All 35 complete patches, the intermediate packings and their solver results are in `research/anchor-charts`.

The official fourth-level formula depends on the tile’s canonical coordinates. The 29-square certificate remains applicable to this new positive witness. Its frozen formula has 1,791,185 variables and 9,374,012 clauses, SHA-256 `48a7d8ab9c9f225f1bacc21f29c977b29ece68a13db728a07df8823aec09ddb1`. The archived binary DRAT is byte-for-byte the prior checker-verified proof. After XZ decompression its 17,602,340 bytes hash to `808a8b1d5ad126fcd6abcf52c419156c07c23179aefcc64ad08f8c396363882b`. `verify_release.py` checks the canonical tile, the descriptor and both raw and compressed digests. The complete solid third ring supplies the matching lower bound.

## A 38-square tile with a porous fourth corona

The 38-square tile spans 13 by 4. We tested 24 distinct complete third-ring footprints and improved the earlier charged defect from `29/293` to `5/304`. The strongest packing uses `1,5,10,21` copies through ring three and 33 partial fourth-ring tiles. It misses `(-5,-18)`, `(-1,17)`, `(25,10)`, and `(25,21)` and leaves one additional enclosed square at `(22,-12)`. Seed 10025 used 2,303 legal outer placements and recorded successive charges of 16, 14, 12 and 5, ending `UNKNOWN`. The earlier witness, the improved witness, the 24 chart files and the comparison figure are included. [Earlier 38-square witness](https://github.com/Layr-Labs/heesch/blob/aa509075a6df97c04a5e04edcc2f2b6bed52e358/submission/research/38-square.heesch)

To explore whether four rings can surround this outline, we generated the benchmark's canonical `F(S,4)` directly. It contains 3,604,076 variables and 18,328,235 clauses, takes 6,890,614,475 bytes in DIMACS, and hashes to `95273fc1796c6cf458d8317089c86b414f15e4e076c3d65f09f5a29de1048d0e`. CaDiCaL returned a satisfying assignment. A separate streaming checker evaluated every original clause under the complete assignment and found all 18,328,235 satisfied. We decoded its level-major, orientation-indexed positive placement variables and passed the resulting coordinates through the frozen witness checker. There are `1,5,10,21,31` copies, 68 distinct placements in total. The number of uncovered required sites is zero in every ring. The successive numbers of enclosed empty squares are `0,0,0,0,36`. `research/model-four.heesch` gives a 37-copy solid three-ring witness followed by a separate 68-copy porous four-ring witness. Both declared bounds `Hc ≥ 3` and `Hh ≥ 4` replay without a discrepancy. `research/porous-fourth.png` marks every enclosed square in red.

We separately tested fourth-ring solidity with an exact halo-cover search over supported adjacent placements, checking Euler characteristic on each completed ring. That search exhausted its selected domains after 136,348 nodes at a maximum of three solid rings. A fourth-ring search result depends on the domain restrictions used. The witness establishes the lower bounds above. The 38-square shape is finite for a separate geometric reason. In a full tiling every tile must have a complete edge-covering neighborhood. We enumerated 1,130 neighborhoods using 234 relative placements after discarding two-tile pockets whose area is indivisible by 38. Enforcing reciprocal neighbors leaves 468, 320, then 320 neighborhoods. Requiring each neighbor’s neighborhood to agree on the occupied cell partition leaves 44, 35, 26, 16, 8, then zero. Since an actual plane tiling would survive each step, this proves a plane tiling is impossible. The benchmark enforces a maximum proof level of four for 38-square outlines. Its fourth-level formula is SAT and a level-five formula falls outside the official band. Consequently the 38-square findings accompany the scored 29-square tile as independent research.

## Five larger finite polyominoes

The third-ring placements of each parent identify horizontal and vertical unit strips that must receive equal widths under the rotations and reflections present. Those equalities have two classes for each parent. Assigning different positive widths to the classes stretches the patch into a new assembly of congruent copies. We reconstructed five outlines and their complete solid three-ring witnesses. Each has an independently replayed finite edge-neighborhood obstruction.

| Parent | Two strip widths | Child area | Raw neighborhoods | Surviving counts after compatibility pruning |
| --- | --- | ---: | ---: | --- |
| 29 | 3, 1 | 77 | 536 | 48, 31, 13, 5, 0 |
| 29 | 1, 2 | 83 | 694 | 44, 27, 13, 5, 0 |
| 38 | 3, 1 | 102 | 730 | 68, 51, 34, 16, 8, 0 |
| 38 | 1, 2 | 108 | 956 | 64, 47, 30, 16, 8, 0 |
| 29 | 4, 1 | 110 | 572 | 56, 35, 13, 5, 0 |

The 108-square tile also has a separately discovered patch with `1,6,11,19` copies. Its inherited patch has `1,5,10,18`. Each child has finite Heesch number and at least three solid coronas. Its exact number remains open here. `research/strip-family/strip-widths.pdf` shows the constructions. The companion witnesses and the maps that rebuild them are in the same directory.

## Replay

From the benchmark root, with the benchmark environment active, run the following. The porous-model decode uses NumPy. The optional outer packing search requires OR-Tools.

```sh
python -m heesch_verify submission/best.heesch
python -m heesch_verify submission/research/model-four.heesch
PYTHONPATH=. python submission/research/verify_release.py
PYTHONPATH=. python submission/research/replay.py
PYTHONPATH=. python submission/research/strip-family/strip_replay.py
PYTHONPATH=. python submission/research/pocket.py submission/research/anchor-charts/seed883.d3.heesch /tmp/anchor.heesch --bound 18 --seconds 60
```
