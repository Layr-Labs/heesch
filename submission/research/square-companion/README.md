# A finite 99-square tile with a partial fourth ring

Start with a rectangle of twenty by five unit squares, with coordinates \(0\le x<20\) and \(0\le y<5\). Remove (2, 0), (7, 0), (12, 0), (17, 0), and (19, 2). Add (2, 5), (7, 5), (12, 5), and (17, 5). The resulting outline replaces the angled markings of Casey Mann's square polypillar with single-square tabs and notches. Figure 7 and Theorem 2 describe the published family. Its published bound need not carry over to this change of outline. [Mann, “Heesch’s Tiling Problem,” *American Mathematical Monthly* 111 (2004), pp. 509–517](https://faculty.washington.edu/cemann/Heesch.pdf)

The witness has 48 copies, with 7, 14, and 26 tiles in its three complete rings. A further 39 copies cover 544 of the fourth ring’s 576 required squares. The verifier counts 32 uncovered squares and 11 enclosed squares outside that required set, giving 43 charged defects. The result establishes \(H_c\ge3\) and finite Heesch number. For a 99-square tile, the record runner’s proof band ends at encoded level three. Certifying this three-ring construction for a score would require a level-four obstruction or deeper. [Exact witness](polypillar.heesch)

## Proof that the tile cannot tile the plane

Call a missing square a notch if three of its four edge neighbors belong to the tile. Call an occupied square a leaf if exactly one edge neighbor belongs to the same tile. The five removed squares are exactly the five notches. The four added squares are exactly the four leaves.

In a plane tiling, the copy that fills a notch can have at most one edge neighbor of its own at that square. It must have at least one because the tile is edge-connected and contains more than one square. Each notch therefore consumes a leaf. Two different copies cannot claim the same notch, because any two three-element subsets of its four neighbors intersect, and the copies would overlap.

Choose one reference square per copy and let \(M_R\) count copies whose reference squares are in a box of side \(R\). Pick a constant \(D\) bounding coordinate distance from the reference square to every tile square and notch, in every orientation. The \(5M_R\) notches need distinct leaves belonging to copies in the concentric box of side \(R+4D\). Consequently \(5M_R\le4M_{R+4D}\). Different reference squares occupy distinct lattice sites, so the border strip adds only \(O(R)\) copies. The inequality gives \(M_R=O(R)\). The inset box of side \(R-2D\), however, must be covered by copies counted in \(M_R\), and each such copy covers at most 99 squares. Thus \(M_R\ge (R-2D)^2/99\), a contradiction. This specializes Mann’s area-versus-boundary argument to the actual square-grid geometry.

## Replay and search lineage

From the cloned benchmark directory, pass the installed companion’s path to Python. The script reconstructs the outline, enumerates its notches and leaves, verifies every ring, and independently recounts the uncovered and pocket squares. It uses the frozen geometry verifier with default limits and requires no search solver. [Replay script](replay.py)

```sh
PYTHONPATH=. python path/to/square-companion/replay.py
```

The native placement search uses Craig S. Kaplan’s square-grid isometries, contact enumeration, and isohedral checker. The ring placements in this file came from a fresh search for the 99-square outline. [Kaplan’s heesch-sat, commit d12a527](https://github.com/isohedral/heesch-sat/tree/d12a527c04310fed51d522318126781e2f7ed56d)

Holindauer’s public Yukon submission `d3ea7fb2-01ec-43bf-bda3-beac87916e30` supplied the fixed-patch CP-SAT optimizer for the initial partial fourth ring. On this tile it left 28 required squares uncovered and 99 additional pocket squares. Removing and replacing outer copies, with a fresh exterior flood fill after each trial, reduced the charged defects from 127 to 43. [Public optimizer, commit b59317b](https://github.com/Layr-Labs/heesch/blob/b59317be68f164c65fac56103e35a6589023b738/submission/research/optimize_defect.py)
