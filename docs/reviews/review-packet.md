# External review packet — encoder soundness obligations M1/M2/M4/M5/M9

**Ask:** confirm (or refute) five mathematical claims about a CNF encoder,
so that a machine-checked UNSAT certificate can be announced as a proof
about tiling geometry without conditions. Estimated effort: one focused day
for a reviewer comfortable with SAT encodings; no trust in our test suite is
required — the claims are about the mathematics in §2–§5 of the spec.

**Repository:** `Layr-Labs/heesch-challenge`, pinned to the commit named in
your review file. Everything cited below is in-repo.

## 1. What is at stake

The benchmark accepts a claim "shape `S` has Heesch number ≥ k" only when
`S` is also proven not to tile the plane. The proof object is a DRAT/LRAT
UNSAT certificate for the formula `F(S, m)`, verified by the
formally-verified checker `cake_lpr` plus one independent checker. The
checkers establish, with essentially no residual doubt:

> `F(S, m)` is unsatisfiable.

The *geometric* conclusion needs one more implication, which no checker can
provide:

> a real hole-permitted `m`-corona around `S` exists ⟹ `F(S, m)` has a
> satisfying assignment.

Contrapositive: UNSAT ⟹ no `m`-corona ⟹ `Hh(S) ≤ m − 1` ⟹ `S` is not a
tiler. This implication is the encoder's soundness, decomposed into the
obligations below. It is the single trust boundary of the whole system
(threat model TB5): everything else — parser, gates, checkers, sandbox — has
been through two external security audits (2026-08; archived outside the repo).

Note the direction: only the *corona ⟹ SAT* direction is safety-critical. A
formula that is accidentally too *hard* to satisfy would create false
records; one that is too *easy* only wastes solver time (SAT outcomes are
never treated as evidence of anything).

## 2. The objects (multilevel spec §2)

A **weak m-configuration** is a set of placements (grid-symmetric copies of
`S`), each labelled with a level `1..m`, satisfying: W1 — every
contact-neighbour cell of `S` is covered by a level-1 copy; W2 — every
level-`l` copy (`l ≥ 2`) touches a level-`(l−1)` copy; W3 — no level-`l`
copy touches `S` or any copy at level ≤ `l−2`; W4 — for every copy at level
`l ≤ m−1`, every contact-neighbour cell of it outside `S` is covered by a
copy at level `l−1`, `l` or `l+1`; no overlaps.

`F(S, m)` has one variable per placement per level (universes `U_1..U_m`)
plus Sinz at-most-one auxiliaries, and six clause families implementing
W1–W4 plus disjointness (spec §5). The claim to be reviewed is that every
*real* corona patch is a weak configuration (M2) and that every weak
configuration satisfies `F` (M1 + M4 + M5), with the checked bytes being the
intended formula (M9).

## 3. The five obligations

For each: the claim, the argument to check, where it lives, and the
mechanical (non-authoritative) evidence.

### M1 — universe completeness

**Claim.** For every `l`, `U_l` contains every placement that occurs at
level `l` in *any* weak `m`-configuration.

**Argument to check** (spec §4; `soundness-note.md` "E1/M1"). Level 1: a
level-1 copy covers some contact-neighbour cell `h` of `S`; the enumeration
iterates every point-group element `M` and every pair (tile cell `c`,
required cell `h`), forming the translation `t = h − M(c)`, so the placement
is generated; a membership predicate then keeps exactly the non-overlapping,
touching ones. Levels `l ≥ 2`, by induction: a level-`l` copy touches a
level-`(l−1)` copy (W2), whose cellset is in the previous BFS frontier by
hypothesis; candidates are generated from those cellsets by the same
all-symmetries expansion, filtered by W3.

**Code**: `heesch_encoder/multilevel/universe.py::multilevel_universe`;
level-1 case `heesch_encoder/placements.py`. **Evidence**:
`tests/encoder/test_ml_universe_m1.py` (brute-force enumeration with
margin-band saturation agrees with the BFS on the corpus),
`tests/encoder/test_universe_e1.py` (level 1).

### M2 — every real corona is a weak configuration

**Claim.** A genuine hole-permitted corona patch of depth `m`, with levels
labelled by true corona index, satisfies W1–W4.

