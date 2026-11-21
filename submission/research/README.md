# Census construction with a partial fourth corona

This archive contains a concrete eight-cell polyhex construction with three
complete coronas and a partial fourth corona. The unchanged Yukon benchmark
ran locally and reported **3.839695**. The exact defect contribution is
`110/131`, so the unrounded arithmetic value is `3 + 110/131`.
This is a reproducible submission-pipeline experiment, not a five-corona
claim or a claim to improve the current promoted frontier.

Effort: xhigh. Work was performed using GPT 6 Astra in the Codex harness.
The candidate was generated and evaluated on macOS ARM64 with 48 GiB RAM.
The model and harness are also supplied through Yukon's dedicated attribution
flags. No external collaborators participated.

## Construction and measured result

The submitted polyhex, in the benchmark's axial coordinate convention, is:

```text
H 0 0 1 0 -3 1 -1 1 0 1 1 1 -3 2 -2 2
```

The shape is connected, has no holes, and lies inside the complete eight-cell
polyhex census accepted by the benchmark. Its canonical digest is
`54ccb5993100828f18313d229fe479842bd6652c5962f8be4c0acad41ffb32fd`.
The census establishes that this shape has `Hc = Hh = 3`; this submission
supplies actual placements for that value and a separately checked partial
next corona.

| Measurement | Result |
| --- | ---: |
| Shape cells | 8 |
| Complete patch tiles, including the center | 38 |
| Verified Hc | 3 |
| Verified Hh | 3 |
| Required cells on corona 4 | 131 |
| Partial corona-4 tiles | 30 |
| Uncovered required cells, Hh view | 17 |
| Additional enclosed pocket cells | 4 |
| Hc defect | 21 |
| Scored fraction | 110/131 |
| Benchmark score, as written to score.json | 3.839695 |
| Non-tiler evidence | census |
| Record eligible | false |

The distinction between the two defect counts matters. The partial tiles
cover 114 of the 131 required cells, but four additional enclosed pocket
cells count against the hole-free objective. The score therefore uses
`1 - 21/131`, not `1 - 17/131`. Both quantities were measured by the
benchmark's own `verify_defect` implementation. The file's claims match
those measurements.

The complete `submission/best.heesch` file has SHA-256
`42299f76c9a28eca5bc186dd125e3b19427a900558d57f5ad27a53dbd340d12d`.
It contains the shape, the full three-corona patch, and the `#DEFECT` block.
It has no proof block because census membership supplies the required
non-tiler evidence. No proof from a different shape has been copied,
transported, or edited into this construction.

## Source and provenance

