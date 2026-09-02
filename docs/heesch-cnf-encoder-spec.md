# heesch-encoder/v1 — CNF encoder specification (revision 1)

The single-level encoder: for a tile `S` and a verified hole-free patch
`P_k` (coronas `0..k`), the formula `F(S, P_k)` is satisfiable iff a
hole-allowed corona `k+1` exists **around that particular patch**. Section
numbers are cited from `heesch_encoder/*` and `tests/encoder/*`
(`encoder spec §N`, or bare `§N` inside the encoder package); keep them
stable. The enforced acceptance path uses encoder v2
(`heesch-multilevel-encoder-spec.md`); v1 remains the reference single-level
encoder, the `m = 1` continuity anchor for v2 (multilevel spec §9.6), and a
sound exactness tool at `k = 0` only (§13, `soundness-note.md` E8).

## 1. Role and trust boundary

A DRAT/LRAT proof certifies that a specific CNF is unsatisfiable. Nothing in
the proof, the checker or the solver says anything about whether that CNF
faithfully encodes the geometry — the encoder is the entire trust boundary of
any exactness or non-tilerhood claim. Hence: byte-identical regeneration
(§6), obligations with tests (§7, §9), and frozen constants (§11).

## 2. Inputs

`encode(tile_cells, patch_cells, grid, contact)` — `tile_cells` are the
tile's cells as the verifier gives them (canonical form is the caller's
contract; v2 fixes it to `canonical_form(cells, grid, True)`), `patch_cells`
the union of the verified patch `P_k`, `grid ∈ GRIDS`, `contact` the ONE
threaded `Contact` object (architecture §11.1). There is deliberately no
level parameter: level `k+1` is implicit in `patch = P_k` (a level argument
invites an off-by-one).

## 3. Placement universe

### 3.1 Membership
`U = { p = (M, t) : M ∈ point group, t lattice-legal, cells(p) ∩ P_k = ∅,
touches(cells(p), P_k, contact) }` — `heesch_encoder.placements.in_universe`,
using `heesch_verify.patch.touches` verbatim (E5).

### 3.2 Enumeration
For every point-group element `M` and every pair (tile cell `c`, required
cell `h ∈ R = contact_neighbors(P_k) \ P_k`) form `t = h - M(c)`, keep it if
§3.1 holds, deduplicate. Completeness (E1): a legal placement touches `P_k`
without overlapping it, so one of its cells lies in `R`; that cell and its
preimage generate exactly `t`. No halo-radius arithmetic exists, so there is
no off-by-one to get wrong.

### 3.3 Canonical order
`Placement(symmetry_index, ty, tx)` — the tuple IS the sort key
(`ordering.placement_key`); variables `x_p` are numbered `1..|U|` in that
order. Cells sort `(y, x)` (`ordering.cell_key`).

## 4. Clauses

4.1 Variables: `x_p` for `p ∈ U`, then Sinz auxiliaries.
4.2 Non-overlap: for every cell covered by ≥ 2 placements, at-most-one over
its covering variables (cells in canonical order, variable lists ascending).
4.3 Coverage: for every `h ∈ R` (canonical order) the clause `∨ x_p` over
placements covering `h`. A cell no placement reaches emits a **real empty
clause** — the formula is then trivially UNSAT, the artifact stays uniform,
and the checker still runs (`_has_empty_clause` recognises this case).
4.4 AMO encoding: pairwise `(¬x_i ∨ ¬x_j)` when the group has ≤
`AMO_THRESHOLD = 20` variables, else Sinz sequential with auxiliaries
`s_1..s_{n-1}` numbered after all `x`; `amo.aux_assignment` is the canonical
functional extension `s_i = OR(x_1..x_i)` used by §9.2. The threshold is a
frozen constant.
4.5 Nothing else: no symmetry breaking, no implied clauses, no preprocessing —
each would be an opportunity to change the solution set; the solver's own
preprocessing is covered by its proof.

## 5. Checker failure semantics

Every checker outcome maps to exactly one `ProofStatus`: `VERIFIED`,
`PROOF_CNF_DIGEST_MISMATCH`, `PROOF_HEADER_MISMATCH`, `PROOF_TRUNCATED`,
`GATE_PROOF_INVALID`, `RESOURCE_EXCEEDED`, `CHECKER_UNAVAILABLE`. A SAT
outcome of the formula is an honest "not yet" — the pipeline reports
`GATE_PROOF_INVALID` ("a SAT model is not an UNSAT proof") and
`tools/prove.py` exits 2; it is never presented as evidence either way.
Timeout/OOM is `RESOURCE_EXCEEDED`, never
`NOT_VERIFIED`. A missing checker is `CHECKER_UNAVAILABLE`, never a
downgrade to a weaker checker (audit F1/F2), except the checker-independent
empty-clause case (F5), which is unreachable from the harness because the
preflight (architecture §13.3) runs first.

## 6. DIMACS profile and emission order

`p cnf <vars> <clauses>\n`, one clause per line, literals space-separated,
`0`-terminated, no comments, ASCII, `\n` line ends
(`dimacs_profile = p-cnf/newline/space/zero-terminated/no-comments/v1`).
Emission: all AMO clauses (by cell, then pair / Sinz order), then coverage
clauses (by cell); literals within a clause sorted `(abs, negative-first)`.
Digest = sha256 of the bytes. Determinism is a correctness requirement: the
server regenerates and hash-matches before touching a proof; the emission
path passes an AST lint forbidding unordered iteration
(`tests/encoder/test_no_unordered_iteration.py`) and fresh-subprocess digests
under randomized `PYTHONHASHSEED` match committed goldens.

