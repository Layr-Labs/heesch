# Heesch verifier — architecture specification

Normative: what the verifier and the harness accept, in what order, and what
they record. Section numbers are cited from code and tests (`architecture
§N`); they are stable. Companions: `heesch-cnf-encoder-spec.md` (encoder v1),
`heesch-multilevel-encoder-spec.md` (encoder v2 — the proof formula),
`soundness-note.md` (theorems + obligations), `CONVENTIONS.md` (frozen
constants), `THREAT-MODEL.md`, `submitting.md` (the participant guide).

Terminology (Kaplan 2022, arXiv:2105.09438): a *corona* is a ring of copies
surrounding the accumulated patch; `Hc` counts hole-free coronas, `Hh`
allows holes in the outermost corona only; `Hc <= Hh <= Hc + 1` for
non-tilers; a plane tiler has no finite Heesch number.

## 1. Purpose

Grade the claim "shape `S` has Heesch number ≥ k" from a plain-text file,
and score it only when *proven*: the witness proves the lower bound, and the
shape's non-tilerhood — without which "Heesch number" is not finite — is
proven by census or by a checked UNSAT proof. Nothing is trusted from the
participant except bytes.

## 2. Jobs and gates

Three jobs, one-way dependencies:

- **Job A — witness verifier** (`heesch_verify.witness`, stdlib-only):
  independently re-derives `Hc >= k` / `Hh >= k'` from the submitted patch.
  The same code is published to participants and run server-side.
- **Job B — non-tiler gates** (`heesch_verify.gates`, `.proofgate`).
- **Job C — encoder + proof pipeline** (`heesch_encoder`): regenerates the
  CNF a proof refers to and drives the vendored checkers.

Job A never imports B or C; B imports C lazily inside the proof gate only.

### 2.1 Gates

| Gate | Module | Verdicts | Basis |
|---|---|---|---|
| 1 census + constructive | `gates.IsohedralGate` | `NON_TILER` (census) / `TILER` / `INCONCLUSIVE` | Kaplan 2022's complete non-tiler lists (`known_nontilers.json`, pinned in `third_party/kaplan-heesch/PIN`); boundary-word factorizations (Beauquier–Nivat, Conway, quarter-turn); bounded periodic-tiling search |
| 3 proof-carrying | `proofgate.ProofCarryingGate` | `VERIFIED` or a rejection code | checked UNSAT proof of `F(S, m)` (§13) |

(Gate 2 — a bare SAT-solver verdict — was removed: a solver's say-so is not
independently checkable.)

Gate 1 semantics are load-bearing. Inside the census (polyominoes ≤ 10,
polyhexes ≤ 8, polyiamonds ≤ 12) every hole-free shape is decided exactly:
listed → `NON_TILER` with the published `Hc/Hh`; unlisted → `TILER`. Above
it the gate returns `TILER` only on a *constructive* proof that a tiling
exists and never `NON_TILER` — anisohedral tilers exist, so a failed
criterion proves nothing. Missing criteria only weaken the constructive
filter; under §2.2 they never admit a tiler. Every verdict carries a
machine-readable `gate_detail`.

### 2.2 The acceptance rule (fail closed)

A submission is **accepted and scored** iff

1. the witness verifies (§7 stages 1–5, plus the defect pass if a `#DEFECT`
   block is present), and
2. Gate 1 does not return `TILER`, and
3. non-tilerhood is proven — `census` (Gate 1 `NON_TILER`) or `proof`
   (`#PROOF` block, Gate 3 `VERIFIED`), and
4. every block present verifies (a failing `#PROOF` rejects even a census
   shape, mirroring `#DEFECT`), and
5. the census tripwire holds: `hc_verified <= census_hc` and
   `hh_verified <= census_hh` for census shapes (`CENSUS_CONTRADICTION`
   otherwise — that would mean the verifier or the census is wrong).

Everything else is `REJECTED` with a stable §8 code, nonzero exit, no
`score.json`. No pending state, no hollow entries.

