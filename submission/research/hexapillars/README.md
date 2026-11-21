# Two five-ring triangular constructions

Casey Mann proved that the marked row of four hexagons has Heesch number 5. Its boundary has one more notch than bump. We recovered the edge pattern from the public five-hexagon drawing and checked all 2,005 shared edges in that drawing. Its three interior hexagons have identical marks. We deleted one interior hexagon, searched for a fresh patch of the four-hexagon tile, and checked all 986 shared coarse edges. We then rasterized the bump-and-notch outline as unmarked elementary triangles. [Mann, “Heesch’s Tiling Problem,” Theorem 1 (2004)](https://faculty.washington.edu/cemann/Heesch.pdf) · [Five-hexagon source drawing](https://commons.wikimedia.org/wiki/File:Heesch-5.svg)

`mann-four-pillar.heesch` records 121 exact placements of the 215-triangle outline. After the center, the five hole-free rings contain 5, 11, 23, 34 and 47 copies. Its minimum span sum is 92. The benchmark limits are 200 cells and span sum 29. The replay uses bounds of 215 and 117, the latter being the span sum of the saved orientation. The finite Heesch number comes from Mann’s theorem. The replay checks the five-ring lower bound.

`18-iamond.heesch` arose from shortening and perturbing triangular outlines derived from the five-hexagon chart. It fits the benchmark geometry limits with 18 cells and span sum 20. The 113-copy patch consists of the center and rings of 6, 15, 22, 29 and 40 copies. This outline tiles the plane, ruling it out as a finite-Heesch submission.

`18-iamond-period.json` supplies all 12 rigid motions in a fundamental domain. Each triple holds the frozen triangular-grid orientation index followed by its translation in benchmark coordinates. The period vectors in paired-triangle lattice coordinates are `(18, 0)` and `(6, 6)`. Each period has 108 triangle pairs. The replay checks that all 216 individual triangles have multiplicity one.

Run the following from the benchmark root, replacing `path/to/companion` with this directory’s relative path.

```sh
PYTHONPATH=. python path/to/companion/replay.py
```
