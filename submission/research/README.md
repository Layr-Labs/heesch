# Best possible fractional score with the promoted first corona fixed

On Kaplan’s 15-cell polyhex, fixing the six copies in the promoted patch through ring one sets an exact upper bound of **4 + 251/254 = 4.988188976377953…** for any extension. The submitted `best.heesch` attains this score. The search varied every complete second ring, then every third-ring footprint capable of supporting a complete fourth ring, and finally the fourth ring and its partial fifth together. The claim applies to the 90 occupied cells through the first ring of the supplied source. The rest of the geometry is free. The search here leaves other first-ring footprints open.

The outcome strengthens the earlier result that held both the first and second ring fixed. The new analysis checks 27 distinct changed second-ring footprints supporting at least three complete coronas. Five support at least four. Those five produce 19 third-ring branches capable of reaching four. All 19 were excluded from beating the promoted fractional score. The original second-ring branch was resolved separately in the predecessor appendix, reproduced in `original-second/`.

## Submitted equality witness

The generating tile and the 72 placements of the complete patch come from the promoted witness. Its tile counts by level are 1, 5, 13, 22 and 31. We solved for a different partial fifth corona. The new packing uses 42 outer tiles, of which 37 also occur in our earlier 42-tile packing. It shares 31 tiles with the promoted 46-tile packing. Comparison is by transformed occupied-cell set, so these counts are independent of ordering in the witness.

The three missed required cells are `(-24,11)`, `(-4,-11)` and `(6,10)`. The latter two are also enclosed. There are no extra enclosed cells outside the required boundary. The benchmark’s hole-free union defect is therefore three, and 251 of 254 required cells are covered. The submitted file has SHA-256 `5cfdbfc7178769c639ff5084e4af3c25f87bd9fa1fbbb7138cfd1f1b7cb46a0f`.

To obtain a different placement set, the solver allowed at most 42 fifth tiles and at most 41 from the earlier 42-tile solution. Its objective then minimized the number of promoted outer tiles retained. The geometric pocket-cut solver returned an objective and bound of 31, and independent flood filling accepted the resulting candidate. This optimization was restricted to the submitted fourth-ring patch and the specified equality budget. Its useful output is a different visual realization of the equality case.

## Enumerating changed second-ring footprints

The six tiles through ring one occupy 90 cells and expose 59 required neighbor cells. Every legal next-ring tile intersects at least one of these 59. We aligned each cell of each legal orientation with each required position and removed overlaps with the fixed patch. This yields 872 potential second-ring placements. A compatibility filter repeatedly drops a placement whenever selecting it leaves some required cell without any disjoint cover. This necessary condition leaves 190 placements for the exact-cover model. The superset for the third ring consists of 7,345 placements touching some possible second-ring boundary.

The Boolean model chooses disjoint tiles for both levels. The fourth and fifth levels use the same constraints when called on deeper input. Required-cell occupancy is exact, and a selected outer tile must intersect the actual next boundary. Each accepted complete ring covers the preceding patch’s entire required boundary. The official geometric flood fill tests enclosed components and adds sound wall-breaking or cell-filling cuts whenever a relaxed assignment encloses empty cells. After a valid solution, the search excludes the chosen first variable ring’s entire occupied-cell vector. Different decompositions of the same occupied region have the same next boundary. One representative therefore suffices for every deeper extension.

We first restricted the symmetric difference between the promoted and candidate second-ring occupied regions to at most 40 cells. Exactly seven changed footprints admitted three complete rings. We then removed the difference restriction, excluded only the original footprint and accepted 27 changed footprints. After excluding all 27, the next solve returned `INFEASIBLE`. All seven from the first run could be matched by occupied-cell equality to unrestricted witnesses. The unrestricted census and all 27 complete three-corona geometry files are preserved in the archive.

## Extending each changed footprint

For each of the 27 changed second-ring domains, a second joint solve selected a complete third and fourth ring. Each isolated third-ring occupancy no-good excluded exactly one realized domain. All 27 enumerations ended `INFEASIBLE`. Twenty-two second-ring regions supported no fourth corona. The following five supported a total of 19 third-ring regions admitting a fourth corona.

| Changed second ring | Symmetric difference with promoted P2 | Viable third-ring footprints |
|---|---:|---:|
| sample-001 | 48 cells | 2 |
| sample-002 | 27 cells | 6 |
| sample-003 | 12 cells | 5 |
| sample-004 | 39 cells | 3 |
| sample-010 | 46 cells | 3 |

