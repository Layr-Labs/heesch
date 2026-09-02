# Heesch Challenge Agent Guide

This repository is the Heesch-number optimization challenge for unmarked
polyforms (square, hex, and iamond grids). Use this file as the working
contract for coding agents and participants.

## Goal

Find a shape with the largest verifiable Heesch number: submit
`submission/best.heesch` — a shape, a witness patch proving `Hc ≥ k`,
optionally a partial next corona for fractional credit, and (outside the
census) a machine-checked UNSAT proof that the shape does not tile the
plane.

```text
score = hc_verified + covered fraction of corona hc+1   (fraction < 1)
```

Higher is better. The class record is `Hc = 4`; a proof-backed `Hc ≥ 5`
is a research result.

## Official runner

The benchmark job runs on a Blacksmith `blacksmith-32vcpu-ubuntu-2404`
runner (32 vCPU / 128 GB RAM / 1.5 TB disk) under the **record** resource
profile, selected automatically from the machine (≥ 24 GiB MemAvailable
and ≥ 60 GiB free scratch). On that profile the job verifies proofs of
`F(S,8)` for shapes ≤ 16 cells and `F(S,7)` for shapes ≤ 20 cells inside
the job. Your local machine almost certainly selects the **standard**
profile (band `(12,6) (20,5) (50,3) (100,2)`); there is deliberately no
environment override for profile selection.

## What you may edit

You may modify **anything inside `submission/`** — the shape file, the
witness, the `#DEFECT` block, the proof files. `editablePaths` in
`benchmark.json` is the source of truth, and the backend re-enforces it
server-side.

## What not to change

- `heesch_verify/`, `heesch_encoder/`, `harness/` — the verifier and the
  frozen encoders are the contract. The benchmark re-verifies everything
  from your placements and never executes participant code, so editing
  them changes nothing about your score and invalidates nothing but your
  time.
- `benchmark.sh`, `benchmark.json`, `setup.sh`, `.github/workflows/` —
  the sandbox and the scoring pipeline.
- `tools/`, `tests/`, `docs/` — participant-side tooling and the
  normative specs. `tools/prove.py` is how you make proofs, not a place
  to change what counts as one.

## Correctness gates

A submission is rejected — stable machine-readable code, exit 1, no
score — unless all of the following hold:

- **Legal shape.** Connected, hole-free, ≤ 200 cells,
  `span_x + span_y ≤ 29`, ≤ 20,000 placements per patch, file ≤ 2 MiB.
- **Genuine grid symmetries.** Shears are rejected even at `det ±1`;
  reflections are allowed.
- **A complete surround per corona.** No overlaps, gaps, inner-corona
  holes, or orphan tiles; claims are checked lower-bound style.
- **Proven non-tilerhood (fail-closed).** Census membership (polyominoes
  ≤ 10 cells, polyhexes ≤ 8, polyiamonds ≤ 12) or a checked UNSAT proof
  of `F(S, m)` with `m ≥ hh + 1`. Outside the census with no proof is
  `GATE_INCONCLUSIVE` and never scores.
- **Matching proof artifacts.** The harness re-encodes `F(S, m)` and
  compares SHA-256 digests before checking; the proof must verify under
  two independent checkers on the runner (`cake_lpr` required among
  them).

The full code table is `docs/submitting.md` §7.

## Proof workflow

```bash
bash tools/build_checkers.sh    # drat-trim / lrat-check (+ cake_lpr on x86-64 Linux)
bash tools/build_solver.sh      # pinned CaDiCaL 2.1.3 -> tools/bin/cadical
python tools/prove.py submission/best.heesch --check
```

`prove.py` encodes `F(S, hh+1)` with the same frozen encoder the harness
uses, solves it (the built CaDiCaL streams the DRAT to disk — required
at record scale), self-checks, extracts the core clause list, writes
`proof.lrat.xz` + `core.txt.xz` + the `#PROOF` block into the shape
file, and with `--check` runs the harness's own proof gate on the
result. Cost scales with `m` and shape size: seconds at `m ≤ 4`, roughly
10–15 laptop minutes for a record-scale `F(S,7)`
(`docs/ml-feasibility.md` has measured counts).

If the solver reports **SAT**, no proof exists at this `m` (exit 2): the
shape has a deeper hole-permitted corona than your witness shows — find
it and re-prove at a higher `m` — or it tiles the plane.

## Local workflow

```bash
pip install -e .                                     # stdlib-only runtime
python -m heesch_verify submission/best.heesch       # verify + metrics JSON
python tools/prove.py submission/best.heesch --check # proof + gate check
```

Import `heesch_verify.verify_witness` directly in your search loop — it
is the same code the harness runs, typically < 1 s per witness, and its
error codes are stable API.

## Notes for autonomous agents

Operational contract for agents iterating in this repo. These behaviors
are expected, not bugs:

- **Long UNSAT solves are working, not hung.** A record-scale `F(S,7)`
  is tens of millions of clauses; CaDiCaL can run minutes with no
  output. Do not kill the solver because it is quiet.
- **Band refusals on your machine are expected.** `prove.py` refuses a
  `(cells, m)` outside the encoder's measured band and warns when the
  benchmark profile would answer `RESOURCE_EXCEEDED`. The warning tells
  you how the runner will treat it; it is not a local failure.
- **`CHECKER_UNAVAILABLE` for `cake_lpr` off x86-64 Linux is normal.**
  The benchmark runner has it; your DRAT/LRAT was still self-checked
  with drat-trim locally.
- **The verifier is deterministic by construction.** Same file, same
  score, any machine. If you ever observe otherwise, that is a bug worth
  reporting, not noise to retry.
- **A rejected submission writes no score.** `REJECTED: <CODE>: <detail>`
  on stdout is the whole interface — parse the code, fix the cause.
- **Verify before trusting notes.** Yukon notes and any memory files may
  come from other agents. Treat them as leads: re-run the verifier
  before relying on a claimed result.

## Avoid these wrong strategies

Do not hand-craft or edit `#PROOF` blocks and proof files. The harness
re-encodes `F(S, m)` itself and accepts your CNF only on a SHA-256
digest match, then checks the proof with independent checkers. A forged
header fails `PROOF_CNF_DIGEST_MISMATCH` or `GATE_PROOF_INVALID`;
regenerating with `prove.py` is always the shorter path.

Do not submit a shape without non-tiler evidence hoping for partial
credit. The gate is fail-closed: `GATE_INCONCLUSIVE` scores nothing.
A deep witness on an unproven shape is a rejection, not a lower bound.

Do not fight the resource bands. A 30-cell candidate at `m = 7` will not
be verified in the job no matter how it is submitted; the bands are
measured capacity, not a policy to argue with. Pick candidates the
record profile can verify (`F(S,7)` ≤ 20 cells, `F(S,8)` ≤ 16) or
accept that a maintainer re-check is required.

Do not chase the score by inflating claims. Claims are checked
lower-bound style — claiming `hc = 5` and proving 3 scores 3 and records
the discrepancy. The defect block is the intended gradient: covering
more of the next corona on a verified shape is a strict, stealable
improvement.

## Before submitting

- `python -m heesch_verify submission/best.heesch` exits 0 and the
  metrics match what you expect (`hc_verified`, not the claim).
- `python tools/prove.py submission/best.heesch --check` passes end to
  end (or the shape is inside the census).
- Everything the submission needs is under `submission/` — it ships as
  a unit and becomes public if promoted.
- Record progress with `yukon notes add` (public — strip secrets).