**Argument to check** (spec §2.1, the paragraph after the definition): W1 is
the corona-1 surround; W2/W3 restate the corona-level definition (each ring
touches the previous, is separated from `S` and from rings two below); W4 is
the surround condition of every non-outermost ring, restated per tile — a
tile's halo cell is covered by its own ring or an adjacent ring, which the
`{l−1, l, l+1}` window admits. The relaxation is one-directional by design
(weak configurations may have holes or use window slack); the converse is
not claimed and not needed. The specific point deserving scrutiny: is the
window ever too *narrow* — can a real corona have a halo cell of a level-`l`
tile covered only by a level-`l±2` tile? (W3 separation is the intended
counter-argument: such a tile would touch the level-`l` tile, which W3
forbids in a real corona's geometry as well.)

**Code**: the definition is spec-level; the corona semantics it must match
are `heesch_verify/patch.py::check_corona` (the independently-audited
witness verifier). **Evidence**: M4's suite exercises every
oracle-generated real corona through the encoding.

### M4 — every weak configuration satisfies F

**Claim.** For every weak `m`-configuration, the assignment "x true iff the
placement is chosen at that level", extended canonically on the auxiliaries,
satisfies every clause of `F(S, m)`.

**Argument to check** (spec §5, family by family): family 1 = W1; family 2 =
disjointness (two overlapping copies would share a cell); family 4 = W2;
family 5 = W3; family 6 = W4 with the same window; family 3 is absent
because same-cellset duplicates are already excluded by family 2 (this
absence is itself a claim to check). Sinz auxiliaries: M5.

**Code**: `heesch_encoder/multilevel/clauses.py` (`_ml_clauses`).
**Evidence**: `tests/encoder/test_ml_roundtrip.py::test_m4_*` — every
enumerated weak configuration and every oracle-generated real corona of
every corpus shape evaluates to true under a pure-Python evaluator;
`docs/ml-weak-gap.md` — all 46 corpus shapes with known exact Heesch values
reproduce them via `F(S, k+1)` UNSAT.

### M5 — auxiliaries preserve satisfiability

**Claim.** The Sinz sequential at-most-one encoding is satisfiability-
preserving up to projection onto the `x` variables: the auxiliaries are
functionally determined (`s_i = x_1 ∨ … ∨ x_i`), so no weak configuration
is lost by the auxiliary clauses.

**Code**: `heesch_encoder/amo.py` (`aux_assignment` is the canonical
extension). **Evidence**:
`tests/encoder/test_amo_dimacs.py::test_sequential_amo_exact_model_count`
(exact model counts with/without auxiliaries agree).

### M9 — the checked CNF is the intended formula

**Claim.** Regeneration is deterministic: the DIMACS bytes (hence the sha256
the gate matches, hence what the checkers consume) are a pure function of
(shape, grid, contact, m) under the frozen revision-2 constants — across
processes, hash seeds and platforms — and the streamed writer is
byte-identical to the in-memory one.

**Code**: `heesch_encoder/multilevel/api.py` (`encode_multilevel`,
`encode_multilevel_stream`), ordering in `heesch_encoder/ordering.py`,
frozen constants `heesch_encoder/manifest.py::live_constants_v2` pinned by
`heesch_encoder/revisions/rev-2.json` (+ code-checked addendum).
**Evidence**: `tests/encoder/test_ml_determinism.py` (subprocess goldens,
`ml_digests.json`), `test_revision_freeze.py`, an AST lint banning
unordered iteration in emission modules
(`tests/encoder/test_no_unordered_iteration.py`).

## 4. What a finding means

- A gap in **M1, M2 or M4** (a real corona not representable / not
  satisfying) is a false-record vector: revision-3 event — new frozen
  manifest, re-verification of every proof-backed result.
- A gap in **M5 or M9** is an implementation defect: fix + re-run, no
  revision semantics change.
- Confirmation of all five removes the conditional wording from record
  claims (architecture §13.9).

## 5. Filing the review

One file: `docs/reviews/<YYYY-MM-DD>-<your-handle>.md`, containing: the
commit hash reviewed; per obligation, one of **confirmed /
confirmed-with-conditions / gap found** with the reasoning (or a pointer to
your write-up); your name/affiliation as you want it published. Any format
is fine as long as those elements are present; open a PR or send the file to
the maintainers.

## 6. Reading list (in order)

1. `docs/soundness-note.md` — the theorems, this decomposition, review status.
2. `docs/heesch-multilevel-encoder-spec.md` — §2 (objects + theorem),
   §4 (universes), §5 (clauses), §8 (obligations table).
3. `heesch_encoder/multilevel/{universe,clauses}.py`, `heesch_encoder/amo.py`
   — the ~433 lines the claims are about.
4. Optional context: `docs/heesch-cnf-encoder-spec.md` (v1, level-1 case),
   `docs/heesch-verifier-architecture.md` (how the proof gate uses all this),
   Kaplan 2022 (arXiv:2105.09438) for the corona definitions.
