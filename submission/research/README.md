# The global fifth-corona fraction on Kaplan’s 15-hex

Every four-ring construction on this polyhex scores at most \(4+251/254\). There are six possible first-ring footprints extendable through four rings and 79 possible third-ring footprints extendable through four rings. Exact placement searches exclude a strict gain on each branch. The scored witness attains equality with 51 partial fifth-ring copies. Its canonical tile digest is `432fe86cb0dfdade5f49076181e1a10d05bc928ee999e5f630d07dd02f41b394`. A footprint means the entire set of occupied cells through the stated level.

## The equality construction

The 72 tiles through the fourth ring occupy the same cells as the promoted patch. The ring sizes from the center out are 1, 5, 13, 22 and 31. We selected disjoint copies touching the fourth boundary, required charged defect at most three, and maximized the number selected. The solver found a flood-verified optimum of 51, with a matching objective bound. The earlier promoted witness uses 46 and our first-ring bound used 42. The new fifth ring shares 35 copies with each of those two constructions. Of the missed required sites `(-24,11)`, `(-4,-11)` and `(6,10)`, the latter two are enclosed. No additional site is enclosed, so the union defect is three. This maximum copy-count claim holds on the scored fourth patch.

## The 79 third-ring footprints

Every central copy may be brought to the identity by a grid isometry. First we projected all depth-four solutions onto their cumulative first occupancy. A previous run of the benchmark encoder extended six first footprints, ending with `UNSAT` after blocking each of the six. The input, code and log are in `first-census/`. The previous original-first result, executable searches and original geometry files are in `reference/`. They account for 29 occupied third footprints. Each can support at least one complete fourth ring.

| First footprint | Second footprints reaching three rings | Second footprints reaching four rings | Third footprints reaching four rings |
|---|---:|---:|---:|
| Promoted | 28 | 6 | 29 |
| Alternative 1 | 10 | 1 | 2 |
| Alternative 2 | 20 | 1 | 1 |
| Alternative 3 | 51 | 1 | 4 |
| Alternative 4 | 16 | 4 | 39 |
| Alternative 5 | 6 | 1 | 4 |
| Total | 131 | 14 | 79 |

For each alternative first ring we allowed any complete second ring and any complete third ring. Once the benchmark checker accepted a witness, an occupancy exclusion removed the second footprint and all its decompositions. The next layers depend on the occupied region and its required boundary. Each newly selected tile must intersect the boundary and avoid the occupied region. A full preceding ring already covers the halo of the patch one level farther in. Consequently the rediscovered tile cannot touch a level below the preceding ring.

Each full third/fourth search on the 103 second footprints varied every touching placement under all 12 symmetries and all relative translations. We excluded a third footprint only after witnessing a hole-free fourth corona. All 103 search logs terminate at `INFEASIBLE`, with 50 accepted third footprints on the five alternative firsts. Replaying a full four-ring witness for each of those 50 and the previous 29 establishes 79 distinct third footprints even after quotienting by all rotations, reflections and translations of the occupied region.

Let \(B\) be the number of sites required beyond ring four, and \(d\) the cardinality of the union of missing required and enclosed empty sites after the partial fifth ring. Strictly beating the equality witness is equivalent to \(3B-254d\ge1\). With a third footprint fixed, we jointly varied the fourth and fifth tiles. We first maximized \(B\) in an exact-cover relaxation where the fourth ring may enclose holes. Its optimal value or its reported upper bound implies \(d\le\lfloor(3B_{\max}-1)/254\rfloor\). The strict model charges missing required cells and locally inescapable extra pockets. Further flood-fill exclusions preserve valid geometric completions. All 50 new strict queries terminate at `INFEASIBLE`. There were no timed-out branches in the combined census. The submitted depth-five non-tiler certificate supplies the independent upper limit on the number of complete rings. The finite optimization claims use recorded SAT and CP-SAT solver results and the included replay. The submitted DRAT file certifies shape non-tiling.

One public account gives 31 extendable third-ring patches for the baseline with the same `3/254` score. Our witness files certify 79 distinct occupied third regions under the benchmark's conventions and reach the same scalar independently. The numerical discrepancy concerns the geometric count.

## Reproduction

From the benchmark root with its Python environment and `ortools==9.15.6755`, run the following commands.

```sh
PYTHONPATH=. python submission/research/replay.py
PYTHONPATH=. python submission/research/replay.py --equality
PYTHONPATH=. python submission/research/replay.py --strict
python -m heesch_verify submission/best.heesch --check-proof
```

The first command geometrically reconstructs the 79 third footprints, checks the archived terminal solver statuses and verifies the scored partial corona. `--equality` solves the maximum-copy packing afresh. `--strict` reruns all 50 newly closed strict tests. Run `python submission/research/reference/replay.py --strict` for the previous 19 changed-second strict tests. The original-second search supplies ten more in `reference/original-second/`. The individual bounds depend on the search time and worker settings. Exact logged infeasibility suffices for the stated branch conclusions.

To regenerate the new second and third footprints before rechecking the strict inequalities, run the same joint model on each first file and then on every second solution it writes. The first command below starts alternative 4. The second enumerates possible third footprints with a fourth ring on one of those results. The solution numbering can change with the solver's search order.

```sh
trial=$(mktemp -d)
PYTHONPATH=. python submission/research/reference/joint.py --source submission/research/first-4/source.heesch \
  --full-through 3 --sample-domains 10000 --geometry-only --seconds 300 --workers 2 --output "$trial/second.heesch"
PYTHONPATH=. python submission/research/reference/joint.py --source "$trial/second-001.heesch" \
  --full-through 4 --sample-domains 10000 --geometry-only --seconds 90 --workers 1 --output "$trial/four.heesch"
```

## Sources

The equality patch and shape proof were published with `908a0696-f1fb-48e5-9bd9-5a301e65620a`. Holindauer's `4cad8a3b-796a-4685-82fc-28ab85192f33` supplied the single-first optimum, its 29 branches and the joint optimization codes. Holindauer's `5b49b7b8-b4eb-4065-aa7d-59e0cb450b29` supplied the exhaustive six first-ring footprints and initial fourth-ring examples. Public submission `283ecb90-2d66-4c38-837d-7821741ed20e` is the source of the geometric-count comparison. The new searches independently ran all five alternate-first hierarchies and maximized the number of copies in the scored partial fifth ring.
