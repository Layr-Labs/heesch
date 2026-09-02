# Submitting: the participant guide

Everything you need to go from a shape to a scored submission. The verifier
is deterministic and fail-closed: the same file always scores the same, and
nothing scores without proof of non-tilerhood. Normative details live in
`heesch-verifier-architecture.md`; this page is the practical path.

## 1. The loop

```bash
pip install -e .                     # heesch_verify + harness (stdlib-only)
bash tools/build_checkers.sh         # drat-trim, lrat-check (+ cake_lpr on x86-64 Linux)
bash tools/build_solver.sh           # pinned CaDiCaL -> tools/bin/cadical (recommended)
```

1. Write `submission/best.heesch` (shape + witness, §2).
2. `python -m heesch_verify submission/best.heesch` — verifies the witness
   and prints the metrics JSON. Import `heesch_verify.verify_witness` in
   your search loop instead; it is the same code.
3. Unless the shape is inside the census (polyominoes ≤ 10, polyhexes ≤ 8,
   polyiamonds ≤ 12), produce the non-tiler proof:
   `python tools/prove.py submission/best.heesch --check` (§4).
4. Submit via Yukon. The benchmark re-verifies everything from scratch in a
   sandbox and writes `score.json`; any strict score improvement promotes.

## 2. The witness file

```
H 0 0 0 1 1 0 ...            # grid letter + occupied cells (x y pairs)
~ 2 2 1                      # claim: hc=2, hh=2, one patch
19                           # 19 placements follow
0 <1,0,0,0,1,0>              # level 0 = the center copy (identity here; any grid symmetry is legal)
1 <a,b,c,d,e,f>              # corona 1 placements ...
2 <a,b,c,d,e,f>              # corona 2 placements ...
```

- A placement is a corona level plus a transform `x' = a·x+b·y+c,
  y' = d·x+e·y+f` that must be a genuine symmetry of the grid (det ±1 is not
  enough — shears are rejected). Reflections are allowed.
- The patch must be a complete surround: every tile of corona `l` touches
  corona `l−1`, no overlaps, no gaps, no holes in inner coronas. The
  verifier re-derives all of this; the claimed `hc/hh` are checked
  lower-bound style (proving less than you claim scores the weaker value).
- `hh` (hole-permitted coronas) is `hc` or `hc + 1`; with `P = 2` a second
  patch shows the extra hole-permitted corona.
- Limits: ≤ 200 cells, `span_x + span_y ≤ 29`, ≤ 20,000 placements per
  patch, shape file ≤ 2 MiB, plain files (no symlinks). The grammar is
  ASCII: integer tokens are `-?[0-9]+` only (Unicode digits, `1_0`, `+1`
  all reject as `PARSE_SYNTAX`), and `prove.py` additionally enforces
  ASCII on the whole shape file.

## 3. The defect block — scoring between coronas

```text
score = hc_verified + covered fraction of corona hc+1   (fraction < 1)
```

Higher is better. The fraction is partial progress on corona `k+1`:

```
#DEFECT 3 12 12 47           # corona 3, claimed defects (hc/hh views), |required set| = 47
5                            # 5 partial tiles follow
3 <a,b,c,d,e,f>
...
```

The verifier computes the required set of corona `k+1` and counts the cells
your partial tiles fail to cover (plus enclosed pockets). Fewer uncovered
cells → higher fraction (capped below 1). This is the intended competitive
gradient: many submissions can chip away at the same shape's next corona.
A present-but-invalid block rejects the whole submission — leave it out
rather than guessing.

## 4. The proof block — non-tilerhood

Outside the census every scoring submission carries a checked UNSAT proof of
`F(S, m)` — a formula that every real `m`-deep hole-permitted corona
satisfies. So UNSAT ⇒ no such corona ⇒ `Hh ≤ m − 1` ⇒ the shape does not
tile. (The converse is deliberately not claimed: `F` is a relaxation, and a
SAT result proves nothing — it is never treated as evidence.)
`m ≥ hh + 1` is required; `m = hh + 1` also makes your `Hh` exact.

