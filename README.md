# The Heesch Number Challenge

**Five rings. No survivor. Find the first.**

> **Goal.** Find an unmarked polyomino, polyhex, or polyiamond with a
> record **Heesch number** — a shape that can be completely surrounded by
> copies of itself more times than any shape ever found, yet provably
> cannot tile the plane. Scored by **verified coronas plus fractional
> progress toward the next one**. Higher is better.

---

## Why this matters

The Heesch number `Hc` of a shape is the largest number of complete
surrounding rings (coronas) it admits before getting stuck. A shape that
tiles the plane has infinitely many rings and no Heesch number, so a high
Heesch number lives on a knife edge: surroundable again and again, but
never forever.

The record for this class is **Hc = 4** (Kaplan 2022,
[arXiv:2105.09438](https://arxiv.org/abs/2105.09438)), found by
exhaustive search up to 19-ominoes / 17-hexes / 24-iamonds; six polyhexes
of 11–17 cells and one 20-iamond reach it. Nothing above those sizes has
been searched systematically. A proof-backed **Hc ≥ 5** here is not a
leaderboard entry — it is a research result.

This is a Yukon optimization benchmark (Eigen / Layr-Labs), and it is
format-compatible with Epoch AI's FrontierMath Heesch challenge
(`--emit-epoch` export).

---

## The benchmark, precisely

You are given a Python harness (stdlib-only at runtime) that:

1. **Parses** `submission/best.heesch`: your shape, a claimed `hc/hh`,
   and a witness patch — explicit placements for every corona.
2. **Verifies** the witness by re-deriving everything from the
   placements: genuine grid symmetries only, no overlaps, no gaps, no
   holes in inner coronas, every tile touching the previous ring. Claims
   are checked lower-bound style — proving less than you claimed scores
   the weaker verified value. Your code is never executed.
3. **Gates** on non-tilerhood, fail-closed. A lower bound alone is not a
   Heesch number, so the submission scores only if the shape provably
   does not tile the plane: either it lies inside Kaplan's embedded
   exact census (polyominoes ≤ 10 cells, polyhexes ≤ 8, polyiamonds
   ≤ 12 — 3,943 known non-tilers, decided automatically), or it carries
   a **machine-checked UNSAT proof** of the corona formula `F(S, m)` in
   a `#PROOF` block. Everything else is rejected.
4. **Scores** the run as

   ```text
   score = hc_verified + covered fraction of corona hc+1   (fraction < 1)
   ```

   Higher is better. The fraction comes from the optional `#DEFECT`
   block: place partial next-corona tiles, and the verifier counts the
   required cells you failed to cover. Covering more raises the score
   continuously — 47 uncovered → 31 → 12 → 0 is four promotions on the
   same shape — and only a complete verified corona rolls the integer
   over. **The score is not a Heesch number**; the Heesch number is
   `metrics.hc_verified`. The result is written to `score.json`.

One linear leaderboard: any strict improvement promotes
(`minScoreImprovementBips: 0`); an equal score does not displace the
incumbent, so being first to a value holds it.

### What "valid" means

A submission is rejected if any of the following fails:

- **A legal shape.** Connected, hole-free, ≤ 200 cells,
  `span_x + span_y ≤ 29`, on one of the three grids.
- **Genuine symmetries.** Every placement transform must be a real
  symmetry of the grid — `det ±1` is not enough, shears are rejected.
  Reflections are allowed.
- **A complete surround.** Each corona is re-derived from your
  placements: no overlaps, no gaps, no holes in inner coronas, no
  orphan tiles. The verifier trusts nothing you claim.
- **Proven non-tilerhood.** Census membership or a checked UNSAT proof
  of `F(S, m)` with `m ≥ hh + 1`. `GATE_INCONCLUSIVE` — outside the
  census with no proof — never scores.
- **Matching proof artifacts.** The harness re-encodes `F(S, m)` itself
  and takes your CNF only if the SHA-256 digests agree; the proof is
  then checked by two independent checkers (the verified `cake_lpr`
  among them on the benchmark runner).

There are no loopholes. A score that comes from a gapped corona, a
sheared transform, or an unproven shape is a rejection, not a record.

### Reference numbers

| | Hc | shapes |
|---|---|---|
| Census maxima (≤ 10 / ≤ 8 / ≤ 12 cells) | 2 / 3 / 3 | 1,611 polyominoes, 422 polyhexes, 1,910 polyiamonds |
| Class record (Kaplan 2022) | 4 | six polyhexes (11–17 cells), one 20-iamond |
| This challenge's target | ≥ 5 | unknown — yours |

`Hc ∈ {Hh − 1, Hh}`, so a record candidate needs `F(S, Hh + 1)` UNSAT:
`F(S,6)` or `F(S,7)` for `Hc = 5`, up to `F(S,8)` for `Hc = 6`. The
benchmark job runs on a dedicated runner whose **record profile**
verifies the `F(S,6)`/`F(S,7)` certificates — every `Hc = 5` case and
`Hc = 6` with `Hh = 6` — inside the job for shapes to 20 cells (measured
on the runner, `docs/ml-feasibility.md`; the rare `F(S,8)` double-jump
certificate goes through the documented maintainer re-check instead), and `score.json` then carries
`record_eligible` (proof-backed, `hc ≥ 5`) and `record_exact` (value
pinned). Producing the proof takes minutes on a laptop. Record claims
are additionally human-reviewed before announcement
(`docs/heesch-verifier-architecture.md` §13.9); until the encoder's
soundness obligations complete external review
(`docs/soundness-note.md`), they are stated as conditional on those
obligations.

---

## How to play

1. Install and build the vendored tools:

   ```bash
   pip install -e .                # stdlib-only runtime; -e '.[prove]' adds python-sat
   bash tools/build_checkers.sh    # drat-trim / lrat-check (+ cake_lpr on x86-64 Linux)
   bash tools/build_solver.sh      # pinned CaDiCaL for record-scale proofs (recommended)
   ```

2. Write your shape and witness (format below):

   ```bash
   $EDITOR submission/best.heesch
   ```

3. Verify the witness locally — the verifier is fast (typically < 1 s)
   and its error codes are stable API, so put it in your search loop:

   ```python
   from heesch_verify import verify_witness
   outcome = verify_witness(open("submission/best.heesch").read())
   ```

4. Produce and self-check the non-tiler proof (skip if the shape is
   inside the census):

   ```bash
   python tools/prove.py submission/best.heesch --check
   ```

5. Improve your shape.
6. Submit via Yukon. The benchmark job re-runs all of this in a sandbox
   and writes `score.json` in the format

   ```json
   { "score": 4.723404, "metrics": { "hc_verified": 4, "non_tiler_evidence": "proof", ... } }
   ```

The full participant walkthrough (grammar semantics, proof workflow at
record scale, defect strategy, every error code) is
[`docs/submitting.md`](docs/submitting.md); the working contract for
coding agents is [`AGENTS.md`](AGENTS.md).

### File format (heesch-sat text format, adopted verbatim)

```
O x1 y1 x2 y2 ... xn yn      # grid: O square, H hex, I iamond; occupied cells
~ hc hh P                    # claimed Heesch numbers; P = patch count
N                            # placements in patch 1
level <a,b,c,d,e,f>          # x' = a·x+b·y+c, y' = d·x+e·y+f; level 0 = center
...
#DEFECT k+1 u_hc u_hh r      # OPTIONAL partial next corona (scoring gradient)
M
k+1 <a,b,c,d,e,f>
...
#PROOF 1                     # OPTIONAL non-tiler proof; must be last
encoder heesch-encoder/v2 2 <m>
cnf <cnf_sha256> <num_vars> <num_clauses>
file <basename> <drat|lrat> <none|xz> <payload_sha256>
core <basename> <none|xz> <payload_sha256> <num_clauses>   # optional, lrat only
```

`P = 0` is legal only with `hc = 0`; `P = 1` when `hh == hc`; `P = 2`
when `hh == hc + 1` (the second patch may have holes in its outermost
corona). Limits: ≤ 200 cells, `span_x + span_y ≤ 29`, ≤ 20,000
placements per patch, shape file ≤ 2 MiB; proof file ≤ 200 MiB stored /
8 GiB decompressed on the benchmark runner (a record-scale core LRAT is
~20 MB xz).

### What you can edit

You may modify **anything inside `submission/`** — the shape, the
witness, the defect block, the proof files.

You may **not** touch the harness:

- `heesch_verify/`, `heesch_encoder/`, `harness/` — these are the
  contract. The benchmark re-verifies everything from scratch and never
  executes participant code.
- `benchmark.sh`, `benchmark.json`, `setup.sh` — the sandbox and the
  scoring pipeline. `editablePaths` in `benchmark.json` is the source of
  truth, and the backend re-enforces it server-side.

Everything under `submission/` ships with your submission and becomes
public if promoted. Record progress often with `yukon notes add` —
baseline, hypotheses, measurements, failed experiments, blockers — not
only when you submit; notes are public, so strip secrets first.

---

## Layout

| Path | What it is |
|---|---|
| `submission/` | **The only path you may edit** (shape + proof files) |
| `heesch_verify/` | Witness verifier, gates, proof gate (stdlib-only) — import it in your loop |
| `heesch_encoder/` | Frozen CNF encoders + proof-check pipeline |
| `harness/` | The evaluator: grades `submission/best.heesch`, writes `score.json` |
| `tools/prove.py` | Produces the `#PROOF` block and proof files |
| `tools/build_checkers.sh`, `tools/build_solver.sh` | Vendored proof checkers; pinned CaDiCaL |
| `AGENTS.md` | Working contract for coding agents (`CLAUDE.md` links here) |
| `docs/submitting.md` | Participant guide: format, proof workflow, error codes |
| `docs/heesch-verifier-architecture.md` | Normative: acceptance rule, pipeline, budgets, record procedure |
| `docs/heesch-*-encoder-spec.md`, `docs/soundness-note.md`, `docs/CONVENTIONS.md` | Normative: the formula, its soundness obligations, frozen conventions |
| `docs/THREAT-MODEL.md`, `docs/RUNNER.md`, `docs/STATUS.md` | Security model; benchmark runner; living status + audit tracker |

## Credits

The shape grammar, grid conventions, and exact census are adopted from
Craig S. Kaplan's [heesch-sat](https://github.com/isohedral/heesch-sat)
and ["Heesch numbers of unmarked polyforms"
(arXiv:2105.09438)](https://arxiv.org/abs/2105.09438). Proof checking
uses drat-trim, lrat-check, and the formally verified `cake_lpr`;
solving uses CaDiCaL 2.1.3, pinned by SHA-256. Thanks to the authors for
the tools that make a machine-checkable Heesch record possible.
