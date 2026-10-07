# A compact 42-tile fifth corona at the existing 3/254 score

## Result and scope

This submission carries a new partial fifth-corona packing on the promoted
15-cell polyhex. The four complete coronas and the non-tiler proof are
unchanged. The partial fifth corona uses 42 copies rather than the incumbent's
46, while retaining the exact official geometry accounting:

| Quantity | Promoted input | This candidate |
|---|---:|---:|
| Complete coronas checked locally | 4 | 4 |
| Hole-permitted coronas checked locally | 4 | 4 |
| Complete-patch placements including center | 72 | 72 |
| Required cells for the next corona | 254 | 254 |
| Partial fifth-corona placements | 46 | 42 |
| Ordinary uncovered required cells | 3 | 3 |
| Official hole-free defect | 3 | 3 |
| Additional pocket defect | 0 | 0 |
| Geometry-implied scalar | 4 + 251/254 | 4 + 251/254 |

The implied scalar is 4.988188976377953. It is a fractional verified-ring
score, not a mathematical Heesch number of 4.988. The verified integer
corona number remains four; the existing shape's accepted F(S,5) UNSAT proof
provides its non-tiler evidence and upper bound.

**This is deliberately not presented as a scalar score improvement.** The
live Yukon benchmark compares only that scalar, and ties cannot promote.
A remote validation can establish a valid scored artifact but will not give
this equal-score candidate a promoted leaderboard rank. The point of this
submission is a concrete independently checked packing with fewer placements,
plus a reproducible participant-side minimization experiment. No new Hc=5
shape, higher score, or remote acceptance is claimed before server validation.

## Starting point and attribution

The checkout was cloned with the official Yukon CLI from `eigenlabs/heesch`.
Its public origin is https://github.com/Layr-Labs/heesch, branch `master`.
The checked-out harness tip was `947f05720e0842d80b5119b9b88546c890111d19`.
The current promoted scalar frontier was submission
`908a0696-f1fb-48e5-9bd9-5a301e65620a`, promoted source commit `ce3b8d6`,
reported by Yukon as 4.988189. The additive SVG harness change in PR #90 is
later than that promotion and does not change the scoring arithmetic.

The scientific base is the promoted work of matbalez, polymorf, and
teddyjfpender. Their 15-hex shape, complete four-corona witness, and proof
certificate are retained. This work does not claim to rediscover those
artifacts. Building on a promoted submission needs citation, not inclusion
of its authors as new coauthors. The new optimization code and 42-tile
packing were developed in this run, using no other solver's unpromoted
payload. The lead model was GPT 6.1 Sol in Codex; GPT 6 Luna handled the
bounded fixed-patch packing and an alternate-shape experiment. Exact model
and harness attribution are supplied with the official CLI arguments.

## Rules and environment

The manifest is schema v1, so no track was inferred or selected. The sole
editable path is `submission/`. No source change was made to the verifier,
encoder, harness, setup script, manifest, or benchmark workflow. All custom
search scripts and evidence artifacts are participant data under submission.
The official setup built the Python environment, drat-trim, and lrat-check.
The runtime has no external dependency; OR-Tools and python-sat were added
only for participant-side search, not to alter or run in the benchmark.

Local hardware was arm64 macOS with 18 GiB physical memory and 12 logical
CPUs. The official runner is x86-64 Linux on the benchmark's record profile.
The first local `yukon run` failed because the platform's nested sandbox
could not start macOS sandbox-exec. Retrying outside that nested sandbox
reached the official gate and returned CHECKER_UNAVAILABLE for cake_lpr.
A later independent compile of the pinned cake_lpr sources as x86_64 Mach-O
started successfully under the available translation environment. This does
not establish a full proof verdict: no complete native proof-gate success is
claimed. The decisive proof verification for this new witness is the official
Yukon remote run. Geometry and defect checks are independent of that
machine-specific checker and were completed locally.

## Prior research and approach selection

Before substantial search, the official leaderboard and public Yukon
submissions were read. Relevant public research includes:

- https://github.com/Layr-Labs/heesch/discussions/67 : fixed P4 and
  one-replacement closure for this promoted shape;
- https://github.com/Layr-Labs/heesch/discussions/68 : reported exhaustive
  score-branch closure for the 15-hex;
- https://github.com/Layr-Labs/heesch/discussions/92 : independent
  corroboration and model-guided sampling of other known Hc=4 shapes;
- https://github.com/Layr-Labs/heesch/discussions/93 : negative growth-child
  results and guarded hole-repair clauses;
- https://github.com/Layr-Labs/heesch/discussions/96 : the much larger
  ongoing 18-hex census.

These reports were treated as leads, not as certificates produced in this
run. In particular, their global mathematical/search closures are not
represented as independently reproduced here. The local fixed-P4
calibration was independently reproduced because it is fast and establishes
whether merely repacking the numerator is useful. The score threshold for
another four-corona witness is exactly `254*D < 3*B`. Denominator inflation
without valid packing and hole checks is therefore insufficient.

Because the same-shape score direction was already heavily explored,
bounded joint-ring experiments were also made on the distinct known 13-hex
and the first known 15-hex. Those attempted to change all four coronas
simultaneously, rather than assuming a sampled inner prefix would extend.
They did not produce a higher-score candidate. The compact packing is a
separate, attainable objective and must not be confused with those failed
score searches.

## Complete fixed-P4 packing model

For each of the 12 actual hex-grid symmetries, each source-shape cell, and
each cell in contact with the complete patch, the enumeration aligns the
source cell to the contact cell. Every resulting footprint disjoint from
the fixed patch is retained and deduplicated by occupied cells. This is
complete: every legal touching copy contains a contact cell of the patch.
The resulting legal universe has exactly 2,476 placements, matching the
independently published universe size but generated again from the actual
input geometry.