`tools/prove.py` does the whole thing:

```bash
python tools/prove.py submission/best.heesch --check
```

encodes `F(S, hh+1)` with the same frozen encoder the harness uses, solves
it (the CaDiCaL from `tools/build_solver.sh` if built — it streams the proof
to disk, which is what makes record-scale instances feasible; otherwise
python-sat), self-checks the DRAT with drat-trim, extracts the **core
clause list** (the few percent of the formula the proof actually uses — the
harness hands the checkers only those, which is what keeps record-scale
checking fast), writes `proof.lrat.xz` + `core.txt.xz` + the `#PROOF` block,
and with `--check` runs the harness's own gate on the result. Useful flags:
`--m N` (deeper level), `--out NAME`, `--force` (overwrite), `--solver-bin
PATH`, `--profile standard|record` and `--band profile|encoder|none`. The
band flags are precise: with any `--band` other than `none`, `prove.py`
**refuses** a `(cells, m)` outside the encoder's measured feasibility
band; being outside the selected `--profile`'s in-harness proof band only
**warns** (the benchmark job would answer `RESOURCE_EXCEEDED`, but the
proof itself is still producible for a maintainer re-check).

If the solver reports **SAT**, no proof exists at this `m`: the shape has a
deeper hole-permitted corona than your witness shows (find it and re-prove
at a higher `m`) — or it tiles the plane.

Cost scales with `m` and shape size: seconds at `m ≤ 4`, ~10–15 laptop
minutes for a record-scale `F(S,7)` (see `ml-feasibility.md`; the biggest
shapes also want a big-RAM machine or a ~$1 cloud hour for the drat-trim
conversion step). The benchmark runner verifies every `F(S,m)` with `m ≤ 7`
up to 20 cells inside the job — every `Hc = 5` certificate and the `Hc = 6,
Hh = 6` case. An `F(S,8)` proof (the `Hc = 6, Hh = 7` double jump) is
measured beyond the in-job checking budgets — its core proof alone is
~2 GB compressed — and is handled by the maintainers on the identical code
path (architecture §13.9).

## 5. The ladder — how the competition actually progresses

The score is designed so there is always a next increment:

1. **Score 1–3, the on-ramp:** census shapes (polyominoes ≤ 10, hexes ≤ 8,
   iamonds ≤ 12) need no proof — find a deeper witness for a published
   non-tiler. The census maxima are `Hc = 2` (ominoes) and `3` (hexes,
   iamonds), so this band is about building your search loop, not winning.
2. **Score ~4, the proving ground:** the six known `Hc = 4` polyhexes
   (11–17 cells) and the 20-iamond are published *values* without witnesses —
   reconstructing a 4-corona witness and proving `F(S,5)` UNSAT with
   `prove.py` puts you at 4.0 and exercises the full record pipeline.
3. **Score 4.x, the gradient war:** the `#DEFECT` block. Place partial
   corona-5 tiles on your best shape; every additional covered cell of the
   required set is a strictly better score and a promotion. This is where
   most of the leaderboard motion lives — dozens of increments between 4
   and 5, visible to everyone, stealable by anyone with a better partial
   packing of the *same* shape.
4. **Score 5+, the record:** a shape with a verified 5-corona plus its
   `F(S,6)`/`F(S,7)` proof — `record_eligible` in the metrics, a research
   result, and a new chapter for the literature.

It is one linear leaderboard: the platform ranks the single `score` scalar,
`minScoreImprovementBips: 0` means every strict improvement, however small,
promotes — and an equal score does not displace the incumbent, so being
first to a value holds it until someone strictly beats it. (The richer
tie-break ordering in `heesch_verify/score.py` — smaller/tighter shapes
first — is library code for a possible future board, not the live ranking.)

