# heesch-encoder/v2 — multilevel encoder specification (revision 2)

One formula `F(S, m)` per (tile, level count), quantifying over **all**
patches at once. Its UNSAT is the only proof object the harness accepts for
non-tilerhood and exactness (architecture §2.2, §13). Section numbers are
cited from `heesch_encoder/multilevel/*`, `tools/*` and `tests/encoder/*`
(`multilevel spec §N`, `v2 spec §N`); keep them stable. Encoder v1
(`heesch-cnf-encoder-spec.md`) is the single-level anchor.

## 1. Why a second encoder

Encoder v1's `F(S, P_k)` is parametrized by ONE submitted patch. UNSAT there
proves "this `P_k` admits no corona `k+1`", but `Hh >= k+1` needs only that
SOME hole-free `k`-patch extends, and patches are not interchangeable
(corona search backtracks across patch choices; heesch-sat encodes all
levels in one formula for this reason). So a checked v1 proof does not
establish `Hh <= k` for `k >= 1` — the E8 gap. v2 removes the patch from the
formula: variables exist for placements at every level `1..m`, with
level-adjacency constraints, so UNSAT genuinely quantifies over all patches.

## 2. The object and the theorem

### 2.1 Weak configurations
A *weak m-configuration* is a set of placements, each labelled with a level
`l ∈ 1..m`, such that

- W1 every contact-neighbour cell of `S` (`R_0`) is covered by a level-1 copy;
- W2 every level-`l` copy (`l >= 2`) touches some level-`(l-1)` copy;
- W3 no level-`l` copy touches `S` for `l >= 2`, nor any copy at level `<= l-2`;
- W4 for every copy `q` at level `l <= m-1`, every contact-neighbour cell of
  `q` outside `S` is covered by some copy at level `l-1`, `l` or `l+1`
  (the `{l-1, l, l+1}` window);
- no two copies overlap (and no copy overlaps `S`).

Every genuine hole-allowed corona patch of depth `m` (levels labelled by
their true corona index) is a weak `m`-configuration: W1 is the corona-1
surround, W2/W3 are the level definition, W4 is the surround condition for
levels below the outermost, restated per tile with the window absorbing the
fact that a tile's halo cells are covered by its own level or its two
neighbours. The converse fails — a weak configuration may enclose holes or
use the window slack — hence "weak" and hence the *weak gap* (§9.4). The
relaxation is one-directional by design: it only ever makes SAT easier.

### 2.2 The theorem
For a hole-free tile `S` and `m >= 1`:

> `F(S, m)` UNSAT ⇒ no weak `m`-configuration exists ⇒ no hole-allowed
> `m`-corona patch exists around `S`, for ANY choice of inner patches ⇒
> `Hh(S) <= m - 1` ⇒ `S` is not a plane tiler (a tiler has coronas at every
> depth).

Combined with a verified witness (architecture §7): `Hh >= hh_verified`, so
`m >= hh_verified + 1` is forced (`PROOF_LEVEL_INCONSISTENT` otherwise);
with `m = hh_verified + 1`, `Hh = hh_verified` exactly, and if
`hc_verified = hh_verified` then `Hc = Hh = k` exactly. Assumptions: the
obligations M1–M9 (§8) hold for the frozen revision-2 constants (§11); those
are what external review (architecture §13.9) attests.

SAT says nothing beyond "a weak configuration exists" — never
`Hh >= m`, never a failure; the pipeline reports it as
`GATE_PROOF_INVALID` ("a SAT model is not an UNSAT proof").

## 3. Inputs

`encode_multilevel(tile_cells, grid, contact, m)`: `tile_cells` in the
verifier's canonical form (`canonical_form(cells, grid, True)`; the digest
depends on the cells as given), `grid ∈ GRIDS`, the ONE threaded `Contact`,
`m >= 1`. Output `MLEncodingResult(dimacs, digest, num_vars, num_clauses, m,
universe_sizes, family_counts, formula)`.