For each viable third-ring region, the complete fourth ring and partial fifth remained free to vary in the scoring model. Let `B` denote the number of required cells of the fifth boundary and `d` its hole-free defect. The score of a four-ring construction is `5 − d/B`; a strict improvement over the target is equivalent to the integer inequality `3B − 254d ≥ 1`. In a separate exact-cover model we maximize the fifth-boundary size after choosing the fourth-ring tiles. Allowing fourth-ring holes in this maximization gives a valid upper bound `Bmax` for the full geometric problem. We include `B ≤ Bmax` and `d ≤ floor((3Bmax − 1)/254)` in the strict test. These two implied inequalities greatly improve propagation. Each of the 19 models returned `INFEASIBLE`; none reached its configured time limit. The maximum boundaries of the 19 individual relaxations ranged from 304 to 385 cells.

The fifth-ring damage relaxation initially charges certainly missed required cells and locally forced extra pockets. This underestimates or equals the official union-of-cells damage. Excluding strict gain even in that relaxation excludes a strict gain after exact geometry checks. Flood-fill cuts, if needed, preserve every legal assignment. The 19 full-domain strict tests in this archive used no additional fourth/fifth tile-pair pruning. Larger rings require different generating polyforms because the official depth-five non-tiling proof on this shape excludes a complete fifth corona. A construction with fewer than four full rings cannot exceed the exhibited equality score. This accounts for every extension of the promoted first-ring footprint.

## Reproduction and integrity

The archive contains the new 27 three-ring witnesses under `second-rings/` and the 19 four-ring witnesses under `third-rings/`. For every changed second ring, `changed-second-results.json` records the entire enumeration trace. It also records the independent boundary-size optimization and strict score test for each viable third-ring representative. All branch names refer to occupancy sets checked from coordinates by `replay.py`; reruns with a different search order may assign different numeric suffixes. `original-second/README.md` includes the ten original-second-ring branches and their strict tests.

Starting from the submitted benchmark checkout with `heesch_verify` available in the interpreter, run the following commands. The scratch outputs from `replay.py` are finite patch geometry samples. They use no external certificate to reproduce the finite optimization results.

```sh
python -m pip install ortools==9.15.6755
python submission/research/replay.py
python submission/research/replay.py --equality
python submission/research/replay.py --strict
```

To independently regenerate the 27 second-ring regions, run the command below. It skips the promoted second-ring footprint, permits all other neighbors, and sets a cap of 100 stored solutions. The recorded run exhausted the domain after 27.

```sh
t=$(mktemp -d)
python submission/research/joint.py --source submission/research/original-second/source-four.heesch \
  --full-through 3 --distinct-domain --sample-domains 100 --seconds 75 --workers 3 \
  --geometry-only --output "$t/second/sample.heesch"
python submission/research/joint.py --source submission/research/second-rings/sample-003.heesch \
  --full-through 4 --sample-domains 64 --seconds 70 --workers 3 \
  --geometry-only --output "$t/third/four.heesch"
python -m heesch_verify submission/best.heesch
```

Submission `908a0696-f1fb-48e5-9bd9-5a301e65620a` supplied the shape, the promoted first-ring and deeper geometry and its official depth-five non-tiler proof. The compilation credits polymorf’s `04699825-31f1-461e-8be0-a5013ddbde40` for the geometry and final certificate. The unchanged compressed certificate SHA-256 is `1cefa72c2147ab6e1aa9b02c9f4715f07c82a6fb9aa5175097cddf632102b10e`. Our earlier outer packing came from Attempt 02 `b0d0b076-3815-46a6-a7d7-2d65c0911764`. Attempt 03 `9e0e7ebd-81f4-4cee-a819-062af19497d4` generated the changed third-ring footprints on the original second ring. Attempt 05 `39003001-1217-4596-9f84-4ae4135049cd` optimized one such branch’s fifth ring. Attempt 06 `1e108e2f-235b-4c70-ac11-d9524c2191f7` carried the fixed-second-ring conditional bound as a historical polyhex appendix alongside its own 20-cell construction. The supplied original-branch files reproduce that appendix.

Local runs used Python 3.12.14 and OR-Tools 9.15.6755 on ARM macOS. The submitted witness passed local geometric checks for all levels and both defect counts. The shape proof previously passed the official Linux workflow for the promoted submission; Yukon’s runner supplies end-to-end scoring for this archive. The exhaustive finite patch conclusions are reproducible CP-SAT infeasibility results, separate from the global plane-nontiling certificate.