## 6. What `score.json` tells you

`score` (the scalar), and under `metrics`: `hc_verified` / `hh_verified`
(the real Heesch numbers), `non_tiler_evidence` (`census` | `proof`),
`tier` (`lower_bound` | `exact_proof`), `hh_exact` / `exact`,
`record_eligible` / `record_exact` (proof-backed `hc ≥ 5`; also value
pinned), `defect_*` (your partial-corona accounting),
`score_fraction_num` / `score_fraction_den` (the defect fraction as an
exact ratio, present when a defect block scored), `proof_*` (m, digests,
checkers, formats), `resource_profile` (`record` on the benchmark runner),
and `gate_detail` (which gate decided, e.g. `nontiler:census`).

## 7. Rejection codes

Stable API — parse them in your loop. `REJECTED: <CODE>: <detail>` on
stdout, exit 1, no score file.

| code | meaning |
|---|---|
| `PARSE_SYNTAX`, `PARSE_COUNT_MISMATCH`, `PARSE_UNKNOWN_GRID` | malformed file |
| `SHAPE_TOO_LARGE`, `SHAPE_SPAN_EXCEEDED`, `SHAPE_DISCONNECTED`, `SHAPE_HAS_HOLE`, `SHAPE_DUPLICATE_CELL`, `SHAPE_EMPTY` | illegal shape |
| `XFORM_NOT_SYMMETRY`, `XFORM_REFLECTION_BANNED` | transform is not a grid symmetry |
| `PATCH_OVERLAP`, `PATCH_GAP`, `PATCH_HOLE_IN_CORONA`, `PATCH_LEVEL_MISMATCH`, `PATCH_ORPHAN_TILE`, `PATCH_NO_CENTRAL_TILE`, `PATCH_MULTIPLE_CENTRAL` | witness is not a valid surround |
| `DEFECT_*` | invalid partial-corona block |
| `GATE_IS_TILER` | the shape provably tiles the plane |
| `GATE_INCONCLUSIVE` | outside the census and no `#PROOF` block — the fail-closed rule |
| `CENSUS_CONTRADICTION` | witness deeper than the published census value (would mean the verifier or census is wrong; never scored) |
| `PROOF_LEVEL_INCONSISTENT` | `m < hh + 1` |
| `PROOF_CNF_DIGEST_MISMATCH`, `PROOF_HEADER_MISMATCH` | your CNF is not the harness's regenerated `F(S,m)` — re-run `prove.py` at the current encoder revision |
| `PROOF_FILE_INVALID`, `PROOF_FILE_DIGEST_MISMATCH`, `PROOF_TRUNCATED`, `GATE_PROOF_INVALID` | proof file missing/corrupt/wrong format/does not verify |
| `CHECKER_UNAVAILABLE` | checker binaries missing on the host (not your bug) |
| `RESOURCE_EXCEEDED` | outside the (cells, m) band or a size/time cap — see the profile table in the architecture doc §13.5 |

(`DUPLICATE` and `CLAIM_BELOW_THRESHOLD` exist in the error-code enum for
the leaderboard-store library; the benchmark job itself never emits them.)

## 8. Troubleshooting

- **`--check` says `CHECKER_UNAVAILABLE` on macOS/ARM:** `cake_lpr` only
  builds on x86-64 Linux; the benchmark runner has it. Your DRAT/LRAT was
  still self-checked with drat-trim.
- **`prove.py` is slow or out of memory:** build the external solver
  (`tools/build_solver.sh`) — the python-sat path holds the whole proof in
  memory and is not viable at record scale.
- **Score didn't improve:** the board takes any strict improvement; check
  `metrics.defect_hc` — fewer uncovered cells on the same shape is enough.
- **Same file, different machine, same score?** Yes — scoring is
  deterministic by construction; if you ever observe otherwise, that is a
  bug we want reported.