## 4. Universes

### 4.1 Level 1
`U_1` is v1's universe for `P_0 = S` (§3 of the v1 spec, E1).

### 4.2 Levels `l >= 2` by reachability BFS
`U_l` = all lattice-legal placements that touch some cellset in `U_{l-1}`,
do not overlap `S`, and do not touch `S` (W3). Candidates are generated from
the previous level's *cellsets* (deduplicated cell unions) and re-expanded
into all symmetry-indexed representatives producing that cellset
(`placements_of_cellset`, anchored by the cell-key-minimal cell). Obligation
M1: `U_l` contains every placement occurring at level `l` in ANY weak
configuration — induction on `l` over W2/W3. Level-synchronous loop, no
recursion, sorted containers only.

## 5. Clauses (B = 0)

Variables: `x_{l,p}` for `p ∈ U_l`, numbered level-major in `placement_key`
order (`ordering.xvar_key`), then Sinz auxiliaries. Families:

- **1 — base coverage (W1)**: for each `h ∈ R_0`, `∨ x_{1,p}` over level-1
  placements covering `h`; an unreachable cell emits a real empty clause.
- **2 — per-cell at-most-one across levels**: for every cell covered by ≥ 2
  variables (any levels), pairwise if ≤ `AMO_THRESHOLD = 20`, else Sinz.
- **3 — absent by design**: same-cellset copies share every cell, so
  family 2 already forbids two of them (`test_ml_roundtrip.py` checks the
  implication is real and nothing is emitted).
- **4 — adjacency (W2)**: for `l >= 2`, `¬x_{l,p} ∨ ∨ x_{l-1,q}` over `q`
  touching `p`.
- **5 — separation (W3)**: for `l >= 3` and every `j <= l-2`,
  `¬x_{l,p} ∨ ¬x_{j,q}` for `q` touching `p`.
- **6 — per-tile surround (W4)**: for `l <= m-1`, every halo cell `h` of
  `p` outside `S`: `¬x_{l,p} ∨ ∨ x_{l',q}` over `q` covering `h` with
  `l' ∈ {l-1, l, l+1} ∩ [1, m]`.
- **7 / coverage auxiliaries — do not exist at B = 0.** `B` is the weak
  bound: extra slack that would let W4 windows widen; the calibration (§9.4)
  found `B = 0` sufficient on every measured shape, and it is frozen in
  revision-2.

The touch graph is computed once over the union of level cellsets
(`universe.touching_cellset_pairs`) and shared by clause construction and the
feasibility counter, so counts and clauses cannot drift.

## 6. Emission order

Deliberately different from v1's (do not harmonize either way): family 1
(by cell), family 2 (by cell, then pair / Sinz order), family 4 (by
`(l, placement)`), family 5 (by `(l, p, j, q)`), family 6 (by `(l, q, cell)`);
literals within a clause `(abs, negative-first)`. DIMACS profile and digest as
v1 §6. Determinism enforced by the same AST lint (`EMISSION_MODULES` includes
the three multilevel modules) and subprocess goldens (`ml_digests.json`).

## 7. Model self-check

`multilevel.model`: `decode_model` (positive `x` literals → `[(level,
Placement)]`), `config_assignment` (a weak configuration → full assignment
including the canonical Sinz extension; a placement outside its level's
universe raises — an M1 violation caught loudly), `violated_clause`,
`config_to_corona_placements` (→ verifier placements with the central copy
prepended). Not on the emission path.

## 8. Obligations M1–M9

