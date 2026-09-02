# Soundness note — what a checked UNSAT proof establishes

The encoder is the entire trust boundary of an exactness or non-tilerhood
claim: a DRAT/LRAT proof certifies that one specific CNF is unsatisfiable,
and nothing in the proof, the checker or the solver says anything about
whether that CNF faithfully encodes the geometry. This note states the two
theorems the repository relies on — one per encoder version — with their
assumptions, and records the review status of each. Obligations are
specified in `heesch-cnf-encoder-spec.md` §7 (E1–E8) and
`heesch-multilevel-encoder-spec.md` §8 (M1–M9); each has a test under
`tests/encoder/`.

**Status.** Encoder v2 is the enforced acceptance path (architecture §2.2/§13):
its obligation suites are green and its theorem is stated below. What
remains open is *external review* of the M1–M9 arguments for revision 2 and a
citable proof of E7; both gate record *announcements* (architecture §13.9),
not scoring. Encoder v1 is not used for acceptance.

## External review of M1–M9 — procedure and status

The repository cannot close this obligation by itself; it can only make the
review cheap, pinned and recordable. Status 2026-08-20: **not yet reviewed
externally.** Until a review is filed, every record claim is worded as
*"accepted by the revision-2 verifier and its checked UNSAT proof,
conditional on the stated encoder soundness obligations (M1/M2/M4/M5/M9)"*
(architecture §13.9; `docs/STATUS.md`).

What a reviewer is asked to confirm, for encoder revision 2 (commit pinned
in the review file):

| Obligation | Claim to confirm | Where the argument lives | Mechanical evidence |
|---|---|---|---|
| M1 | the reachability-BFS universe of level `l` contains every placement that can occur at level `l` in ANY hole-permitted `m`-corona configuration of `S` | multilevel spec §4.2 | `tests/encoder/test_ml_universe_m1.py` (brute force + margin-band saturation) |
| M2 | every real hole-permitted `m`-corona (true levels) is a weak configuration in the sense of spec §2.1 (relaxation only weakens) | multilevel spec §2.1–§2.2 | exercised by M4 on oracle-generated coronas |
| M4 | every weak configuration extends to a satisfying assignment of `F(S, m)` under the canonical auxiliary extension | multilevel spec §5 (families 1, 2, 4, 5, 6) | `tests/encoder/test_ml_roundtrip.py::test_m4_*` |
| M5 | the Sinz at-most-one auxiliaries are functionally determined, so satisfiability is preserved under projection onto the `x` variables | cnf spec §7 E2, multilevel spec §8 | `tests/encoder/test_amo_dimacs.py` |
| M9 | the regenerated CNF is exactly the frozen formula (emission order, literal order, DIMACS profile, digest) | multilevel spec §6, §11 | `tests/encoder/test_ml_determinism.py`, `test_revision_freeze.py` |

The reviewer gets: this note, the two encoder specs, `heesch_encoder/`
(the universe BFS `multilevel/universe.py`, clause families
`multilevel/clauses.py`, AMO `amo.py`), the corpus (`tests/corpus/`) and
the 46/46 exact-case cross-check (`docs/ml-weak-gap.md`). They do NOT need
to trust the tests: the claims are about the mathematics of §2–§5.

A self-contained packet to hand a reviewer is
`docs/reviews/review-packet.md`. Recording the outcome: a file
`docs/reviews/<YYYY-MM-DD>-<reviewer>.md`
stating the commit and encoder revision reviewed, one verdict line per
obligation (confirmed / confirmed-with-conditions / gap found), the argument
text or a pointer to it, and the reviewer's affiliation. A "gap found" on
M1/M2/M4 is a revision-3 event (new manifest, re-verification of every
record-tier proof); M5/M9 gaps are implementation fixes. Once M1/M2/M4/M5/M9
are confirmed, the conditional wording is dropped from §13.9, `STATUS.md`
and the README in the same commit that files the review.

## Theorem v1 (single-level; sound for exactness only at k = 0)

