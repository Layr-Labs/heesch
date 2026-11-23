# A 22-triangle tile from the empty space between five copies

Five copies of an 18-triangle piece surround a 22-triangle cavity. We took the cavity as a new outline and found 44 copies of it forming three solid rings. It matches the sixth tile in Craig S. Kaplan’s list of 22-iamonds reaching two rings. The listed values are \(H_c=H_h=3\). Our independently generated \(F(S,4)\) refutation establishes the upper bound in Yukon’s proof system. The earlier construction in our 22-iamond submission matched catalogue record three. [Kaplan’s 22-iamond data](https://cs.uwaterloo.ca/~csk/heesch/iamond/22iamond_2up.txt) · [Earlier 22-iamond construction](https://github.com/Layr-Labs/heesch/tree/9a6b909b87b37b66f491f837943d29c5d7b56748/submission)

The submitted patch has a center and rings of 6, 13 and 24 copies. Its partial fourth ring has 39 more copies. They cover 289 of 357 required sites. Of the 88 charged defects, 68 are missing required triangles and 20 are additional sites enclosed by the combined patch. This gives \(3+269/357=1340/357\), approximately 3.75350. Our first packing on a different third-ring footprint cost 132 of 362. The two packings and the data for coordinate-frame searches are archived.

## Recovering the cavity

We started from the center and five edge-touching neighbors in our earlier 20-iamond submission. We expressed each neighbor in the center tile’s coordinate frame, removed cells `(1,4)` and `(0,6)` from the prototype of every neighbor, and kept all five placement maps fixed. An edge flood fill from `(3,3)` stops after exactly 22 cells. The unchanged 20 central cells and two newly exposed cells form the new outline. It is connected and has a legal orientation inside the span cap. The cut neighbors each have 18 cells. The archived figure shows the difference between those neighbors and the 22-cell copies used in the scoring patch. [20-iamond source witness](https://github.com/Layr-Labs/heesch/tree/4760bd56688f86c7f14a4fb2af648b908f8e4b09/submission)

Our previous polyhex experiment used the same geometric question on 13-hex neighbors and produced an 18-hex periodic tile. Here the neighbor edits, empty-site flood fill and all symmetry offsets use the triangular grid. A legal triangular cell has barycentric site coordinates `(3u+r,3v+r)` with `r` equal to 0 or 1. Losing the orientation bit changes which triangles touch. [Earlier hexagonal cavity](https://github.com/Layr-Labs/heesch/tree/242d6d47b7a5d0a0b354d6e154e37b84a1ea5bbb/submission/research)

## Searching other gaps between tiles

The five source witnesses supplied 70 distinct, fully edge-covered neighbor configurations. We tried 9,000 edits per configuration. The generator discarded overlapping neighbors and empty components that reached the cutoff. Of 630,000 proposals, 87,532 had disjoint neighbors and 38,984 closed around a connected, hole-free cavity in the tested size interval. Checking changed outlines, legal spans and symmetry equivalence left 5,038 distinct outlines with areas 19 through 39. A separate Python program rebuilt every outline from its source witness and recorded edits. These counts describe this search family.

Eight outlines found or still under consideration in the fourth- and fifth-ring screens have exact periodic tilings. Each saved translation domain contains 2 to 8 copies. The replay assigns each triangle to its translation residue and verifies one occupant per residue. Six five-ring patches were independently verified. They illustrate how a deep patch can also occur in a repeating tiling.

For 299 outlines the exterior triangles sharing two edges with a central tile outnumber the tile’s one-neighbor tips. Covering such a vacancy in a plane tiling consumes a tip of another copy. Two disjoint tiles cannot both impose this two-edge demand on the same triangular site. Counting in an expanding patch gives a positive deficit proportional to the number of interior copies, while the boundary accounts for only a linear number of exceptions. The archive saves actual vacancy and tip coordinates for all 299. The scored outline has a separate obstruction.

## Two plane obstructions for the scored outline

The first argument enumerates every feasible neighborhood covering the edge vacancies of the central tile. There are 222 relative placement motions after excluding overlaps and impossible enclosed-area residues. There are 15,773 disjoint, edge-covering neighborhoods. Every neighbor relation in a tiling must have a compatible reciprocal relation. Two reciprocal deletions leave 11,383 neighborhoods. Requiring each retained neighbor to carry a neighborhood compatible with the placements already around the central tile leaves 888, then 17, then zero neighborhoods. A plane tiling would survive every deletion.

The benchmark’s frozen multilevel encoder separately produced \(F(S,4)\) with 905,803 variables and 5,254,695 clauses. CaDiCaL returned UNSAT and native `drat-trim` verified its proof on the original formula. Extracting 388,836 original clauses and solving that subset gave a shorter binary DRAT. We replayed the shorter proof on the original 5,254,695 clauses. `drat-trim` verified it and produced LRAT, which also passed `lrat-check`. The actual Yukon payload is the short DRAT compressed to 3,624,832 bytes. It binds the canonical outline to the full formula.

## Reproduction

Run the following commands from the frozen benchmark checkout with its Python environment active. The generation step uses a C++17 compiler. The witness and certificate replay through Python uses the benchmark’s own triangular grid, contact rules and flood fill.

```sh
PYTHONPATH=. python submission/research/check.py
PYTHONPATH=. python submission/research/cavity-bank/replay.py
PYTHONPATH=. python -m heesch_verify submission/best.heesch
cd submission/research/cavity-bank
c++ -std=c++17 -O3 cavities.cpp -o cavities
./cavities charts.txt rebuilt-bank.tsv rebuilt-origins.tsv 9000
```

`check.py` reconstructs the selected cavity, checks the catalogue entry up to triangular symmetry, replays the three-ring chart, recomputes both components of defect, verifies the independent local neighborhood count and hashes the decompressed proof. `cavity-bank/replay.py` verifies the stored construction history for all 5,038 outlines together with the emitted patches and periodic witnesses. The five source witnesses are in `cavity-bank/parents`. The independent native DRAT and LRAT check summaries are in `research`. Public sources supplied the 20-iamond center, the other four donor witnesses, the earlier hexagonal cavity idea and the fixed-footprint coverage optimizer. We used Kaplan’s `heesch-sat` and independently tested each patch it emitted with the benchmark verifier. [Placement search](https://github.com/isohedral/heesch-sat/tree/d12a527c04310fed51d522318126781e2f7ed56d)