The census shape and initial search machinery come from Craig Kaplan's
public [heesch-sat repository](https://github.com/isohedral/heesch-sat),
pinned to commit `d12a527c04310fed51d522318126781e2f7ed56d`.
The shape was selected from `data/hex/nontile-8.txt`; its three-corona
placement patch was reconstructed locally using that searcher. The emitted
patch is retained as `submission/research/seed-h3.heesch`.
This is a known shape, not a newly discovered polyhex.

The initial challenge checkout was
`947f05720e0842d80b5119b9b88546c890111d19` from
`https://github.com/Layr-Labs/heesch`. The original inherited submission
was preserved outside this archive before preparing this candidate.
No previous Yukon submission's shape, placement witness, partial-corona
packing, proof artifact, or search implementation is incorporated into
this census construction. Public Yukon notes were consulted during
separate exploratory work on larger shapes, but those larger-shape
experiments and their descendants are not part of this archive.

The native searcher normally uses CryptoMiniSat. For this local run its
small solver API surface was adapted to the benchmark's pinned CaDiCaL
2.1.3 library. The adapter is included as
`submission/research/native/cryptominisat.h`. It maps zero-based signed
literals to DIMACS literals, forwards clauses and solve calls, and exposes
the resulting assignment. A small `boost::hash_combine` compatibility
header is also included under `submission/research/native/boost/functional/`.
These headers affect search only. They are not replacements for any
benchmark code or correctness gate.

The partial-corona optimizer is new code in
`submission/research/optimize_defect.py`. It uses OR-Tools CP-SAT
9.15.6755, the installed benchmark geometry definitions, and the unchanged
benchmark verifier. Neither the submitted archive nor the reproduction
procedure changes `heesch_verify`, `heesch_encoder`, `harness`, `tools`,
the benchmark manifest, or the scoring scripts.

## Search method and its scope

The seed patch is held fixed. Let `P` be the occupied cells of that
hole-free three-corona patch and `R` the benchmark's required set outside
`P`. To enumerate every legal touching placement, the optimizer applies
each genuine grid orientation to the shape and aligns each oriented
shape cell with each cell in `R`. A touching tile must contain a required
cell, so this enumeration does not impose an arbitrary placement radius.
Translations must be legal for the grid. Placements intersecting `P`
are discarded and identical occupied cell sets are deduplicated.

This produced 1,327 candidate placements for the submitted seed. Each
candidate has one Boolean selection variable. For every cell that could
be occupied by multiple candidates, an at-most-one constraint prohibits
overlap. Since selected tiles cannot overlap, their individual counts
of covered required cells add without double counting.

The CP-SAT objective first maximizes required-cell coverage, then minimizes
tile count among equally covering packings. In code, the multiplier for
coverage is the number of candidate placements plus one, so the secondary
tile-count term cannot sacrifice even one covered required cell.
Parameters were four search workers, random seed `20261120`, and a
45-second time limit.

Each improving solver assignment is passed through the real geometry
and defect verifiers before it is written. The saved incumbent is ranked
by actual Hc defect, then Hh defect, then tile count. Thus the saved file
is chosen using the scored quantity even though the integer-programming
objective is a simpler coverage surrogate. The callback records pockets
explicitly, checks the serialized witness again, and saves only a
successfully verified construction.

CP-SAT reported `OPTIMAL` in approximately 0.107 seconds for the
coverage-and-tile-count objective. Its objective and bound were both
151362. This does **not** establish globally optimal Hc defect, globally
optimal packing over different three-corona witnesses, or any bound on
larger shapes. In particular, a packing with slightly less direct
coverage but fewer pockets could improve the scored result. The full
search configuration and solver report are in
`submission/research/optimization.json`.

Intermediate saved constructions had Hc defects 88, 74, 64, and 21.
The final saved packing retained defect 21 while reducing the number of
uncovered required cells from 18 to 17; the extra pocket penalty explains
why this did not increase the score. The report distinguishes the
mathematical coverage objective from the official scored objective.

## Reproduction and validation

Use Python 3.12 or a compatible supported Python and install the benchmark
according to its own setup instructions. The local environment used Python
3.12.14 and OR-Tools 9.15.6755. The scored file is self-contained and does
not require OR-Tools to verify; OR-Tools is needed only to repeat the
partial-corona search.

From the benchmark root:

```sh
python -m pip install -e .
python -m pip install ortools==9.15.6755
python submission/research/optimize_defect.py \
  submission/research/seed-h3.heesch /tmp/reconstructed.heesch \
  --seconds 45 --workers 4 --seed 20261120
python -m heesch_verify /tmp/reconstructed.heesch
python -m heesch_verify submission/best.heesch
yukon run
```

Parallel CP-SAT search may select a different equivalent packing on a
repeat run. The archived witness and its SHA-256 identify the exact
submitted construction; verifying that file is deterministic. The
optimizer writes a sibling `.search.json` with measurements of each run.
Its comments and report delimit the fixed-patch search scope.

To reproduce the native seed generation, clone the pinned `heesch-sat`
source separately, build the benchmark's pinned CaDiCaL with the normal
`bash tools/build_solver.sh`, and compile upstream `src/sat.cpp` and
`src/isohedral.cpp` with C++20, the included adapter directory on the
include path, the CaDiCaL source include path, and its built static library.
Run the resulting executable with
`-isohedral -hh -show -maxlevel 5`, feeding it the shape line above with
the initial marker written as `H?`.
The locally reconstructed seed took about 23.9 seconds and passed
`python -m heesch_verify` before any partial tiles were added.
The seed is archived so repeating the native build is optional.

The unchanged `yukon run` completed successfully for this final candidate
and printed `Benchmark complete (score: 3.839695)`. A compact copy of the
actual `score.json`, with only its large SVG field omitted, is included
as `submission/research/local-score.json`. The official runner remains
responsible for independently evaluating the submitted archive.

An earlier attempt to evaluate the inherited proof-bearing baseline on
this ARM Mac stopped at `CHECKER_UNAVAILABLE` for the Linux-only
`cake_lpr` binary. That limitation was not bypassed. The present census
candidate instead passes the normal, supported census non-tiler gate.
For future shapes outside the census, the required workflow remains
`python tools/prove.py submission/best.heesch --check`, with generated
proof artifacts checked again by the official runner.

## Next construction steps

The most direct improvement for this fixed seed is to optimize the actual
hole-free defect rather than coverage alone: eliminate pockets, search
alternative three-corona boundaries, and compare verified incumbents.
For the five-ring objective, a different shape outside this census is
necessary. A five-ring placement must be verified and accompanied by
the appropriate non-tiler proof; a deep SAT search, a solver timeout,
or a nearly complete partial corona is not that result.

This submission records a concrete construction and a functioning
verification-and-submission loop. It makes no claim that the selected
polyhex or the partial packing is new, and no claim of a new Heesch record.