## 7. Soundness obligations (with their tests)

| | Obligation | Test |
|---|---|---|
| E1 | universe completeness (§3.2) — the false-record obligation | `test_universe_e1.py` (brute force over an oversized region with margin-band saturation) |
| E2 | equisatisfiability up to projection onto `x` (auxiliaries functionally determined) | `test_amo_dimacs.py::test_sequential_amo_exact_model_count` |
| E3 | every SAT model decodes to a corona the geometry verifier accepts (over-permissive detector) | `test_roundtrip.py::test_e3_*` |
| E4 | every oracle-legal corona satisfies `F` under the canonical aux extension, checked by a pure-Python clause evaluator (over-restrictive detector — the false-record direction) | `test_roundtrip.py::test_e4_*` |
| E5 | one contact relation: `R`/`touches` are `heesch_verify.patch`'s, same threaded object | `tests/test_contact_threading.py`, AST lint |
| E6 | deterministic regeneration (§6) | `test_determinism.py`, `test_no_unordered_iteration.py`, `test_revision_freeze.py` |
| E7 | `Hc <= Hh <= Hc + 1` for non-tilers | argument in `soundness-note.md`; citation status open (§14 Q2) |
| E8 | **the per-patch quantifier gap** — UNSAT of `F(S, P_k)` proves only that THIS `P_k` has no corona `k+1`; sound for `Hh <= k` only at `k = 0` | resolved by encoder v2 |

## 8. Proof-check order of operations

1. regenerate the CNF server-side; 2. digest match — before touching any
proof bytes; 3. header var/clause counts; 3b. argv guard (basename may not
start with `-`); 4. size gate; 5. format sniff on bounded windows (reject SAT
models, empty and unknown; require a terminated last line for text formats);
6. checkers (record tier: two independent VERIFIED verdicts, one of them
`cake_lpr`). Implemented once, schema-blind, in
`proofcheck.pipeline.check_proof_encoded`; v1 (`check_proof`) and v2
(`check_proof_v2`) differ only in step 1.

## 9. Test suites (encoder round trip)

9.1 E3 model → geometry; 9.2 E4 geometry → model with the aux extension;
9.3 E1 universe completeness; 9.4 (v2) weak-gap calibration; 9.5 negative
proof handling (`test_proof_pipeline.py`: digest/header mismatch, SAT model,
empty, truncated, oversized, tier arity, format table, real drat-trim positive
control); 9.6 E6 determinism goldens; 9.7 (v2) determinism; 9.8 (v2)
record-tier proof artifact positive control. The proof-carrying gate is
enabled (architecture §2.2) because these suites are green; the revision's
external review status is tracked in `soundness-note.md` and gates *record
announcements* (architecture §13.9), not scoring.

## 10. Feasibility

Single-level formulas are small (tens of thousands of variables for corpus
shapes). v2's band is the operative limit (multilevel spec §10.2).

## 11. Revision freeze

`heesch_encoder/revisions/rev-1.json` records the frozen constants
(`manifest.live_constants()`: AMO threshold, placement/cell/literal order,
clause emission, DIMACS profile, digest algorithm, contact relation, point
groups) and their digest; `tests/encoder/test_revision_freeze.py` asserts the
live code matches the manifest and pins the manifest's own sha256. Any change
to universe, ordering, clause schema, emission or contact is a new encoder
version and a new revision: historical proofs stay valid against their recorded
version, are never re-checked against a new encoder, never silently
migrated; bug fixes are not exempt. The manifest's `checkers.record_tier_policy`
string (`cake_lpr-or-lrat-check`) predates audit F2 and is documentary only:
the enforced policy is the code's (§8 step 6, architecture §13.4) — `cake_lpr`
required, `lrat-check` never a substitute. The manifest is left byte-identical
because it is immutable by construction; this note and
`heesch_encoder/revisions/rev-2-addendum.json` (code-checked) are the correction.

Naming note (2026-08-18): the frozen-constants versions were previously
called "epochs" (`heesch_encoder/epoch/epoch-N.json`, manifest key `epoch`).
That word collides with Epoch AI, whose FrontierMath Heesch challenge this
benchmark cross-submits to (`--emit-epoch`), so the concept is now
"revision" (`heesch_encoder/revisions/rev-N.json`, key `revision`). The
rename changed only the file names and that one key; the frozen constants,
their digests and every historical proof are unchanged. The manifest sha256
pins were re-recorded for the renamed key.

## 12. Determinism and hygiene

No hash-order iteration on the emission path (pragma-audited), no timings
in outputs, no environment influence on the *encoding* (`python -I` in the
benchmark; the one checker-side knob, `HEESCH_CAKE_HEAP_MB`, sizes the
`cake_lpr` heap and cannot change a verdict).

## 13. Sound uses of v1

- `k = 0`: `P_0` is the tile itself (unique up to the motions the formula
  quantifies over), so UNSAT of `F(S, P_0)` proves `Hh = 0` exactly.
- Any `k`: as a *search* aid ("this patch cannot be extended"), never as an
  acceptance argument.

## 14. Open questions

Q1 (closed) — how to quantify over all patches: encoder v2. Q2 (open) — a
citable proof of E7 (`Hh <= Hc + 1` under the outermost-corona-only hole
convention; Kaplan 2022 states the observation) — required before the first
record announcement (architecture §13.9), not for scoring.