| | Obligation | Status / test |
|---|---|---|
| M1 | per-level universe completeness (§4.2) | `test_ml_universe_m1.py` (brute force with inductive licensing + margin-band saturation) |
| M2 | relaxation soundness — every hole-allowed `m`-corona patch (true levels) is a weak configuration (§2.1) | argued in §2.1; exercised by M4 on every oracle-generated corona |
| M3 | model → geometry: every SAT model decodes to placements whose recomputed levels agree with the labels and which the hole-agnostic Stage-5 oracle accepts | `test_ml_roundtrip.py::test_m3_*` |
| M4 | geometry → model: every enumerated weak configuration (and every real corona) satisfies `F` under the canonical aux extension, pure-Python evaluator | `test_ml_roundtrip.py::test_m4_*` (+ geometric cross-count) |
| M5 | equisatisfiability up to projection onto `x` (Sinz auxiliaries functionally determined) | v1 E2 argument and `test_amo_dimacs.py`; the same `amo` module is used |
| M6 | label integrity: no empty level below `m` in a decoded model; per-level nonemptiness and label equality | `test_ml_roundtrip.py` (M6 checks) |
| M7 | window ⇔ family-5 structure: the `{l-1,l,l+1}` window is exactly the complement of separation, so a tile's halo cannot be covered by a level it is forbidden to touch | `test_ml_roundtrip.py::test_m7_*` |
| M8 | v1 continuity: `F_v2(S, 1) ≡ F_v1(S, P_0)` on the whole corpus | `test_ml_continuity.py` (§9.6) |
| M9 | determinism: universe serialization and full-CNF digests stable across processes and hash seeds | `test_ml_determinism.py` |

M1 and M4 are the false-record obligations: an incomplete universe or an
over-restrictive clause would make a real corona unrepresentable and UNSAT
meaningless. External review of this table for revision 2 is the precondition
for record *announcements* (architecture §13.9); the gate itself is enforced
because the tests are green and the theorem's assumptions are exactly these
rows.

## 9. Test suites

9.1 hole-agnostic oracle (`patch.check_corona(hole_mode="none")`,
`tests/test_hole_mode.py`); 9.2 M1; 9.3 M3/M4/M6/M7 round trips; 9.4 weak-gap
calibration — `tools/close_census.py`, `docs/ml-weak-gap.md`: every corpus
shape with known exact values is UNSAT at `F(S, k+1)`, 46/46, weak gap 0;
9.5 negative proof handling shared with v1; 9.6 continuity (M8);
9.7 determinism (M9); 9.8 record-tier proof artifact positive control
(`test_ml_proof_pipeline.py`) and, end to end through the harness,
`tests/test_proof_gate.py` (an 11-omino with `F(S,3)` UNSAT scores as a
proof-backed non-tiler; a census octomino with `F(S,2)` UNSAT scores exact).

## 10. Feasibility

### 10.1 Sizes
Universe sizes grow roughly geometrically in `m` (`docs/ml-feasibility.md`:
corpus shapes ~11–21 k vars at `m = 2`, ~39–77 k at `m = 3`; a 50-cell
rectangle 1.45 M vars at `m = 3`, 6.7 M at `m = 5`; a 100-cell square DNF at
`m = 5`; a 200-cell rectangle DNF at `m = 3`).

### 10.2 The band (enforced)
`heesch_encoder.multilevel.api.FEASIBILITY_BAND` (measured policy — it
changes no CNF byte, so widening it is not a new revision; the revision-2
manifest + code-checked addendum carry the history):
`(<= 20 cells, m <= 8)`, `(<= 50, m <= 4)`, `(<= 100, m <= 3)`,
`(<= 200, m <= 2)` (measurements in docs/ml-feasibility.md).
`check_proof_v2` answers `RESOURCE_EXCEEDED` **before encoding** outside it
(`in_feasibility_band`), and encodes by streaming to disk
(`encode_multilevel_stream`, byte-identical to `encode_multilevel`) so peak
memory is the universe, not the formula. The harness applies the stricter
in-harness band of its resource profile (architecture §13.5: `record`
`(20,7) (50,4) (100,3) (200,2)`, `standard` `(12,6) (20,5) (50,3)
(100,2)`) because it must also encode inside the benchmark job.