| Gate 1 | `#PROOF` | Gate 3 | Outcome |
|---|---|---|---|
| `TILER` | any | not run | `GATE_IS_TILER` |
| `NON_TILER` | absent | — | accept, `non_tiler_evidence=census` |
| `NON_TILER` | present | `VERIFIED` | accept, `evidence=proof`, `gate_detail=nontiler:census+proof:v2:m=<m>` |
| `INCONCLUSIVE` | absent | — | `GATE_INCONCLUSIVE` |
| `INCONCLUSIVE` | present | `VERIFIED` | accept, `evidence=proof` |
| any non-`TILER` | present | failure | that failure's code |

### 2.3 Tiers, exactness and records

- Census evidence: `exact` iff `hc_verified == census_hc == census_hh ==
  hh_verified` (rests on Kaplan's computation; threat model R1).
- Proof evidence: `F(S, m)` UNSAT proves `Hh <= m − 1` over all patches
  (multilevel spec §2.2). With `hh_verified = m − 1`, `Hh` is exact
  (`hh_exact`); if additionally `hc_verified == hh_verified`, `Hc = Hh = k`
  exactly (`exact`). `hh = hc + 1` with `hh_exact` leaves `Hc` undecided
  between `k` and `k+1` — recorded as `exact = false`, not as a status of
  its own (the enum's `EXACT_UNDECIDED_HOLE_CASE` is reserved, §8).
- `tier = exact_proof` iff `exact` via a checked proof; every other accepted
  entry is `tier = lower_bound`.
- `record_eligible = evidence == proof and hc_verified >= 5`: a checked
  proof gives a finite `Hh <= m − 1`, the witness gives `Hc >= 5`, and
  `Hc <= Hh` — record-breaking whatever the exact value (`Hc ∈ {Hh−1, Hh}`,
  so an `Hc = 5` shape may need `F(S,7)`, not `F(S,6)`).
  `record_exact = record_eligible and exact`. Records additionally require
  the human review in §13.9.

The scalar (§9.2.6) is `hc_verified + fractional defect progress`; tier and
evidence are board metadata, never multipliers.

## 3. No participant code

The harness executes nothing under `submission/`. Inputs: `best.heesch`
(text, ≤ 2 MiB, regular file, no symlinks) and, when named by a `#PROOF`
block, proof/core files in the same directory (regular files, size-capped,
bounded xz decompression). All are hostile data, handled inside the sandbox
(§13.8, `THREAT-MODEL.md`). Everything else in `submission/` is inert.

## 4. File format

heesch-sat's text format verbatim, plus two optional trailing blocks:

```
<G> x1 y1 x2 y2 ... xn yn      # grid O/H/I and the tile's cells
~ hc hh P                      # claim; P = 1 (hh == hc) or 2 (hh == hc + 1)
N                              # placement count of patch 1
level <a,b,c,d,e,f>            # x' = a·x + b·y + c,  y' = d·x + e·y + f
...                            # (patch 2 follows if P = 2)
#DEFECT k+1 u_hc u_hh r        # OPTIONAL partial next corona (§9.2.7)
M
k+1 <a,b,c,d,e,f>
...
#PROOF 1                       # OPTIONAL non-tiler proof (§13.2); must be last
encoder heesch-encoder/v2 2 <m>
cnf <cnf_sha256> <num_vars> <num_clauses>
file <basename> <drat|lrat> <none|xz> <payload_sha256>
core <basename> <none|xz> <payload_sha256> <num_clauses>   # optional, lrat only (§13.3 5b)
```

CRLF and repeated spaces tolerated; markers are exact first tokens;
`#DEFECT` precedes `#PROOF`; each block at most once; trailing garbage is
`PARSE_SYNTAX`; lines ≤ 1 000 000 chars; integers `|v| <= 2^31`; ≤ 20 000
placements per patch; `P = 0` only with `hc = 0`. `~` claims are lower
bounds: a weaker verified value is accepted and recorded with
`claim_discrepancy` unless `--strict`. `--emit-epoch` writes the
Epoch-compatible file with both optional blocks stripped.

## 5. Stdlib-only rule

`heesch_verify`, `heesch_encoder` and `harness` have no third-party runtime
dependency (hard rule). Solvers live only in the `prove`/`test` extras and
`tools/`; the checkers are vendored, sha256-pinned C/CakeML sources compiled
by `setup.sh` into `tools/bin`.

## 6. Calibration against heesch-sat

Grid encodings, orientation tables and the contact relation are transcribed
from Kaplan's `heesch-sat` (`tools/NOTES-kaplan.md`) and re-confirmed by the
calibration corpus (§10) and the census table. Divergences are recorded,
never smoothed over (currently one: the 6-hex `-2 2 -1 1 0 0 1 0 2 0 2 1`,
published `Hc = Hh = 2`, our capped searches find one corona —
`tests/corpus/MANIFEST.json`).

## 7. Pipeline

Stages, in order; each rejection is a `VerifyError` with a §8 code.

1. **Parse** (`parse.parse_submission`) — §4 grammar.
2. **Shape validity** (`shape.check_shape`) — non-empty, ≤ 200 cells,
   edge-connected, hole-free (padded-bbox flood fill — the one hole
   detector), `span_x + span_y <= 29`.
3. **Canonical form** (`canonical.canonical_digest`) — lexicographic minimum
   over the grid's point group (reflections included); `symmetry_order`.
4. **Transform validity** (`transform.check_symmetry`) — the linear part
   must be a frozen orientation AND the translation lattice-legal (iamond:
   `≡ (0,0) mod 3`); `det = ±1` alone is never enough.
5. **Patch legality** (`patch.check_corona`, one threaded `Contact`, §11.1):
   5a disjointness; 5b levels recomputed from adjacency — submitted labels
   are never trusted; 5c surround — every contact-neighbour of the
   accumulated patch covered by the next level; 5d holes — hole-free for
   `hc`, outermost corona may enclose holes for `hh`; 5e report. The corona
   work budget (`patch.MAX_CORONA_WORK`, 8 000 000 cell·levels) bounds
   5c/5d on the participant path (adversarial nested-ring patches stop at
   ~15 s with `RESOURCE_EXCEEDED`).
6. **Non-tiler rule** — Gate 1, defect pass, Gate 3 if present, §2.2
   (harness only).
7. **Record** — `Result` (§9) written to `score.json`; the append-only
   `store.RecordStore` keeps the best per canonical digest (§9.2.5 order).

## 8. Error codes (API)

Stable strings; every rejection is `REJECTED: <CODE>: message`, exit 1, no
`score.json`.

| Family | Codes |
|---|---|
| Parse | `PARSE_SYNTAX`, `PARSE_COUNT_MISMATCH`, `PARSE_UNKNOWN_GRID` |
| Shape | `SHAPE_EMPTY`, `SHAPE_TOO_LARGE`, `SHAPE_SPAN_EXCEEDED`, `SHAPE_DISCONNECTED`, `SHAPE_HAS_HOLE`, `SHAPE_DUPLICATE_CELL` |
| Transform | `XFORM_NOT_SYMMETRY`, `XFORM_REFLECTION_BANNED` |
| Patch | `PATCH_OVERLAP`, `PATCH_LEVEL_MISMATCH`, `PATCH_ORPHAN_TILE`, `PATCH_GAP`, `PATCH_HOLE_IN_CORONA`, `PATCH_NO_CENTRAL_TILE`, `PATCH_MULTIPLE_CENTRAL` |
| Claims | `CLAIM_WEAKER_THAN_STATED` |
| Defect (§9.2) | `DEFECT_XFORM_INVALID`, `DEFECT_TILE_OVERLAP`, `DEFECT_TILE_NOT_TOUCHING`, `DEFECT_TILE_OUT_OF_BAND`, `DEFECT_CLAIM_MISMATCH`, `DEFECT_LEVEL_MISMATCH` |
| Gates (§2.2) | `GATE_IS_TILER`, `GATE_INCONCLUSIVE`, `CENSUS_CONTRADICTION` |
| Proof (§13) | `PROOF_LEVEL_INCONSISTENT`, `CHECKER_UNAVAILABLE`, `PROOF_FILE_INVALID`, `PROOF_FILE_DIGEST_MISMATCH`, `PROOF_CNF_DIGEST_MISMATCH`, `PROOF_HEADER_MISMATCH`, `PROOF_TRUNCATED`, `GATE_PROOF_INVALID` |
| Resources | `RESOURCE_EXCEEDED` |

Reserved, never emitted by the benchmark job: `DUPLICATE` and
`CLAIM_BELOW_THRESHOLD` belong to the leaderboard-store library
(`heesch_verify/store.py`, not wired into the scoring path), and the
enum's non-terminal statuses (`PROMOTED`, `SUPERSEDED`,
`EXACT_UNDECIDED_HOLE_CASE`) are store/library vocabulary — a SAT
result on the proof path is reported as `GATE_PROOF_INVALID` ("a SAT
model is not an UNSAT proof"), not as a status of its own.

## 9. Record fields

### 9.1 Base fields
`hc_verified`, `hh_verified`, `cell_count`, `span_x/y`, `symmetry_order`,
`patch_size`, `grid`, `reflections_used`, `canonical_digest`, `gate_tier`,
`verified_claim` (a sentence stating exactly what was established),
`claim_discrepancy`, `hc_claimed`, `hh_claimed`, `conventions` (§11),
`resource_profile` (§13.5). The harness additionally injects
`gate_detail` (which gate decided, e.g. `nontiler:census`) and — when a
defect block scored — `score_fraction_num` / `score_fraction_den` (the
defect fraction as an exact ratio) into `metrics` when building
`score.json`; they are metrics fields, not `Result` fields.

### 9.2 Defect board
9.2.1 The defect is what a partial corona `k+1` FAILS to cover — uncovered
cells of the required set `R = contact_neighbors(P_k) \ P_k` (plus enclosed
pockets for `defect_hc`); a gradient many submissions can descend on one
shape. 9.2.2 Claims are lower-bound-shaped ("a placement with defect ≤ d
exists", never minimality). 9.2.3 Tiles must be legal symmetries, disjoint,
touching `P_k`, in the band. 9.2.4 Fractions compare exactly
(`fractions.Fraction`), never floats. 9.2.5 Board ordering: `(hc_verified,
−defect fraction, hh_verified, −cell_count, −span sum, −patch_size)`; an Hc
board reads `defect_hc` only. 9.2.6 The scalar
`score = hc_verified + min(1 − defect/required, 0.999999)` is **not** a
Heesch number; `hc_verified` is. 9.2.7 Block grammar in §4. 9.2.8 Recorded
on every submission; `defect_enabled` (on by default) gates whether the
fraction enters the scalar and the ranking, so the emitted flag and the
score always agree.

### 9.3 Non-tiler evidence (§2.2/§2.3)
`non_tiler_evidence` (`census|proof`), `tier`, `census_hc/hh` (census shapes
only), `proof_status`, `proof_m`, `proof_cnf_digest`, `proof_sha256`,
`proof_format` (declared), `proof_format_detected` (sniffed; disagreement is
`GATE_PROOF_INVALID` before any checker runs), `proof_checkers`,
`proof_core_clauses`, `hh_exact`, `exact`, `record_eligible`,
`record_exact`. Timings are never recorded (determinism).

## 10. Calibration corpus

`tests/corpus/`: witnesses for every non-tiler in the complete small
families, each verifying at exactly Kaplan's published `Hc/Hh` in strict
mode, plus holed shapes that must reject; `MANIFEST.json` records population
counts and the §6 divergence. `tests/test_census_gate.py` enumerates every
free polyform at the census sizes and asserts zero gate misses and zero
false `TILER`s.

## 11. Frozen conventions

`CONVENTIONS.md` is normative: contact relation (boundary point),
reflections allowed, hole rules, tile is a disk, caps, grid encodings.
Every convention is written into each record; changing any is a new
revision.

### 11.1 One contact relation
`required_set` / `touches` come from ONE `Contact` object per run, threaded
through the verifier, the defect pass and both encoders
(`tests/test_contact_threading.py` + the AST lint enforce this). There is no
second adjacency implementation.

## 12. Test suites

12.1 calibration (`test_calibration.py`); 12.2 negative (`test_negative.py`:
one mutated property per test); 12.3 metamorphic (`test_metamorphic.py`);
12.4 differential (`test_differential.py` vs `reference_impl.py`); 12.5
defect (`test_defect.py`); 12.6 record store (`test_score_store.py`); 12.7
fuzz (`tests/fuzz`); 12.8 harness e2e (`test_harness.py`,
`test_gate_detail.py`, `test_file_load_hardening.py`,
`test_parser_hygiene.py`, `test_corona_work_budget.py`,
`test_gate_boundary_cap.py`); 12.9 performance (`test_perf.py`). Census
(`test_census_gate.py`), proof path (`test_parse_proof.py`,
`test_proof_gate.py`, `test_core_proof.py`, `test_prove_cli.py`,
`test_profile.py`, `test_record_flag.py`), encoder obligations
(`tests/encoder/*`).

## 13. Proof pipeline

### 13.1 Overview
The only accepted proof object is an UNSAT proof (DRAT or LRAT) of the
multilevel `F(S, m)`, encoder v2 revision 2. The server regenerates
`F(S, m)` from the shape line alone — the participant's CNF is never read —
matches digest and header, then runs the checkers. Encoder v1's per-patch
formula is never accepted (soundness-note E8: sound only at `k = 0`).

### 13.2 Submission channel
The `#PROOF` block (§4) binds a proof file to the shape: schema `1`;
`encoder heesch-encoder/v2 2 m` with `1 <= m <= 8`; the regenerated CNF's
sha256 + header counts; a plain basename
(`^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`, suffix spells format+compression,
never `best.heesch`); the decompressed payload's sha256. The CNF is encoded
from the tile's canonical form by both `tools/prove.py` and the harness —
that is the digest contract. The optional `core` line names a clause list —
the subset of `F(S, m)` the LRAT proof refutes (measured 2–5 % of F), its
ids in the LRAT being positions in that list — so the checkers load only
those clauses; this is what makes record-scale proofs checkable in-band.
`prove.py` produces it by default.

### 13.3 Order of operations (`ProofCarryingGate.check` → `check_proof_v2`)
1. Level rule `m >= hh_verified + 1`, else `PROOF_LEVEL_INCONSISTENT` (a
   witness deeper than the proof allows is a contradiction, never
   "corrected").
2. Checker preflight: all three checkers present as regular, *executable*
   files (the same predicate the spawn applies; spawn-time `OSError` is also
   `CHECKER_UNAVAILABLE`).
3. Bands and scratch: the selected profile's in-harness band (§13.5) and
   the encoder feasibility band (`multilevel.api.FEASIBILITY_BAND`), else
   `RESOURCE_EXCEEDED` before any work; free scratch below the profile's
   floor also refuses here. The in-process encoding is wall-clock guarded
   (`profile.encode_timeout_s`, encoder call only —
   `heesch_encoder/proofcheck/guard.py` — clipped to the budget's remaining
   time); the checkers are bounded by §13.5, not by this guard.
4. Materialise the proof (and core) into scratch: `lstat`/`O_NOFOLLOW`/
   `fstat` regular-file discipline, stored size ≤ the profile's cap,
   streamed xz decompression (`lzma` memlimit 256 MiB, decompressed cap =
   the profile's payload cap, no trailing data), sha256 compared with the
   block. This bounded materialisation deliberately precedes step 5:
   regenerating `F(S, m)` is the expensive step and must not be triggerable
   more cheaply than the capped decompression; proof bytes are never parsed
   or handed to a checker before the digest matches.
5. Regenerate `F(S, m)` (streamed to scratch, written once — the checkers
   read the same file); digest match, header match, argv guard (basename
   may not begin with `-`), size gate, format sniff on bounded windows
   (SAT models / empty / unknown reject; declared format must equal the
   sniffed class).
   5b. **Core subset** (LRAT only): strict grammar (one clause per line,
   `0`-terminated, no comments, no tautologies), each clause canonicalised
   to the encoder's literal order, and every clause required to be — by
   exact string equality against F's own streamed DIMACS lines — a clause
   of F; the checkers then run on a core CNF *we* write from F's own lines.
   Soundness: a refutation of a subset of F refutes F; the only added trust
   is the exact-membership check. Any deviation rejects before a checker
   runs; profile caps bound the work.
6. Checkers (§13.4); verdict maps 1:1 onto §8 codes; `VERIFIED` yields the
   §9.3 fields.

### 13.4 Tiers and checkers
The harness always checks at **record tier**: two independent `VERIFIED`
verdicts, one of which must be the formally-verified `cake_lpr`. DRAT:
`drat-trim` (emitting LRAT) → `cake_lpr` on that LRAT. LRAT: `cake_lpr` →
`lrat-check`. `lrat-check` never substitutes for `cake_lpr` (not formally
verified; `N 0 0` vacuously verifies). Verdicts are line-anchored; any
`NOT VERIFIED` line forces failure; exit codes are ignored. A missing
checker is `CHECKER_UNAVAILABLE`, never a downgrade.

### 13.5 Budgets — resource profiles
Every budget comes from ONE place, `heesch_verify/profile.py`, selected by
the machine (`detect()`: `record` iff MemAvailable ≥ 24 GiB and scratch
free ≥ 60 GiB — met by the Blacksmith record runner, `RUNNER.md` — else
`standard`). The choice is recorded (`resource_profile`) and is never read
from an environment variable or participant input: the machine is the
policy, and the workflow preflight (`tools/runner_preflight.py --require
record`) fails the job on a machine below the record minima rather than
silently scoring under the narrow profile.

| budget | `standard` (8 GB CI runner) | `record` (`RUNNER.md`) |
|---|---|---|
| in-harness band (cells, max m) | (12,6) (20,5) (50,3) (100,2) | (20,7) (50,4) (100,3) (200,2) |
| encode guard (encoder call only) | 600 s | 3600 s |
| checker caps drat-trim / cake_lpr / lrat-check | 600 / 900 / 300 s | 7200 / 7200 / 3600 s (ceilings; the deadline binds) |
| proof-stage deadline (`CheckBudget`) | 1500 s | 9300 s (sized under the platform's 3 h run cancel) |
| proof / core file as submitted | 48 MiB | 240 MiB (×2 + shape ≤ `maxSubmissionBytes` 512 MiB) |
| decompressed payload (scratch disk) | 1 GiB | 16 GiB |
| core list | 4 M clauses / 512 MiB | 32 M clauses / 8 GiB |
| `cake_lpr` heap + stack (85 % of MemAvailable covers both; stack = heap/12) | 12 GB | 96 GB |
| scratch required before encoding | 8 GiB | 96 GiB |
| job timeout (workflow) | 25 min (`ci.yml`; no standard-profile proof workflow exists) | 240 min |

`CheckBudget`: each spawn gets `min(cap, deadline − now)`; a non-positive
remainder is `RESOURCE_EXCEEDED` without spawning. The budget starts when
the proof stage starts, so the deadline spans materialisation + encoding +
checkers. The encode guard is two-layered: `SIGALRM` where available plus a
portable monotonic deadline the encoder checks between universe levels and
every 4096 clauses. Worst case under `record` is the 9000 s deadline
≈ 2.5 h < the 240-min job (the encode guard runs inside the deadline, not
in addition to it); measured record instances finish in 5–20 min.

The record band is measured, not hoped (`ml-feasibility.md`, runner run
32409736078/32409736648): the heaviest in-band instance, the 16-hex
`F(S,7)`, clears every budget on the production runner (encode 697 s,
`cake_lpr` on the 62 MB-xz core in 318 s); the 20-cell shapes are lighter.
`m = 8` was measured **out**: the 16-hex `F(S,8)` core LRAT is 2.2 GB xz
(11× the stored cap) and its formal check takes 3.9 h (3.9× the checker
cap) — that certificate takes the §13.9 maintainer path. Widening a profile
is measured policy (§13.9), not an encoder revision.

### 13.6 Round-trip oracle
`patch.check_corona(..., hole_mode="none")` is the hole-agnostic geometric
oracle of the encoder suites (unbudgeted; never on the participant path).

### 13.7 Checker availability
`setup.sh` compiles `tools/bin/{drat-trim,lrat-check,cake_lpr}` from
sha256-pinned sources and fails on x86-64 Linux if any is missing. The
harness locates them via `HEESCH_CHECKER_DIR` (set by `benchmark.sh` inside
the sandbox) or `<repo>/tools/bin`.

### 13.8 Sandbox
Parser and checkers run under bubblewrap / `sandbox-exec`: read-only repo,
writable scratch only (`TMPDIR`), no network, no capabilities, stdin
`/dev/null`, path arguments only.

### 13.9 Record procedure

A `record_eligible` entry is a machine-checked research claim, **scored
in-harness**: the record profile admits the certificate every realistic
candidate needs — `F(S,6)` and `F(S,7)` (every `Hc = 5` case, and
`Hc = 6` with `Hh = 6`) for shapes to 20 cells. Participants produce the proof
with `tools/prove.py` (external CaDiCaL via `tools/build_solver.sh`; the
core-LRAT payload is tens of MB xz) and submit normally.
`.github/workflows/record-e2e.yml` proves the path end to end — an
`F(S,7)` proof produced by the participant tooling and scored by
`./benchmark.sh` — on a weekly schedule and on manual dispatch, and is
the regression guard for "a legitimate `Hc = 5, Hh = 6` candidate passes
the proof limits".

**Beyond the record band** (any `m = 8` — measured beyond the checking
budgets, `ml-feasibility.md` — or > 20 cells at `m ≥ 5`) the harness
answers `RESOURCE_EXCEEDED` — fail
closed, never a wrong verdict. Maintainers then run the identical code path
with only the band relaxed (`python -m heesch_verify … --check-proof
--profile record --band encoder|none`), file the verdict JSON + digests in
`docs/records/`, and widen the band by measurement (`measure.yml`) so the
next such submission scores in-harness. A scheduling step, not a weaker
check.

Before **announcing** any record the maintainers (i) re-run the proof check
independently, (ii) confirm the encoder's soundness obligations (multilevel
spec M1–M9) have been externally reviewed — until then the claim is stated
as "accepted by the revision-2 verifier and its checked UNSAT proof,
conditional on the stated encoder soundness obligations"
(`soundness-note.md`, `docs/reviews/`) — and (iii) publish shape, witness,
proof and digests. None of this alters the score.

## 14. Resource bounds

Shape ≤ 200 cells, `span_x + span_y <= 29`; ≤ 20 000 placements per patch;
≤ 64 corona levels; corona work budget 8 000 000 cell·levels; shape file
≤ 2 MiB; proof, payload, core and checker budgets per profile (§13.5);
boundary-word caps 410 / 810 edges; benchmark job 240 min on the record
runner. Bounds are not frozen conventions: raising one is not a new
revision, and every accepted result stays valid.

## 15. Open questions

(1) the 6-hex divergence (§6); (2) whether the Hh board should be its own
track; (3) proof feasibility above ~50 cells / m > 2 — the enforced band is
the measured one, widened as measurements allow; (4) replacing census
evidence with maintainer-generated checked proofs for the small shapes
(feasible: `F(S,2)`/`F(S,3)` solve in seconds), so every scored entry is
proof-backed.