Let `S` be a hole-free tile, `P_k` a verified hole-free patch with coronas
`0..k`, and `F(S, P_k)` the v1 formula (encoder spec §3–§4).

- UNSAT of `F(S, P_k)` ⇒ **this particular** `P_k` admits no hole-allowed
  corona `k+1`.
- For `k = 0`: `P_0 = S` is unique up to the motions the formula already
  quantifies over, so UNSAT of `F(S, P_0)` ⇒ `Hh(S) = 0`, hence
  `Hc = Hh = 0` and `S` is not a tiler.
- For `k >= 1`: **no conclusion about `Hh(S)`.** `Hh >= k+1` requires only
  that SOME hole-free `k`-patch extends, and patches are not interchangeable
  (corona search genuinely backtracks across patch choices; that is why
  heesch-sat encodes all levels in one formula). This is obligation E8, found
  in implementation review; the old inference "UNSAT of `F(S, P_k)` ⇒
  `Hh <= k` ⇒ `Hc = Hh = k`" is withdrawn for `k >= 1` and no longer appears
  anywhere in the pipeline.

Assumptions: E1 (universe completeness), E2 (equisatisfiability up to
projection), E5 (one contact relation), E6 (deterministic regeneration).
Continuity: `F_v2(S, 1) ≡ F_v1(S, P_0)` on the whole corpus (M8), so the
`k = 0` case is also covered by v2.

## Theorem v2 (multilevel; the enforced path)

Let `S` be a hole-free tile, `m >= 1`, and `F(S, m)` the v2 formula
(multilevel spec §5) over the placement universes `U_1..U_m` (§4).

> **UNSAT of `F(S, m)` ⇒ no weak `m`-configuration exists ⇒ no hole-allowed
> `m`-corona patch exists around `S` for any choice of inner patches ⇒
> `Hh(S) <= m - 1` ⇒ `S` is not a plane tiler.**

Combined with a verified witness (`Hc >= hc_verified`, `Hh >= hh_verified`):
`m >= hh_verified + 1` is forced (`PROOF_LEVEL_INCONSISTENT` otherwise);
with `m = hh_verified + 1`, `Hh = hh_verified` exactly; and if
`hc_verified = hh_verified` then **`Hc = Hh = k` exactly**. If
`hh = hc + 1`, `Hc ∈ {k, k+1}` remains undecided (recorded as
`exact = false`).

Assumptions (multilevel spec §8): M1 per-level universe completeness (the
false-record obligation), M2 relaxation soundness (every real hole-allowed
`m`-corona patch is a weak configuration), M4 geometry → model (every weak
configuration satisfies `F` under the canonical auxiliary extension), M5
equisatisfiability up to projection, and M9 determinism (the checked CNF is
the one the server regenerates). M3/M6/M7 are consistency checks that make an
encoder bug visible in the SAT direction; they are not needed for the UNSAT
inference. E5 (one contact relation) holds for v2 by construction (the same
`heesch_verify.patch` functions and the same threaded `Contact`).

The relaxation is one-directional: a weak configuration need not be a real
corona (holes, window slack), so SAT proves nothing about `Hh >= m` and is
never treated as evidence. Calibration (multilevel spec §9.4,
`docs/ml-weak-gap.md`): every corpus shape with known exact values is UNSAT
at `F(S, k+1)` — 46/46, weak gap 0 — and the census closures (the last
octomino, three 6-hex non-tilers) were obtained this way.

## E1 — universe completeness (v1) / M1 (v2)

A legal corona-`(k+1)` copy `T·S` touches `P_k` under the frozen contact
relation and does not overlap it, so some cell of `T·S` lies in
`R = contact_neighbors(P_k) \ P_k`; the enumeration iterates every
point-group element `M` and every pair (tile cell `c`, required cell `h`),
forming `t = h - M(c)`, so that placement is generated and kept by the
membership predicate. ∎ (v1: `test_universe_e1.py`, brute force with margin
saturation.) For v2 the same argument is applied level by level: a level-`l`
copy touches a level-`(l-1)` copy whose cellset is in the previous frontier
by induction (`test_ml_universe_m1.py`).

