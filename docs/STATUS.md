# Verifier status — audit tracker and open items

A living document: where every external-audit finding stands and what is
still open. Update the relevant row in the same commit that changes the
behaviour. What the verifier *does* is specified once, in
`heesch-verifier-architecture.md` (acceptance rule §2.2, pipeline §7/§13,
budgets/profiles §13.5, record procedure §13.9) — this file does not
duplicate it.

Last updated: 2026-08-24 (audit reports archived outside the repo; band settled by runner measurement).

## 1. Snapshot

- Acceptance is fail-closed; a scored entry is a proven non-tiler; the
  harness never executes participant code. Confirmed by the 2026-08-19
  external audit: no false-acceptance route found.
- The record path runs **in-harness** on Blacksmith's
  `blacksmith-32vcpu-ubuntu-2404` runner (128 GB / 1.5 TB, `RUNNER.md`):
  record band `(20,7) (50,4) (100,3) (200,2)` — every `Hc = 5` certificate
  and `Hc = 6, Hh = 6`, to 20 cells — validated end-to-end on the runner
  (16-hex `F(S,7)`: `cake_lpr` 318 s on a 62 MB-xz core). `F(S,8)` was
  **measured out** (core LRAT 2.2 GB xz, `cake_lpr` 3.9 h) → maintainer
  path per §13.9. Guarded by `.github/workflows/record-e2e.yml`.
- Record claims are worded *"accepted by the revision-2 verifier and its
  checked UNSAT proof, conditional on the stated encoder soundness
  obligations"* until the external M1–M9 review (below) is filed.

## 2. Audit tracker

Three external audits (2026-08-11 participant-side vulnerability review
V1–V12/F1–F5, 2026-08-16 comparative audit, 2026-08-19 update audit H1–L15)
are closed: every finding is fixed or accepted with a written reason, each
with a regression test in `tests/`. The audit reports and formal responses
are archived outside the repository (Linear, project "Heesch Challenge");
the fix commits are on `master` (PRs #4, #5, #6 and `0c4b08d`…`0443a37`).
The single open row:

| # | Finding | Severity | Status | Where | Test |
|---|---|---|---|---|---|
| TB | Encoder soundness (M1/M2/M4/M5/M9) needs independent mathematical review | Trust boundary | **OPEN** — external; procedure + reviewer brief + filing format in `soundness-note.md` / `docs/reviews/`; conditional record wording until filed | `docs/soundness-note.md` | round-trip + 46/46 exact-case suites (empirical) |

## 2a. Independent re-verification, 2026-08-20

The six headline items of the external audit were re-verified
adversarially against the code. Verdicts, with what remains:

| Audit item | Verdict | Remaining |
|---|---|---|
| `prove.py --out` escape/clobber | FIXED | The hidden `--worker` self-exec mode now refuses to overwrite any existing file (open mode `x`, tested); nothing remains. |
| `Hc = 5, Hh = 6` passes the limits | FIXED to 20 cells (record profile) | 21+ cells and `(20, 8)` still go through the maintainer path (§3.2); the record path has not yet run on the real runner (§3.1). |
| Malformed input → crash, not rejection | FIXED | Write-side `OSError` during proof/core materialisation and the CNF scratch copy now reject with `RESOURCE_EXCEEDED` (ENOSPC/EDQUOT) or `PROOF_FILE_INVALID`; `--check-proof` reports I/O errors as JSON; the parser enforces ASCII integers (`-?[0-9]+` — Unicode digits, `1_0`, `+1` reject). |
| Proof-format metadata recorded incorrectly | FIXED | Declared-vs-detected enforced before any checker; both recorded. |
| Documented timeout policy ≠ implementation | FIXED | The §13.5 table matches `profile.py` exactly; the stale comments in `proofgate.py` / `profile.py` / `checkers.py` / `benchmark.yml` are corrected; the gate now passes the profile's deadline as the pipeline timeout ceiling, removing the latent 3600 s clip. |
| Encoder soundness externally reviewed | OPEN (unchanged) | Procedure + reviewer packet ready; zero reviews filed (row TB). |

## 3. Open items (all outside the repository)

1. **Install the Blacksmith GitHub App** for this repo (app.blacksmith.sh —
   5-minute admin step, `RUNNER.md`), then dispatch:
   `benchmark.yml` on the baseline (preflight must pass;
   `resource_profile: record` in score.json) → `record-e2e.yml` (the
   acceptance test: an `F(S,7)` proof scored in-harness) → `measure.yml`
   for the `ml-feasibility.md` shapes at `m = 7/8`.
2. **Band status: settled by measurement (2026-08-20 runner run).**
   `F(S,7)` to 20 cells is in-band and validated; `F(S,8)` is out at every
   size (the proof object itself exceeds the submission and checker caps by
   an order of magnitude) — `Hc = 6, Hh = 7` candidates go through the
   maintainer path of architecture §13.9.
   (Superseded expectation, kept for the record: the plan was to admit
   `(20, 8)` after this measurement — the measurement decided the opposite.)
3. **External M1–M9 review** (`soundness-note.md`): gates record
   *announcements*, not scoring; drop the conditional wording in the same
   commit that files the first review.

## 4. How to verify

```
python -m pytest -q                                   # full suite
python -m compileall -q heesch_verify heesch_encoder harness tools
```
CI: `.github/workflows/ci.yml` (Ubuntu + Windows, real checkers on Linux);
`record-e2e.yml` and `measure.yml` on the record runner.
