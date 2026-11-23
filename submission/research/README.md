# Near-periodic square tilings with incompatible lattice symmetries

Each generated polyomino has an explicit near-cover of a finite square-grid quotient. The determinant is the number of residue cells under the translations `(A,0)` and `(B,C)`. Each source cell has one Boolean selection variable shared by all placed copies. Selecting it occupies every residue in its image; an exact search prohibits duplicates and permits a fixed number of empty sites. Coordinates, rotations, reflections, period shear and placement translations are sampled without an existing Heesch tile as a seed. The emitted shape must be edge-connected and hole-free.

The four- and six-copy pilot and mixed families start from two rows of rectangular tile footprints. Reflected or rotated copies join across the row boundary; the second row can be shifted and twisted. Follow-up two- and three-copy searches require at least one relative isometry whose linear part sends one of the two periods outside the period lattice. Thus it does not induce an action on quotient residues. Different representatives of a residue can give different images in the next copy. Only the selected finite outline must lift unambiguously under each pose. Every admissible result in those two searches has one, two or three missing residues.

| Family | Proposed templates | Geometrically distinct outlines in batch |
|---|---:|---:|
| Rectangular rows | 12,000 | 120 |
| Rotated rows with irregular spacings and periods | 1,500,000 | 848 |
| Two-copy incompatible symmetry | 55,000 | 8,086 |
| Three-copy incompatible symmetry | 65,000 | 2,660 |

The four batches yielded 11,054 distinct outlines. Of these, 9,758 were absent from 83 direct prior coordinate banks. Independently verified four-ring patches appeared on 257 distinct shapes. Every depth-four shape yielded an exact plane-tiling certificate. A further two distinct shapes had period certificates despite a timed-out initial four-ring search. The quotient recheck assigns every cell under every listed motion and confirms exactly one occupant of each residue.

For 253 fresh shapes, explicit deficient matching certificates proved non-tiling. Vacancies bordered on at least two sides by a receiving copy need a neighboring donor square. In a plane tiling two receiving copies cannot charge the same donor cell: if their sets of neighboring receiver cells each have at least two elements and were disjoint, they would use all four incident sides, leaving no neighboring square in the connected donor tile. An exact collision test gives the available donor positions and a bipartite matching supplies the deficient demand set. Repeating the set across a growing square makes the deficit proportional to area while outside contributions grow only with perimeter. Independent validation reproduced all 253 certificates. The bounded searches among these candidates produced one full first ring, and no full second or third ring.

## Fresh finite witness

The stage in `fresh-finite/submission` contains the candidate `interface2_7900`. It comprises 17 square cells. A reflected copy and its partner occupy 34 of 36 sites in a quotient with generators `(12,0)` and `(3,3)`. The shape has eight charged recesses whose only possible donor positions span seven cells. Its first ring passed the frozen verifier. A native checked DRAT refutation of the complete benchmark formula `F(S,2)` proves the hole-permitting second ring impossible. The formula has 73,051 variables and 229,748 clauses. The compressed proof is 105,876 bytes. A partial second ring covers 87 of 99 required cells, with 12 charged defects, giving a scalar of **62/33**, approximately **1.878788**.

A second, previously explored 17-square shape independently arose from both incompatible-period families. It has full certified `Hc=Hh=1`. Its separate checker evidence under `interface3/upper` was retained for comparison. The higher-scoring benchmark submission stays ahead of both.

`models.tsv` stores every executed template’s parameters and bounded search outcome. `routes.tsv` contains each unique outline's local coordinates and quotient motions. `all.tsv`, `fresh.tsv`, `old.tsv` and `direct-prior.paths` cover the global deduplication. `four.tsv`, `periods.tsv`, `high-periods.tsv` and `unknown*.tsv` in the individual groups retain the free-placement search and quotient diagnostics. `hall.tsv` gives donor counts and geometric deficient subsets; `charged1.tsv`, `charged2.tsv` and `charged3.tsv` record the fresh finite candidates' witnessed rings.

`audit.py` independently reconstructs the quotient occupancies, canonical outlines, four-ring charts, complete periods and all relevant matching certificates. `audit.json` records those checks and both finite proof manifests. The generation binaries take output bank, route and run-log paths followed by proposed trials and fixed seed. `interface` adds the number of copies. The seeds in table order are 69733, 787391, 612973 and 918741. Run `audit.py` and `stage.py` with the challenge's pinned Python environment and `PYTHONPATH=heesch` from the project root.