## E2 / M5 — equisatisfiability up to projection

Auxiliaries are Sinz sequential-AMO variables, functionally determined by
the `x` variables (`amo.aux_assignment` is the canonical extension
`s_i = OR(x_1..x_i)`), so satisfiability is unchanged and the model ↔
geometry correspondence is stated up to projection onto `x`
(`test_amo_dimacs.py::test_sequential_amo_exact_model_count`).

## E3/E4 (v1), M3/M4 (v2) — the two directions

Model → geometry: every SAT model decodes to a placement set the geometry
oracle accepts (`hole_mode="none"`, multilevel spec §9.1) with recomputed
levels equal to the labels. Geometry → model: every oracle-legal corona (v1)
/ every enumerated weak configuration and every real corona (v2) satisfies
`F` under the canonical aux extension, checked by a pure-Python clause
evaluator with no solver in the loop, plus geometric cross-counts.

## E5 — one contact relation

`R` and `touches` in both encoders ARE `heesch_verify.patch.required_set` /
`touches`, called with the same threaded `Contact` object the verifier uses
(architecture §11.1). `tests/test_contact_threading.py` and the AST lint
enforce this structurally.

## E6 / M9 — deterministic regeneration

Byte-identical DIMACS across hosts, architectures, Python versions and
randomized `PYTHONHASHSEED`; canonical orders live only in `ordering.py`; the
emission path passes an AST lint forbidding unordered iteration; committed
goldens (`tests/encoder/golden/`).

## E7 — `Hc <= Hh <= Hc + 1` for non-tilers

`Hc <= Hh` is immediate. `Hh <= Hc + 1`: a hole-allowed patch with coronas
`1..m` has holes only in its outermost corona, so truncating it to `m-1`
coronas is a hole-free witness, `Hc >= m - 1 = Hh - 1`. **Citation status:
open.** The argument assumes the convention that only the outermost corona
may enclose holes (architecture §11; Kaplan 2022 uses these definitions and
observes `Hh ∈ {Hc, Hc+1}`). Before the first record announcement, either a
citable proof is located or this argument is reviewed with the rest of this
note (encoder spec §14 Q2). Nothing in scoring depends on E7: the harness
records `hh_exact`/`exact` from the level rule alone.

## E8 — the per-patch quantifier gap (v1)

Stated under Theorem v1. Resolution: encoder v2 (built 2026-08-07, all
M-suites green, feasibility band measured and frozen in revision 2, and — since
2026-08 — the enforced acceptance path with a submission channel,
`ProofCarryingGate`, checker build in `setup.sh` and `tools/prove.py`).

## Deliberately absent (encoder spec §4.5)

No symmetry breaking, no implied clauses, no preprocessing — each is an
opportunity to change the solution set; the solver's own preprocessing is
covered by its proof.

## Frozen constants

`heesch_encoder/revisions/rev-1.json`, `rev-2.json`. Any change to the
placement universe, variable ordering, clause schema, emission order,
contact relation, AMO threshold, level window or weak bound is a new revision:
historical proofs stay valid against their recorded version, never re-checked
against a new encoder, never silently migrated. Bug fixes are not exempt.

## Census cross-check and the one open divergence

Kaplan's complete non-tiler lists (`heesch_verify/known_nontilers.json`)
carry the published exact `Hc/Hh` for 3 943 shapes; every corpus witness
agrees. One shape is recorded as open: the 6-hex
`-2 2 -1 1 0 0 1 0 2 0 2 1`, published `Hc = Hh = 2`. Our v2 formula
`F(S, 3)` is UNSAT (so `Hh <= 2`, consistent) and `F(S, 2)` is SAT (a weak
2-configuration exists), but neither the exact-cover classifier nor an
enumeration of 200 000 `F(S, 2)` models (all with a hole in corona 2) has
produced a hole-free 2-corona witness within budget. The census table keeps
Kaplan's values; the harness would accept a 2-corona witness for it if one
is submitted, and would reject anything deeper (`CENSUS_CONTRADICTION`).