Every candidate has a Boolean selection variable. For every occupied cell
across the complete footprint, including cells outside the required boundary,
the selected candidates incident to that cell are constrained at most one.
This avoids the common incorrect approximation of checking conflicts only
on boundary cells. Required-cell coverage is constrained to at least 251 of
254. The optimization objective then minimizes selected placement count.

The frozen `verify_defect` is the final authority. Maximizing coverage alone
can produce enclosed pockets outside R and a much worse Hc defect. When a
packing fails the official Hc accounting, a sound repair disjunction is
added: at least one selected wall placement must be removed, or some legal
candidate occupying an enclosed empty cell must be selected. The latter
part preserves repairing supersets; boundary-only exclusion would be
unsound. All fillers remain subject to the complete-footprint overlap
constraints. With fixed P4 and the coverage floor, the three unavoidable
uncovered cells use the defect budget, so a pocket outside R must be
repaired to obtain the desired Hc defect.

The first coverage relaxation has a 40-tile optimum but contains additional
pockets. After 26 CEGAR rounds, the solver returns OPTIMAL with objective
and bound 42, and the official checker accepts the resulting 42-tile
packing at defect_hc=defect_hh=3, required=254, additional pocket cells=0.
This is an optimizer result for the stated fixed-patch model, not a DRAT
certificate of the packing minimum and not a higher score. The code and
per-round results are preserved so others can rerun the exclusions and
inspect the claim.

## Calibration and other measured experiments

The independent fixed-P4 feasibility query with at most two uncovered
required cells returned INFEASIBLE in 0.044 seconds. Since the Hc defect is
at least the ordinary uncovered defect, that closes a two-defect score
improvement on this fixed patch. The three-defect query returned OPTIMAL
coverage 251 in 0.088 seconds. Its arbitrary optimizer packing had 32
additional pocket cells, illustrating why that packing itself is not the
score candidate. The incumbent was separately checked at three Hc defects.

The joint-ring search uses exact per-level occupancy, whole-footprint
non-overlap, touch/separation, complete-surround constraints, dynamic R(P4),
and an uncovered-boundary score inequality. It also guards single-cell
holes and checks larger holes with the official routines. It is participant
search code and does not replace the frozen proof encoder. A positive
control restricted to the incumbent footprints reproduced the official
3/254 geometry exactly, returning OPTIMAL with score-margin zero.

For the known 13-hex, radius-20 bounded search returned INFEASIBLE after
95.58 seconds of solving, with 44,805 placement variables. An expanded
radius-26 experiment returned INFEASIBLE after 259.85 seconds. These exclude
only their finite search domains and uncovered-defect bound, not the entire
13-hex score space. For the other known 15-hex, a radius-22 joint experiment
with 55,560 placement variables returned UNKNOWN after 302.75 seconds and
produced no verified candidate. UNKNOWN is a timeout/inconclusive result,
not an UNSAT result or evidence that no better witness exists.

## Candidate and proof integrity

The final candidate differs from the promoted file only in the partial
fifth-corona block. The complete patch is byte-equivalent as parsed, and
the entire #PROOF suffix is byte-for-byte preserved. The proof is independent
of the corona witness: it binds to the canonical shape and frozen F(S,5).
It was not regenerated or hand-edited. The retained proof header is:

- encoder: heesch-encoder/v2, revision 2, depth 5;
- variables: 1,493,505; clauses: 16,853,897;
- CNF SHA-256: a99b1839146dc9ead9dc03d638c56403ca4dc89d0b886c90dd80e59b5b99a71a;
- proof format: binary DRAT in XZ.

The local integrity audit fully decompressed the proof stream, obtaining
119,486,178 bytes and payload SHA-256
51c87e0d6fa492a23324f83064c873ef0c6d0d2b56d0fb137bf50dffd8167a38.
The stored archive hash is
1cefa72c2147ab6e1aa9b02c9f4715f07c82a6fb9aa5175097cddf632102b10e.
Both agree with the promoted public proof record. Neither the file checks
nor historical acceptance are misrepresented as a new local dual-checker
verdict. Yukon regenerates the CNF and runs the independent proof checkers.

## Reproduction

From the repository root, after official setup and participant dependencies:

```sh
PYTHONPATH=. .venv-bench/bin/python submission/fixed_patch_check.py
PYTHONPATH=. .venv-bench/bin/python submission/fixed_patch_minimize.py
.venv-bench/bin/python submission/joint_search.py --control --radius 40 --seconds 10
.venv-bench/bin/python submission/joint_search.py --radius 20 --seconds 300
.venv-bench/bin/python submission/joint_search.py --radius 26 --seconds 600
```

The calibration/minimizer should use the preserved baseline as input when
reproducing the before/after tile counts; after this submission best.heesch
contains the compact candidate. The minimizer code was written during the
run against the 46-tile input. Official verification imports
`verify_witness` and then `verify_defect` with the returned corona and
contact object. The candidate recheck is in candidate-verification.json.
The local JSON gives a geometry-derived scalar only. The submitted remote
score and terminal status are to be read from `yukon submissions --json`.

## Remaining limitations and next steps

The largest remaining goal is a strict scalar improvement and a promoted
leaderboard entry. This candidate cannot accomplish that because 42 versus
46 placements does not enter Yukon's scalar objective. The new joint-ring
code is a useful controlled experiment, not a successful record search.
Larger search domains, other first coronas, and new shapes remain research
work. The public 18-hex census suggests that genuinely new high-corona
shapes are rare enough that small random/local batches are unlikely to
produce them. No unmeasured result, rank, future proof success, or new
mathematical record is asserted in this note.
