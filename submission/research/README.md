# Replaying the six first-ring footprints

Run these commands from the benchmark root with the benchmark Python environment active.

```sh
PYTHONPATH=. python submission/research/replay.py
PYTHONPATH=. python submission/research/hinged-hex/replay.py
python -m heesch_verify submission/best.heesch
```

The first replay checks all five fresh four-ring witnesses, their difference from `original.heesch`, the achieved defect and the shape certificate’s raw digest. `first-rings.png` compares the reference arrangement with the scored third alternative. The 237-site fourth footprint has optimal charged damage 25. Reopen all outer placements and test 24 as follows.

```sh
trial=$(mktemp -d)
PYTHONPATH=. python submission/research/pack.py --seed-file submission/best.heesch \
  --candidate "$trial/unused.heesch" --budget 24 --workers 3 --seconds 65 --feasibility
```

The recorded run reports INFEASIBLE. `fixed-four-budget24.log` contains its output. The other saved budget experiment, `fixed-third-strict.log`, is for **first-rings/1.heesch**, on which a joint test ruled out the simultaneous conditions of at most three charged defects and `3B − 254d ≥ 1` after fixing its third-ring patch. The full fourth footprint and the partial fifth were free in that test. This supplementary experiment gives no additional bound on the submitted third example.

`first-rings/1.heesch` through `5.heesch` are one complete fourth-ring representative per new first footprint. `first-rings/i-coverage.json` gives the raw-coverage optimizer’s initial score on representative `i`. Repaired fifth-ring packings are provided in `first-rings/packing-i.heesch`. `first-rings/packing-summary.json` records the corresponding geometrically replayed values. Summaries of the original packed reference and the five alternatives should use the same visible center in the axial coordinate system.

## Full first-footprint enumeration

`enumerate_first.py` invokes the benchmark's frozen multilevel encoder and universe generator. `bridge.cpp` exposes the vendored CaDiCaL C++ library to Python. Build the bridge against the existing CaDiCaL build. On macOS use `-dynamiclib` as below. On Linux use a compiler and static library built with `-fPIC`, replace `-dynamiclib` by `-shared`, and pass the absolute shared output path in `HEESCH_BRIDGE`. The script consumes memory to keep the benchmark placement universe, its CNF and the incremental solver in memory. The raw four-level DIMACS alone occupies approximately 1 GiB.

```sh
trial=$(mktemp -d)
cad=build/cadical-rel-2.1.3
c++ -O3 -std=c++20 -dynamiclib -I"$cad/src" submission/research/bridge.cpp \
  "$cad/build/libcadical.a" -o "$trial/bridge.dylib"
PYTHONPATH=. HEESCH_BRIDGE="$trial/bridge.dylib" \
  python submission/research/enumerate_first.py --workdir "$trial"
```

Output paths and the order in which equally valid representatives appear can vary with a different encoder, solver build, or random settings. The first-ring footprint is the set of actual occupied cells through level one. Within one footprint, changing a second, third or fourth level can give a different full patch. The claims in the note use the installed benchmark versions.

The working enumeration used the printed 15-hex from the source as its input, fixing the center by its identity transform. Its depth-four CNF has 771,443 variables and 5,183,667 clauses before the occupancy exclusions and pocket cuts. Each first-ring world cell is linked bidirectionally to the union of its placement selectors. Excluding a successful first footprint then removes all decompositions of that occupied set at once. All cumulative patches must pass the unchanged flood fill. After the five reported new footprints, the incremental solver returned UNSAT, completing enumeration. There is no separate DRAT certificate for this research formula in the archive. The submitted plane non-tiling proof is bound to the benchmark's depth-five shape formula.