Measured (docs/ml-feasibility.md): every known `Hc = 4` shape (11–20 cells)
has its exactness proof `F(S, 5)` inside both bands (11-hex: 60 s encode,
UNSAT in ~30 s; 20-iamond: 173 s encode). **An `Hc = 5` certificate is
`F(S, 6)` when `Hh = 5`, and `F(S, 7)` when `Hh = 6`** (`Hc ∈ {Hh − 1, Hh}`,
so a genuine `Hc = 5` shape may have a real hole-permitted 6-corona; then
`F(S, 6)` is SAT and the finite certificate must be `F(S, 7)` — see
§10.2a below and audit 2026-08-19 High 1). For the 11-hex `F(S, 6)` encodes in 112 s at 2.5 GB RSS (17.2 M
clauses, 2.1 GB DIMACS), is UNSAT in 157 s, drat-trim verifies and emits the
LRAT in 61 s (513 MB, 25 MB xz), lrat-check verifies in 16 s. The
formally-verified `cake_lpr` needs more than ~6 GB of heap to load that CNF:
on the standard 8 GB GitHub runner it reports `CakeML heap space exhausted`
after ~5 min and the harness answers `RESOURCE_EXCEEDED` (naming the checker,
never `NOT_VERIFIED`). With the core list `prove.py` emits by default the
checkers load ~2–5 % of F, which removes the memory pressure — that, plus
the record runner, is why every `m <= 7` instance at `<= 20` cells is
checked in-band today. At `m = 8` even the core proof explodes (16-hex:
2.2 GB xz, 3.9 h in `cake_lpr` — measured on the runner, §10.2a and
docs/ml-feasibility.md), so those take the §13.9 maintainer re-check.

### 10.2a The `Hc = 5, Hh = 6` case and the resource profiles

The record flag does not require exactness (architecture §2.3): a verified
`hc >= 5` plus ANY checked `F(S, m)` UNSAT is record-breaking. But the level
rule `m >= hh_verified + 1` means a candidate whose witness shows a real
hole-permitted 6-corona can only be certified by `F(S, 7)` — 36–120 M
clauses for 11–20-cell shapes (`docs/ml-feasibility.md`). The benchmark
therefore runs on a dedicated runner under the `record` resource profile
(`heesch_verify/profile.py`, architecture §13.5; `docs/RUNNER.md`), whose
in-harness band `(20, 7) (50, 4) (100, 3) (200, 2)` admits that
certificate for every realistic candidate size — `F(S, 8)` (the `Hc = 6,
Hh = 7` case) was measured beyond the checking budgets and takes the §13.9
maintainer path —
**inside the job**. The profile is selected from the machine (MemAvailable,
scratch), never from an environment variable or participant input; the
workflow preflight fails a smaller machine loudly. The band is still a
parameter for the maintainer CLI (`python -m heesch_verify --check-proof
--profile {auto,standard,record} --band {profile,harness,record,encoder,none}`,
`tools/prove.py --profile … --band …`) for re-checks beyond the record band
(architecture §13.9). Widening a band after a measurement changes no CNF
byte and is not a revision bump.

## 11. Frozen constants (revision 2)

`heesch_encoder/revisions/rev-2.json` (`manifest.live_constants_v2()`):
encoder version, families active `1,2,4,5,6`, `weak_bound_B = 0`, level
window `{l-1,l,l+1}`, universe construction `reachability-bfs/v1`, variable
order, clause emission order, the feasibility band, and the constants digest;
sha256-pinned by `test_revision_freeze.py`. Any change is revision 3. The
`checkers.record_tier_policy` string in the manifest is documentary and
superseded by the enforced code policy (v1 spec §11); the corrected
provenance — the enforced checker policy and the current measured band —
is `heesch_encoder/revisions/rev-2-addendum.json`, checked against the
code by `test_revision_freeze.py::test_rev2_addendum_matches_code` (the
frozen manifest stays byte-identical).
